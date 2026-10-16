// screen-listen helper: record the audio output of one running application (matched by bundle
// id) to a WAV file through a Core Audio process tap, never the microphone and never the screen.
//
//   screen-listen processes                         -> {"ok":true,"data":[{pid,bundle,running_output}]}
//   screen-listen record (--bundle ID [--prefix] | --pid PID) --seconds N --out FILE
//                                                   -> {"ok":true,"data":{...}} | {"ok":false,"kind","error"}
//
// Core Audio registers audio under the responsible process (what launched the app), so a
// bundle id matches the app's own process objects; ``--pid`` serves diagnostics.
//
// One JSON object on stdout, nothing else. The first `record` on this machine makes macOS ask
// for "System Audio Recording" for the app bundle this binary lives in (NSAudioCaptureUsageDescription
// in the bundle's Info.plist). The process tap API needs macOS 14.2 or later.

import AVFoundation
import CoreAudio
import Foundation

let maxSeconds = 3600.0
nonisolated(unsafe) var stopRequested: Int32 = 0   // set by a signal handler, read by the wait loop

struct Failure: Error {
    let kind: String
    let message: String
}

func emit(_ object: [String: Any]) {
    let data = try! JSONSerialization.data(withJSONObject: object, options: [.sortedKeys])
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write("\n".data(using: .utf8)!)
}

func fail(_ kind: String, _ message: String) -> Never {
    emit(["ok": false, "kind": kind, "error": message])
    exit(1)
}

// MARK: - Core Audio property helpers

func address(_ selector: AudioObjectPropertySelector) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: selector, mScope: kAudioObjectPropertyScopeGlobal,
                               mElement: kAudioObjectPropertyElementMain)
}

func read<T>(_ object: AudioObjectID, _ selector: AudioObjectPropertySelector, _ initial: T) throws -> T {
    var addr = address(selector)
    var size = UInt32(MemoryLayout<T>.size)
    var value = initial
    let status = withUnsafeMutablePointer(to: &value) { pointer in
        AudioObjectGetPropertyData(object, &addr, 0, nil, &size, UnsafeMutableRawPointer(pointer))
    }
    guard status == noErr else { throw Failure(kind: "coreaudio", message: "property \(selector) failed (\(status))") }
    return value
}

func readString(_ object: AudioObjectID, _ selector: AudioObjectPropertySelector) throws -> String {
    var addr = address(selector)
    var size = UInt32(MemoryLayout<CFString?>.size)
    var value: Unmanaged<CFString>?
    let status = AudioObjectGetPropertyData(object, &addr, 0, nil, &size, &value)
    guard status == noErr, let string = value?.takeRetainedValue() else { return "" }
    return string as String
}

func readArray(_ object: AudioObjectID, _ selector: AudioObjectPropertySelector) throws -> [AudioObjectID] {
    var addr = address(selector)
    var size: UInt32 = 0
    var status = AudioObjectGetPropertyDataSize(object, &addr, 0, nil, &size)
    guard status == noErr else { throw Failure(kind: "coreaudio", message: "property size \(selector) failed (\(status))") }
    var ids = [AudioObjectID](repeating: 0, count: Int(size) / MemoryLayout<AudioObjectID>.size)
    status = AudioObjectGetPropertyData(object, &addr, 0, nil, &size, &ids)
    guard status == noErr else { throw Failure(kind: "coreaudio", message: "property \(selector) failed (\(status))") }
    return ids
}

struct AudioProcess {
    let object: AudioObjectID
    let pid: pid_t
    let bundle: String
    let runningOutput: Bool
}

func audioProcesses() throws -> [AudioProcess] {
    let system = AudioObjectID(kAudioObjectSystemObject)
    return try readArray(system, kAudioHardwarePropertyProcessObjectList).compactMap { object in
        guard let pid = try? read(object, kAudioProcessPropertyPID, pid_t(0)) else { return nil }
        let bundle = (try? readString(object, kAudioProcessPropertyBundleID)) ?? ""
        let running = ((try? read(object, kAudioProcessPropertyIsRunningOutput, UInt32(0))) ?? 0) != 0
        return AudioProcess(object: object, pid: pid, bundle: bundle, runningOutput: running)
    }
}

func matches(_ process: AudioProcess, bundle: String, prefix: Bool) -> Bool {
    if prefix {
        return process.bundle == bundle || process.bundle.hasPrefix(bundle + ".")
    }
    return process.bundle == bundle
}

