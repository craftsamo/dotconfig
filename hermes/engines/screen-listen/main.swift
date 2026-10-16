// screen-listen helper: record the audio output of one running application (matched by bundle
// id) to a WAV file through a Core Audio process tap, or one window of it to an MP4 through
// ScreenCaptureKit. Never the microphone, never the whole screen.
//
//   screen-listen processes                         -> {"ok":true,"data":[{pid,bundle,running_output}]}
//   screen-listen record (--bundle ID [--prefix] | --pid PID) --seconds N --out FILE
//                        [--mono] [--progress FILE]
//                                                   -> {"ok":true,"data":{...}} | {"ok":false,"kind","error"}
//   screen-listen windows [--bundle ID]             -> {"ok":true,"data":[{id,pid,bundle,title,width,height,on_screen}]}
//   screen-listen capture --bundle ID --seconds N --out FILE.mp4
//                        [--window TITLE] [--fps N] [--max-width N] [--no-audio] [--progress FILE]
//
// Core Audio registers one process object per process that plays, with that process's own
// bundle id, so an app's helper processes (``<bundle>.helper`` and the like) are matched with
// ``--prefix``; ``--pid`` serves diagnostics. ``--mono``
// mixes the processes down to one channel (voice recordings; half the bytes). ``--progress``
// rewrites a small JSON file every few seconds (pid, seconds, frames, peak, whether audio
// arrived since the last write) so a long recording can be watched and stopped from outside:
// SIGTERM ends it cleanly, with the WAV finalized and the final JSON on stdout.
//
// ``capture`` records the app's largest normal window (or the one whose title contains
// ``--window``) as it is composited for that window alone, so other windows over it do not
// show; the app's own audio goes into the same file unless ``--no-audio``. ``--fps`` (30) and
// ``--max-width`` (1280 points) bound the file size of a long take. It ends the same way as
// ``record``, and also when the window closes.
//
// One JSON object on stdout, nothing else. The first `record` on this machine makes macOS ask
// for "System Audio Recording" for the app bundle this binary lives in (NSAudioCaptureUsageDescription
// in the bundle's Info.plist); the first `windows` or `capture` asks for "Screen Recording", a
// consent macOS re-confirms periodically. The process tap API needs macOS 14.2 or later;
// `capture` writes through SCRecordingOutput and needs macOS 15.

import AVFoundation
import CoreAudio
import CoreGraphics
import CoreMedia
import Foundation
import ScreenCaptureKit

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

// MARK: - Window capture (ScreenCaptureKit)

/// Blocks the main thread on a semaphore while keeping its run loop served: the consent dialog
/// and ScreenCaptureKit's callbacks must not find it dead.
func wait(_ semaphore: DispatchSemaphore, upTo seconds: Double = .infinity) -> Bool {
    let deadline = Date().addingTimeInterval(seconds)
    while semaphore.wait(timeout: .now()) == .timedOut {
        if Date() >= deadline { return false }
        RunLoop.main.run(until: Date().addingTimeInterval(0.05))
    }
    return true
}

func shareableContent() throws -> SCShareableContent {
    let semaphore = DispatchSemaphore(value: 0)
    var outcome: Result<SCShareableContent, Error> = .failure(Failure(kind: "screencapture", message: "no answer"))
    SCShareableContent.getExcludingDesktopWindows(false, onScreenWindowsOnly: false) { content, error in
        if let content {
            outcome = .success(content)
        } else {
            outcome = .failure(Failure(kind: "permission", message: "ScreenCaptureKit refused to list windows "
                               + "(\(error.map { "\($0)" } ?? "no error")); Screen Recording may be refused for this helper"))
        }
        semaphore.signal()
    }
    _ = wait(semaphore)
    return try outcome.get()
}

func describe(_ window: SCWindow) -> [String: Any] {
    ["id": Int(window.windowID), "pid": Int(window.owningApplication?.processID ?? 0),
     "bundle": window.owningApplication?.bundleIdentifier ?? "", "title": window.title ?? "",
     "width": Int(window.frame.width.rounded()), "height": Int(window.frame.height.rounded()),
     "on_screen": window.isOnScreen]
}

/// Normal windows (layer 0) of the app, big enough to be a document rather than a tooltip.
func windows(of bundle: String?, in content: SCShareableContent) -> [SCWindow] {
    content.windows.filter { window in
        guard let app = window.owningApplication, window.windowLayer == 0 else { return false }
        if let bundle, app.bundleIdentifier != bundle { return false }
        return window.frame.width >= 100 && window.frame.height >= 100
    }
}

