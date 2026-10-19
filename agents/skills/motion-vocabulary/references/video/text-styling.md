# Typographic treatment vocabulary: video builds

How each entry of [../text-styling.md](../text-styling.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

## Glyph physics

| Name | Built with |
| --- | --- |
| character magnetize（文字マグネット整列） | seeded start positions per char, a shared end, `power3.out`, a small stagger between letters |
| letter collision bounce（文字衝突バウンス） | precomputed collision keyframes per char: a short pull back, a hit that shifts the neighbours, then a decaying settle to home |
| inertia letters（飛び込んで揺れて止まる文字） | `elastic.out` on x with a rotate sway of decaying amplitude, per-letter staggered landings |
| drop and bounce in（落下バウンド） | per-char y from above with `bounce.out`, a short stagger, shadow tween on the floor layer |
| raining characters（文字の雨） | per-char y fall in shuffled order with `power2.out`, a few trailing copies at lower opacity removed on landing |
| falling text physics（落下して積もる） | seeded resting positions, a `bounce.out` fall with loss on each rebound, slight give in the lower row on impact |
| pendulum swing（振り子スイング） | rotate from a start angle with decaying amplitude, transform-origin at the pivot, a spring-like ease, a small stagger |
| squash landing（着地スクワッシュ） | scaleY stretch in flight, at contact scaleY down and scaleX up, then `elastic.out` recovery with origin at the bottom |
| spring chain follow（バネ連鎖追従） | the lead's path is keyed on the timeline; each other letter reuses the same sampled spring keyframes shifted by a growing delay, so its position at any time is a function of the lead's keyed position at an earlier time, plus its width offset |
| zero-gravity drift（無重力ドリフト） | slow seeded x, y and rotate yoyo per char with `sine.inOut`, finite repeats |
| domino topple（ドミノ倒し） | per-char rotate from the bottom corner on `power2.in`, the next starting at impact, wide tracking so contact comes late |

## Path and shape

| Name | Built with |
| --- | --- |
| circular text spin（円形テキスト回転） | SVG `textPath` on a circle, the group rotated linearly for a finite number of turns |
| curved loop marquee（曲線ループマーキー） | `textPath` `startOffset` tween across exactly one period, linear |
| text along path（パスに沿って走る） | `textPath` startOffset or per-char positions on the path, ease out to the hold, then ease in |
| path with tracking inertia（パス+慣性トラッキング） | per-char offsets with different delays and `back.out`, a decaying oscillation applied to spacing on the stop |
| outline stroke draw（アウトライン線描） | glyph paths with `stroke-dashoffset`, a small glyph stagger, then a fill opacity fade |
| handwriting write-on（手書き線描） | centreline paths revealed through a mask with `stroke-dashoffset`, sequential per stroke, easing at both ends of each |
| spiral text（渦巻きテキスト） | `textPath` on a spiral, offset tween linear, font size tied to the radius |
| morphing path ride（変形するパスに乗る） | path `d` morph with matching point counts, text offset tween, ease in and out |
| shape contour text（図形の輪郭を巡る） | `textPath` on the shape outline, offset tween linear over a loop, the string repeated to fill the length |

## Colour and light

| Name | Built with |
| --- | --- |
| animated gradient text（グラデーション流動） | `background-clip:text`, background-position tween linear, first colour repeated at the end |
| aurora text（オーロラテキスト） | blurred colour blobs beneath a text clip, with a gentle rotate and scale on a long ease in and out |
| conic gradient spin（コニック回転） | conic gradient fill, angle tween linear for finite full turns, first colour repeated at the end |
| colour band sweep（カラーバンド・スイープ） | gradient with hard stops and a narrow band, position tween on `power1.inOut` |
| per-character hue cycle（色相サイクル）, colourful text cycle（カラフル文字サイクル） | hue values per character taken from a phase list, finite cycles, with an optional small y hop and blur at each swap |
| neon flicker-on（ネオン点灯） | seeded opacity steps per letter, stacked glow copies, final state fully lit |
| line shadow text（ラインシャドウ） | a repeating-gradient shadow layer offset behind the text, background-position tween linear |
| long shadow grow（ロングシャドウ伸長） | stacked copies or a skewed shadow layer with a scale tween, `power2.out` |
| blend overlap（文字重なり合成） | letter-spacing tween negative, `mix-blend-mode: multiply` or `screen` on layers, ease in and out |

## Distortion and glitch

| Name | Built with |
| --- | --- |
| RGB split glitch（RGB分離グリッチ） | tinted copies in triplicate, `mix-blend-mode: screen`, clip bands with seeded offsets, brief frame bursts |
| slice displacement（スライス変位グリッチ） | clip-path strips with seeded x offsets, held a few frames |
| fuzzy text（ファジーテキスト） | `feTurbulence` plus `feDisplacementMap` on the text layer with a seeded scale, the field redrawn every frame, intensity raised for a moment of emphasis |
| turbulence wobble（タービュランス揺らぎ） | displacement map driven by a turbulence field with a small scale, the seed stepped at a leisurely interval, applied to the text layer only |
| ASCII text（ASCII テキスト） | a `<pre>` grid built from a brightness ramp over the rendered word, a small wave offset per row, updated at a modest frame rate |
| VHS tracking noise（VHS 走査線ノイズ） | a tracking band tweened down the frame with offset slices inside it, static scanlines, an occasional brief jump, a faint chroma offset |
| pixel mosaic resolve（モザイク解像） | scale-down then back up with `image-rendering: pixelated`, driven by `steps()` so the resolution changes in even hard jumps, then held sharp |
| melt drip（溶けて垂れる） | per-char scaleY stretch at the bottom with drop streaks, a displacement and threshold filter for the liquid edge, ease-in, an offset per character |

## 3D and depth

| Name | Built with |
| --- | --- |
| perspective type tunnel（文字遠近トンネル） | one layer per ring inside a perspective container, each at a stepped translateZ; a slow shared z tween on the group with `power2.inOut`, far rings faded by opacity |
| 3D flip up（3D フリップアップ） | per-char rotateX from lying down to upright with the transform origin at the bottom edge, perspective on the parent, a short stagger, `expo.out` |
| swing door（スイングドア） | per-char rotateY from turned away to flat with the pivot at the right edge, translateZ easing to zero, stagger from the end, `expo.out` |
| fly in from depth（奥から飛来） | per-char translateZ from far to zero under a perspective parent, opacity from faint to full, `back.out` with a small overshoot, short stagger |
| tumbling 3D entrance（回転落下イン） | per-char rotateX and translateZ from seeded different starts to rest, perspective on the parent, `power1.inOut`, a small bounce on y at landing |
| 3D roll flip（3D ロールフリップ） | per-char box with preserve-3d and two faces, rotateX by a quarter turn, a short per-letter delay, a brisk ease-in-out |
| 3D cylinder text（3D 円筒テキスト） | each rotateY set by the letter's slot angle then translateZ pushed out to the radius, the group rotating at constant speed with `none` ease for a seamless loop |
| layered depth text（レイヤー奥行き文字） | a stack of copies at tiny stepped translateZ steps with a front copy on top, the group tilted by rotate keyframes sampled from the drawn cursor path at an earlier time, so the lag is a fixed delay on the timeline |
| paper fold（折りたたみ） | a few stacked panels, each rotateX hinged on its top edge to alternate angles, staggered, `power2.out`, shade overlay opacity tied to the angle |
| MoText falloff sweep（エフェクター掃引(MoText)） | per-char transforms read from a falloff curve around a moving point driven by a linear tween, each char returning through `elastic` |

## Variable fonts

| Name | Built with |
| --- | --- |
| variable font pulse（可変フォントパルス） | `font-variation-settings` weight tween on the element, `back.out` outward, a short settle back, finite repeats |
| variable weight wave（ウェイトウェーブ） | per-char weight yoyo offset by index, `sine.inOut`, each char held in a fixed-width box, finite repeats |
| variable width stretch（可変幅ストレッチ） | width axis tween per char offset by index, `sine.inOut`, container centred or given room, finite repeats |
| weight breathe（ウェイト呼吸） | yoyo weight tween on one element across the axis minimum and maximum, `sine.inOut`, fixed-width container, finite repeats |
| thin to bold entrance（細→太で出現） | per-char opacity set, weight from minimum to maximum with `power3.out`, short stagger, space held at the final-weight width |
| slant axis swing（傾き(slnt)スイング） | per-char `slnt` axis tween offset by index, `sine.inOut`, finite repeats; skewX with the origin at the bottom as a stand-in |
| width/slant velocity（速度で幅・傾き変化） | width and slant axes taken from the derivative of the authored scroll curve, with the overshoot after the stop baked into sampled keyframes or an `elastic` return, all a function of timeline time |
| text pressure（テキストプレッシャー） | weight and width axes per char from distance to a timeline-driven cursor, the line held in a fixed-width box |
| variable proximity（可変プロキシミティ） | weight per char from a Gaussian falloff of distance to the cursor path, optical-size axis alongside |

## Pointer

| Name | Built with |
| --- | --- |
| magnetic letters（マグネット文字） | per-char x/y offset computed each frame as a pure function of the distance to the cursor's timeline position, easing with `power3.out` out to the cursor's departure time, returning to zero |
| pointer proximity repel（近接反発） | per-char displacement opposite the cursor direction, proportional to proximity, with the lag written as an exponential approach that is a function of time since the cursor's position changed, evaluated from the cursor's timeline path |
| proximity scramble（近接スクランブル） | per-char swap and restore times precomputed from the distance between each glyph and the cursor's drawn path, restore time scaled by distance, set with `steps()`, final glyph restored |
| clone roll hover（複製ロールホバー） | two stacked copies in an `overflow:hidden` slot, y tween on both with `power3.out`, per-char stagger |
| hover word lift（ホバー単語リフト） | per-word y offset upward with `back.out`, colour set as the cursor path reaches each word |
| text cursor trail（カーソル軌跡テキスト） | stamp spans placed at path-length intervals along the drawn cursor path, each with a fixed timeline start time computed from where the path reaches that length, scale in with `back.out`, a finite pool, exit by fade and scale down |
| spotlight outline hover（スポットライト輪郭） | stroke-dashoffset draw-on, a second copy with a gradient stroke under a radial mask following the cursor path, `sine.inOut` |
| pointer reveal card（ポインタでめくる） | two stacked layers, clip edge following the cursor path, return tween with `power2.out` |
| cursor bulge lens（カーソル膨張レンズ） | a displacement filter or magnified round clone positioned each frame from the cursor's drawn timeline path, `power2.inOut` ramp, a still frame when at rest |

## Numbers and data

| Name | Built with |
| --- | --- |
| monospace data shuffle（等幅データシャッフル） | seeded digit lists per cell, resolved by index with `expo.out`, tabular figures, a small impact on each lock |
| price ticker flash（価格ティッカー・フラッシュ） | background colour sets on change fading out, changed-digit y slide, finite pulses; never more than 3 flashes in any one second, and no saturated red full-frame flash |
| score update（スコア更新） | two digit layers folding on rotateX with `power2.out`, a small scale pop on the arriving one, and a background layer on the cell rising in opacity then falling back; one event, ends at rest |
| number scramble settle（数字シャッフル確定） | seeded digits per index changing in `steps()`, a lock time per index staggered, tabular figures |
| percent with ring（パーセント+リング） | a ring path with its dash offset tweened on `power2.out`, and the centre number written from the same tween value on every update; the ring track sits still behind, ending on the full figure |
| countdown zoom（カウントダウン） | per-numeral scale and opacity with `back.out` in then an ease-in out, swapped at set times |
| seven-segment display（7セグメント表示） | seven bar rects per digit with opacity set from a mask, a very short transition, colon on a finite beat |

## Loops and decoration

| Name | Built with |
| --- | --- |
| wave loop（ウェーブループ） | per-char y with `sine.inOut`, a phase offset per index, finite repeats |
| wiggly scale breathe（拡縮の呼吸） | per-char scale yoyo with a seeded rate and phase, `sine.inOut`, finite repeats |
| sparkles text（スパークル文字） | seeded sparkle positions, scale pops, a turn, finite respawns |
| sequential hop（順番ジャンプ） | per-char y arc with `back.out` and a squash, offset by index, finite loop with a pause |
| staggered Y spin（文字スピン連鎖） | per-char rotateY by a full turn with `power2.inOut`, perspective on the parent, finite repeats with a pause |
| loading dots（読み込み中…、ローディングドット） | three dot spans with a stagger on y and opacity, `sine.inOut`, a finite number of cycles, ending with the dots at rest |
| hanging sign sway（吊り看板の揺れ） | rotate on the wrapper with the origin above, a damped start with `elastic.out`, then `sine.inOut`, finite |
