---
name: web-live-page-capture
description: >-
  Use when recording a live web page's real motion (native scroll-snap, momentum,
  lazy images, carousel gestures) to video faithfully via Chrome DevTools
  Protocol frames and ffmpeg (実サイトの動きを動画にする, スクロール録画, デモ動画,
  プロモ動画, 縦型リール, "record the page scrolling", "show the carousel
  snapping", "capture the live demo to video", CDP screencast, puppeteer).
license: MIT
compatibility: Needs a Chromium-based browser with remote debugging, node or python CDP client, and ffmpeg.
---

# Live Page Video Capture

Record what a real page actually does — native scroll-snap, momentum, lazy
images, carousel gestures — as a frame sequence that can be encoded and
assembled into a deliverable video.

## When to Use

Promo reels and demo videos built from a real site rather than a mockup:
"record the page scrolling through its sections", "show the carousel
snapping", "make an Instagram vertical from the live demo", "capture the
mobile experience at 1080x1920".

Not for: rendering an animation you authored yourself (that is a normal
headless render), or verifying a single static image (`visual-artifact-
verification`).

## Core principle

**The page's real behavior IS the deliverable — never modify the page to make
capture easier.** The moment you set `scrollSnapType='none'`, force
`loading='eager'`, or call `scrollTo()` to place the viewport, the recording
no longer shows the thing it claims to show. Every convenience of that kind
silently converts a document of real behavior into a reconstruction.

The capture harness may configure the *browser* (launch flags, emulation,
clock). It may never configure the *page* (DOM, CSS, attributes, storage,
scroll position by script).

## Workflow

### 1. Write the fidelity contract before any code

List explicitly what must not change, because these are the things a capture
script reaches for under pressure:

- `scroll-snap-type` / `scroll-behavior` on the scroll container
- `loading` attributes on images; any forced `decode()`
- DOM, CSS, text, spacing, storage (`localStorage`, cookies, theme keys)
- scroll position set by script instead of by input

Movement must come from dispatched input events only. Keep this list in the
spec file the recorder is built from; it is also the grep-list in step 6.

### 2. Recon the scroller read-only

Before designing gestures, measure: the scroll container, `scrollHeight` /
`clientHeight`, computed snap and behavior values, each section's offset and
height, and which horizontal carousels are genuinely scrollable
(`scrollWidth > clientWidth`) with their card pitch. Inventory every `<img>`
with `complete` / `naturalWidth`.

Section offsets give you the landing table that later proves snap survived.

### 3. Spike the capture mechanism before building the recorder

This is a go/no-go gate. Two properties must be demonstrated on the real
page, not assumed — they are the two that routinely fail:

- **Raster size**: PNGs come out at the intended output resolution.
- **Cadence**: frames land on a fixed fps grid with no gaps during motion.

**Prove cadence at production length, not just in a short trial.** Capture
cost accumulates, so a 2-gesture trial can pass comfortably while the
full-length take fails on the same mechanism at the same settings. A trial is
only a screen for obvious unusability; the acceptance measurement is the
full-length take.

Mechanism options and their tradeoffs are in
`references/cdp-capture-mechanisms.md`. Record the outcome as a small report
with the exact browser flags used, so the recorder inherits a proven
configuration rather than a guess.

**Judge a "not possible" verdict by what was actually tried.** A spike that
failed on two mechanisms has established that those two configurations
failed, not that the capability is unavailable — verify the failing evidence
yourself (re-probe the artifacts), then check the untried standard causes
before accepting the verdict. Raster and cadence failures each have a known
fix in the reference file, so a NO-GO that never tested them is premature.
When the untried hypotheses are exhausted and still fail, the limit is real:
report it with the evidence rather than degrading the deliverable to fit.

### 4. Prewarm inside the recording context

Lazy images must be loaded by traversing the page with the same kind of
input used for recording, in the **same page/context** that will be
recorded, then returning to the start. A prewarm performed in a different
context or a previous browser launch warms nothing.

Assert afterwards that every image is `complete && naturalWidth > 0`. Prewarm
gestures sit outside the recorded window and do not count against gesture
budgets in the spec.

### 5. Record with real input and a per-frame ledger

Drive movement with `Input.dispatchTouchEvent` (or the pointer equivalent),
never synthetic scrolling. Per gesture: swipe -> poll until the settled
offset stops changing -> hold. Log two ledgers as you go:

- **per input**: type, coordinates, dispatch timestamp, resulting frame index
- **per frame**: index, virtual/wall time, scroll offsets of every scroller,
  PNG hash

These ledgers are the evidence for the report; reconstructing them afterwards
from the video is not possible.

### 6. Verify the recording before encoding

- **Landing table**: every settled offset is an exact multiple of the section
  height, zero tolerance. This is the proof that native snap was preserved.
- **Gesture count**: horizontal swipes in the recorded window match the spec
  exactly.
- **Page unchanged**: computed snap/behavior values and page text identical
  before and after; zero non-GET requests; no navigation beyond the target.
- **Source grep**: the recorder source contains none of the forbidden APIs
  from step 1 (`.style`, `loading=`, `scrollTo`, `scrollIntoView`,
  `synthesizeScrollGesture`, `mouseWheel`, `localStorage`).

### 7. Encode, assemble, and prove frame identity

Encode the body all-intra with pinned parameters so it can be stream-copied
rather than re-encoded into the final timeline, then compare decoded frame
hashes between the body and the uncovered region of the assembled output —
all frames, not samples. Recipes and the exact ffmpeg invocations are in
`references/encode-and-assemble.md`.

## Pitfalls

- **CDP screenshots raster at the compositor surface size, not the emulated
  DPR.** `Emulation.setDeviceMetricsOverride` with `deviceScaleFactor: 3`
  makes the *page* report `devicePixelRatio` 3 while the surface stays at CSS
  size, so a 360x640 emulation yields 360x640 PNGs. Set the device scale at
  launch (`--force-device-scale-factor`) with a matching `--window-size`, or
  pass an explicit `clip` with `scale` to `Page.captureScreenshot`.
- **`maxWidth` / `maxHeight` on a screencast are caps, not requests.** They
  never upscale. Re-probe the actual PNG dimensions yourself before trusting
  any capture pipeline's claimed resolution.
- **Real-time screencast cannot guarantee a fixed fps grid.** Frames are
  ack-throttled and delivered on swap, so motion intervals show gaps far
  larger than the frame period. Use a deterministic clock when exact cadence
  matters; resampling a gappy stream to 30fps fabricates smoothness that was
  never captured.
- **A vertical-only prewarm never loads offscreen horizontal cards.** Lazy
  images inside a carousel load when that carousel scrolls, so traverse every
  axis that holds lazy content to its end and back.
- **Check the touch-start point with `elementFromPoint` before dispatching.**
  A gesture beginning on a link or button turns a read-only capture into a
  navigation or a form interaction.
- **Duplicate real frames for held stills; do not hold a "live" frame.** A
  hero with an infinite animation is never pixel-static, so a still specified
  as static must be built by repeating one captured frame.
- **A settled offset near a snap point is not a snap.** Assert exact
  multiples of the section height; a tolerance window makes a failed snap and
  a smooth-scroll landing look identical at ±3px.
- **Spawn your own browser with `--remote-debugging-port=0` and read the real
  port from `DevToolsActivePort` in your own user-data-dir.** A script that
  attaches to a fixed port can land on an already-running browser carrying the
  owner's logins, and leaks the tabs it opens.
- **Read a cadence failure's SHAPE before blaming the hardware.** Per-gesture
  numbers that start inside budget and degrade monotonically across the take
  indicate accumulation in the harness (in-loop hashing, per-frame journal
  appends, a draining write queue, retained frame buffers); a genuine machine
  ceiling is roughly uniform from the first gesture. Fix the accumulation —
  ack then hand off and drop the reference, batch journals after acquisition,
  drain the write queue during the scripted holds — before declaring a limit.
- **Drive traversal loops by measured position, not a fixed repetition
  count.** A swipe dispatched while the previous one is still settling is a
  no-op, and a fixed-count loop counts it as progress and stops short of the
  boundary — then the harness's own completeness assertion fails and looks
  like a mechanism failure. Loop until the offset stops changing, retry
  no-ops without counting them, and keep the count only as a safety valve.
- **Do not count pre-acquisition harness errors against a mechanism's attempt
  budget.** A crash before the first frame (an unhandled target creation, a
  bad assertion) tested the harness, not the mechanism; retiring a viable
  mechanism on those attempts abandons it having never measured it. Reset the
  budget when the fix is in the harness, and record why in the ledger.

## Files

- `references/cdp-capture-mechanisms.md` — mechanism decision table: raster
  size, cadence, clock control, and how to prove each one.
- `references/encode-and-assemble.md` — ffmpeg parameters for stream-copyable
  bodies and full-frame identity verification.
