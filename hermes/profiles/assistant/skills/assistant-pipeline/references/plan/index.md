# Plan mode — align goal and plan, one approval

Enter Plan mode for any non-trivial request (anything beyond a Chat
answer). Plan conversationally, backward from the goal:

1. **Normalize silently** — goal and beneficiary, observable done
   criteria, constraints, inputs (paths, URLs, pasted facts), workspace.
   Infer from chat, workspace, and memory. Ask one `clarify` only when an
   unresolved item changes the outcome, scope, cost, an irreversible
   action, or a grant. Never run a form-filling interview.
2. **Consult before committing** — when feasibility, cost, or approach is
   genuinely uncertain, open the relevant resident session early and ask
   for a feasibility read or a cheap sample (see the capability plan
   file). For engineering, ground the plan in the repo with an OpenCode
   plan session (`engineering/index.md`).
3. **Decompose to tiers** — split the work into stages and assign each a
   tier. A stage may be planned as a kanban card **only by matching it to
   a `card_units` entry** in the execute tree (name the unit type in the
   plan); everything else is a resident session or inline. If a stage
   doesn't map cleanly onto units, decompose further or keep it resident
   — never stretch a unit definition to fit.
4. **Present one plan** — deliverable, capability route, stages with
   tiers, rough cost/time, and the grants it needs (Budget / Authority /
   Publish), in the persona's voice, sized to a phone screen. Present
   alternatives only when a real tradeoff exists.
5. **One approval** — a single `clarify` (approve / adjust). The user's
   approval sanctions the named grants and the card units as planned.
   Small obvious jobs (one asset, one fix, clear spec) skip the ceremony:
   state what you're about to do and proceed unless stopped.

There is no second approval gate. Plan revisions mid-flight (a premise
breaks, scope changes materially, cost balloons, a card comes back
malformed) come back to the user as one plain update + `clarify` when a
real decision is needed.

## Capability plan files

| Capability | File | Owns |
| --- | --- | --- |
| engineering | `engineering/index.md` | repo grounding, unit decomposition, Authority |
| creative | `creative/index.md` | MediaBrief, style anchor, Budget |
| writing | `writing/index.md` | type decisions, unit decomposition (outline / piece), sources |
| research | `research/index.md` | question fixing, coverage claims |
| marketing | `marketing/index.md` | positioning/offer/funnel decisions, campaign decomposition, Publish stance |
