# Plan — video-creator: motion

Read [common plan](../../SKILL.md) first.

`create-motion` is the served route for authored motion design: a launch or
promo piece, brand/sizzle video, feature reveal, kinetic typography or logo
sting that VideoCreator designs and draws itself in HTML/CSS/SVG/GSAP,
3..60 seconds at 30fps (16:9 default, 9:16, 1:1, 4:5). It is checked before
the legacy `creator-html-motion` table row. It is not a UI task walkthrough
([create-tour](tour.md)), a CTA/claims advertisement from approved assets
([create-ad](ad.md)), a learning explainer
([create-explainer-video](explainer-video.md)) or model-generated footage
([generate-clip](clip.md) / [generate-music-video](music-video.md)).
"Reproduce this video" / "make one like this" with a motion-graphics
reference is this leaf with `reference_use: reproduce` or `inspiration`.

Settle with the client only what changes the piece: `subject`, `what_for`
(purpose, destination, viewer), aspect/duration if not obvious, any exact
copy they fix, supplied assets, and the look/energy in their words. Do not
ask the client for a storyboard, a shot list or timings: VideoCreator
proposes them. A reference video is read locally; it never authorizes an
upload. Reproducing a third-party brand, logo or copy needs the client's
permitted-use statement (for example "internal study, not published"),
relayed verbatim in `note`; without it, the form says `inspiration`.

Plan the dependencies up front. VideoCreator draws vectors and UI itself but
has no image generation, TTS, music or SFX. Tell the client the expected
units: the storyboard approval, then audio-creator's soundtrack (music
and/or SFX, usually a Mix master) scored to the approved storyboard's audio
plan, then any raster asset the storyboard lists as pending through the
fitting image-creator leaf. Each is its own released unit with its own
budget/approval; generating them does not ride on the storyboard approval.
A piece the client wants silent is `audio: none` in the storyboard, stated,
not assumed.
