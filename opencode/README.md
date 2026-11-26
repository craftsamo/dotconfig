# opencode

XDG native: OpenCode 2 reads `~/.config/opencode/`. That directory is a real
machine-local one holding a link per tracked entry of this directory
(`install.sh` "[config]", `CONFIG_ENTRY_ROOTS`), because OpenCode writes its
own files beside the config (`service.json`, with the background-service
password) and `hyperframes skills` mirrors its store into `skills/` — both
land next to the links, never in this repo. `skills/` is itself such a root:
`~/.config/opencode/skills/<category>` links here, installer droppings and
the private overlay's skills sit beside them. `cli.json` is seeded once, not
linked: OpenCode rewrites it by temp file + rename, which would replace a
link. Installed from the `anomalyco/tap/opencode-v2` formula (see the
[`Brewfile`](../Brewfile)).

## User-managed content

| Path               | Purpose                                                 |
| ------------------ | ------------------------------------------------------- |
| `opencode.jsonc`   | main configuration (models, permissions, MCP, ...)      |
| `cli.json`         | terminal UI preferences (theme, keybinds, session view) |
| `AGENTS.md`        | global instructions, loaded into every session          |
| `agents/`          | custom agents / subagents (`*.md`)                      |
| `commands/`        | custom slash commands (`*.md`)                          |
| `plugins/`         | local plugins (`*.ts`), auto-discovered                 |
| `lib/`             | code imported by plugins (not scanned by OpenCode)      |
| `skills/`          | opencode-only skills (`<name>/SKILL.md`)                |
| `package.json`     | plugin dependencies, installed by `install.sh --deps`   |
| `opencode-quota/`  | quota plugin settings (`settings.jsonc`)                |
| `antigravity.json` | Antigravity plugin settings (updater off, one account)  |

A fresh clone needs `./install.sh --deps` once: OpenCode 2 does not install
config-directory dependencies, and without `node_modules/zod` the custom-tools
plugin fails to load. The `opencode-v2` formula conflicts with the 1.x
`opencode` formula; uninstall that first on a machine that still has it.

Custom tools live in `lib/custom-tools/<module>.ts` (or `<module>/index.ts`)
and are registered by `plugins/custom-tools.ts`, which exports both a V1
`server()` and a V2 `setup()`. Tool IDs keep the `<module>_<export>` form
(`web_ui_check` and `x_search` only), matching the permission
actions in `opencode.jsonc`. Do not add a `tools/` directory: V1 would register
the same IDs twice and V2 does not load it. Keep subdirectories out of
`plugins/`; V2 loads each one as a plugin package. Child processes go through
`lib/custom-tools/exec.ts`, which spawns with an explicit environment (Bun.$
looks programs up on the PATH the process started with).

Git comes from `@craftsamo/git-tools`, configured in `opencode.jsonc` with
all toolsets and `worktree_root: ~/Worktrees`. Hermes pins the same release
in `hermes/scripts/external-plugins.json`. The local `commit` and `pullrequest`
skills supply conventions over the package's mechanics skills: `git-repo`,
`git-commit`, `git-rebase`, `git-worktree` and `git-push`.

Publication runs through `git_push_read` `preview`, then `git_push_send`,
`github_pr_create` or `github_pr_edit`, and `github_stack_link` for native
stacks. PR attachments and metadata belong to github-tools, not local git
helpers.
Rewrites follow the package's check (`git_commit_read` `amend`): a task
branch's own commits may be rewritten even once pushed (the result says when
the push needs `--force-with-lease`), never the default branch, commits already
on it or held by another remote branch (layers above in the same native stack
excepted), or a branch GitHub protects against force pushes.

GitHub work (issues, Projects, PR status and metadata) goes through
`@craftsamo/github-tools`, pinned in `opencode.jsonc` at the same release
Hermes pins. Its `github-pull-requests` skill covers PR mechanics, including
labels, assignees, review requests, milestones and media attachments.

The package's V2 plugin registers the `git-tools.worktrees` strategy, so the
TUI lists its worktrees. `git_worktree_add` creates them at
`~/Worktrees/<repository>/<branch>` on a new branch cut from the fetched
default branch, the layout the Hermes workspace uses; it does not move the
session. `git_worktree_read` and `git_worktree_remove` read and remove them.
`plugins/builtin-worktree-tools.ts` removes the built-in
`opencode_worktree_create` and `opencode_worktree_remove` from the tool registry;
worktree listing and session moving stay available.

