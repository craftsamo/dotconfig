"""The shared workspace layout is public and read explicitly."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[4]
LAYOUT = ROOT / "references" / "workspace-layout.md"


class WorkspaceLayoutOwnershipTest(unittest.TestCase):
    def test_shared_layout_reference_owns_map_and_drafts(self):
        text = LAYOUT.read_text(encoding="utf-8")
        for needle in ("## Map", "## Drafts", "Projects/<Group>/", "Personal/<Group>/",
                       ".agent/<YYYYMMDD>-<job>/", ".inbox/", ".registry/", "workspace_registry",
                       "workspace_drafts", "Promotion is the only way into canon", "`legacy`"):
            self.assertIn(needle, text)

    def test_kernel_requires_reading_the_reference_explicitly(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("read_file", text)
        self.assertIn("${HERMES_SKILL_DIR}/references/workspace-layout.md", text)
        self.assertNotIn("~/Workspaces/AGENTS.md", text)

    def test_file_disposition_refs_read_the_public_layout_explicitly(self):
        layout = "~/.hermes/profiles/assistant/skills/assistant-pipeline/references/workspace-layout.md"
        refs = [ROOT / "chat-assistant" / "references" / f"{name}.md" for name in ("signal", "whatsapp", "x", "discord")]
        refs.append(REPO / "hermes/plugins/messaging/telegram-access/skills/telegram-account/SKILL.md")
        for ref in refs:
            text = " ".join(ref.read_text(encoding="utf-8").split())
            self.assertNotIn("~/Workspaces/AGENTS.md", text, ref.name)
            self.assertIn(layout, text, ref.name)
            self.assertIn("read_file", text, ref.name)

    def test_public_installer_seeds_nothing_private_dependent(self):
        text = (REPO / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("Workspaces/AGENTS", text)


if __name__ == "__main__":
    unittest.main()
