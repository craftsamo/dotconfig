# Motion and component vocabulary

A dictionary, not a rulebook. Left alone, a plan collapses every idea into
"fade in", "slide", "card" and "transition", every abstract idea into a
label or an icon, and every look into "clean flat". Use these names instead: pick
the one that says exactly what the viewer should see, and write it into the
storyboard or design by name (one entry per event or component; combine
entries freely; a more precise name of your own is fine). Each entry gives
what it looks like and how it is usually built in HTML/CSS/SVG/GSAP.

## Text animations

| Name | Looks like | Built with |
| --- | --- | --- |
| split-text stagger（スタッガー） | letters/words/lines arrive one after another as a wave | split into spans; stagger 0.02-0.08 s on y/opacity |
| mask reveal (line rise)（マスクリビール、行マスク・せり上がり） | each line slides up out of an invisible slot, cut off below (vertical writing: each column slides down from above) | line wrapper `overflow:hidden`; inner span y 110% -> 0 (x for vertical columns) |
| blur-in / focus pull（ブラーイン、文字ブラーイン） | words arrive soft and snap sharp as they land | `filter: blur()` 12-20px -> 0 with y or scale |
| scale punch（スケールパンチ） | a key word lands oversized and settles to size | scale 1.3-1.6 -> 1, expo/back ease |
| tracking-in（字間が縮まって入る、トラッキング・エクスパンド、トラッキング収束） | letters spread wide then contract into the word | letter-spacing 0.5em -> normal, opacity |
| typewriter + caret（タイプライター、カーソル点滅タイプ） | characters appear one by one with a blinking caret | per-char opacity set; caret element |
| scramble / decode（スクランブル、スクランブル解読） | random glyphs resolve into the real word | per-char text swap from a fixed seeded glyph list |
| word swap slot（ワード切り替えスロット、縦ロールで単語切替） | one word in a sentence rolls to the next option | vertical stack in a masked slot, y steps |
| odometer digits（オドメーター、オドメーター桁ロール） | each digit column rolls like a mechanical counter | per-digit column of 0-9, masked, y tween |
| count-up（カウントアップ） | a number climbs to its value | tween an object, write rounded value per frame |
| marker highlight（マーカーハイライト、マーカー強調） | a colour band sweeps behind a word | pseudo-element scaleX 0 -> 1 from the left |
| underline draw（アンダーライン描画、下線ドロー） | a stroke draws under the word | SVG path `stroke-dashoffset` |
| outline-to-fill（縁取りから塗りへ、輪郭→塗りスイープ） | hollow outlined letters fill with colour | `-webkit-text-stroke` + fill clip or opacity layer |
| gradient sweep text（グラデーションスイープ、シャイン・スイープ） | a light band travels across the letters | `background-clip:text`, animate background-position |
| echo stack（エコースタック、エコートレイル字幕） | the word repeats in fading copies behind itself | duplicated layers offset in y/z, decreasing opacity |
| karaoke highlight（カラオケ風ハイライト、カラオケ塗り） | words brighten in reading order | colour/opacity per word on a stagger |
| kinetic lockup（キネティックロックアップ） | words of a line fly in from different directions and lock into a block | per-word from-vectors, shared end time |
| text as window（文字の窓抜き、テクスチャ/動画の流し込み、文字窓ズーム） | giant type acts as a mask revealing imagery/UI inside it | `background-clip:text` or SVG mask with text |

## Transitions (between beats)

