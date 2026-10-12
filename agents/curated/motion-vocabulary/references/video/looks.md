# Looks, light and effects vocabulary: video builds

How each entry of [../looks.md](../looks.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

The rendering language of the world you draw: backgrounds, props, type and
your own drawn shapes. Name one in the look-in-words; the producer's own style
reference, when chosen, is the fuller brief. A look never re-renders supplied
art, a cast or a logo: apply a look's filters and textures to world layers,
never to a wrapper that contains supplied art. Entries marked 3D need a 3D
path where the producer offers one; elsewhere build the 2.5D imitation named
in the same row.

## Drawn looks

### Hand-drawn and paper

| Name | Built with |
| --- | --- |
| risograph（リソグラフ） | one layer per ink with `mix-blend-mode: multiply`; dots as a `radial-gradient` with `background-size`; a few px offset per plate; fixed-seed `feTurbulence` grain (see halftone / dither) |
| origami（折り紙） | SVG polygons in 2-3 tones of one hue; unfolding = facets rotating on their shared crease (`transform-origin` on the edge) |
| sumi-ink brush（墨の筆） | a filled variable-width stroke shape revealed by a mask path drawn along its centreline (`stroke-dashoffset` on the mask, slow-fast-slow ease; a plain stroke keeps one width); fixed-seed `feTurbulence` + `feDisplacementMap` for the ragged edge; a thinner offset stroke through a grain mask for dry brush; washes as blurred low-opacity shapes; ink bleed / brush wipe between beats |
| pencil sketch（鉛筆スケッチ） | shapes made of many thin hatch paths; draw-on per stroke group; low-scale displacement for hand wobble; paper-tooth overlay |
| crayon（クレヨン） | fills as dense zig-zag strokes clipped to the shape; coarse grain mask on fill and outline; boil |
| watercolor（水彩、水彩のにじみ、watercolor wash） | layered blurred shapes with `mix-blend-mode: multiply`; the same shape stroked and less blurred for the edge; fixed-seed noise mask for blooms; bleed-in = slow scale/opacity spread |
| paper cut-out (kirie)（切り絵、ストップモーション、paper cut / stop-motion） | flat SVG layers, one drop shadow per layer, parallax by layer |
| chalkboard（黒板） | stroked paths through a grain mask on a dark green surface; write-on via `stroke-dashoffset`; ghosts as low-opacity blurred copies |
| one-line drawing（一筆書き） | a single path drawn by `stroke-dashoffset`; blobs as soft shapes that fade in after the line passes |

### Anime

| Name | Built with |
| --- | --- |
| cel anime（セルアニメ） | SVG shapes with a base fill and a separate hard-edged shadow path per form; `stroke` at the cast's line weight; no blur or soft gradients on drawn forms; motion on twos with limited-animation holds |
| painted anime backdrop（アニメの背景美術） | layered SVG or supplied painted plates with a fixed-seed brush-texture mask; haze as a low-opacity light layer per depth plane; parallax by plane; the cast layer never takes the paint texture |

### Graphic

| Name | Built with |
| --- | --- |
| flat Bauhaus（フラットなバウハウス） | SVG primitives; motion as half discs rotating and bars sliding on a grid |
| isometric（アイソメトリック） | SVG on an isometric grid, or one `rotateX(60deg) rotateZ(45deg)` plane |
| infographic（インフォグラフィック） | SVG paths; donut arcs by `stroke-dashoffset`; labels by count-up |
| blueprint（青写真） | grid from repeating linear gradients; line draw per part; callouts as tooltip / callout |
| stained glass（ステンドグラス） | SVG polygons with a thick dark stroke, an inner radial glow, a sheen / shimmer passing over |
| tile mosaic（タイルモザイク） | a grid of small rects coloured from a source shape, fixed-seed jitter; reveal staggered from the centre |
| silhouette（シルエット） | flat dark SVG shapes over a gradient, parallax layers |
| stark graphic（ストイックなグラフィック） | flat SVG fills with no blur, gradient or texture; long holds broken by one snap move; hard cuts on the beat; cards as full-frame rects; never more than 3 flashes in any one second, and no saturated red full-frame flash |

### Screen and retro

| Name | Built with |
| --- | --- |
| CRT / VHS（ブラウン管、VHS、走査線、CRT scanlines） | repeating-gradient scanlines; rounded inner vignette for the glass; chromatic aberration; a band tweened down the frame |
| pixel art（ドット絵） | draw small and scale with `image-rendering: pixelated`, or `shape-rendering: crispEdges` rects; motion in whole-pixel steps |
| ASCII terminal（ASCIIターミナル） | a `<pre>` grid whose characters come from a brightness ramp computed per frame from a deterministic shape; typewriter + caret for the prompt |
| glitch（グリッチ、グリッチイン） | `clip-path` slices offset on a seeded schedule; RGB-split copies; each burst held 2-6 frames |
| neon sign（ネオンサイン） | stroked text/paths with layered blurred copies (bloom / glow); seeded opacity steps for the flicker; radial gradient halo |

### Solid (3D)

| Name | Built with |
| --- | --- |
| low-poly 3D（ローポリ3D） | 3D: flat-shaded procedural geometry; 2.5D: SVG triangles in three tones |
| toon 3D（トゥーン3D） | 3D: toon material plus an inverted-hull outline; 2.5D: flat shapes with one hard shadow shape |
| clay stop-motion（クレイアニメ） | 3D: rough material with fixed noise; 2.5D: soft gradients and grain; animate on twos |
| product shot（プロダクトショット） | only from supplied product photos or renders, never invented packaging; shadow stack, reflection floor; 3D turntable only for a procedural stand-in shape |

### Generative, math and data

| Name | Built with |
| --- | --- |
| flow field（フローフィールド） | lines precomputed from a field (potential flow around a circle, psi = y(1 - R^2/r^2), or fixed-seed noise angles); motion by `stroke-dashoffset` along each line |
| particles（パーティクル、粒が集まって形になる、particles coalesce、パーティクル文字） | canvas or SVG points with seeded starts, each grain tweening between two samplings of the shapes |
| marbling (suminagashi)（マーブリング、墨流し） | closed rings around seeded centres, warped by fixed-seed displacement whose scale tweens |
| math diagram（数式ダイアグラム） | SVG; one angle tween drives the radius end, a growing path and the written number |
| transit map（路線図） | lines by `stroke-dashoffset`; map + pin + route; push-in |
| kinetic typography（キネティックタイポグラフィ） | kinetic lockup, scale punch, blur-in, outline-to-fill |

## Effects

| Name | Built with |
| --- | --- |
| bloom / glow（ブルーム、グロー） | blurred duplicate behind, `mix-blend-mode: screen` |
| light leak（ライトリーク） | large blurred gradient blobs drifting |
| light field（ライトフィールド） | 2-4 radial gradients, slow drift |
| lens streak（レンズストリーク） | thin blurred bar, screen blend |
| sheen / shimmer（シーン、光沢のきらめき） | angled gradient masked to the element, x tween |
| glassmorphism（グラスモーフィズム） | `backdrop-filter: blur()`, 1px light border |
| shadow stack（シャドウスタック） | multiple `box-shadow` layers |
| reflection floor（反射する床） | flipped copy with gradient mask |
| motion blur（モーションブラー、subframe motion blur） | directional blur only while moving |
| depth of field（被写界深度） | per-layer blur |
| film grain（フィルムグレイン） | SVG `feTurbulence` or seeded noise overlay, low opacity |
| chromatic aberration（色収差、色収差分離） | RGB-split copies offset a few px |
| pulse ring（パルスリング） | circle scale 1 -> 3, opacity 1 -> 0 |
| particle burst（パーティクルバースト） | pre-placed seeded particles, radial tweens |
| sparkle（スパークル、きらめき、twinkle sparkles） | small scale/rotate pops |
| spotlight（スポットライト） | radial gradient positioned on the subject |
| halftone / dither（ハーフトーン、ディザ） | pattern fill or SVG filter |
| vignette（ビネット、周辺減光、vignette breathe、呼吸する周辺減光） | radial gradient overlay |
| noise gradient / mesh gradient（ノイズグラデーション、メッシュグラデーション） | several blurred blobs, optional grain |
| confetti（紙吹雪） | seeded pieces with an upward radial launch on `power2.out`, then gravity on y, rotate, sideways sway and scaleY driven by a cosine to flip front and back; finite fall, cleared before the next beat |
| rising embers（立ち昇る火の粉） | seeded dots with a linear upward y, a sine sway on x, and size and opacity decaying over each lifetime, with varied speeds and starts |
| snow（雪） | seeded flakes grouped in a few layers, a linear y fall with a sine sway on x, with size, speed and blur set by layer and the nearest layer softest |
| fireworks with trails（花火、尾を引く） | a launch y on `power2.out`, radial seeded sparks expanding on an ease-out, then a gravity droop, with trail copies drawn at earlier positions and decreasing opacity |
| swarm（群れ、漂う光） | seeded points each following a centre plus noise offset from a shared field, the centre itself drifting slowly and pulling the group in, with varied speeds per point |
| misregistration（版ずれ、リソグラフ） | drawn artwork as separate colour layers with multiply blend, the offset between them reduced in a few `steps()` toward a small remainder, limited to two or three plates |
| brush write-on（筆で書く、ライトオン） | a mask path laid along each stroke revealed with `stroke-dashoffset` on a slow-fast-slow ease, strokes started one after another in writing order with a small gap |
| pixelate（ピクセル化、粗くする） | a canvas downsample at stepped coarseness drawn back up with crisp, non-smoothed scaling on `steps()`, each level held a few frames, applied to drawn layers |

## Light and glow

| Name | Built with |
| --- | --- |
| glow pulse（グローパルス、グロー脈動） | a blurred copy layer behind the element, opacity and size yoyo on `sine.inOut` for a finite number of repeats, ending at the resting glow |
| neon flicker（ネオン点滅） | seeded opacity steps on the glow layers, with the sharp core flickering a little less than the halo, ending steady at full |
| light sweep（ライトスイープ） | an angled gradient on a drawn layer masked to the element, tweened in x on `power2.inOut` with an add blend |
| bloom reveal（ブルーム出現） | a blurred, bright copy layer shrinks and fades while the sharp layer rises in opacity, both on `power3.out` |
| rim glow（リムグロー） | a stroke or edge-glow layer with a moving gradient along the outline on `sine.inOut`, one loop or a finite few |
| energy charge（エネルギーチャージ） | rings rotating and shrinking toward the core on `power2.in`, with core glow rising to its maximum on the last frame of the build |
| light trail（光跡） | trailing copies of a glow layer on growing delays with falling opacity, merging into the head position when it comes to rest |
| scan line（スキャンライン） | a thin bar layer tweened across a masked area with `none` ease, with a faint trailing gradient |
| aurora glow（オーロラグロー） | blurred gradient blobs on drawn layers behind the subject, long looping tweens on `sine.inOut`, finite repeats |
| radial flash（ラジアルフラッシュ） | a radial gradient layer scaled up with opacity falling on `expo.out`; never more than 3 flashes in any one second, and no saturated red full-frame flash |
| lens flare sweep（レンズフレアスイープ） | a bright streak and several discs offset along one axis on a drawn layer, screen blend, tweened across on `power2.inOut` |
| holographic sheen（ホログラムシーン） | a multi-colour gradient masked to the element, its position tweened on `sine.inOut`, ending off the surface |

## Effects and swaps

| Name | Built with |
| --- | --- |
| blur zoom（ブラーズーム） | one tween of scale with blur to zero and opacity up on a drawn layer, on `power3.out`, transform origin at the centre |
| slice reveal（スライスリビール） | several clipped copies of the subject with staggered x offsets from alternating sides on `power2.inOut`, ending with zero offset |
| ripple reveal（リップル出現） | an expanding ring-shaped mask on a drawn layer with a second ring on a delay, both on `power2.out`, the subject uncovered where the mask has passed |
| noise resolve（ノイズ解像） | a seeded noise overlay layer fading down, blur on the drawn layer falling to zero and its opacity rising, on `sine.out` |
| liquid morph（リキッドモーフ） | a blur plus high-contrast filter over moving blobs, or a path morph between two contours, on `power2.inOut` |
| mosaic flip（モザイクフリップ） | a grid of tiles each with `rotateY` on a diagonal stagger, the new face sitting behind and the old one hidden after the half turn |
| displacement wave（ディスプレイス波） | an `feDisplacementMap` on a drawn copy with its scale tweened up and back, or a moving map, on `sine.inOut` |
