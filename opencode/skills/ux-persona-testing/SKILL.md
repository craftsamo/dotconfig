---
name: ux-persona-testing
description: Use when testing UI/UX with simulated user personas — hostile, reluctant, conscripted, low-IT-literacy, hurried-expert, distracted-mobile — to find where real users struggle and to separate temperament noise from genuine UX defects (UX テスト, ペルソナテスト, 敵対的ユーザー, 拒否的ユーザー, 非自発的ユーザー, リテラシーが低い, ユーザビリティテスト, usability test, persona test, UX audit, user simulation, friction, 離脱, 導線). Runs persona simulations through the ux-persona subagent, triages FACT/REACTION reports with a Signal/Noise/Watch rubric plus cross-persona corroboration, and gates critical flows with a worst-case floor test. Do NOT use for dark-pattern audits of third-party sites, visual design critique (use web-ui / ui-review), or functional unit/e2e testing.
---

<Goal>

Find where real users fail, quit, or suffer — before they do — by running
temperament-differentiated persona simulations against the real rendered app,
then separating genuine UX defects from noise that merely reflects the
persona's attitude. Personas are defect-class detectors, not character
sketches: each exists to surface a class of problem the others cannot.

</Goal>

<Scope>
<UseWhen>

- After implementing or changing a user-facing flow, to test it as users
  would experience it (typical: right after a `web-ui` cycle passes).
- The user asks for persona testing, usability testing, or "would a hostile /
  reluctant / novice user survive this?".
- Gating a critical flow (payment, consent, onboarding) before release.

</UseWhen>

<DoNotUseWhen>

- Visual/aesthetic critique — that is `web-ui` + `ui-review`.
- Functional correctness — unit/e2e tests own that.
- Dark-pattern audits of sites you did not build (Hermes has a separate
  skill for that).

</DoNotUseWhen>
</Scope>

<Lifecycle>

1. Define the scenario (see <Scenarios>).
2. Discovery: launch the core personas in PARALLEL — one `task` call per
   persona to the `ux-persona` subagent, same scenario, mode `discovery`.
   Add extension personas when the flow profile calls for them.
3. Triage every friction event with <TriageRubric>. Present the user a
   Signal list (with fix directions), a Watch list, and a discarded-Noise
   count.
4. Fix Signals through the `web-ui` loop (direction, implementation, render
   verification).
5. Re-test: re-invoke the SAME persona task_ids with "the app changed —
   re-run your scenario" so the persona retains its history and can confirm
   its own frictions resolved.
6. Floor test (critical flows only): after Signals are fixed, run the
   Forced-novice floor persona (mode `floor`). Pass = task completed without
   permanent stuck points. Fail = fix and repeat. This is an acceptance
   gate, not a discovery pass.

Cost discipline: each persona run is browser-heavy and screenshot-heavy —
that is why it lives in the subagent. Do not simulate personas in the
primary session; you built the UI, you know every button's intent, and a
knower cannot get genuinely lost.

</Lifecycle>

<Scenarios>

A persona without a concrete task produces only vibes. Every run needs:

- Goal: one user-level outcome ("create an event and invite a member") — a
  task, never a tour ("look around the dashboard" is not a scenario).
- Entry URL (resolve it as `web-ui` prescribes; never assume a port).
- Any credentials/state needed, prepared in advance.

Never include: the correct click path, implementation vocabulary, feature
explanations, or hints. If the scenario needs a hint to be completable, that
is already a finding.

</Scenarios>

<PersonaLibrary>

Core three — deploy by default, in parallel. All are first-time users with
different temperaments, so shared stumbling points corroborate strongly.

Hostile (敵対的) — distrusts the product, tries to break it

- Behavior: adversarial inputs (emoji, 10k-char paste, script-looking
  strings), double-submits, back-button mid-flow, ignores confirmation text,
  probes for loopholes.
- Patience: high — keeps going until something breaks.
- Detects: robustness, validation, double-submit and data-loss bugs, error
  handling, destructive-action safety.
- Noise profile: complains about everything; success-with-grumbling is the
  classic discard.

Reluctant (拒否的) — does not want to be here, minimum effort

- Behavior: skips onboarding, tooltips, and all explanatory text; accepts
  defaults; shortest possible inputs; never opens menus "to see".
- Patience: minimal — QUITS after 2 friction events or >30s on one step.
- Detects: abandonment points, onboarding cost, default quality, forced
  fields, time-to-value.
