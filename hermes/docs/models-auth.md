# Models, authentication and secrets

Model fallback chains, authentication inheritance and secrets layering. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Models and fallback chains

Each profile carries its own `model:` (tier 1) plus a `fallback_providers:`
list (tiers 2+). `fallback_providers` is **per-turn**: it triggers on errors
(429 / 5xx / 401 / 404 / malformed) and the primary is restored on the next
turn. A tier may reuse the same provider with a different model; only an
identical provider+model pair is skipped.

Models are chosen per role by the capability the role needs, not by the
strongest model; the budget is each subscription's usage allowance, not
dollars. **Hermes chat and auxiliary models run on Claude first**, on the
Hermes Claude account; the ChatGPT subscription belongs to OpenCode, and
Hermes touches it for image generation and, on `writer` / `researcher` /
`assistant` only, as a last-resort chat tier ahead of the OpenRouter tail (see
"Codex" below). Judgment profiles lead with Opus or Fable and fall through a
second Claude model and Sonnet 5.5 before that tail; **researcher**, **writer**
and the **image-creator** / **audio-creator** hands lead on
**Sonnet 5.5**.

- **Opus 5.5 leads `default`, `assistant`, `marketer`, `creator`
  and `video-creator`** — above Fable 5.1 on reasoning, agentic terminal work and
  coding at a lower token rate. The Opus-led judgment profiles take **Fable 5.1
  as T2**, never another Opus: every Opus model draws on the same Opus weekly
  sub-cap, so an Opus T2 fails exactly when that cap is why T1 failed, while
  Fable draws on its own 50%-of-week ceiling. (An Opus on the Console API lane,
  ahead of or after T1, is a different account: no shared sub-cap — see
  "Console credit lanes".) **Sonnet 5.5 is the last Claude
  tier** everywhere: Anthropic meters Opus separately from "all other models"
  per week, so Sonnet stays alive when the Opus cap is the reason T1 failed.
  Prose quality (`writer`, `marketer`) has no public benchmark. `writer` leads
  on Sonnet 5.5 to spare the shared Claude weekly pool (T2 Opus 5.5, T3 Fable
  5.1) — revert it to Opus 5.5 if its output degrades; `marketer` still leads
  on Opus 5.5 — revert it to Fable 5.1 if its output degrades.
- **`default` stays off Fable deliberately** — every `--clone` inherits its
  chain, and a neutral starting point should not lead with the model that has
  the tightest sub-cap.
- **The Creator family splits by hand.** `creator` and `video-creator` lead
  on Opus 5.5; `image-creator` and `audio-creator` lead on Sonnet 5.5. A blind
  A/B on one launch-video brief (isolated homes, model pinned, fallback off;
  evidence in
  `~/Workspaces/Projects/Acme/docs/hermes-studies/creator-ab-2026-09/VERDICT.md`)
  scored every Sonnet 5 run fidelity 1/5 whether it ran the full pipeline or a
  bare single agent, while Opus 5.5 reached 3-4/5 on both. A later blind
  per-family A/B of Opus 5.5 against Sonnet 5.5 (same isolation; evidence in
  `~/Workspaces/Projects/Acme/docs/hermes-studies/creator-quality-2026-09-29/VERDICT.md`)
  found Sonnet 5.5 equal on image and audio leaves at about 0.6x the tokens,
  but clearly behind on authored video (craft −0.8, lost 8 of 8 explainer
  pairings) and inconclusive for Creator as broker. The Opus-led pair takes
  Fable 5.1 as T2, then Sonnet 5.5; the Sonnet-led pair takes Opus 5.5 as T2,
  then Fable 5.1. All four keep `openrouter` / `minimax/minimax-m3` as the
  tail, so a hand still inherits `creator`'s vision fallback for eyeballing
  generated assets. The launch-video study measured
  500-970 `vision_analyze` calls and 20-39M input tokens per video job; three
  concurrent Opus video jobs hit a 429 within ~20 min — a concurrency limit,
  not the usage cap. Watch the Opus sub-cap: a silent drop to the Sonnet or
  minimax tier degrades Creator and video output.
  Grok is deliberately deferred as a possible insertion BEFORE the Sonnet
  tier, pending runtime capability/entitlement validation (vision is
  unverified for these profiles); it is not adopted silently, and the
  OpenRouter tail is not removed to make room for it.
