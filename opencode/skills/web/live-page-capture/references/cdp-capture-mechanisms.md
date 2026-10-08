# CDP capture mechanisms — choosing and proving one

The two properties that decide a mechanism are **raster size** and
**cadence**. Prove both on the real page during the spike; neither can be
repaired afterwards.

## Decision table

| Mechanism | Cadence | Raster | Use when |
| --- | --- | --- | --- |
| `Page.captureScreenshot` per step | Whatever you pace; no real-time guarantee | Honors `clip.scale`; otherwise surface size | Stepped capture where each frame is a settled state |
| `Page.startScreencast` | Real-time, ack-throttled, gaps during motion | Surface size; `maxWidth`/`maxHeight` only cap | Rough motion reference, timing analysis, or CFR-resampled delivery under stated gap criteria |
| `Emulation.setVirtualTimePolicy` + screenshot per budget | Exact grid — advance a fixed budget per frame | As configured at launch | Deterministic fps; verify native input still advances (see below) |
| `HeadlessExperimental.beginFrame` | Exact grid, screenshot returned per frame | As configured at launch | Deterministic fps; older headless builds, non-macOS |

## Raster size

The compositor surface, not the page's emulated DPR, decides PNG dimensions.

- `Emulation.setDeviceMetricsOverride({deviceScaleFactor: 3})` changes what
  the page reports for `devicePixelRatio` and which image sources it picks.
  It does not, by itself, make the captured raster denser.
- Set the scale at launch instead: `--force-device-scale-factor=<n>` with
  `--window-size=<cssW>,<cssH>`, so the surface itself is `cssW*n x cssH*n`.
- Or capture with an explicit clip:
  `Page.captureScreenshot({captureBeyondViewport: false, clip: {x: 0, y: 0, width: cssW, height: cssH, scale: n}})`.

After either, assert two things: the PNG probes at the target pixel size, and
the page still reports the intended CSS viewport. The layout must stay a
phone; only the raster gets denser.

## Cadence

A fixed frame period is only guaranteed when a clock you control drives the
frames.

- **Virtual time**: set a policy with a budget equal to the frame period,
  await `Emulation.virtualTimeBudgetExpired`, screenshot, repeat.
- **BeginFrame**: request each frame with an explicit `frameTimeTicks` on the
  renderer clock, taking the screenshot the call returns.

Either way, the question that decides usability is whether **native input
momentum and snap animations advance under that clock**. Test it directly:
dispatch a real swipe, advance the clock one frame period at a time, log the
scroll offset per step. Progression that ends on an exact snap offset means
the clock drives native behavior.

When using a controlled clock, keep `--disable-threaded-animation` and
`--disable-threaded-scrolling` so those animations run on the main thread
where the clock applies. **Do not carry those flags into a real-time
capture** — moving scroll off the compositor and onto an already-contended
main thread makes real-time cadence dramatically worse (measured: max motion
gap roughly doubled on an otherwise identical take).

### Controlled clocks vs native input

A frozen JavaScript clock is not a frozen animation clock: `performance.now`
can sit still under virtual time while `document.timeline` and running
animations keep advancing on wall time. Verify what the clock actually
governs instead of assuming it governs everything.

Controlled-clock paths also interact badly with dispatched input on some
platforms — observed on macOS: under `setVirtualTimePolicy`, a touch gesture
stalls mid-sequence (`Input.dispatchTouchEvent` stops responding), and
`Target.createTarget({enableBeginFrameControl: true})` is rejected outright
with `BeginFrameControl is not supported on MacOS yet`. Probe both on the
target platform early, because they invalidate the deterministic-cadence
plan before any recorder work is worth doing. Treat these as things to
re-probe, not as permanent facts — they are build- and platform-specific.

### When the grid is unreachable

If no controlled clock is usable, real-time capture plus timestamp-based CFR
resampling is the honest fallback, but it must be accepted on explicit
criteria rather than assumed adequate: a maximum tolerated no-update gap
during motion, and a maximum run of identical frames mid-motion (intended
holds excluded from both). State the duplicate and dropped frame counts in
the report. When even that fails at full length, splitting the recording into
shorter takes joined at settled, stationary landing points preserves fidelity
— never join mid-motion, never interpolate, and disclose the split.

## When a mechanism fails

A crash or timeout is a configuration result, not a verdict on the API.
Before concluding a mechanism is unavailable, retry it with the smallest
flag set that still enables it, and drop rendering-pipeline flags one at a
time. On macOS headless, `CVDisplayLinkCreateWithCGDisplay failed` in the
browser log points at the display-link path — try `--disable-gpu` or a
software backend before abandoning the mechanism.

Record each attempt with its exact flags and the artifact it produced.
Distinct configurations are distinct attempts; rerunning an identical failing
configuration is a retry and buys nothing.
