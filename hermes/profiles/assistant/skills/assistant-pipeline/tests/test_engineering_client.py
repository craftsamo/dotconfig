from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EngineeringClientTests(unittest.TestCase):
    def test_plan_is_client_owned_not_technical_decomposition(self):
        text = (ROOT / "plan-assistant-engineering/SKILL.md").read_text()
        self.assertIn("Client, not a second technical planner", text)
        self.assertIn("explicit implementation approval", text)
        self.assertNotIn("opencode run", text)
        self.assertIn("Issue management is explicit-only", text)

    def test_one_release_to_pr_and_no_raw_opencode(self):
        text = (ROOT / "execute-assistant-engineering/SKILL.md").read_text()
        self.assertIn("single approval releases the agreed plan through PR delivery", text)
        self.assertIn("no per-unit", text)
        self.assertNotIn("opencode run", text)
        self.assertIn("ONLY when the Client explicitly requests", text)

    def test_plan_archetypes_still_have_acceptance_rows(self):
        names = {p.stem for p in (ROOT / "plan-assistant-engineering/references").glob("*.md")}
        text = (ROOT / "qa-assistant-engineering/references/inspection.md").read_text()
        rows = set(re.findall(r"^\| ([a-z][a-z-]+) \|", text, re.MULTILINE))
        self.assertEqual(names, rows)

    def test_existing_change_routes_hands_catalogs_and_lets_engineer_investigate(self):
        text = " ".join((ROOT / "plan-assistant-engineering/references/existing-change.md").read_text().split())
        self.assertIn("existing-repository maintenance, not media production", text)
        self.assertIn("distinguishing assessment-only from requested changes", text)
        self.assertIn("Engineer investigates from the purpose or a bounded inventory", text)
        self.assertIn("do not demand technical filenames or fields from the user or invent them", text)
        self.assertIn("Findings alone never authorize repairs or factual-status upgrades", text)

    def test_execute_inquiry_is_bounded_and_work_is_not_approval(self):
        text = (ROOT / "execute-assistant-engineering/SKILL.md").read_text()
        self.assertIn('Reserve kind="inquiry"', text)
        self.assertIn("without terminal, browser or OpenCode", text)
        self.assertIn('specialist_call(kind="work")', text)
        self.assertIn("it is not implementation approval", text)
        self.assertIn("read-only assessment of current state", text)

    def test_execute_sizes_turns_and_never_drives_engineer_out_of_band(self):
        text = " ".join((ROOT / "execute-assistant-engineering/SKILL.md").read_text().split())
        self.assertIn("one verifiable increment per turn", text)
        self.assertIn("continued in the SAME conversation", text)
        self.assertIn("checkpoint-commit verified work", text)
        self.assertIn("no `hermes -p engineer` from the terminal, no `--resume`", text)
        self.assertIn('kind="reconcile"', text)
        self.assertIn("do not forbid the wrapper itself", text)
        self.assertIn("a refused name is reported back", text)
        self.assertIn("read the conversation's latest `.handoff` record", text)
        self.assertIn("`[truncated]`", text)

    def test_qa_no_longer_reimplements_technical_work(self):
        text = (ROOT / "qa-assistant-engineering/SKILL.md").read_text()
        self.assertIn("Do not duplicate that pipeline", text)
        self.assertIn("does not authorize merge or deployment", text)
        self.assertNotIn("opencode run", text)


if __name__ == "__main__":
    unittest.main()
