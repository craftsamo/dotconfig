# Paths, diagrams and data vocabulary: video builds

How each entry of [../data.md](../data.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

## SVG and paths

| Name | Built with |
| --- | --- |
| svg stroke draw（SVG線描画） | the path's `stroke-dasharray` is set to its length and `stroke-dashoffset` is tweened from full length to zero on `power2.out`; fill, if any, fades in after |
| svg path morph（SVGパスモーフ） | a tween of the path `d` between two paths with matching point counts and order, on `power2.inOut`, ending on the target path |
| svg segment trim（区間トリム） | `stroke-dasharray` set as a short dash and a gap, with `stroke-dashoffset` moved along the path on `power2.inOut` |
| svg motion path（モーションパス追従） | the item is positioned from the path by a progress value with tangent rotation, tweened on `power2.inOut`; the final point is the path's end |
| svg mask reveal（SVGマスクリビール） | a mask element on the artwork, its shape scaled from small to past full on `power2.out` around a chosen centre |
| svg gradient flow（グラデーション流動） | gradient stops or `gradientTransform` tweened along the line with `none` ease, a finite number of loops |
| gooey merge（グーイーマージ） | a blur followed by a colour-matrix contrast filter over moving circles on a drawn layer, on `power2.inOut`; the final frame is a clean shape |
| signature stroke（署名ストローク） | several paths each with a dash offset tween in writing order, round caps, on `power2.inOut`, with each starting as the last finishes |
| radial repeater（リピーター） | clones placed at an even angle step around a pivot with staggered scale or rotation on `sine.inOut`, ending at a settled arrangement |
| noise blob（ゆらぐブロブ） | path points moved by a seeded noise list over a looping time axis, with the loop closing on its first frame |
| radiating burst lines（集中線、放射の線） | a set of lines from one origin, extended on `power2.out` with a stagger and erased from the base; lengths vary by a seeded list |
| marching dashes（破線が流れる） | a path with a dash pattern whose offset tweens by exactly one pattern length on `none` ease, so the loop seam is invisible; a finite number of loops, then the line stops |

## Data storytelling

| Name | Built with |
| --- | --- |
| sankey flow reveal（サンキー流量リビール） | band paths drawn with a dash offset from the source end on `power2.inOut`, stroke widths set from the data and the node labels fading in just before |
| metric odometer cascade（指標オドメーター） | per-digit vertical columns of numerals moved in y with a stagger between metrics on `power2.inOut`; each column ends aligned on its target digit |
| threshold alarm wave（閾値アラーム波） | the line draws past a marked limit; at the crossing a colour ring on a drawn layer expands from that point on `power2.out` and tints the line it passes |
| forecast confidence fog（予測信頼度フォグ） | a blurred band around the forecast path, its width and softness growing along x on `expo.out`, drawn on a layer beneath the line |
| live signal pulse map（ライブ信号パルスマップ） | pulse rings at seeded points on a fixed schedule, scale up with opacity down on `power2.out`, a finite number of events in total |
| comparison delta split（比較デルタ分割） | two bars move apart on `power2.inOut`, a bracket drawn along the gap, and the difference figure fades in beside it |
| timeline scrub trail（タイムライン軌跡） | a line drawn left to right with a cursor dot at its head, the older portion fading by opacity along its length, on `none` ease |
| network topology bloom（ネットワークトポロジー展開） | nodes popped by scale on `back.out` with a stagger by depth, edges drawn by dash offset outward from the parent layer by layer |
| progress milestone firefly（進捗マイルストーン蛍） | a dot moving along the path by progress on `power2.inOut`, each milestone's glow layer fading up on arrival, finishing at the last one |
| heatmap ripple focus（ヒートマップ注目波） | a ring from the hot cell, with each neighbour's scale pop reduced by its distance on `back.out`, and the grid ending at rest |
| stream graph breathing（ストリームグラフ呼吸） | stacked paths morphed between two sets of values on `sine.inOut` for a finite number of repeats, ending at the first set |
| rank ladder climb（順位ラダー上昇） | y tween per row to its new position on `power2.out`, the climbing row lifted slightly in front and the numbers updating at the end |
| data cluster merge（データクラスタ結合） | points tweened to a shared centre with small offsets on `back.out`, one colour taking over from the groups at the end |
| event sequence domino（イベント列ドミノ） | per-item rotate or drop on a stagger on `expo.out`, with each starting as the previous reaches the next |
| kpi spotlight relay（KPIスポットライトリレー） | a moving light pool on a drawn layer glides between the figures while the old one's brightness falls and the new one's rises |
| radial budget bloom（放射予算ブルーム） | arcs by `stroke-dashoffset` on a stagger around the ring, each ending at its share, labels counting up with it |
| calendar density sweep（カレンダー密度スイープ） | per-cell fill with a stagger across rows on `power2.out`, with colour intensity set from the data |
| live queue compression（ライブキュー圧縮） | row items moved in x steps, with a small squash on arrival on `back.out`, the queue ending evenly spaced |
| sentiment spectrum shift（感情スペクトラム遷移） | a marker tweened in x over a fixed gradient on `power2.inOut`, with the label crossfading as it goes |
| goal projection arc（目標予測アーク） | an arc path dashed by a pattern and revealed with a mask or clip growing along it on `power2.inOut`, then an end marker scaled up on `back.out`; ends still |
| scatter reveal（散布図が現れる） | dots in a seeded order on a stagger on `power2.out`, followed by a line drawn left to right |
