# Creator family splits by hand

Status: in force
Owner doc: docs/models-auth.md "Models and fallback chains" (bullet "The Creator family splits by hand")

## Decision

`video-creator` leads on Opus 5.5, `creator` on Fable 5.1 (Opus 5.5 as T2),
and `image-creator` and `audio-creator` on Sonnet 5.5. The split is by hand,
not for the family as a whole.

## Why

- A blind A/B on one launch-video brief (isolated homes, model pinned, fallback
  off) scored every Sonnet 5 run fidelity 1/5, with the full pipeline or a bare
  single agent, while Opus 5.5 reached 3-4/5 on both.
- A later blind per-family A/B of Opus 5.5 against Sonnet 5.5 found Sonnet
  equal on image and audio leaves at about 0.6x the tokens, clearly behind on
  authored video (craft -0.8, lost 8 of 8 explainer pairings) and inconclusive
  for Creator as broker.
- The arms were small, so this rests on a clear gap on video, not on statistics.
- `creator` runs on Fable 5.1 as a trial, not a measured result: it is a
  low-turn advisor whose broker comparison was inconclusive, and the Claude
  weekly pool has headroom. Keep it only if its proposals hold up against the
  Opus baseline and the pool still covers `video-creator`.

## Do not

- Move `video-creator` or `creator` to a Sonnet lead to save tokens without a new blind comparison on authored video.
- Move `video-creator` to Fable on the strength of the `creator` trial: its hundreds of vision calls per job burn Fable's ceiling far faster.
- Treat the family as one model choice: image and audio keep the cheaper lead on purpose.
