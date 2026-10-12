# Motion and component vocabulary: video builds

How each entry of [../core.md](../core.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

A look or effect never re-renders supplied art, a cast or a logo; full-frame flashes stay at most three in any one second, with no saturated red full-frame flash.

## Text animations

| Name | Built with |
| --- | --- |
| split-text stagger（スタッガー） | split into spans; stagger 0.02-0.08 s on y/opacity |
| mask reveal (line rise)（マスクリビール、行マスク・せり上がり） | line wrapper `overflow:hidden`; inner span y 110% -> 0 (x for vertical columns) |
| blur-in / focus pull（ブラーイン、文字ブラーイン） | `filter: blur()` 12-20px -> 0 with y or scale |
| scale punch（スケールパンチ） | scale 1.3-1.6 -> 1, expo/back ease |
| tracking-in（字間が縮まって入る、トラッキング・エクスパンド、トラッキング収束） | letter-spacing 0.5em -> normal, opacity |
| typewriter + caret（タイプライター、カーソル点滅タイプ） | per-char opacity set; caret element |
| scramble / decode（スクランブル、スクランブル解読） | per-char text swap from a fixed seeded glyph list |
| word swap slot（ワード切り替えスロット、縦ロールで単語切替） | vertical stack in a masked slot, y steps |
| odometer digits（オドメーター、オドメーター桁ロール） | per-digit column of 0-9, masked, y tween |
| count-up（カウントアップ） | tween an object, write rounded value per frame |
| marker highlight（マーカーハイライト、マーカー強調） | pseudo-element scaleX 0 -> 1 from the left |
| underline draw（アンダーライン描画、下線ドロー） | SVG path `stroke-dashoffset` |
| outline-to-fill（縁取りから塗りへ、輪郭→塗りスイープ） | `-webkit-text-stroke` + fill clip or opacity layer |
| gradient sweep text（グラデーションスイープ、シャイン・スイープ） | `background-clip:text`, animate background-position |
| echo stack（エコースタック、エコートレイル字幕） | duplicated layers offset in y/z, decreasing opacity |
| karaoke highlight（カラオケ風ハイライト、カラオケ塗り） | colour/opacity per word on a stagger |
| kinetic lockup（キネティックロックアップ） | per-word from-vectors, shared end time |
| text as window（文字の窓抜き、テクスチャ/動画の流し込み、文字窓ズーム） | `background-clip:text` or SVG mask with text |

## Transitions (between beats)

| Name | Built with |
| --- | --- |
| hard cut on hit（ハードカット、拍で切る、hard cut） | `tl.set` visibility at the cut |
| crossfade / dissolve（クロスフェード、ディゾルブ） | two full-frame layers on one shared overlap: outgoing opacity down and incoming opacity up with a linear ease, both starting and ending together, the outgoing layer hidden once the incoming is solid |
| blur crossfade（ブラー・クロスフェード） | blur filter on each scene layer rising then falling on `sine.inOut`, symmetric around the swap, with an opacity crossfade layered on top; the blur sits on drawn scene layers and the swap lands at its peak |
| push / slide（プッシュ、押し出し） | both layers translated on x by one frame width in the same direction on `power2.inOut`, the incoming starting just off-frame; one shared tween drives both so the seam stays closed, the outgoing layer hidden at the end |
| match cut（マッチカット） | align geometry of both sides at the cut |
| carrier handoff（キャリーハンドオフ） | same element (or aligned twin) continues its tween |
| shared-element morph（共有要素モーフ） | FLIP: tween position, size, radius between two layouts |
| zoom-through（ズームスルー、scale-through） | scale up + blur on exit, incoming scales from 0.8 |
| inverse zoom / arrival（逆ズーム、アライバル） | incoming scale 1.25 -> 1, outgoing shrinks |
| dolly into screen（画面へ飛び込む） | scale the device until its screen fills the canvas, swap |
| pull-back reveal（引きで見せる） | start scaled 3-5x on a detail, tween to 1 |
| whip pan（ウィップパン、ウィップ、急な振り、whip） | x travel + directional blur (SVG feGaussianBlur x only) |
| clip-path wipe（クリップパスワイプ、ワイプ、linear wipe、インセット・クリップ、inset、マスクワイプ） | `clip-path: inset()/polygon()` tween |
| clock wipe（クロックワイプ） | conic-gradient or wedge mask on the incoming layer whose angle tweens from nothing to a full turn on `sine.inOut`, starting at twelve o'clock; an optional thin line rides the leading edge |
| iris / circle reveal（アイリス、丸く開く、アイリスオープン、アイリス円形リビール） | `clip-path: circle(0 -> 150%)` |
| shaped iris（形のアイリス、ハート、鍵穴） | an SVG shape path as the mask on the incoming layer, scaled from the origin point on `power2.in` until it overshoots the farthest corner so no edge remains, centred on the subject |
| colour flood（カラーフラッド） | a full-frame colour disc or rect scaled out from the origin on an ease-in, the swap on the frame it fully covers, then pulled back on an ease-out; the reach passes the farthest corner, the colour is the brand accent |
| slats / blinds（スラット、ブラインド） | a row of bars over the next beat, each `scaleY` or `rotateX` to nothing on `power2.out`, starts staggered from one side by a small constant offset; a moderate bar count keeps it from flickering, bars removed at the end |
| staggered blocks（ブロックで覆う） | a grid of rects with scale or opacity tweens whose start offsets follow distance along one direction (light seeded jitter allowed), the swap at full cover, then the clearing in the same order on `power2.inOut` |
| light wipe（ライトワイプ） | bright gradient bar tweened across, swap under it |
| glow wash（グローウォッシュ） | full-frame radial white overlay opacity up/down |
| rack focus（ラックフォーカス） | wrapper blur spike, swap at peak |
| card flip（カードフリップ、3Dフリップ、3D card flip） | `rotateY(180deg)`, `backface-visibility` |
| fold / unfold（折りたたみ） | two halves with `rotateX` on a shared edge |
| shutter slices（シャッタースライス） | N strips with staggered x/y |
| push stack（プッシュスタック） | incoming y from 100%, old scales to 0.94 and dims |
| split-screen expand（分割拡大） | width/clip tween on two panes |
| dither / pixel dissolve（ピクセルディゾルブ） | canvas or SVG pattern mask, seeded |
| shape-morph bridge（シェイプモーフで橋渡し） | an SVG path morph from path A to path B with equal point counts and aligned start points on `power2.inOut`, fill and position tweened in step; the scene swap hides while the shape covers the frame |
| glitch cut（グリッチ、RGBずれ） | seeded slice offsets through clip-path strips and RGB-split copies on the drawn scene layers, on `steps()` timing, held a few frames either side of the swap and then removed |
| ink bleed（インクブリード、インクリビール） | a growing blurred shape through a fixed-seed displacement mask, scale tween, swap at full cover |
| brush wipe（ブラシワイプ） | reveal mask along a thick stroked path (`stroke-dashoffset` on the mask), ragged edge by displacement |
| letterform mask wipe（文字の中を抜けて次へ） | a heavy glyph as an SVG mask or clip on the incoming layer, scaled on `expo.in` about a point on the letter nearest the next subject, the swap hidden inside it, the mask dropped once it fills the frame |
| gravity drop（グラビティドロップ） | the outgoing layer on top, y tween past the bottom edge on `power2.in` with a small rotate in step; the incoming layer stays still underneath from the start and the old layer is hidden at the end |
| light-streak whip（ライトストリーク・ウィップ） | x travel with directional blur on the scene layers plus a feathered light bar tweened across on `power3.in`, the swap while the bar is over the centre, the bar leaving the frame after |
| J-cut / L-cut（Jカット、Lカット） | the audio clip start or end time offset against the picture cut on the master timeline, the lead shorter than the trail; the offset lives in the audio mix, no visual layer is involved |

## Camera

| Name | Built with |
| --- | --- |
| push-in / pull-out（プッシュイン、プルアウト、ドリーイン、push in / dolly in、pull out） | scale on a camera wrapper |
| truck / pedestal（トラック、ペデスタル、横移動、上下移動） | x/y on a camera wrapper over an oversized stage |
| pan（パン、首振り） | a single shared x offset on every scene layer using `sine.inOut`, possibly a small rotateY within a `perspective` parent on the camera wrapper; blur applied only to quick pans |
| roll（ロール、傾き） | a rotate tween on the camera wrapper, out on `power2.out` then back with a short spring-like settle; the amplitude is slight and the start is timed to the hit |
| zoom (flat)（ズーム、平板） | one uniform scale tween on a single flat layer, or all layers at an equal factor, on `power2.inOut`, with the origin on the point of interest |
| dolly zoom (vertigo)（ドリーズーム、めまい） | the camera wrapper moves forward in z while the background layers scale the opposite way to cancel it, the subject layer held at constant size, on `power2.inOut`, used once at the key moment |
| crane / jib（クレーン、ジブ） | y travel on the camera wrapper with a slight scale and a rotate tilt that compensates the rise, on `power2.inOut`, over a long stretch |
| orbit（オービット、ターンテーブル、turntable、周回） | `rotateY` on the object inside a `perspective` parent |
| handheld drift（手持ち風のゆれ） | seeded noise or a sum of slow sines with different periods on x, y and a very small rotate of the camera wrapper, finite and closing at the end |
| snap / crash zoom（クラッシュズーム） | short scale tween, expo.in-out |
| punch-in on the beat（拍でパンチイン） | scale on the camera wrapper stepped up at each time in the beat list and decaying back on `power2.out`, a larger step for beats after the drop |
| ken burns（ケン・バーンズ） | one image layer with scale and x/y translate tweened on a linear ease across a long span, drift aimed at the subject and zoom kept modest so the image stays sharp |
| parallax layers（視差、パララックス、パララックスレイヤー） | same tween, different distances per layer |
| follow with lookahead（フォロー、先読みで追う） | the camera target eased toward the mover's current position plus its velocity times a short lead, with a spring-like ease on the wrapper's x and y |
| infinite canvas pan（無限キャンバスパン） | one large stage translated through keyed positions |
| tilt-shift（ティルトシフト） | gradient-masked blurred copies or backdrop-filter bands |
| dutch tilt（ダッチアングル） | small rotate on the camera wrapper |
| focus follow（フォーカスフォロー） | per-layer blur tweens |
| camera shake（カメラシェイク、衝撃のシェイク、screen shake on hit） | seeded list of x/y/rotate offsets on the camera wrapper, amplitude decaying over 0.3-0.6 s |

## Sync to sound

| Name | Built with |
| --- | --- |
| SFX cues on the grid（SFXを拍に置く） | cue times snapped to the beat list or to the tween's measured peak, sound onset and visual peak sharing one frame, placed on the picture's own timeline |
| audio bars（オーディオビジュアライザー） | bar heights read from precomputed per-frame band levels, a quick rise on an ease-out and a slower decay, bands laid out left to right |
| sidechain duck（サイドチェイン・ダック） | a scale or brightness dip on the whole scene at each beat time, followed by a quick return on `power2.out`, repeated down the beat list |
| word-locked sync（歌詞・字幕を語に合わせる） | per-word start times taken from timestamps, each word's colour or opacity tween begun at its time, the previous word settling as the next lights |

## Components (drawn UI and graphics)

| Name | Built with |
| --- | --- |
| phone frame（スマホフレーム） | rounded rects, inner screen, gloss |
| browser window（ブラウザウィンドウ） | flex header + content area |
| URL / domain bar（URLバー） | pill, icon, text |
| one-page site mock（ワンページサイトのモック） | stacked sections, real words and numbers |
| bento grid（ベントーグリッド） | CSS grid, varied spans |
| floating UI cards（浮遊UIカード） | absolutely positioned cards with z/shadow |
| exploded view（分解ビュー） | same layers offset in `translateZ` |
| wall of screens（スクリーンの壁） | grid of mini mocks |
| notification toast stack（通知トーストの積み重ね） | stacked cards, y/scale offsets |
| chat bubbles（チャット吹き出し） | alternating bubbles, typing dots |
| form with caret（キャレット付きフォーム） | inputs as divs, per-char reveal |
| button press（ボタン押下） | scale 0.96 -> 1, colour change, ring |
| oversized cursor（大きなカーソル） | SVG pointer, eased path, click squash |
| toggle / switch（トグルスイッチ） | knob x tween, track colour |
| checklist with ticks（チェックリスト） | SVG check path draw per item |
| progress bar / ring（プログレスバー、リング） | scaleX or `stroke-dashoffset` |
| stepper / timeline（ステッパー、タイムライン） | nodes + line fill |
| calendar strip（カレンダーストリップ） | row of day cells, fill sweep |
| price tag（値札） | shape + string, pendulum rotation |
| pricing card（料金プランカード） | card with large numeral |
| receipt / invoice（レシート、請求書） | clip reveal downward |
| stat card（数値カード、大きな数字のカード） | count-up numeral |
| badge / chip / pill（バッジ、チップ） | rounded spans |
| avatar stack（アバタースタック） | negative margins, stagger in |
| map + pin + route（地図とピンとルート、地図にピンが落ちる） | SVG shapes, pin drop, path draw |
| search bar with typed query（検索バーに入力） | caret typing, list stagger |
| tooltip / callout（ツールチップ、コールアウト） | line draw + label pop |
| hand-drawn annotation（手描きの書き込み、手描き丸囲み） | SVG path draw, rough stroke |
| marquee / ticker（マーキー、流れる帯、ティッカー、無限マーキー） | duplicated row, linear x |
| carousel（カルーセル） | row x steps, scale on centre |
| sticky note（付箋） | rotate + scale pop with shadow |
| QR / scan frame（QRスキャン枠） | corner brackets tighten |
| logo lockup reveal（ロゴロックアップの登場） | the supplied file, opacity/position only when the brand forbids effects |

## Visual metaphors

| Idea | Built with |
| --- | --- |
| bottleneck（ボトルネック） | dots on paths converging to one point, staggered release |
| filtering / selection（絞り込み、選別） | two particle groups, one passes a mesh line, one deflects |
| growth（成長） | SVG stem path draw, leaf scale from the node, count-up at the tip |
| compounding（複利） | scale tied to x, rotation, trail |
| scale / replication（拡大、複製） | one element, staggered clones from its position |
| sync / integration（同期、連携） | SVG gears, rotation ratios by tooth count, start on contact |
| connection / network（つながり、ネットワーク） | node pop, path draw, dot along path |
| handoff / trust（引き継ぎ、信頼） | carrier handoff between two tracks |
| pipeline / flow（パイプライン、流れ） | items on a path, state swap at station x |
| transformation（変身、変換） | occluder box, swap the shape while hidden |
| automation（自動化） | looped sub-timeline repeated on the master clock |
| chaos to order（混沌から秩序へ） | seeded start positions and angles, shared end layout |
| simplification（シンプル化） | SVG path morph from a tangled path to a straight one |
| complexity / clutter（複雑さ、散らかり） | growing stack with jitter-free seeded offsets |
| overload（過負荷） | fill level tween, spill particles past the edge |
| accumulation / saving（蓄積、貯蓄） | stacked drops with settle, level line |
| waiting / delay（待ち、遅延） | row x steps with holds between |
| speed（スピード） | lines behind the motion vector, directional blur |
| breakthrough（ブレイクスルー） | crack path draw, pre-cut shards pushed outward |
| protection / security（保護、セキュリティ） | shield scale-in, deflected dots, lock shackle drop |
| isolation / sandbox（隔離、サンドボックス） | circle with sheen, collisions reflect at its radius |
| unlock / access（解錠、アクセス） | key rotate, door `rotateY` on its hinge |
| dependency / chain reaction（依存、連鎖反応） | per-tile rotate with stagger from the pivot edge |
| layers / abstraction（レイヤー、抽象化） | exploded view of flat panels in `translateZ` or y |
| decision / branching（意思決定、分岐） | path draw, highlight one branch, dot along it |
| journey / progress（旅路、進捗） | camera truck along a path, markers pop as passed |
| feedback loop（フィードバックループ） | dot on a closed path, state change per lap |
| balance / trade-off（バランス、トレードオフ） | beam rotation from summed weights, pans hang level |
| memory / cache（記憶、キャッシュ） | drawer x slide, second retrieval much shorter |
| fit / solution（適合、解決策） | rotate + translate into the slot, small settle |
| signal from noise（ノイズから信号へ） | SVG path morph between noisy and clean |
| clarity / focus（明快さ、フォーカス） | masked sharp layer under a moving circle |
| spark / idea（ひらめき、アイデア） | pulse ring, bloom, radial stagger of lit elements |