// MARK: - Recording

final class Recorder {
    private var tap = AudioObjectID(kAudioObjectUnknown)
    private var aggregate = AudioObjectID(kAudioObjectUnknown)
    private var ioProc: AudioDeviceIOProcID?
    private var file: AVAudioFile?
    private let queue = DispatchQueue(label: "screen-listen.io")
    private(set) var frames: Int64 = 0
    private(set) var peak: Float = 0
    private(set) var writeError: String?
    private(set) var sampleRate: Double = 0
    private(set) var channels: Int = 0

    func start(processes: [AudioObjectID], output: URL) throws {
        let description = CATapDescription(stereoMixdownOfProcesses: processes)
        description.uuid = UUID()
        description.name = "screen-listen"
        description.isPrivate = true
        description.isExclusive = false
        description.muteBehavior = .unmuted
        var status = AudioHardwareCreateProcessTap(description, &tap)
        guard status == noErr, tap != kAudioObjectUnknown else {
            throw Failure(kind: "permission", message: "could not create the process tap (\(status)); "
                          + "System Audio Recording may be refused for this helper")
        }

        let system = AudioObjectID(kAudioObjectSystemObject)
        let outputDevice = try read(system, kAudioHardwarePropertyDefaultSystemOutputDevice, AudioObjectID(0))
        let outputUID = try readString(outputDevice, kAudioDevicePropertyDeviceUID)
        let aggregateDescription: [String: Any] = [
            kAudioAggregateDeviceNameKey: "screen-listen",
            kAudioAggregateDeviceUIDKey: UUID().uuidString,
            kAudioAggregateDeviceMainSubDeviceKey: outputUID,
            kAudioAggregateDeviceIsPrivateKey: true,
            kAudioAggregateDeviceIsStackedKey: false,
            kAudioAggregateDeviceTapAutoStartKey: true,
            kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: outputUID]],
            kAudioAggregateDeviceTapListKey: [[kAudioSubTapUIDKey: description.uuid.uuidString,
                                               kAudioSubTapDriftCompensationKey: true]],
        ]
        status = AudioHardwareCreateAggregateDevice(aggregateDescription as CFDictionary, &aggregate)
        guard status == noErr, aggregate != kAudioObjectUnknown else {
            throw Failure(kind: "coreaudio", message: "could not create the aggregate device (\(status))")
        }

        var asbd = try read(tap, kAudioTapPropertyFormat, AudioStreamBasicDescription())
        guard let format = AVAudioFormat(streamDescription: &asbd) else {
            throw Failure(kind: "coreaudio", message: "the tap reported no usable stream format")
        }
        sampleRate = format.sampleRate
        channels = Int(format.channelCount)
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: format.sampleRate,
            AVNumberOfChannelsKey: format.channelCount,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsNonInterleaved: false,
        ]
        file = try AVAudioFile(forWriting: output, settings: settings, commonFormat: .pcmFormatFloat32,
                               interleaved: format.isInterleaved)

        status = AudioDeviceCreateIOProcIDWithBlock(&ioProc, aggregate, queue) { [weak self] _, input, _, _, _ in
            guard let self, let file = self.file else { return }
            guard let buffer = AVAudioPCMBuffer(pcmFormat: format, bufferListNoCopy: input, deallocator: nil),
                  buffer.frameLength > 0 else { return }
            self.frames += Int64(buffer.frameLength)
            if let data = buffer.floatChannelData {
                // ``stride`` is 1 for planar buffers and the channel count for interleaved ones, so
                // ``data[channel][i * stride]`` is sample ``i`` of that channel in either layout.
                let stride = buffer.stride
                for channel in 0..<Int(buffer.format.channelCount) {
                    let samples = data[channel]
                    for i in 0..<Int(buffer.frameLength) {
                        let magnitude = abs(samples[i * stride])
                        if magnitude > self.peak { self.peak = magnitude }
                    }
                }
            }
            do { try file.write(from: buffer) } catch { self.writeError = "\(error)" }
        }
        guard status == noErr, ioProc != nil else {
            throw Failure(kind: "coreaudio", message: "could not create the IO proc (\(status))")
        }
        status = AudioDeviceStart(aggregate, ioProc)
        guard status == noErr else {
            throw Failure(kind: "coreaudio", message: "could not start the aggregate device (\(status))")
        }
    }

    func stop() {
        if let ioProc {
            AudioDeviceStop(aggregate, ioProc)
            AudioDeviceDestroyIOProcID(aggregate, ioProc)
            self.ioProc = nil
        }
        if aggregate != kAudioObjectUnknown {
            AudioHardwareDestroyAggregateDevice(aggregate)
            aggregate = kAudioObjectUnknown
        }
        if tap != kAudioObjectUnknown {
            AudioHardwareDestroyProcessTap(tap)
            tap = kAudioObjectUnknown
        }
        queue.sync { file = nil }
    }
}

