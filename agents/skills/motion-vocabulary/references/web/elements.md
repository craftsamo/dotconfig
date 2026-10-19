# Element motion: web builds

How each entry of [../elements.md](../elements.md) is built on a real web page: the trigger that starts it (load, enter view, scroll progress, hover, focus, press, drag, state or route change), the smallest tool that builds it (CSS, then the Web Animations API, then a library) and what replaces it under `prefers-reduced-motion: reduce`. Read the entry's Looks like and The tell first. Typical values here come from common web practice; a project's own motion tokens win.

How a single element or a small group enters, moves, scales, rotates, reacts and draws attention on a real page. Easing names: `--out: cubic-bezier(.22,1,.36,1)`, `--in: cubic-bezier(.64,0,.78,0)`, `--inout: cubic-bezier(.65,0,.35,1)`; springs use `linear()` or Motion `type: "spring"`. Prefer `transform`, `opacity`, `clip-path` and `filter`; the few rows that animate `background-position` or `border-image` repaint, so keep them small. For display toggles (dialog, popover, `display: none` to block) use `@starting-style` written with a selector (`.x { @starting-style { opacity: 0; } }` or `@starting-style { .x { opacity: 0; } }`) plus `transition-behavior: allow-discrete`; list reorders use FLIP or Motion `layout`.

## Entrance and exit

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| fade slide（フェード＋スライド） | load, enter view | `.x { @starting-style { opacity: 0; translate: 0 12px } }` with `transition: opacity 400ms var(--out), translate 400ms var(--out)`; for scroll use IntersectionObserver to add a class once. Add `transition-behavior: allow-discrete` if `display` toggles. | Opacity fade only, 150ms, no translate. |
| soft rise（ソフトライズ） | load, enter view | Transition `opacity`, `translate: 0 8px` and `filter: blur(6px)` to none over 600ms `ease-out`; clear the blur a little earlier via a `@keyframes` at 80%. Blur repaints, so keep it on small elements. | Fade only, no blur or lift. |
| snap in（スナップイン） | load, state change | `transition: translate 180ms cubic-bezier(.16,1,.3,1), opacity 120ms` from `translate: 24px 0`, or toggle a class with no tween for a hard cut. | Instant state, no travel. |
| split reveal（スプリットリビール） | load, enter view | One overlay with `clip-path: inset(0 50% 0 50%)` growing to `inset(0 0 0 0)` on the subject, or two pseudo-elements `translateX(-100%)` and `translateX(100%)`, 500ms `var(--inout)`. | Subject shown at once or a 150ms opacity fade; no covers. |
| diagonal wipe（斜めワイプ） | enter view, state change | Animate `clip-path: polygon()` from a zero-area sliver such as `polygon(0 100%, 0 100%, 0 100%)` to the full `polygon(0 0, 100% 0, 100% 100%, 0 100%)` over 600ms `cubic-bezier(.76,0,.24,1)`; same point count both ends so it interpolates. | Shown fully, optional 150ms fade. |
| trail exit（残像アウト） | state change | On remove, clone the node 3 times (`cloneNode`), place absolutely, and `element.animate` each to `translateX(120%)` with `delay: i * 40`, opacity `0.5 - i*0.12`, 350ms `ease-in`; remove clones on `finish`. | Plain 150ms fade out, no clones. |
| collapse away（折りたたみ退場） | state change | `transform-origin: bottom; transition: scale 400ms var(--in), opacity 400ms` to `scale: 1 0.02`; then `display: none` via `allow-discrete` or on `transitionend`. Avoid animating `height`. | Instant removal or 150ms fade. |
| 3d fold in（3D折り込み） | enter view, state change | Parent `perspective: 800px`; child `transform-origin: top; rotate: x -80deg` to `rotate: x 0deg` over 600ms `var(--out)`, `backface-visibility: hidden`. | Fade only, no rotation. |
| shrink fade exit（縮小フェード退場） | state change | `transition: scale 300ms var(--in), opacity 300ms, filter 300ms` to `scale: .6; opacity: 0; filter: blur(3px)`, origin centre, then `display: none` via `allow-discrete`. Motion: `AnimatePresence` with `exit`. | Opacity fade 150ms, no scale or blur. |

