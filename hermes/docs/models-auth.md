# Models, authentication and secrets

Model fallback chains, authentication inheritance and secrets layering. Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Models and fallback chains

Each profile carries its own `model:` (tier 1) plus a `fallback_providers:`
list (tiers 2+). `fallback_providers` is **per-turn**: it triggers on errors
(429 / 5xx / 401 / 404 / malformed) and the primary is restored on the next
turn. The default profile already proves the YAML shape.

The fleet is split across the two subscription pools by role (2026-09-05).
Most profiles lead with Claude for judgment, long-context work and prose,
and fall to a second Claude model before ever touching the OpenAI pool.
**Researcher** leads the other way, on **GPT-6 Astra**. The other profiles
listed below retain their role-appropriate OpenRouter tails.

**Capability reallocation (2026-09-23).** Models are chosen per role by the
capability the role needs, not by the strongest model; the budget is each
subscription's usage allowance, not dollars. **Claude Opus 5.5** (released
2026-09-22) replaced Fable 5.1 on `assistant`, `writer` and `marketer` and
Opus 5 on `default` and `video-creator`: Anthropic's own table puts it above
Fable 5.1 on reasoning (HLE), agentic terminal work (Terminal-Bench 4.0) and
coding (SWE-bench Pro) at ~40% of Fable's token rate and ~80% of Opus 5's.
Those Opus-led profiles take **Fable 5.1 as T2** rather than another Opus:
every Opus model draws on the same Opus weekly sub-cap, so an Opus T2 fails
exactly when that cap is the reason T1 failed, while Fable draws on its own
50%-of-week ceiling. Prose quality (`writer`, `marketer`) is not covered by
any public benchmark — revert those two to Fable 5.1 if their output
degrades. `engineer` alone stays on **Fable 5.1** (T2 now Opus 5.5) so the
OpenCode hidden primaries that plan for and review it (Opus 5.5) remain a
different model; see `AGENTS.md` for the Assistant Admin-topic exception.
On the Codex side, GPT-6 Sol replaced GPT-5.6 Sol wherever Sol was a
fallback (`default` T2, `researcher` T2), and GPT-6 Luna replaced GPT-5.6
Luna as the pinned auxiliary model (half the allowance, fewer
hallucinations on AA-Omniscience).

**Creator's hands are on the Anthropic pool (2026-09-13 follow-up).**
`creator`, `image-creator` and `audio-creator` lead on **Claude Sonnet 5**;
`video-creator` leads on **Claude Opus 5.5** (heavier judgment for authored
HTML/CSS/GSAP video work). All four keep the shared `base_url:
https://api.anthropic.com`, fall to `openai-codex` / **GPT-6 Astra**, and
keep their original `openrouter` / `minimax/minimax-m3` tail at the end of
the chain (Claude -> GPT -> OpenRouter minimax), so a hand still inherits
`creator`'s vision fallback for eyeballing generated assets. Grok is
deliberately deferred as a possible insertion BEFORE the GPT tier, pending
runtime capability/entitlement validation (vision support is unverified for
these profiles); it is not adopted silently and the existing OpenRouter tail
is not removed to make room for it.
**Searcher** is unchanged
on `xai-oauth` / grok-4.3: xAI capacity is reserved for Searcher, X search and
Imagine video. The coding model inside OpenCode is a separate layer entirely —
Engineer uses OpenCode's configured per-agent defaults, optionally overridden by
maintainer opencode_cli.models. No second fixed ladder or automatic replay of
an uncertain run lives in Engineer's Skill.

