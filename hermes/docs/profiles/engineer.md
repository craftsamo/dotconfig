# Engineer

Engineer dialogue loop, grants and approvals, mode entries, the OpenCode runtime, resident turns and UI evaluators. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Engineer dialogue loop

Engineer is a developer using OpenCode, not a passive relay or a second coder.
Its Client is either a human directly or Assistant. The Client supplies purpose,
constraints and decisions, not a pre-built technical decomposition; Engineer
investigates and proposes the technical plan with OpenCode. No
Assistant-produced decomposition, Issue or Base session is required. Existing
plans remain useful context, not an automatic new approval.

| Relationship | Owner of decisions | Execution |
| --- | --- | --- |
| Client with Engineer | Outcome, scope and important tradeoffs agreed conversationally | Human clarify or structured Client Q<n> replies |
| Engineer with OpenCode | Technical planning, in-scope implementation sequencing, evidence and correction | opencode_call / opencode_session |
| OpenCode with its own agents | Code-level methods, exploration, testing and review | OpenCode's own tools/skills |
| Engineer with UI evaluators | Visual/UX evaluation scope and final triage | ui-review / ux-persona resident conversations |

One explicit implementation approval releases the agreed scope through QA,
task-branch push and PR delivery. Ordinary internal steps need no per-unit
re-release; a short implementation approval advances to Build, not a restarted
Plan. Material changes return to the Client. Plan/Assess can finish with an
answer and no code. Issue create/edit/comment is enabled only when the Client
explicitly requests Issue management for this job — never inferred from an
Issue URL (read-only grounding) or task size. No automatic Issues/epics/boards,
merge, deployment, repo creation or default-branch push.

### Mode entries

Engineer v9 exposes `plan-engineer`, `build-engineer`, `qa-engineer` and
`assess-engineer` below the retained, thin `engineer-pipeline` root, outside its
`references/`. Their bodies own the mode procedures and each entry routes its
own details. The root retains invariant role, approval and delivery rules; only
`references/opencode.md` (OpenCode transport) and
`references/shared/design-catalog.md` are shared. No old mode-path aliases.
Loading follows the shared [entry loading contract](../topology.md#entry-loading-contract);
Engineer's delta: read the shared OpenCode contract before a wrapper call when
its body is missing. Unavailable required instructions stop that action, never
widen a grant or replay work.

Status: candidate. Cutover needs explicit approval, a controlled gateway restart
and fresh sessions; offline runtime tests (real scanner, index, reader and
canonical recovery in an isolated HOME) are not evidence of live model
selection, approval compliance or delivery. Existing specialist jobs and grants
are reconciled, never silently replayed by migration.

### OpenCode runtime

`plugins/opencode` owns CLI execution (`opencode_call`, `opencode_session`) and
the private `opencode-sessions/` records (state, prompts, bounded logs — never
Git). The CLI resolves through PATH, preserving the normal secret shim. Each
conversation binds its originating Hermes session, Git worktree and branch; there
is no implicit last-session resume. The plugin captures JSON events, reapplies
permissions on resume, records private evidence and never blindly retries
uncertain work:

- CLI error events can arrive with exit zero, so exit code alone is not success.
- Deadlines are finite. `stop` requests termination, never rollback; only the
  owning live runner signals its child group.
- An `unknown` result blocks replay until observed process/Git/remote effects
  are explicitly reconciled — by inspection, never an invented completion
  assertion. A CLI stop event is not technical acceptance.
- Approval text is an operating-contract record, not authentication; records and
  command-deny policies are not a process sandbox.

The plugin registers for `engineer` AND `assistant`, each with its own
`opencode_cli` block and its own registry under its home. The Assistant's grant
is the Admin topic's scope (this config repo, Hermes upkeep, a named workspace
repo; contract text in that topic's private `channel_prompts` entry), never
Engineer's project work. Because registries are per home, the Assistant's
worktree-busy check cannot see an Engineer hold — the contract, not the code,
keeps them apart. The Assistant's Telegram calls run in the background with a
completion notification, so its 420 s tool deadline stays; only a CLI assistant
would block.

**Hidden primaries.** plan/build/review run on hidden OpenCode primaries, not the
human TUI agents: `OPENCODE_AGENTS` in the plugin maps each Hermes role to
`~/.config/opencode/agent/hermes-{plan,build,review}.md` (`mode: primary`,
`hidden: true`; `debug` stays shared). Every other plugin decision — `--auto`,
the permission shape, the task-branch gate, the appended scope lines — keys on
the Hermes role name, so renaming an installed agent touches only the map. A
hidden primary is reachable only by name via `opencode run --agent`;
`default_agent` refuses it and the TUI never cycles to it. OpenCode's plan-mode
reminder is keyed on the literal agent name `plan`, so `hermes-plan`'s read-only
posture is prompt + permission, not plan mode. The primaries replace the
provider default prompt with a non-interactive contract: no `question` tool, no
plan→build handoff or PlanHandoff todos, Client decisions returned as `Q<n>:`
with a default already taken, every check delegated to `verifier`, and
reviewer / reviewer-deep passes ONLY when the message asks (overriding the
human-facing "consider a reviewer pass before commits" rule).

**Models.** Models are pinned per role in the agent frontmatter (plan + review
Opus 5.5, build GPT-6 Sol) so Engineer's own model (Fable 5.1, see
[`models-auth.md`](../models-auth.md) "Models and fallback chains") never
challenges or QAs its own OpenCode output; `opencode_cli.models` / `--model`
still override. Accepted exception: the Assistant also runs on Opus 5.5, so its
Admin-topic OpenCode calls are planned and reviewed by the requesting model —
accepted because Admin work is small inline upkeep. Do not extend it to
Engineer; moving Engineer off Fable, or broadening Admin's grant, needs the
reviewer moved to another model family first. `allowed_models` keeps
`openai/gpt-5.6-sol` on both profiles as the one-flag rollback if GPT-6 Sol
builds regress. `opencode_call` also takes `model` / `variant` (OpenCode
`--model` / `--variant`), fail-closed against `opencode_cli.allowed_models` /
`allowed_variants`: a name outside the list is refused, never substituted, and
an explicit selection binds the rest of that conversation.