## Movement

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| linear travel（一定速移動） | load, loop | `animation: slide 2s linear forwards` with `@keyframes slide { to { translate: 400px 0 } }`; for a gentle stop chain a second short `ease-out` animation. Marquees use `linear infinite` and need a pause control. | Jump to end state, no travel. |
| smooth arrival（なめらかな到着） | state change, load | `transition: translate 700ms cubic-bezier(.45,0,.2,1)`; scale duration with distance (about 1ms per 1px, capped 300 to 900ms). Use FLIP when the move comes from a layout change. | Instant move or 120ms fade. |
| arc travel（弧を描く移動） | state change | Two stacked animations on one element: `translate` x with `linear` on the outer wrapper and y keyframes `0, -80px, 0` with `ease-in-out` on the inner, same duration; or `offset-path: path(...)` with `offset-distance` 0 to 100%. | Straight instant move. |
| anticipated move（予備動作つき移動） | press, state change | `element.animate([{translate:'0'},{translate:'-12px',offset:.2},{translate:'200px'}],{duration:600,easing:'cubic-bezier(.68,-.6,.32,1.6)'})`, or Motion keyframes `x: [0,-12,200]`. | Direct move, no wind-up, or instant. |
| heavy stop（重い停止） | state change | Move with `translate 500ms cubic-bezier(.2,.8,.2,1)`, then WAAPI keyframes `scale: 1 1 → 1.12 .88 → 1` over 250ms with `transform-origin` at the leading edge. | Land with no squash. |
| path follow（パス追従） | scroll progress, load | CSS `offset-path: path("M0 0 C 120 -80 240 80 360 0"); offset-rotate: auto; animation: ride 3s ease-in-out forwards` with `offset-distance: 0%` to `100%`; or scrub with `animation-timeline: view()`. Fallback: GSAP MotionPathPlugin. | Placed at the end position, no travel. |
| stagger follow（段差追従） | state change, load | Per item `style="--i: n"` and `animation-delay: calc(var(--i) * 60ms)` with `translate` 0 to target, 500ms `var(--out)`; Motion: `stagger(0.06)`. | Items move together instantly, no delay. |
| magnetic snap（マグネット吸着） | drag, hover | On pointermove compute distance to the target; inside 80px, set `translate` toward it with `transition: translate 250ms cubic-bezier(.34,1.56,.64,1)`. Drop zones use `scroll-snap` or snap in JS. Outline the target with `outline-offset`. | Snap straight to target on release, no pull or overshoot. |
| zigzag travel（ジグザグ移動） | state change | Outer wrapper `translate` x linear; inner keyframes `translate: 0 0, 0 -24px, 0 24px, 0 -12px, 0 0` over the same 1s with `ease-in-out`. | Direct move, no zigzag. |
| momentum drift（慣性ドリフト） | drag, state change | Release velocity in JS drives a `linear()` spring or Motion `inertia` (`power: .8, timeConstant: 300`); CSS fallback `translate 900ms cubic-bezier(.2,.9,.3,1.08)`. | Stop at the target at release, no coast. |
| waypoint hop（ウェイポイントホップ） | click, state change | Chain WAAPI animations per hop: `translate` y `0 → -30px → 0` (`ease-out` then `ease-in`) plus x advance, `scale: 1 .9` for 80ms at landing; `await anim.finished` between hops. | Jump marker to marker instantly. |

