# Text motion: web builds

How each entry of [../text.md](../text.md) is built on a real web page: the trigger that starts it (load, enter view, scroll progress, hover, focus, press, drag, state or route change), the smallest tool that builds it (CSS, then the Web Animations API, then a library) and what replaces it under `prefers-reduced-motion: reduce`. Read the entry's Looks like and The tell first. Typical values here come from common web practice; a project's own motion tokens win.

How words and letters appear, leave, swap, type out and take emphasis on a real page. Splitting rules for every row below: keep the text accessible by keeping the full text in a visually hidden copy (or `aria-label` only on a heading or an element with a role, since `aria-label` is ignored on a generic `span`, `div` or `p`) and putting `aria-hidden="true"` on the split spans; split by grapheme with `Intl.Segmenter(undefined, { granularity: 'grapheme' })` so emoji and combining marks never break; split Japanese by phrase using a precomputed segmenter such as BudouX (run at build time, ship the phrase list). Animate `transform`, `opacity`, `filter`; stagger with a CSS variable like `style="--i:3"` and `animation-delay: calc(var(--i) * 40ms)`.

## Reveal

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| line-by-line reveal（行ごとのリビール） | enter view | Split lines by measured `offsetTop` into spans, same `translateY(0.5em)` and `opacity` rise, 600 ms `cubic-bezier(.2,.7,.2,1)`, delay `line*150ms`; re-split on resize. | Whole paragraph fades in 150 ms. |
| word ghost reveal（移動量が減っていく語の出現） | load, enter view | Per-word `--d` set in JS as `base * 0.6**i` px, `translateX(var(--d))` to `0`, `opacity 0` to `1`, 700 ms `cubic-bezier(.16,1,.3,1)`, delay 50 ms apart; `overflow: clip` on the parent. | Fade only, no travel. |
| kinetic lines on verbs（動詞で行が立ち上がる） | time, state change | Cue times array from the audio/video; on `timeupdate` or `requestVideoFrameCallback` add `.in` to each line (`translateY(40%)` to `0`, 350 ms `cubic-bezier(.2,.9,.2,1)`). Lines stay in DOM, hidden with `opacity:0` only until cued. | All lines visible from start; the current line gets a colour change. |
| character fade up（文字フェードアップ） | load, enter view | Grapheme spans (`Intl.Segmenter`), `translateY(0.4em)` and `opacity:0` to rest, 500 ms `cubic-bezier(.2,.7,.2,1)`, delay `i*30ms`, cap total near 1 s by scaling the per-letter delay. | Block fades in 150 ms. |
| word fade up（単語フェードアップ） | load, enter view | Split by word (or by BudouX phrase for Japanese, precomputed at build, particles stay with the preceding word); `translateY(0.3em)` and opacity, 600 ms ease-out, delay `i*80ms`; keep `white-space` so wrapping is unchanged. | Single fade, no stagger. |
| slide down by character（文字スライドダウン） | load, enter view | Grapheme spans, `translateY(-0.5em)` to `0` with opacity, 500 ms `cubic-bezier(.2,.7,.2,1)`, delay `i * (900/n)ms` so the total build stays constant. | Fade only. |
| alternating line reveal（行ごと交互方向リビール） | load, enter view | Each line `overflow: hidden`; inner `translateY(±100%)` to `0`, 600 ms `cubic-bezier(.65,0,.35,1)`, stagger 100 ms; a second stage adds a per-letter opacity step with seeded random delay up to 200 ms. | Lines shown in place with one fade. |
| stretch rise（伸縮せり上がり） | load, enter view | Inline-block graphemes, `transform-origin: 50% 100%`, keyframes `translateY(100%) scale(.6, 1.6)` to `scale(1.05,.95)` to `scale(1)`, 600 ms `cubic-bezier(.34,1.56,.64,1)`, delay 30 ms. | Fade in place, no scaling. |
| vertical unfold（縦方向展開） | load, enter view | `transform-origin: 50% 0`, `scaleY(.05)` to `1` with `cubic-bezier(.34,1.56,.64,1)`, 450 ms, delay 30 ms per letter; inline-block spans. | Letters appear with a 150 ms fade. |
| converge from spread（中央へ収束） | load, enter view | Per-grapheme `--x` = `(i - center) * 3` em-units, `translateX(var(--x))` to `0`, 800 ms `cubic-bezier(.45,0,.2,1)`, delay increasing with distance from centre; `overflow: clip` on the parent. | Fade only, no travel. |
| center-out reveal（中央から外へ展開） | load, enter view | Opacity fade with `animation-delay: calc(abs(var(--i) - var(--mid)) * 50ms)` (precompute `--d` in JS), 400 ms ease-out. | One block fade. |
| scatter assemble（散乱から集合） | load, enter view | Seeded `--x`, `--y`, `--r` per grapheme (fixed seed so reloads repeat), `translate() rotate()` to none, 900 ms `cubic-bezier(.45,0,.2,1)`, shuffled delays up to 400 ms; `overflow: clip`. | Text already assembled; 150 ms fade. |
| random tilt scale in（ランダム傾きズームイン） | load, enter view | Per-grapheme `--r` in ±12deg, keyframes `scale(.5) rotate(var(--r))` to `none`, 500 ms `cubic-bezier(.16,1,.3,1)`, delay 25 ms. | Fade only. |
| smear stretch in（スミア伸長イン） | load, enter view | `transform-origin: right`, from `translateX(-3em) skewX(-30deg) scaleX(3)` to none, 500 ms `cubic-bezier(.2,.8,.2,1)`, delay `(n-i)*25ms`. | Fade only. |
| elastic scale pop（弾性スケールポップ） | load, enter view | `transform-origin: 50% 70%`, `scale(0)` to `1` with a `linear()` spring easing of 2 oscillations (about 700 ms), delay 30 ms; or Motion `spring({stiffness:300, damping:12})`. | Instant full size or 150 ms fade. |
| range selector soft wave（レンジセレクター・ソフトウェーブ） | scroll progress, load | One progress var `--p` (0-1+) on the parent, via `animation-timeline: scroll()` with `@property --p` or one JS tween; each letter computes `clamp((--p*n - i)/w,0,1)` for opacity and y in CSS `calc()`; w = ramp width (e.g. 6). | Text fully shown. |
| random-order fade（ランダム順フェード） | load, enter view | Seeded shuffled delay per grapheme, `opacity 0` to `1`, 300 ms ease-out, delays up to 800 ms. | Block fades in together. |
| grapheme-safe emoji pop（絵文字混じりポップ） | load, enter view | `Intl.Segmenter` grapheme spans (never `split('')`), `scale(0)` to `1` with `cubic-bezier(.34,1.56,.64,1)` 400 ms, delay 40 ms; `display:inline-block`; full text in a visually hidden copy. | Show text at once. |

