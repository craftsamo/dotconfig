"""Explainer-video reviews route to one technic that orchestrates, never produces."""

from pathlib import Path
import unittest

import hermes_yaml as yaml

from _pair import PUBLIC_ROOT


ROOT = Path(__file__).resolve().parents[1]
TECHNIC = PUBLIC_ROOT / "hermes/profiles/assistant/skills/technic/explainer-video-review"
LOAD = 'skill_view(name="explainer-video-review")'


def flat(path: Path) -> str:
    return " ".join(path.read_text().split())


class ExplainerVideoReviewRouting(unittest.TestCase):
    def test_technic_is_a_technic_with_its_script(self):
        text = (TECHNIC / "SKILL.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(meta["name"], "explainer-video-review")
        self.assertEqual(meta["metadata"]["hermes"]["category"], "technic")
        self.assertIn("Independent of the video's release state", " ".join(meta["description"].split()))
        self.assertTrue((TECHNIC / "scripts/review.py").is_file())

    def test_entries_load_the_technic(self):
        for entry in ("execute-assistant-creative/SKILL.md", "chat-assistant/SKILL.md"):
            self.assertIn(LOAD, flat(ROOT / entry), entry)
        self.assertIn("`explainer-video-review`", flat(ROOT / "plan-assistant-creative/references/explainer-video.md"))
        self.assertIn("`explainer-video-review`", flat(ROOT / "qa-assistant-creative/SKILL.md"))

    def test_owners_and_transports(self):
        text = flat(TECHNIC / "SKILL.md")
        for owner in ("video-creator `analyze-explainer-video`", "Never do this check yourself or through `delegate_task`",
                      "review.py import", "`analyze-speech`", '`kind="work"`, at most five videos per conversation',
                      "`analyze-card`", "`destination: youtube-thumb`",
                      "`technic: primary-fact-pack`", "`technic: claim-check`, through Creator",
                      "`write-document`, format `report`"):
            self.assertIn(owner, text)
        self.assertNotIn('analyze-speech` with `kind="inquiry"', text)

    def test_the_picture_leaf_is_commissioned_and_bounded(self):
        commission = flat(ROOT / "execute-assistant-creative/references/explainer-video.md")
        self.assertIn("`analyze-explainer-video`", commission)
        self.assertIn('kind="work")`, one conversation per video', commission)
        self.assertIn("`remote_analysis` defaults to no", commission)
        leaf = flat(PUBLIC_ROOT / "hermes/profiles/video-creator/skills/video-creator-pipeline/analyze/explainer-video/SKILL.md")
        for boundary in ("Never say whether a portrait looks like a real person", "List them; do not judge them",
                         "Text heights come from `measure`", "No thumbnail review"):
            self.assertIn(boundary, leaf)

    def test_requester_format_only_on_user_instruction(self):
        text = flat(TECHNIC / "SKILL.md")
        self.assertIn("recorded, not applied", text)
        self.assertIn("in `template` only when the user told you to use it", text)
        self.assertIn("never patch the report yourself", text)

    def test_judgments_stay_with_the_user(self):
        text = flat(TECHNIC / "SKILL.md")
        self.assertIn("| Listening, likeness, the final send | the user |", text)
        self.assertIn("leave the verdict to the user", text)
        self.assertIn("Nothing goes to the requester without the user's explicit OK", text)


if __name__ == "__main__":
    unittest.main()
