# Models, authentication and secrets

Model fallback chains, authentication inheritance and secrets layering. Read it before changing a profile's model chain, a credential or a secret layer. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Models and fallback chains

Each profile carries its own `model:` (tier 1) plus a `fallback_providers:`
list (tiers 2+); the actual chains live in `profiles/*/config.example.yaml`, the
private real `profiles/*/config.yaml` and the root `config.yaml`, this section keeps only the rules behind them.
`fallback_providers` is **per-turn**: it triggers on errors (429 / 5xx / 401 /
404 / malformed) and the primary is restored on the next turn. A tier may reuse
the same provider with a different model; only an identical provider+model pair
is skipped.

Models are chosen per role by the capability the role needs, not by the
strongest model; the budget is each subscription's usage allowance, not
dollars. **Hermes chat and auxiliary models run on Claude first**, on the
Hermes Claude account; the ChatGPT subscription belongs to OpenCode, and
Hermes touches it for image generation and, on every profile except
`searcher` (which leads on it), as a last-resort chat tier ahead of the
OpenRouter tail (see "Codex" below).

- **Opus 5.5 leads the judgment profiles** (`default`, `assistant`, `marketer`,
  `video-creator`), **Fable 5.1 leads `creator`**, and **Sonnet 5.5 leads**
  `researcher`, `writer`, `image-creator` and `audio-creator` (`writer` to
  spare the shared Claude weekly pool). An Opus-led chain takes **Fable 5.1 as
  T2** (`default` is the exception, below), never another Opus: every Opus model draws on the same Opus weekly sub-cap, so an Opus T2
  fails exactly when that cap is why T1 failed, while Fable draws on its own
  50%-of-week ceiling. The Fable-led `creator` takes Opus 5.5 as T2 for the
  same reason. (An Opus on the Console API lane is a different account,
  with no shared sub-cap: see "Console credit lanes".) **Sonnet 5.5 is the last
  Claude tier** of an Opus- or Fable-led chain: Anthropic meters Opus separately from "all
  other models", so Sonnet stays alive when the Opus cap is the reason T1
  failed. A Sonnet-led chain takes Opus 5.5 as T2, then Fable 5.1 where it has
  one (`researcher` goes straight to Codex and carries no Fable). The profile
  configs own the exact chains.
- **`default` stays off Fable deliberately** — every `--clone` inherits its
  chain, and a neutral starting point should not lead with the model that has
  the tightest sub-cap.
- **The Creator family splits by hand.** `video-creator` leads on Opus 5.5
  and `creator` on Fable 5.1; `image-creator` and `audio-creator` lead on Sonnet 5.5, which
  matches Opus on image and audio leaves at about 0.6x the tokens but is clearly
  behind on authored video (rule and reason:
  [decision](./decisions/creator-family-model-split.md)). All four keep
  `openrouter` / `minimax/minimax-m3` as the tail, so a hand still inherits
  `creator`'s vision fallback for eyeballing generated assets. A video job makes
  hundreds of `vision_analyze` calls, so concurrent Opus video jobs hit a 429
  concurrency limit, not the usage cap. A silent drop to the Sonnet or minimax
  tier degrades Creator and video output: watch the Opus sub-cap.
- **Searcher leads on GPT-6.1 Sol** (`openai-codex`), then Sonnet 5.5, then
  `xai-oauth` / grok-4.7, then the OpenRouter tail. xAI stays in the chain
  because `x_search` and Imagine video draw on it. Searcher is the only profile
  that leads on the shared ChatGPT allowance, so re-size OpenCode's usage if its
  retrieval volume grows ("Codex" below). Its window is pinned
  (`model.context_length: 1000000`, `compression.threshold: 0.5`,
  `codex_gpt55_autoraise: false`) so compression starts at 500k: the Codex
  catalog still reports 272k for GPT-6.1 Sol, and the autoraise would pin the
  trigger to 85 % of the window instead.
