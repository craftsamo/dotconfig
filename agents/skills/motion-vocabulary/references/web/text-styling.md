# Typographic treatments: web builds

How each entry of [../text-styling.md](../text-styling.md) is built on a real web page: the trigger that starts it (load, enter view, scroll progress, hover, focus, press, drag, state or route change), the smallest tool that builds it (CSS, then the Web Animations API, then a library) and what replaces it under `prefers-reduced-motion: reduce`. Read the entry's Looks like and The tell first. Typical values here come from common web practice; a project's own motion tokens win.

Treatments that live inside the letters of real page text: glyph physics, type on a path, colour and light, distortion, depth, variable-font axes, pointer play, counters and decorative loops. Shared habits: split text into per-character spans only when needed, keep the full string in a visually hidden copy (or `aria-label` only on a heading or an element with a role, since `aria-label` is ignored on a generic `span`, `div` or `p`) and set `aria-hidden="true"` on the spans; wait for `document.fonts.ready` before measuring; loops run a finite count or pause off screen (IntersectionObserver). Under `prefers-reduced-motion: reduce` the text is simply shown in its final, readable state.

## Glyph physics

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| character magnetize（文字マグネット整列） | enter view | Per-char spans; start `translate` from seeded random offsets, WAAPI or CSS transition to `translate: 0` over 700-900 ms, `cubic-bezier(0.215, 0.61, 0.355, 1)` (ease-out cubic), 25 ms stagger via `--i`. Transform and opacity only. | Show the text in place; at most a 150 ms opacity fade. |
| letter collision bounce（文字衝突バウンス） | enter view or hover | Keyframes per char: short pull-back `translateX(-6px)`, hit pushing the neighbours `+10px`, then decaying settle; 600-900 ms with a 40 ms stagger delay growing outward from the impact letter. Or Motion springs per span. | Static text; no impact, no travel. |
| inertia letters（飛び込んで揺れて止まる文字） | enter view | Per char `translateX` in plus `rotate` keyframes with decaying amplitude (12deg, -7deg, 3deg, 0), 900 ms, `linear()` spring easing for the overshoot, stagger 30-50 ms. Motion `type: "spring"` also fits. | Instant final state or 150 ms fade. |
| drop and bounce in（落下バウンド） | enter view | Per char `translateY(-120%)` to 0 with `linear()` bounce easing (or keyframes 0, -18%, 0, -6%, 0), 800 ms, 50 ms stagger; optional blurred shadow element scaled with the same keyframes. | Text appears in place, opacity fade only. |
| raining characters（文字の雨） | enter view | Per-char `translateY(-100vh)` to 0, `cubic-bezier(0.215, 0.61, 0.355, 1)` 600 ms, delay from a shuffled index array times 30 ms; ghosts are 2 clones at opacity 0.3 and 0.15 with `animationend` removal. | Final text instantly; no ghosts. |
| falling text physics（落下して積もる） | enter view | Matter.js (or Rapier) bodies from each word's measured box, render by writing `transform` per frame in rAF, `engine.gravity.y = 1`, restitution 0.3; start on enter view and stop the engine once bodies sleep. Fallback: seeded final offsets and `linear()` bounce keyframes. | Words stay in reading order, static; no simulation. |
| pendulum swing（振り子スイング） | enter view or state change | `transform-origin: 50% 0`, keyframes `rotate(25deg)`, `-17deg`, `10deg`, `-4deg`, 0 over 1.6 s with `ease-in-out`; add 60 ms per-char delay for a travelling wave. | Hangs straight, no swing. |
| squash landing（着地スクワッシュ） | enter view | Per char with `transform-origin: 50% 100%`: `scale(0.85, 1.25)` falling, `scale(1.2, 0.8)` at contact (around 45% of 700 ms), then `linear()` spring to `scale(1)`; `translateY` for the drop. | Final shape instantly. |
| spring chain follow（バネ連鎖追従） | pointer or state change | Motion `useSpring` per char chained: each follows the previous one's value (stiffness 120-180, damping 12-18), or rAF with `x += (target - x) * 0.18` per char reading the predecessor; write `translate` only. | Letters move with the lead rigidly or not at all; no lash. |
| zero-gravity drift（無重力ドリフト） | enter view then loop | Per char CSS custom properties `--dx --dy --r` seeded in JS; keyframes to those values and back, 6-10 s `ease-in-out`, `animation-iteration-count: 2`, `animation-fill-mode: both`; transform only. | No drift; text static at home. |
| domino topple（ドミノ倒し） | enter view or scroll progress | Per char `transform-origin: 0 100%`, `rotate(0)` to `rotate(80deg)` with `ease-in`, 120 ms each, each delay chained on the previous; with wide `letter-spacing`. Scrub variant: `animation-timeline: view()` plus per-char `animation-range` offsets. | Text stays upright; optional 150 ms colour change instead. |

