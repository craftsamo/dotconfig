# Steps Contract

The manifest contains only `steps`. Absolute physical local paths are
required; resolve known filesystem aliases before use. URLs, symlinks,
animated images, EXIF-rotated images, nonfinite numbers and unknown fields
are rejected. Maximum input file size is 64 MB; JSON is at most 1 MB.
Alpha is flattened onto the form's background; original bytes are retained.
Extremely narrow aspect ratios that display below 120 px on either stage
axis are rejected. Crop deliberately rather than silently stretching them.

```json
{
  "steps": [
    {"id": "open", "image": "/absolute/01.png", "target": [80, 90, 180, 48], "action": "click", "label": "Open settings", "duration": 2.5},
    {"id": "name", "image": "/absolute/02.png", "target": {"text": "Name", "language": "eng"}, "action": "type", "typed": "Example", "label": "Enter a name", "duration": 3},
    {"id": "done", "role": "done", "image": "/absolute/03.png", "label": "Settings saved", "duration": 2}
  ]
}
```

An optional id follows the slug rules and must be unique (default s1, s2,
etc.). Reusing an image is allowed. All screens must have identical pixel
dimensions. Explicit rectangles are in original screenshot pixels, not
the displayed canvas. Text anchors are exact case-insensitive whole-token
or same-line phrase matches after whitespace normalization. Language is
eng, jpn or eng+jpn; absent, Japanese script selects jpn, otherwise eng.
TSV evidence is preserved. Zero or multiple matches return candidate text
and rectangles; choose an explicit rectangle rather than a guessed match.
Missing language data returns an actionable error, never an automatic install.

Every non-done step needs target and label (48 characters maximum).
Actions: click (default), type (requires typed, at most 80 characters), none
(highlight without a press). Done occurs exactly once, last, with no target
or typed value. The screenshot, not generated text, must prove completion.
Frames are decorative chrome: browser, macos, ios, android, none. Mobile
uses a tap ring, no arrow. `auto` picks browser for wide screens, ios for tall.

Choose `duration` OR `track` per step. Silent steps last at least 2 seconds;
typing requires max(2, 1.4 + .06 * characters + .5). A track is a finished
WAV from audio-creator, with matching adjacent `<stem>.words.json` containing
file, duration, PCM SHA-256 (48 kHz mono s16le), words and captions. Validate
nonoverlapping finite intervals against decoded duration. The helper never
runs ASR or TTS. Track duration plus .3 s lead and .5 s tail is the clock,
extended only for typing. A 2.5 s goal precedes steps, showing the task and
optional app text as a short supporting line; total <=60 s. The final done
step is the outro: its supplied label and real screen hold for its duration.

The camera contains the original screen, then punches toward the target
with bounded pan/scale. The form's optional `max_zoom` caps scale at 1..2
(default 2); 1 disables the punch. It never changes target rectangles or
their click centers. Prefer this cap to enlarging a target inaccurately.
Screen changes are task-state cuts after the action,
not marketing scene transitions; no crossfades or idle animation. The shared
device and pointer carry the viewer through the task. Typed text is a visual
overlay, retained along with the camera position across identical screenshot
bytes, not proof that the application accepted it. Inspect the next screen.
