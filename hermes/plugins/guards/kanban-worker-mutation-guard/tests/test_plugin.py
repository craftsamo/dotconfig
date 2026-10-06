from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN = Path(__file__).resolve().parents[1] / "__init__.py"
SPEC = importlib.util.spec_from_file_location("kanban_worker_mutation_guard", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class KanbanWorkerMutationGuardTest(unittest.TestCase):
    def guard(self, tool_name: str, args: dict | None = None):
        return MODULE._guard_worker_kanban_mutation(
            tool_name=tool_name, args=args or {}
        )

    def test_allows_assistant_context(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.guard("kanban_create"))

    def test_blocks_worker_graph_tools(self) -> None:
        with patch.dict(os.environ, {"HERMES_KANBAN_TASK": "task-1"}, clear=True):
            for tool_name in ("kanban_create", "kanban_link", "kanban_unblock"):
                with self.subTest(tool_name=tool_name):
                    self.assertEqual("block", self.guard(tool_name)["action"])

    def test_allows_worker_lifecycle_tools(self) -> None:
        with patch.dict(os.environ, {"HERMES_KANBAN_TASK": "task-1"}, clear=True):
            for tool_name in (
                "kanban_show",
                "kanban_comment",
                "kanban_block",
                "kanban_complete",
                "kanban_attach",
            ):
                with self.subTest(tool_name=tool_name):
                    self.assertIsNone(self.guard(tool_name))

    def test_blocks_terminal_graph_mutation(self) -> None:
        with patch.dict(os.environ, {"HERMES_KANBAN_TASK": "task-1"}, clear=True):
            for command in (
                "hermes kanban create --title x",
                "/tmp/hermes kanban link child parent",
                "true && hermes kanban unblock task-2",
                "command hermes kanban unlink child parent",
                "env X=1 hermes kanban show task-2",
                "hermes -p engineer kanban create --title x",
                "hermes --profile=engineer kanban link child parent",
            ):
                with self.subTest(command=command):
                    result = self.guard("terminal", {"command": command})
                    self.assertEqual("block", result["action"])

    def test_allows_unrelated_terminal_command(self) -> None:
        with patch.dict(os.environ, {"HERMES_KANBAN_TASK": "task-1"}, clear=True):
            self.assertIsNone(
                self.guard("terminal", {"command": "opencode run verify"})
            )


if __name__ == "__main__":
    unittest.main()
