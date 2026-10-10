# Audio tooling

The speech-to-text fallback chain and the maintainer commands for the audio
hands (SFX helper, mix fixture, local Stable Audio 3 Medium runtime). Read it
when changing STT providers or running audio-leaf helpers by hand.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Speech-to-text — fallback chain

STT for `default` / `assistant` runs through the `transcription/stt-fallback`
plugin (`stt.provider: stt-fallback`). It tries the tiers in `stt.fallback.chain`
(in `config.yaml`; that key is the only copy of the order) and returns the first
successful, non-empty transcript — outage fallback, not quality fallback.

- Tiers whose credentials are missing are skipped at runtime, so reorder, add
  or remove tiers by editing `stt.fallback.chain`; credentials come from the
  Keychain (see [`models-auth.md`](../models-auth.md)). `xai` can also use the
  SuperGrok OAuth login (`hermes auth add xai-oauth`).
- `local` (faster-whisper; `stt.local.*`) needs no key and is the offline floor;
  an empty `stt.local.language` auto-detects.
- `mistral` is excluded by default: its SDK was quarantined on PyPI.

STT serves the gateway (voice input) and CLI voice mode.

## Audio hands tooling

Contracts for every audio leaf: [docs/hands/audio.md](../hands/audio.md). This
section only holds the maintainer commands. Run leaf helpers with Hermes' Python
through `hermes-python`.

**SFX helper.** From the `hermes/` directory, with an existing output parent and
a new output directory:

```sh
hermes-python \
  profiles/audio-creator/skills/audio-creator-pipeline/scripts/sfx-media.py \
  synth --kind whoosh --seconds 0.5 --pitch 880 --seed 0 \
  --out /tmp/sfx-example --slug whoosh
```

The output directory must be new. `track`, `edit` and `analyze` document their
flags via `--help`; no command installs an engine or overwrites media.

**Mix/video integration fixture** (synthetic tones, not real speech or client
approval), from the `hermes/` directory with a fresh absolute output path:

```sh
hermes-python \
  scripts/tests/fixtures/mix-video/example.py \
  --root <new-absolute-test-directory> --freeze
```

It freezes real Mix/Ad/Tour bundles; each video leaf's snapshot/render helper
then verifies its exact test preview hashes. It proves wiring only.

Motion Canvas and Three WebGL runtimes are maintainer-provisioned from
`engines/motion-canvas/setup.mjs` / `engines/three-webgl/setup.mjs`; see
[docs/hands/video.md](../hands/video.md).

### Local Stable Audio 3 Medium runtime

`scripts/stable_audio3.py` is shared by SFX and music; pins live in
`engines/stable-audio-3/` and the install under the ignored
`local/stable-audio-3/`:

```sh
python3 hermes/scripts/stable_audio3.py install --accept-terms   # maintainer-only, once
python3 hermes/scripts/stable_audio3.py check [--full]           # readiness / drift
python3 hermes/scripts/stable_audio3.py refresh \
  --previous-adapter /absolute/path/to/previous-stable_audio3.py
```

Jobs never install or download anything. After a maintainer-only adapter
change, `refresh` verifies the old adapter fingerprint and the complete existing
installation offline before refreshing its marker. It never downloads models,
reinstalls packages, accepts new terms, or rewrites old job receipts. Drift
semantics: [docs/hands/audio.md](../hands/audio.md) "Local Stable Audio 3
Medium runtime".