**Permissions.** The plugin is the ONLY owner of the primaries' permissions; the
agent files carry no `permission:` block (a plugin test fails if one reappears).
OpenCode deep-merges frontmatter with the injected `OPENCODE_CONFIG_CONTENT`
(nested maps union, injected value wins per key, last matching rule wins at
evaluation), so two sources meant neither was the truth. The policy rests on
two facts: an agent-level `"*": deny` shadows the user's global tool allows AND
OpenCode's own auto-allows (skill dirs, the `tool-output/` overflow dir, its
temp dir), so every tool a read-only role needs is listed in `_permissions` and
only the two scratch dirs are re-allowed under `external_directory`; and a plain
`ask` on this transport is never a question — `opencode run` rejects it without
`--auto` and approves it with `--auto` — so build's `external_directory` is
`deny`. Subagents (`verifier`, `explore-*`, `reviewer*`, `worker`) keep their
own frontmatter permissions and are not governed by the injected policy.

**Plan → Build on the same conversation.** The next `opencode_call` on a plan
conversation may name `agent="build"` plus `approval`; OpenCode resumes the
session under `hermes-build` with the whole history (investigation, proposal,
`DECISION(Q<n>)` lines) in context. The wrapper requires the same worktree and
branch and refuses a default-branch build, so `plan-engineer` moves the
checkout onto a task branch BEFORE the first plan call when implementation is
likely (a worktree only for isolation). A plan made on the default branch
starts a new conversation whose message carries the proposal sections and
decisions verbatim; `--fork` is a full-history copy and prunes nothing.

### Resident turns and reconcile

