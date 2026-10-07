"""Declared caller/specialist contracts, not simulated runtime authorization."""

from pathlib import Path
import re
import unittest

import hermes_yaml as yaml

from _pair import PUBLIC_ROOT, private_config


ROOT = Path(__file__).resolve().parents[1]
UNITS = {
    "research": ("evidence-pack", "tradeoff-matrix", "fact-check", "guidance"),
    "search": ("lookup", "sweep", "hunt"),
}
CARD_YAML = """card_units:
  - name: survey-enumeration
    assignee: searcher
    required_inputs: [settled-question, coverage-claim, per-item-fields]
    unit_cap: "one enumeration/survey with an explicit floor count and per-item field list"
    runtime_cap: 1800
  - name: exhaustive-hunt
    assignee: searcher
    required_inputs: [settled-question, done-criteria, scope-exclusions]
    unit_cap: "one goal-mode multi-hop source hunt; goal_mode: true + goal_max_turns"
    runtime_cap: 3600
"""


def public_pipeline(domain):
    role = domain + "er"
    path = PUBLIC_ROOT / "hermes/profiles" / role / "skills" / f"{role}-pipeline"
    if not (path / "SKILL.md").is_file():
        raise FileNotFoundError(path)
    return path


def text(path):
    return " ".join(path.read_text(encoding="utf-8").split())


