# Timing, easing and feel vocabulary: video builds

How each entry of [../timing.md](../timing.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

## Principles

| Name | Built with |
| --- | --- |
| staging（ステージング） | the hero tweened up from slightly small to full size while the other layers fade to a lower opacity, both on `power2.out` and ending on the same frame |
| pose to pose / straight ahead（ポーズ・トゥ・ポーズ、ストレートアヘッド） | keys set first and filled with `power2.inOut`; the straight-ahead version is a long sampled list where each value is computed from the one before with a seeded function |
| slow in and slow out（スローイン、スローアウト） | `power2.inOut` or `sine.inOut` on the tween; entrances use an ease-out, exits an ease-in, and the symmetric curve is used for moves that stay in frame |
| arcs（アーク、弧の軌道） | a motion path on a curved SVG route, or x and y given different eases so the combined path bends |
| secondary action（セカンダリーアクション） | an extra tween on a child element at a fraction of the hero's travel, started slightly after it with `sine.inOut` against the hero's `power2.out` |
| exaggeration（誇張） | larger from-values and a deeper squash, with `back.out` or `elastic.out` on the hero element and a short return |
| solid drawing / depth（ソリッドドローイング、立体感） | `perspective` on the parent and `rotateY` swinging a slight amount each way on `power2.inOut`, with a drawn shadow layer whose offset and length follow the angle |
| appeal（アピール、気持ちよさ） | knob x tween on `power2.out`, a scaleX stretch only mid-travel, and the label colour tween started a few frames later and ending with the knob |
| cause-and-effect chain（原因と結果の連鎖） | each element's start set relative to the previous one's end or hit moment, all on `power2.out` with the same short duration |
| anti-robotic jitter（アンチ・ロボット、ゆらぎ） | a base stagger plus a small seeded offset to each start and a slight seeded size variation per element, finite looped micro-tweens for anything held |
| primary / secondary / ambient（主役・脇役・背景の三層） | three tween layers at different speeds, the lead fastest, the supporting ones delayed and smaller, and the background on a slow looped sine drift |
| no dead frames（止まって見えるコマを作らない） | a slow `sine.inOut` drift or breathing loop on the background layer underneath every held pose, finite repeats |
| counter-motion（カウンターモーション） | opposite-direction x tweens started together on the same `power2.out`, the background travelling only a fraction of the hero's distance |

## Easing

| Name | Built with |
| --- | --- |
| linear（linear、等速） | `ease: "none"` on rotation, drift or a marquee, with the speed matched across a loop seam |
| ease-out expo（入り） | `expo.out` on the entrance tween, a moderate duration, paired with an ease-in for the exit |
| ease-in expo（退場） | `expo.in` on the exit tween, shorter than the entrance of the same item |
| ease-in-out cubic（移動） | `power3.inOut`, with a longer duration for longer distances |
| thin-peak curve（シンピーク、ハウスカーブ） | custom ease drawn from a steep-middle path, on a logo or large move, optionally with a little blur added during the fast middle |
| whip curve（WHIP、ムチ） | `expo.inOut`, or a `CustomEase` with a flat start, a near-vertical middle and a short tail, with a smear on the fast part |
| glide（グライド） | `power4.out` or `expo.out` stretched over a long tween |
| ease-out quint（ease-out quint） | `power4.out` on a longer entrance, on large moves and scale-ups, often with a stagger |
| Material 3 standard（Material 3 標準） | custom ease drawn as a curve with a quick rise and a long flat finish, medium duration for small UI |
| Material 3 emphasized（Material 3 強調、減速） | custom ease with a steep early rise and a long tail, on the hero's big entrance and paired with an accelerate for the exit |
| Material 3 accelerate（Material 3 加速、退場） | an in-curve such as `power2.in` or a custom ease of that shape, short, with an opacity fade |
| Apple standard（Apple 標準） | a `CustomEase` of that front-loaded shape, on small state changes |
| back out（オーバーシュート） | `back.out` on a success or add moment |
| back in（引いてから去る） | `back.in` on an exit or launch |
| back in-out（back in-out） | `back.inOut` on a logo or playful scene |
| sine in-out（呼吸） | `sine.inOut`, looped for a finite breathing cycle with a small amplitude |
| circ out（circ out） | `circ.out` on mechanical UI |
| elastic out（ゴム） | `elastic.out` on a mascot or sticker, long enough for the wobble to finish |
| bounce out（弾む） | `bounce.out` on a drop, with a squash added at each contact |
| steps / posterize（steps、コマ打ち） | `steps()` ease, or `SteppedEase`, on counters and sprites, or posterize after easing |
| SlowMo（速い→遅い→速い） | `SlowMo` ease on a title passing through, with the slow part taking up much of the move |
| RoughEase（ガタつき） | `RoughEase` with `randomize: false`, or a precomputed seeded keyframe list, for glitch or tension moments, the amount of jitter tuned by its strength |
| ExpoScale（等速に見えるズーム） | `ExpoScaleEase` on scale, for push-ins and pull-outs |
| CustomWiggle（揺れ） | `CustomWiggle` ease with a finite wiggle count on a notification bell or error shake |
| CustomBounce with squash（CustomBounce＋スクワッシュ） | `CustomBounce` squash ease driving scaleY next to the matching y ease, weaker after each bounce |

## Springs

GSAP has no spring ease; a spring here is a damped curve sampled into a fixed keyframe list, or a close named ease.

| Name | Built with |
| --- | --- |
| snap spring（指ではじく） | strong stiffness with heavy damping and little mass, baked into sampled keyframes |
| bounce spring（ボール） | stiff, light, low damping, sampled to keyframes or `elastic.out`, with a squash on landing |
| smooth spring（ダンパー付きの扉） | moderate stiffness, damping just enough to stop sway, sampled to keyframes |
| heavy spring（重い物） | large mass, moderate stiffness, strong damping, sampled to keyframes, for big cards and sheets |
| react-spring default（react-spring default） | spring with its default stiffness and damping, sampled |
| react-spring wobbly（react-spring wobbly） | low stiffness and low damping, sampled to keyframes, on a character or sticker |
| react-spring molasses（react-spring molasses） | large mass and large damping, sampled, for atmospheric background elements |
| Framer bouncy（Framer bouncy） | type spring with high stiffness and low damping, sampled, on a key add or success moment |
| Apple modal（Apple モーダル） | critically damped or nearly so, quick, sampled, on modals and sheets |
| critically damped（臨界減衰、揺れない最速） | damping exactly balancing stiffness, sampled, for precise positioning along a drawn path |
| summed springs（目標が変わるバネ、足し合わせ） | one spring per target change, their offsets added together on the timeline, position depending only on time |
| split-edge springs（伸びるタブ、前後で別のバネ） | each of the left and right edges gets a spring of its own, stiff on the front and soft on the back, swapped when direction flips, with width derived from the pair |
| spring vs tween（スプリング vs トゥイーン） | sampled spring keyframes for the first; an eased `to` with `expo.out` for the second |
| overshoot budget（オーバーシュートの予算） | an overshoot ease on the key element only, others on a no-overshoot ease, with the strength chosen by purpose |
| inertia / momentum（慣性、投げて止まる） | `InertiaPlugin`, or a decaying curve sampled to keyframes whose predicted end point is rounded to the grid |
| projectile（放物運動、Physics2D） | `Physics2DPlugin`, or linear x with a quadratic list for y, launch speed varied per particle from a seed |

## Timing and rhythm

| Name | Built with |
| --- | --- |
| duration by size（大きさで尺を変える） | duration set per element by its area in steps, on `power2.out` |
| distance-scaled duration（距離で尺を変える、√ の法則） | per-move duration derived from travel, rising slower than distance, bounded below by a floor and above by a cap |
| exit faster than enter（退場は登場より短く） | exit tween shorter than the entrance of the same item, ease-out in and ease-in out, with less travel on the exit |
| stagger: sequential（ステッガー：順番に） | `stagger: { each }` from the start on `power2.out`, with the gap narrowed as the total rises |
| stagger: from center（ステッガー：中央から） | `stagger: { from: "center" }` with the hero element placed centrally |
| stagger: from edges（ステッガー：両端から） | `stagger: { from: "edges" }`, the last-filled middle serving as the landing point |
| stagger: random（ステッガー：ランダム） | `stagger: { from: "random" }` with a seeded order list, the total kept short |
| stagger: grid diagonal（ステッガー：グリッド斜め） | `stagger: { grid, from: "start", axis: null }` with the starting corner chosen by from |
| snap, then hold（パッと出て、止めて見せる） | a very short tween followed by a short settle on `expo.out`, then an empty gap before the next |
| beat grid（拍のグリッド） | cut times computed on a grid from the track tempo and frame rate, major events set on the downbeat |
| speed ramp into a hit（スピードランプ） | ease-in tween ending in a short squash and a held frame, the impact on the downbeat |
| overlap levels（重なり、オーバーラップの量） | each next tween starts at an offset from the end of the previous one, held constant through a sequence |
| reading hold（読める時間を確保する） | a hold whose length follows the amount of text, between a short enter and exit |
| energy arc（エネルギーの弧） | durations and stagger gaps shrunk toward the peak, then relaxed in a short calm resolution |