| Name | Looks like | Built with |
| --- | --- | --- |
| hard cut on hit（ハードカット、拍で切る、hard cut） | instant change on a beat, no dissolve | `tl.set` visibility at the cut |
| match cut（マッチカット） | the next beat's shape appears exactly where the last one was | align geometry of both sides at the cut |
| carrier handoff（キャリーハンドオフ） | one object keeps moving across the cut and becomes part of the next beat | same element (or aligned twin) continues its tween |
| shared-element morph（共有要素モーフ） | a card grows into a full page / a button becomes a panel | FLIP: tween position, size, radius between two layouts |
| zoom-through（ズームスルー、scale-through） | camera pushes through the outgoing beat into the next | scale up + blur on exit, incoming scales from 0.8 |
| inverse zoom / arrival（逆ズーム、アライバル） | the next beat arrives oversized and settles back | incoming scale 1.25 -> 1, outgoing shrinks |
| dolly into screen（画面へ飛び込む） | camera flies into a device screen, which becomes the frame | scale the device until its screen fills the canvas, swap |
| pull-back reveal（引きで見せる） | a close detail pulls back to reveal the whole | start scaled 3-5x on a detail, tween to 1 |
| whip pan（ウィップパン、ウィップ、急な振り、whip） | very fast sideways travel with streaked blur | x travel + directional blur (SVG feGaussianBlur x only) |
| clip-path wipe（クリップパスワイプ、ワイプ、linear wipe、インセット・クリップ、inset、マスクワイプ） | a hard-edged shape sweeps the new beat in | `clip-path: inset()/polygon()` tween |
| iris / circle reveal（アイリス、丸く開く、アイリスオープン、アイリス円形リビール） | a circle opens from a point (often a click) | `clip-path: circle(0 -> 150%)` |
| light wipe（ライトワイプ） | a band of light sweeps and leaves the new beat behind it | bright gradient bar tweened across, swap under it |
| glow wash（グローウォッシュ） | a bloom rises to near-white, beat swaps under it | full-frame radial white overlay opacity up/down |
| rack focus（ラックフォーカス） | the scene defocuses, swaps, refocuses | wrapper blur spike, swap at peak |
| card flip（カードフリップ、3Dフリップ、3D card flip） | a surface turns over and its back is the next beat | `rotateY(180deg)`, `backface-visibility` |
| fold / unfold（折りたたみ） | a panel folds along a crease into the next shape | two halves with `rotateX` on a shared edge |
| shutter slices（シャッタースライス） | the frame splits into strips that slide away | N strips with staggered x/y |
| push stack（プッシュスタック） | the new beat slides over the old like a card on a pile | incoming y from 100%, old scales to 0.94 and dims |
| split-screen expand（分割拡大） | a divider opens, one side grows to fill the frame | width/clip tween on two panes |
| dither / pixel dissolve（ピクセルディゾルブ） | the image breaks into pixels and rebuilds | canvas or SVG pattern mask, seeded |
| ink bleed（インクブリード、インクリビール） | a wash spreads from a point with a soft ragged edge and floods the frame; the next beat is under it | a growing blurred shape through a fixed-seed displacement mask, scale tween, swap at full cover |
| brush wipe（ブラシワイプ） | one broad brush stroke sweeps across and leaves the next beat behind it | reveal mask along a thick stroked path (`stroke-dashoffset` on the mask), ragged edge by displacement |

## Camera

| Name | Looks like | Built with |
| --- | --- | --- |
| push-in / pull-out（プッシュイン、プルアウト、ドリーイン、push in / dolly in、pull out） | slow move toward/away from the subject | scale on a camera wrapper |
| truck / pedestal（トラック、ペデスタル、横移動、上下移動） | sideways / vertical travel over a wide layout | x/y on a camera wrapper over an oversized stage |
| orbit（オービット、ターンテーブル、turntable、周回） | camera circles an object in 3D | `rotateY` on the object inside a `perspective` parent |
| snap / crash zoom（クラッシュズーム） | abrupt fast zoom onto a detail | short scale tween, expo.in-out |
| parallax layers（視差、パララックス、パララックスレイヤー） | foreground, midground, background move at different rates | same tween, different distances per layer |
| infinite canvas pan（無限キャンバスパン） | camera travels across one huge board of UI and text | one large stage translated through keyed positions |
| tilt-shift（ティルトシフト） | top and bottom blurred, middle sharp; looks miniature | gradient-masked blurred copies or backdrop-filter bands |
| dutch tilt（ダッチアングル） | slightly rotated frame for energy | small rotate on the camera wrapper |
| focus follow（フォーカスフォロー） | depth of field shifts to whatever becomes important | per-layer blur tweens |
| camera shake（カメラシェイク、衝撃のシェイク、screen shake on hit） | a short jolt after an impact that dies away | seeded list of x/y/rotate offsets on the camera wrapper, amplitude decaying over 0.3-0.6 s |

## Character and physical motion

How things and characters move as if they had weight, joints and material.
Joint-level entries (walk cycle, blink, follow-through of a tail) need a
character built from separate parts: your own drawn shapes or supplied part
files. Supplied whole-pose art moves by pose swaps and whole-body transforms
only; a walk is then a swap between approved walk poses over a sliding ground.