## Path and shape

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| circular text spin（円形テキスト回転） | loop | SVG `<text><textPath href="#circle">` on a circle path; animate the wrapping `<g>` or the SVG element with CSS `rotate` 360deg, 20 s `linear infinite`, `transform-origin: center`. Pause when off screen and add a pause button (or cap `animation-iteration-count` at 1). | Static emblem, no rotation. |
| curved loop marquee（曲線ループマーキー） | loop | `textPath` with `startOffset` animated by SMIL `<animate>` or WAAPI from `0%` to the exact width of one text unit plus separator, `linear`, infinite (with a pause button, or a capped repeat count); repeat the string so the period joins. Text layout repaints, so keep the string short. | Static text on the curve. |
| text along path（パスに沿って走る） | enter view | `textPath` `startOffset` animated (WAAPI on the SVG attribute or GSAP `attr`) from negative to the hold value with ease-out, wait, then ease-in out; hold on a gentle stretch. Or CSS `offset-path` per char span with `offset-distance`. | Text shown at the hold position, static. |
| path with tracking inertia（パス+慣性トラッキング） | enter view | Per-char `offset-path: path(...)` with `offset-distance` animated, delays per index, easing `cubic-bezier(0.34, 1.56, 0.64, 1)` for the spring-back; or GSAP with `back.out`. | Letters placed at final spacing instantly. |
| outline stroke draw（アウトライン線描） | enter view | Text converted to SVG paths; `pathLength="1"`, `stroke-dasharray: 1`, `stroke-dashoffset` 1 to 0 over 1 s, 80 ms stagger per glyph, then `fill-opacity` 0 to 1 for 400 ms. | Filled text shown at once. |
| handwriting write-on（手書き線描） | enter view | SVG centreline paths inside a `<mask>` with thick stroke, `stroke-dashoffset` animated per stroke in sequence, `ease-in-out` each, duration scaled to stroke length; the visible fill sits under the mask. | Word shown fully, no write-on. |
| spiral text（渦巻きテキスト） | enter view | `textPath` on a spiral SVG path with `startOffset` animated linearly; font size tied to the radius via several `tspan`s with stepped `font-size`. Plain `<text>` size cannot follow a curve continuously. | Show the final spiral static. |
| morphing path ride（変形するパスに乗る） | state change or loop | Animate the path `d` (CSS `d: path(...)` inside `@supports (d: path("M0 0"))`, which is not in all engines; fallback: SMIL `<animate attributeName="d">`, a JS path morph such as GSAP MorphSVG, or an instant swap) with matching point counts; `textPath` relayouts every frame, so keep it brief. | Jump to the end shape or hold one shape. |
| shape contour text（図形の輪郭を巡る） | loop | `textPath` on the shape outline; repeat the string to fill `getTotalLength()`, animate `startOffset` linearly across one period, 15-30 s, with a pause button or a capped repeat count. | Static text on the contour. |