- **Searcher leads on GPT-6.1 Sol** (`openai-codex`), then Sonnet 5.5, then
  `xai-oauth` / grok-4.7, then the OpenRouter tail. xAI stays in the chain
  because `x_search` and Imagine video draw on it. Searcher is the only profile that leads on the
  shared ChatGPT allowance, so re-size OpenCode's usage if its retrieval volume
  grows ("Codex" below).
- The coding model inside OpenCode is a separate layer: the Assistant's OpenCode
  roles use OpenCode's configured per-agent defaults (OpenCode's own Anthropic
  account, so they draw nothing from the Hermes weekly pool), optionally
  overridden by a maintainer `model` on a role in `opencode.roles`. Whether a role
  may run on the caller's own model and what its `alternate` is are in
  [`opencode.md`](./opencode.md) "Models". A GPT-family alternate draws on the
  ChatGPT allowance below. No automatic replay of an uncertain run lives in the
  Assistant's skills.

| Profile                              | T1 (primary)                              | T2                                    | T3                                    | T4                                  | T5                                          | `reasoning_effort` |
| ------------------------------------ | ----------------------------------------- | ------------------------------------- | ------------------------------------- | ----------------------------------- | ------------------------------------------- | ------------------ |
| **default**                          | `anthropic-oauth` / claude-opus-5-5       | `anthropic-oauth` / claude-sonnet-5-5 | `openrouter` / `xiaomi/mimo-v2.5`     | —                                   | —                                           | `medium`           |
| **assistant**                        | `anthropic-oauth` / **claude-opus-5-5**   | `anthropic-oauth` / claude-fable-5-1  | `anthropic-oauth` / claude-sonnet-5-5 | `openai-codex` / gpt-6.1-sol        | `openrouter` / `xiaomi/mimo-v2.5`           | `medium`           |
| **researcher**                       | `anthropic-oauth` / **claude-sonnet-5-5** | `anthropic-oauth` / claude-opus-5-5   | `openai-codex` / gpt-6.1-sol          | `openrouter` / `xiaomi/mimo-v2.5`   | —                                           | `medium`           |
| **searcher**                         | `openai-codex` / **gpt-6.1-sol**          | `anthropic-oauth` / claude-sonnet-5-5 | `xai-oauth` / grok-4.7                | `openrouter` / `xiaomi/mimo-v2.5`   | —                                           | `low`              |
| **creator**, **video-creator**       | `anthropic-oauth` / **claude-opus-5-5**   | `anthropic-oauth` / claude-fable-5-1  | `anthropic-oauth` / claude-sonnet-5-5 | `openrouter` / `minimax/minimax-m3` | —                                           | `medium`           |
| **image-creator**, **audio-creator** | `anthropic-oauth` / **claude-sonnet-5-5** | `anthropic-oauth` / claude-opus-5-5   | `anthropic-oauth` / claude-fable-5-1  | `openrouter` / `minimax/minimax-m3` | —                                           | `medium`           |
| **writer**                           | `anthropic-oauth` / **claude-sonnet-5-5** | `anthropic-oauth` / claude-opus-5-5   | `anthropic-oauth` / claude-fable-5-1  | `openai-codex` / gpt-6.1-sol        | `openrouter` / `deepseek/deepseek-v4-flash` | `medium`           |
| **marketer**                         | `anthropic-oauth` / **claude-opus-5-5**   | `anthropic-oauth` / claude-fable-5-1  | `anthropic-oauth` / claude-sonnet-5-5 | `openrouter` / `xiaomi/mimo-v2.5`   | —                                           | `medium`           |

