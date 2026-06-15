# Backends & the fallback chain

`video_generate` dispatches to whatever `video_gen.provider` names. On this
machine that's a **fallback chain** (plugin: `video-fallback`), so a call tries
one backend and falls through to the next on unavailability / error / rate-limit
/ missing tier.

| `video_gen.provider` | Order | Use |
|---|---|---|
| **`vid-xai-fal`** (default here) | Grok Imagine → FAL.ai | Grok first; FAL.ai as the safety net |
| `vid-fal-xai` | FAL.ai → Grok Imagine | FAL first (e.g. for audio / 1080p / specific model) |

Switch chains by setting `video_gen.provider` in the profile's `config.yaml`.
**Don't pass `model=` from the agent** — a model id valid for one backend is
invalid for the other and breaks failover. To force a specific model family, set
the backend directly (not the chain) and configure its model via `hermes tools`.

## Capability matrix

| | **xAI Grok Imagine** (`xai`) | **FAL.ai** (`fal`) |
|---|---|---|
| Modalities | text + image | text + image |
| Aspect ratios | 16:9, 9:16, 1:1, 4:3, 3:4, 3:2, 2:3 | 16:9, 9:16, 1:1 |
| Resolutions | 480p, 720p | 360p, 540p, 720p, **1080p** |
| Duration | 1–15s | 1–15s |
| Audio | **no** | **yes** (model-dependent) |
| Negative prompt | no | **yes** |
| Reference images | **up to 7** | 0 |
| Credentials | xAI Grok OAuth (SuperGrok / Premium+) or `XAI_API_KEY` | `FAL_KEY` |

Pick by need: **portrait + reference images** → Grok strengths; **1080p, audio,
or negative prompts** → FAL strengths (consider `vid-fal-xai`).

## Model families

**xAI Grok Imagine** (`~60–240s` per clip):
- `grok-imagine-video` — text-to-video (+ legacy image-to-video fallback).
- `grok-imagine-video-1.5-preview` — latest **image-to-video** model.

**FAL.ai** (default family: `pixverse-v6`):
| Model | Tier | Notes |
|---|---|---|
| `ltx-2.3` | cheap | 22B, native audio, affordable |
| `pixverse-v6` | cheap | affordable, negative prompts, 1–15s |
| `veo3.1` | premium | Google DeepMind; cinematic, native audio, strong adherence |
| `seedance-2.0` | premium | ByteDance; cinematic, synced audio + lip-sync, 4–15s |
| `kling-v3-4k` | premium | 4K output, native audio (CN/EN), 3–15s |
| `happy-horse` | premium | Alibaba; new, conservative defaults |

The active FAL model is user-configured via `hermes tools`; the agent shouldn't
hardcode it.

## Credentials on this machine

- **`FAL_KEY`** — present in the Keychain (`hermes` layer), injected by the
  `bin/hermes` shim. FAL is ready.
- **xAI** — inherited via the default profile's `auth.json` OAuth (SuperGrok /
  Premium+), read-only across profiles; `XAI_API_KEY` also works if set.
- Grok Imagine video may require a sufficient xAI tier; if a call 4xxs on tier,
  the chain falls through to FAL automatically.
