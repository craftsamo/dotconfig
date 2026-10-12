# Interface space and material vocabulary: video builds

How each entry of [../ui-space.md](../ui-space.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

## Layout and navigation

| Name | Built with |
| --- | --- |
| shared element（共有要素トランジション） | the same element tweened between its two layouts in one move on `power2.inOut`, the surrounding page swapping beneath; core: `shared-element morph` |
| view crossfade（ビュークロスフェード） | two stacked layers, the old one's opacity out and the new one's in over the same span on `sine.inOut` |
| FLIP reorder（FLIP並べ替え） | first and last boxes recorded, then each item starts at the inverted offset and tweens to zero on `power2.inOut` |
| modal morph（モーダルモーフ） | a FLIP of position, size and radius between the trigger box and the dialog box on `power3.inOut`, scrim in step |
| tab indicator（タブインジケーター） | one indicator, x and width tweened between tab boxes on `power3.out`, label colour switching on arrival |
| filter reflow（フィルター再配置） | opacity and scale out on the removed cards, then a FLIP of the remaining grid cells on `power2.inOut` |
| route slide（ルートスライド） | two screens, x tweens on `power3.inOut`, the old one offset by a fraction and dimmed |
| page wipe（ページワイプ） | a full-height panel with `scaleX` or a `clip-path` tween on `power4.inOut`, origin left then right, with the page swapped at full cover |
| sidebar reveal（サイドバー展開） | panel x tween from off the edge on `power3.out`, scrim opacity a touch later, optional content offset |
| command palette open（コマンドパレット展開） | scale and y from slightly smaller on `power2.out`, scrim fade, per-row stagger starting after the box |
| dropdown origin reveal（ドロップダウン起点展開） | `transform-origin` at the trigger corner, scaleY and opacity tween on `power2.out`, options staggered downward |
| list-to-detail expand（一覧から詳細展開） | a FLIP from the row box to the full page on `power3.inOut`, sibling rows fading and shifting |
| popover enter and exit（ポップオーバー出入り） | scale and opacity from the anchor on `power2.out`, played in reverse on exit |
| top layer dialog（トップレイヤーダイアログ） | a dialog layer above, scrim opacity and the surface's y and scale tweened on `power2.out` with different spans |
| circular view transition（円形ビュー遷移） | `clip-path: circle()` on the new view, from zero radius at the click position to the frame diagonal on `power3.inOut`; core: `iris / circle reveal` |
| discrete property exit（離散プロパティ退場） | opacity and scale out on `power2.in`, then `tl.set` for display none and a FLIP of the neighbours |
| intrinsic height expand（自動高さ展開） | height tween from zero to the measured content height on `power2.out`, overflow clipped, opacity starting a touch later |
| page stack transition（ページスタック遷移） | incoming y from the bottom edge, outgoing scale and dim on `power3.inOut`; core: `push stack` |
| modal enter / exit（モーダルを開く・閉じる） | scale and opacity in on `power3.out`, a shorter reverse out, the scrim fading in step |

## Navigation and overlays

| Name | Built with |
| --- | --- |
| hero expand（ヒーロー展開） | FLIP of box and radius from thumbnail to full frame on `power3.out`; core: `shared-element morph` |
| spring sheet（スプリングシート） | sheet y from below the frame to its stop on `back.out`, scrim opacity tweened along with it |
| parallax push（パララックスプッシュ） | incoming screen x over the full travel and outgoing x over a fraction, same ease and start, dimmed as it leaves |
| staggered reveal（段階リビール） | per-item y and opacity tweens on `power2.out` with an even stagger, the first starting as the screen lands |

## Spatial UI and depth

| Name | Built with |
| --- | --- |
| cursor depth pull（カーソル奥行きプル） | per-layer translateZ and x/y offset scaled by the drawn cursor's timeline position, eased with `expo.out` |
| focus portal（フォーカスポータル） | scale and translateZ on the chosen item, blur and scale down on the others, on an in-out ease |
| radial command bloom（放射コマンドブルーム） | items on a circle from the press point, the radius growing with a stagger on a smooth ease |
| spatial breadcrumb（空間パンくず） | panels placed in z, each step shifting the others back by one step on `power3.out` |
| perspective dock（遠近ドック） | per-icon scale by distance to the drawn cursor's timeline position, rotateY tilt, `back.out` as the cursor settles |
| layer peel（レイヤーピール） | corner lift by `rotate3d` with a moving clip, a shade overlay, on `expo.out` |
| tooltip orbit（ツールチップ軌道） | labels positioned on a circle around the target, the ring rotating on a smooth ease |
| depth lens（奥行きレンズ） | masked sharp copies per depth plane under a moving circle |
| magnetic constellation（磁気コンステレーション） | dot offsets and the lines between near pairs computed per frame from the drawn cursor's timeline position, on a short ease-out |
| infinite canvas jump（無限キャンバスジャンプ） | stage x/y and scale to a keyed position on `back.out`; core: `infinite canvas pan` |
| Z-axis notification（Z軸通知） | notice translateZ from far to zero on `expo.out`, page scale and dim at the same time |
| camera dolly UI（カメラドリーUI） | a camera wrapper's translateZ through keyed positions on a smooth ease |
| volumetric menu（ボリュームメニュー） | faces of each item in 3D with `preserve-3d`, a stagger of translateZ |
| parallax inspector（パララックス検査面） | per-layer offset driven by the tilt value on a smooth ease |
| spatial search reveal（空間検索リビール） | per-result translateZ and scale from the box position on `back.out` with a stagger |
| orbiting context menu（軌道コンテキストメニュー） | items placed on a ring around the target, the ring rotating on a smooth ease |
| depth stack reorder（奥行きスタック並べ替え） | translateZ and y swaps with a stagger on a smooth ease |
| perspective calendar fold（遠近カレンダーフォールド） | two halves on `rotateX` about the crease with a shade; core: `fold / unfold` |
| cursor raycast select（カーソルレイキャスト選択） | line draw from the cursor to the target on `power2.out`, highlight tween on contact |
| spatial audio locator（空間オーディオロケーター） | a source dot on an orbit, rings emitted from its position with a small overshoot, a fixed listener |

## Material and surface motion

| Name | Built with |
| --- | --- |
| liquid tab bridge（液体タブブリッジ） | two blobs and a connector under a goo filter, ending on `back.out` |
| gel button split（ジェルボタン分裂） | a circle splitting under a goo filter, the parts moving apart on `back.out` |
| glass refraction hover（ガラス屈折ホバー） | `backdrop-filter` and a displacement filter on a circle at the cursor |
| ink adhesion（インク吸着） | round drops on a drawn layer under a blur-plus-contrast goo filter, seeded starts and arcs toward the button edge on `power2.in`; a rim-bulge tween on contact, all drops gone by the end |
| metallic foil tilt（メタリック箔チルト） | a card layer on a slow rock with `sine.inOut`, a gradient band on a drawn layer clipped to the card and offset against the rotation, hue shifted along the way; ends level |
| soft body toggle（ソフトボディトグル） | knob squash with `elastic.out`, a track colour tween |
| viscous progress（粘性プログレス） | a fill shape on a drawn layer under a blur-plus-contrast goo filter, its width tweened on `power3.out`, a small blob riding the front with a gentle seeded wave; the final frame is a full clean bar |
| chromatic glass edge（色分散ガラスエッジ） | three tinted copies of the edge layer on a drawn pane, offsets tweened apart and back on `sine.inOut` with a screen blend; the pane art moves, nothing is re-rendered; core: `chromatic aberration` |
| paper fold reveal（ペーパーフォールド） | a few panels hinged by rotateY at their creases inside a perspective parent, staggered on `back.out`, a shade overlay tied to each angle; ends flat; core: `fold / unfold` |
| cloth wave panel（クロスウェーブパネル） | strips with offset y keys, or a displacement filter with a tweened scale |
| bubble merge menu（バブル結合メニュー） | circles on a drawn layer under a blur-plus-contrast goo filter, each satellite tweened out along its own direction on `power2.out` with a stagger and back again; ends as one bubble |
| frost melt unlock（フロスト融解アンロック） | a frosted overlay on a drawn layer, blurred and whitened, with seeded hole shapes growing in size and merging, overlay opacity falling on `sine.inOut`; ends with the layer gone |
| elastic membrane press（メンブレンプレス） | displacement or radial scale from the press point on `elastic.out` |
| sand dissolve state（砂状ステート切替） | seeded grain particles sampled from the old state on a drawn layer, dispersed along a shared drift with stagger on `power2.in`, then gathered into the new state on `power2.out`; ends fully formed; core: `particles` |
| oil slick selection（オイルスリック選択） | a multi-hue gradient on a drawn layer clipped to the item, its position and hue tweened slowly on `sine.inOut` with a few seeded wobbles; a finite loop that ends settled |
| magnetic fluid badge（磁性流体バッジ） | a blob path morphed between a smooth and a spiked contour on `power2.out`, the spike side set from the drawn cursor angle; relaxes to the smooth shape at the end |
| glass crack recover（ガラス亀裂リカバー） | crack paths drawn on a drawn glass layer by dash offset from the impact outward on `power3.out`, a faint light line along them, then reversed in the same order and faded; seeded branching |
| neon tube draw（ネオン管ドロー） | a sharp core path and two blurred wider copies on drawn layers, all revealed by dash offset on `power2.inOut`, strokes in order; the halo settles to a steady level at the end; core: `neon sign` |
| chrome ripple surface（クローム面リップル） | concentric rings with a displacement filter and decaying amplitude |
| clay morph icon（クレイアイコンモーフ） | a path morph between two contours on `power3.inOut` with intermediate keyed bulges, a soft shading gradient layer moved with it; the shaded art is drawn, ends on the target shape |

## 3D objects

| Name | Built with |
| --- | --- |
| cube rotation（立方体の回転） | six faces placed in `translateZ` around a centre inside a `perspective` parent, `rotateY` on the parent tweened with `none` ease, plus a small fixed `rotateX` tilt |
| cover flow（カバーフロー） | row x steps with `rotateY` and scale set by the distance from the centre position, on a spring-like ease, finishing with one card centred |
| depth stack（奥行きのある重なり） | each card positioned by its own `translateZ` inside a `perspective` parent, with the stack tweened forward by one step on `none` ease and the front card fading out |