Every `anthropic-oauth` above is the subscription lane, and the table shows the
subscription chain. **assistant** carries one more tier between T1 and the
table's T2: `anthropic` / the same Opus 5.5 on the Console API lane. **marketer**
and **writer** lead on that lane instead (`anthropic` / Opus 5.5 and Sonnet 5.5),
so the table's T1 is their T2 (see "Console credit lanes").

A `fallback_providers` entry carries no per-entry `reasoning_effort` or
`api_mode` for the main agent: on each fallback activation Hermes re-reads the
profile config and re-resolves both from provider / base URL / model
(`chat_completion_helpers.py`). **There is no per-tier effort knob in
0.21.0** — `agent.reasoning_overrides` is a _session_ concept
(`gateway/session_state.py`, driven by `/model`), not a config key, so a
profile's single `agent.reasoning_effort` applies to every tier in its chain.

Routing is probed with one-token requests per provider/model, not evaluated
for per-profile behavior or prose quality; the Creator-family split is
backed by the two blind A/Bs above (small n per arm). Provider facts:

- **Anthropic native** (`base_url: https://api.anthropic.com`) — OAuth resolves
  from the global Claude Code credential/token, not per-profile `auth.json`
  (see "Authentication inheritance"). **Fable 5.1 is not in the `hermes model`
  picker** (`/v1/models` lags the alias; the curated list stops at
  `claude-fable-5`), so it is written straight into `config.yaml`;
  `get_model_context_length` reports 1M for it via the `claude-fable` prefix.
- **Codex** (`base_url: https://chatgpt.com/backend-api/codex`) — **images,
  plus one last-resort chat tier.** GPT-6.1 Sol sits ahead of the OpenRouter
  tail on `writer`, `researcher` and `assistant`, and the lead tier on
  `searcher`, so a spent Claude weekly pool degrades to a capable model instead of a cheap one. No auxiliary task is
  pinned to it, but searcher's stay `auto`, which resolves to its main model:
  compression and titles there now run on GPT-6.1 Sol. The ChatGPT subscription
  is sized for OpenCode (its searchers,
  `debugger`, `reviewer-deep` and cheap subagents on GPT-6.1 Sol, plus the
  `alternate` of the Assistant's OpenCode roles when the Claude pool is spent)
  and shares one Plus allowance with Hermes, so keep the tier off
  profiles with heavy jobs: a single `video-creator` job reads tens of millions
  of tokens and would exhaust it for OpenCode too. GPT-6.1 Sol rejects
  `reasoning.effort` `none` / `minimal` and its context length is not in
  Hermes' static table (it resolves from the live Codex catalog, else the 256K
  default), so keep the profile's `reasoning_effort` at `low` or above. The
  Codex OAuth login in `default` stays on purpose: the `image-fallback` chains
  (`img-codex-xai-fal` on creator / image-creator, `img-xai-codex-fal` on
  default) still try `openai-codex` for images, which draws on that shared pool.
  Do not add the tier to another profile or an aux task without re-sizing
  OpenCode's usage.
