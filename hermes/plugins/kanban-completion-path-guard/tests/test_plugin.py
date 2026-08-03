from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any


def load_plugin() -> ModuleType:
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("kanban_completion_path_guard", plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load plugin from {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self) -> None:
        self.hooks: dict[str, Any] = {}

    def register_hook(self, kind: str, callback: Any) -> None:
        self.hooks[kind] = callback


class KanbanCompletionPathGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plugin = load_plugin()

    def guard(self, **kwargs: Any) -> dict[str, str] | None:
        return self.plugin._guard_kanban_complete(**kwargs)

    def test_ignores_other_tools(self) -> None:
        self.assertIsNone(
            self.guard(tool_name="kanban_create", args={"artifacts": ["x"]})
        )

    def test_blocks_nonempty_top_level_artifacts(self) -> None:
        result = self.guard(tool_name="kanban_complete", args={"artifacts": ["draft"]})

        self.assertEqual(result["action"], "block")

    def test_blocks_malformed_nonempty_artifact_fields(self) -> None:
        for args in (
            {"artifacts": "draft"},
            {"metadata": {"artifacts": {"name": "draft"}}},
        ):
            with self.subTest(args=args):
                result = self.guard(tool_name="kanban_complete", args=args)
                self.assertEqual(result["action"], "block")

    def test_allows_empty_artifact_fields(self) -> None:
        self.assertIsNone(
            self.guard(
                tool_name="kanban_complete",
                args={"artifacts": [], "metadata": {"artifacts": []}},
            )
        )

    def test_allows_nested_artifact_handoff(self) -> None:
        self.assertIsNone(
            self.guard(
                tool_name="kanban_complete",
                args={
                    "metadata": {
                        "artifact_handoff": {"artifacts": [{"name": "draft"}]}
                    }
                },
            )
        )

    def test_blocks_existing_explicit_local_path_in_summary(self) -> None:
        with tempfile.NamedTemporaryFile() as output:
            result = self.guard(
                tool_name="kanban_complete",
                args={"summary": f"Wrote {output.name}."},
            )

        self.assertEqual(result["action"], "block")

    def test_blocks_existing_explicit_local_path_in_result(self) -> None:
        with tempfile.NamedTemporaryFile() as output:
            result = self.guard(
                tool_name="kanban_complete",
                args={"result": {"message": f"Saved to {output.name}"}},
            )

        self.assertEqual(result["action"], "block")

    def test_blocks_existing_path_wrapped_in_markdown(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png") as output:
            for summary in (
                f"Candidate: **{output.name}**",
                f"Candidate: _{output.name}_",
                f"Candidate: `{output.name}`",
            ):
                with self.subTest(summary=summary):
                    result = self.guard(
                        tool_name="kanban_complete", args={"summary": summary}
                    )
                    self.assertEqual(result["action"], "block")

    def test_blocks_existing_path_before_unlisted_separators(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png") as output:
            for summary in (
                f"| {output.name}| candidate |",
                f"Candidate: {output.name}#candidate",
            ):
                with self.subTest(summary=summary):
                    result = self.guard(
                        tool_name="kanban_complete", args={"summary": summary}
                    )
                    self.assertEqual(result["action"], "block")

    def test_allows_prose_and_nonexistent_paths(self) -> None:
        result = self.guard(
            tool_name="kanban_complete",
            args={
                "summary": "Completed the draft and checked the output.",
                "result": "No file was created at /definitely/not/a/real/path.",
            },
        )

        self.assertIsNone(result)

    def test_registers_pre_tool_call_hook(self) -> None:
        context = FakeContext()

        self.plugin.register(context)

        self.assertIs(context.hooks["pre_tool_call"], self.plugin._guard_kanban_complete)


if __name__ == "__main__":
    unittest.main()