| Name | Looks like | Built with |
| --- | --- | --- |
| timing contrast（緩急、タイミング(重さ)） | the same move reads heavy when slow-in, light when snappy; a hold makes the next move land | duration and ease choice per move; a short hold before a fast move |
| spring settle（バネの収まり） | the object overshoots and settles in shrinking swings | `elastic.out(amplitude, period)` or a damped keyframe list; a drawn coil is an SVG zig-zag scaled in y with `vector-effect: non-scaling-stroke` |
| squash and stretch（スカッシュ＆ストレッチ、スクワッシュ＆ストレッチ） | stretched along its path while falling, flat only while touching the floor, leaves stretched, round at the top | scaleX/scaleY with `transform-origin` at the contact point, width x height kept near constant; one `fromTo` per phase so seeking in any order gives the same frame |
| anticipation（予備動作、予備動作(アンティシペーション)） | a small move the opposite way just before the main action | a short reverse tween before the main one |
| follow-through / lag（フォロースルー、しっぽ・髪のフォロースルー、tail follow-through、フォロースルー／オーバーラップ） | hair, tails, cloth and chained parts arrive after the body and swing past its stop | the same rotation on each link with a growing delay and a small overshoot |
| jointed walk cycle（ウォークサイクル、歩き、walk cycle） | legs swing from the hip, the knee folds on the forward swing, the body bobs twice per stride, arms swing against the legs | nested limbs with `transform-origin` at each joint; thigh +-25-30 deg per stride, the knee folds so the foot trails behind (away from the facing direction); finite repeats; the ground or background slides under a walker held in frame |
| blink and mouth flap（まばたき、口パク、blink） | eyes shut for 2-4 frames at uneven intervals; a loose mouth open/close on spoken syllables | eye scaleY to ~0.1 and back; a mouth-shape swap on a list of times. Loose flapping, not lip sync |
| line draw and retract（線の描画と引き戻し） | a line draws itself, loops, then pulls back into its own tip | `stroke-dasharray` + `stroke-dashoffset` forward, then continue the offset past the length so the tail chases the head |
| page turn（ページめくり） | a page lifts, turns over the spine under a travelling shadow and shows its back | page with two faces (`backface-visibility: hidden`, back face `rotateY(180deg)`), `rotateY` on the spine edge inside `perspective`; a shade overlay peaks at 90 deg. Stacked faces trip the layout overlap audit: mark only the page-number/text blocks `data-layout-allow-overlap` |
| seamless loop（シームレスループ、継ぎ目のないループ） | the last frame matches the first, so it can repeat | every tween returns to its start or travels a whole period; finite repeat count |
| boil（ボイル、ラインボイル、線の震え、line boil） | a drawn line redraws slightly every few frames, alive like hand animation | swap between 2-3 fixed displacement seeds on steps of 2-3 frames |
| animate on twos（2コマ打ち、1 コマ打ち・2 コマ打ち・3 コマ打ち） | the motion updates every other frame, reading as hand-drawn or stop motion | `steps()` ease, or time rounded to 1/12 s |
| limited-animation hold（リミテッドアニメの止め） | a strong pose held still for a beat while only hair, eyes, a mouth or one prop moves; the energy sits in a few fast changes | a pose swap followed by a hold; secondary parts on `steps()`; the hold is a timed gap, not a frozen render |
| smear frame（スミア） | one stretched in-between that sells a fast swing or dash | on your own drawn shapes: one frame of a stretched shape along the path; on supplied whole-pose art: a drawn streak layer behind it for 1-2 frames, never a deformed cast |
| impact frame（インパクトフレーム） | at a hit, one to three frames flash to a stark two-tone or inverted palette with radial speed lines, then snap back | a full-frame overlay layer (flat colour plus `mix-blend-mode: difference` or a drawn two-tone plate) and an SVG radial line burst, each held 1-3 frames on a seeded schedule; never more than 3 flashes in any one second, and no saturated red full-frame flash |

## Effects

