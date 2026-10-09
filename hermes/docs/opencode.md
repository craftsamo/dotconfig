# OpenCode runtime

How the Assistant drives OpenCode: the plugin, bindings, permissions, models,
hand-backs and rendered-UI checks. Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Who does what

OpenCode is the developer. It investigates, plans, implements, tests, reviews
and commits with its own agents and skills (`opencode/AGENTS.md`). The
Assistant is the user's Client and supervisor: it frames the outcome, grounds
the plan through OpenCode plan/debug/review runs, obtains the user's explicit
implementation approval, drives the build to a task-branch PR, answers what the
runs pause on and accepts the result. It never edits target code itself, and it
sends every code question or change to OpenCode, however small. The Assistant's
engineering entries (`{plan,execute,qa}-assistant-engineering`) carry those
decisions, including which work goes to OpenCode and what plan and Build share;
the plugin's own skill (`opencode:opencode`) carries the tool mechanics. Code
work happens in any Telegram/Discord topic. The CLI `default` profile has no
OpenCode tools: there the person runs OpenCode directly, as they usually do on
this configuration repo (`~/.config`). The Assistant may run OpenCode on it too
(hands-reference upkeep does), but its links make every change in the live
checkout effective at once, so it plans there read-only and builds only in the
task worktree `opencode_session workspace` creates; the plugin refuses a write
run in the live checkout. Cutover stays the person's decision. Its Admin topic
also makes small inline edits there.

| Relationship                 | Owner of decisions                                                  |
| ---------------------------- | ------------------------------------------------------------------- |
| User with the Assistant      | Outcome, scope, important tradeoffs and the implementation approval |
| Assistant with OpenCode      | Requests, in-scope technical answers, acceptance evidence           |
| OpenCode with its own agents | Code-level methods, exploration, testing and review                 |

One explicit implementation approval releases the agreed scope through QA,
task-branch push and PR delivery. Issue writes need a separate, explicit
request to manage this job in Issues. No automatic Issues, epics or boards, and
never merge, deployment, repository creation or default-branch push.

## The plugin

`plugins/orchestration/opencode` drives the person's shared OpenCode 2 service
over its HTTP API for the Assistant (`plugins.enabled: opencode`, settings under
`opencode` in its `config.yaml`). Requests go through the documented
`opencode api` command, which finds or starts the background service and
authenticates like the TUI, so the plugin handles no server address or
password. The command gets a minimal environment (`PATH`, `HOME`, locale,
`TMPDIR`, `XDG_*`): a service it starts keeps that environment for every
session, a person's included, so Hermes' secrets never reach it.

**No run record.** A run is an OpenCode session. Its metadata (`hermes`) binds it
to the caller, role and branch, and a caller can only act on sessions it is
bound to; there is no implicit last-session resume. State is read from the
service each time: the `idle` message that closes a turn carries its outcome
(`succeeded`, `failed`, `interrupted`); the active-session list says whether it
still runs; pending permission requests and forms say whether it is paused.
Why: the service is the one source of truth and sessions survive Hermes. The
cost is deliberate — nothing enforces a deadline, so a run outlives its Hermes
turn until the caller interrupts it, and an unanswered request stays pending.
The only local file is a per-worktree lock under the profile home that
serializes concurrent starts; it records nothing. Approval text is an
operating-contract record, not authentication; permission rules are not a
process sandbox.

**Binding.** A live (Telegram/Discord) caller binds a session to its profile
home and conversation route — platform, chat, topic/thread, sender and session
key — without the Hermes session id. A run therefore stays answerable after
`/new`, a compression continuation or a gateway restart in the same topic, and
stays foreign to other topics, senders and profiles. A CLI or resident caller
has no route that outlives its session and stays bound to its session id.
`opencode_history` can still find a foreign session read-only. A `delegate_task`
child inherits its parent's route, so the tools refuse delegated subagents.

**Roles are configuration.** `opencode.roles` maps a role name to an installed
OpenCode agent, a policy (`read-only` or `write`), and optionally a model
(`provider/model[#variant]`) and a note. Each becomes an `opencode_run_<role>`
tool; with no `roles` the four defaults apply (plan, review and debug
read-only, build write). The agents are the person's own modes — there are no
hidden primaries and no operating contract beyond a short `hermes.note`
instruction entry (prepended to the prompt if the service refuses the entry).
Hermes sits in the person's seat: a question the agent asks and a permission it
needs arrive as `waiting` and are answered with `opencode_request`.

