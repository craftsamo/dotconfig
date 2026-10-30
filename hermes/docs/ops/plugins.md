# Plugins

How plugins under `hermes/plugins/` are enabled and grouped, the config
convention for the media backends, and the mechanics of the plugins that have
no design doc of their own. Read it before enabling, moving or configuring a
plugin.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Plugins

`~/.hermes/plugins` is a real directory of links into `hermes/plugins/` (a
flat plugin linked whole, a group as a directory of one link per plugin), and
each profile's `plugins` links to it ([README "Symlinks"](../../README.md#symlinks)).
So a new plugin, like any new file, needs `../install.sh` to link it, and then
`plugins.enabled` (and any toolset) in the relevant `config.yaml`; until the
installer runs, Hermes does not see it. Editing an existing plugin needs no
installer run: its link already points into the repo. After a new plugin, an
enablement change or a change to plugin code the gateway runs, the multiplex
gateway needs one normal drained restart (`/restart` or
`gateway-launchctl.sh restart`); never launch a second gateway.

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
  youtube), `web3/` (chain reads, Hyperliquid reads and the wallet), `orchestration/` (specialist,
  OpenCode and session-history transports), `workspace/` (the public drafts, repos and
  registry engines; a local overlay may add more), `guards/` (topology and Worker guards),
  `inspection/` (vision window, video analysis, media and writing inspection,
  listening to an app's audio),
  the media families `image_gen/`, `video_gen/`, `audio_gen/`, `tts/`,
  `transcription/`, and `model-providers/` (inference providers: `antigravity`,
  [`../models-auth.md`](../models-auth.md) "Google Antigravity"). A
  model-provider plugin needs no `plugins.enabled` entry: Hermes' provider
  discovery imports every one under `model-providers/` in every profile, and it
  is used only where a config or a session selects its provider. `google-access` and `hermes-achievements` (upstream writes
  its data to a fixed path; per-machine, ignored) stay at the top level. A
  directory with no `plugin.yaml` (`_shared/`) is code, not a plugin.
- **Progress lines.** For a tool with no preview of its own, Hermes shows the
  first argument named `query`, `text`, `command`, `path`, `name`, `prompt`,
  `code` or `goal` in the chat's progress line (a message body or a local path
  as written), or just `<tool>...`. So each plugin tool installs its own
  preview through `_shared/tool_preview.py` at registration: `enums` shows the
  call's `action` (and `kind` where the schema has one), `fixed` a constant
  label for a tool whose arguments are all content, `install` a builder of the
  plugin's own (OpenCode's `reply once×2, answer`, `specialist_call`'s
  `work → <target>` with the target checked against the roster). Only values
  the schema declares as choices pass, so free text never reaches the line.
  Hermes has no hook for this: the builders go into `agent.display`'s private
  table, one for every profile in the gateway. If an update renames it, the
  plugin logs `tool preview … not installed` and the lines fall back to
  Hermes' own, while the tools keep working. A change applies at the next
  gateway restart. `display.tool_progress: verbose` still prints every
  argument. The line's leading emoji is the `emoji=` each plugin passes to
  `register_tool` (an OpenCode run tool takes its role's, see
  [opencode.md](../opencode.md)); without one Hermes shows ⚙️ in a chat and ⚡
  in the CLI, and `test_plugin_tool_emojis.py` refuses that.

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
  with config-driven backends, so `auxiliary.vision` can stay `auto` and images
  route natively to the main model. **Pinning `auxiliary.vision` to a
  video-capable model disables the main model's native image vision.** The
  whole video goes to `video_analyze.backends` (a list of `{provider, model}`,
  tried in order; the single `{provider, model}` form and the OpenRouter MiMo
  default still read), through `plugins/_shared/media_backends.py`: an error,
  or a reply with no text after one retry, moves to the next backend, and the
  result names the backend that answered and the ones that failed. Each
  backend is called directly, not through `async_call_llm`, whose capacity
  fallback would send the video to a provider the list does not name. A reply
  that is only reasoning counts as no answer, since a model that never saw the
  video describes one anyway; when every backend fails, the tool says so
  rather than returning a guess.
- **inspection/audio-analyze** (`standalone`): the `audio_analyze` tool for the
  Assistant, researcher and audio-creator. One recording (a local file or an
  http(s) URL; wav, mp3, m4a, aac, ogg, opus, flac or aiff, up to 14 MiB)
  goes whole, as `input_audio`, to `audio_analyze.backends` through the same
  `media_backends` rules as `video_analyze` (default: OpenRouter's
  `google/gemini-3.8-flash`), which answers about speech, speakers, tone,
  music and other sounds with no local transcription first. The recording
  leaves the machine: the tool is for a request that asked for it, and
  audio-creator's speech and music analysis stays local unless the
  commission's note asks for a remote listen.
- **inspection/media-inspect** (`standalone`): the `media_inspect` tool for
  Creator and the Assistant (`probe`, `frames`, `sheet`; each profile is offered
  its own action list). It never writes next to the input: output goes to a
  fresh run directory under the OS temporary directory, and runs older than
  seven days are removed when the plugin registers.
- **inspection/screen-listen** (`standalone`): the `screen_listen` tool for the
  Assistant: record what one allowed app (Discord by default) is playing on this
  Mac through a Core Audio process tap — a few minutes transcribed locally, or
  a session of hours kept as an m4a under `screen_listen.record_dir`, with
  the app's window on video (ScreenCaptureKit) when asked. The helper app is
  built by `scripts/screen-listen.sh install` and holds the System Audio
  Recording consent (and Screen Recording for video). Contract:
  [`../screen-listen.md`](../screen-listen.md).
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
  explicit `specialist_call.resident_targets` allowlist. A profile kept in
  the private overlay is added to the plugin's roster by the overlay's
  `local_targets.json`, linked into `~/.hermes/plugin-data/specialist-call/`. Behavior:
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
- **guards/clarify-context** refuses a `clarify` whose subject the user has not
  seen: nothing visible since their last message and no question `context`, or
  `MEDIA:` tags in a reply of the current turn that the question's `context`
  does not carry (reply attachments arrive after the turn, so after the card;
  `context` attachments arrive before it). Gateway
  notifications do not count as the user speaking. It needs the hermes-agent `feat/clarify-context` patch
  (the `context` field, delivered and verified before the card) and stands down
  with a warning on a runtime without it. Enabled where `clarify` is allowed:
  the Assistant and Marketer.
- **guards/cron-manifests** replaces the built-in `cronjob_manage` (same name
  and schema; `plugins.entries."guards/cron-manifests".allow_tool_override:
true` is required, or Hermes keeps its own tool) so a job the agent creates
  is a `cron.d/<name>/` directory of its profile that cron-sync turns into the
  job, an update rewrites that directory, a removal deletes it with the job,
  and a job tracked in a repository is refused. `list` and `run` are the
  runtime's. Enabled where the `cronjob` toolset is: the Assistant. Contract:
  [`cron.md`](./cron.md).
