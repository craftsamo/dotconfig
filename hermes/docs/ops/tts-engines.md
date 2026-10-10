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
English — so it _declines_ English-dominant text (too small a share of
kana/kanji, `tts.irodori_tts.min_japanese_ratio`) by raising, and the chain
advances to Qwen3. No routing layer exists and none should be added. The
hand-off is per utterance on purpose: the same reference voice sounds audibly
different on the two engines, so splicing them inside one sentence is audible.
When a server is unavailable or still loading, `tts-fallback` advances to the
next tier and finally to Edge TTS; the call only errors if every tier fails.
Normal speech omits a voice ID and uses each engine's default. For a pinned,
named voice (no routing, no substitution), see
[docs/hands/audio.md](../hands/audio.md) "Character voices and performance
direction".

Auto-speech (`voice.auto_tts: true`) is voice-in → voice-out in the gateway and
TTS-on-by-default inside CLI voice mode — it never auto-speaks plain text
turns. After changing a live config, restart the relevant Hermes process (e.g.
the gateway).

**Voice data never enters this repo.** Reference audio lives in the private
character tree and is copied into the ignored `local/<engine>/` by the
launchers; the Irodori pronunciation lexicon (`local/irodori-tts/lexicon.json`)
is a symlink the private overlay installs. Do not add a local-engine voice
(`voice:`) key under `tts.*` and do not name a lexicon or manifest path in
`config.yaml` — both are tracked. Private voice and lexicon paths go through the launchers' `register*`
commands only.

**Irodori** runs fp32 on MPS (bf16 is CUDA/XPU-only upstream) from a git
checkout pinned in `engines/irodori-tts/pinned.conf`, which also records the
checkpoint's memory, speed and licence. The checkpoint renders slower than real
time, so a long reply can spend the whole `tts.irodori_tts.synthesis_timeout`
on Irodori before the chain falls through to Qwen3. The provider then repairs
its own WAV before delivery: the in-pause codec rustle is gated, leading dead
air and trailing hallucinated fragments are trimmed, the onset click is faded
and the level is normalised. That repair uses numpy and the stdlib only,
because Hermes' dependency generation carries no soundfile or scipy.

**Irodori readings are fixed in the provider, not left to the model.** The
checkpoint has no reading frontend (the server only applies NFKC and deletes
some symbols, including every hyphen, so `-5` arrives as `5`), and the shared
Hermes cleaner, written for English voices, has already turned `25°C` into
`25 degrees Celsius` and `10~20` into `10 about 20`. The plugin's `reading.py`
therefore applies the private lexicon to the text as written, maps that English
back to Japanese, spells out symbols (ranges, minus signs, times, dates, `¥`,
`→`) and rewrites only the number forms the model misreads: digit grouping, `%`
and Latin units; phone numbers and versions are read digit by digit in kana.
It is not kana throughout, because a long kana run loses its word boundaries
and the model phrases it wrongly. `tts.irodori_tts.numerals` picks the numeral
style; `reading_frontend: false` switches the rewriting off and keeps the
lexicon. The shared cleaner itself stays untouched (see
[`AGENTS.md`](../../AGENTS.md)); a line the cleaner closes with an extra `.`
after `？`/`！`/`。` loses that stop here, since the model reads it as a second,
falling sentence end.

**Irodori pacing is set in the provider too.** The duration predictor is
speaker-conditioned: with some references it allots several seconds to any
short line, and the model fills the slack with speech nobody wrote — the line
again, or fragments before or after it — loud enough to survive the WAV repair.
The plugin's `pacing.py` therefore splits the text at sentence ends itself,
sends each chunk with server chunking off and a `max_seconds` cap estimated
from the text, and joins the renders with a short pause. The cap is a ceiling:
longer text is predicted correctly and keeps its own length. A `caption` lifts
the cap (direction may slow the take on purpose) and an emoji adds time for its
performance. `tts.irodori_tts.pacing: false` restores the single request with
the server's own chunking.