- Noise profile: "why do I even have to use this" statements.

Conscripted (非自発的) — ordered to use it, complies but never explores

- Behavior: follows only explicit signposts (labeled buttons, visible
  instructions), takes labels literally, never guesses, never scrolls
  "just in case"; when the trail ends, looks around 3 times, then freezes.
- Patience: medium; freezes rather than quits.
- Detects: broken signposting, inaccurate labels, invisible affordances,
  jargon on the happy path.
- Noise profile: motivation grumbles.

Extension personas — add per flow profile:

Earnest novice (低リテラシー・善意) — wants to succeed, low IT literacy

- Behavior: reads EVERYTHING including tooltips; halts at jargon and
  unlabeled icons (does not know hamburger/gear conventions); never clicks
  anything that looks dangerous; on error, assumes it is their own fault
  and repeats the same action; confuses browser chrome with app UI.
- Patience: high, BUT anything frightening is permanently blocked (fear
  freeze — count separately from abandonment).
- Detects: jargon vs plain language, unlabeled icons, missing undo, missing
  reassurance copy ("you can change this later"), error messages without a
  next action, destructive/safe actions styled symmetrically.
- Noise profile: INVERTED — self-blame bias under-reports. A self-blaming
  REACTION with friction in the FACT is Signal, not noise. Deploy
  near-default for consumer-facing flows.

Hurried expert (せっかちな上級者) — knows the domain, keyboard-first

- Behavior: keyboard only (Tab/Enter/Esc), expects shortcuts and batch
  operations, never reads helper text, notices every wasted step and delay.
- Patience: medium; harsh on latency.
- Detects: focus order, keyboard traps, step count waste, missing bulk
  actions, slow feedback.
- Noise profile: "the old tool was faster" nostalgia.

Distracted mobile (片手スマホ・注意散漫) — one thumb, interrupted

- Behavior: 375px viewport, taps targets directly (fat-finger adjacent
  elements when small), gets interrupted mid-task — abandon the tab, come
  back later, expect to resume.
- Patience: low; 2 mistaps = irritation event.
- Detects: tap-target size, state persistence, session-expiry handling,
  resume-ability, mobile layout traps.
- Noise profile: environment complaints (connectivity, notifications).

Floor persona — floor test only, never discovery:

Forced novice (強制された初心者) — Earnest novice rules + Conscripted
no-exploration + CANNOT QUIT (usage is mandatory). Stuck means staying
stuck. Metrics are completion, stuck points, time, and would-be support
tickets — not friction counts. Use on critical flows as the post-fix
acceptance gate.

</PersonaLibrary>

<TriageRubric>

Triage happens HERE, in the primary session — never inside the persona (a
persona judging its own findings breaks character and self-censors). Judge
each friction event's FACT first, then use the REACTION and the persona's
declared noise profile as a lens:

- Signal (fix it): the FACT shows objective task damage — dead end, wrong
  outcome, no feedback, misleading label, unrecoverable state, attempts
  above the persona's budget — OR the same spot tripped 2+ personas of
  different temperaments (corroboration beats severity).
- Noise (discard, but count): task succeeded within expected steps and only
  the REACTION is loud; pure preference statements with no measurable
  friction; complaints matching the persona's declared noise profile with a
  clean FACT.
- Watch (recheck next run): single-persona, low-impact, but the FACT is
  real. Promote to Signal on recurrence.

Bias correction at the extremes: discount the Hostile persona's outrage
(over-reporting temperament) and amplify the Earnest novice's self-blame
(under-reporting temperament). The rubric is symmetric — attitude is
filtered out in both directions, which is precisely how "computer hate"
noise is separated from real defects.

Report to the user: Signals with fix directions and evidence screenshots,
Watch list, and a one-line count of discarded noise (do not itemize it
unless asked).

</TriageRubric>

<AntiPatterns>

- Playing personas in the primary session — the implementer knows too much
  to get lost; fidelity requires the subagent's clean context.
- Compound "worst user" personas in discovery — stacked constraints destroy
  attribution and flood triage; the floor test is the only sanctioned
  compound, and it reports completion, not frictions.
- Scenario briefs that leak the correct path or explain the UI.
- Letting the persona triage itself, or an out-of-character persona
  ("the aria-label says...").
- Treating a floor-test pass as a discovery result, or running the floor
  test before Signals are fixed.
- Fixing straight from raw persona output without the rubric — that is how
  temperament noise becomes churn in the codebase.

</AntiPatterns>
