# Creative timeline document

Assistant authors the visual intent; this stdlib helper only validates data and
draws a self-contained planning document. It never generates art, plays a film,
chooses a production engine, approves a design or changes a media budget. The
neutral boxes are spatial diagrams, not the final component look. All detailed
design text is retained, including references and intermediate states. The
optional bound review presents concise authored decisions first and opens
complete detail in place; no information is generated when a panel opens.

```sh
python3 ~/.hermes/profiles/assistant/scripts/creative-timeline.py --spec /absolute/design.json --check
python3 ~/.hermes/profiles/assistant/scripts/creative-timeline.py --spec /absolute/design.json --out /absolute/timeline-v1
```

Use the installed helper after approved paired cutover; candidate tests use the
candidate script explicitly, never change live links. Inputs and output paths
must be absolute, physical and symlink-free. The output parent must already
exist; the output directory must not. Each revision uses a new directory.
The bundle contains unchanged `design.json`, deterministic `timeline.html` and
`receipt.json` written last. A receipt carries source/document SHA-256 identity,
not human approval. The HTML itself displays the source SHA-256, so attachments
remain identifiable even when their filenames match. Include that identity in
the accompanying Telegram message and retain the actual agreement with it in
job notes. CLI output includes the exact HTML/design/receipt file paths for
the existing file-delivery mechanism, not just a directory to reconstruct.
An interrupted bundle stays incomplete; do not overwrite it on retry.

## Schema v1

All fields below are required; unknown fields are rejected, never silently lost.
Text is nonempty, at most 4,000 characters, with no control characters except
newline/tab. Use the user's language for authored text. The document's fixed
labels are English. JSON input is at most 2 MiB, output at most 16 MiB; no NaN,
infinity, duplicate keys or booleans in numeric fields.

- Root: `version: 1`, `title`, `goal`, `duration` (0.001..3600 seconds), `timing`
  (`estimated` or `agreed`, neither asserts measured audio), `open_items` (0..80
  strings), `reference_note`, `sources`, `visual_system`, `components`, `scenes`.
  Nonempty open items label the document discussion-only. Empty open items pass
  structure, not a semantic readiness or feasibility assessment.
- Sources (0..16): `id`, HTTPS `url` without credentials, `observed`, `inspection`
  (what/when was actually inspected and its limits), `adopt`, `avoid`. If no
  source applies, explain that honestly in `reference_note`; never invent a
  source, inspection or timestamp. These links are navigation only, not assets.
- Visual system: `typography`, `geometry` (proportion, alignment, spacing, edges),
  `surfaces` (material/light/foreground relationships), `palette` (2..16 token
  names mapped to six-digit hex colors). It describes the production design;
  only palette colors are applied to diagram geometry.
- Components (1..80): `id`, `name`, `anatomy`, `typography`, `surface`, `states`,
  `reference_ids`. Include icon rules in anatomy/typography where applicable.
  Shared instances use the same component ID; describe intentional exceptions.
- Scenes (1..60): `id`, `title`, `start`, `end`, `purpose`, `focus`, `entry`,
  `exit`, `reference_ids`, `events`, `absent_lanes`, `keyframes`. Scenes are
  ordered and contiguous from zero to duration, with no positive-length overlap.
- Events (1..80 per scene): `id`, `lane` (`visual`, `camera`, `text`, `audio`),
  `kind` (`change` or `hold`), `start`, `end`, `subject`, `before`, `during`,
  `after`, `trigger`, `trajectory`, `pacing`, `component_ids`, `reference_ids`.
  All intervals have positive length within their scene and are ordered by
  start; overlap is allowed for coordinated actions. Visual events must cover
  the entire scene, including deliberate holds. For each absent nonvisual lane,
  `absent_lanes` maps its name to a reason; do not also put events in that lane.
  Every event links at least one component and every component is used by an
  event. Sound/camera events link the visible subject they accompany.
- Keyframes (2..242 per scene): `at`, `label`, `nodes` (1..80). The ceiling covers
  endpoints and an intermediate state of each of the 80 allowed events, even
  with distinct overlapping boundaries. Never remove a real change to fit a
  sampling cap. Times are strictly
  ordered and include both scene endpoints. Every change event has at least one
  strictly intermediate keyframe, not only endpoints. An endpoint is a design
  state, not the nonexistent final encoded frame of a renderer.