- The coding model inside OpenCode is a separate layer: its roles use OpenCode's
  own per-agent defaults (OpenCode's own Anthropic account, nothing from the
  Hermes weekly pool), optionally overridden by `model` on a role in
  `opencode.roles`; see [`opencode.md`](./opencode.md) "Models". A GPT-family
  alternate draws on the ChatGPT allowance below.

The tracked examples name only `provider: anthropic` so they run on a stock
runtime. In the private configs on the patched runtime, every `anthropic-oauth`
tier is the subscription lane and the `anthropic` tiers on assistant, marketer
and writer are the Console lane ("Console credit lanes").

A `fallback_providers` entry carries no per-entry `reasoning_effort` or
`api_mode`: on each fallback activation Hermes re-resolves both from provider /
base URL / model. **There is no per-tier effort knob** —
`agent.reasoning_overrides` is a _session_ concept (driven by `/model`), not a
config key, so a profile's single `agent.reasoning_effort` applies to every tier
in its chain.

Provider facts:

- **Anthropic native** — the subscription is one or more PKCE rows in the
  root `anthropic-oauth` credential pool, inherited read-only by every profile
  (see "Authentication inheritance"). **Fable 5.1 is not in the
  `hermes model` picker** (`/v1/models` lags the alias), so it is written
  straight into `config.yaml`.
- **Codex** — **images, plus one last-resort chat tier**: GPT-6.1 Sol sits ahead
  of the OpenRouter tail on every profile (`default` included), so a spent
  Claude weekly pool degrades to a capable model instead of a cheap one. The
  ChatGPT subscription is sized for OpenCode (its searchers, `debugger`,
  `reviewer-deep` and cheap subagents, plus the `alternate` of the Assistant's
  OpenCode roles) and shares one Plus allowance with Hermes. The tier only runs
  once the Claude tiers above it have failed, but a `video-creator` job reads
  tens of millions of tokens, so a long spell on it drains the allowance:
  re-size OpenCode's usage before adding the tier to an aux task. Searcher's
  aux tasks stay `auto`, so they run on
  GPT-6.1 Sol. GPT-6.1 Sol rejects `reasoning.effort` `none` / `minimal`, so
  keep `reasoning_effort` at `low` or above. The Codex OAuth login in `default`
  stays on purpose: the `image-fallback` chains still try `openai-codex`.
- **xAI** — `xai-oauth` is a flat-rate **xAI subscription**, not the metered
  `XAI_API_KEY` API, so searcher adds no worker to the Claude weekly pool.
  grok-4.7 is not on Hermes' reasoning-capable allowlist
  (`model_metadata.py`), so Hermes drops `reasoning_effort` for it on purpose:
  xAI answers an unsupported `reasoningEffort` with 400.

  **A lapsed xAI OAuth hides `x_search`.** Chat does not depend on that login
  (Codex leads searcher), but the credential gate still removes `x_search` from
  the schema, which `hermes doctor` misleadingly reports as
  `x_search (missing XAI_API_KEY)`. Re-authenticate with `hermes model` from
  the **default** profile — never with `-p`, which would write the worker's own
  `auth.json` and shadow the inherited credential.

- **Auxiliary models are pinned, not `auto`.** `auto` resolves to the profile's
  own main provider _and main model_ (`agent/auxiliary_client.py`), which would
  run compression, titles and triage on the most expensive model. Every task
  except `vision` and `web_extract` is pinned to a cheap Claude sibling with a
  `fallback_chain` to the OpenRouter text-only tail (searcher stays `auto`);
  below that sit the configured chain and a last-resort hop to the main model,
  so a pinned aux model is never a single point of failure. **`vision`
  deliberately stays `auto`** — pinning it disables the main model's native
  image vision (see [`ops/plugins.md`](ops/plugins.md)). **`background_review`**
  is pinned to Sonnet on `assistant`: on `auto` it replays the whole
  conversation on Opus every few turns. Auxiliary usage is read from
  `session_model_usage` in each profile's `state.db` (`task <> ''`), not from
  `sessions`.