- **xAI (searcher T3, `x_search`, Imagine)** — `xai-oauth` (`base_url: https://api.x.ai/v1`) is a
  flat-rate **xAI subscription**, not the metered
  `XAI_API_KEY` API, so per-token prices do not apply and searcher adds no
  worker to the Claude weekly pool. grok-4.7 is not on the reasoning-capable
  allowlist (`model_metadata.py` lists `grok-4.3`, `grok-4.5`, `grok-4.6`), so
  Hermes drops its `reasoning_effort` on purpose, because xAI answers an
  unsupported `reasoningEffort` with 400, and the profile's `low` does not
  reach it. Its context length is not in the static table either (the closest
  prefix, `grok-4`, is 256K against the catalog's 500K).

  **A lapsed xAI OAuth is no longer a searcher outage, but it still hides
  `x_search`.** While xAI led, credential resolution failed before the request
  was built, so the agent aborted with `xAI OAuth state is missing access_token`
  and `fallback_providers` never engaged. With Codex leading, chat no longer
  depends on that login; the same gate still hides `x_search` from the
  schema, which
  `hermes doctor` misleadingly reports as `x_search (missing XAI_API_KEY)` — the tool
  prefers the OAuth bearer and only falls back to the key (`tools/xai_http.py`).
  Re-authenticate with `hermes model` from the **default** profile — never
  with `-p`, which would write the worker's own `auth.json` and shadow the
  inherited credential.

- **Auxiliary models are pinned, not `auto`.** `auto` resolves to the
  profile's own main provider _and main model_ (`agent/auxiliary_client.py`),
  which would run compression, titles, triage and the rest on the most
  expensive model. Every task except `vision` and `web_extract` is pinned to a
  cheap Claude sibling — `anthropic-oauth` / `claude-sonnet-5` on the judgment
  profiles, `claude-sonnet-5-5` on researcher and Creator's family (their
  thinking-off calls get `between_tools`, see below) — each with a
  `fallback_chain` to `openrouter` /
  `deepseek/deepseek-v4-flash` (searcher stays `auto`).
  Below that sit the configured chain and a last-resort hop to the main agent
  model, so a pinned aux model never becomes a single point of failure.
  **`vision` deliberately stays `auto`** — pinning it disables the main
  model's native image vision (see [`README.md`](../README.md#plugins)).
  **`background_review`** (the post-turn memory / skill review fork) is pinned
  to `claude-sonnet-5-5` on `assistant`: left on `auto` it replays the whole
  conversation on the main Opus model every few turns, which was most of the
  Assistant's weekly cache reads. Auxiliary usage is read from the
  `session_model_usage` table in each profile's `state.db` (`task <> ''`), not
  from `sessions`.
- **OpenRouter tails split vision vs text-only.** Profiles whose fallback turns
  may need to SEE something keep a vision-capable tail: `default` /
  `assistant` / `researcher` / `searcher` / `marketer` use `xiaomi/mimo-v2.5`
  (omnimodal, cheap; video analysis stays decoupled via the
  `video-analyze-mimo` plugin — see `README.md` "Plugins"), Creator's hands
  `minimax/minimax-m3`. Text-only work rides the cheaper
  `deepseek/deepseek-v4-flash` (`writer`). Also valid:
  `google/gemini-3.5-flash`.
- **Copilot is in no chain** — the subscription became unusable and its
  catalog drift 404'd tiers silently. `GITHUB_TOKEN` stays in the `hermes`
  layer for the Skills Hub; it is not a model-provider credential.

Optional: set `delegation.model: google/gemini-3.5-flash` on default /
assistant to route `delegate_task` subagents to a cheap model.

### Fable and the Claude weekly pool

These facts govern the paired Claude tiers (Fable 5 and 5.1 behave the same):

