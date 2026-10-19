---
name: motion-vocabulary
description: >-
  Use when naming or building motion: a video storyboard, a creative direction
  or a revision, or animation on a real web front end such as a landing page
  or app UI (スタッガー, パララックス, スティッキー, スクロールスナップ, ロワーサード,
  「弾む感じ」, 「もっと重く」, 「おしゃれに動かして」, "name the transition", "turn
  this feedback into named changes", "scroll-triggered reveal", "pin and
  scrub", view transitions, GSAP ScrollTrigger, Motion / Framer Motion, CSS
  scroll-driven animations). A dictionary of named motions with Japanese
  aliases, feel words and the detail that tells each apart, plus how each is
  built in a rendered video and on a real page with its reduced-motion form;
  never a rulebook. Not for rendering a video itself, choosing a visual
  direction (palette, type) or measuring an existing UI's polish.
license: MIT
---

<Goal>

Give a storyboard author, a creative advisor, a video producer or a front-end
developer one shared name for each motion, so a plan says "mask reveal (line
rise)" or "sticky" instead of "fade in" or "make it move nicely", and whoever
builds it, in a rendered video or on a real page, knows what the viewer
should see and what makes it read as itself.

</Goal>

<Read>

Naming (a storyboard, a direction, a revision): read
[references/core.md](references/core.md), then only the file below that the
current decision needs. Each entry gives its Feel, what it is usually For, what
it Looks like and The tell, the detail that sets it apart from a near
neighbour. Write the entry's name, and when the result could come out generic,
its tell.

Building a rendered video: for every entry the approved plan names, read its
row in the matching `references/video/` file.

Building a real web page: read
[references/web/building.md](references/web/building.md) (workflow, reduced
motion, typical values), then the rows of the named entries in the matching
`references/web/` file.

A described feel (なめらか, きびきび, やわらかい, 重い, 弾む) maps to entries through
the Feel column; the five words are defined in
[references/timing.md](references/timing.md) "## Feel". Japanese names in
parentheses are aliases for finding an entry from a Japanese request; either
name works.

| Deciding | Names | Video builds | Web builds |
| --- | --- | --- | --- |
| what most films use: text basics, transitions, camera, sound sync, components, compositions, film structures, visual metaphors | [core.md](references/core.md) | [video/core.md](references/video/core.md) | [web/core.md](references/web/core.md) |
| a drawn look, texture, light, glow or finishing effect | [looks.md](references/looks.md) | [video/looks.md](references/video/looks.md) | — |
| weight and physics on anything, characters or UI cards alike: squash and stretch, anticipation, spring settle, follow-through, walk, blink, loops | [character.md](references/character.md) | [video/character.md](references/video/character.md) | — |
| speed, easing, springs, rhythm, or a described feel | [timing.md](references/timing.md) | [video/timing.md](references/video/timing.md) | [web/timing.md](references/web/timing.md) |
| how one element or a group enters, moves, scales, rotates, reacts or takes attention | [elements.md](references/elements.md) | [video/elements.md](references/video/elements.md) | [web/elements.md](references/web/elements.md) |
| charts, maps, drawn paths, diagrams and number moments | [data.md](references/data.md) | [video/data.md](references/video/data.md) | [web/data.md](references/web/data.md) |
| how words appear, leave, swap, type out or take emphasis | [text.md](references/text.md) | [video/text.md](references/video/text.md) | [web/text.md](references/web/text.md) |
| a treatment inside the letters: physics, path, colour, glitch, depth, variable fonts, counters | [text-styling.md](references/text-styling.md) | [video/text-styling.md](references/video/text-styling.md) | [web/text-styling.md](references/web/text-styling.md) |
| captions, subtitles, telop, film titles, Japanese typesetting (縦書き, ルビ, 文節) | [telop.md](references/telop.md) | [video/telop.md](references/video/telop.md) | — |
| a scrolling page or LP: sticky, pin and scrub, parallax, snap, scrollytelling, scroll-driven text | [scroll.md](references/scroll.md) | [video/scroll.md](references/video/scroll.md) | [web/scroll.md](references/web/scroll.md) |
| buttons, toggles, forms, gestures, loaders, toasts and reactions in an interface | [ui-controls.md](references/ui-controls.md) | [video/ui-controls.md](references/video/ui-controls.md) | [web/ui-controls.md](references/web/ui-controls.md) |
| page transitions, overlays, spatial and depth UI, material and surface motion in an interface | [ui-space.md](references/ui-space.md) | [video/ui-space.md](references/video/ui-space.md) | [web/ui-space.md](references/web/ui-space.md) |
| a game screen: HUD, hits, rewards, quests, game cinematics | [game.md](references/game.md) | [video/game.md](references/video/game.md) | — |

</Read>

<Discipline>

The vocabulary describes; it never prescribes. It adds no numeric default,
avoid-list, score or required motion count, and a more precise name of your
own is always fine. A look or effect never re-renders supplied art, a cast or
a logo. Only the web builds carry typical values, because a shipped page needs
them and the project's own motion tokens still win.

</Discipline>
