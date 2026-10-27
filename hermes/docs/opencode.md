# OpenCode runtime

How the Assistant drives OpenCode: the plugin, bindings, permissions, models,
hand-backs and rendered-UI checks. Read it before changing
`plugins/orchestration/opencode` or the Assistant's engineering entries. Part
of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Who does what

OpenCode is the developer. It investigates, plans, implements, tests, reviews
and commits with its own agents and skills (`opencode/AGENTS.md`), and owns
every technical choice: methods, checks, commit and PR splitting. The Assistant
commissions it on the user's behalf rather than relaying between them: it
briefs OpenCode in plain prose on what the user wants and why and on the
current stage's goal, turns OpenCode's proposals and questions into plain
language for the user, keeps the job's decision log (the user's exact words
live there), obtains the user's explicit implementation approval, answers what
the runs pause on and accepts the result. People read the briefs in OpenCode
too, and a relay of quoted remarks and restated approvals reads as a
subcontract and narrows the run, so a brief is written as `opencode:brief`
says: the user's words inside its own sentences, no commands, steps or report
templates, backticks as the only markup, repository paths relative to the
root. It never edits target code itself, and it
sends every code question or change to OpenCode, however small. The Assistant's
engineering entries (`{plan,execute,qa}-engineering`) carry those decisions;
the plugin's own skills carry the tool mechanics: `opencode:brief` the message
to a run, `opencode:drive` starting, reading and reporting runs,
`opencode:answer` what a run pauses on. Code work happens in any Telegram/Discord topic. The CLI `default`
profile has no OpenCode tools: there the person runs OpenCode directly, as they
usually do on this configuration repo (`~/ghq/github.com/craftsamo/dotconfig`). The Assistant may run
OpenCode on it too, but its links make every change in the live
checkout effective at once, so it plans there read-only and builds only in the
task worktree `opencode_session workspace` creates; the plugin refuses a write
run in the live checkout. Cutover stays the person's decision.

| Relationship                 | Owner of decisions                                                                 |
| ---------------------------- | ---------------------------------------------------------------------------------- |
| User with the Assistant      | What people can do and see, what is stored, scope, cost, the approval of each unit |
| Assistant with OpenCode      | The brief (what and why), the stage's goal, the decision log, acceptance evidence  |
| OpenCode with its own agents | Technical design, methods, exploration, testing, review, commit and PR splitting   |