@available(macOS 15.0, *)
final class Capture: NSObject, SCStreamDelegate, SCStreamOutput, SCRecordingOutputDelegate {
    private(set) var frames: Int64 = 0
    private(set) var audioBuffers: Int64 = 0
    private(set) var streamError: String?
    private(set) var recordingError: String?
    let started = DispatchSemaphore(value: 0)
    let finished = DispatchSemaphore(value: 0)
    let queue = DispatchQueue(label: "screen-listen.capture")

    func stream(_ stream: SCStream, didOutputSampleBuffer buffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard buffer.isValid else { return }
        switch type {
        case .screen:
            // Only a complete frame is a picture; idle and blank frames carry nothing new.
            let attachments = CMSampleBufferGetSampleAttachmentsArray(buffer, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]]
            let status = (attachments?.first?[.status] as? Int).flatMap(SCFrameStatus.init(rawValue:))
            if status == .complete { frames += 1 }
        case .audio:
            audioBuffers += 1
        default:
            break
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        streamError = "\(error)"
        stopRequested = 1
    }

    func recordingOutputDidStartRecording(_ recordingOutput: SCRecordingOutput) { started.signal() }

    func recordingOutput(_ recordingOutput: SCRecordingOutput, didFailWithError error: Error) {
        recordingError = "\(error)"
        stopRequested = 1
        finished.signal()
    }

    func recordingOutputDidFinishRecording(_ recordingOutput: SCRecordingOutput) { finished.signal() }
}

func commandWindows(_ args: [String]) {
    do {
        let content = try shareableContent()
        emit(["ok": true, "data": windows(of: option("--bundle", args), in: content).map(describe)])
    } catch let failure as Failure {
        fail(failure.kind, failure.message)
    } catch {
        fail("screencapture", "\(error)")
    }
}

