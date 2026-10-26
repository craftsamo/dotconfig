# Painted Anime

Intent: a gentle, wide-open story told like a hand-drawn feature film -
weather, light and place carry the feeling; suits cel-style cast art
(fine even line, flat fills, one hard-edged shadow tone), such as a
generate-mascot `anime-2d` anchor and its poses.

World: backgrounds painted with visible brush texture and atmospheric
depth - skies with soft-edged clouds, foliage and buildings in layered
planes, haze growing lighter with distance, natural light from one
side - behind a crisp cel cast that never takes the paint texture. The
richest result uses painted background plates supplied in `assets`
(an image-creator illustration is the dependency request when none
exist); without them, build each depth plane in SVG with a fixed-seed
brush-texture mask and a low-opacity haze layer, never re-randomised
per frame. Keep the far planes calmer and less saturated than the cast
so the characters read first.

Acting and camera: unhurried - held poses with secondary motion in the
world (grass, cloud, curtains, steam) on twos; a pose swap lands on the
beat and then rests. Slow pans across wide plates, gentle parallax
between depth planes, a slow push toward the cast at the emotional
beat; wind rising before a turn in the story. Cuts are calm; a
dissolve through light can carry a change of time.

Type: understated subtitle captions low in the frame; never decorative
lettering over the painting.

QA: the cast stays crisp cel art on top of the painted world - the two
layers read as one frame, not a sticker on a painting, and the paint
texture never covers the cast; the light side of the world agrees with
the cast's shadows; textures do not flicker; secondary motion never
competes with a speaking character.
