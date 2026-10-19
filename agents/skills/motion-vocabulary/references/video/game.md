# Game motion vocabulary: video builds

How each entry of [../game.md](../game.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

Tints, colour drains and distortions go on the drawn world layers; supplied art, a cast or a logo moves, holds or is copied, never re-rendered.

## Game HUD

| Name | Built with |
| --- | --- |
| coin collect（コイン回収） | the coin element follows a curved path with an in-out ease; on arrival it is hidden, the count-up starts and the counter box gets a quick scale pop that settles back |
| HP ghost bar（HPゴーストバー） | two stacked fills; the front one tweens straight to the new width, the back one runs the same width tween later with an in-out ease |
| cooldown ability（クールダウン） | a conic or SVG arc mask on the dim layer tweened to empty on a near-linear ease; at the end an outward ring and a brief brightness lift on the icon with `power2.out` |
| score roll-up（スコアロールアップ） | per-digit columns translated in y with the leading places on later starts, or a count-up value tweened and rounded; the numeral scales up at the start and back at the end |
| stamina pulse（スタミナ脈動） | gauge scale and glow on a looped sub-timeline with `expo.out` on the push and a slower ease back; the repeat count is finite and ends on the rest state |
| ammo reload（弾薬リロード） | per-pip opacity and scale on a stagger, the refill pass starting after the empty pass; an arc around the icon fills to the clip total with an in-out ease |
| compass lock（コンパスロック） | the strip translated in x on an in-out ease, ending with the target tick under the mark; the marker takes a small settle tween on arrival |
| minimap ping（ミニマップピン） | a pulse ring scaled out and faded with `power2.out` inside a circular clip; the pin dot is popped on at the same moment and stays |
| objective marker（目標マーカー） | marker y loop on `sine.inOut` with a finite repeat; the label value is a count-down tweened over the shot, rounded, and not offset |
| resource cap（資源上限警告） | bar x offsets taken from a seeded list with quick decay; label opacity switched in steps, ending on a visible state |
| party status（パーティ状態） | stacked cards with bar fills; the hit card takes a small x nudge and a tint overlay tween, then settles back |
| buff timer（バフタイマー） | a ring path with `stroke-dashoffset` tweened to empty on a near-linear ease; the icon opacity fades just after the ring ends |

## Combat and hit effects

| Name | Built with |
| --- | --- |
| damage numbers（ダメージ数値） | text pop with scale `expo.out`, then a y travel with opacity out; the starting size scales with the damage amount and the x is a small seeded offset |
| combo counter（コンボカウンター） | count-up in steps with a scale punch back to rest on `expo.out` per step; an underline or gauge refilled on each hit |
| critical flash（クリティカルフラッシュ） | a full-frame white overlay held for a few frames over a drawn radial burst, then faded; the damage figure is popped on top; never more than 3 flashes in any one second, and no saturated red full-frame flash |
| hit confirm（ヒット確認） | the drawn slash scaled in at the contact point; a short x recoil on the target that returns; a particle burst on seeded vectors |
| guard break（ガードブレイク） | crack paths drawn on, then pre-cut shards pushed outward with `expo.out`; the gauge layer removed at the break |
| perfect dodge（ジャスト回避） | a grayscale or tint tween on the world layers; one afterimage copy with reduced opacity; an overshoot with `back.out` back to the normal state |
| parry window（パリィ成功） | ring scale tween toward the contact, radial spark lines scaled out on `expo.out`, then an x recoil on the foe that settles |
| status ailment（状態異常付与） | an icon popped in above the target; a colour overlay tweened on the target; looped small particles with finite repeats |

## Rewards and loot

| Name | Built with |
| --- | --- |
| level up burst（レベルアップ） | a pulse ring, a seeded particle burst, the banner scale with `back.out`, and a count-up of the level number |
| chest open（宝箱オープン） | lid `rotateX` around the back edge on `expo.out`; a light gradient that grows after it; item y and opacity on a stagger |
| three star clear（三つ星クリア） | per-star scale and rotate tweens on a stagger from larger to rest; a sparkle added on each landing |
| gacha pull（ガチャ排出） | a glow bloom tween; the capsule translated up; two halves translated apart; the result card shown beneath them |
| new record stamp（新記録スタンプ） | stamp scale from oversized to rest with `power2.out`, a fixed small rotate offset, and a small camera shake right at contact |
| loot rarity（レア度確定） | border and glow colour tweens; per-star opacity on a stagger |
| achievement unlock（実績解除） | toast x travel in on `expo.out`; the icon popped after it; a sheen swept across; a slide back out in the same direction |
| daily bonus（デイリーボーナス） | tile flip on the current tile; check draws on the earlier tiles; a glow tween on today's tile |
| currency rain（通貨レイン） | seeded start positions and delays; y fall with different distances and a slight rotation, finite in number |
| reward card reveal（報酬カード公開） | `rotateY` per card on a stagger with `power2.out`, back face hidden at the midpoint; a glow on the best card |

## Progression and quests

| Name | Built with |
| --- | --- |
| quest banner（クエストバナー） | banner clip or x travel in with an in-out ease, a hold, and the same travel out; the title unmasked inside it on a later start |
| skill unlock（スキル解放） | the lock shackle dropped and faded; a node glow tween; the connector with `stroke-dashoffset` drawn afterward |
| login streak（連続ログイン） | stamp scale per tile with `power2.out` on a stagger; the last stamp larger; a count-up for the streak number |
| energy refill（エネルギー回復） | fill height tween; the wave an animated path on the surface; icon bounce with `back.out` on arrival |
| XP overflow（XP繰り上がり） | bar fill to full; an instant reset with `tl.set`; a second fill to the remainder; the level number swapped at the wrap |
| battle pass（バトルパス進行） | a line fill along the track; a per-tile open triggered at the time the line crosses |
| mission step（ミッション段階） | check draw per step; a highlight bar moved to the next row with an in-out ease |
| rank up（ランク昇格） | an emblem swap under a sheen sweep; a scale punch with `power2.out`; a small sparkle |
| collection complete（収集コンプリート） | item pop on a stagger; a grid scale bounce with `back.out`; a seal stamped on top at the end |

## Game cinematics and warnings

| Name | Built with |
| --- | --- |
| lucky roulette（ラッキールーレット） | `rotate` on the wheel with a decelerating ease like `power4.out` to a chosen angle; a pointer flick on each segment pass |
| countdown GO!（カウントダウンGO） | number swaps by `tl.set`, a scale punch with `power2.out` for each, and the final word with a burst |
| boss warning（ボス警告） | stripe layers scrolled in opposite directions; the word with a scale slam; a tint overlay pulsing on a fixed list; never more than 3 flashes in any one second, and no saturated red full-frame flash |
| victory title（勝利タイトル） | scale from large with a weighty `expo.out`; radial rays rotating slowly; a small camera shake at landing |
| defeat dissolve（敗北ディゾルブ） | grayscale and dim tweens on the world layers; the word by blur-in; a vignette that closes in |
| chapter intro（チャプター導入） | a mask reveal for the title; a line with `stroke-dashoffset`; a dimmed background |
| raid start（レイド開始） | cards on a stagger; a hard-cut title; a quick scale push-in on the wrapper |
| letterbox focus（シネマ帯フォーカス） | two bars with y tweens; a wrapper scale; a small overshoot on the bars with `back.out` |

## Game impact FX

| Name | Built with |
| --- | --- |
| hit-stop frame（ヒットストップフレーム） | a hold on the pose by a timed gap; sparks on their own short tweens; everything resumes at one time |
| shockwave typography（衝撃波タイポ） | a pulse ring from the word; per-letter offsets scaled by distance from the centre and tweened back |
| directional slash reveal（方向スラッシュリビール） | a thin line tween along a diagonal; two `clip-path: polygon()` halves pushed apart |
| freeze-frame color drain（静止色抜き） | a hold; a grayscale tween on the world layers; one accent layer kept above |
| combo heat escalation（コンボ熱量上昇） | scale and colour stepped per count; the flame layer opacity and size grown at the same steps |
| screen-edge damage pulse（画面端ダメージ脈動） | a vignette-shaped inset glow overlay; opacity pulses on a seeded list; never more than 3 flashes in any one second, and no saturated red full-frame flash |
| armor crack network（アーマー亀裂網） | crack paths by `stroke-dashoffset` from the impact point; pre-cut shards dropped |
| critical lens compression（クリティカルレンズ圧縮） | scale on the camera wrapper; a radial displacement on the world layers; a snap back with `expo.out` |
| boss phase shatter（ボスフェーズ破砕） | pre-cut polygon shards pushed outward with seeded vectors, a bright overlay under them, a new layer under the shards |
| speedline tunnel（スピードライントンネル） | a radial line set scaled outward on a loop with a finite count; a vignette ring |
| parry time slice（パリィ時間スライス） | two clipped copies of the scene, one delayed in time; a thin bright seam |
| elemental affinity burst（属性アフィニティバースト） | a particle burst in an element palette; drawn shapes per element; a bloom |
| camera kick HUD（カメラキックHUD） | seeded x/y/scale offsets on the HUD wrapper only, decaying; see camera shake |
| afterimage dash（残像ダッシュ） | cloned layers with decreasing opacity and a growing delay along the path |
| victory impact hold（勝利インパクトホールド） | a hold on the pose; a line burst; a title scale punch; a slow drift on the camera |
| loot beam column（ルートビーム柱） | a tall gradient bar with `scaleY` from the ground; a screen blend; particles rising |
| warning stripe slam（警告ストライプスラム） | stripe-pattern bars from the edges with `expo.out`; a small camera shake |
| shield recharge sweep（シールド再充填スイープ） | a gradient bar tween over the segments; a per-segment opacity flip as it passes |
| mission stamp punch（ミッションスタンプパンチ） | stamp scale from oversized, a rotate offset, a pulse ring, a camera shake |
| finisher title cut（フィニッシャータイトルカット） | a hard cut by `tl.set`, one full-frame white frame before it, a title scale punch on black |
