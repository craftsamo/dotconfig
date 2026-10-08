# Rendered Web UI - Client guide

Use with the site or app guide whenever a change alters what a page looks
like. There are usually no mockups: the agreed look is a set of screenshots
the user approved, kept as the repository's baseline at
`~/Workspaces/Projects/<Group>/assets/ui-baseline/<repo>/` (outside the
repository, canonical like any Group asset).

1. **Direction in words.** An existing design system or the current look wins;
   extend it. Without one, ask OpenCode's plan run for one concrete direction
   grounded in the project, and let the user choose or adjust. Suggestions stay
   proposals until the user decides. Missing copy or media is a dependency on
   Writer or the hands, never a fabricated placeholder presented as final.
2. **Pages in scope.** Name the routes the change touches; viewports and dark
   mode follow the project when it names its own.
3. **Baseline.** Check whether a baseline exists for those pages. If none does,
   tell the user the first build's screenshots will be shown for approval and
   become the baseline. If one does, the plan states which pages are expected
   to change and which must not.

OpenCode's build checks every rendered change with its `web_ui_check` tool
(overflow, accessibility, focus, runtime errors, broken images, screenshots and,
given the baseline, comparison images). Neither you nor OpenCode grades taste.

Acceptance: [qa-assistant-engineering](../../qa-assistant-engineering/SKILL.md)
compares the new screenshots with the baseline and asks the user only about
changes the approved scope does not explain.