| Name | Looks like | Built with |
| --- | --- | --- |
| bloom / glow（ブルーム、グロー） | light bleeding around bright elements | blurred duplicate behind, `mix-blend-mode: screen` |
| light leak（ライトリーク） | warm/cool soft light spills across a corner | large blurred gradient blobs drifting |
| light field（ライトフィールド） | soft coloured glows living in the background | 2-4 radial gradients, slow drift |
| lens streak（レンズストリーク） | a thin horizontal flare line across a highlight | thin blurred bar, screen blend |
| sheen / shimmer（シーン、光沢のきらめき） | a diagonal gloss passes over a surface | angled gradient masked to the element, x tween |
| glassmorphism（グラスモーフィズム） | frosted translucent panels over colour | `backdrop-filter: blur()`, 1px light border |
| shadow stack（シャドウスタック） | contact + ambient + tinted shadows under objects | multiple `box-shadow` layers |
| reflection floor（反射する床） | objects mirrored faintly on a glossy floor | flipped copy with gradient mask |
| motion blur（モーションブラー、subframe motion blur） | streak along fast movement | directional blur only while moving |
| depth of field（被写界深度） | far things soft, near things sharp | per-layer blur |
| film grain（フィルムグレイン） | fine moving noise over everything | SVG `feTurbulence` or seeded noise overlay, low opacity |
| chromatic aberration（色収差、色収差分離） | colour fringe on fast moves | RGB-split copies offset a few px |
| pulse ring（パルスリング） | a ring expands from a tap or node | circle scale 1 -> 3, opacity 1 -> 0 |
| particle burst（パーティクルバースト） | small shapes spray out from an impact | pre-placed seeded particles, radial tweens |
| sparkle（スパークル、きらめき、twinkle sparkles） | brief star glints on a success moment | small scale/rotate pops |
| spotlight（スポットライト） | a soft pool of light follows the focus | radial gradient positioned on the subject |
| halftone / dither（ハーフトーン、ディザ） | printed dot or pixel texture | pattern fill or SVG filter |
| vignette（ビネット、周辺減光、vignette breathe、呼吸する周辺減光） | edges darkened to hold the eye in the centre | radial gradient overlay |
| noise gradient / mesh gradient（ノイズグラデーション、メッシュグラデーション） | rich multi-colour soft background | several blurred blobs, optional grain |

## Components (drawn UI and graphics)

| Name | Looks like | Built with |
| --- | --- | --- |
| phone frame（スマホフレーム） | realistic device with bezel, notch, screen content | rounded rects, inner screen, gloss |
| browser window（ブラウザウィンドウ） | chrome with traffic lights, tabs, URL bar | flex header + content area |
| URL / domain bar（URLバー） | a pill showing a web address with a lock | pill, icon, text |
| one-page site mock（ワンページサイトのモック） | hero, sections, menu, hours, map, footer with real-looking content | stacked sections, real words and numbers |
| bento grid（ベントーグリッド） | tiles of different sizes each showing a feature | CSS grid, varied spans |
| floating UI cards（浮遊UIカード） | pieces of UI detached and floating in depth | absolutely positioned cards with z/shadow |
| exploded view（分解ビュー） | an interface separated into layers in 3D | same layers offset in `translateZ` |
| wall of screens（スクリーンの壁） | many screens tiled, camera travels across | grid of mini mocks |
| notification toast stack（通知トーストの積み重ね） | notifications dropping in and stacking | stacked cards, y/scale offsets |
| chat bubbles（チャット吹き出し） | a conversation building up | alternating bubbles, typing dots |
| form with caret（キャレット付きフォーム） | fields filling themselves, focus ring moving | inputs as divs, per-char reveal |
| button press（ボタンを押す） | a button squashes, changes state, ripples | scale 0.96 -> 1, colour change, ring |
| oversized cursor（大きなカーソル） | a big pointer that travels and clicks | SVG pointer, eased path, click squash |
| toggle / switch（トグルスイッチ） | a switch flips on | knob x tween, track colour |
| checklist with ticks（チェックリスト） | items tick off one by one | SVG check path draw per item |
| progress bar / ring（プログレスバー、リング） | fills to a value | scaleX or `stroke-dashoffset` |
| stepper / timeline（ステッパー、タイムライン） | numbered steps connected by a line that fills | nodes + line fill |
| calendar strip（カレンダーストリップ） | days in a row, a range highlighting | row of day cells, fill sweep |
| price tag（値札） | a hanging tag with an amount | shape + string, pendulum rotation |
| pricing card（料金プランカード） | plan card with price, period, inclusions | card with large numeral |
| receipt / invoice（レシート、請求書） | a slip printing line by line | clip reveal downward |
| stat card（数値カード、大きな数字のカード） | a big number with a label | count-up numeral |
| badge / chip / pill（バッジ、チップ） | small labelled capsules | rounded spans |
| avatar stack（アバタースタック） | overlapping round portraits | negative margins, stagger in |
| map + pin + route（地図とピンとルート、地図にピンが落ちる） | a map with a dropping pin and a path drawing | SVG shapes, pin drop, path draw |
| search bar with typed query（検索バーに入力） | a query types, results drop in | caret typing, list stagger |
| tooltip / callout（ツールチップ、コールアウト） | a label with a leader line pointing at a detail | line draw + label pop |
| hand-drawn annotation（手描きの書き込み、手描き丸囲み） | circles and arrows scribbled on the UI | SVG path draw, rough stroke |
| marquee / ticker（マーキー、流れる帯、ティッカー、無限マーキー） | a line of text or logos scrolling endlessly | duplicated row, linear x |
| carousel（カルーセル） | cards sliding past a focus position | row x steps, scale on centre |
| sticky note（付箋） | a paper note slapped on | rotate + scale pop with shadow |
| QR / scan frame（QRスキャン枠） | a scan frame locking onto a code | corner brackets tighten |
| logo lockup reveal（ロゴロックアップの登場） | the mark resolves with the wordmark | the supplied file, opacity/position only when the brand forbids effects |