## Colour and light

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| animated gradient text（グラデーション流動） | loop | `background: linear-gradient(90deg, a, b, c, a) 0 0 / 200% 100%; background-clip: text; color: transparent;` animate `background-position` to `-200% 0`, 6 s `linear infinite` with a pause button (or cap `animation-iteration-count`). Repaint only. Include the `-webkit-` prefixes. | Static gradient. |
| aurora text（オーロラテキスト） | loop | Text with `background-clip: text` over layered `radial-gradient`s; animate `@property --a` angle or move `background-position` and `background-size` on 12-20 s `ease-in-out alternate`, with a pause button or a capped iteration count. Or blurred blobs masked by text via `mix-blend-mode`. | Static colour field. |
| conic gradient spin（コニック回転） | loop | `@property --angle { syntax: "<angle>"; inherits: false; initial-value: 0deg }`, `background: conic-gradient(from var(--angle), ...)` with `background-clip: text`; animate `--angle` to 360deg, 8 s linear. Fallback: no animation without `@property`. | Fixed angle. |
| colour band sweep（カラーバンド・スイープ） | enter view or hover | Gradient with hard stops: grey, bright edge, final colour, `background-size: 300% 100%`, `background-clip: text`; transition `background-position` 700 ms `cubic-bezier(0.45, 0, 0.55, 1)`. | Final colour set instantly. |
| per-character hue cycle（色相サイクル）, colourful text cycle（カラフル文字サイクル） | loop | Per-char `animation: hue 3s linear infinite; animation-delay: calc(var(--i) * -80ms)` with keyframes `color: hsl(0 80% 55%)` to `hsl(360 80% 55%)` (or `filter: hue-rotate`). Cycle variant adds `translateY(-4px)` and `blur(1px)` pulses. Limit to a few cycles (cap `animation-iteration-count` or add a pause button). | One static colour per char. |
| neon flicker-on（ネオン点灯） | load or enter view | Keyframes on `opacity` per char with irregular steps (0, 1, 0.2, 1, 0.5, 1) over 1.2 s, `steps()` or `step-end`, seeded delays; glow via stacked `text-shadow: 0 0 4px #fff, 0 0 16px #f0f, 0 0 40px #f0f`. Final state lit. Avoid more than 3 flashes per second. | Lit state, no flicker (also avoids flash risks). |
| line shadow text（ラインシャドウ） | loop | Pseudo-element copy (`content: attr(data-text)`) offset 3px, filled with `repeating-linear-gradient(45deg, ...)` via `background-clip: text`, `z-index: -1`; animate `background-position` 1 s linear, capped at 5 iterations or behind a pause button. | Static stripes. |
| long shadow grow（ロングシャドウ伸長） | enter view or hover | Many stacked `text-shadow` steps (1px increments to 60px, generated by JS or Sass) with alpha falling off; animate a `--len` custom property via `@property` and `calc()`, or animate a skewed pseudo-element with `scaleX`, `cubic-bezier(0.215, 0.61, 0.355, 1)` 500 ms. | Shadow at full length, static. |
| blend overlap（文字重なり合成） | enter view or hover | Per-char spans with distinct colours, `mix-blend-mode: multiply` or `screen`, `isolation: isolate` on parent; transition `letter-spacing` from 0.1em to -0.3em over 900 ms `ease-in-out`. Layout shifts, so reserve width or use `translate` per char instead. | Final spacing at once. |

## Distortion and glitch

Flashing glitches stay under 3 flashes per second and never fill the viewport.

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| RGB split glitch（RGB分離グリッチ） | hover or time | Three stacked copies via `::before`/`::after` plus the base, colours `#f00 #0f0 #00f`, `mix-blend-mode: screen`, `clip-path: inset()` bands with seeded `translateX`; keyframes 250 ms with `steps(4)`, long rest (3-6 s) between bursts; at most 3 flashes per second. | No glitch; static text. |
| slice displacement（スライス変位グリッチ） | hover or time | Duplicate layers with `clip-path: inset(top 0 bottom 0)` strips and different `translateX`, redrawn per burst by JS setting custom properties; 200 ms `steps()` keyframes then home; at most 3 flashes per second. | Static text. |
| fuzzy text（ファジーテキスト） | hover or loop | Render text to canvas and redraw each row shifted by a random 0-3 px in rAF; or SVG filter `feTurbulence` plus `feDisplacementMap` with `scale` 4-10, seed changed per frame. Filters are paint-heavy; apply to one heading. | Clean text. |
| turbulence wobble（タービュランス揺らぎ） | loop | SVG `filter` with `feTurbulence baseFrequency="0.01 0.02"` and `feDisplacementMap scale="6"`, `seed` stepped every 150-250 ms by JS or SMIL `<animate>` with `calcMode="discrete"`; apply `filter: url(#wobble)` to the text only. | No filter. |
| ASCII text（ASCII テキスト） | load or loop | Draw the word to an offscreen canvas, sample brightness per cell, map to a ramp ` .:-=+*#%@`, write into a `<pre>` with `font-family: monospace`; shift the sampled rows with a sine in rAF at about 12 fps. Keep the real text in a visually hidden copy and mark the `<pre>` `aria-hidden="true"`; add a pause button for the ripple. | Static ASCII frame. |
| VHS tracking noise（VHS 走査線ノイズ） | time | Overlay with `repeating-linear-gradient` scanlines (static), a tracking band `div` animated `translateY(-100%)` to `100%` over 4 s, `mix-blend-mode: overlay`, inner slices shifted via `clip-path`; rare 100 ms jump; small `text-shadow` chroma offset. | Static scanlines only. |
| pixel mosaic resolve（モザイク解像） | enter view | Draw text to a small canvas, scale up with `image-rendering: pixelated`; step the canvas scale through 8, 16, 32, full over 5 steps on JS timers (or CSS `steps(5)` on a `@property` size). Swap to live text when sharp. | Sharp text immediately. |
| melt drip（溶けて垂れる） | hover or enter view | Per-char `transform-origin: 50% 0`, `scaleY(1)` to a seeded `scaleY(1.4-2)` with `ease-in`, 1.2 s; goo via SVG filter `feGaussianBlur` plus `feColorMatrix` threshold; drops are small circles falling with `translateY`. Filter is paint-heavy. | Static text. |