Work is planned in execution units: one goal that lands in one merge (one PR
or one native stack), one issue on GitHub. Inside a unit, Phase N is one
reviewable layer (one PR, or one layer of the stack) and Phase N.m its
checkpoint steps. A roadmap of several units is approved whole, then each
unit's plan before that unit's build; one approval releases that unit, all
its layers, through QA, task-branch push and PR delivery; never merge,
deployment, repository creation or default-branch push. Every job on a
repository the user owns or belongs to is recorded on GitHub unless the user
excludes it (someone else's repository gets only what its conventions ask;
the user's own record goes on their fork or board): the roadmap's approval
files the parent and its units, a unit's approval makes its issue Fixed and
In Progress before the build, and the Assistant mirrors the run to it
([github-access.md](./github-access.md),
[decision](./decisions/issue-driven-engineering.md)); a run reads the issue
bound to it (the `issue` argument, below), and the Assistant does not pass `issue_approval` (the plugin
keeps it for a caller that does want a build to write Issues through `gh`).

## The plugin

`plugins/orchestration/opencode` drives the person's shared OpenCode 2 service
over its HTTP API for the Assistant (settings under `opencode` in its
`config.yaml`). Requests go through the documented `opencode api` command, which
finds or starts the service and authenticates like the TUI, so the plugin
handles no server address or password. The command gets a minimal environment:
a service it starts keeps that environment for every session, a person's
included, so Hermes' secrets never reach it.

**No run record.** A run is an OpenCode session. Its metadata (`hermes`) binds it
to the caller, role and branch, and a caller can only act on sessions it is
bound to; there is no implicit last-session resume. State is read from the
service each time: the `idle` message that closes a turn carries its outcome
(`succeeded`, `failed`, `interrupted`); the active-session list says whether it
still runs; pending permission requests and forms say whether it is paused.
Why: the service is the one source of truth and sessions survive Hermes. The
cost is deliberate — nothing enforces a deadline, so a run outlives its Hermes
turn until the caller interrupts it, and an unanswered request stays pending.
The only local state is a per-worktree lock that serializes concurrent starts;
the notifier's log (below) is written for people and never read back.
Approval text is an operating-contract record, not authentication; permission
rules are not a process sandbox.

**Binding.** A live (Telegram/Discord) caller binds a session to its profile
home and conversation route — platform, chat, topic/thread, sender and session
key — without the Hermes session id, so a run stays answerable after `/new`, a
compression continuation or a gateway restart in the same topic, and stays
foreign to other topics, senders and profiles. A CLI or resident caller stays
bound to its session id. A `delegate_task` child inherits its parent's route, so
the tools refuse delegated subagents.

**Roles are configuration.** `opencode.roles` maps a role name to an installed
OpenCode agent, a policy (`read-only` or `write`), and optionally a model
(`provider/model[#variant]`) and a note. Each becomes an `opencode_run_<role>`
tool; with no `roles` the four defaults apply (plan, review and debug
read-only, build write). The agents are the person's own modes — there are no
hidden primaries and no operating contract beyond a short `hermes.note`
instruction entry. The prompt is the caller's message exactly as written:
everything mechanical (the operating note, the output directory, where a report
goes) travels in that entry, which the service announces as session
instructions, so the user message a person reads in the session is the brief alone;
only when the service refuses the entry does the note lead the prompt instead.
The note tells the run the technical calls are its own and to say what it chose.
Because rules match each command as written and every
unmatched one waits for the caller, the note asks every run to write commands
plainly (no `NAME=value` prefix, status wrapper or launcher such as `npx`), and
a read-only role's note also asks it to batch commands. A write run's note says
whether Issue writes are granted, so it learns that before trying one. A write run with an
output directory is also asked to keep its Phase steps in `progress.md` there
(below); a person's own sessions never are.

**The issue a run works on.** `issue` (`owner/repo#N`) on any run binds the
unit's issue to the session (`metadata.hermes.issue`, inherited by a fork,
reported in every result and session row); the note then names it as the
specification the run reads with its own tools and says which PR closes it
(`Closes #N` on the completing layer, `Refs #N` on any other). It is checked
like the other bound values and re-sent on every turn. A build is refused
before anything runs unless the session has an issue or the caller passes
`untracked_reason`, the user's words excluding the job from GitHub (or
choosing no record of their own for a job on someone else's repository),
which is bound in the issue's place; passing an issue later replaces it. Why a plugin
argument rather than a sentence in the brief: the brief is free text the
caller can forget under a compaction, and the branch, the PR references and
the record the Assistant mirrors all hang on this one value.

**A build's own writes to its issue.** The OpenCode `gh_issue_*` and
`gh_project_*` write tools assert a permission before they write (the tool id
as the action, the targets as resources, what they will change as metadata;
`opencode/lib/custom-tools/github/gate.ts`), and the session ruleset denies
them all by name. A build run bound to an issue and to a GitHub `mandate`
(the id of one in force, `github_mandate list`; bound to the session like the
issue, kept by a read-only turn, dropped by a build when it lapsed) has two
of them ask instead (`policy.RUN_GH_WRITES`): ticking its own issue's body,
and setting its own issue's board Status to In Progress. `ghwrite.py` answers
those requests in the caller's place while a wait, a status read or the
notifier polls: the request is turned into the `github_change` it amounts
to, github-access's planner reads the targets fresh and the mandate is
checked again at the write (`mandate.still_fits`), so the mandate's own
bounds, not this plugin's reading of the request, decide. Anything else
(another issue, a title, a close, a comment, a label, Done or any other
Status, a board the mandate does not name, no mandate) is rejected with the
reason, and an Issue or board write that still reaches the caller, through
a tool or the shell, can only be rejected: `opencode_request` refuses `once`
on it, since such a write runs on a card or inside a mandate and the
caller's approval is neither ([decision](./decisions/github-mandates.md)). A
linked branch (`gh_issue_develop`) stays denied: a PR from one closes the
issue on its first merge, past the stack's `Refs`/`Closes`, and GitHub links
the task branch to the issue through the PR anyway. Hermes sits in the person's seat: a
question the agent asks and a permission it needs arrive as `waiting` and are
answered with `opencode_request`. The Assistant's `design` role runs a
read-only OpenCode `design` agent that writes HTML mocks and diagrams into the
output directory only, for the user to open before a plan is fixed.