## Compositions

| Name | Looks like |
| --- | --- |
| full-bleed hero（全面ヒーロー） | one object or word fills the whole frame, edges cropped |
| oversized type crop（巨大文字のトリミング） | letters bigger than the frame, only part visible |
| centre stack（中央積み） | headline, object, sub-line stacked on the centre axis |
| split layout（分割レイアウト） | frame divided into two zones (text / object), often diagonal |
| over-the-shoulder device（肩越しのデバイス） | device held close to camera, content readable, background soft |
| macro close-up（マクロクローズアップ） | extreme close view of one UI detail |
| top-down flat lay（真上のフラットレイ） | objects arranged on a surface seen from above |
| isometric（アイソメトリック） | 3D-looking layout without perspective convergence |
| tunnel / corridor（トンネル、回廊） | cards lining the walls of a corridor the camera travels through |
| orbit around headline（見出しを周回） | objects circling a central line of text |
| collage（コラージュ） | many cut-out elements overlapping at different scales |
| screen within screen（画面の中の画面） | a device whose screen shows another device or the film itself |
| before / after split（ビフォーアフター分割） | two states side by side with a moving divider |

## Drawn looks

The rendering language of the world you draw: backgrounds, props, type and
your own drawn shapes. Name one in the look-in-words; the leaf's own `style`
reference, when chosen, is the fuller brief. A look never re-renders supplied
art, a cast or a logo: apply a look's filters and textures to world layers,
never to a wrapper that contains supplied art. Entries marked 3D need
`graphics: three-webgl2` where the leaf offers it; elsewhere build the 2.5D
imitation named in the same row.

### Hand-drawn and paper

| Name | Looks like | Built with |
| --- | --- | --- |
| risograph（リソグラフ） | two or three flat spot inks overprinted, darker where they overlap, halftone dots, plates slightly out of register, paper grain | one layer per ink with `mix-blend-mode: multiply`; dots as a `radial-gradient` with `background-size`; a few px offset per plate; fixed-seed `feTurbulence` grain (see halftone / dither) |
| origami（折り紙） | everything folded from paper: triangle facets and creases, each facet one tone lighter or darker than its neighbour, soft shadows | SVG polygons in 2-3 tones of one hue; unfolding = facets rotating on their shared crease (`transform-origin` on the edge) |
| sumi-ink brush（墨の筆） | black ink on off-white paper; strokes swell and thin with pressure, dry-brush streaks at the tail, soft grey wash hills | a filled variable-width stroke shape revealed by a mask path drawn along its centreline (`stroke-dashoffset` on the mask, slow-fast-slow ease; a plain stroke keeps one width); fixed-seed `feTurbulence` + `feDisplacementMap` for the ragged edge; a thinner offset stroke through a grain mask for dry brush; washes as blurred low-opacity shapes; ink bleed / brush wipe between beats |
| pencil sketch（鉛筆スケッチ） | graphite on white: construction lines, hatching for shade, smudged edges; objects look drawn, not rendered | shapes made of many thin hatch paths; draw-on per stroke group; low-scale displacement for hand wobble; paper-tooth overlay |
| crayon（クレヨン） | waxy thick strokes, paper tooth showing through, scribble fills that miss the outline, wobbly child-like shapes | fills as dense zig-zag strokes clipped to the shape; coarse grain mask on fill and outline; boil |
| watercolor（水彩、水彩のにじみ、watercolor wash） | soft pigment pools with darker dried edges, colours bleeding into each other, white paper kept for highlights | layered blurred shapes with `mix-blend-mode: multiply`; the same shape stroked and less blurred for the edge; fixed-seed noise mask for blooms; bleed-in = slow scale/opacity spread |
| paper cut-out (kirie)（切り絵、ストップモーション、paper cut / stop-motion） | silhouettes cut from stacked coloured paper, a flat colour per layer with a small shadow, lit windows punched through | flat SVG layers, one drop shadow per layer, parallax by layer |
| chalkboard（黒板） | chalk lines and handwriting on dark green slate, dusty edges, faint ghosts of erased writing | stroked paths through a grain mask on a dark green surface; write-on via `stroke-dashoffset`; ghosts as low-opacity blurred copies |
| one-line drawing（一筆書き） | a whole object drawn as one continuous line, a few flat colour blobs offset behind it | a single path drawn by `stroke-dashoffset`; blobs as soft shapes that fade in after the line passes |