**Plan → Build on the same session.** The next run on a plan session may use
`opencode_run_build` plus `approval`: OpenCode records the switch of agent and
injects its own mode-change reminder, so the session keeps its whole history in
context, and each turn re-sends agent, model, permissions and metadata and
verifies the service applied them before the prompt. A plan is read-only and
runs on the default checkout. A build refuses a default-branch worktree, so
after the Client's approval `opencode_session workspace` gives the idle plan
session a worktree of its own: the plugin fetches, runs
`git worktree add --no-track -b <branch>` from the fetched remote default branch
(`base=head` starts from the current commit; with no remote or default branch it
refuses) under `opencode.worktree_root` (default `~/Worktrees`, as
`<root>/<main checkout's directory name>/<branch with / as ->`), moves the
session there with the service's `move` route at the real path (a symlinked
spelling makes the service file it outside its project and diffs go empty),
rebinds `metadata.hermes.branch` and renames the session. If the move or the
rebinding fails it moves the session back and removes the worktree and branch.
Git runs without hooks and with a minimal environment, since a tracked
`core.hooksPath` is code a write run can change and this process holds the
gateway's secrets. The service's own worktree route is not used: it can only
create a detached HEAD. A fork is a full-history
copy in the parent's worktree and prunes nothing; give it its own with
`workspace` as well, which is how a clean plan is kept to build two ways.

**One repository per session.** `session_move` is a tool the agent reaches
through `execute`; it asks no permission and takes any session id, so an agent
can move itself (or another session) anywhere (measured on 2.0.23). The binding therefore records the
repository (`metadata.hermes.repo`, the real git common directory), and every
turn refuses a session whose directory no longer belongs to it, or that was bound
before the repository was recorded; a move to another branch of the same
repository is caught by the branch binding. This detects a move at the next turn,
not within the turn: a write run's `edit *` allow follows the session's location,
so a run that moves itself mid-turn can edit there until it hands back. The
plugin cannot stop an agent from moving a session it does not own.

**Readiness.** `opencode_preflight(directory, phase)` is the one read-only
check before a run: the service and the version the plugin was measured on, each
role's agent, effective model and alternate against the catalog, the worktree
and branch, and (for `phase=build`) a task branch, no session already running in
the worktree and any uncommitted paths. Healthy is one line; otherwise only the
findings, `error` blocking and `warn` informing. It reads no quota: the data
OpenCode's quota plugin exports is only as fresh as an open TUI, so a limit is
met as a failed turn and answered with the role's `alternate` (see Models).

**Output directory.** A run may take `output_dir`: an existing job directory
inside a Workspaces draft (`.agent/`), outside the worktree and spelled without
wildcards. The session ruleset allows `external_directory` for exactly that
directory, ahead of the person's own outside-path denies (which still win), and
a read-only run may edit there too (never a secret-looking file). The session
metadata keeps it for later turns and every turn validates the stored value
again. It is where a run's reports and screenshots land without a permission
round trip.

**Permissions.** OpenCode 2 evaluates ordered rules, last match wins: global
config, then the agent's own `permissions`, then the session's ruleset; and
every subagent session copies its parent's ruleset (measured on 2.0.23). So the
session ruleset (`policy.rules`) owns each run's constraints for the whole
session tree, and it is applied after a subagent's own posture. It therefore
holds denies, asks and narrow allows: the worktree boundary
(`external_directory` asks, the output directory and OpenCode's own scratch dirs
and the read-only config/skill dirs re-allowed), secrets unreadable, history
rewrites, branch moves, package runners and ungranted Issue writes as asks, the
hard denies (force and protected-branch pushes, merges, `gh api`, Project
writes), and last the person's own denies read from the built-in `build` agent,
so a broad allow never reopens `sudo` or `secret get`. One deliberate exception:
a `write` run allows `edit` in its worktree. Without it every edit is a round
trip to the caller; the cost is that a subagent that denies itself edits
(explore) loses that denial for the run. The allow is placed before the edit
denies for OpenCode's config/skill directories and secret files, which therefore
still win. `read-only` denies edits and the `worker` and `general` subagents. A
write run needs the user's quoted `approval`, a named non-default task branch,
and a worktree no other session is running in (a person's included); read-only
runs may run alongside. V2 wildcards match whole values and `*` crosses `/`, so
secrets are spelled `*.env`, `*.pem`, … (`**/.env` misses a root-level file).

**Requests.** An `ask` pauses the run as `waiting`, from the session or any of
its subagents (requests are listed per location; the plugin keeps those of its
own session tree). The caller answers each with `opencode_request`: a permission
`once`, or `reject` with a reason OpenCode receives; a question with its answer.
There is no broader approval: `always` saves a project-wide approval people's
own sessions would inherit, and a session-wide allow would be copied into every
subagent session after its own denies. The decision rule — inside the user's
approved scope, otherwise reject and ask — lives in the plugin skill and the
engineering entries.

**Models.** A role's model comes from `opencode.roles.<role>.model`, else the
OpenCode agent's own pin. The plugin passes the model explicitly with every turn
(and on every resume or fork), checks it against the service's model catalog
(it must use tools; a variant must be one the model offers), and reports it as
`engine`. A caller may choose any catalog model of `opencode.allowed_providers`
with `model` / `variant`; `opencode_catalog` `models` lists them with each
role's default and alternate. A name outside the providers or the catalog is
refused, never substituted, and an explicit selection binds the rest of that
session.

The defaults are OpenCode's own: a role pins no `model` unless a maintainer has a
reason, so the OpenCode agent's configured model runs (OpenCode uses its own
subscription account, not the Hermes weekly pool). The caller's own model
(the configured `model.default` and the model it last answered with in this
Hermes session; a `post_api_request` hook records it, so a fallback counts too)
is refused by default, so a role does not review or build for the model it
answers to without anyone having chosen that. A role may set `caller_model: allow`
to run on it anyway, and the Assistant's roles do (the owner's decision): the
OpenCode agents' own defaults are the point, a refusal would force every role off
them and break whenever a fallback changes the Assistant's model, and independence
is kept where it matters (a build starts its own reviewer inside its session, a
standalone `review` looks at someone else's work or starts fresh, and the
Assistant accepts through its own QA). Speed tiers and dated snapshots count as
the same model.