## Scale

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| pop scale（ポップスケール） | load, state change | `.x { @starting-style { scale: .1; opacity: 0 } }` with `transition: scale 350ms cubic-bezier(.34,1.56,.64,1), opacity 150ms`; Motion `type: "spring", stiffness: 400, damping: 18`. | Opacity fade only, no scale. |
| breathing scale（呼吸する拡縮） | loop | `animation: breathe 4s ease-in-out infinite alternate` between `scale: .97` and `1.03`; pause off-screen via IntersectionObserver and `animation-play-state`; add a pause button or cap `animation-iteration-count` (for example 5) because it runs past five seconds. | Remove the loop; static at scale 1. |
| elastic scale（エラスティックスケール） | load, state change | Springy `linear()` easing with 4 to 5 decaying peaks over 800ms (`transition: scale 800ms linear(0, .6 10%, 1.18 22%, .92 36%, 1.05 52%, .98 70%, 1)`), or Motion spring `damping: 8`. | Instant final scale or short fade. |
| axis stretch（軸方向ストレッチ） | state change | WAAPI on the moving node: `scale: 1 1 → 1.4 .75 → 1 1` timed to the speed peak (offset .5) while translating; `transform-origin` centre. Never animate width. | Plain move, no distortion. |
| focus pulse（フォーカスパルス） | focus, state change | `::after { border: 2px solid; border-radius: inherit; animation: ping 600ms var(--out) 2 }` with `to { scale: 1.6; opacity: 0 }`; fire on `:focus-visible` or after an update. | One 150ms static outline instead of the ring. |
| depth zoom（奥行きズーム） | enter view, load | Parent `perspective: 600px`; child `transform: translateZ(-400px)` to `translateZ(0)`, `filter: blur(8px)` to none, opacity 0 to 1, 900ms `cubic-bezier(.76,0,.24,1)`. | Fade only, no zoom. |
| soft shrink（ソフトシュリンク） | state change | `transition: scale 300ms ease-in, opacity 300ms` to `scale: .85; opacity: 0`, centre origin; Motion `exit={{scale:.85,opacity:0}}`. | Opacity fade only. |
| impact squash（インパクトスクワッシュ） | state change | After the drop, WAAPI `scale: 1 1 → 1.25 .75 → 1 1` over 400ms with a spring `linear()` easing, `transform-origin: bottom`. | Land with no squash. |
| center punch（センターパンチ） | load, press | `.x { @starting-style { scale: .2 } }` with keyframes `scale: .2, 1.25 40%, 1` over 400ms `cubic-bezier(.34,1.56,.64,1)`; no reflow since only `scale` changes. | Instant final size or fade. |
| width reveal（横幅リビール） | enter view, state change | Bar `transform-origin: left; scale: 0 1` to `1 1`, 400ms `var(--out)`; label `opacity` with `transition-delay: 250ms`. Do not scale the text itself. | Show bar and label at once, short fade. |
| depth pullback（奥行きプルバック） | load, enter view | Keyframes from `scale: 2.2; filter: blur(10px) brightness(1.6)` to `scale: 1; filter: none` over 1.2s `var(--inout)`; on large nodes prefer opacity plus scale and skip filter. | Show the subject in its final state. |

