<Goal>

This reference covers the two approved implementation backends behind
`creator-generated-video`. The MediaBrief fixes one before production.

For `core:video_generate`, the tool dispatches to whatever
`video_gen.provider` names. On this machine that is a **fallback chain**
(plugin: `video-fallback`), so a call tries one provider and falls through to the
next on unavailability / error / rate-limit / missing tier.

| `video_gen.provider` | Order | Use |
|---|---|---|
| **`vid-xai-fal`** (default here) | Grok Imagine → FAL.ai | Grok first; FAL.ai as the safety net |
| `vid-fal-xai` | FAL.ai → Grok Imagine | FAL first (e.g. for audio / 1080p / specific model) |

Switch chains by setting `video_gen.provider` in the profile's `config.yaml`.
**Don't pass `model=` from the agent** — a model id valid for one backend is
invalid for the other and breaks failover. To force a specific model family, set
the backend directly (not the chain) and configure its model via `hermes tools`.

</Goal>

<ComfyUILocal>

`external:comfyui` is a separate local workflow runtime, not a member of the
core fallback chain. Load the official `comfyui` skill and preflight, without
submitting a prompt:

- `comfy` resolves the intended workspace, and the approved host is an exact
  loopback URL (`127.0.0.1` / `localhost`), never Comfy Cloud or a proxy;
- hash the selected API-format workflow and keep that path + SHA-256 in the
  capability handshake;
- `health_check.py` is reachability/dependency evidence, not proof of the whole
  preflight: inspect `server.stats.devices` for the expected accelerator (never
  CPU), require `node_check_skipped: false`, empty missing lists, and empty
  `folder_errors`;
- run `extract_schema.py` and inspect the workflow's models and output/container
  nodes explicitly;
- query the same host's `/object_info` and audit every workflow `class_type`.
  Reject `api_node: true`, Partner/API categories, and custom nodes whose package
  or source is not installed in the resolved local workspace. For every
  non-core custom node, require a trusted-package allowlist entry or inspect its
  source for outbound HTTP clients, cloud SDKs, API-key reads, subprocesses, and
  hidden hosted-generation calls;
- every model file and custom node exists, and newly installed nodes have been
  loaded by a server restart;
- the estimated render time fits the MediaBrief's local runtime grant;
- output nodes write a supported video container to a durable/localizable path;
- the graph contains no ComfyUI Partner API node. Such a node is hosted
  generation with a separate wallet, not the approved local backend.

Any failed check blocks this backend. Do not call `video_generate`, switch to a
Partner node, download a new model, or cross to cloud without a new released
decision from the Assistant.

Only the selected run proves executability. Preserve `run_workflow.py`'s JSON,
then use its `prompt_id` with the external skill's `fetch_logs.py --raw --host
<same-loopback-host>`. The raw history entry is the evidence for the effective
submitted graph, model/seed parameters, status, and execution timing. Hash the
effective graph separately and compare node IDs/classes/wiring with the
pre-run source; recorded parameter injections may differ. If history was not
captured, report those claims as unknown and do not pass V1.

</ComfyUILocal>

<CapabilityMatrix>

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

</CapabilityMatrix>

<ModelFamilies>

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

</ModelFamilies>

<Credentials>

- **`FAL_KEY`** — present in the Keychain (`hermes` layer), injected by the
  `bin/hermes` shim. FAL is ready.
- **xAI** — inherited via the default profile's `auth.json` OAuth (SuperGrok /
  Premium+), read-only across profiles; `XAI_API_KEY` also works if set.
- Grok Imagine video may require a sufficient xAI tier; if a call 4xxs on tier,
  the chain falls through to FAL automatically.

</Credentials>