// MARK: - Commands

func option(_ name: String, _ args: [String]) -> String? {
    guard let index = args.firstIndex(of: name), index + 1 < args.count else { return nil }
    return args[index + 1]
}

func commandProcesses() {
    do {
        let list = try audioProcesses().map { p -> [String: Any] in
            ["pid": Int(p.pid), "bundle": p.bundle, "running_output": p.runningOutput]
        }
        emit(["ok": true, "data": list])
    } catch let failure as Failure {
        fail(failure.kind, failure.message)
    } catch {
        fail("coreaudio", "\(error)")
    }
}

func commandRecord(_ args: [String]) {
    let bundle = option("--bundle", args) ?? ""
    let pid = pid_t(option("--pid", args) ?? "") ?? 0
    guard !bundle.isEmpty || pid > 0 else { fail("usage", "--bundle or --pid is required") }
    guard let secondsText = option("--seconds", args), let seconds = Double(secondsText), seconds > 0,
          seconds <= maxSeconds else { fail("usage", "--seconds must be between 0 and \(Int(maxSeconds))") }
    guard let outPath = option("--out", args), outPath.hasPrefix("/") else { fail("usage", "--out must be an absolute path") }
    let prefix = args.contains("--prefix")
    let output = URL(fileURLWithPath: outPath)
    if FileManager.default.fileExists(atPath: outPath) { fail("usage", "--out already exists") }

    let processes: [AudioProcess]
    do {
        processes = try audioProcesses().filter {
            pid > 0 ? $0.pid == pid : matches($0, bundle: bundle, prefix: prefix)
        }
    } catch let failure as Failure {
        fail(failure.kind, failure.message)
    } catch {
        fail("coreaudio", "\(error)")
    }
    let wanted = pid > 0 ? "pid \(pid)" : "bundle id \(bundle)"
    guard !processes.isEmpty else { fail("no_process", "no running process with \(wanted) is registered with Core Audio") }

    let recorder = Recorder()
    let started = Date()
    do {
        try recorder.start(processes: processes.map(\.object), output: output)
    } catch let failure as Failure {
        recorder.stop()
        try? FileManager.default.removeItem(at: output)
        fail(failure.kind, failure.message)
    } catch {
        recorder.stop()
        try? FileManager.default.removeItem(at: output)
        fail("coreaudio", "\(error)")
    }
    // A signal ends the recording early but cleanly: the WAV is finalized and the tap torn down.
    signal(SIGINT) { _ in stopRequested = 1 }
    signal(SIGTERM) { _ in stopRequested = 1 }
    let deadline = started.addingTimeInterval(seconds)
    while stopRequested == 0 && Date() < deadline {
        Thread.sleep(forTimeInterval: min(0.1, max(0, deadline.timeIntervalSinceNow)))
    }
    recorder.stop()
    let elapsed = Date().timeIntervalSince(started)
    if let writeError = recorder.writeError {
        fail("io", "writing the WAV failed: \(writeError)")
    }
    let size = (try? FileManager.default.attributesOfItem(atPath: outPath)[.size] as? Int) ?? 0
    emit(["ok": true, "data": [
        "file": outPath,
        "bytes": size,
        "seconds": (elapsed * 100).rounded() / 100,
        "stopped_early": stopRequested != 0,
        "frames": recorder.frames,
        "sample_rate": recorder.sampleRate,
        "channels": recorder.channels,
        "peak": (Double(recorder.peak) * 10000).rounded() / 10000,
        "silent": recorder.peak < 0.001,
        "processes": processes.map { ["pid": Int($0.pid), "bundle": $0.bundle, "running_output": $0.runningOutput] },
    ]])
}

let arguments = Array(CommandLine.arguments.dropFirst())
switch arguments.first {
case "processes":
    commandProcesses()
case "record":
    commandRecord(Array(arguments.dropFirst()))
default:
    fail("usage", "commands: processes | record (--bundle ID [--prefix] | --pid PID) --seconds N --out FILE")
}
