"""Background transcription of one kept recording with local faster-whisper.

    transcribe_job.py AUDIO OUT_DIR MODEL [LANGUAGE]

Runs detached under the gateway's own interpreter (it carries faster_whisper). Progress and the
outcome go to ``OUT_DIR/transcript.job.json`` (rewritten atomically); the results are
``transcript.txt`` (one line per segment, ``[H:MM:SS] text``), ``transcript.vtt`` and
``segments.json``. Never imports the plugin: it must stay runnable as a plain script.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time


STATE: dict = {}


def save(job: Path, **fields) -> None:
    """The job file, rewritten whole from this run's own state (never merged with an older run's)."""
    STATE.update(fields, updated=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    write(job, json.dumps(STATE, ensure_ascii=False, indent=1))


def write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def stamp(seconds: float, vtt: bool = False) -> str:
    seconds = max(0.0, float(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    if vtt:
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"
    return f"{int(h)}:{int(m):02d}:{int(s):02d}"


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    audio, out_dir, model_name = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    language = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
    STATE.clear()
    job = out_dir / "transcript.job.json"
    save(job, status="running", pid=os.getpid(), model=model_name, language=language, progress_seconds=0.0,
         started=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio), language=language, vad_filter=True, beam_size=5)
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        save(job, duration=duration, detected_language=getattr(info, "language", None))
        found = []
        last_save = time.monotonic()
        for seg in segments:
            text = (seg.text or "").strip()
            if text:
                found.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
            if time.monotonic() - last_save > 5:
                save(job, progress_seconds=round(seg.end, 1), segments=len(found))
                last_save = time.monotonic()
        lines = [f"[{stamp(s['start'])}] {s['text']}" for s in found]
        write(out_dir / "transcript.txt", "\n".join(lines) + ("\n" if lines else ""))
        vtt = ["WEBVTT", ""]
        for i, s in enumerate(found, 1):
            vtt += [str(i), f"{stamp(s['start'], True)} --> {stamp(s['end'], True)}", s["text"], ""]
        write(out_dir / "transcript.vtt", "\n".join(vtt))
        write(out_dir / "segments.json", json.dumps(found, ensure_ascii=False, indent=1))
        save(job, status="done", progress_seconds=round(duration, 1), segments=len(found),
             ended=time.strftime("%Y-%m-%dT%H:%M:%S%z"), files=["transcript.txt", "transcript.vtt", "segments.json"])
        return 0
    except Exception as exc:  # noqa: BLE001 - the outcome goes to the job file for the plugin to report
        save(job, status="failed", error=f"{type(exc).__name__}: {exc}", ended=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        return 1


if __name__ == "__main__":
    os.umask(0o077)   # other people's speech: every file this job writes is private
    sys.exit(main())