- Nodes: `component`, `x`, `y`, `w`, `h`, `label`, `fill` (palette token).
  Geometry uses a normalized visible canvas of 0..100, with bounded offscreen
  overscan: `x`/`y` -100..200, `w`/`h` >0..300, right/bottom edges <=200.
  The viewport clips offscreen portions, so entry/exit need not be faked as
  in-frame states. Nodes draw in listed back-to-front order. This is illustration of
  composition, not production coordinates or a claimed final aspect ratio.

IDs and palette tokens are lowercase slugs beginning with a letter, at most 64
characters. IDs are unique per collection; event IDs are unique across scenes.
Reference/component links must resolve to real entries. No raw HTML, CSS, SVG,
JavaScript, remote fonts, screenshots or media are accepted. Every authored
string is escaped; the HTML has no scripts or remote asset requests. CSP blocks
active/network content; clicking a cited HTTPS source is explicit navigation.

## Synthetic example

This fictional two-second design is a helper fixture, not reference research,
approved product copy, a taste standard or a completed production. Real briefs
need reference analysis and scene-specific visual design rather than copying it.

```json
{
  "version": 1,
  "title": "Panel expands into a readable result",
  "goal": "Make the relation between a compact task and its result visible.",
  "duration": 2,
  "timing": "estimated",
  "open_items": ["Whether the first result row should appear before or only after the panel passes half height."],
  "reference_note": "Synthetic test; no external example was inspected or adopted.",
  "sources": [],
  "visual_system": {
    "typography": "One sans family; semibold task heading, regular result rows; stable heading baseline.",
    "palette": {"ink": "#182330", "paper": "#E3EFF1", "accent": "#235B72"},
    "geometry": "Heading aligns to result text; thin outer edge; generous row separation, no window chrome.",
    "surfaces": "Opaque quiet surface; result remains in the same plane, without a decorative camera move."
  },
  "components": [{
    "id": "result-panel",
    "name": "Task and result panel",
    "anatomy": "One heading strip over result rows; left alignment survives expansion; no native buttons or icons.",
    "typography": "Task heading remains semibold and stationary; smaller regular result labels have clear line spacing.",
    "surface": "Paper face, ink text, a thin accent boundary; no default OS title bar or bevel.",
    "states": "Compact task, partially expanded with first row, fully expanded with all rows, then still.",
    "reference_ids": []
  }],
  "scenes": [{
    "id": "result",
    "title": "Keep identity through expansion",
    "start": 0,
    "end": 2,
    "purpose": "Connect the compact task to its result without an unrelated screen cut.",
    "focus": "The persistent heading anchors the eye while new information appears below it.",
    "entry": "Compact panel already visible; no opening fade.",
    "exit": "Expanded panel holds; no closing motion is required.",
    "reference_ids": [],
    "absent_lanes": {"camera": "Locked view.", "text": "No separate text animation; rows belong to the panel reveal.", "audio": "Intentionally silent fixture."},
    "events": [{
      "id": "expand",
      "lane": "visual",
      "kind": "change",
      "start": 0,
      "end": 1,
      "subject": "Task panel becomes the result panel",
      "before": "Compact panel shows one heading.",
      "during": "Top and left edges stay fixed; right and bottom expand. First row appears only inside the growing surface.",
      "after": "All result rows are visible with the original heading unchanged.",
      "trigger": "Start of the explanation, not an invented user click.",
      "trajectory": "Expansion right and down; rows stay clipped to the face, with no label scaling or crossfade.",
      "pacing": "Accelerate early, then decelerate into the final size; reserve the next second for reading.",
      "component_ids": ["result-panel"],
      "reference_ids": []
    }, {
      "id": "read-result",
      "lane": "visual",
      "kind": "hold",
      "start": 1,
      "end": 2,
      "subject": "Read the result",
      "before": "Expanded panel.",
      "during": "Geometry and text remain still; no idle wobble or drifting camera.",
      "after": "Same visible result at the end of the design.",
      "trigger": "Expansion finishes.",
      "trajectory": "No spatial change.",
      "pacing": "One full second of stillness in this provisional fixture.",
      "component_ids": ["result-panel"],
      "reference_ids": []
    }],
    "keyframes": [{
      "at": 0, "label": "Compact task",
      "nodes": [{"component": "result-panel", "x": 10, "y": 15, "w": 40, "h": 25, "label": "Heading only", "fill": "paper"}]
    }, {
      "at": 0.5, "label": "Intermediate reveal; heading stays anchored",
      "nodes": [{"component": "result-panel", "x": 10, "y": 15, "w": 60, "h": 45, "label": "Heading and first clipped row", "fill": "paper"}]
    }, {
      "at": 1, "label": "Expansion complete",
      "nodes": [{"component": "result-panel", "x": 10, "y": 15, "w": 80, "h": 70, "label": "Heading and complete result", "fill": "paper"}]
    }, {
      "at": 2, "label": "Same result held",
      "nodes": [{"component": "result-panel", "x": 10, "y": 15, "w": 80, "h": 70, "label": "Heading and complete result", "fill": "paper"}]
    }]
  }]
}
```

