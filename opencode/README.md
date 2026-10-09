# opencode

XDG native: OpenCode 2 reads `~/.config/opencode/` directly — no symlinks
needed. Installed from the `anomalyco/tap/opencode-v2` formula (see the
[`Brewfile`](../Brewfile)).

## User-managed content

| Path              | Purpose                                                     |
| ----------------- | ----------------------------------------------------------- |
| `opencode.jsonc`  | main configuration (models, permissions, MCP, ...)          |
| `cli.json`        | terminal UI preferences (theme, keybinds, session view)     |
| `AGENTS.md`       | global instructions, loaded into every session              |
| `agent/`          | custom agents / subagents (`*.md`)                          |
| `command/`        | custom slash commands (`*.md`)                              |
| `plugins/`        | local plugins (`*.ts`), auto-discovered                     |
| `lib/`            | code imported by plugins (not scanned by OpenCode)          |
| `skills/`         | opencode-only skills (`<name>/SKILL.md`)                    |
| `package.json`    | plugin dependencies, installed by `install.sh --deps`       |
| `opencode-quota/` | quota plugin settings (`quota-toast.jsonc`)                 |

A fresh clone needs `./install.sh --deps` once: OpenCode 2 does not install
config-directory dependencies, and without `node_modules/zod` the custom-tools
plugin fails to load. The `opencode-v2` formula conflicts with the 1.x
`opencode` formula; uninstall that first on a machine that still has it.

Custom tools live in `lib/custom-tools/<file>.ts` and are registered by
`plugins/custom-tools.ts`, which exports both a V1 `server()` and a V2
`setup()`. Tool IDs keep the `<file>_<export>` form (`git_secret_scan`,
`x_search`, ...), matching the permission keys in `opencode.jsonc`. Do not
add a `tools/` directory: V1 would register the same IDs twice and V2 does
not load it. Keep subdirectories out of `plugins/`; V2 loads each one as a
plugin package.

Custom tools run without OpenCode's permission rules, so each enforces its own
limits. `web_ui_check` (`lib/custom-tools/web_ui.ts`) runs
`lib/web-ui-check/web-ui-check.mjs` in a Node child process, because Playwright
is not reliable inside the Bun plugin host; `install.sh --deps` also installs
Playwright's headless shell for it. Tests: `bun test lib/custom-tools` and
`node --test lib/web-ui-check/web-ui-check.test.mjs`.

