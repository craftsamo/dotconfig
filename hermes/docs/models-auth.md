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
dollars. Most profiles lead with Claude for judgment, long-context work and
prose and fall to a second Claude model before touching the OpenAI pool;
**researcher** leads the other way, on **GPT-6 Astra**.

- **Opus 5.5 leads `default`, `assistant`, `writer`, `marketer` and
  `video-creator`** — above Fable 5.1 on reasoning, agentic terminal work and
  coding at a lower token rate. The Opus-led judgment profiles take **Fable 5.1
  as T2**, never another Opus: every Opus model draws on the same Opus weekly
  sub-cap, so an Opus T2 fails exactly when that cap is why T1 failed, while
  Fable draws on its own 50%-of-week ceiling. Prose quality (`writer`,
  `marketer`) has no public benchmark — revert those two to Fable 5.1 if their
  output degrades.
- **`engineer` alone leads on Fable 5.1** (T2 Opus 5.5) so the OpenCode hidden
  primaries that plan for and review it (Opus 5.5) remain a different model;
  see [`profiles/engineer.md`](./profiles/engineer.md) "OpenCode runtime" for
  the Assistant Admin-topic exception.
- **`default` stays off Fable deliberately** — every `--clone` inherits its
  chain, and a neutral starting point should not lead with the model that has
  the tightest sub-cap.
- **Creator's hands are on the Anthropic pool:** `creator`, `image-creator`
  and `audio-creator` lead on **Claude Sonnet 5**, `video-creator` on Opus 5.5
  (heavier judgment for authored HTML/CSS/GSAP video). All four fall to
  `openai-codex` / GPT-6 Astra and keep `openrouter` / `minimax/minimax-m3` as
  the tail, so a hand still inherits `creator`'s vision fallback for eyeballing
  generated assets. Grok is deliberately deferred as a possible insertion
  BEFORE the GPT tier, pending runtime capability/entitlement validation
  (vision is unverified for these profiles); it is not adopted silently, and
  the OpenRouter tail is not removed to make room for it.
- **Searcher** stays on `xai-oauth` / grok-4.3: xAI capacity is reserved for
  Searcher, X search and Imagine video.
- The coding model inside OpenCode is a separate layer: Engineer uses
  OpenCode's configured per-agent defaults, optionally overridden by maintainer
  `opencode_cli.models`. No second fixed ladder or automatic replay of an
  uncertain run lives in Engineer's Skill.

| Profile | T1 (primary) | T2 | T3 | T4 | `reasoning_effort` |
| --- | --- | --- | --- | --- | --- |
| **default** | `anthropic` / claude-opus-5-5 | `openai-codex` / gpt-6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |
| **assistant** | `anthropic` / **claude-opus-5-5** | `anthropic` / claude-fable-5-1 | `openai-codex` / gpt-6-astra | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |
| **engineer** | `anthropic` / **claude-fable-5-1** | `anthropic` / claude-opus-5-5 | `openai-codex` / gpt-6-astra | `openrouter` / `deepseek/deepseek-v4-flash` | `high` |
| **researcher** | `openai-codex` / **gpt-6-astra** | `openai-codex` / gpt-6-sol | `anthropic` / claude-opus-5-5 | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |
| **searcher** | `xai-oauth` / grok-4.3 | `openrouter` / `xiaomi/mimo-v2.5` | — | — | `low` |
| **creator**, **image-creator**, **audio-creator** | `anthropic` / **claude-sonnet-5** | `openai-codex` / gpt-6-astra | `openrouter` / `minimax/minimax-m3` | — | `medium` |
| **video-creator** | `anthropic` / **claude-opus-5-5** | `openai-codex` / gpt-6-astra | `openrouter` / `minimax/minimax-m3` | — | `medium` |
| **writer** | `anthropic` / **claude-opus-5-5** | `anthropic` / claude-fable-5-1 | `openai-codex` / gpt-6-astra | `openrouter` / `deepseek/deepseek-v4-flash` | `medium` |
| **marketer** | `anthropic` / **claude-opus-5-5** | `anthropic` / claude-fable-5-1 | `openai-codex` / gpt-6-astra | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |
| **ui-review**, **ux-persona** | `openai-codex` / gpt-5.6-terra | — | — | — | `medium` |

A `fallback_providers` entry carries no per-entry `reasoning_effort` or
`api_mode` for the main agent: on each fallback activation Hermes re-reads the
profile config and re-resolves both from provider / base URL / model
(`chat_completion_helpers.py`). **There is no per-tier effort knob in
0.21.0** — `agent.reasoning_overrides` is a *session* concept
(`gateway/session_state.py`, driven by `/model`), not a config key, so a
profile's single `agent.reasoning_effort` applies to every tier in its chain.

Routing is probed with one-token requests per provider/model, not evaluated
for per-profile behavior or prose quality; the Creator-family Sonnet 5 lead is
configuration-validated, not live-tested. Provider facts:

