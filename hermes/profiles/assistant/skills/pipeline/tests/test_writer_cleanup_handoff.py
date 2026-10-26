"""Writing acceptance uses leaf evidence; consultation remains planning input."""

from pathlib import Path
import unittest

import hermes_yaml as yaml

from _pair import private_config
from _public_writer_acceptance import public_acceptance_dir, public_text

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return " ".join((ROOT / path).read_text().split())


class WriterCleanupHandoffTest(unittest.TestCase):
    def test_private_assistant_hides_every_writer_execution_entry(self):
        writer = public_acceptance_dir().parents[1]
        entries = {
            yaml.safe_load(path.read_text().split("---", 2)[1])["name"]
            for path in writer.rglob("SKILL.md") if path != writer / "SKILL.md"
        }
        self.assertIn("consult-writer", entries)
        config = private_config()
        self.assertFalse(config.is_symlink(), "Inspect this private checkout's config")
        disabled = set(yaml.safe_load(config.read_text())["skills"]["disabled"])
        self.assertEqual(entries - disabled, set())
        self.assertNotIn("writer-pipeline", disabled)

    def test_consultation_is_decision_input_not_an_artifact_gate(self):
        for path in ("plan-assistant-writing/SKILL.md", "execute-assistant-writing/SKILL.md"):
            self.assertIn("consult-writer", text(path))
        self.assertIn("requested sizing", text("plan-assistant-writing/SKILL.md"))
        gate = public_text("index.md")
        self.assertIn("not an artifact release or a writing-QA pass", gate)
        self.assertIn("It needs no manuscript path", gate)
        self.assertIn("must not be forwarded as approved text", gate)
        self.assertIn("explicitly released outline is an artifact", gate)

    def test_old_lint_and_assess_routes_are_absent(self):
        for area in ("plan-assistant-writing", "execute-assistant-writing", "qa-assistant-writing"):
            for path in (ROOT / area).rglob("*.md"):
                body = path.read_text()
                for retired in (
                    "japanese-writing/scripts/", "references/legacy.md",
                    "references/assess.md", "references/inspection/",
                    "its assess route", "Legacy Japanese deliverables only",
                ):
                    self.assertNotIn(retired, body, (path, retired))
        for name in ("index.md", "prose.md", "script.md"):
            body = public_text(name)
            for retired in (
                "japanese-writing/scripts/", "references/legacy.md",
                "references/assess.md", "references/inspection/",
                "its assess route", "Legacy Japanese deliverables only",
            ):
                self.assertNotIn(retired, body, (name, retired))

    def test_all_family_gates_still_require_independent_evidence(self):
        gate = public_text("index.md")
        for family in ("post", "article", "document", "message", "copy", "script"):
            self.assertIn(f"Served {family} gate", gate)
        self.assertIn("NOT verified", gate)
        self.assertIn("not a claimed pass count", gate)
        self.assertIn("only if the released request explicitly asked", gate)
        self.assertIn("unknown family/operation returns for a contract decision", gate)


if __name__ == "__main__":
    unittest.main()
