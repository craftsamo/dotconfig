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
   plan session (`../../plan-assistant-engineering/SKILL.md`).
3. **Decompose to tiers** — split the work into stages and assign each a
   tier. A stage may be planned as a kanban card **only by matching it to
   a `card_units` entry** in `execute-assistant-creative` (name the unit
   type in the plan); everything else, search included, is a resident
   session or inline. If a stage
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

Do not repeat approval of the same plan. This does not waive a capability's
later exact-proposal, preview, upload or Publish gate, or authorize an
ungranted sample. Small-job shortcuts waive ceremony, not those permissions.
For creative work, consultation and reference research alone authorize no
production; Creator owns production decomposition except on a confirmed
legacy route. Plan revisions mid-flight (a premise breaks, scope changes
materially, cost balloons, a card comes back
malformed) come back to the user as one plain update + `clarify` when a
real decision is needed.

Creative Plan passes intent for new authored video; it authors the local
planning-only HTML timeline (`../../plan-assistant-creative/references/video-design.md`)
only when the user explicitly asks for one.

## Plan entries

For research/search, Client purpose, consumer, constraints, budget and path can
start specialist Plan without detailed pre-decomposition. Specialist proposes
same-role units; Client agrees within its grant, escalating material human-only
or out-of-scope decisions. Overall orchestration and cross-role dependencies
stay with the Client. Consultation authorizes no external search: a preliminary
Build needs bounded agreement, then its result and separate main-proposal
agreement. An explicitly authorized settled brief can enter Build directly;
filled fields or transport kind are not authorization. The domain entries own
these gates; research still travels through engineer, creator or marketer.

This is the common procedure for the selected entry, not another dispatch
step. The table is navigation when the domain changes; do not reload an
entry whose full instructions are already available.

| Capability | File | Owns |
| --- | --- | --- |
| engineering | [plan-assistant-engineering](../../plan-assistant-engineering/SKILL.md) | Client outcome/constraints, Engineer proposal, implementation approval |
| creative | [plan-assistant-creative](../../plan-assistant-creative/SKILL.md) | Client outcome, optional reference research, grants and acceptance criteria; Creator proposes production |
| writing | [plan-assistant-writing](../../plan-assistant-writing/SKILL.md) | type decisions, unit decomposition (outline / piece), sources |
| research | [plan-assistant-research](../../plan-assistant-research/SKILL.md) | purpose and constraints through the primary Client; Researcher proposal and agreement |
| search | [plan-assistant-search](../../plan-assistant-search/SKILL.md) | purpose and constraints; Searcher-proposed retrieval scope, coverage and units for agreement |
| marketing | [plan-assistant-marketing](../../plan-assistant-marketing/SKILL.md) | strategy questions to Marketer; Writer/Creator units, destination and exact remote-save consent planned by you |