A resident Engineer is a plain CLI process, and CLI has no background-process
wakeup (completion notifications are gateway-only), so resident turns block on
OpenCode rather than poll. `opencode_call` waits up to `opencode_cli.timeout`
(3600); the engineer `config.yaml` raises `timeouts.tools.sequential_call` /
`concurrent_batch` to 3660 because the generic 420 s tool deadline cut calls
into costly `status`/`ps`/`sleep` polling loops (the assistant stays at 420).
The fallback `opencode_session(action="wait", timeout?)` blocks on the record,
bounded by `opencode_cli.wait_timeout`, the job deadline and
`RESIDENT_DEADLINE`.

The 90-minute resident turn (`TURN_TIMEOUT`, fixed in both
`resident-session.sh` and `plugins/specialist-call`) is visible to the
specialist: the handoff prints a `Turn budget:` line from `data["deadline"]`,
and `build-engineer` checkpoint-commits verified increments and stops at
~15 min remaining. The Assistant sizes turns to one verifiable increment and
continues in the same conversation — never a whole "implement to PR" scope in
one turn, which strands uncommitted work.

An interrupted conversation accepts `specialist_call(kind="reconcile")` and
nothing else. OpenCode records are owned by the Engineer session + routing
digest, so after a timeout only the SAME resident session can
`opencode_session reconcile` its children — a fresh conversation or a terminal
resume is refused as "another originating session". The reconcile turn runs
with `RESIDENT_TURN_KIND=reconcile`, under which `opencode_call` is refused; on
success the conversation ends `reconciled` (closable, never resumable for
work). The Assistant-side `kind` validation runs inside the gateway process, so
changing it needs a gateway restart; runner/handoff/opencode changes apply on
the next turn. The `Warning: Unknown toolsets: opencode, specialist` line on
every resident turn is a benign plugin-discovery-order artifact.

### UI evaluators

Engineer browses isolated development/test targets itself. `ui-review` and
`ux-persona` are independent, terminal-free, resident-only evaluator profiles:
no terminal/file-edit tools, bots, A2A endpoint, port or personal login
profile. Their resident launcher gives each an owned non-Git job directory, not
the implementation cwd, so ordinary CLI context discovery cannot import the
implementation repository's instructions; memory and coding-context injection
are disabled. They use native browser tools (`browser.backend: "off"` disables
the Browser Use replacement, not browsing) plus `plugins/ui-inspection`'s
bounded `ui_capture(width,height)`, which attaches actual viewport PNGs and
returns private evidence paths. `browser_exec` runs host Python, so upstream
withholds it from terminal-free profiles; never add terminal merely to restore
it. Use isolated test accounts/state, never owner cookies or another profile's
CDP. Browser actions may still change test data; this is not a website sandbox.
Model is `openai-codex/gpt-5.6-terra`; OpenCode's `-fast` alias is not a valid
Hermes Codex model name.

The former global OpenCode web-ui/ux-persona-testing skills and ui-review/
ux-persona definitions moved into Engineer's mode entries and references and
were removed there, not retained as aliases; OpenCode must restart to discover
the removal. OpenCode keeps implementation-time rendering and project tests.

### Hands-reference maintenance

Hands-reference maintenance has conditional Assess / Plan / Build / Quality
assurance guides in Engineer, not another production leaf. They own Client scope
and independent acceptance; the dotconfig OpenCode Skill
`opencode/skills/hermes/hands-references/SKILL.md` owns the procedure.
`scripts/audit-hands-references.py` is a read-only companion to the topology
validator: orphan candidates are warnings, not deletion permission; card checks
import the trusted candidate's adapter, not sandboxed code. Assess never fixes
or upgrades UNVERIFIED claims automatically. A branch in the live
symlink-backed checkout is not runtime isolation: use task worktrees, and keep
self-modification scope, PR delivery and live cutover separate.

### Specialist dialogue discipline

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
coordination and browser draft work for both human and Assistant clients;
Assistant supplies goals/constraints, not a fully settled marketing strategy.
Its exact-consent, draft-only grant: [`marketer.md`](./marketer.md) "Marketer
strategy and browser drafts".
