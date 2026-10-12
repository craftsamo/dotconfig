# Captions, telop and titles vocabulary: video builds

How each entry of [../telop.md](../telop.md) is built in a rendered video: a seekable timeline (HTML, CSS, SVG, GSAP or canvas) with seeded randomness and finite repeats, so every frame renders the same at any seek. A hover, click, drag or scroll is performed by the timeline as a drawn cursor, a finger or a moving page, never a real input. Read the entry's Looks like and The tell first; a build is the usual practice, not a rule.

## Captions and subtitles

| Name | Built with |
| --- | --- |
| pop-on subtitle（ポップオン字幕） | opacity set on at the cue time and off at its end, a small gap between consecutive cues |
| paint-on caption（ペイントオン字幕） | full line laid out first, per-char visibility set on word times, no reflow |
| roll-up caption（ロールアップ字幕） | line-block y step per arriving line using `power2.out`, a handful of rows, the eldest clipped at the top edge |
| live caption block（生字幕(2行ブロック)） | a fixed box of two lines, words added along the timeline, the entire box exchanged at the next cue |
| active-word highlight（現在語ハイライト字幕） | per-word colour and scale driven by word timestamps, `power2.out`, whitespace left intact |
| moving highlight pill（背景ピル移動） | pill x and width tween between word bounds with `power2.out`, text colour set on the active word |
| Hormozi-style pop captions（ショート動画ポップ字幕）, caption spring pop（字幕スプリングポップ） | per-word scale `back.out` or a spring with a slight stagger, tint and slant on the active word, a thick outline |
| forced-narrative fade sync（強制字幕のフェード同期） | per-cue opacity on cue times shifted to match the source fade, linear |
| RSVP word flash（RSVP 一語提示） | a single span with text set per word time, alignment by the key letter, longer holds on punctuation |
| phrase-aware line break（文節改行字幕） | line breaks placed at phrase boundaries computed offline with a phrase segmenter such as BudouX and stored, so the render stays deterministic, each line fading in with `expo.out` |

## Japanese typesetting and writing

| Name | Built with |
| --- | --- |
| bunsetsu phrase reveal（文節単位リビール） | text split at phrase boundaries; `Intl.Segmenter('ja')` yields words, not bunsetsu, so the phrase spans are precomputed offline with a phrase segmenter such as BudouX and stored so the render stays deterministic; a unit per stagger step with a small y rise and opacity, `expo.out`, spans decorative over the original sentence |
| punctuation-aware pause（約物ポーズ） | per-char opacity steps with extra gap inserted after punctuation, closing marks attached to the previous char, `steps()` timing |
| tategaki reveal（縦書きリビール） | `writing-mode: vertical-rl`, per-char y and opacity with `expo.out`, two-digit numbers set upright with `text-combine-upright`, a short per-char delay; the per-character split keeps a tate-chu-yoko run and a ruby group as single units |
| ruby sync reveal（ルビ同期リビール） | the base and its ruby group move as one unit with `power2.out`; only the `<rt>` element gets an opacity animation, starting a little later than the base, with no transform on it |
| IME kana-kanji conversion（かな漢字変換） | typed kana in a span with a thin underline, then the converted text with a thick underline or highlight on the active clause, then plain text with underline removed on commit, `steps()` per keystroke |
| kanji stroke order（漢字書き順） | stroke paths in order, each a stroke-dashoffset draw with `sine.inOut`, a short gap between strokes, round caps |
| brush calligraphy write-on（筆文字ライトオン） | variable-width stroke shapes under a path mask wider than the strokes, a `sine.inOut` draw per stroke with a short gap |
| manga onomatopoeia impact（擬音インパクト） | scale slam with `none` ease, a seeded decaying shake, radial lines on a separate layer, thick stroke copy, a slant |
| lyric motion tame/tsume（リリックモーション(タメツメ)） | an ease-in-heavy cubic-bezier tween after a hold, stepped at a low frame rate, seeded offset, tint for a couple of frames on landing |
| danmaku comment scroll（弾幕コメント） | per-comment lane and x from seeded start times, linear, finite list |
| extra-bold mincho card（極太明朝タイトルカード） | heavy serif weight, cards switched by opacity set on beats, scale pop on the closing card |
| Japanese subtitle by reading speed（日本語字幕(1秒4文字)） | cue length computed from character count, opacity set at cue times, no easing, line width capped per row |
| vertical subtitle（縦字幕） | `writing-mode: vertical-rl`, opacity set per cue, two-digit numbers set upright |
| handwritten-style film subtitle（手書き風映画字幕） | handwriting font, opacity set per cue, fixed per-glyph offsets |

## Titles and film