## Rotation

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| simple turn（シンプルターン） | hover, state change | `transition: rotate 500ms var(--inout)` to `rotate: 180deg` (a chevron or a toggle), centre origin. | Instant rotation or swapped icon. |
| spin stop（スピン停止） | load, press | `rotate: 0` to `1080deg` over 1.2s `cubic-bezier(.1,.7,.1,1)`; end angle a multiple of 360 so the logo lands upright. | Set to final angle, no spin. |
| pendulum wobble（振り子の揺れ） | load, hover | `transform-origin: top center; animation: swing 1.6s ease-in-out` with keyframes `rotate: 12deg, -9deg 30%, 6deg 50%, -3deg 70%, 0deg`. | No swing, static. |
| coin spin（コインスピン） | load, press | Parent `perspective: 800px`; `rotate: y 0deg` to `y 1440deg` over 1.1s `cubic-bezier(.1,.7,.2,1)`; ends at a multiple of 360. | Fade to final face, no turns. |
| tilt reaction（チルトリアクション） | press, hover | On pointerdown set `rotate` toward the pointer side by 4deg with 80ms `ease-out`; on release `transition: rotate 500ms linear(0, 1.3 25%, .9 50%, 1.03 75%, 1)` to 0. | Skip tilt; use a colour change. |
| tumble in（タンブルイン） | load, enter view | `.x { @starting-style { translate: -120% 0; rotate: -270deg } }` with `transition: translate 600ms var(--out), rotate 800ms var(--out)`. | Fade in place, no roll. |
| counter rotation（カウンターローテーション） | load, loop | Outer `animation: spin 8s linear infinite`; inner the same keyframes `animation-direction: reverse`, same pivot, finite for a one-shot with `ease-in-out`; for the endless form add a pause button or cap `animation-iteration-count` at 3. | Stop both; static at rest angle. |
| gyroscope rotation（ジャイロ回転） | load, loop | Nested `div`s with `transform-style: preserve-3d` under `perspective: 900px`; each ring animates `rotateX`, `rotateY`, `rotateZ` with offset durations (6s, 8s, 10s) `ease-in-out infinite`; add a pause button or cap `animation-iteration-count` at 3. | Freeze at a pleasant angle. |
| rotate reveal（回転リビール） | enter view, state change | `perspective: 900px` parent; `transform-origin: left; rotate: y -80deg; opacity: 0` to `rotate: y 0deg; opacity: 1` over 500ms `var(--out)`. | Fade only. |

## Bounce and reaction

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| overshoot（オーバーシュート） | state change, load | `transition: translate 400ms cubic-bezier(.34,1.56,.64,1)`; the end value is the exact target, overshoot comes from the easing alone. | Move with `ease-out` and no overshoot, or instantly. |
| bounce landing（バウンス着地） | load, state change | Keyframes `translate: 0 -200px, 0 0 30%, 0 -60px 50%, 0 0 70%, 0 -15px 85%, 0 0` with per-keyframe `animation-timing-function` alternating `ease-in` and `ease-out`; or a `linear()` bounce curve. | Place at rest, no hops. |
| spring follow（スプリング追従） | drag, state change | Motion `useSpring` chained, each follower with lower stiffness; or per item `animation-delay: calc(var(--i) * 70ms)` with an overshooting `linear()` ease. | Followers move together instantly. |
| rubber band（ラバーバンド） | drag, press | While dragging set `scale` via `calc(1 + d/300) calc(1 - d/600)` with origin on the unpulled side; on release a `linear()` spring `transition: scale 700ms`; Motion `drag` with `dragElastic`. | Return directly with no wobble. |
| recoil（リコイル） | press, state change | Keyframes `translate: 0, 40px 30%, 28px 55%, 33px 100%` over 450ms with `ease-out` segments; the kickback is a small fraction of the move. | Move once with no kick. |
| double bounce（ダブルバウンス） | load, state change | Keyframes `0 -160px, 0 0 40%, 0 -40px 65%, 0 0 85%, 0 -8px 93%, 0 0` using `ease-in` for falls and `ease-out` for rises; exactly two rebounds. | Place at rest. |
| snap back（スナップバック） | drag, press | Keep the stretch as `scale`/`translate` from pointer move; on release `transition: scale 350ms cubic-bezier(.34,1.56,.64,1), translate 350ms cubic-bezier(.34,1.56,.64,1)` to the rest transform. Motion `dragSnapToOrigin`. | Return at once. |
| after shake（余震） | state change | Keyframes `translate: 6px 2px, -5px -2px, 3px 1px, -2px 0, 1px 0, 0` over 600ms `ease-out`, amplitude decaying, ending on the rest transform. | No tremor; static after the hit. |
| settle drop（沈み込み着地） | state change | Fall `translate 300ms ease-in`, then keyframes `translate: 0 6px; scale: 1.06 .94` to `0 0; 1 1` over 600ms `ease-out`. | Land with no sink. |
| drag resistance（ドラッグ抵抗） | drag | Pointer position feeds a lerped target (`x += (px - x) * 0.15` in rAF) or Motion `useSpring(x, {stiffness: 120, damping: 20})`; stretch `scaleX(1 + gap/400)`, spring back on release. | Follow the pointer 1:1, no lag or stretch. |
| follow through（フォロースルー） | state change | Parts with `animation-delay` offsets of 40 to 120ms and keyframes `rotate: 0, 10deg 50%, -3deg 75%, 0`; the parent stops first with `ease-out`. | Parts stay still. |