| Profile | T1 (primary) | T2 | T3 | T4 | `reasoning_effort` |
| --- | --- | --- | --- | --- | --- |
| **default** | `anthropic` / claude-opus-5-5 | `openai-codex` / gpt-6-sol | `openrouter` / `xiaomi/mimo-v2.5` | — | `medium` |
| **assistant** | `anthropic` / **claude-opus-5-5** | `anthropic` / claude-fable-5-1 | `openai-codex` / gpt-6-astra | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |
| **engineer** | `anthropic` / **claude-fable-5-1** | `anthropic` / claude-opus-5-5 | `openai-codex` / gpt-6-astra | `openrouter` / `deepseek/deepseek-v4-flash` | `high` |
| **researcher** | `openai-codex` / **gpt-6-astra** | `openai-codex` / gpt-6-sol | `anthropic` / claude-opus-5-5 | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |
| **searcher** | `xai-oauth` / grok-4.3 | `openrouter` / `xiaomi/mimo-v2.5` | — | — | `low` |
| **creator** | `anthropic` / **claude-sonnet-5** | `openai-codex` / gpt-6-astra | `openrouter` / `minimax/minimax-m3` | — | `medium` |
| **image-creator** | `anthropic` / **claude-sonnet-5** | `openai-codex` / gpt-6-astra | `openrouter` / `minimax/minimax-m3` | — | `medium` |
| **audio-creator** | `anthropic` / **claude-sonnet-5** | `openai-codex` / gpt-6-astra | `openrouter` / `minimax/minimax-m3` | — | `medium` |
| **video-creator** | `anthropic` / **claude-opus-5-5** | `openai-codex` / gpt-6-astra | `openrouter` / `minimax/minimax-m3` | — | `medium` |
| **writer** | `anthropic` / **claude-opus-5-5** | `anthropic` / claude-fable-5-1 | `openai-codex` / gpt-6-astra | `openrouter` / `deepseek/deepseek-v4-flash` | `medium` |
| **marketer** | `anthropic` / **claude-opus-5-5** | `anthropic` / claude-fable-5-1 | `openai-codex` / gpt-6-astra | `openrouter` / `xiaomi/mimo-v2.5` | `medium` |

**`default` stays off Fable deliberately** — every `--clone` inherits its
chain, and a neutral starting point should not lead with the model that has
the tightest sub-cap (Fable: 50% of the week). It leads on Opus 5.5.

**Opus 5.5 needs two LOCAL patches (2026-09-23).** Anthropic documents two
breaking changes that Hermes 0.21.0 (and upstream `main` as of that date)
did not handle; both are carried as `fix/` branches merged into `local` in
the hermes-agent checkout, each with a regression test:

- `fix/anthropic-opus-5-5-mandatory-thinking` — Opus 5.5 thinking cannot be
  disabled (`thinking: {type: disabled}` → HTTP 400). Upstream's
  mandatory-thinking list (`_MANDATORY_THINKING_CLAUDE_SUBSTRINGS`) named
  only `claude-fable`, so `reasoning: none` and the one-shot "answer without
  thinking" length continuation (`turn_truncation.py`) sent the disable and
  lost the turn — the classifier only self-heals on Portal/OpenRouter
  wording. Verified live 2026-09-23: with the list reverted in-process the
  disable came back `HTTP 400: "thinking.type.disabled" is not supported for
  this model` and the turn failed with no retry; with the branch, the same
  request omits `thinking` and answers. The branch adds both id spellings; open upstream PRs #119419 /
  #119793 carry the same change, so drop the branch once one lands.
- a follow-up commit on `fix/anthropic-oauth-tool-choice` — Opus 5.5,
  **Fable 5.1** and Mythos 5.1 reject forced `tool_choice` (`any` / `tool`)
  with HTTP 400. That branch's leaked-invoke-markup recovery forced `any`,
  so its retries were dead on these models — Fable 5.1 included, since
  2026-09-05, unnoticed because the recovery has not fired live since July.
  On those models the recovery now resends the ordinary request.

Ordinary turns were never affected. Re-check after `hermes update` that both
merges survived (`git log --oneline --merges local | rg anthropic`).

```yaml
# example — a 4-tier chain (the shape any profile may use)
model:
  default: claude-fable-5
  provider: anthropic
  base_url: https://api.anthropic.com
fallback_providers:
  - provider: anthropic          # same provider, different model — allowed
    model: claude-opus-5         # (only an identical provider+model pair is skipped)
    base_url: https://api.anthropic.com
  - provider: openai-codex
    model: gpt-5.6-sol
    base_url: https://chatgpt.com/backend-api/codex
  - provider: openrouter
    model: deepseek/deepseek-v4-flash
    base_url: https://openrouter.ai/api/v1
    api_mode: chat_completions
agent:
  reasoning_effort: high
```

A `fallback_providers` entry carries no per-entry `reasoning_effort` or
`api_mode` for the main agent: on each fallback activation Hermes re-reads the
profile config and re-resolves both from provider / base URL / model
(`chat_completion_helpers.py:1668,1846`). **There is no per-tier effort knob
in 0.21.0** — `agent.reasoning_overrides` is a *session* concept
(`gateway/session_state.py:226`, driven by `/model`), not a config key, so a
profile's single `agent.reasoning_effort` applies to every tier in its chain.

