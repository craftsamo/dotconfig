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

    def test_plan_relays_and_is_grounded_in_an_opencode_plan_run(self):
        text = read("plan-assistant-engineering/SKILL.md")
        self.assertIn("You relay; you are neither the user's proxy nor a second technical planner", text)
        self.assertIn("opencode_run_plan", text)
        self.assertIn("a plan is read-only, so it needs no task branch or worktree", text)
        self.assertIn("opencode_preflight", text)
        self.assertIn("Planning consent alone does not authorize implementation", text)
        self.assertIn("Issue management is explicit-only", text)

    def test_messages_to_opencode_carry_words_goal_and_log_not_methods(self):
        text = read("plan-assistant-engineering/SKILL.md")
        self.assertIn("the user's words (quoted, not paraphrased), the goal of the current stage and the path "
                      "of the decision log", text)
        self.assertIn("no commands, steps, file lists, output limits or restated prohibitions", text)
        self.assertIn("A technical question OpenCode asks goes back as its own call", text)
        self.assertNotIn("at most seven", text)
        self.assertNotIn("Five rows", text)
        self.assertNotIn("Settle in-scope technical questions yourself", text)

    def test_a_proposal_becomes_a_decision_only_by_the_users_choice(self):
        log = read("plan-assistant-engineering/SKILL.md")
        self.assertIn("Only the user's explicit choice moves a row to decided", log)
        self.assertIn("A Chat opinion of yours enters as your proposal", log)
        kernel = read("SKILL.md")
        self.assertIn("Your suggestion stays yours until the user takes it", kernel)
        self.assertIn("Ask what only the user can answer", kernel)

    def test_plan_card_and_use_cases_leave_layout_to_the_persona(self):
        text = read("plan-assistant-engineering/SKILL.md")
        self.assertIn("the words, headings and layout you show the user are yours", text)
        self.assertIn("keep **what the user decided** apart from **what anyone proposed**", text)
        self.assertIn("## What goes to OpenCode", text)
        self.assertIn("a write run in the live checkout is refused", text)

    def test_new_products_agree_capabilities_screens_and_data_before_a_roadmap(self):
        text = read("plan-assistant-engineering/references/new-product.md")
        self.assertIn("opencode_run_design", text)
        for stage in ("1. Purpose and use", "2. Capabilities, screens and data", "3. Roadmap", "4. Each Phase"):
            self.assertIn(f"## {stage}", text)
        plan = read("plan-assistant-engineering/SKILL.md")
        self.assertIn("Phase N is one reviewable layer: one PR, or one layer of a native stack", plan)
        self.assertIn("Its approval releases that Phase only", plan)
        self.assertIn("never round away what changes for people", read("references/plan/index.md"))

    def test_the_worktree_comes_after_approval_through_the_plugin(self):
        text = read("execute-assistant-engineering/SKILL.md")
        self.assertIn("opencode_session workspace", text)
        self.assertIn("opencode_session fork", text)
        self.assertIn("never ask OpenCode to move itself", text)
        self.assertIn("alternate", text)

    def test_one_release_per_phase_and_no_edits_of_your_own(self):
        text = read("execute-assistant-engineering/SKILL.md")
        self.assertIn("One Phase's approval releases that Phase through PR delivery", text)
        self.assertIn("The next Phase starts only with its own approval", text)
        self.assertIn("progress.md", text)
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