**Plan → Build on the same session.** The next run on a plan session may use
`opencode_run_build` plus `approval`: the session keeps its whole history in
context, and each turn re-sends agent, model, permissions and metadata and
verifies the service applied them before the prompt. A plan is read-only and
runs on the default checkout. A build refuses a default-branch worktree, so
after the Client's approval `opencode_session workspace` gives the idle plan
session a worktree of its own: the plugin fetches and runs
`git worktree add --no-track -b <branch>` (`task/issue-N` for a session bound
to an issue unless the caller names the branch) from the fetched remote default branch
(`base=head` starts from the current commit) under `opencode.worktree_root` as
`<root>/<repository name on origin, else the main checkout's directory
name>/<branch with / as ->`, moves the session there with the service's `move`
route at the real path (a symlinked spelling makes the service file it outside
its project and diffs go empty), rebinds
`metadata.hermes.branch` and renames the session; if the move or the rebinding
fails it moves the session back and removes the worktree and branch. Git runs
without hooks and with a minimal environment, since a tracked `core.hooksPath` is
code a write run can change and this process holds the gateway's secrets. The
service's own worktree route is not used: `workspace` creates, binds and rolls
back the worktree in one step it can verify. OpenCode's worktree strategy
(`opencode/lib/worktrees/strategy.ts`, used by the TUI and `git_worktree`) keeps
the same layout and base, so change the two together; a run's ruleset denies
`git_worktree`, leaving `workspace` the only way a run gets a worktree. A
fork prunes nothing and shares the parent's worktree; give it its own with
`workspace` as well.

**Commit identity.** The shared service keeps its starter's environment, never
the gateway's, so a run would commit as the person's global identity. When the
gateway's environment holds a complete identity pair (`GIT_AUTHOR_NAME` and
`GIT_AUTHOR_EMAIL`, else both `GIT_COMMITTER_*`), `workspace` writes it as the
new worktree's own `user.name` / `user.email` (`git config --worktree`) and
reports it as `commit_identity`; every commit, amend and rebase in that worktree
then carries it, while the person's other checkouts keep theirs. This turns on
the repository's `extensions.worktreeConfig`, which stays on after the worktree
is removed or rolled back; it only lets each worktree read a config file of its
own. Without a complete pair nothing is written.

**One repository per session.** `session_move` is a tool the agent reaches
through `execute`; it asks no permission and takes any session id, so an agent
can move itself (or another session) anywhere. The binding therefore records the
repository (`metadata.hermes.repo`, the real git common directory), and every
turn refuses a session whose directory no longer belongs to it; a move to
another branch of the same repository is caught by the branch binding. This
detects a move at the next turn, not within the turn: a write run's `edit *`
allow follows the session's location, so a run that moves itself mid-turn can
edit there until it hands back.

**Readiness.** `opencode_preflight(directory, phase)` is the one read-only
check before a run. It reads no quota (the quota plugin's data is only as fresh
as an open TUI), so a limit is met as a failed turn and answered with the role's
`alternate` (see Models). It warns when the service runs with the plugin's
minimal environment (below), since that is the one state of the service the
Assistant can cause and the person would not notice.

**What OpenCode runs with.** `opencode_catalog` reads the service's shape, so
the Assistant can say how OpenCode is set up without a run: `agents` (primaries
and subagents, told apart by `mode`), `skills`, `commands`, `plugins` (id,
source, status), `mcp` (servers and connection status), `config` (every
configuration source the service loaded for the worktree, reduced to its path,
top-level keys and the agent, plugin, MCP server and provider names it defines;
`environment.py` never returns a value from a file, since a config carries MCP
headers, plugin options and provider settings), `locations` (loaded
directories), `info` (`/api/info` whole) and `service`. `service` adds what
the API does not say: the process behind the pid (`ps`: parent, start time,
executable), the paths `opencode debug paths` reports, the `opencode` command
the plugin's clients resolve to, and `environment.kind`, read from the names
in the process environment alone (`ps -E`, never a value): `person-shell` when
any name beyond the plugin's `ENV_NAMES` and the system's own is present,
`hermes-minimal` when none is, `unknown` when `ps` cannot show it. The
distinction matters because `opencode api` starts the service when none runs
and the service keeps its starter's environment for every later session: a
service the plugin started serves the person's own sessions without their
shell's variables (their tool keys among them) until they restart it. The API
lists no tools, so which tools a run has is read from the configuration
repository by a read-only run, not from the catalog.

