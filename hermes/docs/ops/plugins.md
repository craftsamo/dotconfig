# Plugins

How plugins under `hermes/plugins/` are enabled and grouped, the config
convention for the media backends, and the mechanics of the plugins that have
no design doc of their own. Read it before enabling, moving or configuring a
plugin.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Plugins

`~/.hermes/plugins` (and each profile's) is symlinked to `hermes/plugins/`, so a
new plugin needs no re-`install.sh` — only `plugins.enabled` (and any toolset)
in the relevant `config.yaml`. After a plugin enablement change the multiplex
gateway needs one normal drained restart (`/restart` or
`gateway-launchctl.sh install`); never launch a second gateway.

Each plugin's `plugin.yaml` `description:` says what it is; its design is in the
matching `docs/*.md` (index: [`../../PROFILES.md`](../../PROFILES.md)). Plugin
code layout and the maintainer rules for moving plugins and `_shared/`
directories are in [`../../AGENTS.md`](../../AGENTS.md) "Skills".

- **Groups.** Plugins sit either at the top level or one directory down in a
  group (`<group>/<name>/plugin.yaml`; Hermes reads one level and keys the plugin
  `group/name`). `plugins.enabled` accepts the bare name, but `plugins.entries`
  (e.g. `allow_tool_override`) needs the full `group/name` key: a bare key is
  ignored and the plugin fails to load. Current groups:
  `messaging/` (chat accounts), `social/` (public platforms: x, note, substack,
  youtube), `web3/` (chain reads and the wallet), `orchestration/` (specialist,
  OpenCode and session-history transports), `workspace/` (drafts, repos and the
  private registry/report overlay), `guards/` (topology and Worker guards),
  `inspection/` (vision window, video analysis, media and writing inspection),
  and the media families `image_gen/`, `video_gen/`, `audio_gen/`, `tts/`,
  `transcription/`. `google-access` and `hermes-achievements` (upstream writes
  its data to a fixed path; per-machine, ignored) stay at the top level. A
  directory with no `plugin.yaml` (`_shared/`) is code, not a plugin.

### Media stack

Backends are chosen via `*_gen.provider` / `tts.provider` / `stt.provider` plus
`*.fallback.chain`. These custom keys (and top-level ones such as
`video_analyze:`) survive Hermes' config rewrites because `_deep_merge` keeps
user keys.

- **image_gen/image-fallback** (`backend`): `img-codex-xai`,
  `img-xai-codex-fal`, `img-codex-xai-fal` — names spell the order.
  Capabilities: [`../hands/image.md`](../hands/image.md) "Image generation
  capabilities".
- **video_gen/video-fallback** (`backend`): `vid-xai-fal` (Grok Imagine → FAL),
  `vid-fal-xai`.
- **inspection/video-analyze-mimo** (`standalone`): overrides `video_analyze`
  with a fixed, config-driven backend (`video_analyze: {provider, model}`), so
  `auxiliary.vision` can stay `auto` and images route natively to the main
  model. **Pinning `auxiliary.vision` to a video-capable model disables the main
  model's native image vision.**
- **inspection/media-inspect** (`standalone`): the `media_inspect` tool for
  Creator and the Assistant (`probe`, `frames`, `sheet`; each profile is offered
  its own action list). It never writes next to the input: output goes to a
  fresh run directory under the OS temporary directory, and runs older than
  seven days are removed when the plugin registers.
- **tts/tts-fallback**, **tts/irodori-tts**, **tts/qwen3-tts**: see
  [`tts-engines.md`](./tts-engines.md). **transcription/stt-fallback**: see
  [`audio-tooling.md`](./audio-tooling.md) "Speech-to-text — fallback chain".
- **tts/characters** is a private-overlay plugin, not in this repo (its path is
  ignored): the character library — `characters` (toolset `characters`) for
  Writer, Assistant and Creator, and the code behind `bin/characters`, whose
  `sync` registers character voices in the local TTS engines. Writer and
  Creator enable it by name; without the overlay the toolset is simply absent.
  Contract: [`../hands/audio.md`](../hands/audio.md) "Character voices and
  performance direction".

### Transports

- **orchestration/specialist-call** gives the `specialist` toolset to assistant,
  creator and marketer. Enable `specialist-call` in `plugins.enabled`,
  `specialist` in the relevant `platform_toolsets` lists, and configure the
  explicit `specialist_call.resident_targets` allowlist. Behavior:
  [`../profiles/specialist-calls.md`](../profiles/specialist-calls.md).
- **orchestration/opencode** gives the assistant the OpenCode tools over the
  shared OpenCode service. Enable `opencode` in `plugins.enabled` and the
  `opencode` toolset, and set `opencode.enabled: true` (without it the tools
  refuse), `wait_timeout`, `allowed_providers` and optionally `roles`. Behavior:
  [`../opencode.md`](../opencode.md).
- **orchestration/session-history** gives the assistant `hermes_history` (toolset
  `session_history`) and the `/activity` command, and is the code behind
  `bin/ai-history`: [`../session-history.md`](../session-history.md).

### Guards

- **guards/skill-topology** blocks runtime writes into maintainer skill trees
  (here and in the private overlay's `hermes/profiles/*/skills/`, both outside
  `learned/`). It does not intercept dashboard direct-create APIs or arbitrary
  terminal/file writes — the validator catches those after the fact
  ([`skills.md`](./skills.md) "Skills").