Current routing and previously verified provider facts follow. The 2026-09-13
Creator-family reassignment is configuration-validated, not live-tested. The
2026-09-23 capability reallocation was probed live after the gateway restart
(17:05, all 13 connections up): one-token requests answered on
`anthropic` / `claude-opus-5-5` (Hermes account), `openai-codex` /
`gpt-6-sol` and `gpt-6-luna`, the auxiliary route (`title_generation` on
creator → `gpt-6-luna`), and OpenCode's `hermes-review` (Opus 5.5 on the sub
account) plus `gpt-6-sol-fast` / `gpt-6-luna-fast`. Per-profile behavior and
prose quality are not evaluated by that.

- **Anthropic native** — every profile in the table except `researcher` /
  `searcher` leads with `anthropic`
  (`base_url: https://api.anthropic.com`), on `claude-opus-5-5` for
  `default`, `assistant`, `writer`, `marketer` and `video-creator`,
  `claude-fable-5-1` on `engineer`, and `claude-sonnet-5` on creator's other hands
  (`creator`, `image-creator`, `audio-creator`). OAuth
  resolves from the global Claude Code credential/token rather than
  per-profile `auth.json`. **Fable 5.1 is not in the `hermes model` picker** —
  `/v1/models` lags the alias, so the curated list stops at `claude-fable-5`.
  It is written straight into `config.yaml` instead; live one-shot calls
  confirm the slug resolves and answers (2026-09-05), and
  `get_model_context_length` already reports 1M for it via the `claude-fable`
  prefix entry.
- **GPT-6 Astra (T1 on researcher)** — reached over the same
  `openai-codex` OAuth path as Sol. Hermes identifies itself honestly
  (`originator: hermes-agent`, `User-Agent: HermesAgent/<ver>`,
  `agent/codex_headers.py:49-59`) and the Codex backend serves Astra to that
  identity; verified with a live one-shot call (2026-09-05). Like Fable it is
  **absent from the picker** (`DEFAULT_CODEX_MODELS` in
  `hermes_cli/codex_models.py` stops at the 5.x series and live discovery did
  not return it), so it is config-only; `get_model_context_length` resolves
  1,050,000 locally, so no `hermes update` is required for it.
- **xAI (T1, searcher only)** — searcher runs `xai-oauth`
  (`base_url: https://api.x.ai/v1`), which is a flat-rate **SuperGrok /
  Premium+ subscription**, not the metered `XAI_API_KEY` API. The published
  per-token prices therefore do not apply to this path; searcher spends
  subscription allowance, while xAI capacity is also reserved for X search and
  Imagine video rather than adding another worker to the Max weekly pool.

  **Searcher stays on grok-4.3**, which xAI positions for *tool calling and
  instruction following* — the right shape for link-first retrieval, and whose
  reasoning can be switched off entirely (`none`). It is on the
  reasoning-capable allowlist
  (`model_metadata.py:370-410`), so its `reasoning_effort` really is sent as
  `reasoning: {effort: …}` — it is not a no-op. Non-allowlisted Grok models
  have the field dropped on purpose, because xAI answers an unsupported
  `reasoningEffort` with HTTP 400.

  **A lapsed xAI OAuth does not degrade searcher to its lower tiers.**
  Credential resolution fails before the request is built, so the agent aborts
  with `xAI OAuth state is missing access_token` and `fallback_providers` never
  engages — searcher stops dead rather than falling through. The same gate hides
  the `x_search` tool from the schema, which `hermes doctor`
  reports as `x_search (missing XAI_API_KEY)`; that wording is misleading,
  since the tool prefers the OAuth bearer and only falls back to the API key
  (`tools/xai_http.py:243-310`). Re-authenticate with `hermes model` from the
  **default** profile — never with `-p`, which would write the worker's own
  `auth.json` and shadow the inherited credential.