**Output directory.** A run may take `output_dir`: an existing job directory
inside a Workspaces draft (`.agent/`), outside the worktree and spelled without
wildcards. The session ruleset allows `external_directory` for exactly that
directory, ahead of the person's own outside-path denies (which still win), and
a read-only run may edit there too (never a secret-looking file). Every turn
validates the stored value again and names it in the operating note, never in
the prompt. The permission alone does not make Plan
write there: OpenCode's built-in Plan mode reminder forbids every file but its
own fixed plan directory (`~/.opencode/plan`), so the model never tries, and
widening Plan's own `edit` rules would change nothing. So when a read-only turn
completes without its own edit tools touching the output directory, the plugin
saves the turn's final reply there as `<worktree>-<role>-<turn>.md` and returns
it as `report`; the file is the run's deliverable, never read back (only its
existence is checked, so a later status read does not write it twice).

**Permissions.** OpenCode 2 evaluates ordered rules, last match wins: global
config, then the agent's own `permissions`, then the session's ruleset; and
every subagent session copies its parent's ruleset. So the
session ruleset (`policy.rules`) owns each run's constraints for the whole
session tree, and it is applied after a subagent's own posture. It holds
denies, asks and narrow allows: the worktree boundary (`external_directory`
asks; a read-only run is allowed it under `opencode.read_roots`, default
`~/ghq`, plus `worktree_root`, so a plan's explore subagents read the
repositories beside its own without a round trip per directory, while the
person's outside-path denies still win and a root may not be the home
directory, where credentials live, or above it. A write run keeps the ask:
the same action gates its shell's working directory and its edits outside the
worktree, so a read root would let it change the live checkout unasked;
OpenCode's read-only reference clones under its data `repos/` readable),
secrets unreadable, pushes, shell history rewrites, branch moves
(`gh pr checkout` and the person's `gh` aliases included), package downloaders
(`npm exec`, `pnpm dlx`; `pnpm exec` runs only installed tools and is left to
the person's agent rules), anything naming `deploy`, `publish`, `secret`,
`--remote` or `--prod` (a project's task runner can reach those past every other
rule; a best-effort list) and ungranted Issue writes as asks, the hard denies (force and protected-branch
pushes, merges, `gh api`, Project writes, git config, remote rewrites, `gh`
aliases and extensions, edits under `.git/`), and last the person's own denies
read from the built-in `build` agent, so a broad allow never reopens `sudo` or
`secret get`. OpenCode checks each command as written, environment prefixes,
wrappers (`env`, `sh -c`, `xargs`), options before git's subcommand, tabs and
quotes included. So the git rules are containment patterns (`policy.contains`,
e.g. `*git* push* --force*`) that hold however a command is spelled, and catch
a command that merely quotes those words too; the gh rules follow the
subcommand position (`policy.command`), so a PR title saying "merge" passes,
though an identifier spelled like one (`gh_api`) does not. They guard a
cooperative agent's spellings, not a sandbox: several spaces between gh's
words are not covered, and the ruleset (a couple of thousand rules, re-sent
every turn) is capped by a test.
The gated git writes, per-command configuration (`git -c`, `--config-env`)
and branch moves ask in a write run and are denied in a read-only one, whose
session rules hold denies only: a read-only agent may deny those itself, and
an ask or allow there would reopen it. No shell builtin is allowed either,
not even `exit`: OpenCode reports `(exit) >/tmp/x` as the resource `exit` and
checks no redirect target, so an allow would approve a file write unseen; the
operating note asks runs not to wrap commands in `exit` instead. One deliberate exception: a `write` run allows `edit` in its
worktree. Without it every edit is a round trip to the caller; the cost is that
a subagent that denies itself edits (explore) loses that denial for the run. The
allow is placed before the edit denies for OpenCode's config/skill directories
and secret files, which therefore still win. `read-only` denies edits, the
`worker` and `general` subagents, and the `git_commit` / `git_stage_hunks` /
`git_verify_commits` / `git_rebase` / `git_stack` / `git_publish` /
`gh_pr_meta` / `gh_pr_meta_apply` tools,
which write or run commands past the shell rules. A `write` run rewrites its task branch the way the person's
OpenCode does: `git_rebase` and `git_commit`'s amend/fixup run without asking,
because they refuse the default branch, shared commits and protected branches
themselves, and the result leaves the machine only through a push. Every force
spelling stays denied except the task branch's own lease push, re-opened as an
ask by its exact text (`git push --force-with-lease origin
HEAD:refs/heads/<branch>`, optionally with `--force-if-includes`;
`policy.lease_pushes`): a full destination, which push config cannot remap.
A build prefers a native stack for a PR whose work splits into reviewable
layers, and publishes every PR, plain or stacked, through three tools:
`git_stack` (split, add, rebase; local branches only) runs without asking like
`git_rebase`, `git_publish_preview` only reads and is open to every run, and
`git_publish` (push, submit, link) asks through
the person's global rules (a session rule would reopen the deny a read-only
subagent sets itself) and publishes only the exact state the preview's token
pinned, metadata it judged and the PR titles and bodies included: the words
the caller approved are the words published, and the preview reads them
(with each commit subject and branch name) for the working context a run
tends to carry into them — Phase names, decision-log numbers, tool and agent
names, local paths, account state — which the operating note of a write run
names as excluded, since the repository's readers have none of it. The
preview's findings are tripwires for the caller to judge, not a filter: the
rule lives in the `git-pullrequest` skill. `gh_pr_meta` sets PR metadata nothing
reacts to without asking and `gh_pr_meta_apply` asks for the rest, the same
way. In a write run every
`gh stack` command but `view` asks too, since it rebases and force-pushes
layers and takes flags before its subcommand; a read-only run is denied
`gh stack` and both tools entirely, and merging or unstacking a stack always. A write
run needs the user's quoted `approval`, a named non-default task branch, and a
worktree no other session is running in (a person's included). The approval is
the caller's record, kept as `metadata.hermes.approval` (the latest build's,
carried through later read-only turns) and enforced by the ruleset; it is not
added to the prompt, where a restated grant reads as a subcontract. V2 wildcards match whole values and `*` crosses
`/`, so secrets are spelled `*.env`, `*.pem`, … (`**/.env` misses a root-level
file).

**Requests.** An `ask` pauses the run as `waiting`, from the session or any of
its subagents (requests are listed per location; the plugin keeps those of its
own session tree). The caller answers them with `opencode_request`, all pending
ones in one call (`replies`, each checked before any is sent, and sent within
one time budget below the tool deadline; a batch that stops part-way returns
what was `answered` and `unanswered` with the run's state): a permission
`once`, or `reject` with a reason; a question with its answer. A live caller's
reply then waits up to 20 seconds (polling every 5) for the run's next state, so
the next request usually arrives in the same tool result instead of a
notification and a further turn; requests just answered are ignored while the
service still lists them. There is no
broader approval: `always` saves a project-wide approval people's own sessions
would inherit, and a session-wide allow would be copied into every subagent
session after its own denies. The decision rule lives in `opencode:answer` and
the engineering entries.

**Models.** A role's model comes from `opencode.roles.<role>.model`, else the
OpenCode agent's own pin. The plugin passes the model explicitly with every turn
(and on every resume or fork), checks it against the service's model catalog
(it must use tools; a variant must be one the model offers), and reports it as
`engine`. A caller may choose any catalog model of `opencode.allowed_providers`
with `model` / `variant`. A name outside the providers or the catalog is
refused, never substituted, and an explicit selection binds the rest of that
session.

The defaults are OpenCode's own: a role pins no `model` unless a maintainer has a
reason (OpenCode uses its own subscription account, not the Hermes weekly pool).
The caller's own model (the configured `model.default` and the model it last
answered with; a `post_api_request` hook records it, so a fallback counts too)
is refused by default, so a role does not review or build for the model it
answers to without anyone having chosen that. A role may set `caller_model: allow`
to run on it anyway, and the Assistant's roles do (the owner's decision): a
refusal would force every role off the agents' own defaults and break whenever a
fallback changes the Assistant's model, and independence is kept where it matters
(a build starts its own reviewer inside its session, a standalone `review` looks
at someone else's work, and the Assistant accepts through its own QA). Speed
tiers and dated snapshots count as the same model.

A role may name an `alternate` (`provider/model[#variant]`). Nothing switches by
itself: after a turn fails with a `limit` provider error the Assistant reruns on
it. A read-only role simply reruns; for a write role the diff is read first.

**Stops of one model.** The person's OpenCode serves a Claude model from several
places: the active subscription login, another saved login through an alias
model (`claude-<model>-main`), and the Console credit lanes
(`anthropic-credit-*`, providers of their own); on a window limit the
preflight plugin moves a session between them itself, same model and variant
(`opencode/README.md` "Console credit lanes"). The service names the identity
behind each: an alias carries `modelID`, a lane provider `canonical`
(`models.identity`). The plugin keeps to that: a continuing turn that does not
name a model keeps the stop the session is on when it is another stop of the
wanted model (`models.keep_stop`), since re-sending the configured spelling
would move the session back, to be refused again and to pay a prompt-cache
rewrite; a model named this turn still moves it, and a different model is sent
as wanted. An alias or a lane of the caller's own model is the caller's own
too. The catalog marks such entries `stop_of`, and a lane is offered as
`model=` only when its provider is in `allowed_providers`.

**Hand-back.** A live caller gets the current state at once. Only while that
state is `running` it also gets a notifier process, launched through the terminal
tool with completion notification, for the next hand-back; any other state is
already in the result, and a notifier would return it again at once. A
notifier ends at the run's next stop or after 20 minutes as a heartbeat, so
every `status` or `wait` that finds the run `running` starts the next one,
unless Hermes' process registry shows one already watching that run; without
that, a run that paused once or outlived a notifier went unwatched. The
registry has no public lookup by full command, so the check reads its private
`_any_running`; a test pins it against the runtime, and if it disappears the
notifier log records it rather than the check passing silently. Its
output is a summary under 1,800 characters on several lines (status, each
pending request with every command it names, shortened and marked
`complete: false` when cut, the reply's head, the next step), because Hermes shows only the last
~2,000 characters of a notification snapped to a line, and a single long JSON
line shows nothing; the caller reads the full state with `status`. It polls
every 15 seconds and reads the session and its messages only when the run
stops, since every request starts an `opencode api` process. It logs its start
and end to the profile's `logs/opencode-notifier.log` for tracing a missing
notification, and a failure of its own still ends in an `unknown`
notification. The notifier cannot know whether the caller already read its
hand-back through `opencode_session wait`, so the caller answers such a
notification with `[SILENT]`. A blocking (CLI/resident) caller's run tool returns when the turn
finished (`completed`, `failed`, `interrupted`), paused (`waiting`), is stuck in
a provider retry worth a decision, or cannot be confirmed (`unknown`);
otherwise it returns `running` with `timed_out` before the tool and turn
deadlines. A failed turn records `provider_error` (`kind` limit / auth / other)
from its last assistant message. `unknown` blocks nothing: with no record there
is nothing to reconcile, so the caller reads the diff and worktree before another
turn.

**Phase progress.** A Hermes write run with an output directory keeps its
Phase's steps in `<output_dir>/progress.md`, one checklist line per step
(`- [x] Phase2.1 - …`; `[ ]` pending, `[~]` in hand, `[x]` done, `[!]`
blocked). The run writes it; the plugin only reads it (no link followed, 64 KiB
at most), so it is the run's deliverable, not a run record. Every state record
carries its summary as `progress`. A notifier remembers in memory where the list
stood when it started and hands back `running` with `progress_changed` once a
step reaches done or blocked (steps within 30 seconds of each other arrive
together), so the user hears of each step without the caller polling; the
caller's status read starts the next notifier.

**Untrusted output.** Run results, diffs, repository files, Issue and PR text
are material written by others, returned as results, not instructions.

**Session history.** `opencode_history` is the read-only side; contract:
[session-history.md](./session-history.md).

**Tests** use a fake service; a real-service smoke run precedes a cutover.

## Rendered UI

Three questions, three owners:

- **Mechanical defects** — OpenCode's build runs its `web_ui_check` tool
  (`opencode/lib/custom-tools/web_ui.ts`) on every change that alters what a
  page renders (overflow, axe violations, focus, console errors, broken images,
  screenshots per viewport and scheme). It measures; it never grades taste. It
  needs no command permission, and because it also bypasses OpenCode's rules it
  enforces its own: it writes only into the run's output directory or OpenCode's
  scratch directory, never the worktree, loads only local or private-network
  pages, reads a baseline only from under `~/Workspaces`, and runs its Node child
  with a minimal environment.
- **Agreement with the approved look** — given `baseline` (a
  `ui-baseline/<repo>/` directory under `~/Workspaces`, outside the
  repository), the tool writes a baseline | current | diff image per page; the
  Assistant decides whether the approved scope explains each change.
- **The look itself** — the user. The Assistant asks only when no baseline exists
  yet, when a change is not explained by the approved scope, or when the approved
  change is a new look. An approved look becomes the baseline.

Screenshots come from the headless check, never from the Assistant's logged-in
browser profile.
