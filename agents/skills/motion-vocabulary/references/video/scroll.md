# Scroll-driven motion vocabulary: video builds

How each entry of [../scroll.md](../scroll.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

A scroll is the page container translated by the timeline; elements react to that progress value.

## Scroll-driven page

**Group 1: things that appear**

| Name | Built with |
| --- | --- |
| scroll-triggered fade-in / scroll reveal（フェードイン、スクロールリビール） | opacity and a small y tween on `power2.out`, placed on the master timeline at the moment the block crosses the lower edge of the frame |
| slide-in（スライドイン） | x tween from an off-axis start on `power2.out`, with a short opacity ramp; start time set at the entry position, left or right alternating by block |
| stagger（スタッガー） | a shared tween per item with start offsets that grow in index order from the entry position; core: `split-text stagger` |
| text reveal / split text（テキストリビール） | text split into spans, each wrapped in an overflow mask, y from below the mask to zero on `power3.out` with offsets per piece; core: `mask reveal (line rise)` |
| clip-path reveal（マスクリビール） | `clip-path: inset()` tween from three sides closed to open on `power3.inOut`, started at the entry position |
| blur-in reveal（ブラーイン） | `filter: blur()` down to zero together with opacity and a small y rise on `power2.out`; blur ends a little earlier than the move; core: `blur-in / focus pull` |
| typewriter（タイプライター） | per-character opacity set on a list of times stepped by seeded small jitter, caret positioned after the last visible char; core: `typewriter + caret` |
| count-up（カウントアップ） | tween on a plain object on `power2.out`, writing the rounded value into the text on every update; core: `count-up` |

**Group 2: motion tied to scroll progress**

| Name | Built with |
| --- | --- |
| scroll-linked animation（スクロール連動） | a master timeline whose progress is the scroll position, each element's tween placed across its span of that progress on `none` ease |
| parallax（パララックス） | per-layer y distance proportional to progress, a larger multiple for near layers on `none` ease; core: `parallax layers` |
| scale on scroll / scroll depth zoom（スクロールズーム、スクロール奥行きズーム） | scale on a wrapper tied to progress with a matching brightness rise on `sine.inOut`; the outgoing layer optionally blurs or fades |
| scroll-scrubbed image sequence（画像シーケンス） | a stack of supplied frames shown by index from progress, or a canvas drawing the frame at that index; the frames are copied as they are |
| SVG line drawing（SVGラインドロー） | `stroke-dashoffset` mapped from full length to zero across the span of progress, on `none` ease, path length normalised |
| text fill on scroll（テキストフィル） | per-word colour or opacity from dim to full, each word's span a short slice of progress offset by its index |
| background colour transition（背景色トランジション） | a full-frame background layer with colour tweened between keyed progress values on `none` ease |
| marquee / scroll velocity / scroll marquee（マーキー、スクロールマルキー） | linear x tied to progress on a doubled strip that wraps, with an extra offset taken from the speed of the scroll curve, precomputed on the timeline; core: `marquee / ticker` |
| scroll progress（スクロール進捗） | `scaleX` from zero to full tied to progress on `none` ease, transform origin on the left edge of a fixed bar |
| text scroll resolve（文字スクロール解像） | per-character offset, blur and slight tilt brought to zero by progress, each span delayed by its index, from seeded starting values |
| image clip scrub（画像クリップスクラブ） | `clip-path` inset and radius tied to progress on `power2.inOut`, image layer fixed behind |
| scroll velocity skew（スクロール速度スキュー） | `skewY` driven by a speed value taken from the scroll curve's derivative, precomputed on the timeline, clamped to a small angle and eased back to zero on `power2.out` |

**Group 3: fixed, paged and navigation**

| Name | Built with |
| --- | --- |
| sticky / sticky pin（スティッキー、スティッキーピン） | the element's counter-translation equal to the page travel for a span of progress, normal travel before and after |
| pin + scrub（ピン留め＋スクラブ） | pinned wrapper with its y cancelled across the span, inner timeline progress mapped linearly to that span |
| scrollytelling / pinned story steps（スクロールテリング、ピン留めストーリー） | pin + scrub with keyed progress stops, one state change per step on `power2.inOut`, text steps fading and rising past in turn |
| stacking cards（カードスタック） | each card y from the bottom edge to its stack position, the previous card's scale and brightness tied to the next card's progress; core: `push stack` |
| scroll snap（スクロールスナップ、セクションスナップ） | y stepping between section positions, each step an ease-out into the stop on `power4.out`, with a still hold between |
| horizontal scroll / horizontal scrub（横スクロール、横スクロールスクラブ） | pinned wrapper, the row's x tied to progress from zero to the full width minus one frame on `none` ease |
| hide-on-scroll header（隠れるヘッダー） | y from fully visible to just above the frame on `power2.out`, tweens placed at the points where the scroll direction flips |
| scrollspy（スクロールスパイ） | each item's active state keyed to its section's progress range, one indicator element tweened between item positions on `power2.out` |

## Scrolling text

| Name | Built with |
| --- | --- |
| scrubbed chapter index（章番号スクラブ） | the page container moved by the timeline, numeral text set from its progress value, a short slide-and-fade on each change with `power2.out` |
| scroll word highlight（スクロールで単語明転） | per-word opacity from dim to full, each driven by a slice of the container scroll progress, linear scrub |
| view-timeline word reveal（CSS view() 単語リビール） | the CSS `view()` timeline behaviour is reproduced by a progress value computed from the timeline-driven scroll position and each word's place in the container, small y rise and opacity, linear mapping |
| scroll reveal blur and tilt（傾き+ブラー解像） | block rotate to zero plus per-word blur and opacity staggered across the scroll progress, linear scrub |
| scroll clip write-on（スクロール書き出し） | `clip-path` inset on the text tied to scroll progress over an offset range, linear, range offset per line for line-wise writing |
| scroll velocity marquee（スクロール速度マーキー） | duplicated row looped by x modulo one copy width, the offset a closed-form function of time: base drift plus the integral of the authored scroll curve scaled by a sampled spring multiplier |
| velocity skew（スクロール速度スキュー） | skewY on the heading set from the authored scroll curve's speed as sampled keyframes, follow-through with `power3.out`, a small overshoot on release |
| horizontal scroll letter drop（横スクロール文字落下） | pinned container with x moved by the timeline, per-char y and scale from above and oversize with `back.out`, parent clipped |
| dual wave columns（デュアルウェーブ列） | per-item x as sine of its y with a phase offset, one column negated, scroll scrub, highlight by size and colour at the centre |
| text repetition echo（テキスト反復エコー） | stacked duplicate rows with rotate offsets around a low origin, opacity falling along the stack, `power2.inOut` scrub |
| sticky shrinking headline（追従縮小見出し） | pinned element, scale tween from full to small with transform origin top left, linear to scroll progress rather than font size |
| line parallax（行ごとのパララックス） | per-line y multiplier of scroll progress, linear scrub, the section clipped |