- **Codex** — every profile in the table except searcher carries an `openai-codex` tier
  (`base_url: https://chatgpt.com/backend-api/codex`): Astra as T1 on
  researcher, Astra as the T2 fallback on creator's hands (`creator`,
  `image-creator`, `audio-creator`, `video-creator`) ahead of their restored
  OpenRouter T3, Astra as T3 on the
  Claude-judgment profiles (`assistant`, `engineer`, `writer`, `marketer`),
  and GPT-6 Sol as the T2 of `researcher` and `default`. OpenCode's `build` primary and
  `debugger` subagent share this same ChatGPT Pro pool — so this one
  subscription now carries both harnesses. The former `gpt-5.6-terra` profile
  routes were promoted to Sol; the engineer-pipeline's OpenCode ProviderLadder
  remains a separate model-routing layer.

  **Sizing the shared pool.** On Pro 5x, Astra meters at roughly 25-225
  messages per 5h window for the whole account. Move to Pro 20x when either
  signal repeats: the OpenAI meter (`npx -y @slkiser/opencode-quota show`)
  drops under ~15% partway through a window on ordinary days, or the
  Astra-first profiles and OpenCode Build visibly fall through to their T2
  more often than they run on Astra. **The upgrade needs no config change** — the same chains
  simply stop descending.
- **Auxiliary models are pinned, not `auto`** (2026-09-05). `auto` resolves to
  the profile's own main provider *and main model*
  (`agent/auxiliary_client.py:7-15`), so compression, title generation, triage
  and the rest were all running on the profile's most expensive model. Every
  task except `vision` and `web_extract` is now pinned to a cheap sibling on
  the same pool — Claude profiles to `anthropic` / `claude-sonnet-5`; Astra
  profiles and Creator's family to `openai-codex` / `gpt-6-luna` (GPT-5.6
  Luna until 2026-09-23) — each with a `fallback_chain`
  to `openrouter` / `deepseek/deepseek-v4-flash`. Two safety nets already
  exist below that: the configured chain (`auxiliary_client.py:3887`) and a
  last-resort hop to the main agent model (`:3801`), so a pinned aux model
  never becomes a single point of failure. **`vision` deliberately stays
  `auto`** — pinning it disables the main model's native image vision (see
  `AGENTS.md`).
- **Copilot retired from every chain** (2026-07): the subscription became
  unusable, and its catalog drift had already 404'd tiers silently once.
  Profile fallbacks now use Codex first and OpenRouter as the final tail.
  `GITHUB_TOKEN` stays in the `hermes` Keychain layer for the Skills Hub — it
  is no longer a model-provider credential.
- **OpenRouter slugs** — `xiaomi/mimo-v2.5`, `deepseek/deepseek-v4-flash`,
  `google/gemini-3.5-flash` (the earlier `*-v3.2` / `gemini-3-flash-preview`
  refs were planning guesses).
- **OpenRouter tail split (vision vs text-only)** — profiles whose fallback
  turns may need to SEE something keep a vision-capable tail:
  `default` / `assistant` / `researcher` / `searcher` / `marketer` use
  `xiaomi/mimo-v2.5` (omnimodal, cheap; video analysis stays decoupled via
  the `video-analyze-mimo` plugin — see `README.md` "Plugins"). Text-only work
  rides the cheaper `deepseek/deepseek-v4-flash` (`engineer`, `writer` tail).
  Researcher and searcher gained vision in the 2026-07 copilot removal as a
  side effect of standardizing on mimo. Creator's hands (`creator`,
  `image-creator`, `audio-creator`, `video-creator`) keep their
  `minimax/minimax-m3` OpenRouter vision tail (unchanged by the 2026-09-13
  Anthropic-primary reassignment): the chain is Claude -> `openai-codex` /
  `gpt-6-astra` -> `openrouter` / `minimax/minimax-m3`, so eyeballing
  generated assets on the final fallback turn still rides the same
  OpenRouter sibling as before.

Optional: set `delegation.model: google/gemini-3.5-flash` on default /
assistant to route `delegate_task` subagents to a cheap model.

### Fable and the Max weekly pool

Five profiles now lead with **Fable 5.1** (assistant, engineer, writer,
marketer; creator carries it at T2). These facts govern that tier — they were
measured on Fable 5 and the 5.1 alias behaves the same way:

1. **Fable is not a separate quota tank.** On Max it is included but capped at
   **≤50% of the plan's weekly pool**, drawn from the *same* pool as Opus, and
   it burns that pool faster. So `Fable → Opus` only rescues the case where the
   Fable sub-cap is exhausted while the overall weekly still has room. If the
   shared weekly or the 5-hour session limit is what tripped, Opus is dead too
   and the chain correctly continues to Codex.

   **This is why Opus sits at T2, ahead of Astra**, on every Fable profile.
   The sub-cap case is the *long* failure — it persists until the week rolls
   over — and in exactly that case Opus is still alive. Putting Astra there
   instead would hand days of ordinary traffic to the ChatGPT Pro pool that
   OpenCode Build and the two Astra-first profiles depend on. Creator inverts
   the pair for the same reason read from the other side: it leads on Astra,
   so its Claude tiers are the rescue.
