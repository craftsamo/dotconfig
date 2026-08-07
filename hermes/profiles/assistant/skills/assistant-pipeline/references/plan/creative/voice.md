# Voice line (TTS) — decision surface

Speech synthesis from a **final script**. Script writing/editing is
the writer's work — a voice unit releases only after its text passed
your QA. Songs → `song-generation.md`.

Capability `core:tts` (no dedicated technic) · QA `voice` · metered
TTS · card: `tts-voice` (final script required).

## Fix before release

- The exact script, verbatim — plus language, pronunciations for
  ambiguous terms/names, and pacing notes.
- Voice identity: the preset/voice name (and per-voice params when
  the set spans speakers) — one locked voice per speaker across a
  set.
- Output contract: format, sample rate, channels, loudness,
  duration target.
- File count — each output file is one voice asset for Budget.
- Role: standalone deliverable vs a part feeding a composite
  (`composite-media.md`) — a part's container/sample-rate must match
  the assembly's edit spec.

## Defaults

- Anchor: for multi-line/multi-session sets, the first approved
  line locks the voice + params.
- Budget shape: 1 primary synthesis per asset, 1 corrective pass.
  Verification is verbatim back-transcription against the script —
  plan scripts with unambiguous spellings.
