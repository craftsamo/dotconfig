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

| Path              | Purpose                                                 |
| ----------------- | ------------------------------------------------------- |
| `opencode.jsonc`  | main configuration (models, permissions, MCP, ...)      |
| `cli.json`        | terminal UI preferences (theme, keybinds, session view) |
| `AGENTS.md`       | global instructions, loaded into every session          |
| `agents/`         | custom agents / subagents (`*.md`)                      |
| `commands/`       | custom slash commands (`*.md`)                          |
| `plugins/`        | local plugins (`*.ts`), auto-discovered                 |
| `lib/`            | code imported by plugins (not scanned by OpenCode)      |
| `skills/`         | opencode-only skills (`<name>/SKILL.md`)                |
| `package.json`    | plugin dependencies, installed by `install.sh --deps`   |
| `opencode-quota/` | quota plugin settings (`quota-toast.jsonc`)             |

A fresh clone needs `./install.sh --deps` once: OpenCode 2 does not install
config-directory dependencies, and without `node_modules/zod` the custom-tools
plugin fails to load. The `opencode-v2` formula conflicts with the 1.x
`opencode` formula; uninstall that first on a machine that still has it.

Custom tools live in `lib/custom-tools/<module>.ts` (or `<module>/index.ts`)
and are registered by `plugins/custom-tools.ts`, which exports both a V1
`server()` and a V2 `setup()`. Tool IDs keep the `<module>_<export>` form
(`git_secret_scan`, `gh_pr_status`, `x_search`, ...), matching the permission
actions in `opencode.jsonc`. Do not add a `tools/` directory: V1 would register
the same IDs twice and V2 does not load it. Keep subdirectories out of
`plugins/`; V2 loads each one as a plugin package. Child processes go through
`lib/custom-tools/exec.ts`, which spawns with an explicit environment (Bun.$
looks programs up on the PATH the process started with).

The git tools (`lib/custom-tools/git/`) back the `git-commit` and
`git-pullrequest` skills: `git_state` (one snapshot of the branch and
worktree), `git_commit` (lint, secret scan and `git commit -F` on the same
message; also amend and fixup), `git_rebase` (onto the fetched base without an
editor, folding fixups; stops with a conflict map), `git_stage_hunks`,
`git_conflicts`, `git_verify_commits` (each commit in a scratch worktree; asks
every call), `git_worktree`, `git_stack` (a native GitHub stack's local side
over `gh stack`: split a branch into layers, add one, rebase),
`git_publish_preview` (read-only: what publishing a plain branch or a stack
would do, pinned in a token) and `git_publish` (asks: pushes, opens or
updates PRs, or links exactly the previewed branch or stack, then re-reads
each layer), and the read-only
history and lint helpers. Both publishing tools take `attachments`: images and
videos that `gh pr create/edit --attach` (gh 2.99.0 or later) uploads into a
PR body. `git/attachments.ts` checks them in the preview against gh's own
limits and pins each file's content in the token, since an upload cannot be
deleted. A failed upload is reported, never retried.
Rewrites follow one rule (`git/rewrite.ts`, also behind `git_amend_check`): a
task branch's own commits may be rewritten even once pushed (the result says
when the push needs `--force-with-lease`), never the default branch, commits
already on it or held by another remote branch (layers above in the same
native stack excepted), or a branch GitHub protects against force pushes.
`gh_pr_status` (`lib/custom-tools/gh.ts`) reads a PR's checks, failed-job logs
and review threads and can wait for CI. `gh_pr_meta`
(`lib/custom-tools/pr-meta.ts`) sets labels, assignees, review requests and a
milestone, applying at once only what no workflow, merge bot, webhook or
mandated ruleset reacts to and that notifies nobody else; `gh_pr_meta_apply`
(asks) applies the rest against its token.