1. **Fable is not a separate quota tank.** It is included but capped at
   **≤50% of the weekly pool**, drawn from the _same_ pool as Opus, and
   it burns that pool faster. A Fable ⇄ Opus step therefore only rescues the
   case where one model's sub-cap is exhausted while the overall weekly still
   has room; if the shared weekly or the 5-hour session limit tripped, both
   are dead and the chain continues to Sonnet 5.5 (metered under "all other
   models", not the Opus bucket) and then the OpenRouter tail. **That is why
   the second Claude model sits at T2** on every Claude-judgment profile: the
   sub-cap case is the _long_ failure — it persists until the week rolls over
   — and in exactly that case the other Claude model is still alive. With one
   Claude account behind every profile, a busy Creator week can drain the
   shared pool for all of them; watch it before adding concurrency.
2. **The T2 step depends on the token being resolvable outside the credential
   pool.** A `usage_limit_reached` 429 marks the _credential_ exhausted, and
   that mark has **no model dimension** (`credential_pool.py`), so the pool
   refuses to hand it out. The same-provider T2 only succeeds because
   `resolve_anthropic_token()` checks `ANTHROPIC_TOKEN` /
   `CLAUDE_CODE_OAUTH_TOKEN` / the Claude Code Keychain entry **before** the
   pool (`anthropic_adapter.py`). Park the Claude subscription _only_ in the
   credential pool and every later Claude tier is silently skipped — the
   chain quietly degrades straight to OpenRouter.
3. **Hermes has no per-model quota memory.** The "included Fable usage for
   this week" message carries no parseable reset, so a fixed **1-hour** local
   cooldown applies (`credential_pool.py`), while the agent-level fallback
   cooldown is only **60 seconds** (`chat_completion_helpers.py`). At t+61s the
   primary is restored and retried: once a weekly cap is hit this costs **one
   wasted request per turn until the week rolls over**. Writer and
   marketer absorb that cheaply — they are low-turn profiles. The
   **assistant** is the exception: it is the latency-sensitive front door, so
   when its T1's weekly cap is reached, switch its live sessions to another
   model with **`/model`** rather than waiting out the week. That manual escape
   is what makes a capped Claude T1 acceptable there at all.
4. **Adaptive thinking, not manual budgets.** Modern Claude gets
   `thinking: {type: adaptive}` + `output_config: {effort: …}`, so the effort
   level passes straight through (`minimal→low`, `ultra→max`); the legacy
   4k/8k/16k/32k `budget_tokens` table does **not** apply. Long structured
   outputs prefer `high` over `xhigh`: Hermes can otherwise burn the whole
   output budget on reasoning (`conversation_loop.py`). If that warning ever
   appears, drop to `medium` or raise `max_tokens`.
5. **Two request shapes are refused.** Opus 5.5 and Fable thinking cannot be
   disabled (`thinking: {type: disabled}` → HTTP 400), so a thinking-off
   request (`reasoning: none`, the one-shot "answer without thinking" length
   continuation) omits `thinking` instead (for Opus 5.5 carried as a local
   patch). Sonnet 5.5 also refuses the disable but has a real off: its
   thinking-off request sends `thinking: {type: between_tools}` bare on
   anthropic.com (no up-front thinking; it rejects xhigh/max effort and any
   other thinking field) and omits `thinking` elsewhere (local patch). Opus
   5.5, Sonnet 5.5, Fable 5.1 and Mythos 5.1 reject forced `tool_choice`
   (`any` / `tool`) with HTTP 400, so on them the leaked-invoke-markup
   recovery resends the ordinary request (carried as a local patch). Ordinary
   turns are unaffected. Hermes decides these from
   `_MANDATORY_THINKING_CLAUDE_SUBSTRINGS`,
   `_BETWEEN_TOOLS_OFF_CLAUDE_SUBSTRINGS` and
   `_NO_FORCED_TOOL_CHOICE_CLAUDE_SUBSTRINGS`; an unknown Claude id defaults to
   "disable accepted, forcing accepted", so a new Claude release is not
   covered until its breaking changes are read against these lists (see
   `AGENTS.md`).

### Console credit lanes

Anthropic is two providers on one backend that bill different accounts:
`anthropic-oauth` bills the Claude subscription, `anthropic` bills a Console API
key. Each lane refuses the other's token shape (a Console key is `sk-ant-api…`
or `sk-ant-usr…`), so one never bills the other. Max plans grant monthly API
credits, one Console org per plan, spent before any purchased balance and lost
at the end of the billing cycle; Claude Code and extra usage cannot spend them,
only an API key can. OpenCode spends the same credits
([`opencode/README.md`](../../opencode/README.md) "Console credit lanes").

- **Tier.** assistant carries `anthropic` / Opus 5.5 right after T1, then the
  table's T2 onward. A credit Opus draws on no subscription sub-cap, which is why
  it may sit ahead of Fable. **marketer and writer lead on the lane** (Opus 5.5
  and Sonnet 5.5) and fall back to the subscription's tier of the same model,
  then the table's chain: credits expire, and the Sub org's balance needs a
  steady consumer (about $10 a day to be spent by its renewal). Those two are
  low-turn profiles, about that size, and not a front door. assistant stays
  subscription-first: its volume would empty Sub in days and a lane 429 would
  slow the front door. Creator's family stays off the lane: one video job reads
  tens of millions of tokens and would empty it. The other profiles are
  unchanged. While the subscription's reset is ahead, turns stay on the lane:
  that drains the credits by design.
