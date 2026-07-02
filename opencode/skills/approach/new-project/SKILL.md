---
name: approach-new-project
description: >-
  Use when starting a new project from scratch — greenfield, scaffold, no
  existing system to preserve (新規プロジェクト, ゼロから, greenfield, scaffold,
  bootstrap). Apply on top of the `approach` spine with a from-scratch playbook.
---

<Goal>

Start something from scratch, with no existing system or data to preserve.
Apply this on top of the `approach` spine (load it first if not already in
context): investigate → confirm the real goal → co-design one decision at a
time → proceed in small reversible verified steps.

</Goal>

<AntiPatterns>

- Do not build breadth (many half-features) before one end-to-end slice works.
- Do not pick a novel stack without justifying it against boring defaults.
- Do not hand-roll what an official scaffolder or generator provides.
- Do not let the project sit unrunnable while features accumulate.

</AntiPatterns>

<Steps>

1. Clarify scope and constraints:
   - Goal, users, must-haves vs nice-to-haves, and constraints such as stack,
     deadline, hosting, and budget.
   - Derive the implied must-haves the goal requires but the user did not
     name (e.g., accounts imply signup, auth, and password reset); sort them
     into must-have vs nice-to-have.
   - Success criteria for a first usable version.
2. Choose the shape:
   - Pick stack/structure deliberately. Favor boring/proven defaults and justify
     non-obvious choices.
   - Identify the smallest end-to-end slice (MVP) that delivers the core value.
3. Scaffold and iterate:
   - Stand up a minimal skeleton first: structure, deps, run/test, README.
   - Build the MVP slice end-to-end before breadth; keep it runnable at each
     step.
4. Close the loop: hand over how to run it, what works so far, and the next
   steps toward the full scope.

</Steps>

<Gates>

- [ ] Scope + success criteria agreed; MVP defined.
- [ ] Stack/structure chosen with rationale.
- [ ] Runnable skeleton before feature breadth.
- [ ] MVP slice works end-to-end.

</Gates>