## Lists and grids

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| staggered list（リスト順次表示） | enter view, load | `li { animation: in 500ms var(--out) both; animation-delay: calc(var(--i) * 60ms) }` with `from { opacity: 0; translate: 0 12px }`; start via IntersectionObserver; cap the stagger total near 600ms. | All rows appear together, fade only. |
| cascade list（カスケード表示） | enter view, load | Same stagger with `from { translate: 0 -16px; opacity: 0 }` and keyframes `translate: 0 -16px, 0 3px 70%, 0 0` over 600ms; delay step 70ms. | Rows fade in together. |
| alternating list（左右交互イン） | enter view, load | `li:nth-child(odd) { --dx: -40px } li:nth-child(even) { --dx: 40px }`, `from { translate: var(--dx) 0; opacity: 0 }`, 450ms `var(--out)`, delay 50ms per row. | Fade only, no side travel. |
| row expand（行の展開） | press, state change | Use `<details>` or a grid row: `grid-template-rows: 0fr` to `1fr` with `transition: grid-template-rows 350ms cubic-bezier(.34,1.3,.64,1)`; or `interpolate-size: allow-keywords` with `height: auto` inside `@supports (interpolate-size: allow-keywords)` (fallback: the grid row form or a measured `scrollHeight`). Content `overflow: hidden`. | Open instantly, content visible. |
| grid wave（グリッドウェーブ） | enter view | Per cell `--d: calc((var(--row) + var(--col)) * 50ms)`; `animation: rise 500ms var(--out) both; animation-delay: var(--d)` with `from { translate: 0 16px; scale: .9; opacity: 0 }`. | All cells fade in together. |
| center-out grid（中央から展開） | enter view | Delay from distance to centre: `calc(var(--dist) * 60ms)` with `--dist` set in JS (`Math.hypot`); `scale: 0` to `1` on `cubic-bezier(.34,1.56,.64,1)`; Motion `stagger(.06, {from:"center"})`. | Fade in together, no scale. |
| row sweep grid（行スイープ） | enter view | Delay `calc(var(--row) * 90ms + var(--col) * 8ms)`, `translate: 0 10px; opacity: 0` to rest, 350ms `ease-in-out`. | All cells fade in together. |
| shuffle to grid（シャッフル整列） | load, enter view | Per tile start `--x`, `--y`, `--r` from a seeded list; `from { translate: var(--x) var(--y); rotate: var(--r) }` to none over 700ms `cubic-bezier(.68,-.3,.32,1.3)`. Reorder later with FLIP or Motion `layout`. | Tiles already in place, short fade. |
| list slide stack（リスト積み重ね） | state change | Prepend then FLIP: measure old rects, apply inverse `translate`, play to zero with 350ms `var(--out)`; new row `.row { @starting-style { opacity: 0; translate: 0 -100% } }`. Motion: `layout` plus `AnimatePresence`. | New row appears with a fade; others jump. |
| list trim collapse（リスト削除詰め） | state change | Fade and `scale: 1 0` row (origin top) in 200ms, then collapse its slot with `grid-template-rows: 1fr` to `0fr` or FLIP the followers 300ms `var(--inout)`; remove node on `transitionend`. | Row removed with a short fade; list closes instantly. |
| grid spiral（グリッド螺旋展開） | enter view | Compute spiral order index in JS per cell, set `--i`; `animation-delay: calc(var(--i) * 40ms)`, `scale: .8; opacity: 0` to rest, 400ms `var(--out)`. | All tiles appear together. |
| grid diagonal wave（グリッド斜めウェーブ） | enter view | Delay `calc((var(--row) + var(--col)) * 35ms)` with `scale: .85; opacity: 0` to rest, 250ms `cubic-bezier(.22,1,.36,1)`; crisper and shorter than grid wave. | Fade together, no stagger. |