- **Anthropic native** (`base_url: https://api.anthropic.com`) — OAuth resolves
  from the global Claude Code credential/token, not per-profile `auth.json`
  (see "Authentication inheritance"). **Fable 5.1 is not in the `hermes model`
  picker** (`/v1/models` lags the alias; the curated list stops at
  `claude-fable-5`), so it is written straight into `config.yaml`;
  `get_model_context_length` reports 1M for it via the `claude-fable` prefix.
- **Codex** (`base_url: https://chatgpt.com/backend-api/codex`) — every profile
  except searcher has a tier here. OpenCode's `build` primary and `debugger`
  subagent share this same ChatGPT Pro pool, so one subscription carries both
  harnesses. Hermes identifies itself honestly (`originator: hermes-agent`,
  `User-Agent: HermesAgent/<ver>`, `agent/codex_headers.py`) and the backend
  serves Astra to that identity. Astra is also **absent from the picker**
  (`DEFAULT_CODEX_MODELS` in `hermes_cli/codex_models.py` stops at 5.x), so it
  is config-only; `get_model_context_length` resolves 1,050,000 locally, so no
  `hermes update` is required for it.

  **Sizing the shared pool.** On Pro 5x, Astra meters at roughly 25-225
  messages per 5h window for the whole account. Move to Pro 20x when either
  signal repeats: the OpenAI meter (`npx -y @slkiser/opencode-quota show`)
  drops under ~15% partway through a window on ordinary days, or researcher
  and OpenCode Build visibly fall through to their T2 more often than they run
  on Astra. **The upgrade needs no config change** — the same chains simply
  stop descending.
- **xAI (searcher only)** — `xai-oauth` (`base_url: https://api.x.ai/v1`) is a
  flat-rate **SuperGrok / Premium+ subscription**, not the metered
  `XAI_API_KEY` API, so per-token prices do not apply and searcher adds no
  worker to the Max weekly pool. grok-4.3 is positioned for *tool calling and
  instruction following* — the right shape for link-first retrieval — and its
  reasoning can be switched off (`none`). It is on the reasoning-capable
  allowlist (`model_metadata.py`), so its `reasoning_effort` really is sent as
  `reasoning: {effort: …}`; non-allowlisted Grok models have the field dropped
  on purpose, because xAI answers an unsupported `reasoningEffort` with 400.

  **A lapsed xAI OAuth does not degrade searcher to its lower tiers.**
  Credential resolution fails before the request is built, so the agent aborts
  with `xAI OAuth state is missing access_token` and `fallback_providers` never
  engages. The same gate hides `x_search` from the schema, which `hermes
  doctor` misleadingly reports as `x_search (missing XAI_API_KEY)` — the tool
  prefers the OAuth bearer and only falls back to the key (`tools/xai_http.py`).
  Re-authenticate with `hermes model` from the **default** profile — never
  with `-p`, which would write the worker's own `auth.json` and shadow the
  inherited credential.
- **Auxiliary models are pinned, not `auto`.** `auto` resolves to the
  profile's own main provider *and main model* (`agent/auxiliary_client.py`),
  which would run compression, titles, triage and the rest on the most
  expensive model. Every task except `vision` and `web_extract` is pinned to a
  cheap sibling on the same pool — Claude-judgment profiles to `anthropic` /
  `claude-sonnet-5`, researcher and Creator's family to `openai-codex` /
  `gpt-6-luna` — each with a `fallback_chain` to `openrouter` /
  `deepseek/deepseek-v4-flash` (searcher and the evaluators stay `auto`).
  Below that sit the configured chain and a last-resort hop to the main agent
  model, so a pinned aux model never becomes a single point of failure.
  **`vision` deliberately stays `auto`** — pinning it disables the main
  model's native image vision (see [`README.md`](../README.md#plugins)).
- **OpenRouter tails split vision vs text-only.** Profiles whose fallback turns
  may need to SEE something keep a vision-capable tail: `default` /
  `assistant` / `researcher` / `searcher` / `marketer` use `xiaomi/mimo-v2.5`
  (omnimodal, cheap; video analysis stays decoupled via the
  `video-analyze-mimo` plugin — see `README.md` "Plugins"), Creator's hands
  `minimax/minimax-m3`. Text-only work rides the cheaper
  `deepseek/deepseek-v4-flash` (`engineer`, `writer`). Also valid:
  `google/gemini-3.5-flash`.
- **Copilot is in no chain** — the subscription became unusable and its
  catalog drift 404'd tiers silently. `GITHUB_TOKEN` stays in the `hermes`
  layer for the Skills Hub; it is not a model-provider credential.

Optional: set `delegation.model: google/gemini-3.5-flash` on default /
assistant to route `delegate_task` subagents to a cheap model.

### Fable and the Max weekly pool

These facts govern the paired Claude tiers (Fable 5 and 5.1 behave the same):