A role may name an `alternate` (`provider/model[#variant]`). Nothing switches by
itself: it is listed in the catalog and named in the limit hint, and after a
turn fails with a `limit` provider error the Assistant reruns on it. A read-only
role simply reruns; for a write role the diff is read first.

**Hand-back.** A live caller gets the current state at once. Only while that
state is `running` it also gets a notifier process, launched through the terminal
tool with completion notification, for the next hand-back (it waits through
provider retries, which the run call's state already carried). Any other state
(finished, paused, unknown) is already in the result, and a notifier would return
it again at once, so none is launched. The notifier cannot know whether the
caller already read its hand-back through `opencode_session wait`, so the result
note and the skill have the caller answer such a notification with `[SILENT]`.
A blocking (CLI/resident) caller's run tool returns when the
turn finished (`completed`, `failed`, `interrupted`), paused (`waiting`), is
stuck in a provider retry worth a decision (`running` with `retrying`; a limit
at once, anything else from the third attempt), or cannot be confirmed
(`unknown`: service unreachable for two minutes, no outcome 30 s after the run
stopped, or a prompt whose admission was not confirmed); otherwise it returns
`running` with `timed_out` at `min(opencode.wait_timeout, tool deadline − 30 s,
turn deadline)`. `opencode_session wait` blocks the same way and takes
`through_retry` to wait a retry out. A failed turn records `provider_error`
(`kind` limit / auth / other, model, message) from its last assistant message.
`unknown` blocks nothing: with no record there is nothing to reconcile, so the
caller reads the diff and worktree before another turn.

**Untrusted output.** Run results, diffs, repository files, Issue and PR text
are material written by others. The plugin returns them as results, not
instructions; the skill and entries tell the Assistant never to take an action
outside the engineering scope because such text asks for it.

**Session history.** `opencode_history` is the read side of the same plugin,
separate from execution: it never touches sessions' bindings or `opencode`
settings. Contract, with the Hermes counterpart:
[session-history.md](./session-history.md).

**Tests.** `opencode/tests` run against a fake service (`fake_service.py`) that
models the messages, idle markers, requests and forms the real service returns.
They cannot show what the real service does; the shape of those replies was
measured on OpenCode 2.0.23 and a real-service smoke run is a manual step before
a cutover.

## Rendered UI

Three questions, three owners:

- **Mechanical defects** — OpenCode's build runs its `web_ui_check` tool
  (`opencode/lib/custom-tools/web_ui.ts`) on every change that alters what a
  page renders: horizontal overflow, axe WCAG violations, focus visibility,
  console and page errors, broken images, plus full-page screenshots per
  viewport and color scheme. It measures; it never grades taste. The tool is
  part of OpenCode's own plugin, so it needs no command permission; because it
  also bypasses OpenCode's rules, it enforces its own: it writes only into the
  run's output directory (`<job>/ui-check/<timestamp>/`) or OpenCode's scratch
  directory, never the worktree, loads only local or private-network pages,
  reads a baseline only from under `~/Workspaces`, and runs its Node child with
  a minimal environment.
- **Agreement with the approved look** — given `baseline`
  (`~/Workspaces/Projects/<Group>/assets/ui-baseline/<repo>/`, outside the
  repository), the same tool writes one baseline | current | diff image per
  page; the Assistant reads them and decides whether the approved scope explains
  each change.
- **The look itself** — the user. The Assistant asks only when no baseline exists
  yet, when a change is not explained by the approved scope, or when the approved
  change is a new look. An approved look becomes the baseline.

Screenshots come from the headless check, never from the Assistant's logged-in
browser profile. There are usually no mockups: the first approved screenshots
are the baseline.