The GitHub tools share `lib/custom-tools/github/` (GraphQL over `gh api
graphql` with pagination, reference parsers, the repository context, board
resolution on the explicit → linked → org → user route, one flat shape for
project items, and an issue's kind as an Issue Type on an organization
repository or a `type:*` label elsewhere). `gh_issue_*`
(`lib/custom-tools/gh_issue/`) reads and writes issues: `view` and `list`
read; `create`, `update`, `comment`, `relate` (parent, sub-issues, blocked
by) and `develop` (a linked branch) write after checking the viewer's
permission, report a repository the viewer does not own as foreign, close
only with a reason and never delete. `gh_project_*`
(`lib/custom-tools/gh_project/`) does the same for Projects v2 boards:
`resolve` and `item_list` read; `create`, `link`, `field_ensure`,
`view_ensure`, `item_add`, `item_set` (archive, never delete) and
`item_promote` write to a board the viewer can update. The sub-issue, type
and dependency flags need gh 2.94.0. The `gh-issues`, `gh-projects` and
`approach-github-planning` skills carry the conventions; the older
`github_project_*` tools and the `manage-github-projects` /
`approach-github-projects` skills stay until the new ones have been used in
anger.

`plugins/worktrees.ts` registers the worktree strategy in
`lib/worktrees/strategy.ts`, so the TUI, the API and `git_worktree` all place
worktrees at `~/Worktrees/<repository>/<branch>` on a new branch, the layout
the Hermes workspace uses. It also removes OpenCode's own Code Mode
`worktree_create` and `worktree_remove` (2.0.27) from the tool registry, for
every agent and every Hermes session: the first asks for no permission, the
second asks under `edit` and can force away dirty files, so no rule here
reaches them. `worktree_list` stays.

Custom tools run without OpenCode's permission rules, so each enforces its own
limits. `web_ui_check` (`lib/custom-tools/web_ui.ts`) runs
`lib/web-ui-check/web-ui-check.mjs` in a Node child process, because Playwright
is not reliable inside the Bun plugin host; `install.sh --deps` also installs
Playwright's headless shell for it. Tests: `bun test lib/custom-tools
lib/worktrees lib/permissions` and `node --test
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
would point elsewhere. Worker resets `external_directory` to ask, so it still
asks to reach them; a Hermes write run's session ruleset does the same (its
reference clones aside). Descriptions reach every agent's instructions, and
this repository is public: keep them free of private details.

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
would run in the live checkouts unasked. Worker and design reset
`external_directory` to ask and so ask for those directories too.

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
subagent catalog; no agent here uses it, so the twelve specialist subagents
are visible. Hermes drives the plan, build, review, debug and design primaries
through the API like a person does. Visibility is not authorization:
caller-specific permissions decide which specialists may run.

- Plan allows read-only exploration, research, diagnosis, and review, but not
  `general`, `worker`, or `verifier` (which can apply formatters).
- Debug and Review exclude editing agents and ask `verifier` for checks only,
  never formatter application. Build may request scoped formatter application.
- Build allows the project's own scripts and installed tools (`nps`,
  `pnpm run`, `pnpm exec`, `npm run`) and still asks for anything naming
  `deploy`, `publish`, `secret`, `--remote` or `--prod`: a best-effort list,
  defense in depth rather than a sandbox. Worker, debugger and verifier reset
  shell to ask and restate the plain reads (`cat`, `head`, `tail`, `wc`, `ls`,
  `grep`, `rg`, `ps`) after it.
- Design (`agents/design.md`) shows a person what a product will let them do
  before it is planned: static HTML mocks and diagrams, self-contained so they
  open offline from a chat. It reads the repository and writes only under a
  `.agent/` drafts directory (under Hermes, exactly the run's output directory).
- Plan and the built-in Explore explicitly deny edits, overriding the global
  `edit` ask rule. Plan retains its exception for `~/.opencode/plan/*`; writing a
  plan file still requires the user's explicit request.

New subagents use their configured model, otherwise the parent's model; the
specialists in the preflight table below take their route's model instead (see
"Model pin"). A user-requested per-call `model` override takes precedence. General and the
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
subscription preflight below chooses a route but neither reserves quota nor
guarantees that concurrent launches fit the provider's limits.

This is an operating policy, not a measured speedup. Evaluate elapsed waiting,
duplicate work, and limit errors during normal use before adding scheduling
machinery or changing the policy.

## Subscription preflight for new specialists

The local plugin `lib/subagent-fallback` (listed last under `plugins` in
`opencode.jsonc`) checks quota before a new specialist launch and chooses in
this order:

1. The route's primary model, unless Quota reports it exhausted. A Claude
   model whose active login is known exhausted first takes the other saved
   Claude logins in order ("Claude accounts" below): the first one not known
   exhausted, through its alias. A Claude alternate (step 2) walks the
   logins the same way. Only with every login known exhausted does the
   choice go on.
2. The role's alternate, when the primary is known exhausted and the alternate
   is not known exhausted. Missing or stale alternate data does not block
   this, since an exhausted primary is the worse bet. A Claude alternate is
   launched on a Console credit lane first when one is configured and not
   known empty ("Console credit lanes" below), on the subscription otherwise.
3. The usual primary with provider-managed credits as a last resort, when both
   are known exhausted and `creditsLastResort` is `true`. This attempts a
   normal provider request; it does not prove a positive credit balance or
   guarantee success.

Missing, stale or unreadable data about the primary keeps the configured
default, not a quota error or an automatic model switch. One exception: a
window limit a protected child just hit (the provider's own word) counts as
exhausted for the wait it asked for, or an hour without one, so the relaunch
goes elsewhere before the export catches up. No independent
balance/entitlement check is performed. Variants and permissions are
unchanged; with `pinModels` (below) a project's own model for a role is not.

| Role                    | Alternate model   | Variant |
| ----------------------- | ----------------- | ------- |
| explore-max             | claude-opus-5-5   | xhigh   |
| explore-high            | claude-sonnet-5-5 | high    |
| explore-medium          | claude-sonnet-5-5 | medium  |
| reviewer                | gpt-6.1-sol       | medium  |
| worker                  | gpt-6.1-sol       | low     |
| explore-spark           | claude-haiku-5-5  | low     |
| explore-small, verifier | claude-haiku-5-5  | low     |
| debugger, reviewer-deep | claude-opus-5-5   | high    |
| searcher-deep           | gpt-6.1-sol       | medium  |
| searcher                | gpt-6.1-sol       | low     |

Native model IDs are explicit: `gpt-6.1-sol`, `gpt-6.1-sol-fast`, `gpt-6-luna`,
`gpt-6-luna-fast`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`
and `grok-4.7`.
The explore tiers lead on the ChatGPT window, medium, high and spark in fast
mode, which is priority processing of the same model at 2.5x the included
usage; explore-max stays on standard Sol since its xhigh runs are long and rare.
The searchers lead on Grok: retrieval is the work that fits the xAI
subscription's weekly pool, which `x_search` draws on too, and it keeps the
ChatGPT window for the explore tiers until the pool is spent. There is no
free-tier, API-key or environment-variable escalation; both ends must be
approved native OAuth accounts (Claude Max, a ChatGPT login, or the xAI device
login). The plugin never buys credits, enables auto-purchase, or changes
account settings or logins.

**Shared information.** Reads Quota 5's public v2 JSON export once before
each eligible launch: `$XDG_CACHE_HOME/opencode/quota-export.json`, or
`~/.cache/opencode/quota-export.json`. Quota's existing `export.enabled` setting
is enabled in `opencode-quota/quota-toast.jsonc`. Its home footer writes the file
on normal refresh; the selector does not fetch usage, run the Quota CLI, start
timers, read internal caches or patch Quota. A custom export path can be matched
with the plugin option `quotaExportPath` (absolute path).

Rows are matched to the OpenCode connection being weighed using `sourceId`:
the active one, or a saved Claude login, whose rows Quota exports under the
same provider. Only the
5h and Weekly rows decide, and at least one must be present: some ChatGPT plans
have no 5h window, xAI exports only its weekly pool, and an exhausted ChatGPT
account may export just one row. If
either window is at 0% the provider counts as exhausted, since credits may
already be spent behind the scenes. Model-specific rows (such as Claude Fable),
Monthly usage credits and Code Review rows are ignored. Published 0% (or less)
counts as empty, even if rounded.

**Freshness.** The export is rewritten only while the Quota footer refreshes in
the TUI, so it can be old. An empty window with a reset time still in the
future is trusted at any age, because a window cannot recover before its reset
(the reset time is the expiry). Anything else, including "quota remaining",
needs the provider's `fetchedAt` to be at most six minutes old (Quota's
five-minute cache plus export-refresh grace) with no window past its reset;
rewriting the export does not renew its data.

Before the first export, without the home footer (including headless use), or
after its data expires, an unknown primary keeps the configured default. A different
account's rows cannot authorize a fallback. A partial multi-login export can
still use complete matching-account rows. This is a best-effort launch
preference, not an exact prediction of whether a task fits its remaining quota.

**Ongoing transport check.** The actual HTTP and WebSocket transports are
verified for the subscription host, subscription auth and absence of an API
key. Title, compaction and generate requests are guarded too. This is not a
global financial guarantee: tools, other plugins and stateless `ctx.generate`
are out of scope. These guards check identity, model and transport only; they
never read usage or credit balances during execution, including auxiliary
requests. Actual charging and credit availability remain provider-managed.

**Marker.** A durable metadata marker is written on the new child before its
prompt, which closes the registration race and survives a background launch or a
reload. The selector writes no quota cache or credentials; the connectionID
stays in the internal marker, never in its notices. Quota's own public export
contains connection IDs and display labels, but no access tokens. A child
launched on another saved Claude login also carries that login's suffix: it
runs the alias, and the transport check expects that login's token and
connection on its Claude requests, side requests included. A window limit
such a child hits is remembered for that login only.

**Passthrough.** An explicit model, an existing sessionID, unknown roles and
(without `pinModels`) roles whose configured models changed keep the normal
selection. During a task,
Quota errors or exhaustion do not stop a child. Native provider quota errors
and long rate-limit reset waits still end the protected task; short native
transient retries are allowed. There is no model switch, restart or automatic
resubmit for a protected child (Console credit lanes below are a separate path
that never touches one). Native providers may move to credits mid-request;
launch preference is not a no-paid gate. Older markers retain identity/context
protection without their obsolete funding gates. The root parent's model and
retry policy are unchanged unless `creditLanes` is set, so a parent on the same
pool may still fail.
Protection is sticky for marked children, including completed continuations:
historical execution outcomes cannot prove current idleness. They retain their
selected role and model; start a new child for a different explicit selection.

**Model pin.** A project can ship its own agent file for a routed role (say
`.opencode/agents/reviewer.md` on another model), and project definitions
outrank global ones. With `pinModels: true` a new launch of a role in the table
above still takes its route, whatever definition is in effect, global or
project: `ROUTES` in `policy.ts` owns these models, and a test keeps
`agents/<role>.md` in step with it. The plugin passes the route's model
explicitly, keeps the project's prompt and permissions, and prefixes `[Model pin: <role>
<from> → <to>; …]` (metadata `pin: { from, to }`, `from` null when the
definition has no model). Lanes and the preflight then apply as usual. An
explicit model, a continuation or an unknown role is never pinned, and the
agent list still shows the project's model. An agent transform could not do
this on 2.0.23 (not re-checked since): plugin transforms run before Markdown
agents are loaded, so those overwrite any model a plugin sets. There is no
per-project exclusion yet; turn the whole thing off with `pinModels: false`.

**Context limit.** The first alternate's text context may be at most
160000 UTF-8 bytes plus 32768 headroom, relative to the catalog input or
context minus output. The first primary HTTP body or WebSocket frame is also
measured before transmission, including additions from later context hooks. A
zstd or gzip body (`settings.encoding`, zstd by default for ChatGPT sign-in) is
measured decoded, never past the ceiling; any other encoding rejects.
Media or unknown sizes reject, and no compaction is
run to make a launch fit. Later native compaction retains the subscription
identity and route checks, without a fresh quota requirement.

**Reporting.** The UI report uses the built-in tool's content and metadata with
`from` / `to`, including background launches. `funding: included` reports the
fallback preference; `funding: provider` means both reported pools were empty
and the provider decides whether the default can proceed. Neither proves the
actual charge. Declared structured output is unchanged.

**Setup.** Pinned to the OpenCode releases in `SUPPORTED_VERSIONS`
(`index.ts`), currently 2.1.2 (list the old and new release together while
the binary is upgraded): on any other release the automatic new launch is
rejected and a protected child stops, but a manual pass still works. Add a
release only after checking the session hooks, the `subagent` tool's
pre-launch `progress` and the retry error shape against its source, then
re-validate the mocked tests. Run them from the repo root with
`bun test opencode/lib/subagent-fallback`; no test-runner script or new
dependency is installed.

When both reported pools are empty, the default-provider attempt requires
`creditsLastResort: true`; otherwise the launch stops. Missing Quota data still
uses the default, so this option is not a global prohibition on credit charges.

To disable new selection, set the plugin's `options.enabled` to `false`;
guards for already-marked children remain. To keep those guards, do not remove
the plugin or config entries or change auth while it is active. Keep the entry
last, after quota, and trust no other later request mutator.

Options: `enabled: true`, `creditsLastResort: true`, `pinModels: true` (default
off), and for the credit lanes
below `creditLanes` (ordered provider IDs), `creditCooldownMs` (default one
hour) and `primaryFallback` (default on); for a second Claude login,
`claudeAccounts` ("Claude accounts" below). The independent usage reader, billing parser and usage-diagnostic RPCs have been
removed. Tests use synthetic public exports and mocked OpenCode transports;
they do not probe providers or establish real billing/entitlement behavior.

## Console credit lanes

The same plugin spends the Max plans' monthly API credits (see "Accounts")
through `options.creditLanes`, an ordered list of provider IDs. A missing or
empty list turns all of this off, in-flight moves included, except moves to
another Claude login ("Claude accounts" below); `enabled: false` stops only
new lane launches.

- **Specialists** (the two roles with a Claude primary). A new launch takes the
  first lane not known empty, with no subscription marker: the OAuth guards
  above do not apply to API-key requests. With every lane empty, the preflight
  above decides as before. The report carries `funding: console-credit` with
  `from` / `to`. Agent files keep the subscription model; with `pinModels` a
  lane named there is replaced by the route like any other model.
- **ChatGPT specialists** (the roles with a GPT primary) use their own window
  first. Once Quota reports it empty, or a protected child of the role just
  hit its limit, the Claude alternate launches on the first lane not known
  empty, unmarked like any lane launch; with every lane empty it launches on
  the subscription, marked and guarded as a fallback.
- **In flight.** An empty balance (a plain 400 recognised by its "credit
  balance is too low" text), a bad key (401/403) or a window limit marks the
  lane out (for `creditCooldownMs`, one hour; a window limit only for the wait
  it asked for) and moves the session to the next provider with the same model
  and variant, repeating the same step. Only requests on the session's own
  model count: compaction and title requests never move it. These
  fail before anything is generated, so nothing is billed twice. A specialist
  goes lane, next lane, subscription, then another Claude login; after a long
  limit there it stops, so the parent relaunches it and the preflight can pick
  the other vendor (the limit is remembered, see "Subscription preflight").
- **Primary sessions** (no parent). On the subscription's window limit
  (`provider.quota`, or a rate limit that asks for more than ten seconds) they
  move to the first lane, and on to the next lane when one is empty; on a
  lane, the subscription is the last stop before another Claude login. Nothing
  moves a primary back while its lane works: return with `/models`.
  `primaryFallback: false` keeps the primary on the subscription.
- **Another Claude login** ("Claude accounts" below) comes after all of these:
  a session moves to its alias of the same model, and leaves it only on a
  window limit, for the lanes and then the active login. Each login is a stop
  of its own.
- **Probing.** There is no balance API: a lane is probed by use. After its
  cooldown the next request fails fast if it is still empty, which costs one
  rejected request an hour. Each empty-balance error also records a $0
  checkpoint for the balance estimate below (at most once a minute per lane).
- A session never revisits a stop within five minutes, so the chain cannot
  loop. Children launched under the subscription preflight keep their own
  guards and are never moved.

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
  Writers (the Quota endpoint, the CLI, the retry hook) take a lock file beside
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
  port; a cached `opencode stats` run, 30 s), and `quotaProviders` in
  `opencode-quota/quota-toast.jsonc` points a remote-api provider at each. Quota
  sends the lane's own key as the bearer token and the endpoint answers only
  that, so no new secret exists. The percentage (of the grants that still hold
  something), the countdown to the nearest of them expiring and the pace show
  in `/quota`. Quota reuses a provider's result for `minIntervalMs`
  (5 minutes by default, 2 here) even though the sidebar refreshes every minute,
  so use shows up after that wait and the 30 s cache behind the endpoint.

Quota's own `local-estimate` mode was tried and dropped: it re-reads the whole
25 GB history database on every refresh (about a minute), which stalled the
service into a restart loop.

## Claude accounts

OpenCode sends an integration's requests with its one active login
(`opencode auth switch` changes it for every session at once), and the Claude
login plugin rewrites requests of provider `anthropic` only, so a second Claude
Pro/Max login cannot be a provider of its own the way a credit lane is. The
same plugin (`lib/subagent-fallback`) reaches it through alias models instead:

- `providers.anthropic.models` in `opencode.jsonc` defines
  `claude-<model>-sub` for Fable, Opus, Sonnet and Haiku, each with `modelID`
  set to the real model: it sends the real model ID and inherits its variants,
  limits and prices. `/models` lists them as "Claude Opus 5.5 (Sub OAuth)" and
  so on.
- The option `claudeAccounts` maps a model-ID suffix to the label of a saved
  login (`{ "sub": "Sub OAuth" }`). A request on an alias model leaves with
  that login's token in place of the active one's; the plain models keep the
  active login. The side requests of a session on an alias model (compaction
  on the compaction agent's Haiku, a title on a Claude model) follow the
  session's model, so it never draws on the active login's window; warming
  sends the session's own model. A session with no stored model (on the
  default model) follows its last own request instead, so an alias is not
  meant as the default `model`.
- The token is swapped after the login plugin rewrote the request (this
  plugin is the last config entry, and hooks run in load order), and only the
  `authorization` header changes, in place: the login plugin restores tool
  names in the response by the identity of that request. The body it builds
  does not depend on the account.
- Anything unexpected stops the request rather than sending it on the active
  login: an entry with no label, no saved login with that label or two, a
  login that is not Claude Pro/Max, a host other than `api.anthropic.com`, a
  request the login plugin did not rewrite (no bearer token or no
  `oauth-2025-04-20` beta flag), or a release missing from
  `SUPPORTED_VERSIONS`. An option that is not a map stops every Claude
  subscription request until it is fixed: no alias can be told apart then.
  None of this depends on `enabled`.
- A session reaches the login by picking the alias model in `/models`, by
  moving there on a limit after the subscription and the credit lanes
  ("Console credit lanes" above), or, for a new specialist, when Quota
  reports the active login exhausted ("Subscription preflight" above). A
  protected child launched there stays bound to that login.

To add a login, run `opencode auth login anthropic --method claude-max` from a
browser signed into that account. A new login becomes the active one: switch
back right away (`opencode auth switch anthropic "Main OAuth"`), then give the
new login the label the option names, from the TUI's account list or with
`opencode api patch /api/credential/<credential id> --data
'{"label":"Sub OAuth"}'` (`opencode auth list --format json` shows the ID). The
labels are opaque; which account each one is lives in the private overlay.
Quota shows every saved login, as `[Claude Main OAuth] (active)` and
`[Claude Sub OAuth]`; it has no setting to rename the `Claude` prefix.

Limits:

- The login plugin's 429 diagnostics name the active login for an alias
  request: it records the connection before the swap.
- The swap relies on how the login plugin tracks requests: after bumping it,
  run a tool call on an alias model end to end.
- Stateless generation (`ctx.generate`) runs no session hooks, so an alias
  there gets neither the login plugin's rewrite nor the swap.
- Moving a session between logins starts a new prompt cache ("Prompt cache"
  below).

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
  `opencode auth login anthropic --method claude-max`. Several accounts can be
  saved; one is active at a time (`opencode auth switch`, label `Main OAuth`),
  and another is reached through alias models (label `Sub OAuth`, see "Claude
  accounts"), picked by hand or as the last stop after the credit lanes. Which
  account each is lives in the private overlay.
- **Anthropic Console credit lanes**: the monthly API credits that Max plans
  grant (one Console org per plan, spent before any purchased balance and lost
  at the end of the billing cycle). They work only through an API key, never
  in Claude Code or as extra usage. Three providers, `anthropic-credit-team`,
  `anthropic-credit-main` and `anthropic-credit-sub`, read
  `ANTHROPIC_CREDIT_TEAM_ACCOUNT_KEY`, `ANTHROPIC_CREDIT_MAIN_ACCOUNT_KEY` and
  `ANTHROPIC_CREDIT_SUB_ACCOUNT_KEY` from the Keychain project `opencode`; the
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