### Anime

| Name | Looks like | Built with |
| --- | --- | --- |
| cel anime（セルアニメ） | TV-style 2D: flat base fills, one hard-edged shadow tone per colour from one light direction, an even dark line, skies as a flat colour or one clean gradient, small hard highlights | SVG shapes with a base fill and a separate hard-edged shadow path per form; `stroke` at the cast's line weight; no blur or soft gradients on drawn forms; motion on twos with limited-animation holds |
| painted anime backdrop（アニメの背景美術） | backgrounds painted with visible brush texture and atmospheric depth behind crisp cel characters, natural light, wind in grass and cloud | layered SVG or supplied painted plates with a fixed-seed brush-texture mask; haze as a low-opacity light layer per depth plane; parallax by plane; the cast layer never takes the paint texture |

### Graphic

| Name | Looks like | Built with |
| --- | --- | --- |
| flat Bauhaus（フラットなバウハウス） | red, blue, yellow and black on cream: circles, half discs, bars, one strong diagonal | SVG primitives; motion as half discs rotating and bars sliding on a grid |
| isometric（アイソメトリック） | see Compositions: isometric; blocks with a light top and two darker sides, things travel along the axes | SVG on an isometric grid, or one `rotateX(60deg) rotateZ(45deg)` plane |
| infographic（インフォグラフィック） | calm charts: donut, flowing bands (sankey), dot matrix, labelled axes, one accent colour | SVG paths; donut arcs by `stroke-dashoffset`; labels by count-up |
| blueprint（青写真） | white hairlines on blue over a fine grid, dimension arrows, section marks, numbered callouts | grid from repeating linear gradients; line draw per part; callouts as tooltip / callout |
| stained glass（ステンドグラス） | jewel-coloured panes between thick dark lead lines, light glowing through | SVG polygons with a thick dark stroke, an inner radial glow, a sheen / shimmer passing over |
| tile mosaic（タイルモザイク） | the image built from small square tiles with grout gaps and slightly uneven colours | a grid of small rects coloured from a source shape, fixed-seed jitter; reveal staggered from the centre |
| silhouette（シルエット） | solid dark shapes against a warm gradient sky; smoke and steam as soft shapes | flat dark SVG shapes over a gradient, parallax layers |
| stark graphic（ストイックなグラフィック） | two or three flat colours (black, white, one accent), places as bold geometric planes and repeated forms, extreme angles, wide empty fields, full-frame colour cards between scenes | flat SVG fills with no blur, gradient or texture; long holds broken by one snap move; hard cuts on the beat; cards as full-frame rects; never more than 3 flashes in any one second, and no saturated red full-frame flash |

### Screen and retro

