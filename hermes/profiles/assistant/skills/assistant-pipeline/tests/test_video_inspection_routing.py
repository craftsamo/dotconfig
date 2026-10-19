"""Video inspections route to one technic that orchestrates, never produces;
its genre references name the items and the picture leaf."""

import json
from pathlib import Path
import unittest

import hermes_yaml as yaml

from _pair import PUBLIC_ROOT


ROOT = Path(__file__).resolve().parents[1]
TECHNIC = PUBLIC_ROOT / "hermes/profiles/assistant/skills/technic/video-inspection"
LOAD = 'skill_view(name="video-inspection")'


def flat(path: Path) -> str:
    return " ".join(path.read_text().split())


class VideoInspectionRouting(unittest.TestCase):
    def test_technic_is_a_technic_with_its_script_and_genre_references(self):
        text = (TECHNIC / "SKILL.md").read_text()
        meta = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(meta["name"], "video-inspection")
        self.assertEqual(meta["metadata"]["hermes"]["category"], "technic")
        self.assertIn("Independent of the video's release state", " ".join(meta["description"].split()))
        self.assertTrue((TECHNIC / "scripts/inspection.py").is_file())
        body = flat(TECHNIC / "SKILL.md")
        for genre in ("explainer",):
            self.assertTrue((TECHNIC / f"references/{genre}.md").is_file(), genre)
            self.assertIn(f"](references/{genre}.md)", body, genre)
            catalog = json.loads((TECHNIC / f"references/{genre}.json").read_text())
            self.assertEqual(catalog["genre"], genre)
            self.assertTrue(catalog["aspects"])
        self.assertIn("Read the genre reference at step 1", body)
        for step in ("inspection.py aspects <genre>", "inspection.py init ledger.json --genre <genre>",
                     "inspection.py focus ledger.json focus-video.txt --route video-creator",
                     "ask that each finding name its item", "pass it as `--overlay <path>`"):
            self.assertIn(step, body)

    def test_entries_load_the_technic(self):
        for entry in ("execute-assistant-creative/SKILL.md", "chat-assistant/SKILL.md"):
            self.assertIn(LOAD, flat(ROOT / entry), entry)
        self.assertIn("`video-inspection`", flat(ROOT / "plan-assistant-creative/references/explainer-video.md"))
        self.assertIn("`video-inspection`", flat(ROOT / "qa-assistant-creative/SKILL.md"))
        self.assertIn("`video-inspection`", flat(ROOT / "execute-assistant-creative/references/explainer-video.md"))

    def test_owners_and_transports(self):
        text = flat(TECHNIC / "SKILL.md")
        for owner in ("the genre reference's analyze leaf", "Never do this check yourself or through `delegate_task`",
                      "inspection.py import", "`analyze-speech`", '`kind="work"`, at most five videos per conversation',
                      "`analyze-card`", "`destination: youtube-thumb` for a YouTube thumbnail",
                      "`technic: primary-fact-pack`", "`technic: claim-check`, through Creator",
                      "`write-document`, format `report`", "`prosody: yes` when voice is in scope",
                      "never import a speech report as it is", "inspection.py triage-speech",
                      'skill_view(name="google-access:google-sheets")', "inspection.py export", "inspection.py readback"):
            self.assertIn(owner, text)
        self.assertNotIn('analyze-speech` with `kind="inquiry"', text)
        self.assertNotIn("analyze-explainer-video", text, "the picture leaf is the genre reference's, not the procedure's")

    def test_the_explainer_reference_names_its_leaf_items_and_series(self):
        text = flat(TECHNIC / "references/explainer.md")
        for rule in ("video-creator's `analyze-explainer-video`", 'one `specialist_call(kind="work")` conversation per video',
                     "at most 600 seconds", "`remote_analysis`: `no` unless the user consented",
                     "`inspection.py aspects explainer`", "| Aspect | Kinds | Who looks |",
                     "likeness itself is the user's call", "never says whether a portrait looks like a real person",
                     'skill_view(name="explainer-series-notes")', "absent on a machine without it",
                     "never written into a learned skill", "overlay JSON for `init --overlay`"):
            self.assertIn(rule, text)

    def test_the_spreadsheet_is_the_users_channel(self):
        text = flat(TECHNIC / "SKILL.md")
        for rule in ("The spreadsheet is the channel between you and the user, nobody else",
                     "The user owns the answer and `memo`; you own `reply`",
                     "a claim of the defect that YES confirms",
                     "decide it yourself, since the user has said they cannot",
                     "never a local path", "send the sheet's URL, not a file",
                     "the spreadsheet stays between you and the user"):
            self.assertIn(rule, text)

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
        self.assertIn("| Answers (seen, heard, checked), likeness, the final send | the user |", text)
        self.assertIn("leave the verdict to the user", text)
        self.assertIn("Nothing goes to the requester without the user's explicit OK", text)
        self.assertIn("Keep taste out of the ledger", text)


if __name__ == "__main__":
    unittest.main()
