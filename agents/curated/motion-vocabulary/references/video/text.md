# Text motion vocabulary: video builds

How each entry of [../text.md](../text.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

## Reveal

| Name | Built with |
| --- | --- |
| line-by-line reveal（行ごとのリビール） | split into line spans; each line gets the same small upward y and an opacity rise, started a short beat apart, with `power2.out` |
| word ghost reveal（移動量が減っていく語の出現） | per-word y offsets read from a list that decays with word index, each word on `expo.out`, starts only a couple of frames apart |
| kinetic lines on verbs（動詞で行が立ち上がる） | each line holds hidden below its spot; at its verb's timestamp a short y and opacity tween on `power3.out` brings it up |
| character fade up（文字フェードアップ） | per-char spans with a modest y offset and opacity starting at zero, a constant small stagger, `power3.out`; the whole line is timed to finish within a single beat |
| word fade up（単語フェードアップ） | per-word spans, or per-phrase spans whose Japanese phrase offsets are precomputed offline with a phrase segmenter such as BudouX and stored so the render stays deterministic, a small y and opacity tween, a slightly longer stagger than the letter version, `power2.out` |
| slide down by character（文字スライドダウン） | per-char y from negative to zero with opacity, stagger spread so the whole row fills in a set time, `power2.out` |
| alternating line reveal（行ごと交互方向リビール） | every line sits in a clipping mask; y from plus or minus a full line to rest on `power2.inOut`, staggered line starts, then letters on a tiny seeded stagger |
| stretch rise（伸縮せり上がり） | per-char y from below with scaleY large and scaleX narrow easing to one, transform-origin at the baseline, small stagger, `back.out` |
| vertical unfold（縦方向展開） | per-char scaleY from nearly flat to full, pivot pinned to the top, a small stagger, `back.out` |
| converge from spread（中央へ収束） | per-char x from an offset scaled by distance from the middle down to zero, stagger ordered from centre, `power1.inOut`, parent clipped so edges do not leave the frame |
| center-out reveal（中央から外へ展開） | per-char opacity from zero with a delay scaled by distance from centre, brief easing per letter, `power2.out` |
| scatter assemble（散乱から集合） | seeded start x, y and rotate per char to the true layout, small stagger in shuffled order, `power1.inOut` |
| random tilt scale in（ランダム傾きズームイン） | seeded rotate list from a slight tilt to zero, scale from smaller to full, per-char stagger, `power4.out` |
| smear stretch in（スミア伸長イン） | per-char x from far left, rotate and scaleX large easing to rest, origin at the right edge, negative stagger, `power2.out` |
| elastic scale pop（弾性スケールポップ） | per-char scale from zero on `elastic.out`, a small stagger, origin low in the glyph, ending exactly at full size |
| range selector soft wave（レンジセレクター・ソフトウェーブ） | per-char progress from a falloff window moved along the line by a single shared tween, linear sweep, opacity and small y mapped from progress |
| random-order fade（ランダム順フェード） | seeded shuffled index list used as the stagger order, opacity from zero per char with a short ease, `power1.out` |
| grapheme-safe emoji pop（絵文字混じりポップ） | text segmented into graphemes with a span per cluster, scale from zero using a spring-like `back.out`, small stagger |

## Exit

| Name | Built with |
| --- | --- |
| character exit up（文字上抜けアウト） | per-char y to above the slot inside an overflow-hidden wrapper, opacity down, a tiny stagger, `power3.in` |
| fade down out（文字フェードダウン退場） | per-char y a short way down with opacity to zero, stagger from the end, ease-in `power1.in` |
| blur evaporate out（ブラー蒸発アウト） | per-word blur up, y slightly upward, opacity to zero, stagger in reverse order, `power1.out` |
| explode scatter out（爆散アウト） | seeded radial x, y and rotate per char with opacity to zero, short stagger from centre, `power3.out`, split reverted afterwards |
| gravity drop out（重力落下アウト） | per-char y past the bottom of the frame with a slight seeded rotate, shuffled stagger, `power2.in`, parent clipped |
| scale-down vanish（縮小消滅） | per-char scale to zero with origin at the glyph centre, small stagger, `power2.in` |
| reverse-order erase（逆順消去） | the entrance tween reversed with the stagger starting from the end, same duration and ease run backwards |
| collapse to center（中央へ吸い込み） | per-char x moved toward the centre computed from each letter's position, scale to zero, stagger from the edges, `power3.in` |
| noise dissolve（ノイズ溶解） | a seeded noise mask whose threshold is tweened linearly, or `feTurbulence` plus a displacement or threshold filter on the text layer |

## Emphasis

| Name | Built with |
| --- | --- |
| focus word explosion（注目語エクスプロージョン） | scale pop with `back.out`, plus a small seeded particle burst drawn as a separate layer behind the word |
| emphasis slam（強調のスラム）, slam-in title（スラムイン） | scale from oversized down to rest, heavy spring ease, a brief seeded shake on the wrapper at the contact frame |
| elastic type（伸び縮みする文字） | scaleX with a slight scaleY drop and tracking driven by a spring, origin at the baseline, returning to rest |
| falloff bump wave（バンプウェーブ） | per-char scale derived from a cubic falloff on the gap to a point sliding linearly along the line, a single pass |
| jelly rubber band（ゼリー・ラバーバンド） | alternating scaleX and scaleY keyframes with decaying amplitude, origin at the bottom, a small per-letter offset |
| keyword punch（キーワードの打ち込み） | fast scale overshoot landing above the rest size, colour shifted to the accent, other words faded in opacity, `power1.out` |
| wiggly jitter（ウィグリー揺らぎ） | seeded small x, y and rotate offsets per char updated in discrete steps with `steps()`, stopping after a short while |
| pointer highlight box（ポインタ付き強調枠） | a drawn cursor tweened along the diagonal, the box width and height tweened to the text bounds, `power1.inOut` |
| comic pop（コミック・ポップ） | scale from smaller and tilted to rest on `back.out`, heavy stroke, a solid offset shadow copy, a dot pattern layer |
| strike and correct（取り消し線で訂正） | strike line scaleX from the left, old word opacity dimmed but kept, new word scale pop on a delay with `back.out` |

## Swap

| Name | Built with |
| --- | --- |
| glyph slot roll（グリフスロットロール） | masked glyph column, y tween ending on the target row, `power2.inOut`, a small stagger between letters |
| letter flip（文字のフリップ） | per-char rotateX with two faces and `backface-visibility`, letters offset by a few frames, `power2.inOut`, swap at the half-turn |
| split-flap board（スプリットフラップ(パタパタ)） | upper and lower half per cell, `rotateX` steps with a chaining delay, monospace face for alignment, short ease-in on each flap |
| rotating text (spring)（回転テキスト(文字スプリング)） | per-char y exit and entry using `back.out`, slight stagger, container width tweened on the matching spring |
| flip words（フリップワード(ブラー)） | exit tweens y, x, scale and blur together; entrance takes per-char blur down to zero with a stagger on `power2.out` |
| gooey morphing text（グーイー・モーフ） | two stacked layers cross-faded with blur proportional to the remaining fraction, a contrast threshold filter on the group, a hold after each word |
| cube rotate swap（キューブ回転で切替） | `rotateX` on a 3D box inside `perspective`, faces offset outward by half the line height, `power1.inOut` |
| skew swipe（スキュースワイプ） | x and skewX tweened on both layers, old with an ease-in, new with `expo.out`, skew resolving in the final frames |
| letter cascade swap（文字カスケード入替） | per-char y exit plus fade on `power3.in`, new word y from above on `power3.out`, slight offset between the words |
| diff text replace（差分だけ打ち替え） | common prefix and suffix preserved, per-char opacity switches across the differing span at an even interval, no easing |

## Typing and decoding

| Name | Built with |
| --- | --- |
| terminal decode（ターミナルデコード） | seeded glyph list per char, resolve by index along each line, a prompt span fixed in front, a short `back.out` settle as every line locks |
| type and backspace loop（タイプ&バックスペース） | per-char opacity sets forward then back at a faster pace, a hold between phrases, a finite loop that ends on the last phrase |
| humanised typewriter（人間らしいタイプ） | a seeded list of per-char gaps with extra delay after punctuation, applied as stepped opacity sets so the pattern repeats exactly on every render |
| terminal type and scroll（ターミナル風） | line block y stepped by one line height per new line on a brief `power2.out`, per-char typing for command lines, output lines set at once, a block cursor at the end |
| decrypt from center（中央から復号） | per-char scramble re-randomised on a short interval, resolve order by distance from centre, cipher glyphs in a monospace face and different colour |
| per-char flicker in（記号フリッカー出現） | seeded symbol swaps on a frame step, final glyph held, each char's start chained slightly after its left neighbour |
| slot shuffle（スロット・シャッフル） | fast per-char cycling inside masked windows, staggered stop times, `power3.out` deceleration onto the right glyph, `back.out` on the final stop |
| character offset cycle（文字コード送り） | per-char index counting down from a starting offset to the target, wrapped inside its own script, a ramp across the line, `power1.out` |
| placeholder replace（伏せ字から置換） | placeholder glyphs swapped per char on a stagger, an accent colour on the newest character for a short beat before it joins the body colour |

## Mask and clip

| Name | Built with |
| --- | --- |
| masked character rise（文字マスク・せり上がり） | per-char wrapper `overflow:hidden`, y from fully below to zero, a very small stagger, `power3.out` |
| masked horizontal slide（横スライドイン(マスク)） | per-char wrapper with overflow clipping, an inner x tween on `expo.out` |
| split-halves slide（上下分割スライド） | stacked clipped copies cut at the optical centre, x from opposing sides to zero on `expo.out`, one copy hidden from the text layer's reading order |
| soft gradient mask wipe（ソフトマスク・ワイプ） | `mask-image` linear gradient with its position tweened, `power2.out`, the exit continuing in the same direction |
| bar wipe reveal（バーワイプ出現） | bar scaleX up then origin flip and down, text clipped to the trail, per-line starts a few frames apart |
| shape-mask transition（形状マスク切替） | `clip-path` shape tween ease-in, text swapped while the shape covers the frame |
| venetian blinds reveal（ブラインド・リビール） | a set of strips with staggered scaleY, `power2.out`, whole-pixel heights |
| diagonal cut reveal（斜めカット・リビール） | `clip-path: polygon()` tween with `expo.out`, matching vertex counts at both ends |

## Blur and focus

| Name | Built with |
| --- | --- |
| text generate effect（テキスト生成エフェクト） | per-word opacity and blur to zero with a stagger, `power2.out` |
| 3-step blur in（3段ブラーイン） | blur keyframes in stages with y, each segment on `power2.out` |
| random blur in（ランダムブラーイン） | seeded index order for a blur stagger, blur to zero, `power1.inOut` |
| blur and tracking build（ブラー&トラッキング出現） | letter-spacing and blur tweened together with different offsets, `power2.out` |
| directional blur slide（方向ブラースライド） | x tween with an x-only `feGaussianBlur` driven by velocity, `expo.out` |
| scale blur zoom in（スケールブラー・ズームイン） | scale and blur tweened together on one custom bezier-like ease |
| true focus（トゥルーフォーカス枠） | a blurred layer, a bracket frame tweened to word bounds with a pause per word |
