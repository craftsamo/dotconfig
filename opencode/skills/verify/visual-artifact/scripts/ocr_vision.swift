// Apple Vision OCR — second independent engine for image text verification.
// macOS only, no install required (ships with the OS).
//
//   swift ocr_vision.swift <image> [--correct]
//
// Prints an observation count plus each recognized string with confidence and
// a normalized bounding box (origin bottom-left, 0..1 in both axes).
//
// The observation count is the key output: it turns "exactly one text region"
// into a hard number rather than an impression. Language correction is OFF by
// default so the engine cannot "helpfully" autocorrect a brand name or slug
// into a real word — pass --correct only for prose.

import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count > 1 else {
    print("usage: swift ocr_vision.swift <image> [--correct]")
    exit(64)
}
let path = args[1]
let useCorrection = args.contains("--correct")

guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("LOAD_FAIL \(path)")
    exit(1)
}

print("IMAGE \(path)  \(cg.width)x\(cg.height)")

let req = VNRecognizeTextRequest { request, error in
    if let error = error {
        print("VISION_ERROR \(error.localizedDescription)")
        return
    }
    guard let obs = request.results as? [VNRecognizedTextObservation] else {
        print("NO_RESULTS")
        return
    }
    print("OBSERVATION_COUNT \(obs.count)")
    if obs.isEmpty {
        print("NO_TEXT_DETECTED")
        return
    }
    for (i, o) in obs.enumerated() {
        // Ask for up to 3 candidates: a confident single candidate is a much
        // stronger signal than a top pick among several close alternatives.
        let cands = o.topCandidates(3)
        for (j, c) in cands.enumerated() {
            let b = o.boundingBox
            let tag = j == 0 ? "TEXT" : "  alt"
            print(String(format: "%@[%d]: \"%@\" conf=%.3f box=(x=%.4f y=%.4f w=%.4f h=%.4f)",
                         tag, i, c.string, c.confidence,
                         b.origin.x, b.origin.y, b.width, b.height))
        }
    }
    let joined = obs.compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
    print("ALL_TEXT: \(joined)")
}

req.recognitionLevel = .accurate
req.usesLanguageCorrection = useCorrection

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do {
    try handler.perform([req])
} catch {
    print("PERFORM_FAILED \(error.localizedDescription)")
    exit(1)
}