## Schema v2: boards

Version 2 keeps every v1 field and rule, and adds what a reviewer needs to see
the film rather than colored boxes: the real aspect, background, text, surface
shape, identification pattern and opacity. Use v2 for new designs. Existing v1
files stay valid and byte-identical; a v1 design is not upgraded in place but
converted explicitly into a new file with its own identity, marking every
detail that the v1 data did not contain as a design decision, not a fact.

- Root adds `frame`: `{aspect, background}`. `aspect` is `"W:H"` with integers
  1..64 (for example `"9:16"`, `"16:9"`, `"1:1"`); `background` is a palette
  token. Boards are drawn at this aspect on this color; the document never
  substitutes a neutral canvas.
- Nodes add `key`, `kind` and `opacity`, and one group of kind-specific fields.
  `key` is a slug unique within a keyframe that names the same on-screen object
  across keyframes (three strips need three keys; the same strip keeps its key
  from first to last appearance). `opacity` is 0..1 and is drawn literally.
  Geometry, `component`, `label` and `fill` keep their v1 meaning: `x`/`w` are
  percent of frame width, `y`/`h` percent of frame height.
  - `kind: "text"` adds `content` (1..80 characters, the actual on-screen words)
    and `weight` (`regular`, `medium` or `bold`). The text is drawn in the
    system sans-serif at the box height, left-aligned at `x`; `fill` is the
    text color. The box width is the intended measure, not a fit guarantee.
  - `kind: "surface"` adds `shape` (`rect`, `notch-top-right`, `rounded`, `pill`
    or `circle`), `pattern` (`none`, `vertical`, `diagonal`, `chevron`,
    `horizontal` or `dots`) and `pattern_ink` (palette token; drawn only when
    the pattern is not `none`). Patterns are small identification marks at the
    inner left of the surface, never a claim about final artwork.

Motion annotation is derived by the renderer, never authored. A board is
compared by `key` with a reference state: in the full document and in every
detail panel, the preceding keyframe of the same scene; in a beat's overview
row, the previous overview board of that beat, so the row reads as before,
during, after and its first board is the unmarked starting state. An object
whose box moved at the same size gets a translucent afterimage with a dashed
edge at its previous position and an arrow between the centers; an object
that resized gets the afterimage and the arrow on the edge that traveled,
leaving anchored edges unmarked; an object that appears gets a solid outline;
an object that disappears gets the afterimage with a cross. Pure opacity
changes carry no mark because the opacity itself is drawn. Annotation uses
one fixed orange with a white halo, independent of the palette, and the
document explains it once.

## Compact review

New design reviews should use an Assistant-authored `review.json` alongside
the complete design. This separates the viewing hierarchy from production
intent without changing design bytes or their identity. Omitting `--review`
retains the full-document path for existing callers; it does not infer a
condensed overview by truncating fields.

First validate the complete design to obtain its actual `design_sha256`. Then
write the review against that value and check both inputs before publication:

```sh
python3 ~/.hermes/profiles/assistant/scripts/creative-timeline.py --spec /absolute/design.json --check
python3 ~/.hermes/profiles/assistant/scripts/creative-timeline.py --spec /absolute/design.json --review /absolute/review.json --check
python3 ~/.hermes/profiles/assistant/scripts/creative-timeline.py --spec /absolute/design.json --review /absolute/review.json --out /absolute/timeline-v2
```

Review fields are exact and required. Unknown fields fail, never disappear:

- Root: `version: 1`, `design_sha256` (the exact source-byte digest), `language`
  (`ja` or `en`, interface labels only), `title` (1..60 characters), `summary`
  (1..160), `issues`, `sections`. Author meaningful short text in the user's
  language; do not auto-shorten technical prose, invent conclusions or present
  a proposed choice as the user's decision.
- Issues: exactly one `{index, summary}` per design `open_items` entry, in the
  same order. `index` is the zero-based integer; `summary` is 1..80 characters.
  Every issue summary is visible before opening anything; the full original
  text remains in a sibling disclosure. Open items are design questions that
  need the user's judgment (an unresolved framing, a wording choice, a timing
  the user should confirm). Procedural status such as "not approved", "not
  verified", "not a finished video" or "not measured" is not an open item: it
  is identical for every proposal, so it belongs in the accompanying message,
  never in the document. Zero open items means no design question is pending,
  not established approval.