The lexicon is `{"terms": {surface: reading}}`. Keys may be Latin (`GitHub`) or
kanji; a Latin key is matched only where no ASCII letter or digit touches it, so
it fires in `GitHubに` but not inside `GitHubActions`.

To measure readings, run `scripts/irodori_tts_reading_check.py` (flags:
`--help`; tracked corpus: `scripts/irodori_tts_reading_corpus.tsv`) against the
live server. It sends each sentence through the real cleaner and `reading.py`,
transcribes the provider-repaired audio with a kana-writing Whisper (so a
misread kanji cannot hide behind the right spelling) and reports a kana
character error rate per category; it can also track the pitch rise of
questions. The score sees readings, not phrasing: a reading can be right while
the pauses fall inside a word, so listen to a sample before changing how text
is spelled. Findings are candidates: confirm by ear (`--keep-audio DIR`,
re-score with `--from-audio DIR`) before adding a lexicon entry. A corpus of
private names belongs in the private overlay, not in the tracked corpus. A full
run shares the server with Hermes, so schedule it accordingly.

### Qwen3-TTS voice catalog

The `tts/qwen3-tts` plugin sends JSON speech requests to its loopback server;
the plugin applies `tts.speed` and output encoding with `ffmpeg`, then the
gateway handles its normal Opus delivery.

The server keeps one catalog-selected Base model resident on Apple MPS with BF16
and shares it across all registered voices. Voice-clone prompts are built lazily
and retained in a bounded LRU cache. FP16 is intentionally not used: the Base
ICL path can overflow in its code predictor on MPS. Every registered manifest
must pin the same model and exact Hugging Face commit; the server loads that
local snapshot so processor/tokenizer lookups cannot drift to `main`.

Voice-specific settings live in the private character library, not in this
public repo: `characters sync` copies a character's reference files into a
content-addressed bundle under the ignored `local/qwen3-tts/manifests/`,
generates the voice manifest there and registers it. A manifest location
(`/absolute/path/to/voice.json`) is supplied only during machine-local
registration. Each manifest contains the voice id, language, model revision,
generation seed, and paths to the approved reference audio/transcript; it pins
both reference SHA-256 digests and the PCM WAV metadata. Relative reference
paths resolve against the manifest. The reference transcript and audio drive
in-context cloning, which carries the reference's prosody into synthesis — an
expressive, natural reference is the primary lever for output intonation.

A manifest may add an optional `pronunciation.lexicon` entry (`path` +
`sha256`) pointing to a JSON object of surface-form → reading substitutions.
The server applies the lexicon (longest surface first) after whitespace
normalization and before synthesis; use it to pin down words the model
misreads, not to rewrite whole sentences into kana. Long inputs are split into
sentence-aligned chunks (clause fallback), each chunk is generated with the
manifest seed re-applied, and the chunks are joined with a short gap — this
stabilizes intonation and avoids Japanese end-of-text truncation.

The first install registers the default voice. Additional characters are
registered by manifest without adding ports, providers, or LaunchAgents:

```sh
hermes/launchd/qwen3-tts-launchctl.sh install \
  --voice-manifest /absolute/path/to/voice.json
hermes/launchd/qwen3-tts-launchctl.sh register \
  --voice-manifest /absolute/path/to/another-voice.json [--default]
hermes/launchd/qwen3-tts-launchctl.sh unregister --voice another-voice
hermes/launchd/qwen3-tts-launchctl.sh voices
hermes/launchd/qwen3-tts-launchctl.sh install  # reuses the local catalog
hermes/launchd/qwen3-tts-launchctl.sh status
hermes/launchd/qwen3-tts-launchctl.sh uninstall
```

