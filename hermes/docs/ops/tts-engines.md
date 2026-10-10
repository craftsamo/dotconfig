# Local TTS engines

The two loopback TTS engines (Irodori and Qwen3-TTS): how the fallback chain
routes by language, where voice data lives, and how each engine's provider and
launcher work. Read it before changing a TTS plugin, a launcher or a voice
registration.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Local TTS engines

Two loopback-only engines run as LaunchAgents and take no API key:
`irodori-tts` on `127.0.0.1:10103` and `qwen3-tts` on `127.0.0.1:10102`.

**Language routing is the chain order, not a router.** `tts.fallback.chain`
orders `irodori-tts → qwen3-tts → edge`. Irodori is Japanese-only — it mangles
English — so it _declines_ English-dominant text
(`tts.irodori_tts.min_japanese_ratio`) by raising, and the chain advances to
Qwen3. No routing layer exists and none should be added. The hand-off is per
utterance on purpose: the same reference voice sounds audibly different on the
two engines, so splicing them inside one sentence is audible. An unavailable or
still-loading server advances to the next tier and finally to Edge TTS; the call
errors only if every tier fails. Normal speech omits a voice ID and uses each
engine's default. A pinned, named voice (no routing, no substitution, never
reads `tts.fallback.chain`) is a different contract:
[docs/hands/audio.md](../hands/audio.md) "Character voices and performance
direction".

Auto-speech (`voice.auto_tts: true`) is voice-in → voice-out in the gateway and
TTS-on-by-default inside CLI voice mode; it never auto-speaks plain text turns.
After changing a live config, restart the relevant Hermes process (e.g. the
gateway).

**Voice data never enters this repo.** Reference audio lives in the private
character tree and is copied into the ignored `local/<engine>/` by the
launchers; the Irodori lexicon (`local/irodori-tts/lexicon.json`) is a symlink
the private overlay installs. Do not add a local-engine voice (`voice:`) key
under `tts.*` and do not name a lexicon or manifest path in `config.yaml` — both
are tracked. Private voice and lexicon paths go through the launchers'
`register*` commands only.

**Irodori** runs fp32 on MPS (bf16 is CUDA/XPU-only upstream) from a git
checkout pinned in `engines/irodori-tts/pinned.conf`. The checkpoint renders
slower than real time, so a long reply can spend the whole
`tts.irodori_tts.synthesis_timeout` before the chain falls through to Qwen3. The
provider repairs its own WAV (gates pause rustle, trims dead air and trailing
hallucinated fragments, fades the onset click, normalises level) with numpy and
the stdlib only, because Hermes' dependency generation carries no soundfile or
scipy.

**Irodori readings are fixed in the provider, not left to the model.** The
checkpoint has no reading frontend (the server applies NFKC and deletes some
symbols, including every hyphen, so `-5` arrives as `5`), and the shared Hermes
cleaner, written for English voices, has already turned `25°C` into
`25 degrees Celsius`. The plugin's `reading.py` therefore applies the private
lexicon to the text as written, maps that English back to Japanese, spells out
symbols, and rewrites only the number forms the model misreads. It is not kana
throughout: a long kana run loses its word boundaries and the model phrases it
wrongly. `reading_frontend: false` switches the rewriting off and keeps the
lexicon. The shared cleaner itself stays untouched (see
[`AGENTS.md`](../../AGENTS.md)); a line the cleaner closes with an extra `.`
after `？`/`！`/`。` loses that stop here, since the model reads it as a second,
falling sentence end.

**Irodori pacing is set in the provider too.** The duration predictor is
speaker-conditioned: with some references it allots seconds to a short line and
the model fills the slack with speech nobody wrote, loud enough to survive the
WAV repair. `pacing.py` therefore splits the text at sentence ends itself, sends
each chunk with server chunking off and a `max_seconds` cap estimated from the
text, and joins the renders with a short pause. The cap is a ceiling, lifted by
a `caption` (direction may slow the take on purpose). `pacing: false` restores
the single request with the server's own chunking.

The lexicon is `{"terms": {surface: reading}}`. A Latin key is matched only where
no ASCII letter or digit touches it: it fires in `GitHubに` but not inside
`GitHubActions`.

To measure readings, run `scripts/irodori_tts_reading_check.py` against the live
server (it shares the server with Hermes, so schedule it). It scores kana
character error rate through the real cleaner and `reading.py`. The score sees
readings, not phrasing: confirm findings by ear before adding a lexicon entry. A
corpus of private names belongs in the private overlay, not the tracked corpus.