## Exit

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| character exit up（文字上抜けアウト） | state change, route change | Wrapper `overflow: hidden`, `translateY(-110%)` with opacity down, 350 ms `cubic-bezier(.5,0,1,1)` (ease-in), delay 15 ms; remove node or `hidden` on `animationend`. | Instant removal or 150 ms fade. |
| fade down out（文字フェードダウン退場） | state change, route change | `translateY(0.3em)` and opacity 0, 300 ms ease-in (`cubic-bezier(.4,0,1,1)`), delay `(n-i)*20ms`; `animation-fill-mode: forwards`. | Fade only, 150 ms. |
| blur evaporate out（ブラー蒸発アウト） | state change, route change | Per-word `filter: blur(12px)`, `translateY(-0.3em)`, opacity 0, 500 ms ease-out, reversed stagger 60 ms. | Opacity fade only, no blur. |
| explode scatter out（爆散アウト） | state change, press | Seeded `--x`, `--y`, `--r` per grapheme, `translate() rotate()` with opacity 0, 600 ms `cubic-bezier(.2,.8,.2,1)`, delay from centre outward 10 ms; remove spans afterward and restore plain text. | Instant swap or fade. |
| gravity drop out（重力落下アウト） | state change | Keyframes: small `rotate(±3deg)` wobble 120 ms then `translateY(100vh) rotate(var(--r))` 700 ms `cubic-bezier(.55,0,1,.45)`; shuffled delays up to 400 ms; `overflow: clip` on page. | Fade out only, no fall. |
| scale-down vanish（縮小消滅） | state change | Inline-block graphemes, `transform-origin: center`, `scale(1)` to `0`, 300 ms ease-in, delay 20 ms. | Instant hide or 150 ms fade. |
| reverse-order erase（逆順消去） | state change | Play the entrance with WAAPI `animation.reverse()`, or `animation-direction: reverse` with delays flipped (`(n-i)*delay`); same duration and ease. | Instant removal. |
| collapse to center（中央へ吸い込み） | state change, press | Per-grapheme `--x` = distance to centre, `translateX(var(--x)) scale(0)`, 450 ms `cubic-bezier(.7,0,1,.6)`, delay larger for edges (edge-first). | Fade out only. |
| noise dissolve（ノイズ溶解） | state change | SVG `feTurbulence` plus `feComponentTransfer` / `feColorMatrix` threshold, animate the threshold by SMIL `<animate>` on the primitive attribute or a `requestAnimationFrame` `setAttribute` (CSS variables and `element.animate` do not drive SVG filter attributes), applied with `filter: url(#dissolve)` 900 ms linear; filter is costly on large text. | Opacity fade 150 ms. |

