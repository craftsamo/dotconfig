from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.request
import wave
from pathlib import Path
from unittest import mock


HERMES_DIR = Path(__file__).resolve().parents[2]
SERVER_PATH = HERMES_DIR / "scripts" / "qwen3_tts_server.py"
READING_CHECK_PATH = HERMES_DIR / "scripts" / "qwen3_tts_reading_check.py"
PLUGIN_PATH = HERMES_DIR / "plugins" / "tts" / "qwen3-tts" / "__init__.py"
LAUNCHCTL_PATH = HERMES_DIR / "launchd" / "qwen3-tts-launchctl.sh"
PLIST_PATH = HERMES_DIR / "launchd" / "local.qwen3-tts.engine.plist.tmpl"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_voice_manifest(
    root: Path,
    voice_id: str = "lethe",
    *,
    model_name: str = "test-model-Base",
    model_revision: str = "a" * 40,
    lexicon: dict[str, str] | None = None,
    lexicon_sha256: str | None = None,
) -> Path:
    manifest_dir = root / "data" / voice_id
    voice_dir = root / "assets" / voice_id / "voice"
    manifest_dir.mkdir(parents=True)
    voice_dir.mkdir(parents=True)
    audio = voice_dir / "reference.wav"
    transcript = voice_dir / "reference.txt"
    with wave.open(str(audio), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\x00\x00" * 240)
    transcript.write_text("おかえりなさい。", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "id": voice_id,
        "display_name": voice_id.title(),
        "language": {"name": "Japanese", "locale": "ja"},
        "model": {"name": model_name, "revision": model_revision},
        "reference": {
            "audio": {
                "path": f"../../assets/{voice_id}/voice/reference.wav",
                "sha256": sha256(audio),
                "format": "wav",
                "sample_rate": 24000,
                "channels": 1,
                "sample_width_bits": 16,
                "frames": 240,
            },
            "text": {
                "path": f"../../assets/{voice_id}/voice/reference.txt",
                "sha256": sha256(transcript),
            },
        },
        "generation": {"seed": 17},
    }
    if lexicon is not None:
        lexicon_path = voice_dir / "lexicon.json"
        lexicon_path.write_text(
            json.dumps(lexicon, ensure_ascii=False), encoding="utf-8"
        )
        payload["pronunciation"] = {
            "lexicon": {
                "path": f"../../assets/{voice_id}/voice/lexicon.json",
                "sha256": lexicon_sha256 or sha256(lexicon_path),
            }
        }
    manifest_path = manifest_dir / "voice.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    return manifest_path


def write_voice_catalog(
    path: Path, manifests: list[Path], default_voice: str = "lethe"
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "default_voice": default_voice,
                "voices": {
                    json.loads(manifest.read_text(encoding="utf-8"))["id"]: str(
                        manifest
                    )
                    for manifest in manifests
                },
            }
        ),
        encoding="utf-8",
    )
    return path


class FakeSynthesizer:
    model_name = "test-model"
    model_revision = "test-revision"
    release_id = "test-release"
    catalog_sha256 = "a" * 64
    default_voice_id = "lethe"
    voices = {
        "lethe": types.SimpleNamespace(
            voice_id="lethe",
            display_name="Lethe",
            language="Japanese",
            locale="ja",
        ),
        "echo": types.SimpleNamespace(
            voice_id="echo",
            display_name="Echo",
            language="Japanese",
            locale="ja",
        ),
    }

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def list_voices(self) -> list[dict[str, str]]:
        return [
            {
                "id": voice.voice_id,
                "display": voice.display_name,
                "language": voice.locale,
            }
            for voice in self.voices.values()
        ]

    def synthesize(self, text: str, voice_id: str) -> bytes:
        self.calls.append((text, voice_id))
        return b"RIFF-test-wave"


class BlockingSynthesizer(FakeSynthesizer):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def synthesize(self, text: str, language: str) -> bytes:
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test did not release synthesizer")
        return super().synthesize(text, language)


class TextPreprocessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("qwen3_tts_preprocess_test", SERVER_PATH)

    def test_normalize_text_collapses_whitespace(self) -> None:
        self.assertEqual(
            self.module.normalize_text("  こんにちは。\n\nお元気？　そう。 "),
            "こんにちは。 お元気？ そう。",
        )

    def test_apply_lexicon_prefers_longest_surface(self) -> None:
        lexicon = {"高": "こう", "高性能": "こうせいのう"}

        self.assertEqual(
            self.module.apply_lexicon("高性能と高。", lexicon),
            "こうせいのうとこう。",
        )

    def test_short_text_stays_a_single_chunk(self) -> None:
        text = "本日は晴天です。気温は二十度まで上がります。"

        self.assertEqual(
            self.module.split_text_into_chunks(text), [text]
        )

    def test_chunks_split_on_sentence_boundaries(self) -> None:
        text = "一文目です。二文目はもう少し長いですね！三文目はどうでしょうか？"

        chunks = self.module.split_text_into_chunks(text, max_chars=16)

        self.assertEqual(
            chunks,
            ["一文目です。", "二文目はもう少し長いですね！", "三文目はどうでしょうか？"],
        )

    def test_terminator_keeps_closing_quote(self) -> None:
        text = "「もう帰るの？」と聞いた。彼は頷いた。"

        chunks = self.module.split_text_into_chunks(text, max_chars=12)

        self.assertEqual(chunks, ["「もう帰るの？」", "と聞いた。彼は頷いた。"])

    def test_overlong_sentence_splits_on_clause_boundaries(self) -> None:
        text = "資料は明日の会議までに、章ごとに分けて、提出してください"

        chunks = self.module.split_text_into_chunks(text, max_chars=20)

        self.assertEqual(
            chunks,
            ["資料は明日の会議までに、章ごとに分けて、", "提出してください"],
        )

    def test_unbreakable_run_is_hard_sliced(self) -> None:
        text = "あ" * 25

        chunks = self.module.split_text_into_chunks(text, max_chars=10)

        self.assertEqual(chunks, ["あ" * 10, "あ" * 10, "あ" * 5])

    def test_parse_lexicon_rejects_non_string_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            self.module.parse_lexicon({"語": 1})
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            self.module.parse_lexicon({"": "よみ"})
        with self.assertRaisesRegex(ValueError, "JSON object"):
            self.module.parse_lexicon(["語"])


class ReadingCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("qwen3_tts_reading_check_test", READING_CHECK_PATH)

    def test_normalize_kana_folds_katakana_and_drops_noise(self) -> None:
        self.assertEqual(
            self.module.normalize_kana("シメキリ、です。12時ダヨー"),
            "しめきりですだよー",
        )

    def test_split_sentences_handles_terminators_and_newlines(self) -> None:
        self.assertEqual(
            self.module.split_sentences("一文目です。二文目！\n三文目"),
            ["一文目です。", "二文目！", "三文目"],
        )

    def test_matching_reading_yields_no_suspects(self) -> None:
        tokens = [("締切", "しめきり"), ("です", "です")]

        suspects, ratio = self.module.find_suspects(tokens, "しめきりです")

        self.assertEqual(suspects, [])
        self.assertEqual(ratio, 1.0)

    def test_replaced_reading_is_reported_with_source_surface(self) -> None:
        tokens = [("締切", "しめきり"), ("は", "は"), ("金曜日", "きんようび")]

        suspects, ratio = self.module.find_suspects(tokens, "しめきつはきんようび")

        self.assertEqual(len(suspects), 1)
        self.assertEqual(suspects[0].surface, "締切")
        self.assertEqual(suspects[0].expected, "しめきり")
        self.assertEqual(suspects[0].heard, "しめきつ")
        self.assertLess(ratio, 1.0)

    def test_dropped_reading_is_reported_as_empty_heard_span(self) -> None:
        tokens = [("重複", "ちょうふく"), ("を", "を"), ("確認", "かくにん")]

        suspects, _ = self.module.find_suspects(tokens, "をかくにん")

        self.assertEqual(len(suspects), 1)
        self.assertEqual(suspects[0].surface, "重複")
        self.assertEqual(suspects[0].expected, "ちょうふく")

    def test_duplicate_findings_are_deduplicated(self) -> None:
        tokens = [
            ("締切", "しめきり"),
            ("と", "と"),
            ("締切", "しめきり"),
        ]

        suspects, _ = self.module.find_suspects(tokens, "しめきつとしめきつ")

        self.assertEqual(
            [(s.surface, s.heard) for s in suspects], [("締切", "しめきつ")]
        )


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("qwen3_tts_manifest_test", SERVER_PATH)

    def test_manifest_resolves_references_relative_to_its_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(root)
            audio = root / "assets" / "lethe" / "voice" / "reference.wav"
            transcript = root / "assets" / "lethe" / "voice" / "reference.txt"

            manifest = self.module.load_voice_manifest(manifest_path)

            self.assertEqual(manifest.voice_id, "lethe")
            self.assertEqual(manifest.language, "Japanese")
            self.assertEqual(manifest.model_name, "test-model-Base")
            self.assertEqual(manifest.reference_audio, audio.resolve())
            self.assertEqual(manifest.reference_text_file, transcript.resolve())

    def test_manifest_rejects_unknown_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "voice.json"
            manifest_path.write_text('{"schema_version": 2}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "schema_version"):
                self.module.load_voice_manifest(manifest_path)

    def test_manifest_loads_optional_lexicon(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(root, lexicon={"重複": "ちょうふく"})

            manifest = self.module.load_voice_manifest(manifest_path)

            expected = root / "assets" / "lethe" / "voice" / "lexicon.json"
            self.assertEqual(manifest.lexicon_file, expected.resolve())
            self.assertEqual(manifest.lexicon_sha256, sha256(expected))

    def test_manifest_without_lexicon_has_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = write_voice_manifest(Path(directory))

            manifest = self.module.load_voice_manifest(manifest_path)

            self.assertIsNone(manifest.lexicon_file)
            self.assertIsNone(manifest.lexicon_sha256)

    def test_manifest_rejects_lexicon_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = write_voice_manifest(
                Path(directory),
                lexicon={"重複": "ちょうふく"},
                lexicon_sha256="0" * 64,
            )

            with self.assertRaisesRegex(ValueError, "lexicon digest mismatch"):
                self.module.load_voice_manifest(manifest_path)

    def test_manifest_rejects_invalid_lexicon_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(root, lexicon={"重複": "ちょうふく"})
            lexicon_path = root / "assets" / "lethe" / "voice" / "lexicon.json"
            lexicon_path.write_text('{"語": 1}', encoding="utf-8")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["pronunciation"]["lexicon"]["sha256"] = sha256(lexicon_path)
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "non-empty strings"):
                self.module.load_voice_manifest(manifest_path)

    def test_manifest_rejects_modified_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(root)
            transcript = root / "assets" / "lethe" / "voice" / "reference.txt"
            transcript.write_text("変更された台本。", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                self.module.load_voice_manifest(manifest_path)

    def test_catalog_loads_multiple_voices_with_one_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            echo = write_voice_manifest(root / "echo", "echo")
            catalog_path = write_voice_catalog(
                root / "catalog.json", [lethe, echo], default_voice="lethe"
            )

            catalog = self.module.load_voice_catalog(catalog_path)

            self.assertEqual(catalog.default_voice_id, "lethe")
            self.assertEqual(list(catalog.voices), ["echo", "lethe"])
            self.assertEqual(len(catalog.catalog_sha256), 64)

    def test_catalog_rejects_mixed_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            echo = write_voice_manifest(
                root / "echo", "echo", model_revision="b" * 40
            )
            catalog_path = write_voice_catalog(root / "catalog.json", [lethe, echo])

            with self.assertRaisesRegex(ValueError, "same model and revision"):
                self.module.load_voice_catalog(catalog_path)

    def test_catalog_rejects_key_that_differs_from_manifest_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_voice_manifest(root / "lethe", "lethe")
            catalog_path = root / "catalog.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "default_voice": "someone-else",
                        "voices": {"someone-else": str(manifest)},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not match manifest id"):
                self.module.load_voice_catalog(catalog_path)

    def test_catalog_register_and_unregister_preserve_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            echo = write_voice_manifest(root / "echo", "echo")
            first_path = root / "first.json"
            second_path = root / "second.json"
            final_path = root / "final.json"

            self.module.write_voice_catalog(
                first_path, register_manifest_path=lethe, set_default=True
            )
            second = self.module.write_voice_catalog(
                second_path,
                base_catalog_path=first_path,
                register_manifest_path=echo,
            )
            final = self.module.write_voice_catalog(
                final_path,
                base_catalog_path=second_path,
                unregister_voice_id="echo",
            )

            self.assertEqual(second.default_voice_id, "lethe")
            self.assertEqual(set(second.voices), {"lethe", "echo"})
            self.assertEqual(set(final.voices), {"lethe"})

    def test_catalog_cannot_unregister_default_voice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            catalog_path = write_voice_catalog(root / "catalog.json", [lethe])

            with self.assertRaisesRegex(ValueError, "default voice"):
                self.module.write_voice_catalog(
                    root / "new.json",
                    base_catalog_path=catalog_path,
                    unregister_voice_id="lethe",
                )

    def test_model_snapshot_uses_exact_revision(self) -> None:
        huggingface_hub = types.ModuleType("huggingface_hub")
        snapshot_download = mock.Mock(return_value="/tmp/exact-snapshot")
        huggingface_hub.snapshot_download = snapshot_download

        with mock.patch.dict(sys.modules, {"huggingface_hub": huggingface_hub}):
            snapshot = self.module.resolve_model_snapshot(
                "Qwen/test-Base", "a" * 40
            )

        snapshot_download.assert_called_once_with(
            repo_id="Qwen/test-Base", revision="a" * 40
        )
        self.assertEqual(snapshot, Path("/tmp/exact-snapshot").resolve())


class SynthesizerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("qwen3_tts_synthesizer_test", SERVER_PATH)

    def build_synthesizer(self, catalog, prompt_cache_size: int = 1):
        fake_model = mock.Mock()
        fake_model.get_supported_languages.return_value = ["Japanese"]
        fake_model.create_voice_clone_prompt.side_effect = lambda **kwargs: kwargs[
            "ref_audio"
        ]
        model_class = mock.Mock()
        model_class.from_pretrained.return_value = fake_model
        torch = types.ModuleType("torch")
        torch.bfloat16 = object()
        torch.float16 = object()
        torch.float32 = object()
        torch.manual_seed = mock.Mock()
        qwen_tts = types.ModuleType("qwen_tts")
        qwen_tts.Qwen3TTSModel = model_class

        with mock.patch.dict(
            sys.modules, {"torch": torch, "qwen_tts": qwen_tts}
        ), mock.patch.object(
            self.module,
            "resolve_model_snapshot",
            return_value=Path("/tmp/model"),
        ):
            synthesizer = self.module.QwenSynthesizer(
                catalog=catalog,
                release_id="release",
                device="mps",
                dtype_name="bfloat16",
                prompt_cache_size=prompt_cache_size,
            )
        self.addCleanup(synthesizer.close)
        return synthesizer, model_class, fake_model

    def test_model_is_shared_and_prompt_cache_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            echo = write_voice_manifest(root / "echo", "echo")
            catalog = self.module.load_voice_catalog(
                write_voice_catalog(root / "catalog.json", [lethe, echo])
            )
            synthesizer, model_class, fake_model = self.build_synthesizer(catalog)
            synthesizer._voice_prompt("lethe")
            synthesizer._voice_prompt("echo")
            synthesizer._voice_prompt("lethe")

            model_class.from_pretrained.assert_called_once()
            self.assertEqual(fake_model.create_voice_clone_prompt.call_count, 3)
            self.assertEqual(list(synthesizer._voice_prompts), ["lethe"])

    def test_prompt_creation_rejects_reference_mutated_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(root / "lethe", "lethe")
            catalog = self.module.load_voice_catalog(
                write_voice_catalog(root / "catalog.json", [manifest_path])
            )
            synthesizer, _, fake_model = self.build_synthesizer(catalog)
            catalog.voices["lethe"].reference_text_file.write_text(
                "変更された参照文。", encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "text digest mismatch"):
                synthesizer._voice_prompt("lethe")

            fake_model.create_voice_clone_prompt.assert_not_called()

    def test_preprocess_applies_lexicon_and_chunking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(
                root / "lethe", "lethe", lexicon={"重複": "ちょうふく"}
            )
            catalog = self.module.load_voice_catalog(
                write_voice_catalog(root / "catalog.json", [manifest_path])
            )
            synthesizer, _, _ = self.build_synthesizer(catalog)

            chunks = synthesizer.preprocess(
                "重複を\n確認します。以上です。", "lethe"
            )

            self.assertEqual(chunks, ["ちょうふくを 確認します。以上です。"])

    def test_preprocess_rejects_lexicon_mutated_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(
                root / "lethe", "lethe", lexicon={"重複": "ちょうふく"}
            )
            catalog = self.module.load_voice_catalog(
                write_voice_catalog(root / "catalog.json", [manifest_path])
            )
            synthesizer, _, _ = self.build_synthesizer(catalog)
            catalog.voices["lethe"].lexicon_file.write_text(
                '{"重複": "改変"}', encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "lexicon digest mismatch"):
                synthesizer.preprocess("重複を確認します。", "lethe")

    def test_generate_segments_resets_seed_per_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(root / "lethe", "lethe")
            catalog = self.module.load_voice_catalog(
                write_voice_catalog(root / "catalog.json", [manifest_path])
            )
            synthesizer, _, fake_model = self.build_synthesizer(catalog)
            fake_model.generate_voice_clone.return_value = ([[0.0] * 4], 24000)

            segments, sample_rate = synthesizer._generate_segments(
                ["一文目。", "二文目。"], "lethe"
            )

            self.assertEqual(sample_rate, 24000)
            self.assertEqual(len(segments), 2)
            self.assertEqual(fake_model.generate_voice_clone.call_count, 2)
            self.assertEqual(
                [
                    call.kwargs["text"]
                    for call in fake_model.generate_voice_clone.call_args_list
                ],
                ["一文目。", "二文目。"],
            )
            self.assertEqual(synthesizer._torch.manual_seed.call_count, 2)
            synthesizer._torch.manual_seed.assert_called_with(17)

    def test_synthesize_joins_chunks_with_silence_gap(self) -> None:
        try:
            import numpy as np
            import soundfile  # noqa: F401
        except ImportError:
            self.skipTest("numpy/soundfile unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = write_voice_manifest(root / "lethe", "lethe")
            catalog = self.module.load_voice_catalog(
                write_voice_catalog(root / "catalog.json", [manifest_path])
            )
            synthesizer, _, fake_model = self.build_synthesizer(catalog)
            fake_model.generate_voice_clone.return_value = (
                [np.full(2400, 0.5, dtype=np.float32)],
                24000,
            )
            long_text = "。".join(["長めの一文がここに入ります" * 3] * 8) + "。"

            audio = synthesizer.synthesize(long_text, "lethe")

            self.assertGreater(fake_model.generate_voice_clone.call_count, 1)
            chunk_count = fake_model.generate_voice_clone.call_count
            gap_frames = int(24000 * self.module._CHUNK_GAP_SECONDS)
            with wave.open(io.BytesIO(audio), "rb") as result:
                self.assertEqual(result.getframerate(), 24000)
                self.assertEqual(
                    result.getnframes(),
                    2400 * chunk_count + gap_frames * (chunk_count - 1),
                )

    def test_evicted_prompt_reuses_approved_reference_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            echo = write_voice_manifest(root / "echo", "echo")
            catalog = self.module.load_voice_catalog(
                write_voice_catalog(root / "catalog.json", [lethe, echo])
            )
            synthesizer, _, fake_model = self.build_synthesizer(catalog)
            first_prompt = synthesizer._voice_prompt("lethe")
            catalog.voices["lethe"].reference_audio.write_bytes(b"mutated")
            synthesizer._voice_prompt("echo")
            second_prompt = synthesizer._voice_prompt("lethe")

            self.assertEqual(first_prompt, second_prompt)
            self.assertEqual(fake_model.create_voice_clone_prompt.call_count, 3)


class LaunchctlScriptTest(unittest.TestCase):
    def test_release_identity_includes_schema_and_python_version(self) -> None:
        script = LAUNCHCTL_PATH.read_text(encoding="utf-8")

        self.assertIn('RELEASE_SCHEMA="2"', script)
        self.assertIn('PYTHON_VERSION="3.12.11"', script)
        self.assertIn('"$RELEASE_SCHEMA" "$PYTHON_VERSION"', script)

    def make_home(self, root: Path) -> tuple[Path, dict[str, str]]:
        home = root / "home"
        hermes = home / ".config" / "hermes"
        runtime = hermes / "local" / "qwen3-tts"
        scripts = hermes / "scripts"
        launchd = hermes / "launchd"
        launch_agents = home / "Library" / "LaunchAgents"
        fake_bin = root / "bin"
        for directory in (runtime, scripts, launchd, launch_agents, fake_bin):
            directory.mkdir(parents=True)
        shutil.copy2(SERVER_PATH, scripts / SERVER_PATH.name)
        shutil.copy2(PLIST_PATH, launchd / PLIST_PATH.name)
        (hermes / "qwen3-tts-requirements.lock").write_text(
            "qwen-tts==0.1.1 --hash=sha256:" + "0" * 64 + "\n",
            encoding="utf-8",
        )

        (fake_bin / "python3").symlink_to(sys.executable)
        uv = fake_bin / "uv"
        uv.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = venv ]; then\n"
            "  mkdir -p \"$2/bin\"\n"
            "  printf '%s\\n' '#!/bin/sh' > \"$2/bin/python\"\n"
            "  printf '%s\\n' 'if [ \"${1:-}\" = \"--version\" ]; then echo \"Python 3.12.11\"; exit 0; fi' >> \"$2/bin/python\"\n"
            f"  printf '%s\\n' 'exec \"{sys.executable}\" \"$@\"' >> \"$2/bin/python\"\n"
            "  chmod +x \"$2/bin/python\"\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        uv.chmod(0o755)
        launchctl = fake_bin / "launchctl"
        launchctl.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$HOME/launchctl.log\"\n"
            "if [ \"${1:-}\" = load ] && [ \"${SLOW_LOAD_SECONDS:-0}\" != 0 ]; then touch \"$HOME/load.started\"; sleep \"$SLOW_LOAD_SECONDS\"; fi\n"
            "if [ \"${1:-}\" = load ] && [ \"${FAIL_LAUNCHCTL_LOAD:-0}\" = 1 ]; then exit 1; fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        launchctl.chmod(0o755)
        curl = fake_bin / "curl"
        curl.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >> \"$HOME/curl.log\"\n"
            "[ \"${FAIL_HEALTH:-0}\" = 1 ] && exit 1\n"
            "exit 0\n",
            encoding="utf-8",
        )
        curl.chmod(0o755)
        mv = fake_bin / "mv"
        mv.write_text(
            "#!/bin/sh\n"
            "for arg in \"$@\"; do last=$arg; done\n"
            "if [ \"${FAIL_PLIST_MOVE:-0}\" = 1 ] && [ \"$last\" = \"$HOME/Library/LaunchAgents/local.qwen3-tts.engine.plist\" ]; then exit 1; fi\n"
            "exec /bin/mv \"$@\"\n",
            encoding="utf-8",
        )
        mv.chmod(0o755)
        rm = fake_bin / "rm"
        rm.write_text(
            "#!/bin/sh\n"
            "for arg in \"$@\"; do last=$arg; done\n"
            "case \"$last\" in\n"
            "  \"$HOME/.config/hermes/local/qwen3-tts/releases/\"*)\n"
            "    if [ \"${SLOW_PRUNE_SECONDS:-0}\" != 0 ]; then touch \"$HOME/prune.started\"; sleep \"$SLOW_PRUNE_SECONDS\"; fi\n"
            "    ;;\n"
            "esac\n"
            "exec /bin/rm \"$@\"\n",
            encoding="utf-8",
        )
        rm.chmod(0o755)
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
        env["QWEN3_TTS_STARTUP_ATTEMPTS"] = "1"
        env["QWEN3_TTS_STARTUP_SLEEP_SECONDS"] = "0"
        return home, env

    def seed_catalog(
        self,
        home: Path,
        manifests: list[Path],
        default_voice: str = "lethe",
    ) -> Path:
        catalog = (
            home / ".config" / "hermes" / "local" / "qwen3-tts" / "catalog.json"
        )
        return write_voice_catalog(catalog, manifests, default_voice)

    def run_action(
        self, env: dict[str, str], *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["sh", str(LAUNCHCTL_PATH), *arguments],
            cwd=HERMES_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_invalid_replacement_preserves_registration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            old_manifest = write_voice_manifest(root / "old")
            catalog = self.seed_catalog(home, [old_manifest])
            original_catalog = catalog.read_bytes()
            bad_manifest = root / "bad.json"
            bad_manifest.write_text('{"schema_version": 2}', encoding="utf-8")

            result = self.run_action(
                env, "install", "--voice-manifest", str(bad_manifest)
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(catalog.read_bytes(), original_catalog)
            self.assertFalse((home / "launchctl.log").exists())

    def test_load_failure_restores_registration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            old_manifest = write_voice_manifest(root / "old", "old-voice")
            new_manifest = write_voice_manifest(root / "new", "new-voice")
            catalog = self.seed_catalog(home, [old_manifest], "old-voice")
            original_catalog = catalog.read_bytes()
            old_plist = home / "Library" / "LaunchAgents" / "local.qwen3-tts.engine.plist"
            old_plist.write_text("old plist", encoding="utf-8")
            env["FAIL_LAUNCHCTL_LOAD"] = "1"

            result = self.run_action(
                env, "install", "--voice-manifest", str(new_manifest)
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(catalog.read_bytes(), original_catalog)
            self.assertEqual(old_plist.read_text(encoding="utf-8"), "old plist")
            self.assertIn("failed to reload previous", result.stderr)

    def test_async_startup_failure_restores_registration_and_plist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            old_manifest = write_voice_manifest(root / "old", "old-voice")
            new_manifest = write_voice_manifest(root / "new", "new-voice")
            catalog = self.seed_catalog(home, [old_manifest], "old-voice")
            original_catalog = catalog.read_bytes()
            old_plist = home / "Library" / "LaunchAgents" / "local.qwen3-tts.engine.plist"
            old_plist.write_text("old plist", encoding="utf-8")
            env["FAIL_HEALTH"] = "1"

            result = self.run_action(
                env, "install", "--voice-manifest", str(new_manifest)
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(catalog.read_bytes(), original_catalog)
            self.assertEqual(old_plist.read_text(encoding="utf-8"), "old plist")

    def test_plist_move_failure_after_registration_swap_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            old_manifest = write_voice_manifest(root / "old", "old-voice")
            new_manifest = write_voice_manifest(root / "new", "new-voice")
            catalog = self.seed_catalog(home, [old_manifest], "old-voice")
            original_catalog = catalog.read_bytes()
            old_plist = home / "Library" / "LaunchAgents" / "local.qwen3-tts.engine.plist"
            old_plist.write_text("old plist", encoding="utf-8")
            env["FAIL_PLIST_MOVE"] = "1"

            result = self.run_action(
                env, "install", "--voice-manifest", str(new_manifest)
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(catalog.read_bytes(), original_catalog)
            self.assertEqual(old_plist.read_text(encoding="utf-8"), "old plist")

    def test_successful_install_polls_identity_bound_health(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            manifest = write_voice_manifest(root / "voice")

            result = self.run_action(
                env, "install", "--voice-manifest", str(manifest)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            health_call = (home / "curl.log").read_text(encoding="utf-8")
            self.assertIn("release_id=", health_call)
            self.assertIn("catalog_sha256=", health_call)

    def test_successful_install_prunes_inactive_releases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            manifest = write_voice_manifest(root / "voice")

            first = self.run_action(
                env, "install", "--voice-manifest", str(manifest)
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            releases = (
                home / ".config" / "hermes" / "local" / "qwen3-tts" / "releases"
            )
            active_release = next(releases.iterdir())
            previous_id = "b" * 64
            stale_id = "c" * 64
            previous_release = releases / previous_id
            stale_release = releases / stale_id
            previous_release.mkdir()
            stale_release.mkdir()
            plist = home / "Library" / "LaunchAgents" / "local.qwen3-tts.engine.plist"
            with plist.open("wb") as handle:
                plistlib.dump(
                    {
                        "ProgramArguments": [
                            str(previous_release / "venv" / "bin" / "python")
                        ]
                    },
                    handle,
                )

            second = self.run_action(
                env, "install", "--voice-manifest", str(manifest)
            )

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue(active_release.is_dir())
            self.assertTrue(previous_release.is_dir())
            self.assertFalse(stale_release.exists())

    def test_register_adds_voice_without_changing_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            echo = write_voice_manifest(root / "echo", "echo")

            first = self.run_action(
                env, "install", "--voice-manifest", str(lethe)
            )
            second = self.run_action(
                env, "register", "--voice-manifest", str(echo)
            )
            catalog_path = (
                home
                / ".config"
                / "hermes"
                / "local"
                / "qwen3-tts"
                / "catalog.json"
            )
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(catalog["default_voice"], "lethe")
            self.assertEqual(set(catalog["voices"]), {"lethe", "echo"})

    def test_unregister_removes_non_default_and_rejects_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            echo = write_voice_manifest(root / "echo", "echo")
            self.seed_catalog(home, [lethe, echo])

            removed = self.run_action(env, "unregister", "--voice", "echo")
            rejected = self.run_action(env, "unregister", "--voice", "lethe")
            catalog_path = (
                home
                / ".config"
                / "hermes"
                / "local"
                / "qwen3-tts"
                / "catalog.json"
            )
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

            self.assertEqual(removed.returncode, 0, removed.stderr)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("cannot unregister the default voice", rejected.stderr)
            self.assertEqual(set(catalog["voices"]), {"lethe"})

    def test_install_migrates_legacy_registration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            legacy = (
                home / ".config" / "hermes" / "local" / "qwen3-tts" / "voice.json"
            )
            legacy.symlink_to(lethe)

            result = self.run_action(env, "install")
            catalog_path = legacy.with_name("catalog.json")
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(catalog["default_voice"], "lethe")
            self.assertFalse(legacy.exists())

    def test_signal_after_swap_restores_registration_and_plist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            old_manifest = write_voice_manifest(root / "old", "old-voice")
            new_manifest = write_voice_manifest(root / "new", "new-voice")
            catalog = self.seed_catalog(home, [old_manifest], "old-voice")
            original_catalog = catalog.read_bytes()
            old_plist = home / "Library" / "LaunchAgents" / "local.qwen3-tts.engine.plist"
            old_plist.write_text("old plist", encoding="utf-8")
            env["SLOW_LOAD_SECONDS"] = "2"
            process = subprocess.Popen(
                [
                    "sh",
                    str(LAUNCHCTL_PATH),
                    "install",
                    "--voice-manifest",
                    str(new_manifest),
                ],
                cwd=HERMES_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 5
            while not (home / "load.started").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((home / "load.started").exists())
            process.terminate()
            process.communicate(timeout=10)

            self.assertNotEqual(process.returncode, 0)
            self.assertEqual(catalog.read_bytes(), original_catalog)
            self.assertEqual(old_plist.read_text(encoding="utf-8"), "old plist")
            self.assertFalse(
                (
                    home
                    / ".config"
                    / "hermes"
                    / "local"
                    / "qwen3-tts"
                    / ".mutation.lock"
                ).exists()
            )

    def test_overlapping_mutation_cannot_rollback_successful_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            old_voice = write_voice_manifest(root / "old", "old-voice")
            new_voice = write_voice_manifest(root / "new", "new-voice")
            third_voice = write_voice_manifest(root / "third", "third-voice")
            catalog_path = self.seed_catalog(home, [old_voice], "old-voice")
            slow_env = env.copy()
            slow_env["SLOW_LOAD_SECONDS"] = "2"
            first = subprocess.Popen(
                [
                    "sh",
                    str(LAUNCHCTL_PATH),
                    "install",
                    "--voice-manifest",
                    str(new_voice),
                ],
                cwd=HERMES_DIR,
                env=slow_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 5
            while not (home / "load.started").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((home / "load.started").exists())

            overlapping = self.run_action(
                env, "register", "--voice-manifest", str(third_voice)
            )
            first_stdout, first_stderr = first.communicate(timeout=10)
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

            self.assertEqual(first.returncode, 0, first_stderr or first_stdout)
            self.assertNotEqual(overlapping.returncode, 0)
            self.assertIn("mutation is in progress", overlapping.stderr)
            self.assertEqual(catalog["default_voice"], "new-voice")
            self.assertEqual(set(catalog["voices"]), {"old-voice", "new-voice"})

    def test_pruning_retains_mutation_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            first = self.run_action(
                env, "install", "--voice-manifest", str(lethe)
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            releases = (
                home / ".config" / "hermes" / "local" / "qwen3-tts" / "releases"
            )
            (releases / ("c" * 64)).mkdir()

            slow_env = env.copy()
            slow_env["SLOW_PRUNE_SECONDS"] = "2"
            pruning = subprocess.Popen(
                ["sh", str(LAUNCHCTL_PATH), "install"],
                cwd=HERMES_DIR,
                env=slow_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 5
            while not (home / "prune.started").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue((home / "prune.started").exists())
            server = home / ".config" / "hermes" / "scripts" / SERVER_PATH.name
            server.write_text(
                server.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )

            overlapping = self.run_action(env, "install")
            _, pruning_stderr = pruning.communicate(timeout=10)

            self.assertEqual(pruning.returncode, 0, pruning_stderr)
            self.assertNotEqual(overlapping.returncode, 0)
            self.assertIn("mutation is in progress", overlapping.stderr)

    def test_incomplete_lock_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            catalog_path = self.seed_catalog(home, [lethe])
            original_catalog = catalog_path.read_bytes()
            lock = catalog_path.with_name(".mutation.lock")
            lock.write_text("", encoding="utf-8")

            result = self.run_action(env, "install")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid or incomplete", result.stderr)
            self.assertEqual(catalog_path.read_bytes(), original_catalog)
            self.assertFalse((home / "launchctl.log").exists())

    def test_directory_at_lock_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            catalog_path = self.seed_catalog(home, [lethe])
            original_catalog = catalog_path.read_bytes()
            lock = catalog_path.with_name(".mutation.lock")
            lock.mkdir()

            result = self.run_action(env, "install")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid or incomplete", result.stderr)
            self.assertEqual(catalog_path.read_bytes(), original_catalog)
            self.assertTrue(lock.is_dir())
            self.assertEqual(list(lock.iterdir()), [])

    def test_concurrent_stale_lock_recovery_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home, env = self.make_home(root)
            lethe = write_voice_manifest(root / "lethe", "lethe")
            echo = write_voice_manifest(root / "echo", "echo")
            catalog_path = self.seed_catalog(home, [lethe])
            original_catalog = catalog_path.read_bytes()
            lock = catalog_path.with_name(".mutation.lock")
            lock.write_text("99999999\n", encoding="utf-8")
            first = subprocess.Popen(
                ["sh", str(LAUNCHCTL_PATH), "install"],
                cwd=HERMES_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            second = self.run_action(
                env, "register", "--voice-manifest", str(echo)
            )
            _, first_stderr = first.communicate(timeout=10)

            self.assertNotEqual(first.returncode, 0)
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("stale", first_stderr)
            self.assertIn("stale", second.stderr)
            self.assertEqual(catalog_path.read_bytes(), original_catalog)
            self.assertEqual(lock.read_text(encoding="utf-8"), "99999999\n")


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("qwen3_tts_server_test", SERVER_PATH)

    def setUp(self) -> None:
        self.synthesizer = FakeSynthesizer()
        self.server = self.module.QwenHTTPServer(
            ("127.0.0.1", 0), self.synthesizer
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_and_voice_catalog(self) -> None:
        with urllib.request.urlopen(self.base_url + "/health") as response:
            health = json.loads(response.read())
        with urllib.request.urlopen(self.base_url + "/v1/audio/voices") as response:
            voices = json.loads(response.read())

        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["default_voice"], "lethe")
        self.assertEqual(health["voice_count"], 2)
        self.assertEqual(health["revision"], "test-revision")
        self.assertEqual(health["release_id"], "test-release")
        self.assertEqual(voices["voices"][0]["id"], "lethe")
        self.assertEqual(voices["voices"][1]["id"], "echo")

    def test_health_rejects_stale_release(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(self.base_url + "/health?release_id=stale")

        self.assertEqual(raised.exception.code, 409)
        raised.exception.close()

    def test_health_rejects_stale_catalog(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(self.base_url + "/health?catalog_sha256=stale")

        self.assertEqual(raised.exception.code, 409)
        raised.exception.close()

    def test_speech_endpoint_forwards_text_and_language(self) -> None:
        request = urllib.request.Request(
            self.base_url + "/v1/audio/speech",
            data=json.dumps(
                {"input": "おかえりなさい。", "language": "Japanese"}
            ).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            audio = response.read()

        self.assertEqual(audio, b"RIFF-test-wave")
        self.assertEqual(
            self.synthesizer.calls, [("おかえりなさい。", "lethe")]
        )

    def test_speech_endpoint_selects_registered_voice(self) -> None:
        request = urllib.request.Request(
            self.base_url + "/v1/audio/speech",
            data=json.dumps({"input": "hello", "voice": "echo"}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            response.read()

        self.assertEqual(self.synthesizer.calls, [("hello", "echo")])

    def test_speech_endpoint_rejects_empty_input(self) -> None:
        request = urllib.request.Request(
            self.base_url + "/v1/audio/speech",
            data=b'{"input": ""}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request)

        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()
        self.assertEqual(self.synthesizer.calls, [])

    def test_speech_endpoint_rejects_mismatched_voice(self) -> None:
        request = urllib.request.Request(
            self.base_url + "/v1/audio/speech",
            data=b'{"input": "hello", "voice": "someone-else"}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request)

        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()
        self.assertEqual(self.synthesizer.calls, [])

    def test_speech_endpoint_rejects_path_like_voice(self) -> None:
        request = urllib.request.Request(
            self.base_url + "/v1/audio/speech",
            data=b'{"input": "hello", "voice": "../../voice.json"}',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request)

        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()
        self.assertEqual(self.synthesizer.calls, [])

    def test_speech_endpoint_rejects_overlapping_request(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.synthesizer = BlockingSynthesizer()
        self.server = self.module.QwenHTTPServer(
            ("127.0.0.1", 0), self.synthesizer
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

        first_result: list[bytes] = []

        def request_speech(text: str) -> bytes:
            request = urllib.request.Request(
                self.base_url + "/v1/audio/speech",
                data=json.dumps({"input": text}).encode(),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request) as response:
                return response.read()

        first = threading.Thread(
            target=lambda: first_result.append(request_speech("first")), daemon=True
        )
        first.start()
        self.assertTrue(self.synthesizer.started.wait(timeout=2))
        started = time.monotonic()
        with self.assertRaises(urllib.error.HTTPError) as raised:
            request_speech("second")
        elapsed = time.monotonic() - started
        self.assertEqual(raised.exception.code, 503)
        raised.exception.close()
        self.assertLess(elapsed, 1.0)

        self.synthesizer.release.set()
        first.join(timeout=2)
        self.assertEqual(first_result, [b"RIFF-test-wave"])


class FakeResponse:
    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class ProviderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        agent = types.ModuleType("agent")
        tts_provider = types.ModuleType("agent.tts_provider")
        tts_provider.TTSProvider = object
        agent.tts_provider = tts_provider
        with mock.patch.dict(
            sys.modules,
            {"agent": agent, "agent.tts_provider": tts_provider},
        ):
            cls.module = load_module("qwen3_tts_provider_test", PLUGIN_PATH)

    def test_synthesize_writes_wav_and_sends_expected_payload(self) -> None:
        provider = self.module.Qwen3TTSProvider()
        wav = b"RIFF-test-wave"
        captured = {}

        def urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(wav)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "speech.wav"
            with mock.patch.object(
                self.module.urllib.request, "urlopen", side_effect=urlopen
            ):
                result = provider.synthesize(
                    "おかえりなさい。",
                    str(output),
                    format="wav",
                )

            payload = json.loads(captured["request"].data)
            self.assertEqual(result, str(output))
            self.assertEqual(output.read_bytes(), wav)
            self.assertEqual(payload["input"], "おかえりなさい。")
            self.assertNotIn("voice", payload)
            self.assertNotIn("model", payload)
            self.assertNotIn("language", payload)

    def test_synthesize_forwards_explicit_voice_and_model(self) -> None:
        provider = self.module.Qwen3TTSProvider()
        captured = {}

        def urlopen(request, timeout):
            captured["payload"] = json.loads(request.data)
            return FakeResponse(b"RIFF-test-wave")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "speech.wav"
            with mock.patch.object(
                self.module.urllib.request, "urlopen", side_effect=urlopen
            ):
                provider.synthesize(
                    "hello",
                    str(output),
                    voice="wrong-voice",
                    model="wrong-model",
                    format="wav",
                )

        self.assertEqual(captured["payload"]["voice"], "wrong-voice")
        self.assertEqual(captured["payload"]["model"], "wrong-model")

    def test_atempo_filter_covers_hermes_speed_range(self) -> None:
        provider = self.module.Qwen3TTSProvider()

        self.assertEqual(provider._atempo_filter(0.25), "atempo=0.5,atempo=0.5")
        self.assertEqual(provider._atempo_filter(0.5), "atempo=0.5")
        self.assertEqual(provider._atempo_filter(1.2), "atempo=1.2")
        self.assertEqual(provider._atempo_filter(4.0), "atempo=2,atempo=2")

    def test_speed_normalization_rejects_non_finite_values(self) -> None:
        provider = self.module.Qwen3TTSProvider()

        with self.assertRaises(ValueError):
            provider._normalize_speed(float("inf"))
        with self.assertRaises(ValueError):
            provider._normalize_speed(float("nan"))
        self.assertEqual(provider._normalize_speed(0.1), 0.25)
        self.assertEqual(provider._normalize_speed(5.0), 4.0)

    def test_character_tool_sends_explicit_voice_without_fallback(self) -> None:
        path_security = types.ModuleType("tools.path_security")
        path_security.has_traversal_component = lambda path: False
        tools = types.ModuleType("tools")
        file_safety = types.ModuleType("agent.file_safety")
        file_safety.is_write_denied = lambda path: False
        agent = types.ModuleType("agent")
        agent.file_safety = file_safety

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "echo.ogg"
            with mock.patch.dict(
                sys.modules,
                {
                    "tools": tools,
                    "tools.path_security": path_security,
                    "agent": agent,
                    "agent.file_safety": file_safety,
                },
            ), mock.patch.object(
                self.module.Qwen3TTSProvider,
                "synthesize",
                return_value=str(output),
            ) as synthesize:
                result = json.loads(
                    self.module._character_text_to_speech(
                        "こんにちは。", "echo", str(output), 1.1
                    )
                )

        self.assertTrue(result["success"])
        self.assertEqual(result["voice"], "echo")
        synthesize.assert_called_once_with(
            "こんにちは。",
            str(output),
            voice="echo",
            speed=1.1,
            format="ogg",
        )

    def test_character_tool_returns_error_instead_of_fallback(self) -> None:
        with self.assertLogs(self.module.logger, level="ERROR"), mock.patch.object(
            self.module.Qwen3TTSProvider,
            "synthesize",
            side_effect=RuntimeError("server unavailable"),
        ):
            result = json.loads(self.module._character_text_to_speech("hello", "echo"))

        self.assertFalse(result["success"])
        self.assertIn("server unavailable", result["error"])

    def test_character_tools_are_registered_only_for_creator(self) -> None:
        class FakeContext:
            def __init__(self, profile_name: str) -> None:
                self.profile_name = profile_name
                self.tools: list[str] = []
                self.providers: list[object] = []

            def register_tts_provider(self, provider) -> None:
                self.providers.append(provider)

            def register_tool(self, *, name: str, **kwargs) -> None:
                self.tools.append(name)

        creator = FakeContext("creator")
        assistant = FakeContext("assistant")

        self.module.register(creator)
        self.module.register(assistant)

        self.assertEqual(
            creator.tools, ["character_voices", "character_text_to_speech"]
        )
        self.assertEqual(assistant.tools, [])
        self.assertEqual(len(creator.providers), 1)
        self.assertEqual(len(assistant.providers), 1)


if __name__ == "__main__":
    unittest.main()
