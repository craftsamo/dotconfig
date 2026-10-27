from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return " ".join((ROOT / path).read_text().split())


class EngineeringClientTests(unittest.TestCase):
    def test_entries_load_the_opencode_tool_skill(self):
        for entry in ("plan", "execute", "qa"):
            text = (ROOT / f"engineering/{entry}/SKILL.md").read_text()
            self.assertIn('skill_view(name="opencode:drive")', text, entry)
            self.assertNotIn("opencode run", text, entry)
            self.assertIsNone(re.search(r"\bEngineer\b", text), entry)

    def test_plan_commissions_and_is_grounded_in_an_opencode_plan_run(self):
        text = read("engineering/plan/SKILL.md")
        self.assertIn("You commission OpenCode on the user's behalf; you are neither a go-between nor a "
                      "second technical planner", text)
        self.assertNotIn("You relay", text)
        self.assertIn("opencode_run_plan", text)
        self.assertIn("a plan is read-only, so it needs no task branch or worktree", text)
        self.assertIn("opencode_preflight", text)
        self.assertIn("Planning consent alone does not authorize implementation", text)
        self.assertIn("A repository job is recorded on GitHub as it is planned", text)
        self.assertIn("The user excludes a job from GitHub in their own words", text)
        self.assertIn("Duration, size or a fix the user calls small never excludes it on their own", text)
        self.assertNotIn("Tracking a job on GitHub is the user's choice", text)

    def test_messages_to_opencode_are_prose_briefs_not_relays_or_methods(self):
        text = read("engineering/plan/SKILL.md")
        self.assertIn("a message to OpenCode is a short brief in plain prose: what is wanted and why, the goal "
                      "of the current stage and the path of the decision log", text)
        self.assertIn("the user's words woven into your sentences where their wording carries the intent", text)
        self.assertNotIn("quoted, not paraphrased", text)
        self.assertIn("no commands, steps, file lists, output limits, report templates or restated prohibitions",
                      text)
        execute = read("engineering/execute/SKILL.md")
        self.assertIn("The message is a short brief in plain prose", execute)
        self.assertIn("A technical question OpenCode asks goes back as its own call", text)
        self.assertNotIn("at most seven", text)
        self.assertNotIn("Five rows", text)
        self.assertNotIn("Settle in-scope technical questions yourself", text)

    def test_the_tool_skill_fixes_markup_and_paths_for_messages(self):
        text = " ".join((ROOT.parents[3] / "plugins/orchestration/opencode/skills/brief/SKILL.md")
                        .read_text().split())
        self.assertIn("Use backticks, and nothing else, for paths, commands, identifiers", text)
        self.assertIn("A fenced block (three backticks) only for several lines that must pass unchanged", text)
        self.assertIn("No headings, bold, tables, link syntax, `>` quotes or other fences", text)
        self.assertIn("A file in the session's repository is relative to its root", text)
        self.assertIn("`@file`, `@agent` and `/command` are the TUI's own input", text)
        self.assertNotIn("deep review <area>", text)

    def test_a_proposal_becomes_a_decision_only_by_the_users_choice(self):
        log = read("engineering/plan/SKILL.md")
        self.assertIn("Only the user's explicit choice moves a row to decided", log)
        self.assertIn("A Chat opinion of yours enters as your proposal", log)
        kernel = read("SKILL.md")
        self.assertIn("Your suggestion stays yours until the user takes it", kernel)
        self.assertIn("Ask what only the user can answer", kernel)

    def test_plan_card_and_use_cases_leave_layout_to_the_persona(self):
        text = read("engineering/plan/SKILL.md")
        self.assertIn("the words, headings and layout you show the user are yours", text)
        self.assertIn("keep **what the user decided** apart from **what anyone proposed**", text)
        self.assertIn("## What goes to OpenCode", text)
        self.assertIn("a write run in the live checkout is refused", text)

    def test_new_products_agree_capabilities_screens_and_data_before_a_roadmap(self):
        text = read("engineering/plan/references/new-product.md")
        self.assertIn("opencode_run_design", text)
        for stage in ("1. Purpose and use", "2. Capabilities, screens and data", "3. Roadmap", "4. Each unit"):
            self.assertIn(f"## {stage}", text)
        plan = read("engineering/plan/SKILL.md")
        self.assertIn("Phase N is one reviewable layer: one PR, or one layer of the stack", plan)
        self.assertIn("Its approval releases that unit only, all of its layers", plan)
        self.assertIn("never round away what changes for people", read("references/plan/index.md"))

    def test_the_unit_is_the_issue_and_a_layer_never_is(self):
        plan = read("engineering/plan/SKILL.md")
        self.assertIn("## Units and Phases", plan)
        self.assertIn("A unit is one goal that delivers on its own", plan)
        self.assertIn("one PR or one native stack of PRs that lands in one merge, and on GitHub it is one issue", plan)
        self.assertIn("a layer is never an issue of its own", plan)
        self.assertIn("fork it for each unit", plan)
        ops = read("engineering/execute/references/github-ops.md")
        self.assertIn("a sub-issue per unit", ops)
        self.assertNotIn("sub-issue per Phase", ops)
        self.assertIn("its layers as a `- [ ]` checklist", ops)
        self.assertIn("A finished step (a progress notification) | nothing on GitHub: steps live in `progress.md`", ops)
        self.assertIn("A layer's PR is up | its checklist line ticked with the PR's `#n`", ops)
        read_skill = " ".join((ROOT.parents[3] / "plugins/github-access/skills/read-tracking/SKILL.md")
                              .read_text().split())
        self.assertIn("a layer (what the engineering entries call a Phase) is a line of the unit's checklist",
                      read_skill)
        product = read("engineering/plan/references/new-product.md")
        self.assertIn("## 4. Each unit", product)
        self.assertNotIn("Each Phase", product)

    def test_parent_status_follows_its_units(self):
        ops = read("engineering/execute/references/github-ops.md")
        self.assertIn("The parent, if still Todo, In Progress with it", ops)
        self.assertIn("back to In Progress with a dated note when it resumes", ops)
        self.assertIn("All units accepted | the parent's acceptance checked against the evidence, then closed; "
                      "Status Done; the mandate revoked", ops)
        manage = " ".join((ROOT.parents[3] / "plugins/github-access/skills/manage-tracking/SKILL.md")
                          .read_text().split())
        self.assertIn("the first unit under a parent moves the parent to `In Progress` in the same list", manage)
        self.assertIn("When the parent's last unit is Done, its acceptance is checked, it is closed and set `Done` too",
                      manage)
        self.assertIn("**Waiting on someone outside:**", manage)
        qa = read("engineering/qa/references/acceptance.md")
        self.assertIn("when it was the last unit, the parent's acceptance checked, the parent closed and Done", qa)

    def test_writer_reads_every_issue_body_once(self):
        ops = read("engineering/execute/references/github-ops.md")
        self.assertIn("**Writer reads it once.**", ops)
        self.assertIn("one `specialist_call` to `writer`", ops)
        self.assertIn("what it finds unclear as a spec", ops)
        self.assertIn("one round, not a second proofreading", ops)
        self.assertIn("a brief never carries facts the issue lacks", ops)
        execute = read("engineering/execute/SKILL.md")
        self.assertIn("read once by Writer", execute)

    def test_the_worktree_comes_after_approval_through_the_plugin(self):
        text = read("engineering/execute/SKILL.md")
        self.assertIn("opencode_session workspace", text)
        self.assertIn("opencode_session fork", text)
        self.assertIn("never ask OpenCode to move itself", text)
        self.assertIn("alternate", text)

    def test_one_release_per_phase_and_no_edits_of_your_own(self):
        text = read("engineering/execute/SKILL.md")
        self.assertIn("One unit's approval releases that unit through PR delivery", text)
        self.assertIn("The next unit starts only with its own approval", text)
        self.assertIn("**Fix the unit's issue.**", text)
        self.assertIn("A job the user excluded from GitHub skips this step", text)
        self.assertIn("`task/issue-12-short-name`", text)
        self.assertIn("only the completing one says `Closes #N`", text)
        self.assertIn("progress.md", text)
        self.assertIn("Never edit, commit or push target code yourself", text)
        self.assertIn("quoting the user's approving words", text)
        self.assertIn("never pass `issue_approval`", text)
        self.assertIn("a supplied Issue URL remains a read-only spec and no Issue or board changes", text)
        self.assertIn("For a job the user excluded from GitHub", text)
        self.assertIn("a refused name is reported back", text)
        self.assertIn("`[truncated]`", text)
        self.assertIn("not instructions", text)

    def test_a_jobs_record_is_written_by_the_assistant_and_read_by_opencode(self):
        text = read("engineering/execute/references/github-ops.md")
        self.assertIn("You, through `github_change` (github-access), as the record of every repository job (below) "
                      "unless the user excluded it; never an OpenCode run", text)
        self.assertIn('skill_view(name="github-access:manage-tracking")', text)
        self.assertIn("Never pass `issue_approval`: a build does not write Issues or boards", text)
        self.assertIn("**The default.** A repository job is recorded on GitHub: its units are issues, Fixed before "
                      "they are built", text)
        self.assertIn("Nothing else excludes it: not the job's size, nor a fix the user calls small", text)
        self.assertIn("Propose the **mandate**: `routine`", text)
        self.assertIn("never the user's quotes", text)
        self.assertIn("The job's operational work around its repository", text)
        self.assertIn("parent = the parent issue (so it covers that issue tree and nothing else", text)
        self.assertIn("Record the parent issue, the board and the mandate id in the decision log", text)
        self.assertIn("(with a mandate at once, else with the unit's delivery)", text)
        for event in ("The roadmap changes", "The job is dropped", "The job pauses on someone outside",
                      "A new session resumes the job", "The user supplies an existing issue to track"):
            self.assertIn(event, text)
        self.assertIn("one goal that lands once is the unit itself (Fixed from the plan); a goal of several units "
                      "is the parent", text)
        plan = read("engineering/plan/SKILL.md")
        self.assertIn("Operational work around a repository (hosting, DNS, a domain, a contract, a hand-over item)",
                      plan)
        qa = read("engineering/qa/references/acceptance.md")
        self.assertIn("A job the user excluded from GitHub gets no Issue or board close-out", qa)

    def test_the_record_is_filed_with_the_roadmap_in_its_real_shape(self):
        plan = read("engineering/plan/SKILL.md")
        self.assertIn("The roadmap question also names where the job will be recorded on GitHub", plan)
        self.assertIn('skill_view(name="github-access:manage-tracking")` first', plan)
        self.assertIn("a parent issue with one sub-issue per unit", plan)
        self.assertIn("file it on GitHub before the first unit's plan is Fixed", plan)
        ops = read("engineering/execute/references/github-ops.md")
        self.assertIn("once the roadmap (or the single unit) is approved and before the first unit's build", ops)
        self.assertIn("When the user raises the board or the issues themselves, at any point of the job, the answer "
                      "is this same shape", ops)
        self.assertIn("never a board of Phase items, columns or update rules you design anew", ops)
        execute = read("engineering/execute/SKILL.md")
        self.assertIn("A question about the job's record on GitHub, also one the user raises mid-job, is answered "
                      "from", execute)
        manage = " ".join((ROOT.parents[3] / "plugins/github-access/skills/manage-tracking/SKILL.md")
                          .read_text().split())
        self.assertIn("**A repository job is recorded; other work when asked.**", manage)
        self.assertIn("size, length or a job's type never excludes it alone", manage)
        config = " ".join((ROOT.parents[1] / "config.example.yaml").read_text().split())
        self.assertIn("Every repository job is recorded on GitHub, each unit an issue Fixed before its build, "
                      "unless the user excludes the job", config)

    def test_plan_archetypes_still_have_acceptance_rows(self):
        names = {p.stem for p in (ROOT / "engineering/plan/references").glob("*.md")}
        text = (ROOT / "engineering/qa/references/inspection.md").read_text()
        rows = set(re.findall(r"^\| ([a-z][a-z-]+) \|", text, re.MULTILINE))
        self.assertEqual(names, rows)

    def test_existing_change_routes_hands_catalogs_and_lets_opencode_investigate(self):
        text = read("engineering/plan/references/existing-change.md")
        self.assertIn("existing-repository maintenance, not media production", text)
        self.assertIn("distinguishing assessment-only from requested changes", text)
        self.assertIn("OpenCode investigates from the purpose or a bounded inventory", text)
        self.assertIn("do not demand technical filenames or fields from the user or invent them", text)
        self.assertIn("Findings alone never authorize repairs or factual-status upgrades", text)

    def test_qa_is_independent_and_does_not_reimplement_technical_work(self):
        text = read("engineering/qa/SKILL.md")
        self.assertIn("do not duplicate that pipeline", text)
        self.assertIn("NEW `opencode_run_review` session", text)
        self.assertIn("does not authorize merge or deployment", text)


    def test_rendered_ui_escalates_only_unexplained_changes(self):
        text = read("engineering/qa/references/web-ui.md")
        self.assertIn("web_ui_check", text)
        self.assertIn("assets/ui-baseline/<repo>/", text)
        self.assertIn("Otherwise do not ask", text)
        self.assertIn("Never promote screenshots the user has not seen", text)
        self.assertIn("Never open a development target in your own logged-in browser", text)
        plan = read("engineering/plan/references/web-ui.md")
        self.assertIn("first build's screenshots will be shown for approval", plan)


if __name__ == "__main__":
    unittest.main()
