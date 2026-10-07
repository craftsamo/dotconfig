# Visual story and timeline

## Use

By default the producer designs a new authored video's storyboard from the
intent you pass; this guide applies only when the user explicitly asks for an
Assistant-designed timeline. Then read it with the requested video's outcome
guide when a new authored composition,
substantial re-direction or an explicit visual timeline needs concretization.
Assistant designs what the viewer sees, including intermediate motion; Creator
chooses how to realize it. This is the planning document, not the final media,
a Writer storyboard commission or a second production workflow. A standalone
written script/storyboard still belongs to Writer. Research-only, analysis-only,
exact edits and frozen render resumes do not acquire this planning requirement.
For UI appearing in a new image, use the component-design paragraphs below;
do not invent a duration or video timeline for a static image.

## Client decisions

Extract purpose, audience, protected content, references and grants. Do not ask
the user to supply artistic vocabulary, components, shots or timing. Propose one
coherent concrete treatment, identifying your suggestions versus their decisions.
Use Creator for uncertain feasibility before promising a realizable design, not
as a routine detour before every planning action. Missing script, art or sound
is a dependency through Creator, not permission to invent facts or rewrite
Writer's accepted copy. Provisional timing is explicitly estimated, never measured.

Design the whole before summarizing it for Telegram:

- Give every scene a purpose, focus, opening and closing state. Specify which
  object/idea survives into the next scene, and deliberate discontinuities.
- For every meaningful event, name subject, trigger, before/during/after,
  trajectory, pacing and foreground/background relationships. Distinguish UI,
  camera, text and sound. Cover held intervals as deliberately as moving ones.
  A transition called only "morph", "smooth", "cinematic" or "fade" is
  unfinished. Decide what happens to labels, geometry, masks and occlusion in
  the middle without waiting for the user to ask. Keep intermediate states
  consistent with both endpoints, not independently invented illustrations.
- Use event boundaries and key states, not a mandatory one-second grid. Resolve
  short critical changes at tenths of a second or finer when useful; production
  later resolves exact frames and easing. Numbers alone do not constitute design.
- Define a visual system and every distinct visible UI component: anatomy and
  proportions, typography, spacing/alignment, edge treatment, surface/light,
  icon language and the states that actually appear. Instances can share one
  design; exceptions must be explicit. A generic native control, stock window
  or rounded rectangle is not an acceptable accidental default. A deliberately
  plain or faithful real-product UI is valid; never fabricate product features
  or reskin a faithful capture. Appearance applies to parts as well as the scene.
- Keep implementation open where appearance is settled. Describe real parallax,
  occlusion or a moving material boundary rather than dictating a library or
  replacing the request with flat scaling. Creator reports supported methods,
  uncertain methods and actual gaps; a browser demo is not installed support.

Maintain the complete design under the same durable job directory sent to
Creator: the caller-selected destination, else the owning Group's
`.agent/<YYYYMMDD>-<job>/`, else `~/Workspaces/.agent/<YYYYMMDD>-<job>/`. Do not
leave the only copy in a tool cache or change the Group. Read the
canonical helper contract below with `read_file`, recover its full body or stop,
and author its JSON input:

```text
~/.hermes/profiles/assistant/scripts/creative-timeline.md
```

This is a narrow exception permitting local planning
files in Plan, not production code, generated art, an animatic or a paid call.
Author new designs at schema version 2: the real aspect and background, the
actual on-screen words as text nodes, surface shapes and identification
patterns, and literal opacity. The boards are then drawn as the viewer would
see them, and the motion marks (previous position, arrows, appearing and
leaving objects) are derived from the keyframes; never draw or describe them
by hand. Keep one stable `key` per on-screen object across keyframes so the
derivation tracks the right thing.

For a fresh review, also author a concise viewing overview per that contract,
bound to the complete design's identity. Write its short scene/beat headings,
decision summaries, representative boards and issue summaries yourself;
do not make the renderer truncate prose or decide which constraint matters.
Every change retains a visible intermediate preview, and every open item a
visible concise summary. Group meaningful changes rather than assigning one
full-weight page section to every timestamp. This is a second representation
of the same design, not permission to leave hidden details unfinished.

Open items are design questions that need the user's judgment: an unsettled
wording, font or framing choice, a hold length to confirm, a reference whose
applicability is doubtful. Procedural status — not approved, not produced,
feasibility not checked, timing estimated, viewing route unverified — is the
same for every proposal and is stated once in the accompanying Telegram
message, never written into `open_items` or the document. Empty open items
mean no design question is pending, not that anything is approved.
Render only through:

```sh
python3 ~/.hermes/profiles/assistant/scripts/creative-timeline.py --spec <absolute-design.json> --check
python3 ~/.hermes/profiles/assistant/scripts/creative-timeline.py --spec <absolute-design.json> --review <absolute-review.json> --check
python3 ~/.hermes/profiles/assistant/scripts/creative-timeline.py --spec <absolute-design.json> --review <absolute-review.json> --out <new-absolute-timeline-vN-directory>
```

The helper produces two self-contained HTML documents, the retained
design/review JSON and an identity receipt binding all of them:
`timeline.html`, the viewing document made of boards and one line per beat,
and `spec.html`, the complete written design. The user reads boards, not
prose; the prose exists for Creator and for whoever asks for it. Source is data, never arbitrary
HTML/SVG/JavaScript. Its structural
validation cannot judge coherence, component beauty or actual motion. Open the
HTML with existing permitted local viewing tools when available; check phone
readability, key-state correspondence and that no design detail was omitted.
Use the viewing document to judge the whole: an activity-log list, one row
per event under its scene header, each with lane and change chips and a
thumbnail of its end frame; a row opens to every frame of its range and the
parts first pictured there. A CSS-only lane filter narrows the rows.
Disclosures hold only boards, chips and component pictures. Multiple panels may stay open for
comparison. Do not nest them or depend on modal behavior, horizontal
scrolling or links that must auto-open hidden content. Opening a panel never
invokes a model or starts work.
If viewing is unavailable, disclose that instead of inventing a visual pass.

Attach `timeline.html` in Telegram as a document using the existing attachment
mechanism, naming the in-document Design ID and, when present, Review ID in the
accompanying message. Attach `spec.html` only when the user asks for the
written design; it always goes to Creator. That message also carries, in one line, the procedural
status the document omits: this is a design proposal for agreement, not a
produced or feasibility-checked video, and timing is estimated. A chat summary
accompanies, never replaces, the complete artifact.
HTML attachment opening is client-dependent; Telegram message HTML is not a
browser. Confirm the user's viewing route on first use; do not require hosting,
Mini Apps or a new browser service. If it fails, report the delivery gap and
agree a supported export, not a silently shortened text-only substitute.

Each revision gets a new directory. Keep unresolved design questions visible
as open items; do not call missing design or feasibility ready for production
in the message. Ask agreement
on the identified design version, not a taste vote for each event. Retain the
actual user message and design identity separately; the helper cannot approve
anything. Changes to visual intent return for the affected agreement; a frozen
producer proposal/preview remains immutable and keeps its own approval gates.

## References

Read [reference-research.md](reference-research.md) for concrete observed
examples and their applicability, not a list of aesthetic adjectives. Use the
existing `media-craft-direction` reference-interpretation and production-translation
knowledge to connect observed mechanisms to this design. Also read
`media-craft-visual` and its composition/typography/systems-assets references
for actual layout, lettering and UI decisions, and `media-craft-motion` with
timing-spacing/continuity/ui-choreography as applicable. The shared knowledge
does not make Assistant a renderer or its coordinate-script author. Reuse full
bodies in current context; recover missing bodies from their canonical shared
skill directories with `read_file`, following real truncation, or stop that
decision with the named missing resource. Do not install or load all references.

Tie adopted observations to scene, event and component IDs. Record inspected
material and limits, what works and why, what transfers, what must not be copied
and unresolved questions. Existing evidence can be reused; extra research is
bounded to an unresolved design decision, not an obligatory fresh search. Keep
an honest reason when no inspected external source applies. Public URLs and
research captures are not automatically licensed assets or upload consent.

## Acceptance

Before offering design agreement, every scene and significant intermediate
change is concrete, visual holds cover the whole duration, UI parts belong to
an explicit visual system, and camera/text/audio presence or absence is stated.
Trace important choices to observations or mark them as your original proposal.
Reject empty sophistication claims even if every JSON field contains text.
The bundle must retain the design, not hide unresolved work behind a short
Telegram summary. Visible overview boards and captions must preserve the
important intermediate changes, simultaneous relationships and all unresolved
issues. Detailed design lives in `spec.html`, never omitted or written only
after the user asks. Verify actual disclosure operation on the intended client;
previous HTML display alone proves neither opening nor keyboard behavior.
Boards explain space, appearance and sequence; they
are not approved production pixels or a playback test. Unsettled material
design choices stay visible in open items until resolved; unsettled
feasibility is reported in the message and to Creator, not as an open item.

Pass the exact design JSON, review JSON, HTML, receipt, reference observations and actual
agreement to Creator in the normal brief. Creator maps scene/event/component
IDs to implementation and producer evidence. Do not replace this with a broad
style label or ask Creator to invent omitted middle states. This agreement is
visual intent only, not spend, upload, source reuse or exact producer-preview
approval. Production self-checks remain with the hands; ordinary delivery does
not acquire another broker aesthetic-review loop.
