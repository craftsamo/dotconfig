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
| `package.json`    | plugin dependencies (zod), installed by `install.sh --deps` |
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

All global instructions live in `AGENTS.md`. Do not reintroduce an
`instructions` array: OpenCode V2 accepts the key but does not load its files
(anomalyco/opencode#51341).

## Delegation and progress in V2

V2's `subagent` tool takes `agent`, not V1's `task` / `subagent_type`.
The files remain under `agent/` and retain supported legacy frontmatter;
V2 normalizes those settings without rewriting them.

`hidden: true` hides an agent from both interactive discovery and the model's
subagent catalog. The twelve specialist subagents are therefore visible;
the four API-only `hermes-*` primary agents remain hidden. Visibility is not
authorization: caller-specific permissions decide which specialists may run.

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

1. The configured primary model, when its included quota is available.
2. The role's alternate model, when its included quota is available. This can be
   chosen while the primary's quota is unknown, to prefer known included quota.
3. Existing credits, as a last resort, only when both candidates' included
   quotas are verified fresh and exhausted.

If both quotas are unknown and the primary's API proves no usable credits
(`subscription_only`), the usual default is still allowed. If quota is unknown
and the source is credit-funded, nothing is spent unless both included quotas
are exhausted. It covers two routes only: Claude Max (the existing accepted
risk) and ChatGPT Plus. Current model pins, variants and permissions are
unchanged.

| Role                     | Alternate model   | Variant |
| ------------------------ | ----------------- | ------- |
| explore-max              | gpt-6.1-sol       | xhigh   |
| explore-high             | gpt-6.1-sol       | high    |
| explore-medium, reviewer | gpt-6.1-sol       | medium  |
| worker                   | gpt-6.1-sol       | low     |
| explore-spark            | gpt-6-luna        | low     |
| explore-small, verifier  | claude-sonnet-5-5 | low     |
| debugger, reviewer-deep  | claude-opus-5-5   | high    |
| searcher-deep            | claude-sonnet-5-5 | medium  |
| searcher                 | claude-sonnet-5-5 | low     |

Native model IDs are explicit: `gpt-6.1-sol`, `gpt-6-luna`, `claude-opus-5-5`,
`claude-sonnet-5-5` and `claude-haiku-4-5`. There is no Grok, free-tier, API-key
or environment-variable escalation; both ends must be approved native OAuth
accounts. The plugin never buys credits, enables auto-purchase, or changes
account settings or logins.

**Fresh proof.** Quota comes from a direct read of the active OpenCode OAuth
login only, via the provider's usage API (GET). Toast strings, multi-login
export and the cache CLI are not used. A short process-local singleflight
cache (15 s) applies. Unknown authentication proof, or unknown billing, stops
automatic selection before the child is created. Full-context and transport
checks happen before model transmission; a rejected check can leave an empty
child. Timestamps may be at most 30 s old; network calls time out after 5 s.

Fresh billing observations (the native account plus API credit status flags,
or no current paid balance) are kept separate from included quota. A snapshot
is not a durable prohibition. `credits_available` requires an already available,
positive, bounded credit budget.

- **Anthropic** (login method `claude-max`): `extra_usage.is_enabled: false`
  reports no currently usable extra usage; enabled extra usage needs a positive,
  bounded remaining monthly budget for last-resort credits. The known `five_hour` and `seven_day`
  windows and the selected known model's window are checked. The presence of a
  documented field is not an error. In `limits`, the native global kinds
  `session` and `weekly_all` are recorded as shared windows only when
  `scope` is explicitly `null`, with a finite percent in 0..100 and a future
  reset. A `weekly_scoped` entry uses the native model ID only: it counts for
  the selected model only when its `scope.model` ID matches exactly; a
  known scope for a different native model does not apply. An opaque,
  non-native or null model scope with a valid window below 100 does not block
  `available`, because all potentially applicable reported windows still
  have remaining quota; a
  display name is never guessed into a model. An unknown scope at 100 stays
  `unknown` (as does an unknown kind or a malformed entry) unless shared or
  selected-model exhaustion is proven, and credits are never admitted
  prematurely. Malformed windows stay `unknown`. A shared window that is
  exhausted is still valid despite an opaque entry. Not every invalid API
  response is treated as a model-scope problem.
- **OpenAI** (`chatgpt-browser` or headless): metadata must carry the
  accountID and `plan_type` plus the current `rate_limit` windows. An explicit
  backend `allowed` flag and `limit_reached` decision are used; percentages
  alone (even 100) cannot prove exhaustion. `spend_control` is a recognized
  status, not permission to buy credits.

**Ongoing transport check.** The actual HTTP and WebSocket transports are
verified for the subscription host, subscription auth and absence of an API
key. Title, compaction and generate requests are guarded too. This is not a
global financial guarantee: tools, other plugins and stateless `ctx.generate`
are out of scope. Credit authorization applies only to the selected
provider/account; cross-provider title, generate and similar requests need
fresh available included quota. The default unknown-quota exception covers the
exact primary selected model only, not auxiliary requests.

**Marker.** A durable metadata marker is written on the new child before its
prompt, which closes the registration race and survives a background launch or a
reload. No credentials or PII go into quota or token files or logs; the
connectionID stays in the internal marker only, never in logs.

**Passthrough.** An explicit model, an existing sessionID, unknown roles and
roles whose configured models changed keep the normal selection. Once an
included-funded child has started, quota exhaustion stops it: no model switch,
restart, probe resubmit
or waiting for the 5 h reset. A short native transient retry is allowed. A child
funded by admitted credits can run while included quota is exhausted; it carries
a persisted credit-mode marker and is guarded on every request; if credits are
no longer available it stops rather than buying more.
Native providers may move to credits mid-request when an admitted included run
runs out, even if the other provider has included quota left. The strict order
applies only before launch; it is not a server-enforced no-paid gate. Existing
older markers stay strict because the optional `allowUnknownQuota` is absent
(`false`). The root parent's model
and retry policy are unchanged, so a parent on the same pool may still fail.
Protection is sticky for marked children, including completed continuations:
historical execution outcomes cannot prove current idleness. They retain their
selected role and model; start a new child for a different explicit selection.

**Context limit.** The first alternate's text context may be at most
160000 UTF-8 bytes plus 32768 headroom, relative to the catalog input or
context minus output. The first primary HTTP body or WebSocket frame is also
measured before transmission, including additions from later context hooks.
Media or unknown sizes reject, and no compaction is
run to make a launch fit. A later native compaction happens only when its
configured subscription route is approved and quota is available; otherwise it
stops.

**Reporting.** The UI report uses the built-in tool's content and metadata with
`from` / `to`, including background launches, and the funding source (included
or credits). Declared structured output is unchanged.

**Setup.** Pinned to OpenCode V2.0.23: on any other release the automatic new
launch is rejected, but a manual pass still works. Re-validate the mocked tests
after an upgrade. Run them from the repo root with
`bun test opencode/lib/subagent-fallback`; no test-runner script or new
dependency is installed.

Last-resort credits are used only when the plugin option `creditsLastResort` is
`true`, set by explicit user authorization; otherwise the launch stops.

To disable new selection, set the plugin's `options.enabled` to `false`;
guards for already-marked children remain. To keep those guards, do not remove
the plugin or config entries or change auth while it is active. Keep the entry
last, after quota, and trust no other later request mutator.

Current activation: `enabled` is `true` and `creditsLastResort` is `true`;
`allowDiagnostics` is removed. Activation followed the checks below and an
actual Claude-only GET after the fix that returned HTTP 200, `proof_accepted`,
quota `available`, `billingState` `subscription_only`, with the known kinds
`session`, `weekly_all` and `weekly_scoped` in safe shapes. The earlier
`parser_reject` came from our assumption that every supplemental limit was
`weekly_scoped`, not from a missing Max x20 plan. The earlier OpenAI probe was
accepted with quota
available and `credits_available`; no fresh OpenAI GET has been made since. Mock
verification does not prove external billing or entitlement behavior, nor the
actual quality of any role on its alternate model. The plugin never purchases
credits, but cannot prevent the provider's in-flight credit charges.

Verification: review approved; 359 mocked tests and 1184 assertions passed,
along with the Bun build and diff checks.

Diagnostic RPC methods are all gated by the same `allowDiagnostics: true`
plugin option plus an explicit local RPC call; none is a default behavior and
none runs an API call without user consent:

- `dotconfig.subagent-preflight.inspectQuota`: one GET per provider, memoized
  per plugin registration.
- `dotconfig.subagent-preflight.inspectAnthropicQuota`: Anthropic only, one GET,
  memoized and shared with the aggregate method.
- `dotconfig.subagent-preflight.inspectParser`: runs the parser on FIXED
  synthetic fixtures, with ZERO GETs and no auth; it returns the parser
  revision `v2` and the fixture outcomes (50 available, 100 unknown), and the
  active service was verified (no global service restart).

None launches an LLM or child. They return only fixed states, status, reasons
and kind enum names. One-shot usage diagnostics also carry `limitShapes` (at
most 20) with whitelisted field names mapped to type codes and sanitized short
kind strings; no accountIDs, numeric usage, real reset dates, model display
names, full bodies or raw credentials. The user explicitly authorized this
structural information. The flag is absent by default: disable it after the
specific authorized call; any future diagnostic needs the user's explicit
permission. Credentials are never included in diagnostic output.

## Accounts

- **Anthropic** (Claude Pro/Max, the sub account): OpenCode's own OAuth login
  through the `@ex-machina/opencode-anthropic-auth` plugin. It never reads or
  writes Claude Code's Keychain entries, so Hermes' account (the default
  `Claude Code-credentials` entry) and Claude Code stay untouched. Log in from
  a browser signed into the sub account:
  `opencode auth login anthropic --method claude-max`.
- **OpenAI**: built-in ChatGPT login,
  `opencode auth login openai --method chatgpt-browser`.
- **xAI** (`x_search`): built-in SuperGrok login,
  `opencode auth login xai --method device`; `XAI_API_KEY` wins when set.

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