## 3D and depth

Set `perspective` on the parent (about 600-1000px), `transform-style: preserve-3d` where children share the 3D space, and only animate `transform` and `opacity`.

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| perspective type tunnel（文字遠近トンネル） | scroll progress or loop | One layer per ring at stepped `translateZ(-200px * n)`, opacity falling with depth; move the group with `translateZ` bound to scroll via `animation-timeline: scroll()` or a slow 8 s `ease-in-out` loop with a pause button or a capped iteration count. | Static stack. |
| 3D flip up（3D フリップアップ） | enter view | Per char `transform-origin: 50% 100%`, `rotateX(-90deg)` to 0, 700 ms `cubic-bezier(0.16, 1, 0.3, 1)`, 40 ms stagger, opacity 0 to 1. | Fade only or instant. |
| swing door（スイングドア） | enter view | Per char `transform-origin: 100% 50%`, `rotateY(90deg) translateZ(-80px)` to 0, 700 ms `cubic-bezier(0.16, 1, 0.3, 1)`, stagger from the end (`--i` reversed). | Instant or fade. |
| fly in from depth（奥から飛来） | enter view | Per char `translateZ(-1200px)` plus `opacity: 0` to rest, 800 ms `cubic-bezier(0.34, 1.56, 0.64, 1)`, 30 ms stagger. | Fade in place. |
| tumbling 3D entrance（回転落下イン） | enter view | Per char seeded `rotateX(-360deg…) translateZ(-300px)` start to rest, 900 ms `ease-in-out`, small `translateY` bounce at the end via a `linear()` easing; `backface-visibility: visible`. | Fade only. |
| 3D roll flip（3D ロールフリップ） | hover or state change | Per char box: two faces absolutely stacked, front `rotateX(0)` and back `rotateX(90deg)` with `translateZ` half the line height; parent `preserve-3d` rotates `rotateX(-90deg)`, 400 ms `ease-in-out`, 30 ms stagger. | Swap faces instantly. |
| 3D cylinder text（3D 円筒テキスト） | loop or scroll progress | Each letter at `rotateY(i * 360/n deg) translateZ(radius)` inside a `preserve-3d` wrapper; wrapper `rotateY` 0 to 360deg, 12 s `linear`, capped at 1 iteration or behind a pause button; repeat the phrase around the ring. | Static, facing front. |
| layered depth text（レイヤー奥行き文字） | pointer | 10-20 copies at `translateZ(n * 2px)`, parent `rotateX/rotateY` set from `pointermove` (rAF throttled, mapped to ±15deg) with a CSS `transition: transform 150ms ease-out` for the lag; no tilt on touch. | No tilt; flat text. |
| paper fold（折りたたみ） | enter view or scroll progress | Stacked panels, each `transform-origin: top`, alternating `rotateX(±70deg)` to 0, 600 ms `cubic-bezier(0.215, 0.61, 0.355, 1)`, 120 ms stagger; shade overlay opacity from 0.5 to 0. | Flat sheet instantly. |
| MoText falloff sweep（エフェクター掃引(MoText)） | scroll progress or hover | Per-char `rotateY` and `translateZ` computed in rAF from a falloff of distance to a moving x (scroll progress or pointer), eased with `x += (t - x) * 0.15` for the lag; parent perspective 800px. | Letters stay still. |

