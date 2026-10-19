# Researcher leads on Fable, Assistant carries Astra

Status: in force
Owner doc: docs/models-auth.md "Models and fallback chains"

## Decision

`researcher` leads on Fable 5.1 (Opus 5.5 as T2, Sonnet 5.5 as the last
Claude tier, then GPT-6.1 Sol and the OpenRouter tail). `assistant` carries
GPT-6 Astra as T3, between Fable 5.1 and Sonnet 5.5.

## Why

- The ChatGPT Plus allowance shared with OpenCode had headroom. OpenCode took
  most of it (its explore tiers now lead on the ChatGPT window); the
  Assistant takes one tier of it, in the spot where a capable model matters
  more than staying on Claude: both Opus sub-caps spent, Sonnet still alive.
- `researcher` on Fable is the same bet as `creator` on Fable: a profile
  whose judgment matters, on the model with its own 50%-of-week ceiling, so
  it stays alive when the Opus cap is the reason the rest of the pool fails.
  Its chain keeps every Claude tier and gains Sonnet as the last one, so a
  spent Fable ceiling degrades inside the pool before reaching Codex.
- The Codex route caps Astra at 272k; the runtime compresses at the profile's
  threshold once the chain is on it, and a turn already above it falls to
  Sonnet. No pin is set: `model.context_length` describes T1 only.

## Do not

- Put Astra or Sol ahead of the Claude tiers on a profile other than
  `assistant` or `searcher` without re-sizing OpenCode's share of the
  allowance first: a `video-creator` job on it drains the week.
- Move `researcher` back to a Sonnet lead to save Fable's ceiling without
  checking `creator`'s week first: they draw on the same ceiling, and a busy
  Creator week is the case this chain is meant to survive, not cause.