- **OpenRouter tails split vision vs text-only.** Profiles whose fallback turns
  may need to SEE something keep a vision-capable tail (`xiaomi/mimo-v2.5`;
  Creator's hands `minimax/minimax-m3`; video analysis stays decoupled via the
  `video-analyze-mimo` plugin, [`ops/plugins.md`](ops/plugins.md)); text-only
  work (`writer`) rides the cheaper `deepseek/deepseek-v4-flash`.
- **Copilot is in no chain** — catalog drift 404s a tier silently.
  `GITHUB_TOKEN` stays in the `hermes` layer for the Skills Hub; it is not a
  model-provider credential.

### Fable and the Claude weekly pool

These facts govern the paired Claude tiers:

1. **Fable is not a separate quota tank.** It is capped at **≤50% of the weekly
   pool**, drawn from the _same_ pool as Opus, and burns it faster. A Fable ⇄
   Opus step only rescues the case where one model's sub-cap is exhausted while
   the overall weekly has room; if the shared weekly or the 5-hour session limit
   tripped, both are dead and the chain continues to Sonnet 5.5 and then the
   OpenRouter tail. **That is why the second Claude model sits at T2**: the
   sub-cap case is the _long_ failure (until the week rolls over) and in exactly
   that case the other Claude model is still alive. The same pool rows back
   every profile, so a busy Creator week can drain an account for all of them.
2. **A sub-cap 429 benches a model, a weekly 429 benches the account.** A 429
   that carries a reset or retry signal becomes a model-scoped cooldown on the
   row, so the same account's other models stay available and the T2 step
   works. A `usage_limit_reached` 429 with no such signal is classified as
   billing and benches the whole row for an hour; the pool then rotates to the
   next account's row, and only with no other row does the walk skip every
   later tier on that provider (`_candidate_pool_exhausted`) and degrade to
   the next provider. The second account in the pool is therefore what keeps
   the Claude tiers alive once one account's week is spent.
3. **Hermes has no per-model quota memory.** The "included Fable usage for this
   week" message carries no reset, so a fixed 1-hour credential cooldown applies
   while the agent-level fallback cooldown is only 60 s: once a weekly cap is
   hit, that costs **one wasted request per turn until the week rolls over**.
   Low-turn profiles absorb that. The **assistant** is the latency-sensitive
   front door: when its T1's weekly cap is reached, switch its live sessions
   with **`/model`**; that manual escape is what makes a capped Claude T1
   acceptable there.
4. **Adaptive thinking, not manual budgets.** Modern Claude gets
   `thinking: {type: adaptive}` + `output_config: {effort: …}`; the legacy
   `budget_tokens` table does not apply. Prefer `high` over `xhigh` for long
   structured output, or Hermes can burn the whole output budget on reasoning;
   if that warning appears, drop to `medium` or raise `max_tokens`.
5. **Some request shapes are refused per model.** Opus 5.5 and Fable thinking
   cannot be disabled (HTTP 400), so a thinking-off request omits `thinking`.
   Sonnet 5.5 has a real off (`thinking: {type: between_tools}` on
   anthropic.com). Opus 5.5, Sonnet 5.5, Fable 5.1 and Mythos 5.1 reject forced
   `tool_choice`, so the leaked-invoke-markup recovery resends the ordinary
   request. The omissions and the recovery are mostly local patches in the Hermes checkout
   (check `scripts/check-local-patches.sh`), decided from
   `_MANDATORY_THINKING_CLAUDE_SUBSTRINGS`,
   `_BETWEEN_TOOLS_OFF_CLAUDE_SUBSTRINGS` and
   `_NO_FORCED_TOOL_CHOICE_CLAUDE_SUBSTRINGS`; an unknown Claude id defaults to
   "disable accepted, forcing accepted", so a new Claude release is not covered
   until its breaking changes are read against these lists.

### Console credit lanes

