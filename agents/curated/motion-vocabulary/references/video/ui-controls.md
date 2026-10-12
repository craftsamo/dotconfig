# Interface controls vocabulary: video builds

How each entry of [../ui-controls.md](../ui-controls.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

## Web interaction

| Name | Built with |
| --- | --- |
| hover lift（ホバーリフト） | drawn cursor arrives, then y, scale and `box-shadow` tween together on `power2.out`; the exit is the same tween reversed, a touch quicker |
| magnetic button（マグネティックボタン） | button x and y written per frame as a fraction of the drawn cursor's timeline position relative to the button, zero beyond a set radius (a pure function of time), the return on keyframes on `power3.out` after the cursor's drawn exit |
| pointer tilt（ポインターチルト） | `rotateX` and `rotateY` from the cursor's offset inside a `perspective` parent, computed per frame from the drawn cursor's timeline position with a fixed time delay, cursor positions drawn |
| cursor follow（カーソル追従） | follower elements whose position at time t is the drawn cursor path at t minus a fixed delay, each further dot with a longer delay and drawn smaller |
| drag inertia（ドラッグ慣性） | a tween with a long ease-out on `power3.out` whose distance is set from the release speed of the drawn drag path (computed in advance) and clamped to the bounds |
| click ripple（クリックリップル） | a circle at the click point scaled up and faded out on `power2.out`, clipped by the button's mask |
| toggle morph（トグルモーフ） | knob width and x tween on `back.out`, track colour tween halfway through the travel; core: `toggle / switch` |
| accordion open（アコーディオン展開） | height tween from zero to the content height on `power2.inOut`, chevron rotation in step, lower items following the edge |
| button fill hover（ボタン塗りホバー） | a pseudo-element's `scaleX` from zero to full with its origin at the entry side on `power2.out`, text colour swapped at the same moment |
| icon morph（アイコンモーフ） | SVG path morph between two path sets of equal point count, or three bars tweened with the middle bar scaled out, on `power2.inOut` |
| card spotlight（カードスポットライト） | a radial gradient centred on the drawn cursor position, with the position read from the drawn cursor path at the current time and opacity eased in on arrival |
| drag snap（ドラッグ吸着） | drag path, then a short `back.out` from the release point to the slot position, a slot highlight drawn in step |
| card stack fan（カードを広げる） | per-card rotate and x from the pile origin with staggered starts on `back.out`, the top card given the extra overshoot |
| tooltip（ツールチップ） | scale and opacity from the pointer side on `power2.out`, transform origin at the arrow, a faster reverse on exit |
| human cursor path（カーソルは弧を描いて動く） | the cursor on an arc path (`MotionPath` or a quadratic point list) on `sine.inOut`, a short pause, then the click |

## UI buttons

| Name | Built with |
| --- | --- |
| bounce press（バウンスプレス） | a cursor or finger lands, scale on the button tweens down quickly, then back up on `back.out` or `elastic.out` to rest at the original size |
| jelly squash（ジェリースカッシュ） | scaleX and scaleY driven as an opposed pair, squashed on contact, released on `elastic.out` so the pair overshoots alternately before resting |
| tap ripple（タップリップル） | a circle placed at the tap coordinates scales up while its opacity falls, clipped to the button, with a small scale dip and return on the button |
| pulse glow（パルスグロー） | a blurred copy behind the button with scale and opacity on a slow in-out ease, repeated a finite number of times so it ends dim |
| fill sweep（フィルスイープ） | a pseudo-element layer slides in by x or grows by scaleX behind the label, text colour tweened in step, nothing returns afterward |
| send morph（送信モーフ） | width collapses with the label fading, then the icon moves in x and y along a curved path on `expo.out`, finally fading out of frame |
| 3D push（3Dプッシュ） | the face layer moves down in y over a fixed edge layer on a soft in-out ease with a cursor press, returning on release |
| confetti burst（紙吹雪バースト） | seeded pieces with radial outward tweens, a gravity pull on y and individual rotation, finite length and fully faded at the end |
| hold to confirm（長押し確定） | a cursor presses and holds, scaleX of a fill layer runs across the hold, then label and colour swap on a short ease-out |
| border draw（ボーダードロー） | an outline path with stroke-dashoffset from full to zero, then a small scale kick on `back.out` as the line closes |
| shine sweep（シャインスイープ） | an angled soft-edged highlight layer moves in x across the button, masked to its shape, with a gentle in-out ease and a single run |
| loading to success（読込から成功） | spinner fades and scales out, a check path draws with stroke-dashoffset, button colour tweens, label swapped at the beat |
| icon swap（アイコンスワップ） | outgoing icon rotates and scales down while the incoming starts rotated and small and grows, offset so they overlap at the middle |
| heartbeat（ハートビート） | scale keys for a big beat and a smaller beat, then a pause, repeated a finite number of times with an ease-out on each swell |
| wobble tilt（ウォブルチルト） | rotate keys of decaying size around the centre, released on `elastic.out` to end at zero tilt |
| elastic drag（エラスティックドラッグ） | a drawn finger moves away, scale and skew on the button follow its distance, then release on `elastic.out` back to the origin |
| inner press（インナープレス） | inset shadow tweened in while the outer shadow fades, combined with a small scale down, then released in reverse on a smooth ease |
| colour splash（カラースプラッシュ） | a circle at the touch position scales up beyond the corners, clipped to the button, on an in-out ease, with the label colour swapped late |
| breathing gradient（呼吸グラデーション） | an oversized gradient background with background-position tweened back and forth on a gentle ease, repeated a finite number of times |
| button press（ボタンを押す） | core: `button press` |
| one shape, never cut（1 つの形が変わり続ける） | width, height and radius on spring-like eases in step, content layer blurring out and in, cleared before the next morph starts |

## Selection and controls

| Name | Built with |
| --- | --- |
| springy switch（スプリングスイッチ） | knob x on `elastic.out`, track colour tween on a short ease, both started at the moment of the drawn click |
| day and night（昼夜トグル） | knob x, a sun-to-moon path morph, background colour tween, seeded stars fading in on offset starts |
| liquid stretch（リキッドストレッチ） | knob width stretch then x settle, a goo filter over the knob and track pair, finishing on `back.out` |
| check draw（チェック描画） | a path with stroke-dashoffset from full to empty on `power3.out`, the short leg before the long leg |
| heart like（ハートいいね） | scale pop on `back.out`, fill colour tween, a seeded ring of small particles moving outward and fading |
| lock and unlock（ロック解除） | shackle y and rotate about its pivot on `expo.out`, body nudged slightly at the instant of release |
| mute pop（ミュートポップ） | wave paths scaling and fading out in sequence, slash stroke-dashoffset from full to empty, a small pop on the speaker body |
| play and pause（再生停止モーフ） | SVG path morph between the two shapes with equal point counts on an in-out ease, played in reverse for the way back |
| sliding underline（スライド下線） | one bar with x and width tweens between target boxes, a drawn cursor arriving at each item, on an in-out ease |
| pill indicator（ピルインジケーター） | pill x and width tweens on `back.out`, the label colour swapping as the pill arrives |
| bubble expand（バブル展開） | width, height and radius tweens on `back.out`, the content layer fading in a beat later |
| jumping dot（ジャンプドット） | dot y arc between item positions, a small scale squash on arrival, the next hop starting from the new item |
| liquid blob（リキッドブロブ） | two circles with a goo filter, the lead moving first and the follower catching up, ending on `back.out` |
| tint shift（ティントシフト） | colour tween on the selected item on `power2.out`, opacity on the others, started together at the drawn click |

## Forms and state

| Name | Built with |
| --- | --- |
| floating label（フローティングラベル） | label y and scale tween on `power2.out` at the focus time, border colour in step |
| checkbox stroke（チェック線描画） | box fill tween, then path `stroke-dashoffset` on `power2.out` after a short delay |
| switch state spring（スイッチ状態スプリング） | knob x on `elastic.out`, scaleX squeeze in transit, track colour tween timed to arrival |
| inline validation（インライン検証） | border colour tween with the message y and opacity on `power2.out` |
| submit success morph（送信成功モーフ） | width and radius tween to a circle on `power3.inOut`, label out, then check draw |
| upload progress state（アップロード状態遷移） | bar fill, text swaps at keyed times, tick fading in at completion |
| password strength（強度メーター） | per-segment fill steps tied to the typed length, colour changing by level |
| skeleton resolve（スケルトン解決） | the content layer's opacity and y over the skeleton on `power2.out`, skeleton faded out |

## Gesture and mobile

| Name | Built with |
| --- | --- |
| swipe dismiss（スワイプ退場） | card x and rotate along the drawn finger path, then out on `power3.in`, FLIP of the rest of the list |
| swipe actions reveal（スワイプ操作露出） | row x tween with the action layer beneath, buttons scaling in on `power2.out` |
| long press progress（長押し進行） | finger down, `stroke-dashoffset` over the hold on `none` ease, then the state change |
| pull to refresh（引いて更新） | list y with resistance, spinner rotation, then a `back.out` return |
| drag pickup（ドラッグ持ち上げ） | scale and `box-shadow` tween on `power2.out` at finger down |
| reorder drag（並べ替えドラッグ） | dragged y keys from the finger path, FLIP of the displaced rows on `power2.out` |
| bottom sheet drag（ボトムシート追従） | sheet y from the finger path, then an ease into the nearest stop on `power3.out`, backdrop opacity tied |
| pinch zoom（ピンチズーム） | two drawn touch dots moving apart, scale with `transform-origin` at their midpoint |

## Loading and data

| Name | Built with |
| --- | --- |
| skeleton shimmer（スケルトンシマー） | an angled gradient band, x tween on `none` ease, clipped to the blocks, with a finite number of repeats |
| spinner arc（スピナーアーク） | SVG circle `stroke-dasharray` swinging with a constant rotation, finite repeats |
| progress fill（進捗バー） | `scaleX` from zero to the value on `power2.inOut`, origin on the left; core: `progress bar / ring` |
| circular progress（円形進捗） | `stroke-dashoffset` of the ring from the full length to the value with a count-up in the centre on `power2.inOut` |
| chart draw（チャート描画） | path `stroke-dashoffset` on `power2.out`, per-point scale pops staggered against the pen position |
| toast stack（トーストスタック） | each toast y and scale in on `power3.out`, older ones offset by one step; core: `notification toast stack` |
| success check draw（成功チェック描画） | two paths with `stroke-dashoffset` on `power2.out`, the tick starting after the circle |
| staggered bar chart（棒グラフ順次成長） | `scaleY` from the baseline with origin at the bottom, starts staggered on `power2.out` |
| donut segment draw（ドーナツ分割描画） | per-segment `stroke-dashoffset` with a running start offset on `power2.inOut`, centre value fading in late |
| optimistic update（楽観的更新） | the state change keyed at the click time, a second quiet tween when the confirmation arrives |

## Loading and progress

| Name | Built with |
| --- | --- |
| bouncing dots（バウンドドット） | per-dot y with `bounce.out` on offset starts, repeated a finite number of times |
| gradient arc（グラデーションアーク） | a conic gradient mask or gradient stroke rotated on a linear ease, a finite number of turns |
| progress to success（進捗から成功） | fill scaleX, width collapse to a circle with radius, check path draw on a smooth ease |
| typing indicator（入力インジケーター） | per-dot y keys with offset starts, a finite number of repeats; core: `chat bubbles` |
| equalizer bars（イコライザーバー） | scaleY from the baseline using a seeded list of keys per bar, ended with a finite repeat count |
| orbit trail（オービットトレイル） | a dot on a circular path with trail copies lagging behind at falling opacity, a finite number of turns |
| indeterminate bar（不定のバー） | a segment x moving across and beyond a track on an in-out ease, repeated a finite number of times |
| pulse ring（脈打つ輪） | circle scale and opacity tweens with a second ring delayed, finite repeats; core: `pulse ring` |
| morphing squares（四角が入れかわる） | FLIP-like x/y tweens per square in sequence, rotation keys, a short pause between moves |

## Feedback and reactions

| Name | Built with |
| --- | --- |
| heart burst（ハートバースト） | seeded hearts with y rising, x drift and opacity falling, started together from the tap, finite |
| star rating（星評価） | per-star fill tween with a stagger, a small scale pop on each, stopping at the target index |
| clap counter（拍手カウンター） | a count step per drawn tap with a scale bump on `power2.out`, a small spark particle on each |
| emoji bar（絵文字バー） | a stagger of scale-in on `back.out`, then a hover scale on the pointed emoji as the cursor arrives |
| number ticker（数値ティッカー） | per-digit masked column y on `expo.out`; core: `odometer digits` |
| confetti rain（紙吹雪レイン） | seeded pieces with y falling, x sway and rotation, finite duration, all off frame at the end |
| toast（トースト通知） | y and opacity in and out, a slower arrival and a faster exit; core: `notification toast stack` |
| dynamic island（ダイナミックアイランド） | width, height and radius tweens with a springy feel, content fading in later and out first |