## Emphasis

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| focus word explosion（注目語エクスプロージョン） | press, enter view | Word `scale(1)` to `1.3` to `1` with `cubic-bezier(.34,1.56,.64,1)` 450 ms; 8-12 absolutely placed `aria-hidden` particles on `translate(var(--x),var(--y))` with opacity 0 over 600 ms; remove after `animationend`. | Colour change on the word only, no particles. |
| emphasis slam（強調のスラム）, slam-in title（スラムイン） | load, enter view | `scale(2.5)` to `1` 250 ms `cubic-bezier(.7,0,1,.5)`, squash `scale(1.1,.9)` then rest with `linear()` spring; wrapper `translate` shake ±4px for 200 ms at contact via WAAPI. | Word appears in place, no shake. |
| elastic type（伸び縮みする文字） | hover, enter view | `transform-origin: bottom`, keyframes `scale(1.3,.9)` to `scale(.95,1.05)` to `1`, 600 ms `linear()` spring; inline-block spans. | No scaling; colour shift only. |
| falloff bump wave（バンプウェーブ） | hover, enter view | Per-letter keyframe `scale(1)` to `1.4` to `1` with delay `i*40ms` (one pass), or mouse-driven: set `--s` from pointer distance with a cubic falloff in JS; `transform` only. | No wave; static text. |
| jelly rubber band（ゼリー・ラバーバンド） | hover, press | Keyframes `scale(1.25,.75)` / `(.85,1.15)` / `(1.1,.9)` / `(.95,1.05)` / `1`, 800 ms, `transform-origin: bottom`, per-letter delay 30 ms. | Skip; use a colour change. |
| keyword punch（キーワードの打ち込み） | enter view, state change | Word `scale(1.25)` overshoot to `1.1` with `cubic-bezier(.2,1.4,.4,1)` 300 ms, `color: var(--accent)`; siblings `opacity: .4` through a class on the parent. | Colour and opacity change, no scaling. |
| wiggly jitter（ウィグリー揺らぎ） | hover, loop | Per-letter seeded offsets `translate(±1px,±1px) rotate(±2deg)` in `@keyframes` with `animation-timing-function: steps(1)`, 120 ms cycle, random `animation-delay`; stop after 2 s via `animation-iteration-count`. | No movement. |
| pointer highlight box（ポインタ付き強調枠） | enter view | Box span `position:absolute` with `width`/`height` animated 0 to text bounds (or `clip-path: inset(0 100% 100% 0)` to `inset(0)`, cheaper), 600 ms ease-in-out; decorative cursor SVG `aria-hidden` moved by `translate`. | Box shown fully, no cursor travel. |
| comic pop（コミック・ポップ） | enter view, hover | `-webkit-text-stroke: 3px`, `text-shadow: 4px 4px 0 #000`, halftone via `radial-gradient` dots layer; `rotate(-4deg) scale(.8)` to `none` with `cubic-bezier(.34,1.56,.64,1)` 450 ms. | Static, in final style. |
| strike and correct（取り消し線で訂正） | state change, enter view | Old word with `<del>`-style line pseudo-element `scaleX(0)` to `1` (origin left) 300 ms, then opacity .4; new word `<ins>` `scale(0)` to `1` with `back` ease after 300 ms delay; keep `<del>`/`<ins>` semantics. | Both shown at once, no sequence. |