All global instructions live in `AGENTS.md`. Do not reintroduce an
`instructions` array: OpenCode V2 accepts the key but does not load its files
(anomalyco/opencode#51341).

## Delegation and progress in V2

V2's `subagent` tool takes `agent`, not V1's `task` / `subagent_type`.
The files remain under `agent/` and retain supported legacy frontmatter;
V2 normalizes those settings without rewriting them.

`hidden: true` hides an agent from both interactive discovery and the model's
subagent catalog; no agent here uses it, so the twelve specialist subagents
are visible. Hermes drives the plan, build, review and debug primaries through
the API like a person does. Visibility is not authorization: caller-specific
permissions decide which specialists may run.

- Plan allows read-only exploration, research, diagnosis, and review, but not
  `general`, `worker`, or `verifier` (which can apply formatters).
- Debug and Review exclude editing agents and ask `verifier` for checks only,
  never formatter application. Build may request scoped formatter application.
- Plan and the built-in Explore explicitly deny edits, overriding the global
  `edit: ask`. Plan retains its exception for `~/.opencode/plan/*`; writing a
  plan file still requires the user's explicit request.

New subagents use their configured model, otherwise the parent's model. A
user-requested per-call `model` override takes precedence. General and the
built-in Explore have no model configured and inherit the parent; use the
specialists for their role and cheaper default models. Primary sessions retain
their selected model when switching agents; the agent configuration is not a
guarantee of the model currently selected in a session.

V2 has no native Todo tool. Keep ephemeral execution steps in the conversation
as `Phase{N}.{m} - <task> (executor)`, updating pending / in-progress / completed /
blocked statuses and restating unfinished work at handoffs. Plan asks the user
to switch to Build before execution. Do not create local TODO files or claim
that a native list was registered. Durable work still uses GitHub Projects
when requested; no Todo plugin is installed for this workaround.

Empty directories carry a `.gitkeep` so the skeleton survives a fresh clone.

`skills/` holds only the skills that depend on opencode itself — its
subagents, custom tools, or the Plan/Build handoff. Skills any agent can
follow live in [`agents/curated/`](../agents/README.md) and are picked up here
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

1. The configured primary model, unless Quota reports it exhausted.
2. The role's alternate, when the primary is known exhausted and the alternate
   is not known exhausted. Missing or stale alternate data does not block
   this, since an exhausted primary is the worse bet.
3. The usual primary with provider-managed credits as a last resort, when both
   are known exhausted and `creditsLastResort` is `true`. This attempts a
   normal provider request; it does not prove a positive credit balance or
   guarantee success.

Missing, stale or unreadable data about the primary keeps the configured
default, not a quota error or an automatic model switch. No independent
balance/entitlement check is performed. Current model pins, variants and
permissions are unchanged.

| Role                     | Alternate model   | Variant |
| ------------------------ | ----------------- | ------- |
| explore-max              | gpt-6.1-sol       | xhigh   |
| explore-high             | gpt-6.1-sol       | high    |
| explore-medium, reviewer | gpt-6.1-sol       | medium  |
| worker                   | gpt-6.1-sol       | low     |
| explore-spark            | gpt-6-luna        | low     |
| explore-small, verifier  | claude-haiku-5-5  | low     |
| debugger, reviewer-deep  | claude-opus-5-5   | high    |
| searcher-deep            | claude-sonnet-5-5 | medium  |
| searcher                 | claude-sonnet-5-5 | low     |

Native model IDs are explicit: `gpt-6.1-sol`, `gpt-6-luna`, `claude-opus-5-5`,
`claude-sonnet-5-5` and `claude-haiku-5-5`. There is no Grok, free-tier, API-key
or environment-variable escalation; both ends must be approved native OAuth
accounts. The plugin never buys credits, enables auto-purchase, or changes
account settings or logins.

**Shared information.** Reads Quota 5.0.1's public v2 JSON export once before
each eligible launch: `$XDG_CACHE_HOME/opencode/quota-export.json`, or
`~/.cache/opencode/quota-export.json`. Quota's existing `export.enabled` setting
is enabled in `opencode-quota/quota-toast.jsonc`. Its home footer writes the file
on normal refresh; the selector does not fetch usage, run the Quota CLI, start
timers, read internal caches or patch Quota. A custom export path can be matched
with the plugin option `quotaExportPath` (absolute path).

Rows are matched to the active OpenCode connection using `sourceId`. Only the
5h and Weekly rows decide, and at least one must be present: some ChatGPT plans
have no 5h window, and an exhausted ChatGPT account may export just one row. If
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
contains connection IDs and display labels, but no access tokens.

**Passthrough.** An explicit model, an existing sessionID, unknown roles and
roles whose configured models changed keep the normal selection. During a task,
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

**Context limit.** The first alternate's text context may be at most
160000 UTF-8 bytes plus 32768 headroom, relative to the catalog input or
context minus output. The first primary HTTP body or WebSocket frame is also
measured before transmission, including additions from later context hooks.
Media or unknown sizes reject, and no compaction is
run to make a launch fit. Later native compaction retains the subscription
identity and route checks, without a fresh quota requirement.

**Reporting.** The UI report uses the built-in tool's content and metadata with
`from` / `to`, including background launches. `funding: included` reports the
fallback preference; `funding: provider` means both reported pools were empty
and the provider decides whether the default can proceed. Neither proves the
actual charge. Declared structured output is unchanged.

**Setup.** Pinned to OpenCode V2.0.23: on any other release the automatic new
launch is rejected, but a manual pass still works. Re-validate the mocked tests
after an upgrade. Run them from the repo root with
`bun test opencode/lib/subagent-fallback`; no test-runner script or new
dependency is installed.

When both reported pools are empty, the default-provider attempt requires
`creditsLastResort: true`; otherwise the launch stops. Missing Quota data still
uses the default, so this option is not a global prohibition on credit charges.

To disable new selection, set the plugin's `options.enabled` to `false`;
guards for already-marked children remain. To keep those guards, do not remove
the plugin or config entries or change auth while it is active. Keep the entry
last, after quota, and trust no other later request mutator.

Options: `enabled: true`, `creditsLastResort: true`, and for the credit lanes
below `creditLanes` (ordered provider IDs), `creditCooldownMs` (default one
hour) and `primaryFallback` (default on). The independent usage reader, billing parser and usage-diagnostic RPCs have been
removed. Tests use synthetic public exports and mocked OpenCode transports;
they do not probe providers or establish real billing/entitlement behavior.

## Console credit lanes

The same plugin spends the Max plans' monthly API credits (see "Accounts")
through `options.creditLanes`, an ordered list of provider IDs. A missing or
empty list turns all of this off, in-flight moves included; `enabled: false`
stops only new lane launches.

- **Specialists** (the six roles with a Claude primary). A new launch takes the
  first lane not known empty, with no subscription marker: the OAuth guards
  above do not apply to API-key requests. With every lane empty, the preflight
  above decides as before. The report carries `funding: console-credit` with
  `from` / `to`. Agent files keep the subscription model; pinning a role to a
  lane there skips the preflight and fails on an empty balance.
- **In flight.** An empty balance (a plain 400 recognised by its "credit
  balance is too low" text), a bad key (401/403) or a window limit marks the
  lane out (for `creditCooldownMs`, one hour; a window limit only for the wait
  it asked for) and moves the session to the next provider with the same model
  and variant, repeating the same step. Only requests on the session's own
  model count: compaction and title requests never move it. These
  fail before anything is generated, so nothing is billed twice. A specialist
  goes lane, next lane, subscription; after a long subscription limit it stops,
  so the parent relaunches it and the preflight can pick the other vendor.
- **Primary sessions** (no parent). On the subscription's window limit
  (`provider.quota`, or a rate limit that asks for more than ten seconds) they
  move to the first lane, and on to the next lane when one is empty; on a
  lane, the subscription is the last stop. Nothing moves a primary back while
  its lane works: return with `/models`. `primaryFallback: false` keeps the
  primary on the subscription.
- **Probing.** There is no balance API: a lane is probed by use. After its
  cooldown the next request fails fast if it is still empty, which costs one
  rejected request an hour.
- A session never revisits a provider within five minutes, so the chain cannot
  loop. Children launched under the subscription preflight keep their own
  guards and are never moved.

**Balance.** Anthropic has no balance API, and an Admin API is not available to
personal orgs, so `/credits` (or `bun opencode/lib/credit-lanes/status.ts`)
estimates it from `opencode stats`: spend per lane since its grant, what is
left, the pace and what would expire unused. `opencode stats` read within 3% of
Console and answers in about a second. Edit `lib/credit-lanes/lanes.json`
(amount, `grantedOn`, `expiresOn`) at each renewal; spend before `grantedOn`
would otherwise be counted. Quota's own local estimate was tried and dropped:
it re-reads the whole 25 GB history database on every refresh (about a minute),
which stalled the service into a restart loop.

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

- **Anthropic** (Claude Pro/Max, the sub account): OpenCode's own OAuth login
  through the `@ex-machina/opencode-anthropic-auth` plugin. It never reads or
  writes Claude Code's Keychain entries, so Hermes' account (the default
  `Claude Code-credentials` entry) and Claude Code stay untouched. Log in from
  a browser signed into the sub account:
  `opencode auth login anthropic --method claude-max`.
- **Anthropic Console credit lanes**: the monthly API credits that Max plans
  grant (Max 5x and 20x, one Console org per plan, spent before any purchased
  balance and lost at the end of the billing cycle). They work only through an
  API key, never in Claude Code or as extra usage. Two providers,
  `anthropic-credit-main` (the 20x plan's org) and `anthropic-credit-sub` (the
  5x plan's), read `ANTHROPIC_CREDIT_MAIN_ACCOUNT_KEY` and
  `ANTHROPIC_CREDIT_SUB_ACCOUNT_KEY` from the Keychain project `opencode`.
  Never name a key `ANTHROPIC_API_KEY`: it would take precedence over the OAuth
  login. A lane stays inactive while its variable is unset, and its models list
  Opus, Sonnet and Haiku 5.5 explicitly (`canonical` inherits prices, not the
  model list). Neither org has a payment method or auto-reload, so an empty
  balance fails the request instead of billing. The service reads the
  environment at start: a new or rotated key needs `opencode service restart`,
  and `opencode reload` is enough for config only.
- **OpenAI**: built-in ChatGPT login,
  `opencode auth login openai --method chatgpt-browser`.
- **xAI** (`x_search`): built-in SuperGrok login,
  `opencode auth login xai --method device`; `XAI_API_KEY` wins when set. Quota
  shows its usage in the footer and `/quota` (`enabledProviders` includes
  `xai`); the launch selector ignores it, as no specialist role uses Grok.

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