- **Rate limits.** A Console org linked for credits starts on the Start tier.
  One org's Limits page showed Opus 5.5 and Sonnet 5.5 at 2M input tokens (cache
  reads excluded), 400k output tokens and 1,000 requests per quota row, with a
  24 h peak of 36% under OpenCode's parallel specialists; the other org was not
  checked. A lane-first profile adds little to that. Raising a tier is a request
  in the Console; its Edit button only lowers a workspace's share.
- **Two orgs, one tier.** The `anthropic` credential pool holds both keys as
  env-sourced entries: `ANTHROPIC_CREDIT_SUB_ACCOUNT_KEY` (priority 0), then
  `ANTHROPIC_CREDIT_MAIN_ACCOUNT_KEY` (priority 1); `hermes auth list` shows
  them. Sub (the OpenCode account's org) is first; OpenCode spends the other way
  round, so the two start on different orgs and a Console org's rate limit,
  which is per org, is not hit by both at once.
- **Failure.** An empty balance is a plain 400 ("credit balance is too low");
  the classifier treats it as billing, so the turn moves on at once. By the
  code (read, not run), a billing 400 benches that key for an hour and rotates
  to the next pool entry, a 429 is retried once on the same key and then
  rotates, a 401 rotates, and with both keys spent the turn moves to the next
  fallback entry (Fable for assistant; the subscription's tier of the same
  model for marketer and writer). Benches are saved to disk, and while more than ten
  minutes of one remain the walk skips the lane without a request, so an empty
  lane costs at most one rejected request per key per hour. In the last ten
  minutes of a bench the lane is no longer skipped but has nothing to select, so
  it counts as unconfigured and is skipped for the rest of that cached session
  (until the chain config changes or the gateway restarts): after the credits
  refill, restart the gateway if a session stays off the lane. That was read for
  a lane tier behind T1; a profile that leads on the lane (marketer, writer) has
  not been observed through a bench, so after a refill check `billing_provider`
  in its `session_model_usage`. The primary's own restore cooldown is 60 s,
  doubling on repeated rate-limit or billing failures up to 4 h, or the
  provider's reset time when the 429 gives one.
- **Auxiliary tasks follow the turn.** An `auto` auxiliary call (`vision`,
  `web_extract`) uses the main runtime, so while turns stay on the lane through
  the cooldown or a reset gate, those calls bill the credits too (Opus 5.5).
  After a payment error from the main provider it tries the task's own
  `fallback_chain`, then the main model, and does not walk `fallback_providers`.
  An auxiliary call treats only 402/403/404/429 as a payment error, so a lane's
  400 does not fall through; the pinned auxiliary chains stay on Sonnet and the
  OpenRouter tail.
- **Cost.** Both lanes are priced from Hermes' table, so a lane turn reports an
  estimated cost; the real spend is the Console's. OpenCode's `/credits`
  balance is an estimate from OpenCode's own cost accounting, so Hermes' spend
  on the same orgs is not in it.
- **Keys.** The two env names sit in the shared `hermes` layer and, as a second
  copy of the same value, in OpenCode's `opencode` project. The pool entries
  read the variable by name, so rotate both copies and restart the gateway. A
  profile without its own `anthropic` rows reads the root `auth.json` read-only;
  its first rotation or bench writes a copy of its own (video-creator already
  has one), which then shadows the root: `hermes auth list` at the root does not
  show or clear that profile's bench, and a rename at the root does not reach it.
  Neither Console org has a payment method or auto-reload, so an empty balance
  stops requests instead of billing.
- **Exposure.** Terminal and code-execution children drop secrets by name, and
  the list holds each registered provider's variables (`ANTHROPIC_API_KEY`,
  `ANTHROPIC_TOKEN`, `OPENROUTER_API_KEY`), not these two names, so a child of
  any profile that holds them can read both keys. In the shared layer that is
  every profile. A leak costs at most the orgs' monthly credits.