| Name | Looks like | Built with |
| --- | --- | --- |
| CRT / VHS（ブラウン管、VHS、走査線、CRT scanlines） | curved glass, scanlines, colour bleed, a rolling tracking band | repeating-gradient scanlines; rounded inner vignette for the glass; chromatic aberration; a band tweened down the frame |
| pixel art（ドット絵） | a low-resolution grid with hard edges and a small palette | draw small and scale with `image-rendering: pixelated`, or `shape-rendering: crispEdges` rects; motion in whole-pixel steps |
| ASCII terminal（ASCIIターミナル） | the subject drawn with characters in a monospace grid under a command prompt | a `<pre>` grid whose characters come from a brightness ramp computed per frame from a deterministic shape; typewriter + caret for the prompt |
| glitch（グリッチ、グリッチイン） | slices of the frame jump sideways, colour channels split, blocks flicker | `clip-path` slices offset on a seeded schedule; RGB-split copies; each burst held 2-6 frames |
| neon sign（ネオンサイン） | glowing tubes on a dark wall, a flicker on ignition, a coloured halo on the wall | stroked text/paths with layered blurred copies (bloom / glow); seeded opacity steps for the flicker; radial gradient halo |

### Solid (3D)

| Name | Looks like | Built with |
| --- | --- | --- |
| low-poly 3D（ローポリ3D） | faceted, flat-shaded meshes; bright toy landscapes | 3D: flat-shaded procedural geometry; 2.5D: SVG triangles in three tones |
| toon 3D（トゥーン3D） | 3D forms with two-tone cel shading and an outline | 3D: toon material plus an inverted-hull outline; 2.5D: flat shapes with one hard shadow shape |
| clay stop-motion（クレイアニメ） | soft rounded forms with a handled, fingerprinted surface, moving on twos | 3D: rough material with fixed noise; 2.5D: soft gradients and grain; animate on twos |
| product shot（プロダクトショット） | a real product on a seamless sweep, soft key light, contact shadow, slow turn | only from supplied product photos or renders, never invented packaging; shadow stack, reflection floor; 3D turntable only for a procedural stand-in shape |

### Generative, math and data

| Name | Looks like | Built with |
| --- | --- | --- |
| flow field（フローフィールド） | thousands of fine lines streaming across the frame and bending around an obstacle | lines precomputed from a field (potential flow around a circle, psi = y(1 - R^2/r^2), or fixed-seed noise angles); motion by `stroke-dashoffset` along each line |
| particles（パーティクル、粒が集まって形になる、particles coalesce、パーティクル文字） | a shape made of fine grains that disperses and re-forms into another shape | canvas or SVG points with seeded starts, each grain tweening between two samplings of the shapes |
| marbling (suminagashi)（マーブリング、墨流し） | concentric ink rings on water, pulled into swirls | closed rings around seeded centres, warped by fixed-seed displacement whose scale tweens |
| math diagram（数式ダイアグラム） | a unit circle whose turning radius draws y = sin theta beside it, with live values | SVG; one angle tween drives the radius end, a growing path and the written number |
| transit map（路線図） | coloured lines over a faint street map, a station marker, the camera closing on one station | lines by `stroke-dashoffset`; map + pin + route; push-in |
| kinetic typography（キネティックタイポグラフィ） | one giant character with small vertical kana beside it, letters that snap, blur and settle | kinetic lockup, scale punch, blur-in, outline-to-fill |

## Film structures

The shape of a whole piece, named in the storyboard's intent.

| Name | Looks like |
| --- | --- |
| product reveal（プロダクトリビール） | teaser detail, build-up, full reveal on the drop, name and one line, end card |
| showcase reel (PV)（ショーケースリール） | the subject's own cover in the first frame, a tour of its best moments, a brand end card |
| series opening（シリーズオープニング） | world, each character or feature in one signature glimpse, a held key visual with room for the title |
| sizzle montage（シズルモンタージュ） | fast cuts of many moments on the beat, energy rising to one closing line |
| before / after story（ビフォーアフターストーリー） | the problem state held long enough to feel, a turn, the resolved state |
| day in the life（一日の流れ） | one person or place across a sequence of moments in time order |
| countdown / list（カウントダウン、リスト） | numbered items, each with one hero moment, the last one biggest |
| logo sting（ロゴスティング） | a short build that resolves into the mark and holds |

## Visual metaphors