Custom tools run without OpenCode's permission rules, so each enforces its own
limits. `web_ui_check` (`lib/custom-tools/web_ui.ts`) runs
`lib/web-ui-check/web-ui-check.mjs` in a Node child process, because Playwright
is not reliable inside the Bun plugin host; `install.sh --deps` also installs
Playwright's headless shell for it. Tests: `bun test lib/custom-tools
lib/permissions` and `node --test
lib/web-ui-check/web-ui-check.test.mjs`. `node_modules` is gitignored, so in
a task worktree run `../worktree-setup.sh` first (it links the live checkout's
copy); without it the suites that need zod, axe-core or Playwright skip.

All global instructions live in `AGENTS.md`, by choice: this config uses no
`instructions` array, so there is one place that V1 and V2 both read (V2 loads
such an array since 2.0.30).

## Project config for this repository

The repository root holds its own `opencode.jsonc`, loaded only for sessions in
this checkout or one of its worktrees (`install.sh` links directories, never
that file). It adds what work here needs on top of the global config:
references (`hermes-agent`, `private-dotconfig`, `agent-skills`, `opencode`)
with their descriptions, `external_directory` allows for the two local
checkouts and the cached `anomalyco/opencode` clone, and an edit deny on that
clone (a refresh resets it). Editing the local checkouts keeps the global
`edit` ask: they are live, since `~/.hermes` links into them. Paths are spelled
from `~`, because a relative path resolves from the file and a task worktree
would point elsewhere. Worker, worker-deep and refactorer reset
`external_directory` to ask, so they still ask to reach them; a Hermes write
run's session ruleset does the same (its reference clones aside). Descriptions
reach every agent's instructions, and this repository is public: keep them
free of private details.

## Permissions and policies

Two layers decide what an agent may do:

- **Permissions** (`permissions` in `opencode.jsonc` and in each agent file)
  allow, ask or deny. Agent rules are appended after the global ones and the
  last match wins, so an agent that starts its shell rules with `"*": ask`
  turns every global shell deny back into a prompt unless it repeats it.
- **Policies** (top-level `policies`, `tool.use` statements on
  `<action>:<resource>`) are hard denies checked after permissions and saved
  "Allow always" approvals. OpenCode 2.0.25 renamed the action from
  `permission` and moved the key out of `experimental`; it skips a statement
  it does not recognize with only a log warning, and a test keeps every
  statement in the current shape. They never prompt, never
  grant, and project configuration cannot lift the global ones. Keep only
  never-allowed operations there: `sudo`, disk wiping, shutdown, environment
  dumps (`env`, `printenv`), value-exposing or destructive `secret`
  subcommands, `gh repo delete` and printing the GitHub token. A denied call
  fails with `Blocked by configuration policy`. Invalid statements are
  dropped with a warning in the server log, so check it after editing.
  Command patterns are best effort, not a sandbox: the shell scanner emits
  no resource for builtins such as `export -p`, so they run unchecked, and
  an interpreter or a script can still reach the same data.

Reading or editing outside the Location asks: since 2.0.25 the built-in rules
allow it, and the global `external_directory: *` ask restores the prompt. The
skill directories and OpenCode's own scratch directory (`os.tmpdir()/opencode`)
stay open after it. Agent rules come last: the read-only subagents allow
outside reads in their own rules, and Plan allows the source checkouts
(`~/ghq`, `~/Worktrees`), where it reads the repositories beside its own;
credential stores elsewhere in the home directory keep asking. Build does not:
the same action gates a shell's working directory, so its allowed commands
would run in the live checkouts unasked. Worker, worker-deep, refactorer and
design reset `external_directory` to ask and so ask for those directories
too.

Keep the matching permission denies as well (a test checks every shell
policy has one): Hermes copies the build agent's resolved denies into its
session rulesets, and they still hold if a policy is skipped. Custom plugin
tools pass through
neither layer and enforce their own limits.

Patterns are whole-value wildcards where `*` also matches `/`. A file at the
Location root has no directory part, so match secrets with `*.env`, `.env.*`
and `*/.env.*`, never `**/.env`. A shell rule sees each command as written:
an environment prefix, a wrapper (`env`, `sh -c`) or a tab matches no allow
and asks, but options before git's subcommand (`git --no-pager push`) land in
`git *`. So the gated git verbs and the remote writes ask again as
containment patterns (`*git* push *`), and `gh` aliases, extensions and
`gh pr -R … merge` ask the same way; `lib/permissions` checks these forms
against the config. To compare the resolved rules before and
after an edit, read `/api/agent` from a private server whose
`XDG_CONFIG_HOME` points at the candidate config (query it twice: the first
request for a new Location returns an empty list).

## Delegation and progress in V2

V2's `subagent` tool takes `agent`, not V1's `task` / `subagent_type`.
Agents and permissions use the native V2 shape: agent files under `agents/`,
`model: provider/model#variant`, and ordered `permissions` lists with the V2
action names (`shell`, `subagent`, `edit`). Keep each agent entirely in one
format; V2 does not merge V1 and V2 fields inside one agent. The last
matching rule wins, and an agent's rules come after the global ones.

`hidden: true` hides an agent from both interactive discovery and the model's
subagent catalog; no agent here uses it, so the fourteen specialist subagents
are visible. Hermes drives the plan, build, review, debug and design primaries
through the API like a person does. Visibility is not authorization:
caller-specific permissions decide which specialists may run.

- Plan allows read-only exploration, research, diagnosis, and review, but not
  `general`, `worker`, `worker-deep`, `refactorer`, or `verifier` (which can
  apply formatters).
- Debug and Review exclude editing agents and ask `verifier` for checks only,
  never formatter application. Build may request scoped formatter application.
- Build allows the project's own scripts and installed tools (`nps`,
  `pnpm run`, `pnpm exec`, `npm run`) and still asks for anything naming
  `deploy`, `publish`, `secret`, `--remote` or `--prod`: a best-effort list,
  defense in depth rather than a sandbox. Worker, worker-deep, refactorer,
  debugger and verifier reset shell to ask and restate the plain reads (`cat`,
  `head`, `tail`, `wc`, `ls`, `grep`, `rg`, `ps`) after it. Refactorer and
  debugger then ask again for a redirect or a write flag (`--fix`, `--write`,
  `-u`, `--output`) on an allowed check, and refactorer allows a typecheck
  only with `--noEmit`: a best-effort list against a check rewriting files or
  snapshots unasked, not a sandbox.
