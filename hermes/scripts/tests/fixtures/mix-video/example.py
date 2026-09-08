#!/usr/bin/env python3
"""TEST FIXTURE ONLY - Ad + Tour local Mix consumption evidence.

Builds, under a fresh `--root`, two illustrative deliverables that opt into
Audio Mix's `audio_workflow: mix` (see hermes/AGENTS.md "audio_workflow"):

  ad/    the existing create-ad fixture (fixtures/create-ad/example.py, 15s)
  tour/  the existing authored-tour fixture, variant "none"
         (fixtures/authored-tour/example.py, 8s)

plus TWO genuine Mix bundles (one per duration), built exclusively through
Audio Mix's OWN `propose()`/`render()`/`verify_bundle()` in mix-media.py -
never hand-faked receipts. Every source (music bed, speech test tone, sfx
chirp) is a locally generated analytic waveform (numpy/wave only, never a
model). The Mix approval here is AUTOMATED-TEST consent only: this script
itself computes the proposal's SHA-256 and immediately renders against it,
which is never a stand-in for real client approval (see TEST_FIXTURE.md,
written into the produced root).

Only the STAGED subset (master/receipt/captions/timing) is copied into each
deliverable's assets, exactly what create-ad/create-tour's own opt-in mix
staging does - never the physical bundle. Caption text is the literal marker
"Mix test caption" throughout; the speech source is a synthetic sine test
tone, and its `.words.json` timeline is a hand-authored fixture at 1..2s,
never a transcription or ASR/perceptual proof of anything.

Usage:
    python3 example.py --root /absolute/new/path
    python3 example.py --root /absolute/new/path --freeze

`--freeze` additionally calls Ad/Tour's own `ad.freeze`/`authored.freeze`
against the produced plan/form with their EXACT current sha256 - this is a
real freeze call (proves markup/asset/mix validation actually passes), not a
user-approval bypass. It never calls snapshot/render (no hyperframes CLI is
required); an actual local snapshot/render pass belongs to a later verifier
step, not this fixture builder.
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import wave
from html import escape
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
HERMES = HERE.parents[3]
VIDEO_PIPELINE = HERMES / "profiles/video-creator/skills/video-creator-pipeline"
AD_LEAF = VIDEO_PIPELINE / "create/ad"
TOUR_LEAF = VIDEO_PIPELINE / "create/tour"
AUDIO_MIX_SCRIPTS = HERMES / "profiles/audio-creator/skills/audio-creator-pipeline/scripts"

RATE = 48000
CAPTION_TEXT = "Mix test caption"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mix_media = _load("mix_video_fixture_mix_media", AUDIO_MIX_SCRIPTS / "mix-media.py")
mix_audio = _load("mix_video_fixture_mix_audio", VIDEO_PIPELINE / "scripts/mix_audio.py")
ad = _load("mix_video_fixture_ad_render", AD_LEAF / "scripts/ad-render.py")
authored = _load("mix_video_fixture_authored", TOUR_LEAF / "scripts/authored.py")
ad_example = _load("mix_video_fixture_ad_example", HERE.parent / "create-ad/example.py")
tour_example = _load("mix_video_fixture_tour_example", HERE.parent / "authored-tour/example.py")


def require(ok, message):
    if not ok:
        raise ValueError(message)


# ── locally generated analytic waveforms (numpy/wave only, never a model) ───

def write_wav(path, samples):
    """samples: float array in [-1, 1], shape (n,) or (n, channels)."""
    if samples.ndim == 1:
        samples = samples[:, None]
    pcm16 = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(pcm16.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm16.tobytes())


def make_music_bed(path, seconds, amplitude=0.12):
    """Modest stereo bed: two fixed sine tones, purely analytic - no model."""
    n = round(seconds * RATE)
    t = np.arange(n) / RATE
    left = amplitude * np.sin(2 * np.pi * 110.0 * t)
    right = amplitude * np.sin(2 * np.pi * 165.0 * t)
    write_wav(path, np.stack([left, right], axis=1))


def make_speech_tone(path, seconds, amplitude=0.09):
    """A quiet mono sine tone standing in for speech - never real speech,
    never ASR/perceptual proof of anything."""
    n = round(seconds * RATE)
    t = np.arange(n) / RATE
    write_wav(path, amplitude * np.sin(2 * np.pi * 220.0 * t))


def make_sfx_chirp(path, seconds=0.28, amplitude=0.3, f0=900.0, f1=2400.0):
    """A short synthetic linear frequency sweep with a 10ms in/out fade to
    avoid a click at the file boundaries."""
    n = round(seconds * RATE)
    t = np.arange(n) / RATE
    k = (f1 - f0) / seconds
    phase = 2 * np.pi * (f0 * t + 0.5 * k * t * t)
    fade = np.minimum(1.0, np.minimum(t / 0.01, (seconds - t) / 0.01))
    write_wav(path, amplitude * np.sin(phase) * np.clip(fade, 0, 1))


def words_sidecar(wav_path, out_path):
    """A true hash-valid `.words.json` sidecar (see `validate_words` in
    mix-media.py): the PCM hash is computed with the exact same ffmpeg
    decode used internally, over a hand-authored 1..2s test timeline -
    never a transcription."""
    raw = wav_path.read_bytes()
    _, native = mix_media.media.decode(wav_path, raw)
    pcm = mix_media.media.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file",
         "-f", native["container"], "-i", str(wav_path), "-map", "0:a:0", "-ar", str(RATE),
         "-ac", "1", "-t", "600.01", "-f", "s16le", "pipe:1"]).stdout
    words = [{"word": "Mix", "start": 1.0, "end": 1.3},
             {"word": "test", "start": 1.3, "end": 1.6},
             {"word": "caption", "start": 1.6, "end": 2.0}]
    doc = {"file": wav_path.name, "duration": native["decoded_duration_seconds"],
           "pcm_sha256": hashlib.sha256(pcm).hexdigest(), "words": words,
           "captions": [{"start": 1.0, "end": 2.0, "text": CAPTION_TEXT}],
           "segments": [{"start": 1.0, "end": 2.0, "text": CAPTION_TEXT}],
           "provenance": "TEST FIXTURE ONLY: synthetic sine test tone, hand-authored fixture "
                         "timeline, never ASR or real speech/perceptual proof of anything."}
    out_path.write_text(json.dumps(doc), encoding="utf-8")


# ── one genuine Mix proposal/approved render bundle, per target duration ────

def build_mix(build_dir, duration, slug):
    """Build a real Mix bundle by calling Audio Mix's own `propose()`/
    `render()`/`verify_bundle()` directly - never a hand-typed take.json.
    `duration` is the exact target video's total length (8 for tour, 15 for
    ad); the cue timing (voice 1..4s, sfx 4..4.25s, bed spanning the whole
    clip) is identical between the two, only the bed/envelope tail differs
    with the total duration."""
    build_dir.mkdir(parents=True)
    bed_path = build_dir / "music-bed.wav"
    make_music_bed(bed_path, duration)
    voice_path = build_dir / "voice-test-tone.wav"
    make_speech_tone(voice_path, seconds=3.2)
    sfx_path = build_dir / "sfx-chirp.wav"
    make_sfx_chirp(sfx_path)
    words_path = build_dir / "voice-test-tone.words.json"
    words_sidecar(voice_path, words_path)

    timing_path = build_dir / "timing.json"
    timing_path.write_text(json.dumps({
        "version": 1, "duration_seconds": duration,
        "cues": [
            {"id": "music-bed", "source": "music", "start": 0, "source_start": 0, "duration": duration},
            {"id": "voice", "source": "voice", "start": 1, "source_start": 0, "duration": 3},
            {"id": "sfx-chirp", "source": "sfx", "start": 4, "source_start": 0, "duration": .25},
        ]}), encoding="utf-8")

    spec = {
        "version": 1,
        "what_for": f"AUTOMATED TEST FIXTURE bed for create-{slug}'s local audio_workflow: mix "
                    "consumption; never a client-approved deliverable.",
        "direction": "A modest, locally generated analytic stereo music bed (two fixed sine tones, "
                     "no model) ducking under a quiet synthetic speech test tone, with one short "
                     "synthetic sfx chirp. TEST FIXTURE ONLY.",
        "duration_seconds": duration, "channels": 2, "target_lufs": None, "true_peak_dbtp": -1.0,
        "sources": [
            {"id": "music", "path": str(bed_path), "role": "music"},
            {"id": "voice", "path": str(voice_path), "role": "speech", "words": str(words_path)},
            {"id": "sfx", "path": str(sfx_path), "role": "sfx"},
        ],
        "cues": [
            {"id": "music-bed", "source": "music", "start": 0, "source_start": 0, "duration": duration,
             "gain_db": -16, "fade_in": 0, "fade_out": 0,
             "envelope": [{"at": 0, "gain_db": 0}, {"at": .9, "gain_db": 0}, {"at": 1, "gain_db": -8},
                          {"at": 4, "gain_db": -8}, {"at": 4.2, "gain_db": 0}, {"at": duration, "gain_db": 0}]},
            {"id": "voice", "source": "voice", "start": 1, "source_start": 0, "duration": 3,
             "gain_db": -8, "fade_in": 0, "fade_out": 0, "envelope": []},
            {"id": "sfx-chirp", "source": "sfx", "start": 4, "source_start": 0, "duration": .25,
             "gain_db": -12, "fade_in": 0, "fade_out": 0, "envelope": []},
        ],
        "timing": str(timing_path),
    }
    spec_path = build_dir / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    desc_path = build_dir / "description.md"
    desc_path.write_text(
        "AUTOMATED TEST FIXTURE bed. Built and approved for local automated-test consent ONLY - "
        "this script computes the proposal's own SHA-256 and renders against it immediately; that is "
        "never a stand-in for real client approval. Every source is a locally generated analytic "
        "waveform (numpy/wave, no model): a two-tone stereo bed, a synthetic sine speech test tone "
        f"(never real speech, never ASR), and a short synthetic sfx chirp. Caption text is the "
        f"literal marker '{CAPTION_TEXT}', not a transcription.\n", encoding="utf-8")

    proposed = mix_media.propose(str(spec_path), str(desc_path), str(build_dir / "proposal-v1"))
    rendered = mix_media.render(proposed["approved_plan"], proposed["approval_sha256"], "create",
                                 str(build_dir / "take-01"), slug=f"{slug}-fixture")
    bundle = Path(rendered["out"])
    verified = mix_media.verify_bundle(bundle)
    require(verified["take"]["status"] in ("PASS", "WARN"), f"{slug} Mix fixture failed verification")
    return bundle


# ── staging + splicing into the ad/tour source (mirrors create-ad/create-tour's own opt-in wiring) ──

def stage_mix(bundle_dir, dest_assets_dir):
    """Copy ONLY the staged subset - master, receipt, and captions/timing.json
    when the receipt records them - into `dest_assets_dir`, exactly what
    create-ad/create-tour do after `mix-media.py verify --bundle`. Returns
    the `mix` asset-path object and the loaded receipt."""
    dest_assets_dir.mkdir(parents=True, exist_ok=True)
    take = json.loads((bundle_dir / "mix.take.json").read_text(encoding="utf-8"))
    master_name = take["master"]["file"]
    shutil.copyfile(bundle_dir / master_name, dest_assets_dir / master_name)
    shutil.copyfile(bundle_dir / "mix.take.json", dest_assets_dir / "mix.take.json")
    mix = {"master": f"assets/{master_name}", "receipt": "assets/mix.take.json"}
    files = take.get("files", {})
    if "captions.json" in files:
        shutil.copyfile(bundle_dir / "captions.json", dest_assets_dir / "captions.json")
        mix["captions"] = "assets/captions.json"
    if "timing.json" in files:
        shutil.copyfile(bundle_dir / "timing.json", dest_assets_dir / "timing.json")
        mix["timing"] = "assets/timing.json"
    return mix, take


def splice_root(index_path, snippet):
    """Insert `snippet` just inside the composition root's closing tag - the
    renderer owns clip timing from data-start/data-duration; no JS playback
    is ever added here."""
    html = index_path.read_text(encoding="utf-8")
    marker = "</div>\n<script>"
    require(html.count(marker) == 1, "expected exactly one composition-root close marker")
    index_path.write_text(html.replace(marker, f"{snippet}{marker}", 1), encoding="utf-8")


def wire_ad_mix(ad_root, bundle_dir):
    """Wire the staged Mix delivery into the ad plan/source: master/receipt/
    captions/timing all land in `plan['mix']` and the ordinary hashed asset
    map; captions stay metadata only (no extra copy row - `_mix_check` in
    ad-render.py never validates caption markup, unlike the tour leaf)."""
    mix, take = stage_mix(bundle_dir, ad_root / "source/assets")
    plan_path = ad_root / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for relpath in mix.values():
        plan["assets"][relpath] = ad.digest(ad_root / "source" / relpath)
    plan["mix"] = mix
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    splice_root(ad_root / "source/index.html",
                f'<audio id="mix-master" data-start="0" data-duration="{plan["duration"]}" '
                f'data-track-index="1" src="{mix["master"]}"></audio>')
    return plan, take


def wire_tour_mix(tour_root, bundle_dir, duration):
    """Wire the staged Mix delivery into the tour form/source: same audio
    placement as the ad (start 0, full duration, track-index 1), plus one
    `<div id="mix-caption-N" class="clip" ...>` per caption entry - required
    by `mix_check`'s `check_caption_markup`. White text on a dark box for
    contrast, clear of the fixture's permanent disclosure text."""
    mix, take = stage_mix(bundle_dir, tour_root / "source/assets")
    form_path = tour_root / "form.json"
    form = json.loads(form_path.read_text(encoding="utf-8"))
    form["audio_workflow"] = "mix"
    form["mix"] = mix
    form_path.write_text(json.dumps(form), encoding="utf-8")
    splice_root(tour_root / "source/index.html",
                f'<audio id="mix-master" data-start="0" data-duration="{duration}" '
                f'data-track-index="1" src="{mix["master"]}"></audio>')
    captions = json.loads((bundle_dir / "captions.json").read_text(encoding="utf-8"))["captions"]
    divs = "".join(
        f'<div id="mix-caption-{i}" class="clip" data-start="{c["start"]}" '
        f'data-duration="{c["end"] - c["start"]}" data-track-index="{i + 1}" '
        'style="position:absolute;bottom:60px;left:24px;'
        'background:rgba(0,0,0,.75);color:#fff;padding:8px 16px;border-radius:6px;'
        f'font-family:sans-serif;font-size:24px;">{escape(c["text"])}</div>'
        for i, c in enumerate(captions, 1))
    splice_root(tour_root / "source/index.html", divs)
    return form, take, captions


