# Model routing — quota gate, provider ladder, model choice

Loaded before the first OpenCode invocation of an implementation task (and
by advisory tasks only if they invoke OpenCode at all).

## QuotaGate

The gate is **comparative** — both subscription pools are shared with the
human's interactive OpenCode use, so route to the pool with headroom:

```text
terminal(command="npx -y @slkiser/opencode-quota show", workdir="<wd>", timeout=90)
```

- Both pools report a remaining % → pick the one with **more headroom**
  (tie → Claude for heavy/high-risk, OpenAI for standard).
- A pool under ~15% left → treat it as exhausted for heavy work; only
  small/mechanical jobs may still use it.
- **Anthropic `Unavailable (not detected)` is a known false negative** (the
  tool cannot read Claude subscription usage on this machine) — it does NOT
  mean "no quota". Fall back to an auth check: anthropic models listed in
  `opencode models` → Claude is usable; prefer Claude when OpenAI is below
  ~30% or the work is heavy/high-risk, otherwise OpenAI.
- Neither pool usable (auth missing / both exhausted) → cheap tier per
  ProviderSelection. `claude auth status` alone is never the gate.

Within the chosen pool, weight the model by task risk per ModelChoice.

## ProviderSelection

High → low:

1. **Claude via OpenCode** — when QuotaGate routes to Claude.
   Heavy/high-risk → Opus 4.8; light/mechanical → Haiku 4.5.
   If OpenCode-native Claude is gated/unavailable, **Copilot** is the alternate
   Claude-family source (Claude-family first, then OpenAI-family).
2. **OpenAI via OpenCode** — when QuotaGate routes to OpenAI. High-risk →
   `gpt-5.6-sol`; standard → `gpt-5.6-terra`; routine/cheap → `gpt-5.6-luna`
   or the configured light model.
3. **OpenRouter** — cheap coding-capable models only. **Never Claude/GPT via OpenRouter**
   (exclude `anthropic` / `claude` / `openai` / `gpt`). Prefer Deepseek-4-Flash, then Deepseek-4-pro.
4. Direct `claude-code` / `codex` only on explicit request or when OpenCode is unsuitable.

Resolve exact `--model provider/model` slugs at runtime (`opencode models`) — don't hard-code stale ones.

## ModelChoice

Weight by task risk:

| Class | Use for |
|---|---|
| Opus 4.8 / GPT-5.6 Sol | high-risk architecture, complex refactor, hard debugging |
| Sonnet / GPT-5.6 Terra | default implementation, standard features, tests |
| Haiku / GPT-5.6 Luna / cheap OpenRouter | small/mechanical fixes, docs, low-risk cleanup |

## Pitfalls

- Treating `claude auth status` as the quota gate, or reading Anthropic
  "Unavailable (not detected)" as "no Claude" — use the comparative gate and
  its auth fallback.
- Falling back to OpenRouter but selecting Claude/GPT there.
- Treating OpenAI Pro quota as interchangeable with Codex/Copilot quota; check the
  provider actually selected for the run.
- Hard-coding stale model slugs instead of resolving via `opencode models`.

## Verification

- Quota/provider decision recorded in the report (or failure reported).
- On quota / rate / auth errors the run dropped to the next rung and the
  final report names the provider/model actually used.
