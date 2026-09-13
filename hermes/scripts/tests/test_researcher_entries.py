"""Researcher topology and offline real-runtime reads, not model-selection evidence."""

import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import pytest
import yaml


HERMES = Path(__file__).resolve().parents[2]
PROFILE = HERMES / "profiles/researcher"
TREE = PROFILE / "skills/researcher-pipeline"
SPEC = importlib.util.spec_from_file_location(
    "researcher_validator", HERMES / "scripts/validate-profile-skills.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
PHASES = ("plan", "build", "qa")
UNITS = ("evidence-pack", "tradeoff-matrix", "fact-check", "guidance")
ENTRIES = {f"{phase}-researcher" for phase in PHASES}
DOCUMENTS = {"SKILL.md", "references/gather.md"} | {
    f"{name}/SKILL.md" for name in ENTRIES
} | {f"{name}/references/{unit}.md" for name in ENTRIES for unit in UNITS}


def test_candidate_topology_and_always_on_contract():
    errors = []
    assert set(VALIDATOR.validate_researcher_entries(TREE, errors)) == ENTRIES
    assert errors == []
    assert {p.relative_to(TREE).as_posix() for p in TREE.rglob("*.md")} == DOCUMENTS
    assert len(DOCUMENTS) == 17
    assert VALIDATOR.frontmatter(TREE / "SKILL.md")["version"] == "9.0.0"
    for name in ENTRIES:
        path = TREE / name / "SKILL.md"
        data = VALIDATOR.frontmatter(path)
        assert data["version"] == "1.0.0"
        assert data["metadata"]["hermes"]["category"] == "researcher-pipeline"
        assert data["description"][:60].lower().startswith(name.split("-")[0] + " ")
        assert 4 <= path.read_text().find("\n---", 4) < 4000
    config = yaml.safe_load((PROFILE / "config.yaml").read_text())
    prompt = config["agent"]["system_prompt"]
    assert "first message is the brief" not in " ".join(prompt.lower().split())
    assert "Purpose alone is not execution authority" in prompt
    for name in ENTRIES:
        assert name in prompt
    for token in ("every", "turn", "completion", "mid", "phase", "unit", "read_file",
                  "next_offset", "stop", "scope", "budget", "references/<unit>.md"):
        assert token in prompt.lower()
    assert "kanban_block(kind=capability)" in prompt
    assert "artifact-vs-brief quality verdicts" in prompt
    assert "terminal" not in config["toolsets"]
    assert set(config["toolsets"]) == {"file", "web", "vision", "video", "skills", "memory", "delegation"}
    for platform in ("cli", "a2a"):
        assert set(config["platform_toolsets"][platform]) == set(config["toolsets"]) | {"no_mcp"}
    assert config["platform_toolsets"]["telegram"] == []
    assert config["platform_toolsets"]["discord"] == []
    assert not config.get("a2a_agents")
    qa = " ".join((TREE / "qa-researcher/SKILL.md").read_text().split())
    assert "actual Build findings/ledger in current context" in qa
    assert "report it as unverified and stop" in qa


@pytest.mark.parametrize("caller", ("engineer", "creator", "marketer"))
def test_primary_relays_acceptance_baseline_without_transferring_handle(caller):
    root = HERMES / "profiles" / caller
    if caller == "marketer":
        source = (root / "skills/marketer-pipeline/build-marketer/references/parts.md").read_text()
    else:
        source = yaml.safe_load((root / "config.yaml").read_text())["agent"]["system_prompt"]
    text = " ".join(source.split())
    for field in ("questions", "done criteria", "source policy", "budget", "approved changes",
                  "explicitly none when unchanged", "conclusions", "consuming primary"):
        assert field in text
    assert "handle" in text
    assert "Assistant's handle" in text or "handle stays yours" in text


def test_worker_integration(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    shutil.copytree(PROFILE, root / "profiles/researcher")
    monkeypatch.setattr(VALIDATOR, "HERMES_ROOT", root)
    # Only Git ownership is outside this synthetic structure test.
    monkeypatch.setattr(VALIDATOR, "validate_git_boundary", lambda *args: None)
    errors = []
    count, learned = VALIDATOR.validate_worker("researcher", errors, catalog={})
    assert count == 3 and learned == 0
    assert errors == []


@pytest.mark.parametrize("mutation,expected", [
    ("missing_entry", "missing researcher document"),
    ("missing_unit", "missing researcher document"),
    ("old_reference", "unexpected researcher document"),
    ("hidden_skill", "unexpected researcher document"),
    ("old_skill", "unexpected researcher document"),
    ("wrong_name", "frontmatter name must be"),
    ("root_link", "kernel does not route"),
    ("owner_link", "does not link owned reference"),
    ("missing_dependency", "missing dependency/recovery"),
    ("missing_recovery", "missing dependency/recovery"),
    ("missing_canonical", "missing dependency/recovery"),
    ("missing_reuse", "missing full-body reuse contract"),
    ("missing_output", "missing ## Output template"),
    ("missing_plan", "reference missing ## Plan"),
    ("missing_build", "reference missing ## Output template"),
    ("missing_qa", "reference missing ## Verification"),
    ("card", "defines no card units"),
    ("reference_card", "defines no card units"),
    ("reference_name", "reference must not declare a skill name"),
    ("escaping_link", "broken/escaping researcher link"),
    ("escaping_symlink", "must not contain symlinks"),
    ("frontmatter_prefix", "frontmatter exceeds discovery prefix"),
    ("missing_gather", "missing researcher document"),
])
def test_invalid_entries(tmp_path, mutation, expected):
    tree = tmp_path / "researcher-pipeline"
    shutil.copytree(TREE, tree)
    path = tree / "build-researcher/SKILL.md"
    text = path.read_text()
    if mutation == "missing_entry":
        path.unlink()
    elif mutation == "missing_unit":
        (tree / "qa-researcher/references/fact-check.md").unlink()
    elif mutation in {"old_reference", "hidden_skill", "old_skill"}:
        target = tree / {
            "old_reference": "references/fact-check.md",
            "hidden_skill": ".hidden/SKILL.md",
            "old_skill": "fact-check-researcher/SKILL.md",
        }[mutation]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.replace("name: build-researcher", "name: fact-check-researcher"))
    elif mutation == "missing_gather":
        (tree / "references/gather.md").unlink()
    elif mutation == "root_link":
        kernel = tree / "SKILL.md"
        kernel.write_text(kernel.read_text().replace("(build-researcher/SKILL.md)", "(SKILL.md)"))
    elif mutation == "escaping_symlink":
        outside = tmp_path / "outside.md"
        outside.write_text("# Outside fixture\n")
        reference = tree / "qa-researcher/references/fact-check.md"
        reference.unlink()
        reference.symlink_to(outside)
    elif mutation in {"missing_plan", "missing_build", "missing_qa"}:
        phase = mutation.removeprefix("missing_")
        reference = tree / f"{phase}-researcher/references/fact-check.md"
        heading = {"plan": "## Plan", "build": "## Output template", "qa": "## Verification"}[phase]
        reference.write_text(reference.read_text().replace(heading, "## Removed"))
    elif mutation in {"reference_card", "reference_name"}:
        reference = tree / "build-researcher/references/fact-check.md"
        declaration = "card_units: []" if mutation == "reference_card" else "name: hidden-fact-check"
        reference.write_text(f"---\n{declaration}\n---\n" + reference.read_text())
    else:
        if mutation == "wrong_name":
            text = text.replace("name: build-researcher", "name: different")
        elif mutation == "owner_link":
            text = text.replace("(references/fact-check.md)", "(references/guidance.md)")
        elif mutation == "missing_dependency":
            text = text.replace('skill_view(name="researcher-pipeline")', "skip kernel")
        elif mutation == "missing_recovery":
            text = text.replace("read_file", "remember")
        elif mutation == "missing_canonical":
            text = text.replace("${HERMES_SKILL_DIR}/references/<unit>.md", "remember unit")
        elif mutation == "missing_reuse":
            text = text.replace("Reuse only full bodies in current context", "Use remembered summaries")
        elif mutation == "missing_output":
            text = text.replace("## Output template", "## Unspecified output")
        elif mutation == "card":
            text = text.replace("version: 1.0.0", "version: 1.0.0\ncard_units: []")
        elif mutation == "escaping_link":
            (tmp_path / "outside.md").write_text("# Outside fixture\n")
            text += "\n[Outside](../../outside.md)\n"
        elif mutation == "frontmatter_prefix":
            text = text.replace("version: 1.0.0", "padding: " + "x" * 4000 + "\nversion: 1.0.0")
        path.write_text(text)
    errors = []
    VALIDATOR.validate_researcher_entries(tree, errors)
    assert any(expected in error for error in errors), errors


def test_declared_phase_agreement_and_continuity_contract():
    """Instruction assertions, not evidence of actual model routing or approval behavior."""
    kernel = " ".join((TREE / "SKILL.md").read_text().split())
    plan, build, qa = [" ".join((TREE / f"{phase}-researcher/SKILL.md").read_text().split()) for phase in PHASES]
    for phrase in ("purpose, consumer, constraints and budget", "Plan needs client agreement before Build",
                   "never self-release", "already explicitly authorized for execution may go straight to Build",
                   "transport kind or entry selection alone are not authorization",
                   "do not demand human approval for every lookup", "Human-only permissions remain separate",
                   "Multiple own-role units are allowed", "never decompose the whole production",
                   "no outbound peers", "reset budget", "replay completed work"):
        assert phrase in kernel
    for phrase in ("supplied materials only", "bounded preliminary Build", "wait for agreement before gathering",
                   "return to revise", "short approval advances this retained Plan", "build-researcher"):
        assert phrase in plan
    for phrase in ("explicitly authorized settled brief", "Fields and transport kind alone are not authorization",
                   "consumed/remaining budget", "qa-researcher", "scope and remaining budget"):
        assert phrase in build
    for phrase in ("newly invented rubric or numeric self-score", "final domain decision or acceptance",
                   "narrow correction", "agreed scope and remaining budget", "Plan for agreement",
                   "Do not silently repair during QA", "Review: required", "wait", "preliminary Build QA"):
        assert phrase in qa
    for name in ENTRIES:
        text = " ".join((TREE / name / "SKILL.md").read_text().split())
        assert "not a new grant" in text
        assert "budget reset or permission to replay work" in text
        assert "kanban_block(kind=capability)" in text
        assert "every kanban card" in text
        assert "direct entry" in text and "card gate before" in text
        assert "every inbound turn/completion" in text and "midturn phase, unit or scope change" in text
        assert "Reuse only full bodies in current context" in text
        assert "unchanged with a missing body" in text or "unchanged with a missing" in text
        assert "next_offset" in text and "stop the affected action" in text
        assert "Never evade dedup with alternate paths or artificial ranges" in text
        assert "kanban_attach" not in text and "**Card runtime:**" not in text


@pytest.mark.parametrize("unit,fields", [
    ("evidence-pack", ("Summary", "Sources", "Key Observations", "Corroboration", "Uncertainty", "Implications for Caller")),
    ("tradeoff-matrix", ("Decision", "Matrix", "Deal-breakers", "Recommendation", "Sources", "Assumptions & unknowns")),
    ("fact-check", ("Verdicts", "Original", "Restatement", "Verdict", "Evidence", "Counterevidence", "Context", "Sources", "Notes")),
    ("guidance", ("For", "Constraints (MUST)", "Recommendations (SHOULD)", "Open choices", "Evidence base", "Uncertainty")),
])
def test_declared_unit_output_and_qa_coverage(unit, fields):
    build = (TREE / f"build-researcher/references/{unit}.md").read_text()
    qa = " ".join((TREE / f"qa-researcher/references/{unit}.md").read_text().split())
    for field in fields:
        assert field in build
    assert "## Verification" in qa
    for token in ("confidence", "evidence", "budget", "Plan", "Build"):
        assert token in qa
    if unit == "fact-check":
        for text in (build, qa):
            for token in ("byte-for-byte", "Unicode", "apostrophes", "capitalization", "claim-ledger.md",
                          "supported", "refuted", "partly true", "unverifiable", "counterevidence",
                          "origin", "durable", "reliability/credibility"):
                assert token in text
        assert "single B-source" in build and "single B-source" in qa
        assert "two independent a/b" in build.lower() and "two independent a/b" in qa.lower()
    elif unit == "tradeoff-matrix":
        assert "Unknown" in build and "Unknown" in qa
        assert "same axes" in build and "same axes" in qa
    elif unit == "guidance":
        assert "checkable" in build and "checkable" in qa
        assert "open choices" in build and "open choices" in qa


def test_declared_source_floors_and_shared_gather():
    kernel = " ".join((TREE / "SKILL.md").read_text().split())
    for token in ("NATO/Admiralty", "SIFT", "A Reliable", "B Usually reliable", "C Fairly reliable",
                  "D Not usually reliable", "E Unreliable", "F Cannot judge", ">=2 independent reliable",
                  "2 Probably true", "3 Possibly true", "4 Doubtful", "5 Improbable", "6 Cannot judge",
                  "Observation", "Corroboration", "Inference", "Uncertainty", "Never invent URLs",
                  "Never quote snippets", "Review: required", "explicit go"):
        assert token in kernel
    assert "<Method>" not in kernel
    assert "<Method>" in (TREE / "build-researcher/SKILL.md").read_text()
    gather = " ".join((TREE / "references/gather.md").read_text().split())
    for token in ("delegate_task", "Heavy breadth", "orchestrator", "trust scoring", "Open for researcher"):
        assert token in gather
    assert "kanban runtime" not in gather


def test_real_runtime_discovery_reads_and_recovery():
    roots = [Path(p).resolve() for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    source = next((p for p in roots if (p / "agent/skill_utils.py").is_file()), None)
    if source is None:
        pytest.skip("Set PYTHONPATH to Hermes source and run with its provisioned Python")
    configured = yaml.safe_load((PROFILE / "config.yaml").read_text())["skills"]["external_dirs"]
    prefix = "~/ghq/github.com/NousResearch/hermes-agent/"
    assert all(path.startswith(prefix) for path in configured), "Add an explicit isolated mapping for new external roots"
    external = [str(source / path.removeprefix(prefix)) for path in configured]
    with tempfile.TemporaryDirectory(prefix="researcher-entry-runtime-") as directory:
        sandbox = Path(directory).resolve()
        home = sandbox / "home"
        home.mkdir()
        env = {
            "HOME": str(home), "HERMES_HOME": str(home / ".hermes"),
            "XDG_CONFIG_HOME": str(home / ".config"), "XDG_CACHE_HOME": str(home / ".cache"),
            "TMPDIR": str(sandbox), "PATH": "/usr/bin:/bin", "PYTHONPATH": str(source),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "TERMINAL_ENV": "local",
            "TERMINAL_CWD": str(home), "HERMES_NATIVE_FILE_READ": "1", "HERMES_PLATFORM": "a2a",
        }
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--runtime-child",
             str(sandbox), str(source), json.dumps(external)],
            cwd=home, env=env, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout) == {"names": sorted(ENTRIES | {"researcher-pipeline"})}


