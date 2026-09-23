# Engineer

Engineer dialogue loop, grants and approvals. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Engineer dialogue loop

Engineer is a developer using OpenCode, not a passive relay or a second coder.
Its Client is either a human directly or Assistant. The Client supplies purpose,
constraints and decisions; Engineer investigates and proposes the technical plan
with OpenCode. No Assistant-produced decomposition, Issue or Base session is
required. Existing plans remain useful context, not an automatic new approval.

Engineer v9 exposes `plan-engineer`, `build-engineer`, `qa-engineer` and
`assess-engineer` below the retained `engineer-pipeline` root, outside its
`references/`. Their bodies own the former mode indexes and each entry routes
its own details. The root retains invariant role, approval and delivery rules;
OpenCode transport and the design catalog are shared once. Each turn/completion
and midturn mode/scope change reselects the needed entry without resetting the
job or its grant. Direct entry loads the kernel when its full body is absent;
missing instructions recover through canonical reads or block the affected action.
This candidate is not a live cutover: controlled restart and fresh-session checks
need separate approval, and existing specialist jobs are never replayed by migration.

| Relationship | Owner of decisions | Execution |
| --- | --- | --- |
| Client with Engineer | Outcome, scope and important tradeoffs agreed conversationally | Human clarify or structured Client Q<n> replies |
| Engineer with OpenCode | Technical planning, in-scope implementation sequencing, evidence and correction | opencode_call / opencode_session |
| OpenCode with its own agents | Code-level methods, exploration, testing and review | OpenCode's own tools/skills |
| Engineer with UI evaluators | Visual/UX evaluation scope and final triage | ui-review / ux-persona resident conversations |

One explicit implementation approval releases the agreed scope through QA,
task-branch push and PR delivery. Ordinary internal steps need no per-unit
re-release. Material changes return to the Client. Plan/Assess can finish with
an answer and no code. Issue create/edit/comment is explicit-only for this job;
an Issue URL alone is read-only grounding. No automatic Issues/epics/boards,
merge, deployment, repo creation or default-branch push.

The thin CLI plugin binds each conversation to its originating Hermes session,
Git worktree and branch. It captures JSON events, reapplies permissions on resume,
records private evidence and never blindly retries uncertain work. Stop is not
rollback; reconcile requires observed process/Git/remote effects. Approval text
is an operating-contract record, not authentication, and command rules are not
an arbitrary-process sandbox. A CLI stop event is not technical acceptance.

The plugin is the single owner of the hidden primaries' permission policy
(the agent files carry none), and a conversation keeps its OpenCode session
across agents: Plan hands over to Build by naming `agent="build"` on the
same conversation, so the plan run's investigation and decisions stay in the
build run's context. That requires an unchanged worktree and branch and a
non-default branch, hence the task branch is taken before a plan that is
likely to be implemented. A new conversation starts with no memory and
receives the proposal verbatim; a fork copies the whole history.

Engineer browses isolated development/test targets itself. The two independent
evaluators have no terminal/file-edit tools, bots, A2A endpoint or personal login
profile. Resident execution starts in their own non-Git job directory, not the
implementation cwd; memory/coding context are disabled. They use native browser tools (`browser.backend: "off"` disables the
Browser Use replacement, not browsing) plus the bounded ui_capture tool for
viewport PNG evidence. browser_exec runs host Python and upstream therefore
withholds it from terminal-free profiles. Model is openai-codex/gpt-5.6-terra;
OpenCode's `-fast` alias is not a valid Hermes Codex model name.

The former global OpenCode web-ui/ux-persona-testing skills and ui-review/
ux-persona definitions move here; migrated globals are removed, not retained as
aliases. OpenCode keeps implementation-time rendering and project tests. Details:
engineer-pipeline's mode entries and references and [Engineer Runtime](../../README.md#engineer-runtime).

The dialogue discipline is specialist-generic, not engineer-specific:
**creator** and **writer** also honor the `Review: required` gate; creator
speaks the same protocol with a **Budget** grant as its Authority analog
(generation-spend caps; defaults 4 image variants / 2 video renders per
asset + 1 corrective pass, expanded only via `AUTHORITY+:`), leaves
`PROGRESS:` per finished asset, and — since a task's scratch workspace
survives block/crash respawns (deleted only on completion) — resumes by
inventorying surviving intermediates instead of re-spending credits.
Creator consumes **released units** (anchor / part / assembly) whose
deliverable-defining decisions the assistant fixed in its plan family
leaves; a spec gap or implied composite returns as a finding, input
parts are consumed verbatim, and the production boundary keeps every
content-altering transform on the creator side (the assistant handles
bytes, never re-encodes). Details: creator's `creator-pipeline` skill.
**writer** consumes released units the same way — an outline unit
(structure + tone samples, gated before drafting), piece units against
the approved outline, or a whole small job — under the selected leaf's
QA contract, returning
undecided deliverable-defining choices as spec-gap or granularity findings. Details: writer's
`writer-pipeline` skill. **marketer** owns strategy, offer discovery, producer
coordination and browser draft work. It accepts both human and Assistant clients;
Assistant supplies goals/constraints, not a fully settled marketing strategy.
Exact content/assets, service/account and create/update target need user approval
BEFORE remote editor entry because autosave is an upload. Marketer never
publishes, schedules, sends or generates sharing links. Old Publish/P1 grants
are not adopted. Service drafts require same-object reopening and content plus
unpublished-state verification; uncertain saves are reconciled before retrying.
The user owns economic commitments and later publication. Details: marketer's
four-mode `marketer-pipeline` skill and [`marketer.md`](./marketer.md) "Marketer strategy and browser drafts".