1. **Fable is not a separate quota tank.** On Max it is included but capped at
   **≤50% of the plan's weekly pool**, drawn from the *same* pool as Opus, and
   it burns that pool faster. A Fable ⇄ Opus step therefore only rescues the
   case where one model's sub-cap is exhausted while the overall weekly still
   has room; if the shared weekly or the 5-hour session limit tripped, both
   are dead and the chain correctly continues to Codex. **That is why the
   second Claude model sits at T2, ahead of Astra**, on every Claude-judgment
   profile: the sub-cap case is the *long* failure — it persists until the
   week rolls over — and in exactly that case the other Claude model is still
   alive. Astra there would hand days of ordinary traffic to the ChatGPT Pro
   pool that OpenCode Build and researcher depend on.
2. **The T2 step depends on the token being resolvable outside the credential
   pool.** A `usage_limit_reached` 429 marks the *credential* exhausted, and
   that mark has **no model dimension** (`credential_pool.py`), so the pool
   refuses to hand it out. The same-provider T2 only succeeds because
   `resolve_anthropic_token()` checks `ANTHROPIC_TOKEN` /
   `CLAUDE_CODE_OAUTH_TOKEN` / the Claude Code Keychain entry **before** the
   pool (`anthropic_adapter.py`). Park the Max subscription *only* in the
   credential pool and the Claude T2 is silently skipped — the chain quietly
   degrades straight to Codex.
3. **Hermes has no per-model quota memory.** The "included Fable usage for
   this week" message carries no parseable reset, so a fixed **1-hour** local
   cooldown applies (`credential_pool.py`), while the agent-level fallback
   cooldown is only **60 seconds** (`chat_completion_helpers.py`). At t+61s the
   primary is restored and retried: once a weekly cap is hit this costs **one
   wasted request per turn until the week rolls over**. Engineer, writer and
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
   patch). Opus 5.5, Fable 5.1 and Mythos 5.1 reject forced `tool_choice`
   (`any` / `tool`) with HTTP 400, so on them the leaked-invoke-markup
   recovery resends the ordinary request (carried as a local patch). Ordinary
   turns are unaffected. Hermes decides both from
   `_MANDATORY_THINKING_CLAUDE_SUBSTRINGS` and
   `_NO_FORCED_TOOL_CHOICE_CLAUDE_SUBSTRINGS`; an unknown Claude id defaults to
   "disable accepted, forcing accepted", so a new Claude release is not
   covered until its breaking changes are read against both lists (see
   `AGENTS.md`).

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
  per-worker re-auth.** Running `hermes model` *inside* a worker writes that
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
- **Anthropic native** is OAuth (Claude Pro/Max) but its creds live **outside**
  `auth.json` (`~/.hermes/.anthropic_oauth.json` for Hermes' PKCE flow, else
  the Claude Code credential / `CLAUDE_CODE_OAUTH_TOKEN`). That source is
  machine-global, so every profile authenticates with **no per-worker login**
  (`hermes auth status anthropic` → logged in); the read-only fallback does
  not apply to it.
- **Anthropic account mapping — Hermes and OpenCode use different accounts.**
  `resolve_anthropic_token()` ALWAYS prefers the default Keychain entry
  `Claude Code-credentials` over the credential pool (pool entries and
  `suppressed_sources` never override it), and that entry must stay logged
  into the **Hermes** account. OpenCode runs on the **sub account** via the
  `opencode-claude-auth` plugin pinned to a suffixed entry
  (`Claude Code-credentials-<suffix>`; the concrete name lives in the untracked
  `claude-account-source.txt`; `CLAUDE_CONFIG_DIR=~/.claude-sub`, alias
  `claude-sub`). A plain `claude /login` therefore changes **Hermes'** account,
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
  dispatcher-spawned worker: `OPENROUTER_API_KEY` (the OpenRouter tails),
  `GITHUB_TOKEN` (Skills Hub), `FAL_KEY`, `GROQ_API_KEY` and the dashboard auth
  pair. The messaging keys (`TELEGRAM_*` / `DISCORD_*`) parked here are the
  **assistant's**: `profile-secrets.sh` passes them to assistant unfiltered,
  keeps only the shared owner allowlist `TELEGRAM_ALLOWED_USERS` for
  engineer / creator / marketer, and drops every messaging key for the other
  profiles. Do not delete them as dead weight.
- **`global`** — keys the shim shares with other tools (editor, MCP servers,
  CLIs), including the web-search keys (`EXA_API_KEY`, `PARALLEL_API_KEY`,
  `FIRECRAWL_API_KEY`).
- **`hermes-<profile>`** (assistant / engineer / creator / marketer) — that
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

Dispatcher-spawned workers need no unique secret (see
[`topology.md`](./topology.md) "Topology"); the gateway launcher's own `PATH`
and Keychain injection are in [`operations.md`](./operations.md) "Gateway as a
persistent service".