def runtime_child(sandbox, source, configured_external):
    import logging
    from contextlib import ExitStack
    from unittest.mock import patch

    logging.disable(logging.CRITICAL)
    home = sandbox / "home"
    assert Path.home().resolve() == home
    tree = home / ".hermes/skills/researcher-pipeline"
    # Copy only the candidate instruction documents, never live config or state.
    shutil.copytree(TREE, tree)
    (home / ".hermes/config.yaml").write_text(
        "skills:\n  external_dirs: []\n  disabled: []\n  template_vars: true\n"
        "  inline_shell: false\nplugins:\n  enabled: []\n"
    )
    code_roots = (source, Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(),
                  Path("/usr"), Path("/System/Library"), Path("/Library/Apple"))

    def audit(event, args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "socket.sendto",
                     "subprocess.Popen", "os.system", "os.posix_spawn"}:
            raise AssertionError("External execution/network forbidden")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.is_relative_to(sandbox):
                return
            mode, flags = args[1:3]
            write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            )
            if write or path.name in {".env", "auth.json", "config.yaml", "SOUL.md"}:
                raise AssertionError("Non-fixture config/credentials/writes forbidden")
            if not any(path.is_relative_to(root) for root in code_roots):
                raise AssertionError("Read outside source/runtime/sandbox forbidden")

    sys.addaudithook(audit)
    with ExitStack() as stack:
        import hermes_cli.plugins as plugins

        for name in ("discover_plugins", "start_background_plugin_discovery"):
            stack.enter_context(patch.object(plugins, name, return_value=None))
        stack.enter_context(patch.object(plugins.PluginManager, "discover_and_load", return_value=None))
        stack.enter_context(patch.object(plugins, "invoke_hook", return_value=[]))
        from agent import skill_utils as su

        external = []
        stack.enter_context(patch.object(su, "get_external_skills_dirs", return_value=external))
        stack.enter_context(patch.object(su, "get_project_skills_dirs", return_value=[]))
        from agent import prompt_builder as pb
        from tools import skills_tool as st, skills_tool_plugin as sp, skill_usage
        from tools.registry import registry

        for name in ("bump_use", "bump_view"):
            stack.enter_context(patch.object(skill_usage, name, return_value=None))
        for module in (st, sp):
            stack.enter_context(patch.object(module, "_mark_background_review_read", return_value=None))
        names = ENTRIES | {"researcher-pipeline"}
        assert {s["name"] for s in st._find_all_skills()} == names
        prompt = pb.build_skills_system_prompt(
            available_tools={"skill_view", "skills_list", "read_file"}, available_toolsets={"skills", "file"}
        )
        rows = dict(re.findall(r"^    - ([^: \n]+): (.*)$", prompt, re.M))
        assert set(rows) == names and len(set(rows.values())) == 4
        assert all(0 < len(desc) <= 60 for desc in rows.values())
        assert all(rows[f"{phase}-researcher"].lower().startswith(phase + " ") for phase in PHASES)

        def view(name, file_path=None):
            return json.loads(registry.dispatch("skill_view", {"name": name, "file_path": file_path}, task_id="research-test"))

        kernel = view("researcher-pipeline")
        assert kernel["content"] == (tree / "SKILL.md").read_text()
        # Real read mechanics only: this loop selects phases, not a model.
        for phase in PHASES:
            name = f"{phase}-researcher"
            path = tree / name / "SKILL.md"
            payload = view(name)
            assert payload["content"] == path.read_text().replace("${HERMES_SKILL_DIR}", str(path.parent))
            assert view(name)["status"] == "unchanged"
            for unit in UNITS:
                reference = f"references/{unit}.md"
                payload = view(name, reference)
                assert payload["content"] == (path.parent / reference).read_text()
                assert view(name, reference)["status"] == "unchanged"
        gather = view("researcher-pipeline", "references/gather.md")
        assert gather["content"] == (tree / "references/gather.md").read_text()
        assert view("researcher-pipeline")["content_returned"] is False
        assert view("researcher-pipeline", "references/fact-check.md")["success"] is False
        assert view("plan-researcher")["content_returned"] is False
        assert view("plan-researcher", "references/evidence-pack.md")["content_returned"] is False
        for unit in UNITS:
            assert view(f"{unit}-researcher")["success"] is False
            assert view(unit)["success"] is False

        from tools import file_tools as ft, file_tools_paths as fp, skill_manager_guards
        from tools.environments.local import LocalEnvironment
        from tools.file_operations import ShellFileOperations
        from agent.conversation_compression import _reset_read_dedup_caches

        backend = ShellFileOperations(object.__new__(LocalEnvironment), cwd=str(home))
        backend.env.cwd = str(home)
        assert backend._native_read_enabled()
        stack.enter_context(patch.object(ft, "_get_file_ops", return_value=backend))
        stack.enter_context(patch.object(fp, "_terminal_env_type_for_task", return_value="local"))
        stack.enter_context(patch.object(skill_manager_guards, "mark_background_review_skill_read", return_value=None))
        def read(path, offset=1):
            return json.loads(registry.dispatch(
                "read_file", {"path": str(path), "offset": offset}, task_id="research-test"
            ))

        # Recover missing bodies via the documented canonical owner paths. Simulate
        # a real output budget, not arbitrary ranges chosen to evade read dedup.
        owner = tree / "plan-researcher"
        canonical = [owner / "../SKILL.md", owner / "../references/gather.md"]
        canonical.extend(tree / name / relative for name in sorted(ENTRIES)
                         for relative in ("SKILL.md", *(f"references/{u}.md" for u in UNITS)))
        assert len(canonical) == 17
        continued = 0
        with patch.object(ft, "_get_max_read_chars", return_value=1000):
            for path in canonical:
                lines = []
                offset = 1
                while True:
                    payload = read(path, offset)
                    assert not payload.get("error"), payload
                    numbered = payload["content"].splitlines()
                    assert all(re.match(r"^\d+\|", line) for line in numbered)
                    lines.extend(re.sub(r"^\d+\|", "", line) for line in numbered)
                    if not payload.get("truncated"):
                        break
                    assert payload["next_offset"] > offset
                    offset = payload["next_offset"]
                    continued += 1
                assert "\n".join(lines).rstrip() == path.read_text().rstrip()
                assert read(path)["status"] == "unchanged"
                assert "BLOCKED" in read(path)["error"]
        assert continued > 0
        # An unavailable canonical file yields an error, not a usable body. The
        # instruction-only stop requirement is checked separately above.
        missing = tree / "qa-researcher/references/fact-check.md"
        original = missing.read_text()
        missing.unlink()
        assert read(missing).get("error")
        missing.write_text(original)
        _reset_read_dedup_caches("research-test")
        assert "content" in view("build-researcher")
        assert "content" in view("build-researcher", "references/fact-check.md")
        assert "content" in read(tree / "build-researcher/SKILL.md")
        # Scan the profile's configured upstream roots as metadata only, never execute them.
        external.extend(Path(p) for p in configured_external)
        assert all(p.is_dir() and p.resolve().is_relative_to(source) for p in external)
        st._SKILLS_CACHE.clear()
        pb.clear_skills_system_prompt_cache(clear_snapshot=True)
        # skills_list deduplicates by name; inspect raw files so collisions cannot hide.
        discovered = {
            p.resolve(): su.parse_frontmatter(p.read_text())[0].get("name")
            for root in (tree.parent, *external)
            for p in su.iter_skill_index_files(root, "SKILL.md")
        }
        for name in names:
            assert list(discovered.values()).count(name) == 1
        visible = pb.build_skills_system_prompt(
            available_tools={"skill_view", "skills_list", "read_file"}, available_toolsets={"skills", "file"}
        )
        assert names <= set(re.findall(r"^    - ([^: \n]+):", visible, re.M))
        print(json.dumps({"names": sorted(names)}))


if __name__ == "__main__" and sys.argv[1:2] == ["--runtime-child"]:
    runtime_child(Path(sys.argv[2]), Path(sys.argv[3]), json.loads(sys.argv[4]))