Validate a new manifest standalone before registering:
`python3 hermes/scripts/qwen3_tts_server.py check-manifest /path/to/voice.json`.
To find misreadings, run `hermes/scripts/qwen3_tts_reading_check.py --text "…"`
(or `--file corpus.txt`) against the live server: it synthesizes, transcribes
with faster-whisper, compares readings in kana and prints paste-ready lexicon
candidates. Findings are candidates, not verdicts — confirm by ear
(`--keep-audio DIR` keeps the wavs) before adding a lexicon entry and
re-running `install`. It resolves its own dependencies through `uv run`; the
server venv stays untouched.

`install` creates an isolated Python venv under the ignored
`hermes/local/qwen3-tts/`, stores absolute private manifest locations only in
the ignored `catalog.json`, synchronizes the hash-locked
`engines/qwen3-tts/requirements.lock`, validates every manifest, renders the
LaunchAgent, and atomically activates the catalog. A failed registration,
service load, or identity-bound health check restores the previous catalog and
service. The tracked plist contains only the stable ignored catalog path. Model
weights are cached below the same ignored directory; a first start can take
several minutes. Logs land in `~/Library/Logs/qwen3-tts-engine.log`.
`uninstall` removes the LaunchAgent but retains the catalog, venv, and model
cache.

`engines/qwen3-tts/requirements.in` records the top-level package, while
`engines/qwen3-tts/tested-constraints.txt` captures the verified environment
used to regenerate the hashed lock. Dependencies must stay hash-locked; review
changes before recompiling.

### Irodori voice registration

Irodori takes a reference WAV rather than a manifest, and its catalog is a
directory the server reads at startup — so `register` and `unregister` restart
the agent for you (`--no-restart` defers that to one `restart`). Character
voices are registered by `characters sync`, which calls these commands from the
library's declarations; use them directly only for non-character voices.
`unregister` refuses the default voice. Reference audio and the pronunciation
lexicon are private data: both are copied into the ignored runtime directory,
and neither source path may reach tracked config.

A voice may take several clips of the same speaker, which the checkpoint uses as
one longer reference (it was trained on concatenated short clips, so a longer
reference clones more steadily than one short clip). Repeat `--voice` in the
order the clips should be read: they are copied to `voices/<id>/01.wav`,
`02.wav`, … and grouped under `<id>` in `voices/voices.json`, which the launcher
owns: it regenerates the file from those directories on every `register` and
`unregister`, so a hand-written alias there is overwritten. A group costs
synthesis time, because the server re-encodes every clip on each request.

```sh
hermes/launchd/irodori-tts-launchctl.sh install \
  --voice /absolute/path/to/reference.wav --id <voice-id>
hermes/launchd/irodori-tts-launchctl.sh register \
  --voice /absolute/path/to/another.wav --id <voice-id> --default
hermes/launchd/irodori-tts-launchctl.sh register \
  --voice /abs/clip-1.wav --voice /abs/clip-2.wav --id <voice-id>
hermes/launchd/irodori-tts-launchctl.sh unregister --id <voice-id>
hermes/launchd/irodori-tts-launchctl.sh restart
hermes/launchd/irodori-tts-launchctl.sh register-lexicon \
  --file /absolute/path/to/lexicon.json
hermes/launchd/irodori-tts-launchctl.sh voices
hermes/launchd/irodori-tts-launchctl.sh status
hermes/launchd/irodori-tts-launchctl.sh uninstall   # stop (plist KeepAlive)
hermes/launchd/irodori-tts-launchctl.sh purge       # + delete the runtime dir
```

`install` builds a git checkout of the upstream server plus a uv venv under the
ignored `local/irodori-tts/`; the launcher's explicit uv `--python` is
mandatory, since uv otherwise picks 3.12 and the pinned `sentencepiece` has no
wheel for it. The pins file is named `.conf` because `**/*.env` is ignored and
the pins must be tracked. `register-lexicon` validates the JSON before
installing it, and refuses to write through a symlink — that is how the private
overlay owns the file. The plugin caches the lexicon per process, so a live
gateway needs a restart.