- Sections (1..160): `{id, scene, title, summary, start, end, event_ids, previews}`.
  `id` is a unique slug; `scene` is an existing scene ID. Title/summary have the
  same bounds as the root. Group by meaningful visual change, not every timestamp.
  Explain critical conditions and simultaneous behavior in the visible summary.
  Sections must partition every scene in original order with no gaps/overlap.
  Keep start/end in seconds; vertical spacing is for reading, not elapsed time.
- `event_ids`: nonempty list of the scene's actual events. Each referenced event
  must intersect the section, and references across sections must cover its
  whole interval. A long event may appear in multiple sections; do not clip its
  source timing or pretend parallel tracks are sequential to fit the grouping.
- Previews (1..3 per section): `{at, caption}` in strict time order. `at` must
  identify a supplied keyframe within the section; `caption` is 1..32 characters.
  For every change event, at least one overview preview in a referring section
  must lie strictly inside the event. This guards against hiding all intermediate
  states, not against choosing a semantically irrelevant sample. Assistant must
  check that the diagram/caption actually communicates the important change.
  Full keyframes, including those not chosen as overview previews, stay in the
  section's detailed view. No image interpolation or new media is performed.

The output adds an unchanged `review.json` and `review_sha256` to the ordinary
bundle/receipt. The HTML displays both identities. A changed review needs a new
bundle and the appropriate renewed viewing agreement even when the underlying
design hash is unchanged. Neither digest is evidence of user authority.

The bundle holds two documents. `timeline.html` is the viewing document,
shaped like an activity log: title, the one-line summary and the
duration/aspect; the decisions list when any open items exist; one legend
line; a lane filter (radio inputs styled as chips, CSS-only, one chip per
lane that has events plus "all"); then a single bordered list. Each reviewed
section contributes a muted header row (title, time range, one-line summary)
followed by one row per event in start order. A row shows a lane glyph, the
event subject, its time (`start→end` for a change, `start–end` for a hold),
the names of its parts, chips for lane and kind, change chips derived from the
same geometry differences that draw the board marks (moves / resizes /
appears / leaves / opacity, restricted to the event's own parts) and a
thumbnail of the event's end frame at the real aspect, marked against its
first frame. A row with more than one keyframe in its range or with parts
first pictured there is a `<details>` whose `<summary>` is the row; its count
chip (`+ n`) names the frames inside. Open, it lists every keyframe of the
range on an inner sub-rail as a small board with a time chip, its label and
change chips, followed by the parts first pictured there, each drawn alone
with its name. Other rows are plain. Nothing scrolls horizontally, because
in-app document viewers treat horizontal swipes and pull-down bounces as
dismiss gestures. Below the list: the open-item full text as a disclosure,
then one small line naming `spec.html` and the two identities. No prose
specifications appear in this document. `spec.html` is the complete written
design (the full-document renderer) for Creator and for anyone who asks; its
digest is `spec_sha256`. Review `previews` remain validated as the planner's
key frames but the log draws every frame of a row, so they do not select
what is shown.

Panels are siblings, allow multiple simultaneous opens, have real `<summary>`
controls and need no JavaScript. There are no modals, exclusive accordion groups,
nested disclosures, auto-opening panels or local-storage requirements. Links to
supporting sections target their visible disclosure headers, not hidden children.
State persistence across reopening the attachment, find-in-page, printing and
Telegram-specific interaction are not promised; test actual opening/closing on
the user's client. Existing display verification alone is not disclosure evidence.

Inspect the compact view for coherence and visible blockers, then open details
to confirm completeness. A structural pass does not prove the summaries
preserve meaning or improve usability.

## Delivery and limits

Attach the actual `timeline.html` as a Telegram document. Telegram message
HTML formatting does not guarantee attached-document rendering on every client;
check the intended opening route, without silently creating a hosted service.
All content remains in ordinary HTML if a viewer does not display inline SVG.
Use a new version for corrections and disclose unverified viewing conditions.
Reference links do not automatically upload, copy or license their contents.

The checker detects missing fields/IDs, interval gaps, absent lanes and missing
intermediate diagrams. It does not know whether prose is specific, key states
agree, a source was actually inspected or a button looks good. Assistant owns
those design judgments; Creator/hands own feasibility and rendered evidence.
Do not use a structural pass, an empty open-items list or a receipt as approval.