An idea shown as a physical thing the viewer already understands, instead
of a word on a card. Name the idea and the image together ("bottleneck as
funnel"); the image can be drawn in any style and combined with any entry
above.

| Idea | Image | Looks like | Built with |
| --- | --- | --- | --- |
| bottleneck（ボトルネック） | funnel / hourglass neck | many items crowd the wide mouth and trickle through one at a time | dots on paths converging to one point, staggered release |
| filtering / selection（絞り込み、選別） | sieve | a stream of items falls, only the right ones pass, the rest bounce away | two particle groups, one passes a mesh line, one deflects |
| growth（成長） | sprout | a stem rises, leaves unfold, the plant reaches the number | SVG stem path draw, leaf scale from the node, count-up at the tip |
| compounding（複利） | snowball | a small ball rolls downhill and swells with each turn | scale tied to x, rotation, trail |
| scale / replication（拡大、複製） | tile cloning | one unit copies itself outward until it fills a grid | one element, staggered clones from its position |
| sync / integration（同期、連携） | meshing gears | separate gears slide together, teeth catch, all turn as one | SVG gears, rotation ratios by tooth count, start on contact |
| connection / network（つながり、ネットワーク） | nodes and threads | points appear, lines draw between them, a pulse travels the links | node pop, path draw, dot along path |
| handoff / trust（引き継ぎ、信頼） | baton pass | an object passes from one hand or lane to the next without stopping | carrier handoff between two tracks |
| pipeline / flow（パイプライン、流れ） | conveyor or pipe | items ride through stations and change at each one | items on a path, state swap at station x |
| transformation（変身、変換） | machine or box | a rough shape goes in one side, a finished one comes out | occluder box, swap the shape while hidden |
| automation（自動化） | repeating arm | a mechanism does the same task again and again without a hand | looped sub-timeline repeated on the master clock |
| chaos to order（混沌から秩序へ） | snap to grid | scattered, rotated pieces fly into a clean aligned layout | seeded start positions and angles, shared end layout |
| simplification（シンプル化） | untangling | a knotted line pulls straight | SVG path morph from a tangled path to a straight one |
| complexity / clutter（複雑さ、散らかり） | pile or tangle | items overlap and keep arriving until the frame is crowded | growing stack with jitter-free seeded offsets |
| overload（過負荷） | overflow | a container fills past its rim and spills | fill level tween, spill particles past the edge |
| accumulation / saving（蓄積、貯蓄） | filling jar or stack | coins or blocks drop in and the level climbs | stacked drops with settle, level line |
| waiting / delay（待ち、遅延） | queue | a line of items shuffles forward one step at a time | row x steps with holds between |
| speed（スピード） | streak | the subject leaves speed lines and a blurred trail | lines behind the motion vector, directional blur |
| breakthrough（ブレイクスルー） | wall cracking | a barrier fractures and the subject bursts through | crack path draw, pre-cut shards pushed outward |
| protection / security（保護、セキュリティ） | shield or lock | a shell closes around the subject; attacks glance off | shield scale-in, deflected dots, lock shackle drop |
| isolation / sandbox（隔離、サンドボックス） | glass bubble | the subject sits inside a clear sphere; outside things bounce off | circle with sheen, collisions reflect at its radius |
| unlock / access（解錠、アクセス） | key and door | a key turns, a door or lid opens onto what was inside | key rotate, door `rotateY` on its hinge |
| dependency / chain reaction（依存、連鎖反応） | dominoes | one tile tips and knocks the rest down in sequence | per-tile rotate with stagger from the pivot edge |
| layers / abstraction（レイヤー、抽象化） | stacked plates | thin layers separate vertically, each labelled | exploded view of flat panels in `translateZ` or y |
| decision / branching（意思決定、分岐） | forked path | a road splits; one branch lights up and the traveller takes it | path draw, highlight one branch, dot along it |
| journey / progress（旅路、進捗） | road with milestones | a traveller moves past markers toward a goal | camera truck along a path, markers pop as passed |
| feedback loop（フィードバックループ） | circular track | a pulse runs round a loop and changes something each lap | dot on a closed path, state change per lap |
| balance / trade-off（バランス、トレードオフ） | scale | two pans tip as weight moves from one side to the other | beam rotation from summed weights, pans hang level |
| memory / cache（記憶、キャッシュ） | shelf or drawer | a thing is put away, later pulled out instantly instead of fetched far | drawer x slide, second retrieval much shorter |
| fit / solution（適合、解決策） | puzzle piece | the missing piece turns and clicks into the gap | rotate + translate into the slot, small settle |
| signal from noise（ノイズから信号へ） | tuning wave | a jagged waveform smooths into a clean wave | SVG path morph between noisy and clean |
| clarity / focus（明快さ、フォーカス） | lens | a blurry scene sharpens where a lens passes | masked sharp layer under a moving circle |
| spark / idea（ひらめき、アイデア） | ignition | a small point flashes and lights up the shapes around it | pulse ring, bloom, radial stagger of lit elements |
