// screen-listen helper: record the audio output of one running application (matched by bundle
// id) to a WAV file through a Core Audio process tap, never the microphone and never the screen.
//
//   screen-listen processes                         -> {"ok":true,"data":[{pid,bundle,running_output}]}
//   screen-listen record (--bundle ID [--prefix] | --pid PID) --seconds N --out FILE
//                        [--mono] [--progress FILE]
//                                                   -> {"ok":true,"data":{...}} | {"ok":false,"kind","error"}
//
// Core Audio registers one process object per process that plays, with that process's own
// bundle id, so an app's helper processes (``<bundle>.helper`` and the like) are matched with
// ``--prefix``; ``--pid`` serves diagnostics. ``--mono``
// mixes the processes down to one channel (voice recordings; half the bytes). ``--progress``
// rewrites a small JSON file every few seconds (pid, seconds, frames, peak, whether audio
// arrived since the last write) so a long recording can be watched and stopped from outside:
// SIGTERM ends it cleanly, with the WAV finalized and the final JSON on stdout.
//
// One JSON object on stdout, nothing else. The first `record` on this machine makes macOS ask
// for "System Audio Recording" for the app bundle this binary lives in (NSAudioCaptureUsageDescription
// in the bundle's Info.plist). The process tap API needs macOS 14.2 or later.

import AVFoundation
import CoreAudio
import Foundation

let maxSeconds = 4 * 3600.0
let progressInterval = 2.0
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
    // Sound, as distinct from level: 100 ms blocks whose peak clears ``activeThreshold`` are counted,
    // so a join chime in a minute of silence reads as a fraction of a second, not as a loud take.
    private(set) var activeBlocks: Int64 = 0
    private var blockFrames: Int64 = 0
    private var blockPeak: Float = 0
    private let activeThreshold: Float = 0.01
    var activeSeconds: Double { Double(activeBlocks) * 0.1 }

    func start(processes: [AudioObjectID], output: URL, mono: Bool) throws {
        let description = mono ? CATapDescription(monoMixdownOfProcesses: processes)
                               : CATapDescription(stereoMixdownOfProcesses: processes)
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
                // Locals inside the loop: a stored property per sample would cost an exclusivity
                // check each on the realtime thread.
                let stride = buffer.stride
                let channels = Int(buffer.format.channelCount)
                let block = max(Int64(1), Int64(format.sampleRate / 10))
                var peak = self.peak, blockPeak = self.blockPeak, blockFrames = self.blockFrames
                var activeBlocks = self.activeBlocks
                for i in 0..<Int(buffer.frameLength) {
                    for channel in 0..<channels {
                        let magnitude = abs(data[channel][i * stride])
                        if magnitude > peak { peak = magnitude }
                        if magnitude > blockPeak { blockPeak = magnitude }
                    }
                    blockFrames += 1
                    if blockFrames >= block {
                        if blockPeak > self.activeThreshold { activeBlocks += 1 }
                        blockFrames = 0
                        blockPeak = 0
                    }
                }
                self.peak = peak
                self.blockPeak = blockPeak
                self.blockFrames = blockFrames
                self.activeBlocks = activeBlocks
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
    let mono = args.contains("--mono")
    let output = URL(fileURLWithPath: outPath)
    if FileManager.default.fileExists(atPath: outPath) { fail("usage", "--out already exists") }
    let progressPath = option("--progress", args)
    if let progressPath, !progressPath.hasPrefix("/") { fail("usage", "--progress must be an absolute path") }

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
        try recorder.start(processes: processes.map(\.object), output: output, mono: mono)
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
    var lastProgress = Date.distantPast
    var lastFrames: Int64 = 0
    func writeProgress(final: Bool) {
        guard let progressPath else { return }
        let now = Date()
        let frames = recorder.frames
        let object: [String: Any] = [
            "pid": Int(getpid()), "seconds": (now.timeIntervalSince(started) * 10).rounded() / 10,
            "frames": frames, "receiving": frames > lastFrames,
            "peak": (Double(recorder.peak) * 10000).rounded() / 10000, "final": final,
            "active_seconds": (recorder.activeSeconds * 10).rounded() / 10,
            "updated": ISO8601DateFormatter().string(from: now)]
        if let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) {
            // .atomic writes beside and renames over, so a reader never sees a half-written file.
            try? data.write(to: URL(fileURLWithPath: progressPath), options: .atomic)
        }
        lastProgress = now
        lastFrames = frames
    }
    writeProgress(final: false)
    while stopRequested == 0 && Date() < deadline {
        Thread.sleep(forTimeInterval: min(0.1, max(0, deadline.timeIntervalSinceNow)))
        if Date().timeIntervalSince(lastProgress) >= progressInterval { writeProgress(final: false) }
    }
    recorder.stop()
    let elapsed = Date().timeIntervalSince(started)
    if let writeError = recorder.writeError {
        writeProgress(final: true)
        fail("io", "writing the WAV failed: \(writeError)")
    }
    writeProgress(final: true)
    let size = (try? FileManager.default.attributesOfItem(atPath: outPath)[.size] as? Int) ?? 0
    emit(["ok": true, "data": [
        "file": outPath,
        "pid": Int(getpid()),
        "bytes": size,
        "seconds": (elapsed * 100).rounded() / 100,
        "stopped_early": stopRequested != 0,
        "frames": recorder.frames,
        "sample_rate": recorder.sampleRate,
        "channels": recorder.channels,
        "peak": (Double(recorder.peak) * 10000).rounded() / 10000,
        "active_seconds": (recorder.activeSeconds * 10).rounded() / 10,
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
    fail("usage", "commands: processes | record (--bundle ID [--prefix] | --pid PID) --seconds N --out FILE "
                  + "[--mono] [--progress FILE]")
}