## Swap

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| glyph slot roll（グリフスロットロール） | hover, state change | Masked `1lh` window, column of glyphs, `translateY(-k*1lh)` 800 ms `cubic-bezier(.65,0,.35,1)`, delay 40 ms per letter; full text in a visually hidden copy, glyph columns `aria-hidden="true"`. | Show the target glyph instantly. |
| letter flip（文字のフリップ） | hover, state change | Parent `perspective: 600px`; two faces per letter, `rotateX(0)` to `-180deg` with `backface-visibility: hidden`, 500 ms ease-in-out, delay 40 ms; faces swap at the half-turn. | Cross-fade 150 ms. |
| split-flap board（スプリットフラップ(パタパタ)） | state change, time | Each cell: upper and lower half clones, `rotateX(-90deg)` on the upper half in steps of 80-120 ms with the next character underneath, cells run different step counts; monospace; the final text in a visually hidden copy, cells `aria-hidden="true"`. | Show the final characters directly. |
| rotating text (spring)（回転テキスト(文字スプリング)） | time, state change | Per-letter `translateY` out/in using `linear()` spring (about 500 ms), 20 ms stagger; container `width` via `interpolate-size: allow-keywords` inside `@supports (interpolate-size: allow-keywords)` (fallback: measured width with FLIP); Motion `AnimatePresence` for mount/unmount; `aria-live="polite"` on one visible word; stop after a few cycles or add a pause button. | Swap words with a 150 ms fade, no loop. |
| flip words（フリップワード(ブラー)） | time, state change | Exit: `translate(2em,-1em) scale(1.4)`, `blur(10px)`, opacity 0, 500 ms ease-in; entry: per-letter `blur(8px)` to 0 with 30 ms stagger; absolute stacking in one slot. | Instant swap with a 150 ms fade. |
| gooey morphing text（グーイー・モーフ） | time, state change | Two stacked absolutely positioned spans, cross-fade with `filter: blur(calc(8px/ p))` proportional to remaining fraction via JS; group `filter: url(#threshold)` with `feColorMatrix` alpha contrast `0 0 0 255 -140`, and if the SVG primitive itself is animated use SMIL `<animate>` or a `requestAnimationFrame` `setAttribute` on it (CSS variables do not drive SVG filter attributes); hold 1.5 s between words; second copy `aria-hidden`. | Plain cross-fade 150 ms, no filter. |
| cube rotate swap（キューブ回転で切替） | hover, time | Parent `perspective: 800px; transform-style: preserve-3d`; faces `rotateX(0)` and `rotateX(90deg) translateZ(0.5lh)`, container `rotateX(-90deg)` 600 ms `cubic-bezier(.45,0,.2,1)`. | Fade between words. |
| skew swipe（スキュースワイプ） | state change, route change | Old: `translateX(-100%) skewX(-20deg)` ease-in 250 ms; new: `translateX(100%) skewX(-20deg)` to none, 400 ms `cubic-bezier(.16,1,.3,1)`; skew resolves in the last 30%. | Cross-fade 150 ms. |
| letter cascade swap（文字カスケード入替） | state change, time | Old letters `translateY(100%)` with opacity out, ease-in 300 ms; new `translateY(-100%)` to `0`, ease-out 400 ms; delay 25 ms per letter; mask by wrapper `overflow: hidden`. | Instant replace. |
| diff text replace（差分だけ打ち替え） | state change | Compute common prefix/suffix in JS; replace only the middle span, toggling per-char opacity at 40 ms steps with no easing; mark with `<ins>` underline briefly. | Replace the middle text at once. |