2. **The T2 step depends on the token being resolvable outside the credential
   pool.** A `usage_limit_reached` 429 marks the *credential* exhausted, and
   that mark has **no model dimension** (`credential_pool.py:662`) — the pool
   then refuses to hand it out. The Opus attempt only succeeds because
   `resolve_anthropic_token()` checks `ANTHROPIC_TOKEN` /
   `CLAUDE_CODE_OAUTH_TOKEN` / the Claude Code Keychain entry **before** the
   pool (`anthropic_adapter.py:1401`). Park the Max subscription *only* in the
   credential pool and the Opus tier is silently skipped — the chain quietly
   degrades to `Fable → Codex`.
3. **Hermes has no per-model quota memory.** The "included Fable 5 usage for
   this week" message carries no parseable reset, so a fixed **1-hour** local
   cooldown is applied (`credential_pool.py:117`), while the agent-level
   fallback cooldown is only **60 seconds** (`chat_completion_helpers.py:1549`).
   At t+61s the primary is restored and Fable is retried. Once the weekly cap
   is hit this costs **one wasted request per turn until the week rolls
   over**. Engineer, writer and marketer absorb that cheaply — they are
   low-turn profiles. The **assistant** is the exception: it is the
   latency-sensitive front door, so when the cap is reached, switch its live
   sessions off Fable with **`/model`** rather than waiting out the week. That
   manual escape is what makes a Fable T1 acceptable there at all.
4. **Adaptive thinking, not manual budgets.** Modern Claude — Fable 5 included —
   gets `thinking: {type: adaptive}` + `output_config: {effort: …}`, so the
   effort level passes straight through (`minimal→low`, `ultra→max`); the
   legacy 4k/8k/16k/32k `budget_tokens` table does **not** apply. Long
   structured outputs prefer `high` over `xhigh`: Hermes can otherwise burn
   the whole output budget on reasoning (`conversation_loop.py:2600`). If
   that warning ever appears, drop to `medium` or raise `max_tokens`.

### `agent.*` does not inherit from the root profile

A named profile's config is `$HERMES_HOME/config.yaml` deep-merged with the
built-in `DEFAULT_CONFIG` **only** (`hermes_cli/config.py:680,7456`) — the root
`~/.hermes/config.yaml` is never a parent. `--clone` copies it once at creation
time; that is not live inheritance.

This bites hardest on `agent.reasoning_effort`, because `DEFAULT_CONFIG["agent"]`
has **no** `reasoning_effort` key. Omitting it does not inherit the root's
`medium` — it resolves to `None`, and each provider path then does something
different: native Anthropic sends no `thinking`/`output_config` at all
(`anthropic_adapter.py:2854`), Codex defaults to `medium`
(`transports/codex.py:170`), OpenRouter to `{enabled: true, effort: medium}`.
The result is a profile whose T1 is unspecified while its fallbacks are
`medium`. Five profiles sat in that state until 2026-07; every profile now
carries an explicit value. **Set `agent.*` keys per profile, always.**

## Authentication inheritance

`auth.json` is per-profile (`auth.py:855-856`, built from `get_hermes_home()`),
**but** a named profile with no entry for a provider falls back **read-only** to
the default profile's `~/.hermes/auth.json` (`auth.py:1131-1157,1215-1259`).

- OAuth logins done in **default** (`hermes model`, no `-p`) — Codex, Copilot,
  xAI-OAuth — are inherited by every worker. **No per-worker re-auth.**
- **Anthropic native** is OAuth (Claude Pro/Max) but its creds live **outside**
  `auth.json` (`~/.hermes/.anthropic_oauth.json` for Hermes' PKCE flow, else the
  Claude Code credential / `CLAUDE_CODE_OAUTH_TOKEN`). That source is
  machine-global, so every profile authenticates with **no per-worker login**
  (`hermes auth status anthropic` → logged in); the auth.json read-only fallback
  does not apply to it.
- Always run OAuth logins from default. Running `hermes model` *inside* a worker
  writes that profile's `auth.json` and shadows the inherited creds for that
  provider (writes never propagate).