@available(macOS 15.0, *)
func commandCapture(_ args: [String]) {
    guard let bundle = option("--bundle", args), !bundle.isEmpty else { fail("usage", "--bundle is required") }
    guard let secondsText = option("--seconds", args), let seconds = Double(secondsText), seconds > 0,
          seconds <= maxSeconds else { fail("usage", "--seconds must be between 0 and \(Int(maxSeconds))") }
    guard let outPath = option("--out", args), outPath.hasPrefix("/") else { fail("usage", "--out must be an absolute path") }
    if FileManager.default.fileExists(atPath: outPath) { fail("usage", "--out already exists") }
    let progressPath = option("--progress", args)
    if let progressPath, !progressPath.hasPrefix("/") { fail("usage", "--progress must be an absolute path") }
    let fps = Int(option("--fps", args) ?? "30") ?? 0
    guard fps >= 1 && fps <= 60 else { fail("usage", "--fps must be between 1 and 60") }
    let maxWidth = Double(option("--max-width", args) ?? "1280") ?? 0
    guard maxWidth >= 320 else { fail("usage", "--max-width must be at least 320") }
    let titlePart = option("--window", args)
    let audio = !args.contains("--no-audio")
    let output = URL(fileURLWithPath: outPath)
    // SCStream asserts a window-server connection (CGS_REQUIRE_INIT) that a background app has
    // not opened yet; asking for the main display opens it.
    _ = CGMainDisplayID()

    let window: SCWindow
    do {
        let content = try shareableContent()
        let candidates = windows(of: bundle, in: content).filter { window in
            guard let titlePart else { return true }
            return (window.title ?? "").localizedCaseInsensitiveContains(titlePart)
        }
        // On screen before hidden, then the biggest: the app's main window, not a popup.
        guard let chosen = candidates.max(by: { a, b in
            (a.isOnScreen ? 1 : 0, a.frame.width * a.frame.height) < (b.isOnScreen ? 1 : 0, b.frame.width * b.frame.height)
        }) else {
            let wanted = titlePart.map { "a window titled like \"\($0)\"" } ?? "a window"
            fail("no_window", "\(bundle) has no \(wanted) to capture (the app is not running, or shows nothing)")
        }
        window = chosen
    } catch let failure as Failure {
        fail(failure.kind, failure.message)
    } catch {
        fail("screencapture", "\(error)")
    }

    let scale = min(1, maxWidth / max(window.frame.width, 1))
    // H.264 wants even dimensions.
    let width = max(2, Int((window.frame.width * scale / 2).rounded()) * 2)
    let height = max(2, Int((window.frame.height * scale / 2).rounded()) * 2)
    let configuration = SCStreamConfiguration()
    configuration.width = width
    configuration.height = height
    configuration.minimumFrameInterval = CMTime(value: 1, timescale: CMTimeScale(fps))
    configuration.showsCursor = false
    configuration.scalesToFit = true
    configuration.preservesAspectRatio = true
    configuration.queueDepth = 5
    configuration.capturesAudio = audio
    configuration.excludesCurrentProcessAudio = true

    let capture = Capture()
    let stream = SCStream(filter: SCContentFilter(desktopIndependentWindow: window), configuration: configuration,
                          delegate: capture)
    let recordingConfiguration = SCRecordingOutputConfiguration()
    recordingConfiguration.outputURL = output
    recordingConfiguration.videoCodecType = .h264
    recordingConfiguration.outputFileType = .mp4
    let recording = SCRecordingOutput(configuration: recordingConfiguration, delegate: capture)
    do {
        try stream.addStreamOutput(capture, type: .screen, sampleHandlerQueue: capture.queue)
        if audio { try stream.addStreamOutput(capture, type: .audio, sampleHandlerQueue: capture.queue) }
        try stream.addRecordingOutput(recording)
    } catch {
        fail("screencapture", "could not set the stream up: \(error)")
    }

    let started = Date()
    let startSemaphore = DispatchSemaphore(value: 0)
    var startError: String?
    stream.startCapture { error in
        startError = error.map { "\($0)" }
        startSemaphore.signal()
    }
    _ = wait(startSemaphore)
    if let startError {
        try? FileManager.default.removeItem(at: output)
        let permission = startError.contains("-3801") || startError.lowercased().contains("declined")
        fail(permission ? "permission" : "screencapture", "could not start the capture: \(startError)"
             + (permission ? "; Screen Recording may be refused for this helper" : ""))
    }
    signal(SIGINT) { _ in stopRequested = 1 }
    signal(SIGTERM) { _ in stopRequested = 1 }
    let deadline = started.addingTimeInterval(seconds)
    var lastProgress = Date.distantPast
    var lastFrames: Int64 = 0
    func writeProgress(final: Bool) {
        guard let progressPath else { return }
        let now = Date()
        let frames = capture.frames
        let object: [String: Any] = [
            "pid": Int(getpid()), "seconds": (now.timeIntervalSince(started) * 10).rounded() / 10,
            "frames": frames, "receiving": frames > lastFrames, "audio_buffers": capture.audioBuffers,
            "final": final, "updated": ISO8601DateFormatter().string(from: now)]
        if let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]) {
            try? data.write(to: URL(fileURLWithPath: progressPath), options: .atomic)
        }
        lastProgress = now
        lastFrames = frames
    }
    writeProgress(final: false)
    while stopRequested == 0 && Date() < deadline {
        RunLoop.main.run(until: Date().addingTimeInterval(min(0.1, max(0.01, deadline.timeIntervalSinceNow))))
        if Date().timeIntervalSince(lastProgress) >= progressInterval { writeProgress(final: false) }
    }
    let stopSemaphore = DispatchSemaphore(value: 0)
    stream.stopCapture { _ in stopSemaphore.signal() }   // already-stopped is not a failure here
    _ = wait(stopSemaphore, upTo: 10)
    let finalized = wait(capture.finished, upTo: 15)
    let elapsed = Date().timeIntervalSince(started)
    writeProgress(final: true)
    if let recordingError = capture.recordingError {
        fail("io", "writing the MP4 failed: \(recordingError)")
    }
    guard finalized else { fail("io", "the MP4 was not finalized in time") }
    let size = (try? FileManager.default.attributesOfItem(atPath: outPath)[.size] as? Int) ?? 0
    var data: [String: Any] = [
        "file": outPath,
        "pid": Int(getpid()),
        "bytes": size,
        "seconds": (elapsed * 100).rounded() / 100,
        "stopped_early": stopRequested != 0,
        "frames": capture.frames,
        "fps": fps,
        "width": width,
        "height": height,
        "audio": audio,
        "audio_buffers": capture.audioBuffers,
        "window": describe(window),
    ]
    if let streamError = capture.streamError { data["stopped_by"] = streamError }
    emit(["ok": true, "data": data])
}

let arguments = Array(CommandLine.arguments.dropFirst())
switch arguments.first {
case "processes":
    commandProcesses()
case "record":
    commandRecord(Array(arguments.dropFirst()))
case "windows":
    commandWindows(Array(arguments.dropFirst()))
case "capture":
    if #available(macOS 15.0, *) {
        commandCapture(Array(arguments.dropFirst()))
    } else {
        fail("usage", "capture needs macOS 15 or later")
    }
default:
    fail("usage", "commands: processes | record (--bundle ID [--prefix] | --pid PID) --seconds N --out FILE "
                  + "[--mono] [--progress FILE] | windows [--bundle ID] | capture --bundle ID --seconds N "
                  + "--out FILE.mp4 [--window TITLE] [--fps N] [--max-width N] [--no-audio] [--progress FILE]")
}