class ResearchSearchHandoffTest(unittest.TestCase):
    def test_specialist_pipelines_come_from_this_checkout(self):
        for domain in UNITS:
            self.assertTrue(public_pipeline(domain).is_relative_to(PUBLIC_ROOT))

    def test_seven_caller_contracts_match_all_public_phases(self):
        self.assertEqual(sum(map(len, UNITS.values())), 7)
        for domain, units in UNITS.items():
            role = domain + "er"
            public = public_pipeline(domain)
            for phase in ("plan", "qa"):
                caller = ROOT / f"{phase}-assistant-{domain}"
                self.assertEqual({p.stem for p in (caller / "references").glob("*.md")}, set(units))
                for unit in units:
                    with self.subTest(domain=domain, phase=phase, unit=unit):
                        self.assertIn(f"references/{unit}.md", text(caller / "SKILL.md"))
                        contract = text(caller / "references" / f"{unit}.md")
                        if phase == "plan":
                            self.assertIn(f"QA `{unit}`", contract)
                            self.assertIn("not required inputs for a purpose-first Plan", contract)
                        else:
                            self.assertIn(f"QA contract — {unit}", contract)
                            self.assertIn("agreed proposal or explicitly released settled brief", contract)
            for phase in ("plan", "build", "qa"):
                entry = public / f"{phase}-{role}"
                raw = (entry / "SKILL.md").read_text(encoding="utf-8")
                self.assertEqual(yaml.safe_load(raw.split("---\n", 2)[1])["name"], f"{phase}-{role}")
                self.assertEqual({p.stem for p in (entry / "references").glob("*.md")}, set(units))
                for unit in units:
                    self.assertIn(f"references/{unit}.md", raw)
                    self.assertTrue(text(entry / "references" / f"{unit}.md"))

    def test_purpose_first_agreement_and_explicit_direct_build_both_survive(self):
        for domain in UNITS:
            caller = text(ROOT / f"plan-assistant-{domain}" / "SKILL.md")
            public = text(public_pipeline(domain) / f"plan-{domain}er" / "SKILL.md")
            for token in ("purpose", "consumer", "constraints", "budget", "durable path",
                          "Client", "agreement", "Build"):
                self.assertIn(token, caller)
                self.assertIn(token.lower(), public.lower())
            self.assertIn("same-role", caller)
            self.assertRegex(public.lower(), r"(?:same-role|never plan production work or assign other roles)")
            self.assertIn("without a prebuilt detailed spec", caller)
            self.assertIn("You may still author the full specification", caller)
            self.assertIn("without unnecessary reapproval", caller)
            self.assertIn("transport kind alone are not authorization", caller)
            self.assertIn("explicitly authorized settled", public)
            self.assertIn("human-only or out-of-scope", caller)
            self.assertIn("cross-role dependencies", caller)

    def test_preliminary_build_has_separate_main_agreement_and_existing_handle(self):
        for domain in UNITS:
            caller = text(ROOT / f"plan-assistant-{domain}" / "SKILL.md")
            public = text(public_pipeline(domain) / f"plan-{domain}er" / "SKILL.md")
            for token in ("no unapproved external search", "bounded preliminary Build",
                          "scope, output, budget and stop condition", "separate agreement",
                          "Preliminary agreement never releases main work", "conversation_id",
                          "specialist_call", "specialist_session"):
                self.assertIn(token, caller)
            self.assertIn("bounded preliminary Build", public)
            self.assertRegex(public, r"(?:agree the main work|Do not silently release the main work)")

    def test_exact_card_catalog_and_both_lanes(self):
        raw = (ROOT / "execute-assistant-search/SKILL.md").read_text(encoding="utf-8")
        self.assertIn(CARD_YAML, raw)
        self.assertEqual(yaml.safe_load(raw.split("---\n", 2)[1])["card_units"],
                         yaml.safe_load(CARD_YAML)["card_units"])
        caller = " ".join(raw.split())
        public = text(public_pipeline("search") / "SKILL.md")
        for token in ("survey-enumeration", "exhaustive-hunt", "kanban_block(kind=capability)"):
            self.assertIn(token, caller)
            self.assertIn(token, public)
        self.assertIn("No detailed prebuilt spec is required to start Plan", caller)
        self.assertIn("Cards never host Plan", caller)
        self.assertIn("Build -> specialist QA -> terminal", caller)
        self.assertIn("Build -> QA -> terminal", public)
        self.assertIn("Lookups never ride kanban", caller)
        self.assertIn("kanban-lite.md` remains specification authority", caller)
        for marker in ("STATE:", "DECISION(Q<n>):", "PROGRESS:", "AUTHORITY+:",
                       "needs_input", "SCHEDULED: until=", "REVIEW:", "kanban-resolve-block.sh"):
            self.assertIn(marker, public)
        kanban = text(ROOT / "references/execute/kanban-lite.md")
        self.assertIn("every `required_inputs` item exists and is settled", kanban)
        self.assertIn("One round is the cap", kanban)
        self.assertIn("Second block of any kind", kanban)

    def test_research_stays_indirect_with_authorized_one_shot_and_resident_work(self):
        caller = text(ROOT / "execute-assistant-research/SKILL.md")
        public = text(public_pipeline("research") / "SKILL.md")
        for token in ("engineer", "creator", "marketer", "primary", "spec-gap", "granularity"):
            self.assertIn(token, caller)
            self.assertIn(token, public)
        self.assertIn("you never start researcher sessions or register research cards", caller)
        self.assertIn("bounded authorized researcher inquiry may be one-shot", caller)
        self.assertIn('`kind="inquiry"` alone is not authorization', caller)
        self.assertIn('resident `kind="work"`', caller)
        self.assertIn("refuse every kanban card", public)
        for phase in ("plan", "execute"):
            contract = text(ROOT / f"{phase}-assistant-research/SKILL.md")
            self.assertIn("The primary owns and continues the Researcher work handle and `conversation_id`", contract)
            self.assertIn("Assistant uses only its own PRIMARY work handle", contract)
            self.assertIn("Assistant never holds or uses the Researcher conversation", contract)
            self.assertNotIn("Use the existing work handle", contract)
            self.assertNotIn("work handle: `specialist_call` messages retain", contract)
            self.assertIn("heavy breadth", contract)
            self.assertIn("bounded preliminary depth discovery", contract.lower())
        self.assertIn("Require the primary to return the agreed research proposal/scope alongside conclusions", caller)
        self.assertIn("questions, done criteria, source policy, budget and approved changes", caller)
        self.assertIn("Missing baseline means unverified", caller)
        self.assertIn("spec-gap through the primary before acceptance", caller)
        config = text(private_config())
        calls = config.split("### Specialist calls", 1)[1].split("Execution claims", 1)[0]
        self.assertIn("research/search planning dialogue before release", calls)
        self.assertIn("Planning dialogue is allowed without an execution release; execution requires released scope", calls)
        self.assertIn("that discipline permits purpose-first planning dialogue, not just released units", calls)

    def test_self_check_never_replaces_requester_acceptance(self):
        for domain in UNITS:
            caller = text(ROOT / f"qa-assistant-{domain}/SKILL.md")
            public = text(public_pipeline(domain) / f"qa-{domain}er/SKILL.md")
            self.assertIn("agreed proposal or explicitly released settled brief", caller)
            self.assertIn("self-check, not an external pass", caller)
            self.assertIn("scoring, criteria or correction limit", caller)
            self.assertIn("self-check", public)
            self.assertIn("acceptance", public)
            self.assertIn("remaining budget", public)
            self.assertIn("Plan", public)
            self.assertNotIn(public, caller)
            for path in (ROOT / f"qa-assistant-{domain}/references").glob("*.md"):
                self.assertNotIn(text(public_pipeline(domain) / f"qa-{domain}er/references" / path.name),
                                 text(path))
        research = text(ROOT / "qa-assistant-research/SKILL.md")
        self.assertIn("require the primary-relayed agreed research proposal/scope", research)
        self.assertIn("questions, done criteria, source policy, budget and approved changes", research)
        self.assertIn("explicitly authorized original settled brief only while unchanged", research)
        self.assertIn("Missing relayed baseline or authorized original settled brief means unverified", research)
        self.assertIn("request the missing baseline as a spec-gap through the primary", research)
        self.assertIn("No acceptance from purpose alone, conclusions alone or specialist self-QA", research)
        self.assertIn("Assistant must not reconstruct it from the original purpose", research)

    def test_assistant_menu_does_not_import_six_specialist_phase_entries(self):
        phases = {f"{phase}-{domain}er" for domain in UNITS for phase in ("plan", "build", "qa")}
        self.assertEqual(len(list(ROOT.glob("*/SKILL.md"))), 19)
        self.assertTrue(phases.isdisjoint(p.parent.name for p in ROOT.glob("*/SKILL.md")))
        for path in [ROOT / "SKILL.md", *ROOT.glob("references/*/index.md")]:
            self.assertFalse(phases.intersection(re.findall(r'skill_view\(name="([^"]+)"', text(path))))
            self.assertNotIn("skills.external_dirs", text(path))

    def test_caller_resource_paths_resolve_from_the_actual_owning_entry(self):
        for domain in UNITS:
            for phase in ("plan", "execute", "qa"):
                entry = ROOT / f"{phase}-assistant-{domain}"
                for path in entry.rglob("*.md"):
                    raw = path.read_text(encoding="utf-8")
                    for target in re.findall(r"`([^`\n]+\.md)`", raw):
                        if "<" in target or "/" not in target:
                            continue
                        if target.startswith("${HERMES_SKILL_DIR}/"):
                            resolved = entry / target.removeprefix("${HERMES_SKILL_DIR}/")
                        else:
                            resolved = path.parent / target
                        self.assertTrue(resolved.is_file(), (path, target))


if __name__ == "__main__":
    unittest.main()