- Design (`agents/design.md`) shows a person what a product will let them do
  before it is planned: static HTML mocks and diagrams, self-contained so they
  open offline from a chat. It reads the repository and writes only under a
  `.agent/` drafts directory (under Hermes, exactly the run's output directory).
- Plan and the built-in Explore explicitly deny edits, overriding the global
  `edit` ask rule. Plan retains its exception for `~/.opencode/plan/*`; writing a
  plan file still requires the user's explicit request.

New subagents use their configured model, otherwise the parent's model; the
specialists in the route table below take their route's first usable model
instead ("Model fallback for agents"). A user-requested per-call `model` override takes precedence. General and the
built-in Explore have no model configured and inherit the parent; use the
specialists for their role and cheaper default models. Primary sessions retain
their selected model when switching agents; the agent configuration is not a
guarantee of the model currently selected in a session.

`experimental.todo` turns on V2's native `todowrite` tool (2.1.0), which keeps
a session's execution steps as `Phase{N}.{m} - <task> (executor)` and draws
them in the TUI timeline and sidebar (the TUI only). Each call replaces the
whole list and returns only counts and the in-progress item, and there is no
`todoread`. The sidebar keeps showing the last list after a compaction, but
the model keeps only what the summary and the recent turns say, so
`AGENTS.md` `<PlanHandoff>` has it resend the list after one and restate
unfinished work in its replies at handoffs. Plan and Build reach the tool
through the default allow; Debug, Review and Design ask for everything else,
so they allow it by name; every specialist subagent denies `*`, so the list
stays with the primary. Plan asks the user to switch to Build before
execution. Do not create local TODO files or claim that a list was
registered. Durable work still uses GitHub Issues and Projects when
requested. The flag is experimental: while it is off or the tool is gone, the
same list is kept in the conversation. A Hermes-driven run whose operating
note names a `progress.md` keeps its Phase's steps there instead of in
`todowrite`, as `AGENTS.md` `<PlanHandoff>` says, because Hermes reads only
that file.

Empty directories carry a `.gitkeep` so the skeleton survives a fresh clone.

`skills/` holds only the skills that depend on opencode itself — its
subagents, custom tools, or the Plan/Build handoff. Skills any agent can
follow live in [`agents/skills/`](../agents/README.md) and are picked up here
too, since opencode scans `~/.agents/skills` alongside this directory.

## Parallel and background work

The global `ParallelAndBackgroundWork` instructions schedule necessary work by
dependencies, not a fixed count of simultaneous tasks. They add no plugin,
scheduler, permissions, or model changes. Agent-specific restrictions still
apply, including Plan's read-only boundary and Hermes's explicit-review rule.

Parallel execution and background execution solve different problems:

- Start independent questions together, with a distinct scope and expected
  evidence for each specialist. Do not duplicate investigation or manufacture
  tiny tasks to fill parallel slots.
- Use `background: true` when the parent can do useful independent work. When
  the next decision needs the results, wait for them; those calls can still run
  in parallel. Never implement a guess while the needed investigation runs.

| Work                                                            | Useful work while it runs            | Dependency boundary                                         |
| --------------------------------------------------------------- | ------------------------------------ | ----------------------------------------------------------- |
| Independent code, specification, and test-layout investigations | Gather other relevant facts          | Collect answers before choosing the implementation          |
| Review of a frozen change                                       | Prepare the PR explanation           | Resolve findings before committing                          |
| Checks after formatting                                         | Review the diff or prepare a handoff | Collect required check results before reporting completion  |
| A task-owned development server                                 | Prepare the browser check            | Confirm readiness before use; stop it when no longer needed |

Complete authorized formatting before review or verification. Hold the target
files/ref stable until results return. Review and checks may overlap only if
the checks do not modify those files; commands that share build outputs, test
databases, ports, or other mutable resources must run sequentially unless
isolated. A verifier's requested command order still applies. Development
servers belong to an authorized shell workflow, not verifier.

Use completion notifications rather than polling. Keep outstanding tasks in the
conversation, collect results where their dependents need them, and distinguish
passed, failed, skipped, and blocked work. Launching a background task is not
evidence that it passed. Retain background process handles for readiness and
cleanup; never stop an unrelated existing service.

If limits or contention appear, pause new launches on the affected resource;
do not change models, restart tasks, or widen permissions to bypass them. The
model fallback below chooses a route but neither reserves quota nor
guarantees that concurrent launches fit the provider's limits.

This is an operating policy, not a measured speedup. Evaluate elapsed waiting,
duplicate work, and limit errors during normal use before adding scheduling
machinery or changing the policy.

## Model fallback for agents

The npm package `@craftsamo/opencode-model-fallback` (pinned in
`opencode.jsonc` and `package.json`, listed last under `plugins`, after Quota)
launches a routed agent on the first usable model of its **route** and moves a
session to the next usable one when its model hits a limit. A route is the
models `options.routes` lists for an agent, in order, written as `/models`
name them:

```jsonc
"explore-small": [
  "google/antigravity-gemini-4-hydrogen-low",
  "openai/gpt-6-luna#low",
  "anthropic/claude-haiku-5-5#low",
  "anthropic-credit-team/claude-haiku-5-5#low",
  "anthropic-credit-main/claude-haiku-5-5#low"
]
```

The model says where a step runs: a provider listed in `creditLanes` is a
credit lane ("Console credit lanes" below), and anything else runs on its
provider's active login. A step without a variant
stands for every variant, and a move keeps the session's. The first step's
model is the one the agent's own file names; a test keeps the two in step.

**What the package does.**

- **Launch.** A new subagent starts on the first usable step of its agent's
  route, whatever model its definition names; its prompt and permissions stay.
  A step is usable when OpenCode lists its model (enabled, active, able to
  call tools, with the variant) and it is not cooling down, and
  `lib/fallback-steps` does not refuse it. An explicit model, a continuation of
  an existing child and an agent with no route are left alone. When every step
  is refused, the launch goes ahead on the agent's own model, as OpenCode would
  have made it; nothing falls back to credits.
- **Move.** A session, a primary agent's or a subagent's, whose model hits a
  limit moves to the next usable step after its own and retries at once,
  keeping its variant when the step names none. A limit is a quota error, a
  rate limit whose provider asked for a wait longer than ten seconds, or what
  `lib/fallback-steps` names a limit (below). A subagent with no step left
  stops, so its parent gets the failure; a primary agent is left to OpenCode.
  A session moved to a model that is not a step of its route (`/models`) is
  off its route: nothing moves it, and nothing moves it back.
- **Cooldowns.** A model that hit a limit is passed over for the wait the
  provider asked for (else one hour), in `~/.local/state/opencode-model-fallback/cooldowns.json`,
  which survives a restart.
- **Notices.** A launch that changed the model, or found no usable step, starts
  its result with a `[Model fallback: …]` line. OpenCode 2.3 runs subagents in
  the background, so a move there is recorded in the child session's metadata
  (`opencode-model-fallback.moves`), not in the parent's result.

**What `lib/fallback-steps` judges.** The local plugin answers the package's
`usable` and `limit` questions for this setup and shares windows from its
`limited` event. A step is refused while:

- its login has no approved OAuth login (Claude Pro/Max, a ChatGPT login, the
  xAI device login or the Antigravity login);
- Quota reports its login's window exhausted (fresh, or until the reset an
  empty window gave). Missing or stale data is no reason to pass a login over;