## Attention and emphasis

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| nudge（ナッジ） | hover, state change | `element.animate({translate:['0','6px','0']},{duration:250,easing:'cubic-bezier(.34,1.56,.64,1)'})` on the single node; ends on rest. | A brief colour or outline change instead. |
| attention bounce（アテンションバウンス、注目バウンス） | time, state change | Keyframes `translate: 0 0, 0 -14px 40%, 0 0 70%` with `scale: 1 1, 1 1 40%, 1.08 .92 70%, 1 1` over 600ms; run once or on a 5s timer, never endless. | Remove; use a static badge or outline. |
| badge pop（バッジポップ） | state change | Badge `.badge { @starting-style { scale: 0; rotate: -20deg } }` with `transition: scale 350ms cubic-bezier(.34,1.56,.64,1), rotate 350ms`, origin at the corner; the icon is not animated. | Badge appears instantly. |
| focus halo（フォーカスハロー） | focus, state change | `::before { box-shadow: 0 0 0 0 currentColor; animation: halo 900ms var(--out) }` with `to { box-shadow: 0 0 0 16px transparent }`, or a blurred ring scaled with opacity. Box-shadow repaints; prefer a scaled pseudo-element. | Static 2px outline, no animation. |
| highlight sweep（ハイライトスイープ） | enter view, hover | `background: linear-gradient(100deg, transparent 40%, rgb(255 230 120 / .6) 50%, transparent 60%) 200% 0 / 200% 100% no-repeat`; animate `background-position` to `-100% 0` over 900ms `var(--inout)`; or a clipped pseudo-element with `translate`. | Static tint, no sweep. |
| border chase（ボーダーチェイス） | loop, focus | `@property --a { syntax: '<angle>'; inherits: false; initial-value: 0deg }` with `border-image: conic-gradient(from var(--a), transparent 85%, #fff) 1` animated `--a` to 360deg in 2s linear, 2 laps; or an SVG rect with `stroke-dasharray` and `stroke-dashoffset`. | Static bright border. |
| press feedback（プレスフィードバック） | press | `button:active { scale: .96; box-shadow: 0 1px 2px rgb(0 0 0 / .2) } button { transition: scale 120ms, box-shadow 120ms }`; release returns with `transition: scale 200ms var(--out)`. | Keep the colour change only, no scale. |
| jelly emphasis（ゼリー強調） | hover, press | Keyframes `scale: 1 1, 1.2 .8 25%, .9 1.1 50%, 1.05 .95 75%, 1 1` over 700ms `ease-out`, or a `linear()` spring; centre origin. | No wobble; brief colour shift. |
| color pulse（カラーパルス） | loop, state change | `animation: tint 2s ease-in-out 3` with `50% { background-color: var(--accent) }`; a finite count, ending on the base colour. | Single static accent state, no cycle. |
| icon nod（アイコンうなずき） | hover, press | Parent `perspective: 400px`; icon `transform-origin: top; animation: nod 500ms` with keyframes `rotate: x 0deg, x 28deg 35%, x -6deg 70%, x 0deg`. | No nod; static icon. |
| spotlight focus（スポットライトフォーカス） | state change, press | Overlay with `background: radial-gradient(circle at var(--x) var(--y), transparent var(--r), rgb(0 0 0 / .6) calc(var(--r) + 40px))`; register `--x`, `--y`, `--r` via `@property` and transition 500ms `var(--inout)`; or `box-shadow: 0 0 0 100vmax` on a target-sized `outline`. Tutorial overlays need `aria-hidden` and focus handling. | Instant dim with the target lit, no glide. |
| error shake（エラーシェイク） | state change | `animation: shake 400ms ease-out` with keyframes `translate: 0, -8px 15%, 6px 35%, -4px 55%, 2px 75%, 0`; add `outline: 2px solid var(--error)` and `aria-invalid="true"`. | No shake; red outline plus visible error text. |