On the patched runtime, Anthropic is two providers on one backend that bill
different accounts: `anthropic-oauth` bills the Claude subscription, `anthropic`
bills a Console API key (a stock runtime has the one `anthropic`). Each lane refuses the other's token shape (a Console key is `sk-ant-api…`
or `sk-ant-usr…`), so one never bills the other. Max plans grant monthly API
credits, one Console org per plan, spent before any purchased balance and lost
at the end of the billing cycle; Claude Code and extra usage cannot spend them,
only an API key can. OpenCode spends the same credits
([`opencode/README.md`](../../opencode/README.md) "Console credit lanes").

- **Tier.** assistant carries `anthropic` / Opus 5.5 right after T1, then the
  rest of its chain; a credit Opus draws on no subscription sub-cap, which is
  why it may sit ahead of Fable. **marketer and writer lead on the lane** (Opus
  5.5 and Sonnet 5.5) and fall back to the subscription's tier of the same
  model: credits expire, and the Sub org's balance needs a steady consumer
  (about $10 a day to be spent by its renewal), which two low-turn profiles
  supply. assistant stays subscription-first: its volume would empty Sub in days
  and a lane 429 would slow the front door. Creator's family stays off the lane:
  one video job would empty it. While the subscription's reset is ahead, turns
  stay on the lane: that drains the credits by design.
- **Rate limits** are per Console org (Start tier when linked for credits),
  shared with OpenCode's parallel specialists; a higher tier is a request in the
  Console.