- its credit lane is known empty (below), or its Antigravity group is no more
  than the reserve above empty;
- a limit holds its window. The package cools down only the model that hit
  a limit, but a window is shared: the Claude login (every Claude model),
  a credit lane (every model of it), a subscription provider's
  login, or an Antigravity group. The hold is in memory and lasts for the end
  the limit gave.

It takes three more errors for a limit, which the package's own rule misses: a
lane's empty balance, a lane's refused key, and Antigravity's quota protection
("Quota protection: …" or "All N account(s) rate-limited …", held for the wait
it gives, an hour at most). What the plugin keeps (a lane's tries and
refusals) is in `~/.local/state/opencode/fallback-steps.json`.

A Google Antigravity step (`google/antigravity-*`, "Accounts" below) is
weighed by its model's quota group (Gemini Pro, Gemini Flash or Claude) as
Quota's custom provider reports it: a group with no more left than the plugin
keeps back (100 less its `soft_quota_threshold_percent` in
`antigravity.json`, 10% by default) is spent, since the plugin would refuse it.
A model in no group (`antigravity-gpt-oss-*`) is a step the plugin cannot read,
and is not refused. The reserve is read from the user config the plugin reads
(`OPENCODE_CONFIG_DIR`, else `~/.config/opencode`), not a project's own
`.opencode/antigravity.json`.

Missing, stale or unreadable data keeps a step, not a quota error. No
independent balance/entitlement check is performed. Variants and permissions
are unchanged.

| Role                               | Steps, in order                                                                                     |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- |
| explore-max                        | gpt-6.1-sol xhigh → agy opus high → claude-opus-5-5 xhigh                                           |
| explore-high                       | hydrogen high → gpt-6.1-sol high → agy sonnet high → claude-sonnet-5-5 high                         |
| explore-medium                     | hydrogen medium → gpt-6.1-sol medium → agy sonnet medium → claude-sonnet-5-5 medium                 |
| reviewer                           | gpt-6.1-sol medium → agy sonnet medium → claude-sonnet-5-5 medium                                   |
| worker                             | hydrogen medium → gpt-6.1-sol medium → agy sonnet medium → claude-sonnet-5-5 medium                 |
| refactorer                         | hydrogen medium → gpt-6.1-sol medium → agy sonnet medium → claude-sonnet-5-5 medium                 |
| worker-deep                        | claude-sonnet-5-5 high → agy sonnet high → gpt-6.1-sol high → hydrogen high                         |
| explore-spark                      | hydrogen low → gpt-6-luna-fast low → claude-haiku-5-5 low                                           |
| explore-small                      | hydrogen low → gpt-6-luna low → claude-haiku-5-5 low                                                |
| verifier                           | gpt-6-luna low → claude-haiku-5-5 low                                                               |
| debugger, reviewer-deep            | gpt-6.1-sol high → agy opus high → claude-opus-5-5 high                                             |
| searcher-deep                      | grok-4.7 medium → gpt-6.1-sol medium → hydrogen high → agy sonnet medium → claude-sonnet-5-5 medium |
| searcher                           | hydrogen low → grok-4.7 low → gpt-6.1-sol low → claude-haiku-5-5 low                                |
| build, plan, debug, design, review | claude-opus-5-5 (active login) → the lanes; no variant, so a session keeps its own                  |

