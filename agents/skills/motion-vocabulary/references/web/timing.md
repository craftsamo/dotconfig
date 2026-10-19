# Timing, easing and springs: web builds

How each entry of [../timing.md](../timing.md) is built on a real web page: the trigger that starts it (load, enter view, scroll progress, hover, focus, press, drag, state or route change), the smallest tool that builds it (CSS, then the Web Animations API, then a library) and what replaces it under `prefers-reduced-motion: reduce`. Read the entry's Looks like and The tell first. Typical values here come from common web practice; a project's own motion tokens win.

How a web motion moves: principles, easing curves, springs and rhythm, expressed as CSS and JS values. Easings give the CSS form plus the GSAP / Motion name; springs give Motion `type: "spring"` values and a CSS `linear()` approximation (CSS has no spring easing; `linear()` samples a curve and fits one fixed duration). Typical web durations: 100-200ms micro feedback, 200-350ms UI state, 400-700ms larger entrances, over 800ms only for hero or decorative motion. Animate `transform`/`opacity`; keep timing tokens as CSS custom properties.

## Principles

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| staging（ステージング） | state change, press | Opening a card or modal: hero `scale(.96)` to 1 and the rest `opacity: .4` (scrim), both 250ms `cubic-bezier(.16,1,.3,1)`, ending together; `inert` on the background. | Opacity change only, no scale. |
| pose to pose / straight ahead（ポーズ・トゥ・ポーズ、ストレートアヘッド） | state change, loop | Pose to pose: `@keyframes` with explicit stops or WAAPI keyframes plus `ease-in-out` per segment. Straight ahead: a `requestAnimationFrame` loop computing each value from the previous (noise, particles, Canvas). | Show the end pose, or a static frame. |
| slow in and slow out（スローイン、スローアウト） | state change | `cubic-bezier(.65,0,.35,1)` (GSAP `power2.inOut`/`power3.inOut`) for on-screen moves; ease-out `(.22,1,.36,1)` for entrances, ease-in `(.64,0,.78,0)` for exits. CSS keywords `ease-in-out`. | Same easing, but travel shrinks to a short fade. |
| arcs（アーク、弧の軌道） | state change, click | Different easings on `x` and `y` (e.g. `x` `ease-out`, `y` `ease-in`) via two nested elements or two WAAPI animations; or `offset-path: path()` with `offset-distance`; GSAP `MotionPathPlugin`. | Move straight, or jump to the end. |
| secondary action（セカンダリーアクション） | state change, hover | Main animation `cubic-bezier(.22,1,.36,1)` 300ms; a child icon animates at a fraction of the travel, `animation-delay: 60ms`, `ease-in-out` (`cubic-bezier(.37,0,.63,1)`). | Drop the side motion, keep the main change. |
| exaggeration（誇張） | press, state change | `@keyframes` `scale(0)` to `1.2` to `1`, 400ms, or `cubic-bezier(.34,1.56,.64,1)` (GSAP `back.out(1.7)`); Motion spring `stiffness: 400, damping: 12`. | Fade in at full size. |
| solid drawing / depth（ソリッドドローイング、立体感） | hover, pointer move | Parent `perspective: 800px`, card `rotateY(-8deg)` to `8deg` via pointer position, `transform-style: preserve-3d`, 300ms `ease-out`; shadow `box-shadow` offset opposite (use a pseudo-element's `transform`, not animated `box-shadow`, for performance). | No tilt, a static shadow. |
| appeal（アピール、気持ちよさ） | press, state change | Knob `translateX` 200ms `cubic-bezier(.22,1,.36,1)`, a `scaleX(1.2)` keyframe mid-travel only, track colour `transition` with `transition-delay: 40ms`; keep native `<input type="checkbox" role="switch">`. | Knob jumps, colour changes at once. |
| cause-and-effect chain（原因と結果の連鎖） | state change, click | Chain via the `animationend`/`finished` promise of the previous animation, or GSAP timeline with relative start (`"-=0.05"`); same 250ms `cubic-bezier(.22,1,.36,1)` for each. | All at once, or only the final state. |
| anti-robotic jitter（アンチ・ロボット、ゆらぎ） | enter view | Base stagger via `animation-delay: calc(var(--i) * 60ms + var(--j))` with a small `--j` (0-25ms) set per element from a seeded list; slight duration variation (±30ms). | Same — no travel (opacity only, no stagger). |
| primary / secondary / ambient（主役・脇役・背景の三層） | load, scroll progress | Hero 500ms `cubic-bezier(.22,1,.36,1)`; secondaries 350ms, delay 150ms, smaller travel; background a slow `@keyframes` drift 20-40s `ease-in-out`, `alternate`, paused off-screen. | Hero fades in; secondary and ambient removed. |
| no dead frames（止まって見えるコマを作らない） | loop | Very slow `@keyframes` breathing (`scale(1)` to `1.02`, 6-10s, `cubic-bezier(.37,0,.63,1)`, `alternate`) on background or a hero element; run only while visible. | Remove the loop; leave static. |
| counter-motion（カウンターモーション） | enter view, scroll progress | `translateX(40px)` on hero and `translateX(-10px)` on background, same 400ms `cubic-bezier(.22,1,.36,1)`, started together; or scroll-driven with opposite `translate` signs. | Fade in place, no opposing travel. |

## Easing

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| linear（linear、等速） | loop, scroll progress | CSS `linear` (GSAP `"none"`) for spinners, marquees, scroll-scrubbed progress; match speed across loop seams. | Stop spinners/marquees; progress bars may stay. |
| ease-out expo（入り） | enter view, state change | `cubic-bezier(.16,1,.3,1)` (GSAP `expo.out`), 300-600ms; pair with an ease-in exit. | Short opacity fade. |
| ease-in expo（退場） | state change | `cubic-bezier(.7,0,.84,0)` (GSAP `expo.in`), 150-250ms, shorter than the entrance. | Instant removal or 100ms fade. |
| ease-in-out cubic（移動） | state change | `cubic-bezier(.65,0,.35,1)` (GSAP `power3.inOut`), longer for longer distances. | Instant move or fade. |
| thin-peak curve（シンピーク、ハウスカーブ） | state change | `cubic-bezier(.85,0,.15,1)` (GSAP `power4.inOut`/`expo.inOut` approximates); 600-900ms for a logo or large move; add a short `filter: blur(2px)` mid-way only if cheap. | Instant or fade. |
| whip curve（WHIP、ムチ） | state change | `cubic-bezier(.87,0,.13,1)` (GSAP `expo.inOut`), 500-700ms; GSAP `CustomEase` for a flatter start; optional motion smear via `filter: blur()` on the middle. | Fade only. |
| glide（グライド） | enter view, scroll progress | `cubic-bezier(.16,1,.3,1)` or `(.22,1,.36,1)` (GSAP `expo.out`/`power4.out`) over 900-1400ms. | Short fade. |
| ease-out quint（ease-out quint） | enter view | `cubic-bezier(.22,1,.36,1)` (GSAP `power4.out`), 500-800ms for large moves and scale-ups, with stagger 50-80ms. | Fade only. |
| Material 3 standard（Material 3 標準） | state change | `cubic-bezier(.2,0,0,1)`, 250-400ms for small UI; custom `CustomEase` in GSAP. | Instant or fade. |
| Material 3 emphasized（Material 3 強調、減速） | enter view | `cubic-bezier(.05,.7,.1,1)` (decelerate), 400-600ms for a hero entrance; pair with accelerate for the exit. | Fade only. |
| Material 3 accelerate（Material 3 加速、退場） | state change | `cubic-bezier(.3,0,.8,.15)` (GSAP near `power2.in`), 150-200ms, plus `opacity` to 0. | Plain opacity fade. |
| Apple standard（Apple 標準） | state change, hover | `cubic-bezier(.25,.1,.25,1)` (CSS `ease`), 200-300ms, for small state changes. | Same — no travel. |
| back out（オーバーシュート） | state change, press | `cubic-bezier(.34,1.56,.64,1)` (GSAP `back.out(1.7)`), 300-450ms; Motion `ease: backOut`. | Land directly, no overshoot. |
| back in（引いてから去る） | state change | `cubic-bezier(.36,0,.66,-.56)` (GSAP `back.in(1.7)`), 200-300ms for exits. | Fade out only. |
| back in-out（back in-out） | state change | `cubic-bezier(.68,-.6,.32,1.6)` (GSAP `back.inOut`), 500-700ms on a playful logo. | Direct move or fade. |
| sine in-out（呼吸） | loop | `cubic-bezier(.37,0,.63,1)` (GSAP `sine.inOut`), `alternate` infinite, 4-8s, small amplitude; add a pause button or cap `animation-iteration-count`. | Stop the loop. |
| circ out（circ out） | press, state change | `cubic-bezier(0,.55,.45,1)` (GSAP `circ.out`), 150-250ms. | Instant change. |
| elastic out（ゴム） | press, enter view | CSS: `linear(0, .22 2.1%, .84 6.3%, 1.22 9.6%, 1.28 11.5%, 1.04 18%, .9 21%, .97 27%, 1.02 34%, 1)` over 800-1200ms; GSAP `elastic.out(1, 0.3)`. | Land directly. |
| bounce out（弾む） | enter view, state change | CSS: `linear(0, .06 4%, .25 9%, .56 16%, 1 24%, .75 32%, .56 37%, .47 41%, .56 45%, .75 50%, 1 56%, .89 62%, .85 66%, .89 70%, 1 76%, .97 82%, 1 88%, 1)` over 700-1000ms; GSAP `bounce.out`; Motion `ease: bounceOut`. | Land directly. |
| steps / posterize（steps、コマ打ち） | loop, time | `steps(8, end)` (GSAP `steps(8)` or `SteppedEase`), e.g. sprite `background-position` or a blinking cursor `steps(1)`. | Show one frame. |
| SlowMo（速い→遅い→速い） | scroll progress, state change | CSS: `linear(0, .5 20%, .55 40%, .6 60%, 1)` shaped by hand (or `cubic-bezier(.3,.6,.7,.4)`); GSAP `SlowMo.ease.config(0.7, 0.7)`. | Fade only. |
| RoughEase（ガタつき） | state change | CSS `linear(0, .08 10%, .02 18%, .3 30%, .22 38%, .6 55%, .5 62%, .9 82%, 1)` or a seeded keyframe list; GSAP `RoughEase.ease.config({strength: 1, randomize: false})`. Use for glitch or error. | Direct move or static. |
| ExpoScale（等速に見えるズーム） | scroll progress, state change | Animate `scale` through exponential keyframes (e.g. 1, 1.35, 1.82, 2.46, 3.32 at even times) with `linear`; GSAP `ExpoScaleEase.config(1, 3)`. | No zoom, crossfade. |
| CustomWiggle（揺れ） | press, state change | CSS `@keyframes` `translateX` `-6px, 5px, -3px, 2px, 0`, 400ms `ease-in-out` (or `linear()` with decaying oscillation); GSAP `CustomWiggle.create("w", {wiggles: 6})` on bells and error shakes. | Colour flash or an outline instead of a shake. |
| CustomBounce with squash（CustomBounce＋スクワッシュ） | enter view, state change | `y` animation with the bounce `linear()` above, plus a `scaleY` keyframe `.8` at each contact point (`transform-origin: bottom`); GSAP `CustomBounce.create("b", {strength: 0.6, squash: 2})`. | Land directly, no squash. |

## Springs

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| snap spring（指ではじく） | press, drag | Motion `transition: {type: "spring", stiffness: 600, damping: 35, mass: 1}` (high stiffness, strong damping, low mass); CSS `linear(0, .6 6%, 1.04 16%, .99 28%, 1)` ~250ms. | Instant or 100ms fade. |
| bounce spring（ボール） | press, enter view | Motion `{type: "spring", stiffness: 300, damping: 8, mass: 1}` (or `bounce: 0.5`); CSS `linear(0, .5 6%, 1.15 14%, .92 24%, 1.05 34%, .98 46%, 1.01 60%, 1)` ~800ms; add squash. | Land directly. |
| smooth spring（ダンパー付きの扉） | state change, drag | Motion `{type: "spring", stiffness: 170, damping: 26, mass: 1}`; CSS `linear(0, .2 10%, .62 24%, .88 38%, .98 52%, 1)` ~600ms (no velocity carryover in CSS). | Fade or instant. |
| heavy spring（重い物） | state change | Motion `{type: "spring", stiffness: 100, damping: 30, mass: 3}` for big cards and sheets; CSS `linear()` over 900-1200ms. | Instant or fade. |
| react-spring default（react-spring default） | state change | Motion `{type: "spring", stiffness: 170, damping: 26, mass: 1}` (same values as react-spring's default config); react-spring `config.default`. | Instant or fade. |
| react-spring wobbly（react-spring wobbly） | press, hover | Motion `{type: "spring", stiffness: 180, damping: 12, mass: 1}`; react-spring `config.wobbly`; CSS `linear()` over ~1000ms with several decaying swings. | Land directly. |
| react-spring molasses（react-spring molasses） | scroll progress, load | Motion `{type: "spring", stiffness: 280, damping: 120, mass: 1}` (heavily over-damped); react-spring `config.molasses`; use for background layers. | Static at final position. |
| Framer bouncy（Framer bouncy） | press, state change | Motion `{type: "spring", stiffness: 500, damping: 15}` or `{type: "spring", visualDuration: 0.4, bounce: 0.35}`; CSS `linear(0, .7 8%, 1.12 18%, .96 30%, 1.02 44%, 1)` ~450ms. | Land directly. |
| Apple modal（Apple モーダル） | state change | Motion `{type: "spring", stiffness: 300, damping: 30, mass: 1}` open, close `ease: [.3,0,.8,.15]` 200ms; CSS open `linear(0, .5 10%, .9 24%, 1.01 40%, 1)` ~450ms. | Fade only. |
| critically damped（臨界減衰、揺れない最速） | drag, state change | Motion `{type: "spring", stiffness: 200, damping: 28.3, mass: 1}` (damping = 2 × √(stiffness × mass)); CSS `linear(0, .35 8%, .72 18%, .92 32%, .99 50%, 1)`. | Instant or short fade. |
| summed springs（目標が変わるバネ、足し合わせ） | state change, drag | Motion `animate(value, target, {type: "spring"})` on a `motionValue` — a new call carries current velocity; CSS transitions restart from the current value but lose velocity, so use JS for this. | Jump to the latest target. |
| split-edge springs（伸びるタブ、前後で別のバネ） | state change | Animate indicator `left` edge and `right` edge as two Motion values with different springs (front `stiffness: 500, damping: 35`; back `stiffness: 200, damping: 28`), swapped when direction flips; apply as `clip-path: inset()` or `transform` with width derived (avoid animating `width`). | Indicator jumps. |
| spring vs tween（スプリング vs トゥイーン） | state change, drag | Spring for gesture-driven or interruptible motion (Motion `type: "spring"`); tween for fixed-time UI (`cubic-bezier(.16,1,.3,1)`, 300ms CSS `transition`). Gestures and retargeting favour springs. | Same — no travel. |
| overshoot budget（オーバーシュートの予算） | state change | Success badge `cubic-bezier(.34,1.56,.64,1)` or spring `bounce: 0.4`; ordinary controls use `cubic-bezier(.22,1,.36,1)` with none; set via tokens `--ease-pop` and `--ease-plain`. | No overshoot anywhere. |
| inertia / momentum（慣性、投げて止まる） | drag, scroll | Motion `drag` with `dragTransition: {power: 0.3, timeConstant: 300, modifyTarget: v => Math.round(v / 80) * 80}`, or `animate(x, 0, {type: "inertia", velocity})`; native `scroll-snap-type` for lists; GSAP `InertiaPlugin`. | Drag stops where released, no glide. |
| projectile（放物運動、Physics2D） | click, state change | WAAPI with `x` linear and `y` quadratic keyframes sampled from `y = v·t − ½g·t²`; or `requestAnimationFrame` physics; GSAP `Physics2DPlugin` for particles; Canvas for many. | Place at the end point, no flight. |

## Timing and rhythm

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| duration by size（大きさで尺を変える） | state change | Tokens by area: chip 150ms, dialog 250ms, full-width banner 400ms, all `cubic-bezier(.22,1,.36,1)`; set `--dur` per component. | Same durations shortened to ≤150ms fade. |
| distance-scaled duration（距離で尺を変える、√ の法則） | state change | `duration = clamp(180, 120 + 60 * Math.sqrt(distance / 100), 600)` ms in JS when starting a WAAPI or FLIP animation; floor and cap. | Fixed 100ms fade. |
| exit faster than enter（退場は登場より短く） | state change | Enter 300ms `cubic-bezier(.16,1,.3,1)`, exit 150-200ms `cubic-bezier(.7,0,.84,0)`, less `translate` (e.g. 8px vs 24px); `.x { @starting-style { opacity: 0; } }` plus `transition-behavior: allow-discrete` for `display`. | Enter and exit both ≤100ms fades. |
| stagger: sequential（ステッガー：順番に） | enter view | `animation-delay: calc(var(--i) * 60ms)`; Motion `stagger(0.06)`; GSAP `stagger: 0.06` / `{each: 0.06}`; cap total at ~600ms by shrinking each gap as count grows. | All appear together, fade only. |
| stagger: from center（ステッガー：中央から） | enter view | Delay `calc(abs(var(--i) - var(--mid)) * 60ms)` (CSS `abs()`) or precompute; Motion `stagger(0.06, {from: "center"})`; GSAP `stagger: {each: .06, from: "center"}`. | All appear together. |
| stagger: from edges（ステッガー：両端から） | enter view | Delay `calc((var(--mid) - abs(var(--i) - var(--mid))) * 60ms)`; Motion `stagger(0.06, {from: "last"})` is not edges, so precompute; GSAP `stagger: {each: .06, from: "edges"}`. | All appear together. |
| stagger: random（ステッガー：ランダム） | enter view | Shuffle indices once (seeded) and set `--i`; total spread ≤500ms; GSAP `stagger: {each: .05, from: "random"}`. | All appear together. |
| stagger: grid diagonal（ステッガー：グリッド斜め） | enter view | `animation-delay: calc((var(--row) + var(--col)) * 40ms)`; GSAP `stagger: {grid: [rows, cols], from: "start", axis: null, each: .04}`; Motion `stagger(0.04, {startDelay})` with a computed index. | Grid appears at once. |
| snap, then hold（パッと出て、止めて見せる） | enter view, state change | 120-180ms `cubic-bezier(.16,1,.3,1)` arrival, then nothing moves for a time proportional to the content before the next change (carousel `setTimeout`). | Same — no travel. |
| speed ramp into a hit（スピードランプ） | enter view, state change | `cubic-bezier(.7,0,.84,0)` ease-in into a short impact: 80ms `scale(.96)` squash then back, plus a heavier shadow; on contact only. | Instant arrival, no squash. |
| overlap levels（重なり、オーバーラップの量） | state change | GSAP timeline position `"<+0.15"` or `"-=0.1"`; Motion `at: "-0.1"` in sequences; CSS: delay equal to 50-70% of the previous duration (half overlap flows). | No overlap, instant or fade. |
| reading hold（読める時間を確保する） | time | Auto-advancing content (carousel, toast): `duration = 1500 + words * 250` ms; pause on hover or focus; WCAG: provide pause controls; toasts use `role="status"`. | Stop auto-advance; user controls the change. |