- **Three orgs, one tier.** The `anthropic` credential pool holds the keys as
  env-sourced entries (`source: env:<VAR>`, no secret on disk, re-hydrated on
  every load; there is no CLI for one, the row is written into the root
  `auth.json`): `ANTHROPIC_CREDIT_TEAM_ACCOUNT_KEY` (priority 0, a key another
  org's owner lent, whose grant expires on their schedule), then
  `ANTHROPIC_CREDIT_SUB_ACCOUNT_KEY` (1) and `ANTHROPIC_CREDIT_MAIN_ACCOUNT_KEY`
  (2). Among the own orgs Sub (the OpenCode account's) is first; OpenCode
  spends them the other way round, so the two start on different orgs and one
  org's rate limit is not hit by both at once.
- **Failure.** An empty balance is a plain 400 ("credit balance is too low")
  that the classifier treats as billing, so the turn moves on at once: a billing
  400 benches that key for an hour and rotates to the next pool entry, a 429 is
  retried once and then rotates, a 401 rotates, and with every key spent the
  turn moves to the next fallback entry. Benches are saved to disk, and while
  more than ten minutes of one remain the walk skips the lane without a request.
  In the last ten minutes of a bench the lane counts as unconfigured and is
  skipped for the rest of that cached session: after the credits refill, restart
  the gateway if a session stays off the lane (for a profile that leads on the
  lane, also check `billing_provider` in its `session_model_usage`). The
  primary's own restore cooldown is 60 s, doubling on repeated rate-limit or
  billing failures up to 4 h, or the provider's reset time when a 429 gives one.
- **Auxiliary tasks follow the turn.** An `auto` auxiliary call (`vision`,
  `web_extract`) uses the main runtime, so while turns stay on the lane those
  calls bill the credits too. After a payment error it tries the task's own
  `fallback_chain`, then the main model, and does not walk `fallback_providers`;
  an auxiliary call treats only 402/403/404/429 as a payment error, so a lane's
  400 does not fall through.
- **Cost.** A lane turn reports an estimated cost from Hermes' price table; the
  real spend is the Console's. OpenCode's `/credits` balance counts it: it
  reads every profile's `session_model_usage` rows billed to `anthropic`
  (read-only) and charges them in the pool's order. That order is
  `hermes.order` in `opencode/lib/credit-lanes/lanes.json` (a private overlay
  file; the tracked `lanes.example.json` shows the shape); change it with the
  pool's priorities, or the estimate charges the wrong org.
- **Keys.** The env names sit in the shared `hermes` layer and, as a second
  copy of the same value, in OpenCode's `opencode` project. The pool entries
  read the variable by name, so rotate both copies and restart the gateway. A
  profile without its own `anthropic` rows reads the root `auth.json` read-only;
  its first rotation or bench writes a copy of its own, which then shadows the
  root: `hermes auth list` at the root does not show or clear that profile's
  bench, and a rename at the root does not reach it.
- **Exposure.** Terminal and code-execution children drop secrets by name, and
  the list holds each registered provider's variables, not these names, so a
  child of any profile that holds them can read every lane key (in the shared
  layer, every profile). A leak costs at most the orgs' monthly credits; for the
  lent key that is someone else's grant, so it stays only while that lasts.

### `agent.*` does not inherit from the root profile

A named profile's config is `$HERMES_HOME/config.yaml` deep-merged with the
built-in `DEFAULT_CONFIG` **only** — the root `~/.hermes/config.yaml` is never a
parent. `--clone` copies it once at creation time; that is not live inheritance.

`DEFAULT_CONFIG["agent"]` has **no** `reasoning_effort`, so omitting it does not
inherit the root's `medium` — it resolves to `None`, and each provider path then
differs (native Anthropic sends no `thinking`/`output_config`, Codex defaults to
`medium`, OpenRouter to `medium` enabled): a T1 left unspecified while its
fallbacks run `medium`. **Set `agent.*` keys per profile, always.**

## Authentication inheritance

`auth.json` is per-profile, **but** a named profile with no entry for a provider
falls back **read-only** to the default profile's `~/.hermes/auth.json`.

- **OAuth logins happen in default only** (`hermes model`, no `-p`). Codex,
  Copilot and xAI-OAuth creds are then inherited by every profile. Running
  `hermes model` _inside_ a worker writes that profile's `auth.json` and shadows
  the inherited creds for that provider (writes never propagate).
- **Shadowed creds survive a default re-login, and `hermes doctor` will not see
  it.** Doctor inspects default, so it reports the provider healthy while a
  worker still loads its own stale entry; the symptom is uneven (the model keeps
  answering while a tool that resolves through the credential pool, such as
  `x_search`, goes missing). Confirm with `providers` in
  `~/.hermes/profiles/<name>/auth.json`; repair by dropping that provider key so
  the profile inherits default again. Prefer editing the file over
  `hermes auth logout`, which may revoke upstream and take the shared credential
  down with it.
- **Anthropic subscription = PKCE rows in the `anthropic-oauth` pool.** Each
  `hermes auth add anthropic-oauth --label <name>` (from `default`, in a
  browser signed into that account) adds one row with its own refresh token;
  the pool refreshes it before expiry and, on a 429 usage limit, a billing
  error or a 401, benches it and rotates to the next row. Several Claude
  accounts therefore sit in one pool and take over from each other inside a
  turn; a `fallback_providers` tier cannot name an account (same provider +
  same model counts as the same deployment and is skipped), so the pool is the
  only place account order lives. **Order is `priority` among the manual rows
  (`hermes auth priority anthropic-oauth <label> 0` + gateway restart to lead
  with another one)**; manual rows always sort ahead of the seeded ones
  (`ANTHROPIC_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, then the Claude Code Keychain
  entry `claude_code`). Keep the Keychain row suppressed (`hermes auth remove
  anthropic-oauth claude_code`; `auth add` clears every suppression of the
  provider, so remove it again after each login) so a `claude /login` can never
  change which account Hermes bills. Which label is which account, and which
  one leads, is this machine's layout and lives in the private overlay.
  A `manual:hermes_pkce` row keeps its secrets in `auth.json`; a row whose
  tokens are empty is skipped silently (`hermes auth refresh anthropic-oauth
  <label>` proves a row alive, `hermes auth list` shows a dead one).
- **Refresh tokens are single-use, so never fork a row.** `-p <profile> auth
  add`, copying `auth.json` or re-adding a root row while a profile still holds
  a copy gives two holders of one lineage; the first refresh wins and the other
  copy dies (`invalid_grant`, status `dead`, pruned after a day). A profile with
  its own `credential_pool["anthropic-oauth"]` no longer inherits the root
  rows: `hermes -p <name> auth logout anthropic-oauth` deletes that copy (no
  upstream revoke) and restores inheritance. The `claude_code` row cannot fork:
  it is a secret-free reference re-read from the Keychain on every load.
- **OpenCode's Claude login is separate.** It lives in OpenCode's own
  database, never reads or writes the Claude Code Keychain entry, and has no
  rotation of its own ([`opencode/README.md`](../../opencode/README.md)
  "Accounts"). Hermes and OpenCode may share an account; what they share is
  that account's weekly pool.
- **Parallel OAuth refresh.** Several workers refreshing the same rotating
  refresh token at once can race to `invalid_grant`; move high-parallelism
  workers' T1 to an API-key provider if it bites.

## Secrets layering

No `.env`. The `bin/hermes` shim injects the `global` then `hermes` Keychain
layers at launch, and a profile alias runs bare `hermes -p <name>` through the
same shim, so **every profile gets `global` + `hermes`** — mechanics in
[`ops/install.md`](ops/install.md) "Secrets mechanics". What belongs in each layer:

- **`hermes`** — keys only Hermes uses, needed by every profile and worker
  session (OpenRouter, `GITHUB_TOKEN`, `FAL_KEY`, `GROQ_API_KEY`, the dashboard
  auth pair and the two `ANTHROPIC_CREDIT_*` lane keys shared with OpenCode).
  The messaging keys (`TELEGRAM_*` / `DISCORD_*`) parked here are the
  **assistant's**: `profile-secrets.sh` passes them to assistant unfiltered
  and drops every messaging key for the other profiles. Do not delete them as
  dead weight.
- **`global`** — keys the shim shares with other tools (editor, MCP servers,
  CLIs), including the web-search keys.
- **`hermes-<profile>`** — the bot's own `TELEGRAM_BOT_TOKEN` +
  `TELEGRAM_ALLOWED_USERS` (plus `TELEGRAM_HOME_CHANNEL` /
  `TELEGRAM_DM_CHAT_ID` / `DISCORD_*`). Only `hermes-assistant` carries them:
  the assistant is the one bot, and `profile-secrets.sh` drops messaging keys
  from every other profile's layer. One bot, one layer; never share a bot
  token between layers.
- **OAuth** is not a layer: see "Authentication inheritance".

**Multiplex changes where these layers land.** Scope-aware reads inside the
gateway (bot tokens, search keys, `GITHUB_TOKEN`, TTS keys, …) resolve ONLY from
each profile's secret scope and never fall back to the process env. Every
gateway-served profile therefore carries `secrets.command` →
`scripts/profile-secrets.sh <profile>`, which emits `global` + `hermes`
(messaging keys filtered per profile) + `hermes-<profile>` as dotenv lines at
startup (and derives `TELEGRAM_CRON_THREAD_ID` from the persisted Inbox topic for
assistant). Raw-env readers (dashboard auth) still read the process env the
launcher injects — which is also why `BU_CDP_URL` must never be in those layers:
`browser_exec` copies it raw and it would pre-empt real-profile browsing for
every profile at once (see [`ops/browser.md`](ops/browser.md)).

**The helper has one shot per profile per process.** Hermes runs
`secrets.command` once per `HERMES_HOME` (no re-pull) and kills it at
`helper_timeout_seconds`; a Telegram adapter that then finds no token fails
NON-retryably, so that bot is dead until the next gateway restart.
`profile-secrets.sh` therefore fetches each Keychain layer exactly once and every
config sets `helper_timeout_seconds: 60`. Rules for editing the helper live in
`AGENTS.md`.

Worker sessions need no unique secret (see [`topology.md`](./topology.md)
"Topology"); the gateway launcher's own `PATH` and Keychain injection are in
[`operations.md`](./operations.md) "Gateway as a persistent service".