## Typing and decoding

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| terminal decode（ターミナルデコード） | load, enter view | Monospace block with fixed `$ ` prefix span; JS per-char scramble from a seeded glyph list, lock by index at 30 ms per char; locked line does `scale(1.02)` to `1` over 150 ms; the real text in a visually hidden copy, spans `aria-hidden="true"`. | Print the final lines immediately. |
| type and backspace loop（タイプ&バックスペース） | loop, time | JS state machine: type 60 ms/char, hold 1.5 s, delete 30 ms/char, finite phrases ending on the last; caret `steps(1)` blink only while holding; a visually hidden copy holds all phrases or the first; avoid layout shift with `min-height`. | Show the first (or last) phrase static, no loop. |
| humanised typewriter（人間らしいタイプ） | load, enter view | JS timeouts from a seeded gap list around 70 ms with +250 ms after `,` / `.`; precompute so it repeats; reveal by toggling `visibility` on pre-rendered grapheme spans to avoid reflow. | Show full text at once. |
| terminal type and scroll（ターミナル風） | load, time | Console `div` with `overflow: hidden`, command lines typed per char, output lines inserted whole; shift container `translateY(-1lh)` per line over 120 ms ease-out; cursor is `▮` with blink. `role="log"` on the console for the content. | Static finished transcript. |
| decrypt from center（中央から復号） | load, hover | Interval ~40 ms re-randomising unresolved graphemes (monospace, dimmer colour); resolve order sorted by `abs(i - mid)`, one per 40 ms; final text in a visually hidden copy, spans `aria-hidden="true"`. | Show the decrypted text. |
| per-char flicker in（記号フリッカー出現） | load, enter view | Each char cycles 3-5 seeded symbols at 50 ms with blanks, start chained 40 ms after its left neighbour, final glyph held with no easing. | Show final text. |
| slot shuffle（スロット・シャッフル） | press, enter view | Masked column per char with random glyph strip, `translateY` loop with `animation-direction` alternating; stops via WAAPI with `cubic-bezier(.1,.8,.2,1)` then a final `back` overshoot; slight `scaleY(1.2)` while fast. | Show final characters. |
| character offset cycle（文字コード送り） | enter view, hover | JS: per-char starting offset `k = n - i` stepping down via `String.fromCharCode` wrapped in its script, 60 ms ticks; for Japanese cycle within kana. | Show final text. |
| placeholder replace（伏せ字から置換） | load, state change | Render monospace or `ch`-width placeholders `█` so width stays fixed; swap per char every 50 ms; newest gets `color: var(--accent)` for 200 ms. Keep sensitive text out of the DOM until revealed if it is a secret. | Show the real text. |