"hydrogen" is Gemini 4 Hydrogen on Antigravity, whose efforts are models of their
own (`antigravity-gemini-4-hydrogen-low`, `-medium`, `-high`); the pinned
Antigravity plugin routes it through the Gemini Pro quota group, not Gemini
Flash. "agy sonnet" and
"agy opus" are Claude on Antigravity the same way
(`antigravity-claude-sonnet-5-5-medium`, `antigravity-claude-opus-5-5-high`,
…), drawing on the Antigravity Claude group that Sonnet and Opus share. It
has no Haiku and no xhigh, so the Haiku routes go without it and explore-max
takes Opus high there. Claude closes every route: Claude on Antigravity first,
an included pool whose group resets every five hours, then the active Claude
login, then the paid lanes (Team, Main) as the very last
stops; the searchers have no lane. Native model IDs are
explicit: `gpt-6.1-sol`, `gpt-6-luna`, `gpt-6-luna-fast`, `claude-opus-5-5`,
`claude-sonnet-5-5`, `claude-haiku-5-5` and `grok-4.7`. Gemini 4 Hydrogen leads
the explore tiers below max, the worker, the refactorer and the searcher:
it keeps the ChatGPT window and the Claude login for the work behind it.
worker-deep retains its Sonnet-first policy for hard implementation: the
active Claude login on Sonnet comes first, then Claude on Antigravity, then
Sol, then Hydrogen, and the paid lanes still close it. Claude on Antigravity
follows the login there rather than leading, so the first step (the model its
agent file names) stays on the Claude login. (Antigravity steps are
commented out of the routes since 2026-11-15, after an upstream 429 followed
by a misleading 403; restore them in place once the fix is verified.)
explore-max stays on Sol
since its xhigh runs are long and rare. ChatGPT's fast mode (the `-fast` models, priority processing
of the same model at 2.5x the included usage) is kept for explore-spark alone,
a short lookup the parent waits for. The deep searcher leads on Grok, the work that fits the xAI
subscription's weekly pool, which `x_search` draws on too. There is no
free-tier, API-key or environment-variable escalation; a subscription step
must run on an approved native OAuth account (Claude Max, a ChatGPT login,
the xAI device login, or the Antigravity login). Neither plugin buys
credits, enables auto-purchase, or changes account settings or logins.

The primary agents (build, plan, debug, design, review) run Opus: a session
that hits a limit moves through the active login and then the
lanes, in its own variant.

**Shared information.** `lib/fallback-steps` reads Quota's public JSON export (v2 from Quota 5,
v3 from Quota 6) each time the package asks whether a subscription step is usable:
`$XDG_CACHE_HOME/opencode/quota-export.json`, or
`~/.cache/opencode/quota-export.json`. Quota's `system.exportFile` setting is
enabled in `opencode-quota/settings.jsonc`. Quota's background service rewrites
the file after its own checks; the selector does not fetch usage, run the Quota CLI, start
timers, read internal caches or patch Quota.

Rows are matched to the active OpenCode connection being weighed. In v2
a row's `sourceId` is the connection ID. v3 has none: a row's `account` is the
login's label (with the plan after it in parentheses for ChatGPT), so a login
matches by a label no other login of the integration carries, and the
integration's only login owns every row. Two rows for one window are logins
Quota cannot tell apart and match nothing; a login without a usable label
next to others stays unknown. Only the
5h and Weekly rows decide, and at least one must be present: some ChatGPT plans
have no 5h window, xAI exports only its weekly pool, and an exhausted ChatGPT
account may export just one row. If
either window is at 0% the provider counts as exhausted, since credits may
already be spent behind the scenes. Model-specific rows (such as Claude Fable,
weekly too, which v3 tells apart by row id), Monthly usage credits and Code
Review rows are ignored. Published 0% (or less)
counts as empty, even if rounded.

**Freshness.** The export is rewritten only when Quota checks its providers,
so it can be old. An empty window with a reset time still in the
future is trusted at any age, because a window cannot recover before its reset
(the reset time is the expiry). Anything else, including "quota remaining",
needs the provider's `fetchedAt` to be at most six minutes old with no window
past its reset; rewriting the export does not renew its data. Quota checks a
provider only when something asks (the TUI's sidebar, `/quota`, a model turn,
a limit), and the sidebar's asks at most every `minIntervalMs` (two minutes
here, five by default); six minutes leaves room for that and a missed check.

With no TUI open nothing asks, so a question about a subscription step whose
provider's rows are missing or stale asks Quota itself to check that provider,
through the RPC its TUI uses (`slkiser.opencode-quota`, method `refresh`,
reason `poll`). The answer does not wait for the check: the package gives a
question two seconds, and a check takes about one, so the step is weighed on
the export at hand and the next question reads the rewritten one. Questions at
the same time share one check, and the same provider is asked again no sooner
than a minute later. That RPC is Quota's own, not a published interface:
re-check its id and input when bumping Quota (`lib/fallback-steps/quota-refresh.ts`).

When that fails too (no Quota, an RPC that changed), or before the first
export, the step is usable. A different account's rows cannot refuse a step.
A partial multi-login export can still use complete matching-account rows.
This is a best-effort launch preference, not an exact prediction of whether a
task fits its remaining quota.

**What changed from the old `lib/subagent-fallback` plugin (since removed).**

- There are no protected-child markers and no transport or context guards: a
  child launched on a step is an ordinary session, and nothing checks its
  requests' host, auth or size.
- There are no last-resort credits: when every step is refused, the launch
  goes ahead on the agent's own model, as OpenCode would. Missing Quota data
  still launches, so this is not a global prohibition on credit charges.
- Any routed session moves on a limit, not only Claude ones: a Sol worker
  moves to Claude, and a primary agent moves through its route too. The
  `pinModels`, `primaryRoute`, `creditsLastResort`, `creditCooldownMs` and
  `primaryFallback` options are gone.
