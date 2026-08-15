# Verification — inspect what you ship (engine)

Load this before accepting ANY produced file — every produce delivery, every
plan anchor before its sign-off round, every revise pass. A generation
backend returning a file is a claim, not evidence: models mangle text,
drift styles, and render artifacts without erroring. **You own the judgment
that the asset is right.**

Six checks, V1-V6. Run the ones the intent profile (below) marks required;
record what you checked and the outcomes as you go — they become the
report's verification evidence (see `references/delivery.md`).

## V1 — AcceptanceCheck (asset vs the brief)

Re-read the task body's Goal / Done criteria AFTER the assets exist. For
each brief requirement — purpose, asset list, count, platform, tone: which
delivered file satisfies it, and how do you know? A requirement you cannot
point at is not done. Count check in the same pass: exactly the brief's
quantity, nothing missing, nothing extra billed.

For a canonical technic that offers multiple implementations, Backend is also
an acceptance requirement. Compare the MediaBrief, capability handshake, and
actual execution: core provider fallback stays within the approved core
backend; `external:comfyui` used the preflighted local workflow and did not call
a Partner API node or cross to core generation. A visually acceptable artifact
from the wrong Backend fails V1.

For ComfyUI, compare the approved loopback host and workflow SHA-256 with the
runner result and same-host raw `/history/<prompt_id>` entry. The submitted graph
must contain only audited local node classes and reproduce the reported
model/seed parameters. Compare its separately recorded effective-graph hash and
semantic structure with the source: node IDs/classes/wiring stay fixed, while
only recorded parameter injections may differ. Missing raw history, an
unexplained structural change, a non-loopback host, or a hosted Partner/custom
node means the Backend claim is unverified and V1 fails.

## V2 — SpecCheck (mechanical conformance)

Measure, never eyeball, the numbers. From the workspace, with wrapper
tools (`ffprobe`, `sips`/`file`, the bundled scripts — never inline
interpreters; the worker guard fails them):

- Dimensions / aspect ratio exactly as briefed (9:16 is not "roughly
  vertical").
- Format / codec / container the destination accepts; duration and fps for
  video; file size within any platform cap.
- GIF/loop: seam check — first and last frames must join (extract both,
  compare); poster frame present when asked.
- Audio/music/voice: duration, sample rate, channels, codec/container,
  loudness/peak, clipping, silence, and file size as briefed.
- Runnable HTML: target viewport, browser/runtime compatibility, asset loading,
  console errors, interaction paths, and measured performance.

## V3 — PerceptualCheck (inspect every file)

Inspect every deliverable with your own input tools:

- **Stills**: `vision` on the actual file — artifacts, garbled/misspelled
  text (the most common generation failure), broken anatomy/geometry,
  composition matching the brief.
- **Video**: sample it — extract poster + 2-3 spread frames (`ffmpeg`) and
  inspect each, or run the video-analysis tool for motion-level claims
  (text legibility over time, scene order, glitch frames). Never judge a
  video by its first frame.
- **Voice/narration**: transcribe the output back (stt) and diff against
  the script — wrong or skipped words are silent failures; spot-listen
  claims stay unverifiable, the transcript is evidence.
- **Music/SFX/songs**: inspect waveform/spectrogram plus measured audio stats for
  truncation, clipping, silence, and structural gaps. These do not prove timbre,
  mix, lyric fidelity, or emotional fit; record a qualified listen-through or
  state that perceptual limitation explicitly.
- **Interactive HTML**: run the real page, exercise required inputs and resize,
  inspect representative states, and compare repeat runs for seeded output.
- Text IN media is guilty until read: read every rendered word back.

## V4 — ConsistencyCheck (the set holds together)

For batches and anchored work (execute Direction, revise): every asset against the
locked anchor — same palette (pixel-art: one named/derived palette, never
adaptive per asset), same style prompt, same seed/reference for video and
browser-native work, same audio model/prompt/conditioning parameters, same
voice params. Spot-check pairs with the medium's evidence; one drifted asset
breaks the set even when each file passes V3 alone.

## V5 — SpendCheck (budget reconciliation)

Recompute the tally before completing: generations attempted (failures
count), corrective passes used, against the effective Budget (body +
`AUTHORITY+:` comments). The tally in your final `PROGRESS:`/report must
match what actually ran — a mismatch means either an unrecorded spend or an
unearned cap left unreported. Overrun discovered here is a report line,
never silently absorbed.

Count each submitted ComfyUI workflow as a generation/render attempt and report
its measured runtime against the local runtime grant. Zero marginal API cost is
not unlimited compute, and switching Backend is never a budget workaround.

## V6 — DeliveryCheck (nothing stranded)

- Every final artifact `kanban_attach`ed — the scratch workspace dies on
  completion; a file not attached is a file lost.
- Intermediates and rejected variants NOT attached (deliver the set, not
  the darkroom floor).
- Filenames say what they are (asset, variant, dimensions) — the requester
  sees names before pixels.
- Anchor assets that future work will reuse (style spec, palette, seed,
  reference image) are attached or their locked values named in a
  comment — a revise card must be able to find them.

## Intent profiles — what each kind of work must pass

Row selection: produce cards use their intent's row — `new` splits by
anchoring (an asset produced under a locked anchor or as part of a
consistent set uses the batch row, even when it is a single file); execute
Direction cards use `Direction (anchor)`; advisory cards use `advisory`.
Advisory work never loads this production verifier.

`REQ` = required, `-` = usually skippable (judgment stands):

| Intent | V1 | V2 | V3 | V4 | V5 | V6 | Intent-specific gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| new (single) | REQ | REQ | REQ | – | REQ | REQ | the corrective pass was spent on the worst gap, or explicitly banked |
| new (batch / anchored) | REQ | REQ | REQ | REQ | REQ | REQ | no batch asset generated before the anchor sign-off; every asset reuses the locked anchor |
| revise | REQ | REQ | REQ | REQ | REQ | REQ | every feedback item addressed or explicitly declined with a reason; side-by-side against the previous version shows the fix WITHOUT regressing approved aspects |
| salvage | REQ | REQ | REQ | REQ | REQ | REQ | inventory ran BEFORE any spend; nothing that already existed was regenerated; canonicalized outputs traced to their source intermediates |
| Direction (anchor) | REQ | REQ | REQ | - | REQ | REQ | only anchor-allowance spend; the style spec + sample are attached before the sign-off block |
| advisory | REQ | - | - | - | REQ | - | zero generation spend; every claim sourced from the catalog or a cheap prerequisite check |

The profile is a floor, not a ceiling — escalate (more frames sampled, a
full listen-through) when the asset's cost or visibility warrants it.

## Pitfalls

- Trusting the generation tool's "success" without opening the file — V3
  exists because backends fail silently.
- Judging a video by its poster frame, or narration without a transcript.
- Verifying each asset alone and never the set (V4) — consistency drift is
  invisible one file at a time.
- Skipping the spec measurement because it "looks right" (V2) — platform
  rejections are exact, not approximate.
- Burning the corrective pass on taste when the brief is met — corrective
  spend is for misses against the brief, not preference.
- Counting spend from surviving files (failed attempts also cost) — the
  tally comes from the comment trail (V5).
- Attaching intermediates, or NOT attaching the anchor a future revise will
  need (V6).

## Verification (of this engine's own use)

- The intent profile was identified and its REQ checks all ran (or each
  skip is named + justified in the report).
- Checks + outcomes recorded; misses led to the corrective pass, an honest
  gap statement, or a block — never silent acceptance.
- The intent-specific gate passed (anchor reuse, feedback side-by-side,
  inventory-before-spend — as applicable).
