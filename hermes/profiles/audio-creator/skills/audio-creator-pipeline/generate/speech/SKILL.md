---
name: generate-speech
description: >-
  Speak one approved script (up to 600 characters) as narration or a registered
  character line. Deliver a 48 kHz mono WAV, ASR word times, estimated SRT and
  take evidence; optionally an Opus voice message. Not script writing, voice
  cloning/registration, music, singing or sound effects.
version: 1.0.0
metadata:
  hermes:
    category: hands
    hands: audio-creator
    cost: free
    output: "speech_<slug>.wav + .words.json + .srt + .take.json + .script.txt; optional .ogg"
    form:
      script:
        required: true
        type: file
        label: "approved UTF-8 script file, one section of 1-600 characters; do not rewrite it"
      voice:
        required: false
        type: text
        label: "house (default, language fallback chain), or a registered <engine>:<id> from character_voices"
      language:
        required: false
        options: [ja, en]
        other: true
        label: "ASR language code; omit for automatic detection, not an instruction to translate"
      style:
        required: false
        type: text
        label: "delivery direction for a qualified voice whose engine advertises caption; not allowed with house"
      seed:
        required: false
        type: int
        label: "reproduce a qualified voice take; only when the engine advertises seed"
      format:
        required: false
        options: [wav, voice-message]
        label: "wav (default) or voice-message (also deliver mono Opus Ogg)"
      slug:
        required: false
        label: "lowercase ASCII filename slug; default speech"
      note:
        required: false
        type: text
---

<Procedure>

1. Read the script file and form. Reject blank/>600-character scripts and
   contradictory controls before synthesis. Do not silently split long prose
   into extra paid-by-time takes: return it to Creator for sectioning. The
   default allowance is **one take + one corrective**, counting every synthesis
   invocation, including failures. Record the running tally under `deliver`.
2. Resolve the voice. `house` calls `text_to_speech` on the configured
   `irodori-tts -> qwen3-tts -> edge` chain; it accepts neither style nor seed.
   Edge is an online fallback: house permits the script to reach that service;
   a local-only request must name a qualified local voice instead. A qualified
   voice calls `character_voices` first, then `character_text_to_speech` with
   the exact returned ID. Inspect that engine's `style` capabilities: `style`
   needs `caption`, seed needs `seed`, and performed emoji need `emoji`.
   Unsupported controls return `Q<n>`, never ignored or routed to another
   engine. An unknown ID returns available candidates, not a substitution.
   House cannot promise a fixed speaker across languages. Catalog lookup is
   free and may be requested before a complete synthesis form; it produces no
   audio and does not invent a source-speech leaf.
3. Preserve the exact approved words. Approved performed emoji may pass ONLY
   through the capable character path; do not add them from a style request.
   If a house script contains emoji whose intended reading is unclear, ask.
   Send the file's text verbatim to the appropriate tool and an absolute,
   previously unused raw output path under `deliver`. Prefer WAV for the
   character path. Retain the raw tool response as `take-01.tool.json` (and
   `take-02.tool.json` only for an authorized corrective); retain returned seed
   and ID rather than inventing them. An explicit voice failure is a finding,
   never a call to ordinary TTS. A packaging/ASR failure is not a new take.
4. Package the existing raw audio in a fresh bundle, for example
   `deliver/take-01`. The parent `deliver` must exist; only create the job
   directory beneath the agreed Group, never a new Group. Run:

   ```sh
   "$(ghq root)/github.com/NousResearch/hermes-agent/venv/bin/python" "${HERMES_SKILL_DIR}/../../scripts/speech-media.py" track <raw-audio> --script-file <script-file> --take-file <tool-response-json> --out <new-bundle-dir> --slug <slug>
   ```

   Add `--language <code>` only when supplied; add `--voice-message` for that
   format. Text travels through files, never inline CLI arguments (Japanese
   punctuation can trip the terminal guard). Run synthesis/ASR work in a
   resident session; long terminal work uses `background: true` and polling,
   not repeated foreground calls. The helper uses cached local faster-whisper
   `base`; a missing cache is a dependency finding, not permission to install.
5. Read the `RESULT:` JSON, including nonzero exits. `FAIL` may retain a
   candidate bundle for diagnosis; it is not a finished delivery. A close but
   nonidentical transcript is `WARN`, not proof of mispronunciation. Correct
   at most once when there is a concrete synthesis defect and allowance;
   unresolved reading/acting judgments go to Creator/the client. Revisions
   preserve script/voice and modify only requested controls. Seed replay also
   needs the same engine, text and style: compare decoded PCM hashes, not Ogg
   container bytes. A house replay is a new take, not deterministic.

</Procedure>

<QA>

- Master: full decode, PCM s16le, 48000 Hz, mono, positive duration, not silent;
  quote the measured sample peak, true peak, LUFS and clipping count. Any
  clipping or blank output is FAIL; normalization is an edit, not hidden here.
- Readback: quote transcript and `script_match`, similarity and coverage. PASS
  means normalized text equality only; punctuation/emoji and pronunciation are
  not verified. Coverage never overrides missing words. Review every WARN.
- Timing: `.words.json` and SRT remain beside the WAV, timestamps bounded to
  its duration. SRT carries approved text with **estimated** timing, not forced
  alignment. Word times/transcription alone cannot verify acting beats.
- Identity: quote the tool's returned ID/seed/style evidence when present;
  house engine is unknown unless the tool reports it. No invented provenance.
- Voice-message: the Ogg actually exists, decodes as mono Opus at 48 kHz and
  has its own derivative measurements. PCM hash equality applies to identical
  decoding pipelines, not lossy derivatives versus the WAV.
- State explicitly: listening, voice likeness, pronunciation and performance
  remain unverified. A duration delta is not proof of a successful performance.

</QA>

<Report>

Return `generate-speech`, bundle paths, requested voice and returned evidence,
each QA result with measurements, estimated-timing/perceptual gaps, and
`spend: free; takes N/2` (or the granted limit). Mark candidates/FAIL/WARN
visibly. Relay unsupported controls or dependencies as one `Q<n>`/finding;
never claim you listened or ask for another take merely to improve ASR score.

</Report>