## Mask and clip

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| masked character rise（文字マスク・せり上がり） | load, enter view | Per-grapheme wrapper `overflow: hidden` (inline-block), inner `translateY(100%)` to `0`, 500 ms `cubic-bezier(.16,1,.3,1)`, delay 20 ms; exit uses `-100%`. | Fade 150 ms. |
| masked horizontal slide（横スライドイン(マスク)） | load, enter view | Per-char `overflow: hidden` inline-block, inner `translateX(-100%)` to `0`, 400 ms `cubic-bezier(.16,1,.3,1)`, delay 25 ms. | Fade only. |
| split-halves slide（上下分割スライド） | load, enter view | Two copies, `clip-path: inset(0 0 50% 0)` and `inset(50% 0 0 0)`, `translateX(-60%)` / `60%` to `0`, 500 ms `cubic-bezier(.16,1,.3,1)`; the second copy `aria-hidden`. | Single copy fades in. |
| soft gradient mask wipe（ソフトマスク・ワイプ） | enter view, scroll progress | `mask-image: linear-gradient(90deg, #000 40%, transparent 60%)` with `mask-size: 250% 100%` animating `mask-position`, 900 ms ease-out; `-webkit-mask-image` prefix; or `@property` animated stops. | Text unmasked, 150 ms fade. |
| bar wipe reveal（バーワイプ出現） | enter view | Pseudo-element bar `scaleX(0)` to `1` (origin left) 300 ms, then origin `right` and `scaleX(1)` to `0` 300 ms; text `visibility` flipped at midpoint or `clip-path` to the trail. | Text visible, bar skipped. |
| shape-mask transition（形状マスク切替） | state change, route change | View Transitions: `::view-transition-new(root)` animated `clip-path: circle(0)` to `circle(150%)` at 600 ms ease-in; fallback swaps content under an overlaid shape via `clip-path` WAAPI. | Instant swap, no shape. |
| venetian blinds reveal（ブラインド・リビール） | enter view | Overlay of N strips with `scaleY(1)` to `0` from the top, 400 ms ease-out, delay 40 ms; or `mask-image: repeating-linear-gradient` with animated `mask-size`; snap heights to whole pixels. | Text visible, 150 ms fade. |
| diagonal cut reveal（斜めカット・リビール） | enter view, load | `clip-path: polygon(0 0,0 0,-20% 100%,-20% 100%)` to `polygon(0 0,120% 0,100% 100%,0 100%)` with matching vertex counts, 600 ms `cubic-bezier(.16,1,.3,1)`; optional blade pseudo-element. | Fade in, no clip. |

## Blur and focus

| Name | Trigger | Web build | Reduced motion |
| --- | --- | --- | --- |
| text generate effect（テキスト生成エフェクト） | load, enter view | Word spans `filter: blur(8px); opacity: 0` to clear, 500 ms ease-out, delay 80 ms; layout stable because only filter and opacity change. | Opacity only, no blur. |
| 3-step blur in（3段ブラーイン） | load, enter view | Keyframes: `0%` blur 12px, y -20px; `60%` blur 4px, y 6px; `100%` blur 0, y 0; 700 ms ease-out per segment. | Fade only. |
| random blur in（ランダムブラーイン） | load, enter view | Seeded shuffled delay per grapheme, `blur(10px)` to `0` and opacity, 600 ms ease-in-out. | Opacity fade only. |
| blur and tracking build（ブラー&トラッキング出現） | load, enter view | `letter-spacing: .4em` to `0` over 1.6 s and `blur(10px)` to `0` over 1.2 s with a 200 ms offset plus opacity; letter-spacing reflows, so reserve width on a centred block. | Static text, optional fade. |
| directional blur slide（方向ブラースライド） | enter view, load | `translateX(-60px)` to 0, 400 ms `cubic-bezier(.16,1,.3,1)`, with SVG `feGaussianBlur stdDeviation="12 0"` reduced to `0 0` by `setAttribute` in a `requestAnimationFrame` loop (or SMIL `<animate>`); apply with `filter: url(#blurX)`. | Fade only. |
| scale blur zoom in（スケールブラー・ズームイン） | load, enter view | `scale(1.2)` and `blur(12px)` to `scale(1)` and `blur(0)` on one 800 ms `cubic-bezier(.2,.7,.2,1)`; `transform` and `filter` together. | Opacity only. |
| true focus（トゥルーフォーカス枠） | time, hover | Words `filter: blur(4px)`, active word `blur(0)`; bracket `div` positioned from `getBoundingClientRect`, moved with `translate` and sized by `width`/`height` (or FLIP) 350 ms ease; pause 1 s per word. | Highlight word by colour, no blur or frame travel. |
