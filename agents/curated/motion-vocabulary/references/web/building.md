# Building motion on a real web page

Read this before the web rows of an area. The names files say what each motion
looks like and what tells it apart; the `web/<area>.md` rows say how a real page
starts it, builds it and calms it for people who ask for reduced motion.

## Workflow

1. Read the project first: framework, existing animation library, motion
   tokens (durations, easings) and how components already animate. Do not add
   a library for an effect plain CSS can do.
2. Name the motions. Map the person's words — a Japanese or English name, or a
   feel such as 弾む — to entries through the Name cell's aliases and the Feel
   column. Pick by what starts the motion: a heading that plays on load is a
   text entry, the same heading revealed as its section enters is a scroll
   entry. A page usually spans several areas: an LP hero is text, its
   sections are scroll, a bounce comes from elements or timing, a tab or
   toggle is ui-controls. Open each area the request touches and combine
   entries (a scroll-triggered stagger plus an overshoot entrance makes "cards
   bounce in one by one"). Write the chosen names into the plan or PR
   description so the effect is reviewable. If two entries share an alias,
   pick by the Looks like cell and name the chosen entry explicitly.
3. Pick the trigger and the smallest tool that does it: CSS (transitions,
   keyframes, scroll-driven animations, View Transitions, `@starting-style`)
   before the Web Animations API, and a library (GSAP ScrollTrigger, Motion)
   only for what needs it, such as pinned scrubbed sequences or layout
   animation. For scroll, decide once-on-enter, scrubbed with progress, or
   pinned while a sequence plays.
4. Implement on `transform` and `opacity` (plus `clip-path` or `filter` where
   the effect is about them); measure-then-animate (FLIP) instead of animating
   layout properties; keep content visible when JavaScript or a newer CSS
   feature is missing (apply the hidden start state only behind `@supports` or
   after the script runs).
5. Give every entry its Reduced motion form under
   `@media (prefers-reduced-motion: reduce)` (or `matchMedia` in script).
   Content and state stay reachable; parallax, zooms, large travel and
   scroll-jacking go; loops that run longer than five seconds get a pause
   control; nothing flashes more than three times a second.
6. Verify in a browser: the motion matches the named entry's Looks like;
   reduced motion emulated in DevTools shows the reduced form; no layout shift
   or long tasks appear in the performance panel; keyboard focus stays
   visible; touch devices get an equivalent where the trigger is hover; a
   non-supporting browser gets the documented fallback.

## Typical values by feel

Used only when the project has no motion tokens of its own:

| Feel | Japanese | Typical web values |
| --- | --- | --- |
| smooth | なめらか | 250–400 ms; `cubic-bezier(0.22, 1, 0.36, 1)` for arrivals, `cubic-bezier(0.65, 0, 0.35, 1)` for moves |
| snappy | きびきび | 120–220 ms; `cubic-bezier(0.2, 0, 0, 1)`; exits shorter than entrances |
| soft | やわらかい | 300–500 ms; `cubic-bezier(0.37, 0, 0.63, 1)`; travel of a few px |
| heavy | 重い | 450–800 ms; `cubic-bezier(0.76, 0, 0.24, 1)`; reserved for large elements |
| bouncy | 弾む | spring (Motion `stiffness: 300, damping: 20`), `cubic-bezier(0.34, 1.56, 0.64, 1)` or a `linear()` spring curve |

These values are the web build's business; the names files and the video
builds stay free of numeric defaults.