### Qwen3-TTS voice catalog

The `tts/qwen3-tts` plugin sends JSON speech requests to its loopback server;
the plugin applies `tts.speed` and output encoding with `ffmpeg`.

The server keeps one catalog-selected Base model resident on Apple MPS with BF16
and shares it across all registered voices. FP16 is intentionally not used: the
Base ICL path can overflow in its code predictor on MPS. Every registered
manifest must pin the same model and exact Hugging Face commit; the server loads
that local snapshot so processor/tokenizer lookups cannot drift to `main`.

Voice-specific settings live in the private character library, not in this
public repo: `characters sync` copies a character's reference files into a
content-addressed bundle under the ignored `local/qwen3-tts/manifests/`,
generates the voice manifest there and registers it. A manifest pins the voice
id, language, model revision, generation seed and both reference SHA-256 digests;
a manifest location is supplied only during machine-local registration. The
reference transcript and audio drive in-context cloning, which carries the
reference's prosody into synthesis — an expressive, natural reference is the
primary lever for intonation.

An optional `pronunciation.lexicon` (`path` + `sha256`) maps surface forms to
readings, applied longest surface first before synthesis; use it for words the
model misreads, not to rewrite sentences into kana. Long input is split into
sentence-aligned chunks, each generated with the manifest seed re-applied and
joined with a short gap, which stabilizes intonation and avoids Japanese
end-of-text truncation. `hermes/scripts/qwen3_tts_reading_check.py` finds
misreadings; confirm by ear before adding a lexicon entry and re-running
`install`.

Additional characters register by manifest without adding ports, providers or
LaunchAgents: `hermes/launchd/qwen3-tts-launchctl.sh` takes `install` /
`register --voice-manifest <abs path> [--default]` / `unregister --voice <id>` /
`voices` / `status` / `uninstall`. Validate a new manifest first with
`python3 hermes/scripts/qwen3_tts_server.py check-manifest <path>`.

`install` creates an isolated venv under the ignored `hermes/local/qwen3-tts/`,
stores absolute private manifest locations only in the ignored `catalog.json`,
synchronizes the hash-locked `engines/qwen3-tts/requirements.lock`, validates
every manifest, renders the LaunchAgent and atomically activates the catalog. A
failed registration, service load or identity-bound health check restores the
previous catalog and service. The tracked plist contains only the stable ignored
catalog path. `uninstall` keeps the catalog, venv and model cache. Dependencies
stay hash-locked: `requirements.in` is the top level and
`tested-constraints.txt` the verified environment; review before recompiling.

### Irodori voice registration

Irodori takes a reference WAV rather than a manifest, and its catalog is a
directory the server reads at startup — so `register` and `unregister` restart
the agent for you (`--no-restart` defers it to one `restart`). Character voices
are registered by `characters sync`, which calls these commands from the
library's declarations; use them directly only for non-character voices.
`unregister` refuses the default voice. Reference audio and the lexicon are
private data: both are copied into the ignored runtime directory, and neither
source path may reach tracked config.

A voice may take several clips of the same speaker, used as one longer reference
(the checkpoint was trained on concatenated short clips, so it clones more
steadily than from one). Repeat `--voice` in reading order; clips are copied to
`voices/<id>/01.wav`, `02.wav`, … and grouped in `voices/voices.json`, which the
launcher regenerates on every `register` and `unregister`, so a hand-written
alias there is overwritten. A group costs synthesis time (every clip is
re-encoded per request).

`hermes/launchd/irodori-tts-launchctl.sh` takes `install --voice <wav> --id <id>`
/ `register --voice <wav>… --id <id> [--default]` / `unregister --id <id>` /
`register-lexicon --file <json>` / `restart` / `voices` / `status` /
`uninstall` (stop) / `purge` (also deletes the runtime dir).

`install` builds a git checkout of the upstream server plus a uv venv under the
ignored `local/irodori-tts/`; the launcher's explicit uv `--python` is
mandatory, since uv otherwise picks 3.12 and the pinned `sentencepiece` has no
wheel for it. The pins file is named `.conf` because `**/*.env` is ignored and
the pins must be tracked. `register-lexicon` validates the JSON and refuses to
write through a symlink — that is how the private overlay owns the file. The
plugin caches the lexicon per process, so a live gateway needs a restart.
