from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("image_fallback", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StubProvider(MODULE.ImageGenProvider):
    """A chain member that records what it was asked to generate."""

    def __init__(
        self,
        name: str,
        *,
        available: bool = True,
        caps: Dict[str, Any] | None = None,
        result: Dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._available = available
        self._caps = caps
        self._result = result or {"success": True, "image": f"{name}.png"}
        self.calls: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def capabilities(self) -> Dict[str, Any]:
        if self._caps is None:
            return super().capabilities()
        return dict(self._caps)

    def generate(self, prompt: str, aspect_ratio: str = "square", **kwargs: Any) -> Dict[str, Any]:
        self.calls.append({"prompt": prompt, "aspect_ratio": aspect_ratio, **kwargs})
        return dict(self._result)


def _chain(*members: StubProvider) -> MODULE.ChainProvider:
    registry = {m.name: m for m in members}
    chain = MODULE.ChainProvider("test-chain", [m.name for m in members])
    patcher = mock.patch.object(MODULE.image_gen_registry, "get_provider", registry.get)
    patcher.start()
    chain._patcher = patcher  # type: ignore[attr-defined]
    return chain


class CapabilitiesTest(unittest.TestCase):
    """The chain advertises the surface of the member that will serve the call."""

    def tearDown(self) -> None:
        mock.patch.stopall()

    def test_first_available_member_is_reported(self) -> None:
        codex = StubProvider("codex", available=False,
                             caps={"modalities": ["text", "image"], "max_reference_images": 9})
        xai = StubProvider("xai", caps={"modalities": ["text", "image"], "max_reference_images": 2})
        chain = _chain(codex, xai)
        self.assertEqual({"modalities": ["text", "image"], "max_reference_images": 2},
                         chain.capabilities())

    def test_no_available_member_is_text_only(self) -> None:
        chain = _chain(StubProvider("codex", available=False,
                                    caps={"modalities": ["text", "image"]}))
        self.assertEqual({"modalities": ["text"], "max_reference_images": 0},
                         chain.capabilities())

    def test_member_without_declaration_stays_text_only(self) -> None:
        chain = _chain(StubProvider("legacy"))
        self.assertEqual(["text"], chain.capabilities()["modalities"])


class ImageRoutingTest(unittest.TestCase):
    """A call carrying images never lands on a member that would drop them."""

    def tearDown(self) -> None:
        mock.patch.stopall()

    def test_text_only_member_is_skipped_for_reference_calls(self) -> None:
        text_only = StubProvider("fal", caps={"modalities": ["text"], "max_reference_images": 0})
        editor = StubProvider("xai", caps={"modalities": ["text", "image"], "max_reference_images": 2})
        chain = _chain(text_only, editor)
        result = chain.generate("a shiba", reference_image_urls=["/tmp/anchor.png"])
        self.assertTrue(result["success"])
        self.assertEqual([], text_only.calls)
        self.assertEqual(["/tmp/anchor.png"], editor.calls[0]["reference_image_urls"])

    def test_text_only_member_still_serves_plain_prompts(self) -> None:
        text_only = StubProvider("fal", caps={"modalities": ["text"]})
        chain = _chain(text_only)
        self.assertTrue(chain.generate("a shiba")["success"])
        self.assertEqual(1, len(text_only.calls))

    def test_references_are_trimmed_to_the_member_cap(self) -> None:
        editor = StubProvider("xai", caps={"modalities": ["text", "image"], "max_reference_images": 2})
        chain = _chain(editor)
        chain.generate("a shiba", reference_image_urls=["a", "b", "c"])
        self.assertEqual(["a", "b"], editor.calls[0]["reference_image_urls"])

    def test_all_members_text_only_reports_failure(self) -> None:
        chain = _chain(StubProvider("fal", caps={"modalities": ["text"]}))
        result = chain.generate("a shiba", image_url="/tmp/src.png")
        self.assertFalse(result["success"])
        self.assertIn("text-only", result["error"])

    def test_failed_editor_falls_through_to_next_editor(self) -> None:
        broken = StubProvider("codex", caps={"modalities": ["text", "image"], "max_reference_images": 9},
                              result={"success": False, "error": "quota"})
        editor = StubProvider("xai", caps={"modalities": ["text", "image"], "max_reference_images": 2})
        chain = _chain(broken, editor)
        result = chain.generate("a shiba", image_url="/tmp/src.png")
        self.assertEqual("xai.png", result["image"])
        self.assertEqual("/tmp/src.png", editor.calls[0]["image_url"])


if __name__ == "__main__":
    unittest.main()