- **Shadowed creds survive a default re-login, and `hermes doctor` will not see
  it.** Doctor inspects default, so it reports the provider healthy while a
  worker still loads its own stale entry — the fallback only applies to a
  profile with *no* entry at all. The symptom is uneven: the model can keep
  answering while a tool that resolves through the credential pool goes
  missing, so `x_search` returns unavailable on a profile whose grok replies
  fine. Confirm with `providers` in the worker's own
  `~/.hermes/profiles/<name>/auth.json`; the repair is to drop that provider
  key so the profile inherits default again. Prefer editing the file over
  `hermes auth logout`, which may revoke upstream and take the shared
  credential down with it.
- Env tokens work everywhere via the shim: Copilot reads
  `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` → `gh auth token`
  (`copilot_auth.py:39,67-95`); xAI accepts `XAI_API_KEY`.

Two caveats:

1. **Copilot token shadowing** (historical — copilot left every model chain
   2026-07, kept for if it returns). Copilot checks env before stored OAuth
   creds (`COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN` → `gh`); a
   non-Copilot-capable `GITHUB_TOKEN` in the `hermes` layer would 401 it.
   `COPILOT_GITHUB_TOKEN` (highest priority) overrides regardless.
2. **Parallel OAuth refresh.** Several workers refreshing the same rotating
   refresh token at once can race to `invalid_grant`. If it bites, move
   high-parallelism workers' T1 to an API-key provider (OpenRouter / `XAI_API_KEY`).

## Secrets layering

No `.env`. The `bin/hermes` shim injects two Keychain layers at launch —
`global` (shared by every shimmed tool) then `hermes` (the command name). A
profile alias `~/.local/bin/<name>` runs **bare `hermes -p <name>`**, so it
routes through the same `bin/hermes` shim — **every profile gets `global` +
`hermes`** (`~/.config/bin` precedes `~/.local/bin` on `PATH`). See
[`README.md`](../README.md#secrets).

- **`hermes`** — shared model/fallback keys every profile and every
  dispatcher-spawned worker needs: `OPENROUTER_API_KEY` (the OpenRouter
  fallback tails) and `GITHUB_TOKEN` (Skills Hub; no longer a model
  provider since the 2026-07 copilot retirement). The legacy messaging keys
  (`TELEGRAM_*` / `DISCORD_*`) still parked here are IGNORED by the profile
  scopes (filtered by `profile-secrets.sh`) — the per-bot copies below are
  authoritative.
- **`global`** — keys shared with *other* tools (editor, MCP servers, other
  CLIs). Nothing Hermes-specific needs to live here.
- **`hermes-<profile>`** (assistant / engineer / creator / marketer) — that
  bot's own `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_USERS` (assistant also
  `TELEGRAM_HOME_CHANNEL` / `TELEGRAM_DM_CHAT_ID` / `DISCORD_*`). One bot,
  one layer; never share a token between layers.
- **OAuth**: Codex / Copilot / xAI-OAuth in default's `auth.json` (read-only
  fallback to every profile); **Anthropic** resolves separately via the Claude
  Code credential / token (machine-global, every profile).

**Multiplex changes where these layers land.** Scope-aware reads inside the
gateway (bot tokens, `OPENROUTER_API_KEY`, `EXA/PARALLEL/FIRECRAWL/XAI` keys,
`GITHUB_TOKEN`, TTS keys, …) resolve ONLY from each profile's secret scope and
never fall back to the process env. Every profile therefore carries
`secrets.command` → `scripts/profile-secrets.sh <profile>`, which emits
`global` + `hermes` (minus messaging keys) + `hermes-<profile>` as dotenv
lines at startup (and derives `TELEGRAM_CRON_THREAD_ID` from the persisted
Inbox topic for assistant). Raw-env readers (dashboard auth) still read the
process env the launcher injects — which is also why `BU_CDP_URL` must never
be in those layers: `browser_exec` copies it raw from the process env and it
would pre-empt real-profile browsing for every profile at once (see the
browser-stack rule in `AGENTS.md`).

Workers need no unique secret: the dispatcher execs `hermes -p <worker>`, which
hits the `bin/hermes` shim (`global` + `hermes`), and they also inherit the
gateway's env. A background **LaunchAgent** can start with a stripped `PATH`, so
the gateway launcher sets its own `PATH` and `eval`s the Keychain layers
directly (below).
