# Mix Timing And Receiving

Read only for create-ad/create-tour with `audio_workflow: mix`. Simple supplied
audio needs no Mix. Creator brokers all requests; hands never call each other.

## Preliminary timing

With no `mix_bundle`, use Creator's source inventory (stable source IDs,
actual lengths and intent). Author `timing-spec.json` and freeze it:

```json
{"version":1,"duration_seconds":15,"cues":[{"id":"voice-1","source":"voice","start":1,"source_start":0,"duration":4}]}
```

From either create leaf:

```sh
~/ghq/github.com/NousResearch/hermes-agent/venv/bin/python "${HERMES_SKILL_DIR}/../../scripts/mix_audio.py" timing --spec-file <absolute-timing-spec.json> --out <new-timing-directory>
```

At most 32 unique cue IDs; sources may repeat. Times are finite seconds; each
complete cue fits the output and source. Only timing is authored here, never
gains/ducking or new sound. Return frozen `timing.json` and its hash through
Creator to create-mix and STOP. No HTML, capture, pending/fake audio assets or
formal video approval. Users never need to write the JSON.

## Finished Mix

With `mix_bundle`, use the Hermes venv and the literal absolute path to
AudioCreator's `audio-creator-pipeline/scripts/mix-media.py` to run
`verify --bundle <bundle>` before staging. This is read-only validation, not
permission to execute any AudioCreator creation leaf. The Mix's frozen
`timing.json` must match the preliminary timing hash in this work conversation;
a change requires a new timing/Mix proposal, never silent substitution.

Copy the master under its ORIGINAL filename, `mix.take.json`, and any
`captions.json`/`timing.json` into fresh `assets/`. Exclude original stems.
Begin normal video approval using those actual file hashes. Intake fields
`mix_bundle` and `audio_workflow` are not a substitute for frozen source data.
Record this object in ad's plan.json or tour's form.json:

```json
{"mix":{"master":"assets/mix_intro.wav","receipt":"assets/mix.take.json","captions":"assets/captions.json","timing":"assets/timing.json"}}
```

Omit captions/timing only when absent from the receipt. Ad also includes all
paths in its normal hashed asset map; `audio_workflow` is NOT an ad plan key.
Tour keeps `audio_workflow: mix` in its normalized form, but removes the intake
`mix_bundle` path. For explicit screen modes, stage before the ordinary tour
proposal so the full normalized form (including `mix`) gets approved; kept
footage audio conflicts with Mix, so obtain an explicit mute decision upstream.

The master must exactly match the video's full duration. Place it once at
time 0 with a positive track index, unity volume, no media offset, no loop.
No other audio, including embedded video sound, may play alongside it.

## Captions And QA

Mix captions carry clean-speech provenance with transformed times; they are
not a speech words.json and never evidence that ASR ran on the mix. Keep their
estimated label. In Tour, author one timed caption element per captions entry
with `id="mix-caption-<1-based index>"`, literal text, `data-start` and
`data-duration` matching the entry, and a `clip` class. Place on a readable
caption track and inspect its actual visibility at the entry's midpoint.
No caption entries means no invented caption text. In Ad, captions are
provenance only unless explicitly approved as normal copy rows; never inject
unapproved extra ad copy.

Final render must contain the sole Mix track at the expected duration and
within the approved peak ceiling (0.2 dB encoding tolerance, never >=0 dBTP).
Measure the decoded final file, not just the input WAV. Check visible action
times against the timing proposal and inspect captions where present. Hashes,
stream presence and loudness are NOT whole-video synchronization or listening
proof. Changed timing/master requires new Mix and video approvals; never swap
bytes in a frozen project. Persisted v1/v2/v3 and ordinary WAV routes stay as-is.
