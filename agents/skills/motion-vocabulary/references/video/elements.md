# Element motion vocabulary: video builds

How each entry of [../elements.md](../elements.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

## Entrance and exit

| Name | Built with |
| --- | --- |
| fade slide（フェード＋スライド） | x or y offset to rest with opacity from clear to full in one tween on `power2.out`; both properties end together |
| soft rise（ソフトライズ） | small y offset, opacity and a blur filter on one tween with `sine.out`; the blur reaches zero a touch before the position stops |
| snap in（スナップイン） | very short x tween with opacity on `expo.out`, or a `tl.set` for a hard cut; no overshoot |
| split reveal（スプリットリビール） | two covers on a drawn layer over the subject moving apart with `power2.inOut`, or one `clip-path` inset closing toward the centre line |
| diagonal wipe（斜めワイプ） | `clip-path: polygon()` with a slanted edge whose points are tweened across with `power4.inOut`; the final state is the full shape |
| trail exit（残像アウト） | the element tweens out on `power3.in`; a handful of duplicated layers run the same move with growing start offsets, falling opacity and shrinking size |
| collapse away（折りたたみ退場） | scaleY down with `transform-origin` at the bottom edge on `power3.in`, opacity falling with it, removed from view on the last frame |
| 3d fold in（3D折り込み） | `rotateX` from a steep tilt to 0 with the origin on the top edge, inside a `perspective` parent, on `power2.out`; backface hidden |
| shrink fade exit（縮小フェード退場） | scale to a small value, opacity to 0 and a slight blur on one tween with `power2.in`, origin at the centre |

## Movement

| Name | Built with |
| --- | --- |
| linear travel（一定速移動） | x/y tween with ease `none`; when it needs to stop gently, a separate short tween takes over at the end |
| smooth arrival（なめらかな到着） | one long x/y tween with `power2.inOut`, duration scaled to the distance; ends exactly on its resting position |
| arc travel（弧を描く移動） | x and y on different eases (`none` or `sine.inOut` for x, a rise and fall for y) over the same duration, or three keyframes start, apex, end |
| anticipated move（予備動作つき移動） | one `back.inOut` tween whose dip behind the start is the wind-up; or a short reverse tween on `power1.out` followed by a main tween on `power3.out` |
| heavy stop（重い停止） | x tween on `power3.out`; at arrival a scaleX/scaleY squash with the origin on the leading edge, released by a short settle tween |
| path follow（パス追従） | element positioned along an SVG path by progress with `sine.inOut`; rotation read from the tangent at each step |
| stagger follow（段差追従） | one x tween on `power2.out` applied to all items with an equal start offset between neighbours |
| magnetic snap（マグネット吸着） | a tween toward the target position with a slow start, a fast closing and a brief overshoot into rest; the target outline is drawn on its own layer |
| zigzag travel（ジグザグ移動） | keyframe list of alternating y values on `sine.inOut` with x advancing steadily; ends on the target |
| momentum drift（慣性ドリフト） | a `power2.out` tween aimed past the target, then a brief tween back; the first leg covers most of the distance |
| waypoint hop（ウェイポイントホップ） | chained arc tweens (y up on `power2.out`, down on `power2.in`) with a quick scaleY squash at each touch-down |

## Scale

| Name | Built with |
| --- | --- |
| pop scale（ポップスケール） | scale from near 0 to 1 with opacity on `back.out` with a modest overshoot |
| breathing scale（呼吸する拡縮） | scale yoyo between slightly below and slightly above 1 on `sine.inOut` with a finite repeat count, ending at rest |
| elastic scale（エラスティックスケール） | scale from small to 1 with `elastic.out`; the swings come from the ease itself |
| axis stretch（軸方向ストレッチ） | scaleX (or scaleY) up with a smaller counter-scale on the other axis, on `back.inOut`, timed to the move's speed peak |
| focus pulse（フォーカスパルス） | a ring on its own layer from a small scale to a larger one with opacity falling to 0 on `power2.out`; played once or twice |
| depth zoom（奥行きズーム） | scale up with `translateZ` in perspective, blur to 0 and opacity up, on `power4.inOut` |
| soft shrink（ソフトシュリンク） | scale to a lower value and opacity to 0 with origin at the centre on `power2.in` |
| impact squash（インパクトスクワッシュ） | scaleY down with scaleX up, origin at the contact point, released by `elastic.out` right after the landing |
| center punch（センターパンチ） | scale from small through a large peak to 1, origin at the centre, on `back.out` with no layout reflow |
| width reveal（横幅リビール） | scaleX from almost nothing to full with the origin on the left on `power3.out`, a slight overshoot is optional; labels fade in on their own |
| depth pullback（奥行きプルバック） | scale from oversized to 1 with a `translateZ` push away, blur to 0 and brightness down, on `power2.inOut` |

## Rotation

| Name | Built with |
| --- | --- |
| simple turn（シンプルターン） | rotate tween with `power2.inOut` around a fixed pivot; start and end angles chosen on purpose |
| spin stop（スピン停止） | rotate through whole turns on `power3.out`, final angle set first |
| pendulum wobble（振り子の揺れ） | rotate around a top pivot through an alternating, decaying amplitude list on `sine.inOut` segments |
| coin spin（コインスピン） | `rotateY` through whole turns in a perspective parent on `power3.out`, final face forward |
| tilt reaction（チルトリアクション） | a small rotate toward the drawn cursor on `back.out`, then a return tween on `elastic.out`, origin near the touched side; ends at zero rotation |
| tumble in（タンブルイン） | x and rotate on `power2.out` with the rotation ending later than the position, a short settle to upright |
| counter rotation（カウンターローテーション） | parent rotate and child rotate by the opposite amount with `sine.inOut`, same pivot |
| gyroscope rotation（ジャイロ回転） | nested rings with `rotateX`, `rotateY`, `rotateZ` on separate layers, on `sine.inOut` with offset timing |
| rotate reveal（回転リビール） | `rotateY` from a steep hidden angle to rest with the origin at the left edge, plus opacity, on `power2.out` |

## Bounce and reaction

| Name | Built with |
| --- | --- |
| overshoot（オーバーシュート） | a single tween on `back.out` whose end value is the exact target; the overshoot is produced by the ease alone, with no second tween |
| bounce landing（バウンス着地） | y tween on `bounce.out`, or a keyframe list of falling peak heights with the floor line as every contact; ends at rest on the floor |
| spring follow（スプリング追従） | each follower is a delayed tween on `elastic.out`; later followers start later and swing a bit less, and all finish at the same shared position |
| rubber band（ラバーバンド） | a stretch tween on one axis with a smaller counter-scale on the other, released on `elastic.out` with the transform origin on the unpulled side |
| recoil（リコイル） | a short reverse x/y move on `power3.out` straight after the forward peak, then a slow easing return to rest |
| double bounce（ダブルバウンス） | two arc tweens with falling peak height, each coming down on a `bounce.out`-style ease, the second shorter than the first |
| snap back（スナップバック） | a drawn drag or stretch holds the pose, then a fast return tween on `back.out` ends on the rest transform |
| after shake（余震） | seeded x, y and small rotate offsets with decaying amplitude on `expo.out`, tweened back to the exact rest transform at the end |
| settle drop（沈み込み着地） | a y dip below rest paired with a widening scale on landing, followed by a slow tween back to the rest position |
| drag resistance（ドラッグ抵抗） | a drawn cursor tweens across; the element's position at time t is the cursor path at t minus a fixed delay, with a scaleX stretch that grows with the gap between them, then releases with a small overshoot |
| follow through（フォロースルー） | per-part tweens with staggered delays and a small overshoot, each ending on its rest value |

## Lists and grids

| Name | Built with |
| --- | --- |
| staggered list（リスト順次表示） | one tween shared by all rows, a small y offset and opacity on `power2.out`, an equal stagger between neighbours in reading order; the last row ends at rest |
| cascade list（カスケード表示） | y offset from above on `power3.out` with a tiny settle at the end, an equal stagger per row, opacity filling in during the first part of the move |
| alternating list（左右交互イン） | x offset with alternating sign per row on `power2.out`, a short stagger between rows, opacity rising with the move, all rows ending at the shared column |
| row expand（行の展開） | scaleY from a thin line with the origin at the top on `back.out`, the content masked inside, sibling rows below offset in y by the same amount |
| grid wave（グリッドウェーブ） | each cell tweens y and scale from small and low on `power2.out`, with stagger counted from the chosen corner by row plus column |
| center-out grid（中央から展開） | stagger with `from: "center"` on a scale pop using `back.out`, so each ring springs slightly past its final size |
| row sweep grid（行スイープ） | per-row stagger with tiny column offsets on `power2.inOut`, each cell fading and rising a short distance into its slot |
| shuffle to grid（シャッフル整列） | seeded start positions and rotations per tile, then one tween to the shared layout with rotation to level on `back.inOut`; the seed keeps the scatter repeatable |
| list slide stack（リスト積み重ね） | the new row is inserted at a y offset, and all existing rows tween one row down together on `power2.out` while it fades in |
| list trim collapse（リスト削除詰め） | fade and scaleY the removed row toward its top edge, then tween the following rows up by that row height on `power2.inOut` |
| grid spiral（グリッド螺旋展開） | stagger driven by a precomputed array of cell indices in spiral order, each cell fading and scaling in on `power2.out` |
| grid diagonal wave（グリッド斜めウェーブ） | stagger by column plus row from one corner with a short offset, scale and opacity on `power3.out` |

## Attention and emphasis

| Name | Built with |
| --- | --- |
| nudge（ナッジ） | a short x offset out and back on `back.out`, applied to the one element; it ends exactly on its rest position |
| attention bounce（アテンションバウンス、注目バウンス） | a y hop up and down with a small scaleY squash at the landing, the descent on `bounce.out`; ends at the original position |
| badge pop（バッジポップ） | badge scale from zero with a small rotation on `back.out`, transform origin at the corner it sits on; the base layer is not tweened |
| focus halo（フォーカスハロー） | a blurred ring layer tweened in scale and opacity from tight to wide and from visible to clear on `power2.out`, played once |
| highlight sweep（ハイライトスイープ） | a masked gradient or a bar on a drawn layer clipped to the element, x tween across on `power2.inOut`, played once |
| border chase（ボーダーチェイス） | an SVG rect stroke with a short dash and a tweened dash offset, `none` ease, a finite number of laps |
| press feedback（プレスフィードバック） | a drawn cursor arrives, then scale down with shadow reduced on press, and a return on `power2.out` with the ring fading away |
| jelly emphasis（ゼリー強調） | alternating scaleX and scaleY with falling amplitude on `elastic.out`, ending at the original scale |
| color pulse（カラーパルス） | a colour tween to an accent and back on `sine.inOut`, a finite number of repeats, ending on the base colour |
| icon nod（アイコンうなずき） | rotateX about an origin on the top edge inside a perspective parent, forward on `back.out`, then a smaller tween back to level on `sine.out`; one nod, the icon at rest at the end |
| spotlight focus（スポットライトフォーカス） | a dim overlay on a drawn layer with a circular cut-out; the cut-out position and size are tweened on `power2.inOut`, the overlay fading in with it |
| error shake（エラーシェイク） | seeded x offsets with decreasing size on `expo.out`, the outline tinted red on the same layer and held at the end |