### `agent.*` does not inherit from the root profile

A named profile's config is `$HERMES_HOME/config.yaml` deep-merged with the
built-in `DEFAULT_CONFIG` **only** (`hermes_cli/config.py`) — the root
`~/.hermes/config.yaml` is never a parent. `--clone` copies it once at creation
time; that is not live inheritance.

This bites hardest on `agent.reasoning_effort`: `DEFAULT_CONFIG["agent"]` has
**no** such key, so omitting it does not inherit the root's `medium` — it
resolves to `None`, and each provider path then differs: native Anthropic
sends no `thinking`/`output_config` at all (`anthropic_adapter.py`), Codex
defaults to `medium` (`transports/codex.py`), OpenRouter to
`{enabled: true, effort: medium}` — a T1 left unspecified while its fallbacks
run `medium`. Every profile carries an explicit value. **Set `agent.*` keys per
profile, always.**

## Authentication inheritance

`auth.json` is per-profile (`auth.py`, built from `get_hermes_home()`), **but**
a named profile with no entry for a provider falls back **read-only** to the
default profile's `~/.hermes/auth.json`.

- **OAuth logins happen in default only** (`hermes model`, no `-p`). Codex,
  Copilot and xAI-OAuth creds are then inherited by every profile — **no
  per-worker re-auth.** Running `hermes model` _inside_ a worker writes that
  profile's `auth.json` and shadows the inherited creds for that provider
  (writes never propagate).
- **Shadowed creds survive a default re-login, and `hermes doctor` will not see
  it.** Doctor inspects default, so it reports the provider healthy while a
  worker still loads its own stale entry. The symptom is uneven: the model can
  keep answering while a tool that resolves through the credential pool goes
  missing (`x_search` unavailable on a profile whose grok replies fine).
  Confirm with `providers` in `~/.hermes/profiles/<name>/auth.json`; repair by
  dropping that provider key so the profile inherits default again. Prefer
  editing the file over `hermes auth logout`, which may revoke upstream and
  take the shared credential down with it.
- **Anthropic native** is OAuth (a Claude subscription) but its creds live **outside**
  `auth.json` (`~/.hermes/.anthropic_oauth.json` for Hermes' PKCE flow, else
  the Claude Code credential / `CLAUDE_CODE_OAUTH_TOKEN`). That source is
  machine-global, so every profile authenticates with **no per-worker login**
  (`hermes auth status anthropic` → logged in); the read-only fallback does
  not apply to it.
- **Anthropic account mapping — Hermes and OpenCode use different accounts.**
  `resolve_anthropic_token()` ALWAYS prefers the default Keychain entry
  `Claude Code-credentials` over the credential pool (pool entries and
  `suppressed_sources` never override it), and that entry must stay logged
  into the **Hermes** account. OpenCode runs on the **sub account** (its own
  subscription) through its own OAuth login (the
  `@ex-machina/opencode-anthropic-auth` plugin, stored in OpenCode's database),
  which never reads or writes the Keychain. Claude Code's suffixed entry for the
  sub account (`CLAUDE_CONFIG_DIR=~/.claude-sub`, alias `claude-sub`) no longer
  feeds OpenCode. A plain `claude /login` therefore changes **Hermes'** account,
  not OpenCode's; after one, verify with
  `security find-generic-password -s "Claude Code-credentials"` + the OAuth
  profile endpoint before assuming the split still holds.
- **Env tokens** work everywhere via the shim: xAI accepts `XAI_API_KEY`;
  Copilot reads `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` →
  `gh auth token` (`copilot_auth.py`) before stored OAuth creds. Should Copilot
  return to a chain, a non-Copilot-capable `GITHUB_TOKEN` in the `hermes`
  layer would 401 it; `COPILOT_GITHUB_TOKEN` (highest priority) overrides it.
- **Parallel OAuth refresh.** Several workers refreshing the same rotating
  refresh token at once can race to `invalid_grant`. If it bites, move
  high-parallelism workers' T1 to an API-key provider (OpenRouter /
  `XAI_API_KEY`).