## Variable fonts

Use a real variable font with the needed axes (`wght`, `wdth`, `slnt`, `opsz`), animated through `font-variation-settings: "wght" 700` or `font-weight` transitions (`font-weight` range declared in `@font-face`). These animate on the main thread and repaint. A `wght` change usually alters glyph advance, and `wdth` always does, so the line reflows: give each char a fixed-width `inline-block` (`min-width` in `ch` or measured) or reserve space with the widest state, or the surrounding layout will jump.

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| variable font pulse（可変フォントパルス） | hover or state change | Keyframes on `font-variation-settings: "wght" 400` to `"wght" 800` and back, 600 ms with `cubic-bezier(0.34, 1.56, 0.64, 1)` out and a short settle, `animation-iteration-count: 3`; fixed-width box to prevent reflow. | Weight set to the end value, no beat. |
| variable weight wave（ウェイトウェーブ） | loop | Per-char `animation: wght 2s ease-in-out infinite alternate; animation-delay: calc(var(--i) * 80ms)` on `font-variation-settings`; each char in a fixed-width `inline-block`. Finite repeats (cap `animation-iteration-count`) or a pause button, and pause off screen. | Uniform weight. |
| variable width stretch（可変幅ストレッチ） | hover or loop | Per-char `font-variation-settings: "wdth" 75` to `125`, 1.2 s `ease-in-out`, delay `--i * 60ms`. Width changes reflow the line (container needs room, or `overflow: visible` on a centred, fixed-width wrapper). True `wdth` keeps stroke thickness, unlike `scaleX`. | Fixed width. |
| weight breathe（ウェイト呼吸） | loop | `animation: breathe 5s ease-in-out infinite alternate` over `font-weight: 100` to `900` on one element; the fixed-width container prevents reflow (or use `font-synthesis: none` and a wide `min-width`). Stop after a few cycles. | Fixed medium weight. |
| thin to bold entrance（細→太で出現） | enter view | Per-char `opacity: 0` to 1 in 200 ms, `font-weight: 100` to 900 over 900 ms `cubic-bezier(0.215, 0.61, 0.355, 1)`, 40 ms stagger; reserve final-weight width with an invisible bold copy or `inline-grid` stacking. | Final weight, fade only. |
| slant axis swing（傾き(slnt)スイング） | hover or loop | Per-char `font-variation-settings: "slnt" 0` to `"slnt" -12`, 1.5 s `ease-in-out alternate`, `--i * 70ms` delay. Fallback without a `slnt` axis: `skewX(-12deg)` with `transform-origin: 50% 100%` on `inline-block` spans. | No tilt. |
| width/slant velocity（速度で幅・傾き変化） | scroll progress | Compute scroll velocity in a scroll listener (rAF), smooth it with a spring (`v += (target - v) * 0.12`), write `--v` to the element and use `font-variation-settings: "wdth" calc(100 + var(--v) * 20), "slnt" calc(var(--v) * -8)`. Reflow cost: keep it to one headline. | No velocity response. |
| text pressure（テキストプレッシャー） | pointer | On `pointermove` (rAF throttled, mouse only) compute each char's distance to the pointer and write `font-variation-settings: "wght" w, "wdth" d` from a falloff; spring toward target. Fixed-width box so neighbours do not push the line. | No pointer effect; static weight. |
| variable proximity（可変プロキシミティ） | pointer | Same listener but weight only, Gaussian `w = min + (max - min) * exp(-d² / (2 * 80²))`, `opsz` alongside; per-char fixed-width `inline-block`. Skip on touch (`pointerType === "touch"`). | Uniform weight. |

## Pointer

