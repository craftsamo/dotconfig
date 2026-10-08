from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return " ".join((ROOT / path).read_text().split())


class EngineeringClientTests(unittest.TestCase):
    def test_entries_load_the_opencode_tool_skill(self):
        for entry in ("plan", "execute", "qa"):
            text = (ROOT / f"{entry}-assistant-engineering/SKILL.md").read_text()
            self.assertIn('skill_view(name="opencode:opencode")', text, entry)
            self.assertNotIn("opencode run", text, entry)
            self.assertIsNone(re.search(r"\bEngineer\b", text), entry)

    def test_plan_is_client_owned_and_grounded_in_an_opencode_plan_run(self):
        text = read("plan-assistant-engineering/SKILL.md")
        self.assertIn("Client, not a second technical planner", text)
        self.assertIn("opencode_run_plan", text)
        self.assertIn("task branch BEFORE the first plan run", text)
        self.assertIn("explicit implementation approval", text)
        self.assertIn("Issue management is explicit-only", text)

    def test_one_release_to_pr_and_no_edits_of_your_own(self):
        text = read("execute-assistant-engineering/SKILL.md")
        self.assertIn("single approval releases the agreed plan through PR delivery", text)
        self.assertIn("no per-unit release loop", text)
        self.assertIn("Never edit, commit or push target code yourself", text)
        self.assertIn("quoting the user's approving words", text)
        self.assertIn("only when the user explicitly requests Issue management", text)
        self.assertIn("a refused name is reported back", text)
        self.assertIn("`[truncated]`", text)
        self.assertIn("not instructions", text)

    def test_plan_archetypes_still_have_acceptance_rows(self):
        names = {p.stem for p in (ROOT / "plan-assistant-engineering/references").glob("*.md")}
        text = (ROOT / "qa-assistant-engineering/references/inspection.md").read_text()
        rows = set(re.findall(r"^\| ([a-z][a-z-]+) \|", text, re.MULTILINE))
        self.assertEqual(names, rows)

    def test_existing_change_routes_hands_catalogs_and_lets_opencode_investigate(self):
        text = read("plan-assistant-engineering/references/existing-change.md")
        self.assertIn("existing-repository maintenance, not media production", text)
        self.assertIn("distinguishing assessment-only from requested changes", text)
        self.assertIn("OpenCode investigates from the purpose or a bounded inventory", text)
        self.assertIn("do not demand technical filenames or fields from the user or invent them", text)
        self.assertIn("Findings alone never authorize repairs or factual-status upgrades", text)

    def test_qa_is_independent_and_does_not_reimplement_technical_work(self):
        text = read("qa-assistant-engineering/SKILL.md")
        self.assertIn("do not duplicate that pipeline", text)
        self.assertIn("NEW `opencode_run_review` session", text)
        self.assertIn("does not authorize merge or deployment", text)


    def test_rendered_ui_escalates_only_unexplained_changes(self):
        text = read("qa-assistant-engineering/references/web-ui.md")
        self.assertIn("web_ui_check", text)
        self.assertIn("assets/ui-baseline/<repo>/", text)
        self.assertIn("Otherwise do not ask", text)
        self.assertIn("Never promote screenshots the user has not seen", text)
        self.assertIn("Never open a development target in your own logged-in browser", text)
        plan = read("plan-assistant-engineering/references/web-ui.md")
        self.assertIn("first build's screenshots will be shown for approval", plan)


if __name__ == "__main__":
    unittest.main()