- On OpenCode 2.3 subagents run in the background, so a move is recorded in the
  child session's metadata (`opencode-model-fallback.moves`) rather than in the
  parent's result. Notices read `[Model fallback: …]`.
- Window holds are in memory; a restart forgets them (the package's cooldowns
  and the lanes' tries and refusals survive it).
- The retry recorder is gone: the package reads the provider's own wait.

**Setup.** The package needs OpenCode 2.1.2 or later. Keep the package listed
last, after Quota, and bump it
deliberately: re-check the `usable` and `limit` answers and the `limited`
event. Run the tests from the repo root with
`bun test opencode/lib/fallback-steps`;
no test-runner script or new dependency is installed. Tests use
synthetic public exports and mocked OpenCode transports; they do not probe
providers or establish real billing/entitlement behavior.

Options of `lib/fallback-steps`: `creditLanes` (ordered provider IDs; `[]`
turns the lanes off). The
package's own settings (`max_wait_ms`, `cooldown_ms`, `cooldown_scope`,
`state_dir`) keep their defaults.

## Console credit lanes

`lib/fallback-steps` spends the Max plans' monthly API credits (see
"Accounts") through `options.creditLanes`, a list of provider IDs. A route's
step on a lane provider is a credit lane step; an empty list turns the lanes
off (the lane steps are then judged like any other provider's). Lane steps
close every Claude route, after the Claude login, so the credits are the very
last stops.

- **Launches and moves** follow the route ("Model fallback for agents"
  above): a lane step is passed over while the lane is known empty (below) or
  a limit holds it. The notice names the reason.
- **In flight.** An empty balance (a plain 400 recognised by its "credit
  balance is too low" text) or a bad key (401/403) is a limit on the lane's
  step: the lane is passed over (the package cools the step down for its own
  `cooldown_ms`, one hour; a refused key for fifteen minutes) and the session
  moves to the next usable step, which is the same model on the next lane when
  the route is written that way. Only requests on the session's own model
  count: compaction and title requests never move it. These fail before
  anything is generated, so nothing is billed twice.
- **Probing.** There is no balance API: a lane is probed by use. After its
  cooldown the next request fails fast if it is still empty. Each
  empty-balance error also records a $0 checkpoint for the balance estimate
  below (at most once a minute per lane).
- **Known empty.** A lane whose checkpoint is $0, with no grant known since and
  its renewal still ahead, holds nothing (spend only lowers a balance), so
  launches and moves pass it over until then. Neither time of day is known: a
  grant listed by its date alone (`status.ts grant`, below) counts from that
  whole day, and a checkpoint on a renewal day holds only to the day's end. A
  Console balance above $0 (`status.ts checkpoint`) ends it too.
- **Daily try.** One request a day still tries a lane known empty, for a grant
  that arrives off schedule or an estimate that ran ahead: a day after it last
  refused a request for its balance (or after its own empty checkpoint), or
  at once when nothing shows it refusing: a $0 carried forward by another
  lane's checkpoint, or a Console reading. The refusal is kept by the plugin,
  since the next lane's checkpoint carries this lane forward as an estimate.
  A try that has been neither refused nor followed by a Console $0 ten
  minutes later shows money, and the lane is used again. The tries and the
  refusals survive a restart in `~/.local/state/opencode/fallback-steps.json`;
  removing it costs only a rejected request per lane.
- **Whose wait counts.** OpenCode Quota's `waitForQuotaReset` (on by default)
  sets a rate limit's wait to the reset of any used-up row of the model's
  provider: the Fable weekly window or a lane's
  $0 estimate. The model fallback reads the wait the provider itself asked
  for, which no plugin changes, so a short limit Quota stretched is not taken
  for a limit; it is listed after Quota for that reason.

**Balance.** Anthropic has no balance API, and an Admin API is not available to
personal orgs, so the balance is estimated: a **checkpoint** (a balance known at
one moment) less the spend since. The spend is OpenCode's own cost accounting
(`opencode stats`) plus Hermes', which spends the same orgs through its
`anthropic` pool (see `hermes/docs/models-auth.md` "Console credit lanes");
leaving Hermes out makes every lane read high within days.

- **Grants.** An org can hold several grants at once, each with its own expiry
  (the next cycle's can arrive days before the current one ends). Spend takes
  the nearest expiry first; what a grant still holds when it expires is lost.
  A grant expires at local midnight of its date.
- **Checkpoints.** `status.ts checkpoint <lane> <balance>` records the balance
  the Console shows now, the most exact reading: record one whenever the
  Console disagrees. An empty-balance error on a lane (see "In flight") records
  a $0 checkpoint on its own. Every lane is re-based together: the named lane
  takes the reading, the others carry their estimate forward (`rolled`), all on
  one Hermes baseline, since Hermes' spend is split between lanes by the
  windows since their checkpoints. A grant expiring since the checkpoint
  re-bases every lane the same way. Without any checkpoint, the cycle's grant
  counts as full at the cycle start.
- **Consistent readings only.** `opencode stats` counts whole local days, so a
  checkpoint keeps the stats window its OpenCode figure came from
  (`opencodeFrom`) and that window's cost then (`opencodeBase`); a carried
  estimate keeps the very run it was computed from. A checkpoint is written
  only when Hermes could be read, the day did not change during the reading,
  and nothing was written since the reading began (the state counts its
  writes in `revision`); otherwise the next reading tries again, and the CLI
  retries or says why. A carried estimate below zero is carried as $0: the gap
  was within the tolerance above, and carrying it would later infer a grant.
  Writers (the Quota endpoint, the CLI, the limit handler) take a lock file beside
  the state that names its holder; one left by a dead process is removed under
  a short-lived guard, and only while it still names that holder.
- **New grants are inferred.** The current cycle's grant is assumed to arrive
  on its renewal day unless one expiring at the cycle's end is known
  (`projected`). When the estimate falls more than $5 (or 10% of the spend
  since the checkpoint) below zero, a grant must have arrived unlisted, since
  neither org can go below zero: one expiring a cycle after the latest known is
  recorded (`inferred`). An empty balance drops inferred grants again.
  `status.ts grant <lane> <amount> <expires> [granted]` lists one from the
  Console (amount 0 removes it).
- **Hermes.** Its spend comes from each profile's `state.db`
  (`session_model_usage` rows billed to `anthropic`, read-only, about 0.1 s),
  as each row's growth since the checkpoint. It is charged in the pool's order,
  `hermes.order` in `lanes.json` (the pool's priorities), each lane taking only
  what it still holds. This is an approximation: the rows do not say which org
  billed them, and Hermes also moves on after a 429 or 401 while the first
  lane still holds credit. If a profile cannot be read, Hermes is left out of
  that run.
- **Pace** is OpenCode's spend on the lane over the last seven days plus
  Hermes' since the checkpoint; "Unused" is what that pace would leave on each
  grant at its expiry.

`~/.config/opencode/credit-lanes.json` holds each lane's `amount`, its
`renewalDay` (the day of the month the plan renews) and its key variable, plus
where Hermes lives and its lane order; it changes only with a plan. Those are
account details, so the file lives in the private overlay, whose `install.sh`
links it there (a real directory beside the links into this repo, never
inside it); the tracked `lib/credit-lanes/lanes.example.json` shows the shape,
and a machine without the file has no lanes (`/credits` lists none, and the
Quota endpoint answers 404 for each). Every provider in `creditLanes` needs a
lane there, or `/credits` and Quota do not show it and Hermes' spend is never
charged to it. What the lanes learn (grants
and the latest checkpoint) lives outside the repository in
`~/.local/state/opencode/credit-lanes.json` (`CREDIT_LANES_STATE` overrides it).
Three ways to read it:

- `/credits`, or `bun opencode/lib/credit-lanes/status.ts` in a terminal.
- OpenCode Quota. `plugins/credit-lanes.ts` serves each lane as a `quota-v1`
  envelope on `127.0.0.1:47631/<provider id>` (`CREDIT_LANES_PORT` changes the
  port; a cached `opencode stats` run, 30 s), and `providers.custom` in
  `opencode-quota/settings.jsonc` points a remote-api provider at each. Quota
  sends the lane's own key as the bearer token and the endpoint answers only
  that, so no new secret exists. The percentage (of the grants that still hold
  something), the countdown to the nearest of them expiring and, while the
  lane holds something, the pace show in `/quota` (an empty lane is its one
  `Left` row); the dollar amounts the endpoint sends beside the percentage
  (`right`) are checked but not shown. Quota reuses a provider's result for
  `providers.checking.minIntervalMs`
  (5 minutes by default, 2 here) even though the sidebar refreshes every minute,
  so use shows up after that wait and the 30 s cache behind the endpoint.

Quota's own `local-estimate` mode was tried and dropped: it re-reads the whole
25 GB history database on every refresh (about a minute), which stalled the
service into a restart loop.

## Prompt cache

Anthropic's cache lives five minutes from its last use, per workspace, and a
miss rewrites the whole prefix at 1.25 times the input price (about $1 per
rewrite at 380k tokens on Sonnet 5.5; a read costs a tenth). In one long
session 81% of the written tokens were rewrites, on the subscription and on the
credit lanes alike, from two causes:

- **A pause over five minutes.** `warming` (top level of `opencode.jsonc`,
  `interval` four minutes, `duration` twenty) sends a keep-alive request while a
  session sits idle, and stops twenty minutes after the last real request. It
  covers every recently active session and every provider, the subscription
  included: the documentation has no per-provider switch. The longest pause
  measured was sixteen minutes. Each keep-alive is a real request, a cache read
  at most four times per idle window, and it is not in the session history or
  in `opencode stats`; the service log shows `warming session` lines.
- **A change to the prefix.** Switching between Plan and Build changes the
  system prompt and the tools, and moving to another provider or model starts a
  new cache; warming cannot prevent either. Long conversations are cheaper kept
  in one agent, on one provider.

A move to a credit lane (see above) therefore pays one full write.

## Accounts

- **Anthropic** (Claude Pro/Max): OpenCode's own OAuth login through the
  `@ex-machina/opencode-anthropic-auth` plugin, stored in OpenCode's database.
  It never reads or writes Claude Code's Keychain entries, and Hermes keeps its
  own PKCE rows (`hermes/docs/models-auth.md` "Authentication inheritance"),
  so the three logins are independent even where two of them are the same
  account. Log in from a browser signed into the account OpenCode should use:
  `opencode auth login anthropic --method claude-max`. OpenCode uses one active
  Claude login.
- **Anthropic Console credit lanes**: the monthly API credits that Max plans
  grant (one Console org per plan, spent before any purchased balance and lost
  at the end of the billing cycle). They work only through an API key, never
  in Claude Code or as extra usage. Two providers, `anthropic-credit-team` and
  `anthropic-credit-main`, read `ANTHROPIC_CREDIT_TEAM_ACCOUNT_KEY` and
  `ANTHROPIC_CREDIT_MAIN_ACCOUNT_KEY` from the Keychain project `opencode`; the
  names are opaque labels, and which org (and whose grant) each one is lives
  in the private overlay with `lanes.json`. A key whose grant expires on
  someone else's schedule goes first in `creditLanes`, so it is spent while it
  lasts. Never name a key `ANTHROPIC_API_KEY`: it would take precedence over
  the OAuth login. A lane stays inactive while its variable is unset, and its
  models list Opus, Sonnet and Haiku 5.5 explicitly (`canonical` inherits
  prices, not the model list). An org with no payment method or auto-reload
  fails the request on an empty balance instead of billing; whether another
  owner's org bills past its grant is their setting, so keep such a key only
  while the grant lasts. The service reads the environment at start: a new or
  rotated key needs `opencode service restart`, and `opencode reload` is
  enough for config only.
- **OpenAI**: built-in ChatGPT login,
  `opencode auth login openai --method chatgpt-browser`.
- **xAI** (the searchers and `x_search`): built-in device login for the xAI
  subscription (the Grok side of The X Subscription),
  `opencode auth login xai --method device`. The login's weekly pool is shared
  with Grok on X, the Grok apps and Cursor. For `x_search`, `XAI_API_KEY` wins
  when set (metered). Quota shows the pool in the footer and `/quota`
  (`enabledProviders` includes `xai`), and the launch selector reads its
  weekly row like the other subscriptions.
- **Google Antigravity** (Gemini and Claude on an Antigravity plan): the
  `opencode-antigravity-auth` plugin's Google OAuth login,
  `opencode auth login google`, choosing "Google OAuth (Antigravity)". After
  approving, the browser lands on a `localhost:51121` page that does not
  load; paste that page's full address into the prompt (the code alone lacks
  the state). Its models are `google/antigravity-*`. The plugin lists what
  the account's plan serves (cached for an hour), but reads that list only
  when it starts with a saved account; until then the picker shows a short
  fixed list that may name models the plan does not offer, so run
  `opencode reload` after the first login. They are picked by hand, or by a
  specialist route that names them ("Model fallback for agents"), and the
  plugin's `google_search` tool is denied for every agent, since it would
  spend the same login from any model. Google's Antigravity terms forbid
  third-party clients, and Google has banned accounts for it (Antigravity,
  Gemini CLI and Code Assist together; a second strike is permanent), so log
  in with an account you can afford to lose. Besides the OpenCode
  credential, the plugin keeps its account pool, refresh tokens included, in
  `antigravity-accounts.json` beside the links in `~/.config/opencode` (never
  in this repo; `.gitignore` covers it anyway); back it up before moving
  machines. `/antigravity` (`/ag`) manages the accounts and shows their quota
  and reset times, but the pinned version fails there with "Expected JSON
  value" while an account has no saved quota, which a new account never
  has. OpenCode Quota's built-in `google-agy` provider reads another
  plugin's login, so `plugins/credit-lanes.ts` (`lib/credit-lanes/antigravity.ts`)
  also serves `/google-antigravity` on the same `127.0.0.1:47631` loopback
  endpoint: it resolves the `google` Antigravity OAuth connection, queries
  `fetchAvailableModels`, and reports the `Gemini Pro`, `Gemini Flash` and
  `Claude` pools to `providers.custom` in `opencode-quota/settings.jsonc`
  (`ANTIGRAVITY_QUOTA_TOKEN` is set in-process by `plugins/credit-lanes.ts`;
  never set `providers.google.settings.apiKey`, which would switch the
  `google` integration off OAuth). When Google answers 403
  "Verify your account" (`VALIDATION_REQUIRED`), the plugin disables the account:
  complete Google's check in a browser signed in to it, then log in again,
  which enables it. `antigravity.json` turns off the plugin's self-update,
  which would otherwise rewrite the pinned version in a V1 config. In its V1
  login menu, never choose "Configure models in opencode.json": it rewrites
  `opencode.jsonc` through the link as plain JSON, dropping every comment.
  The first start after a version bump installs the package (about ten
  seconds), and a CLI command run meanwhile can fail with "Location plugins
  did not finish activating"; run it again.

`opencode auth list` shows the stored logins; `opencode auth switch` picks
another one. Credentials live in OpenCode's database, not in `auth.json`.

## Web access

The shared background service listens on `127.0.0.1:49374` and serves the web
UI as well; `opencode service status|restart|stop` manage it. It generates and
keeps its own password, which local clients read from its registration. To
reach it from other devices, expose it to the tailnet with Tailscale Serve
instead of binding OpenCode to the LAN:

```sh
tailscale serve --bg 127.0.0.1:49374
```

Then sign a browser or phone in with a one-time link (five minutes, single
use; the QR code encodes the first link):

```sh
opencode pair --url https://<machine>.<tailnet>.ts.net
```

Ignore the hint to `opencode service set hostname 0.0.0.0`: that exposes the
service to the whole LAN. Rotating the password (`opencode service set
password ...`) revokes every paired browser.

`opencode reload` (tmux `prefix O`) rebuilds configuration for every loaded
project; configuration and plugin files are also watched and reloaded on
change. After changing Keychain secrets, run `opencode service restart`: the
service keeps the environment of the client that started it.

`opencode serve` (a foreground, private server) still exists; the secret shim
refuses it unless `OPENCODE_PASSWORD` or `OPENCODE_SERVER_PASSWORD` is set, so
it is never started unauthenticated.

## Ignored machine state

`node_modules/` and the lockfiles — see [`.gitignore`](./.gitignore).