| Name | Built with |
| --- | --- |
| headline ribbon wrap（見出しリボンラップ） | text on a skewed or curved path, offset tween with `power2.inOut`, the back face shaded darker |
| slow tracking expand（スロー字間拡散） | letter-spacing tween on `none` ease across a long dwell, with a closing fade |
| fade-through-black card（フェードスルーブラック） | opacity on a black base up to full and back down using `sine.inOut`, with the next card queued behind the black |
| flash-frame card cut（フラッシュフレームカット） | each card a full-frame layer swapped with `tl.set` on a beat time; a white plate shown for a frame or two at the swap, then cut away; never more than 3 flashes in any one second, and no saturated red full-frame flash |
| perspective opening crawl（オープニングクロール） | a plane tilted with rotateX inside a perspective parent, `y` and scale tweened on `none` ease, opacity falling off near the top |
| bass-style racing credits（グラフィック線のクレジット） | line drawing with staggered text on linear motion, a skewed grid layer, and exits heading in opposing directions |
| sliced bars title（横線分断タイトル） | clipped bands with mirrored `x` offsets, a tight stagger, `expo.out` |
| scratched film jitter（フィルム傷とジッター） | seeded scratch lines, small `x`/`y` hops on `steps()`, an offset duplicate at low opacity |
| rubber-stamp cut-out pop（スタンプ切り絵ポップ） | scale pop on `steps()`, rotate, a rough knock-out mask, backdrop colour assigned per beat |
| light-leak title burn（ライトリーク焼き込み） | a blurred warm gradient layer using `mix-blend-mode: screen`, opacity swelling with `sine.inOut` |
| letterbox reveal（レターボックス開き） | a pair of bars tweened on `y` with `power2.inOut`, text fading in slightly afterwards |

## Broadcast and telop

| Name | Built with |
| --- | --- |
| lower third（ロワーサード） | three layers on offset starts, each plate wiping in on `expo.out` with its text masked within; the exit plays the stages backwards, quicker |
| news ticker crawl（ニュースティッカー） | a cloned row with `x` advanced linearly in integer pixel increments, wrapping at the width of one copy |
| breaking news banner（速報バナー） | bar `scaleX` with `power2.out`, colour swapping on the bar alone for several beats, label pop afterwards, then a hold |
| end credits roll（エンドクレジット） | a single tall column with `y` moved linearly in integer pixel steps per frame, overall duration set by the column's height |
| LED dot-matrix marquee（LED 電光掲示板） | a dot lattice with `x` moved by `steps()` per column, unlit dots drawn at low opacity, plus a glow duplicate |
| pop-in double-outline telop（二重フチのポン出しテロップ） | scale from zero past full size and back with `back.out`, three stacked stroke layers (inner white, outer colour, shadow) beneath the fill |
| shaking telop（揺れテロップ） | seeded per-char `x`/`y`/rotate offsets on `steps()`, applied just for the duration of the line, then easing back to rest |
| zabuton plate wipe（座布団ワイプテロップ） | plate `clip-path` or `scaleX` from the left with `expo.out`, text layer above it starting later, exit in reverse order |
| tsukkomi slam telop（ツッコミテロップ） | scale slam using `power2.in` with a small bounce, slight tilt, a seeded shake on the wrapper, speed lines in their own layer |
| sparkle-appear telop（キラキラ出現テロップ） | scale pop with `back.out`, a seeded sparkle layer around the text, a masked light sweep across the glyphs |
| comment-follow telop（コメントフォロー(話者色)） | outline colour assigned per speaker, `back.out` pop, a short wipe-in, hold timed to character count, summary text per line |
| side super（サイドスーパー） | `writing-mode: vertical-rl` strip or corner labels, a short slide-and-fade on the segment swap with `power2.inOut`, held for the segment |

## Layout and reflow

| Name | Built with |
| --- | --- |
| line break reflow（改行リフロー） | container width tween with FLIP on words, `expo.out` |
| counterweight headline（カウンターウェイト見出し） | two line layers, one offset left and one right of the final column, tweened toward it on `power2.inOut` with the same start; a mask clips each at the frame edge |
| fit-to-width title（幅ぴったり見出し） | per-line scale derived from measured ink width with `power2.inOut`, measured once the font has loaded |
| stacked justified words（均等幅スタック） | per-row font size taken from measured ink bounds, each row sliding up from beneath with `power2.out` |
| layout-animated word swap（レイアウト追従ワード入替） | FLIP on siblings with a soft spring-like ease, the old word exiting upward and the new one entering from below |
| anagram FLIP（アナグラム並び替え） | FLIP per letter between two layouts along arcs, `power3.out`, a slight stagger |
| balanced wrap reflow（バランス改行と再分割） | width tween with balanced wrapping, FLIP on words, `expo.out` |
| line-spacing collapse（行間の収束） | one text block whose line-height tweens from open to tight on `power2.inOut`, anchored at its first line so the head stays put; ends on a still hold |
| kinetic camera follow（カメラ追従キネティック） | a camera wrapper with position, rotation and scale keyed to phrase positions, a strong ease-in-out, a brief hold on each arrival |
| truncate expand（省略から全文展開） | height tween with the ellipsis swapped out, FLIP on the content below |