def inject_caption_sample(contract, captions):
    """Add one contract sample landing inside the (first) caption's on-screen
    window, for visible verification that the caption is actually up when
    the mix says it should be."""
    if not captions:
        return contract
    cue = captions[0]
    at = round((cue["start"] + cue["end"]) / 2, 6)
    samples = sorted(contract["samples"] + [{
        "at": at, "expect": f"Mix caption visible mid-span: {cue['text']!r} "
                             "(TEST FIXTURE synthetic tone; not ASR/perceptual proof)"}],
        key=lambda s: s["at"])
    for i in range(1, len(samples)):
        if samples[i]["at"] <= samples[i - 1]["at"]:
            samples[i] = {**samples[i], "at": samples[i - 1]["at"] + 1 / 30}
    return {**contract, "samples": samples}


# ── top-level fixture ────────────────────────────────────────────────────────

def fixture(root):
    root = Path(root).expanduser().resolve()
    require(root.parent.is_dir(), "root: needs an existing absolute parent directory")
    require(not root.exists(), "root: must not already exist; this fixture never overwrites")
    root.mkdir()

    (root / "TEST_FIXTURE.md").write_text(
        "# TEST FIXTURE ONLY\n\n"
        "Everything under this directory is synthetic, locally generated AUTOMATED-TEST evidence for "
        "the Audio Mix + create-ad/create-tour `audio_workflow: mix` integration. None of it is a "
        "client-approved deliverable.\n\n"
        "- Music bed: two fixed-frequency analytic sine tones (numpy/wave only - never a model).\n"
        "- Speech: a single quiet synthetic sine test tone, never real speech and never ASR output. "
        "Its `.words.json` timeline (1..2s) is a hand-authored fixture, not a transcription.\n"
        "- SFX: a short synthetic frequency chirp.\n"
        f"- Caption text is the literal marker '{CAPTION_TEXT}' throughout.\n"
        "- Mix approval here is AUTOMATED-TEST consent only: this script computes the exact proposal "
        "SHA-256 and immediately renders against it - never a stand-in for real client approval.\n",
        encoding="utf-8")

    ad_root = root / "ad"
    ad_example.fixture(ad_root)
    ad_duration = ad_example.DURATION

    tour_root = root / "tour"
    tour_example.fixture(tour_root, "none")
    # The inherited UI hides its panel behind a modal. Hide the occluded
    # panel explicitly in this fixture too, so contrast checks never measure
    # its light text against the modal's white background through an overlay.
    index = tour_root / "source/index.html"
    html = index.read_text(encoding="utf-8")
    html = html.replace("pose('#modal',{opacity:1,scale:.94,y:12},9);",
                        "pose('#panel',{opacity:0},9);pose('#modal',{opacity:1,scale:.94,y:12},9);")
    html = html.replace("pose('#modal',{opacity:0},14.5);",
                        "pose('#modal',{opacity:0},14.5);pose('#panel',{opacity:1},14.5);")
    index.write_text(html, encoding="utf-8")
    tour_duration = json.loads((tour_root / "form.json").read_text(encoding="utf-8"))["duration"]

    ad_bundle = build_mix(root / "mix-bundles/ad", ad_duration, "ad")
    tour_bundle = build_mix(root / "mix-bundles/tour", tour_duration, "tour")

    ad_plan, ad_take = wire_ad_mix(ad_root, ad_bundle)
    tour_form, tour_take, captions = wire_tour_mix(tour_root, tour_bundle, tour_duration)

    contract_path = tour_root / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract_path.write_text(json.dumps(inject_caption_sample(contract, captions)), encoding="utf-8")

    return {
        "root": str(root),
        "test_fixture_notice": str(root / "TEST_FIXTURE.md"),
        "ad": {"source": str(ad_root / "source"), "plan": str(ad_root / "plan.json"),
               "duration": ad_duration, "mix_bundle": str(ad_bundle),
               "mix_master_sha256": ad_take["master"]["sha256"]},
        "tour": {"source": str(tour_root / "source"), "form": str(tour_root / "form.json"),
                 "contract": str(contract_path), "duration": tour_duration,
                 "mix_bundle": str(tour_bundle), "mix_master_sha256": tour_take["master"]["sha256"]},
    }