## Secrets layering

No `.env`. The `bin/hermes` shim injects the `global` then `hermes` Keychain
layers at launch, and a profile alias runs bare `hermes -p <name>` through the
same shim (`~/.config/bin` precedes `~/.local/bin` on `PATH`), so **every
profile gets `global` + `hermes`** — mechanics in
[`README.md`](../README.md#secrets). What belongs in each layer:

- **`hermes`** — keys only Hermes uses, needed by every profile and every
  worker session: `OPENROUTER_API_KEY` (the OpenRouter tails),
  `GITHUB_TOKEN` (Skills Hub), `FAL_KEY`, `GROQ_API_KEY`, the dashboard auth
  pair and the two Console credit-lane keys (`ANTHROPIC_CREDIT_*`, shared with
  OpenCode). The messaging keys (`TELEGRAM_*` / `DISCORD_*`) parked here are the
  **assistant's**: `profile-secrets.sh` passes them to assistant unfiltered,
  keeps only the shared owner allowlist `TELEGRAM_ALLOWED_USERS` for
  creator / marketer, and drops every messaging key for the other
  profiles. Do not delete them as dead weight.
- **`global`** — keys the shim shares with other tools (editor, MCP servers,
  CLIs), including the web-search keys (`EXA_API_KEY`, `PARALLEL_API_KEY`,
  `FIRECRAWL_API_KEY`).
- **`hermes-<profile>`** (assistant / creator / marketer) — that
  bot's own `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_USERS` (assistant also
  `TELEGRAM_HOME_CHANNEL` / `TELEGRAM_DM_CHAT_ID` / `DISCORD_*`). One bot, one
  layer; never share a bot token between layers (the owner allowlist in
  `hermes` is the one deliberately shared value).
- **OAuth** is not a layer: see "Authentication inheritance".

**Multiplex changes where these layers land.** Scope-aware reads inside the
gateway (bot tokens, `OPENROUTER_API_KEY`, `EXA/PARALLEL/FIRECRAWL/XAI` keys,
`GITHUB_TOKEN`, TTS keys, …) resolve ONLY from each profile's secret scope and
never fall back to the process env. Every gateway-served profile therefore
carries `secrets.command` → `scripts/profile-secrets.sh <profile>`, which emits
`global` + `hermes` (messaging keys filtered per profile, as above) +
`hermes-<profile>` as dotenv lines
at startup (and derives `TELEGRAM_CRON_THREAD_ID` from the persisted Inbox
topic for assistant). Raw-env readers (dashboard auth) still read the process
env the gateway launcher injects — which is also why `BU_CDP_URL` must never be
in those layers: `browser_exec` copies it raw from the process env and it would
pre-empt real-profile browsing for every profile at once (see
[`README.md`](../README.md#browser)).

**The helper has one shot per profile per process.** Hermes runs
`secrets.command` once per `HERMES_HOME` (no re-pull) and kills it at
`helper_timeout_seconds`; a Telegram adapter that then finds no token fails
NON-retryably, so that bot is dead until the next gateway restart
(`✗ telegram failed to connect (profile: …)` right after `[secrets:command]
helper timed out`). `profile-secrets.sh` therefore fetches each Keychain layer
exactly once — a duplicated fetch pushed the bot profiles past the timeout
under boot load — and every config sets `helper_timeout_seconds: 60`. The
maintainer rules for editing the helper live in `AGENTS.md`.

Worker sessions need no unique secret (see
[`topology.md`](./topology.md) "Topology"); the gateway launcher's own `PATH`
and Keychain injection are in [`operations.md`](./operations.md) "Gateway as a
persistent service".
