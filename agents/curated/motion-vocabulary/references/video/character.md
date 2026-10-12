# Character and physical motion vocabulary: video builds

How each entry of [../character.md](../character.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

Joint-level entries (walk cycle, blink, follow-through of a tail) need a character built from separate parts: your own drawn shapes or supplied part files. Supplied whole-pose art moves by pose swaps and whole-body transforms only; a walk is then a swap between approved walk poses over a sliding ground.

## Character and physical motion

| Name | Built with |
| --- | --- |
| timing contrast（緩急、タイミング(重さ)） | duration and ease choice per move; a short hold before a fast move |
| spring settle（バネの収まり） | `elastic.out(amplitude, period)` or a damped keyframe list; a drawn coil is an SVG zig-zag scaled in y with `vector-effect: non-scaling-stroke` |
| squash and stretch（スカッシュ＆ストレッチ、スクワッシュ＆ストレッチ） | scaleX/scaleY with `transform-origin` at the contact point, width x height kept near constant; one `fromTo` per phase so seeking in any order gives the same frame |
| anticipation（予備動作、予備動作(アンティシペーション)） | a short reverse tween before the main one |
| follow-through / lag（フォロースルー、しっぽ・髪のフォロースルー、tail follow-through、フォロースルー／オーバーラップ） | the same rotation on each link with a growing delay and a small overshoot |
| jointed walk cycle（ウォークサイクル、歩き、walk cycle） | nested limbs with `transform-origin` at each joint; thigh +-25-30 deg per stride, the knee folds so the foot trails behind (away from the facing direction); finite repeats; the ground or background slides under a walker held in frame |
| jump（ジャンプ、溜め→伸び→着地） | an anticipation tween (wider, lower), a launch stretch, a parabolic y path (`power2.out` up, `power2.in` down), a landing squash and a quick recovery, all with the origin at the feet |
| blink and mouth flap（まばたき、口パク、blink） | eye scaleY to ~0.1 and back; a mouth-shape swap on a list of times. Loose flapping, not lip sync |
| take（テイク、驚き） | a quick compress, a stretch with overshoot on `back.out`, an eye and mouth pose swap at the peak, a settle tween, then a held pose |
| head turn（振り向き） | separate tweens for the eye group, head group and body, offset starts on `power2.inOut`, body turning least; a pose or part swap at the midpoint as the face becomes visible |
| idle breathing（待機、呼吸、アイドル） | a tiny looped scaleY or y on the torso on `sine.inOut`, shoulders following a little later, plus a weight-shift tween at uneven gaps; finite repeats |
| line draw and retract（線の描画と引き戻し） | `stroke-dasharray` + `stroke-dashoffset` forward, then continue the offset past the length so the tail chases the head |
| page turn（ページめくり） | page with two faces (`backface-visibility: hidden`, back face `rotateY(180deg)`), `rotateY` on the spine edge inside `perspective`; a shade overlay peaks at 90 deg. Stacked faces trip the layout overlap audit: mark only the page-number/text blocks `data-layout-allow-overlap` |
| seamless loop（シームレスループ、継ぎ目のないループ） | every tween returns to its start or travels a whole period; finite repeat count |
| float（浮遊、ふわふわ） | a slow looping y tween with a small rotate on `sine.inOut`, shadow scale and opacity run opposite to the object's height; finite repeats |
| rotating gradient ring（回る光の輪） | a conic-gradient ring with a rotate tween on a linear ease, a blurred copy behind for the glow, a thin border width; finite repeats |
| noise wobble（ゆらゆら、ノイズ） | seeded noise offsets on x, y and rotate, each from its own seed and moving slowly, the loop closing at the end; finite repeats |
| hold & cycle（ホールドとサイクル） | a timeline alternating holds with short tweens, a small sine cycle underneath each hold at a fraction of the main amplitude, repeated a fixed count |
| boil（ボイル、ラインボイル、線の震え、line boil） | swap between 2-3 fixed displacement seeds on steps of 2-3 frames |
| animate on twos（2コマ打ち、1 コマ打ち・2 コマ打ち・3 コマ打ち） | `steps()` ease, or time rounded to 1/12 s |
| limited-animation hold（リミテッドアニメの止め） | a pose swap followed by a hold; secondary parts on `steps()`; the hold is a timed gap, not a frozen render |
| smear frame（スミア） | on your own drawn shapes: one frame of a stretched shape along the path; on supplied whole-pose art: a drawn streak layer behind it for 1-2 frames, never a deformed cast |
| impact frame（インパクトフレーム） | a full-frame overlay layer (flat colour plus `mix-blend-mode: difference` or a drawn two-tone plate) and an SVG radial line burst, each held 1-3 frames on a seeded schedule; never more than 3 flashes in any one second, and no saturated red full-frame flash |