All pointer effects read real `pointermove` events and write from a `requestAnimationFrame` loop that is throttled to one update per frame; they are skipped when `event.pointerType === "touch"` or `matchMedia("(hover: none)").matches`, and under reduced motion. Keep a keyboard `:focus-visible` equivalent where the effect carries meaning.

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| magnetic letters（マグネット文字） | hover | Per-char `getBoundingClientRect()` cached on resize; in rAF compute distance, offset `translate` by `(dx, dy) * clamp(1 - d/120, 0, 1) * 0.3`, smooth with `x += (t - x) * 0.15`; return to 0 on `pointerleave`. | No movement. |
| pointer proximity repel（近接反発） | hover | Same loop with offset opposite the cursor direction scaled by proximity (radius 100px), lerp 0.1 for the lag in both directions; `translate` only. | Static text. |
| proximity scramble（近接スクランブル） | hover | Per-char text node swapped between the real char and a random from `.:·` when distance is under a radius, then restored after a delay proportional to the distance; the text is not re-flowed (use `font-variant-numeric` or monospace). Keep the real text in a visually hidden copy and mark the scrambled spans `aria-hidden="true"`. | No scramble. |
| clone roll hover（複製ロールホバー） | hover or focus | Two stacked copies in an `overflow: hidden` slot (height one line); on `:hover` and `:focus-visible` transition `translateY(-100%)` on both, 400 ms `cubic-bezier(0.16, 1, 0.3, 1)`, per-char delay `--i * 15ms`. Pure CSS; works on touch tap. | Instant colour change, no slide. |
| hover word lift（ホバー単語リフト） | hover | Wrap words in spans (use `Intl.Segmenter` for Japanese); `.word:hover { translate: 0 -4px; color: var(--accent); transition: translate 250ms cubic-bezier(0.34, 1.56, 0.64, 1), color 150ms }`. | Colour change only. |
| text cursor trail（カーソル軌跡テキスト） | hover | On `pointermove` (rAF), accumulate distance and spawn an absolutely positioned `pointer-events: none` span every 40px, rotated to the heading; WAAPI `translate`, `scale 1 to 0` and `opacity 1 to 0` over 900 ms; pool of about 20 nodes. | No trail. |
| spotlight outline hover（スポットライト輪郭） | hover | Text with `-webkit-text-stroke` thin hairline and a second copy with a gradient stroke and `mask-image: radial-gradient(circle 120px at var(--x) var(--y), #000, transparent)`; update `--x --y` in rAF on `pointermove`. Draw-on via `stroke-dashoffset` for SVG text. | Outline shown steady, no spotlight. |
| pointer reveal card（ポインタでめくる） | hover | Two stacked layers; top uses `clip-path: inset(0 0 0 var(--x))` updated from `pointermove` (rAF); on `pointerleave` transition `--x` home (register with `@property`) 500 ms `cubic-bezier(0.215, 0.61, 0.355, 1)`. Provide a tap or focus fallback. | Hover swaps the layers instantly. |
| cursor bulge lens（カーソル膨張レンズ） | hover | Magnified duplicate of the text clipped by `clip-path: circle(80px at var(--x) var(--y))` with `transform: scale(1.4)` and matching origin; or SVG `feDisplacementMap` with a radial map. Updated in rAF; at rest hold still. | No lens. |

## Numbers and data