def freeze_all(root, summary):
    """AUTOMATED-TEST-ONLY freeze: calls Ad/Tour's own `ad.freeze`/
    `authored.freeze` against the produced plan/form with their exact
    current sha256 - a real freeze call (proves the markup/asset/mix
    validation actually passes), never a user-approval bypass. Never calls
    snapshot/render; no hyperframes CLI is required here."""
    root = Path(root)
    ad_root = root / "ad"
    ad_plan_path = ad_root / "plan.json"
    ad_project = ad.freeze(SimpleNamespace(
        source=str(ad_root / "source"), plan=str(ad_plan_path),
        approval_sha256=ad.digest(ad_plan_path), project=str(ad_root / "project")))
    tour_root = root / "tour"
    tour_project = authored.freeze(SimpleNamespace(
        form=str(tour_root / "form.json"), contract=str(tour_root / "contract.json"),
        source=str(tour_root / "source"), project=str(tour_root / "project")))
    summary["ad"]["project"] = ad_project
    summary["tour"]["project"] = tour_project
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, help="new, non-existent absolute directory to build under")
    parser.add_argument("--freeze", action="store_true",
                         help="AUTOMATED-TEST consent to additionally run ad.freeze/authored.freeze on the "
                              "produced fixture with exact hashes; never a client approval; no "
                              "snapshot/render is run")
    args = parser.parse_args()
    summary = fixture(args.root)
    if args.freeze:
        # `fixture()` resolves --root (e.g. macOS /var -> /private/var); reuse
        # that resolved path so `local()`'s symlink guard never sees a raw
        # symlinked ancestor.
        summary = freeze_all(summary["root"], summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