Use `font-variant-numeric: tabular-nums` (or a monospace figure font) so columns do not shift, format with `Intl.NumberFormat(locale, options)` (currency, `maximumFractionDigits`, `compactDisplay`) at every step, and expose the final value to assistive tech (a visually hidden copy with the animated digits `aria-hidden="true"`, or an `aria-live="off"` counter with a polite final announcement).

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| monospace data shuffle（等幅データシャッフル） | enter view or state change | Cells with `tabular-nums` and `font-family: ui-monospace`; in rAF set random digits per cell, lock per index at `index * 60 ms` using an ease-out schedule; final text from `Intl.NumberFormat`. | Final values at once. |
| price ticker flash（価格ティッカー・フラッシュ） | state change | On value change set `data-dir="up|down"`; WAAPI background colour flash fading over 600 ms; changed digits slide `translateY(±100%)` to 0 in an `overflow: hidden` slot; arrow glyph for direction. Max 3 flashes a second, no saturated full-width flash. | Colour tint only, no slide or flash. |
| score update（スコア更新） | state change | Two digit layers, old `rotateX(0)` to `-90deg` and new `90deg` to 0, 300 ms `cubic-bezier(0.215, 0.61, 0.355, 1)`, `perspective` on the cell; cell background opacity pulses 0.4 to 0 over 500 ms. Only the changed digit animates; add `aria-live="polite"`. | Swap instantly; brief background tint. |
| number scramble settle（数字シャッフル確定） | enter view | In rAF at about 20 fps replace unfrozen digits with random 0-9, freeze index `i` at `400 + i * 120` ms; separators and units come from `Intl.NumberFormat` and never change; `tabular-nums`. | Final number instantly. |
| percent with ring（パーセント+リング） | enter view or state change | SVG `circle` with `pathLength="100"`, `stroke-dasharray: 100`, `stroke-dashoffset` driven by the same value as the figure; one WAAPI or rAF tween (1.2 s, `cubic-bezier(0.215, 0.61, 0.355, 1)`) writes both; or `<progress>`/`role="progressbar"` with `aria-valuenow`. | Final ring and number at once. |
| countdown zoom（カウントダウン） | time | One element; per second swap the text and play WAAPI keyframes `scale(0.6)` opacity 0 to `scale(1)` opacity 1 (150 ms `back.out`-like `cubic-bezier(0.34, 1.56, 0.64, 1)`), then `scale(1.6)` opacity 0 over 800 ms; optional SVG ring sweep per beat. Announce via `aria-live`. | Plain number swap, no scale. |
| seven-segment display（7セグメント表示） | state change | Seven `<span>` or SVG `rect`s per digit; a lookup table of 0-9 as bitmasks toggles `opacity` or a `data-on` attribute, 50 ms `transition: opacity`; unlit at 0.1 opacity; colon blinks via 1 s `steps(2)` animation. | Segments switch with no transition; colon steady. |

## Loops and decoration

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| wave loop（ウェーブループ） | loop | Per-char `animation: bob 1.2s ease-in-out infinite; animation-delay: calc(var(--i) * 80ms)` with keyframes `translateY(0)` to `-0.3em`; run a limited count (cap `animation-iteration-count`) or add a pause button, and pause off screen. | Static text. |
| wiggly scale breathe（拡縮の呼吸） | loop | Per-char `scale 1 to 1.12`, `transform-origin: 50% 100%`, `animation-duration` seeded 2-4 s, seeded negative `animation-delay`, `ease-in-out alternate` with a capped `animation-iteration-count` or a pause button; use `scale` property. | Static size. |
| sparkles text（スパークル文字） | loop | Absolutely positioned SVG star spans at seeded spots; `scale 0 to 1 to 0` with `rotate 0 to 180deg` over 900 ms, staggered; re-place at a new seeded spot on `animationiteration`; limit to about 5. | Static stars or none. |
| sequential hop（順番ジャンプ） | loop | Per-char keyframes: crouch `scaleY(0.85)`, `translateY(-0.5em)`, land with squash, `animation-delay: --i * 90ms`, total 2.4 s with the active window under half so there is a pause; finite iterations. | Static text. |
| staggered Y spin（文字スピン連鎖） | loop | Per-char `rotateY(0)` to `360deg`, 800 ms `cubic-bezier(0.45, 0, 0.55, 1)`, delay `--i * 60ms`, `perspective` on the parent, repeating every 4 s with idle time. | Static text. |
| loading dots（読み込み中…、ローディングドット） | loop or state change | Three `<span>` dots with `animation: dot 1.2s ease-in-out infinite`, delays 0, 150, 300 ms, keyframes `translateY(0)` opacity 0.3 to `translateY(-3px)` opacity 1; `role="status"` with an `aria-label` on the wrapper; stop when loading ends, or cap the iterations if loading can run past five seconds. | Dots at steady opacity, or a text change with no motion. |
| hanging sign sway（吊り看板の揺れ） | loop | Wrapper with `transform-origin: 50% -2rem` (pivot outside the box), keyframes `rotate(3deg)` to `-3deg`, 4 s `ease-in-out alternate`, capped at 3 iterations or behind a pause button; start with a damped `linear()` swing, then settle into the loop. | Static sign. |
