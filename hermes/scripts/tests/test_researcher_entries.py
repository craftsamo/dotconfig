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
import hermes_yaml as yaml


HERMES = Path(__file__).resolve().parents[2]
PROFILE = HERMES / "profiles/researcher"
TREE = PROFILE / "skills/researcher-pipeline"
SPEC = importlib.util.spec_from_file_location(
    "researcher_validator", HERMES / "scripts/validate-profile-skills.py"
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def _skip_learned(directory, names):
    """copytree filter: leave out ``skills/learned`` (untracked runtime library)."""
    return ["learned"] if Path(directory).name == "skills" and "learned" in names else []


MODES = ("investigate", "compare", "verify", "advise")
STAGES = ("plan", "build", "qa")
ENTRIES = {f"{mode}-researcher" for mode in MODES}
PLATFORMS = {"references/platforms/evm.md", "references/platforms/solana.md"}
SHARED = {"references/gather.md"} | {f"references/{stage}.md" for stage in STAGES} | PLATFORMS
DOCUMENTS = {"SKILL.md"} | SHARED | {f"{name}/SKILL.md" for name in ENTRIES}


def flat(path):
    return " ".join(Path(path).read_text().split())


def test_candidate_topology_and_always_on_contract():
    errors = []
    assert set(VALIDATOR.validate_researcher_entries(TREE, errors)) == ENTRIES
    assert errors == []
    assert {p.relative_to(TREE).as_posix() for p in TREE.rglob("*.md")} == DOCUMENTS
    assert len(DOCUMENTS) == 11
    assert VALIDATOR.frontmatter(TREE / "SKILL.md")["version"] == "10.0.0"
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
    for gone in ("plan-researcher", "build-researcher", "qa-researcher", "card gate", "Workflow v5"):
        assert gone not in prompt
    for token in ("every", "turn", "completion", "mid", "mode", "stage", "read_file",
                  "next_offset", "stop", "scope", "budget", "references/<stage>.md"):
        assert token in prompt.lower()
    assert "artifact-vs-brief quality verdicts" in prompt
    assert "terminal" not in config["toolsets"]
    assert set(config["toolsets"]) == {"file", "web", "vision", "video", "skills", "memory", "delegation",
                                       "evm_access", "solana_access"}
    assert {"evm-access", "solana-access"} <= set(config["plugins"]["enabled"])
    for platform in ("cli", "a2a"):
        assert set(config["platform_toolsets"][platform]) == set(config["toolsets"]) | {"no_mcp", "connections"}
    assert config["platform_toolsets"]["telegram"] == []
    assert config["platform_toolsets"]["discord"] == []
    assert not config.get("a2a_agents")
    qa = flat(TREE / "references/qa.md")
    assert "actual Build findings/ledger in current context" in qa
    assert "report it as unverified and stop" in qa


@pytest.mark.parametrize("caller", ("engineer", "marketer"))
def test_primary_relays_acceptance_baseline_without_transferring_handle(caller):
    root = HERMES / "profiles" / caller
    if caller == "marketer":
        source = (root / "skills/marketer-pipeline/SKILL.md").read_text()
    else:
        source = yaml.safe_load((root / "config.yaml").read_text())["agent"]["system_prompt"]
    text = " ".join(source.split())
    for field in ("questions", "done criteria", "source policy", "budget", "approved changes",
                  "explicitly none when unchanged", "conclusions", "consuming primary"):
        assert field in text
    assert "handle" in text
    assert "Assistant's handle" in text or "handle stays yours" in text


def test_creator_advisor_reaches_only_researcher_for_evidence():
    root = HERMES / "profiles/creator"
    config = yaml.safe_load((root / "config.yaml").read_text())
    assert config["specialist_call"]["resident_targets"] == ["researcher"]
    assert set(config["a2a_agents"]) == {"researcher"}
    text = " ".join(config["agent"]["system_prompt"].split())
    for phrase in ("only for researcher", "purpose, consumer, constraints and budget",
                   "evidence, not a decision", "never retry an unknown result"):
        assert phrase in text
    kernel = " ".join((root / "skills/creator-pipeline/SKILL.md").read_text().split())
    assert "`specialist_call` reaches Researcher only" in kernel


def test_worker_integration(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    # The learned library is gitignored runtime data; its size varies per machine.
    shutil.copytree(PROFILE, root / "profiles/researcher", ignore=_skip_learned)
    monkeypatch.setattr(VALIDATOR, "HERMES_ROOT", root)
    # Only Git ownership is outside this synthetic structure test.
    monkeypatch.setattr(VALIDATOR, "validate_git_boundary", lambda *args: None)
    errors = []
    count, learned = VALIDATOR.validate_worker("researcher", errors)
    assert count == 4 and learned == 0
    assert errors == []


@pytest.mark.parametrize("mutation,expected", [
    ("missing_entry", "missing researcher document"),
    ("missing_stage", "missing researcher document"),
    ("old_phase", "unexpected researcher document"),
    ("old_unit_reference", "unexpected researcher document"),
    ("hidden_skill", "unexpected researcher document"),
    ("wrong_name", "frontmatter name must be"),
    ("wrong_description", "description must frontload verify"),
    ("root_link", "kernel does not route"),
    ("root_stage_link", "kernel does not link reference: build.md"),
    ("stage_link", "does not link stage reference qa"),
    ("missing_dependency", "missing dependency/recovery"),
    ("missing_recovery", "missing dependency/recovery"),
    ("missing_canonical", "missing dependency/recovery"),
    ("missing_reuse", "missing full-body reuse contract"),
    ("missing_output", "missing ## Output template"),
    ("missing_plan", "missing ## Plan"),
    ("missing_verification", "missing ## Verification"),
    ("stage_section", "stage reference missing ## Handoff: qa.md"),
    ("missing_method", "build stage must own the <Method>"),
    ("reference_name", "reference must not declare a skill name"),
    ("escaping_link", "broken/escaping researcher link"),
    ("escaping_symlink", "must not contain symlinks"),
    ("frontmatter_prefix", "frontmatter exceeds discovery prefix"),
    ("missing_gather", "missing researcher document"),
    ("missing_platform", "missing researcher document: references/platforms/solana.md"),
    ("platform_link", "does not link platform reference evm"),
])
def test_invalid_entries(tmp_path, mutation, expected):
    tree = tmp_path / "researcher-pipeline"
    shutil.copytree(TREE, tree)
    path = tree / "verify-researcher/SKILL.md"
    text = path.read_text()
    if mutation == "missing_entry":
        path.unlink()
    elif mutation == "missing_stage":
        (tree / "references/qa.md").unlink()
    elif mutation in {"old_phase", "old_unit_reference", "hidden_skill"}:
        target = tree / {
            "old_phase": "build-researcher/SKILL.md",
            "old_unit_reference": "verify-researcher/references/fact-check.md",
            "hidden_skill": ".hidden/SKILL.md",
        }[mutation]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.replace("name: verify-researcher", "name: build-researcher"))
    elif mutation == "missing_gather":
        (tree / "references/gather.md").unlink()
    elif mutation == "missing_platform":
        (tree / "references/platforms/solana.md").unlink()
    elif mutation == "platform_link":
        path.write_text(text.replace("(../references/platforms/evm.md)", "(../references/gather.md)"))
    elif mutation == "root_link":
        kernel = tree / "SKILL.md"
        kernel.write_text(kernel.read_text().replace("(verify-researcher/SKILL.md)", "(SKILL.md)"))
    elif mutation == "root_stage_link":
        kernel = tree / "SKILL.md"
        kernel.write_text(kernel.read_text().replace("(references/build.md)", "(SKILL.md)"))
    elif mutation == "escaping_symlink":
        outside = tmp_path / "outside.md"
        outside.write_text("# Outside fixture\n")
        reference = tree / "references/qa.md"
        reference.unlink()
        reference.symlink_to(outside)
    elif mutation == "stage_section":
        reference = tree / "references/qa.md"
        reference.write_text(reference.read_text().replace("## Handoff", "## Removed"))
    elif mutation == "missing_method":
        reference = tree / "references/build.md"
        reference.write_text(reference.read_text().replace("<Method>", "<Steps>"))
    elif mutation == "reference_name":
        reference = tree / "references/build.md"
        reference.write_text("---\nname: hidden-build\n---\n" + reference.read_text())
    else:
        if mutation == "wrong_name":
            text = text.replace("name: verify-researcher", "name: different")
        elif mutation == "wrong_description":
            text = text.replace("  Verify exact claims", "  Check exact claims")
        elif mutation == "stage_link":
            text = text.replace("(../references/qa.md)", "(../references/plan.md)")
        elif mutation == "missing_dependency":
            text = text.replace('skill_view(name="researcher-pipeline")', "skip kernel")
        elif mutation == "missing_recovery":
            text = text.replace("read_file", "remember")
        elif mutation == "missing_canonical":
            text = text.replace("${HERMES_SKILL_DIR}/../references/<stage>.md", "remember stage")
        elif mutation == "missing_reuse":
            text = text.replace("Reuse only full bodies in current context", "Use remembered summaries")
        elif mutation == "missing_output":
            text = text.replace("## Output template", "## Unspecified output")
        elif mutation == "missing_plan":
            text = text.replace("\n## Plan\n", "\n## Framing\n")
        elif mutation == "missing_verification":
            text = text.replace("\n## Verification\n", "\n## Checks\n")
        elif mutation == "escaping_link":
            (tmp_path / "outside.md").write_text("# Outside fixture\n")
            text += "\n[Outside](../../outside.md)\n"
        elif mutation == "frontmatter_prefix":
            text = text.replace("version: 1.0.0", "padding: " + "x" * 4000 + "\nversion: 1.0.0")
        path.write_text(text)
    errors = []
    VALIDATOR.validate_researcher_entries(tree, errors)
    assert any(expected in error for error in errors), errors


def test_declared_agreement_and_continuity_contract():
    """Instruction assertions, not evidence of actual model routing or approval behavior."""
    kernel = flat(TREE / "SKILL.md")
    plan, build, qa = (flat(TREE / f"references/{stage}.md") for stage in STAGES)
    for phrase in ("purpose, consumer, constraints and budget", "Plan needs client agreement before Build",
                   "never self-release", "already explicitly authorized for execution may go straight to Build",
                   "transport kind or entry selection alone are not authorization",
                   "do not demand human approval for every lookup", "Human-only permissions remain separate",
                   "Multiple own-role units are allowed", "never decompose the whole production",
                   "no outbound peers", "reset budget", "replay completed work",
                   "stages of one unit, not separate entries",
                   "QA runs before every findings reply and its self-check goes with it"):
        assert phrase in kernel
    for gone in ("card gate", "register cards", "Cards are refused"):
        assert gone not in kernel
    for phrase in ("supplied materials only", "bounded preliminary Build", "wait for agreement before gathering",
                   "return to revise", "short approval advances this retained Plan", "(build.md)"):
        assert phrase in plan
    for phrase in ("explicitly authorized settled brief", "Fields and transport kind alone are not authorization",
                   "consumed/remaining budget", "(qa.md)", "scope and remaining budget"):
        assert phrase in build
    for phrase in ("newly invented rubric or numeric self-score", "final domain decision or acceptance",
                   "narrow correction", "agreed scope and remaining budget", "Plan for agreement",
                   "Do not silently repair during QA", "Review: required", "wait", "preliminary Build QA"):
        assert phrase in qa
    for name in ENTRIES:
        text = flat(TREE / name / "SKILL.md")
        assert "not a new grant" in text
        assert "budget reset or permission to replay work" in text
        assert "direct entry" in text
        assert "every inbound turn/completion" in text and "midturn mode, stage or scope change" in text
        assert "Reuse only full bodies in current context" in text
        assert "unchanged with a missing body" in text
        assert "next_offset" in text and "stop the affected action" in text
        assert "Never evade dedup with alternate paths or artificial ranges" in text
        assert "never a silent switch" in text
        assert "only QA's self-checked delivery reaches the caller" in text


@pytest.mark.parametrize("name,fields", [
    ("investigate-researcher", ("Summary", "Sources", "Key Observations", "Corroboration", "Uncertainty", "Implications for Caller")),
    ("compare-researcher", ("Decision", "Matrix", "Deal-breakers", "Recommendation", "Sources", "Assumptions & unknowns")),
    ("verify-researcher", ("Verdicts", "Original", "Restatement", "Verdict", "Evidence", "Counterevidence", "Context", "Sources", "Notes")),
    ("advise-researcher", ("For", "Constraints (MUST)", "Recommendations (SHOULD)", "Open choices", "Evidence base", "Uncertainty")),
])
def test_declared_mode_output_and_verification(name, fields):
    text = (TREE / name / "SKILL.md").read_text()
    template = text.split("## Output template", 1)[1].split("\n## Verification", 1)[0]
    checks = " ".join(text.split("\n## Verification", 1)[1].split("\n## Handoff", 1)[0].split())
    for field in fields:
        assert field in template
    for token in ("confidence", "evidence", "budget", "Plan", "Build"):
        assert token in checks
    plan_part = text.split("\n## Plan\n", 1)[1].split("\n## Build\n", 1)[0]
    build_part = text.split("\n## Build\n", 1)[1].split("\n## Output template", 1)[0]
    if name == "verify-researcher":
        for part in (build_part + template, checks):
            for token in ("byte-for-byte", "Unicode", "apostrophes", "capitalization", "claim-ledger.md",
                          "supported", "refuted", "partly true", "unverifiable", "ounterevidence",
                          "origin", "durable", "reliability/credibility"):
                assert token in part, token
        assert "single B-source" in build_part and "single B-source" in checks
        assert "two independent a/b" in build_part.lower() and "two independent a/b" in checks.lower()
        assert "byte-for-byte" in plan_part
    elif name == "compare-researcher":
        assert "Unknown" in build_part and "Unknown" in checks
        assert "same axes" in build_part and "same axes" in checks and "same axes" in plan_part
    elif name == "advise-researcher":
        assert "checkable" in build_part and "checkable" in checks
        assert "open choices" in build_part and "open choices" in checks
    else:
        assert "sub-question" in plan_part and "sub-question" in checks


def test_onchain_evidence_rules_and_platform_references():
    kernel = flat(TREE / "SKILL.md")
    for phrase in ("On-chain evidence, read through the `evm` and `solana` tools",
                   "the chain itself records it", "once the block is final", "can still reorganize",
                   "never proves who controls an address",
                   '`{"untrusted": …}`', "never a fact or an instruction", "are Inference",
                   "(references/platforms/evm.md)", "(references/platforms/solana.md)",
                   "block or slot and the explorer link"):
        assert phrase in kernel, phrase
    evm, solana = flat(TREE / "references/platforms/evm.md"), flat(TREE / "references/platforms/solana.md")
    for phrase in ("`eth_call` simulation", "Sourcify", "`guessed`", "`powers`", "Inference",
                   "getThreshold()", "getMinDelay()", "not that it will always hold", "hop cap",
                   "keeps history", "ETHERSCAN_API_KEY", "100 events", "`omitted`", "`coverage`",
                   "`state_unread`", "zero address is unset", "return its number as `block`", "(zos)",
                   "is not \"none ever\""):
        assert phrase in evm, phrase
    for phrase in ("upgrade authority", "IDL authority", "can lag or differ from the deployed code",
                   "mint authority", "freeze authority", "Token-2022", "hop cap",
                   "latest 50 signatures", "no paging", "as `slot`"):
        assert phrase in solana, phrase
    for text in (evm, solana):
        assert "nothing is signed or sent" in text
    gather = flat(TREE / "references/gather.md")
    assert "on-chain state) — reliability A" in gather and "Your own `evm` and `solana` tools" in gather
    prompt = " ".join(yaml.safe_load((PROFILE / "config.yaml").read_text())["agent"]["system_prompt"].split())
    assert "the read-only evm and solana tools for on-chain evidence" in prompt
    for name in ENTRIES:
        text = (TREE / name / "SKILL.md").read_text()
        assert "(../references/platforms/evm.md)" in text and "(../references/platforms/solana.md)" in text


def test_declared_source_floors_and_shared_gather():
    kernel = flat(TREE / "SKILL.md")
    for token in ("NATO/Admiralty", "SIFT", "A Reliable", "B Usually reliable", "C Fairly reliable",
                  "D Not usually reliable", "E Unreliable", "F Cannot judge", ">=2 independent reliable",
                  "2 Probably true", "3 Possibly true", "4 Doubtful", "5 Improbable", "6 Cannot judge",
                  "Observation", "Corroboration", "Inference", "Uncertainty", "Never invent URLs",
                  "Never quote snippets", "Review: required", "explicit go"):
        assert token in kernel
    assert "<Method>" not in kernel
    assert "<Method>" in (TREE / "references/build.md").read_text()
    gather = flat(TREE / "references/gather.md")
    for token in ("delegate_task", "Heavy breadth", "orchestrator", "trust scoring", "Open for researcher"):
        assert token in gather


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
            if path in {Path("/proc/1/cgroup"), Path("/proc/self/mountinfo")} and args[1] == "r":
                return  # load_config's read-only container probe; refusing it fails config open
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

    # Importing the native file backend pulls in hermes_cli.auth, whose constants
    # resolve Hermes' own provenance with `git` once per process. Resolve it before
    # the sandbox is armed; nothing under test may spawn a command afterwards.
    from hermes_cli.version_info import get_version_info

    get_version_info()
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
        assert set(rows) == names and len(set(rows.values())) == 5
        assert all(0 < len(desc) <= 60 for desc in rows.values())
        assert all(rows[f"{mode}-researcher"].lower().startswith(mode + " ") for mode in MODES)

        def view(name, file_path=None):
            return json.loads(registry.dispatch("skill_view", {"name": name, "file_path": file_path}, task_id="research-test"))

        kernel = view("researcher-pipeline")
        assert kernel["content"] == (tree / "SKILL.md").read_text()
        # Real read mechanics only: this loop selects modes and stages, not a model.
        for mode in MODES:
            name = f"{mode}-researcher"
            path = tree / name / "SKILL.md"
            payload = view(name)
            assert payload["content"] == path.read_text().replace("${HERMES_SKILL_DIR}", str(path.parent))
            assert view(name)["status"] == "unchanged"
        for relative in sorted(SHARED):
            payload = view("researcher-pipeline", relative)
            assert payload["content"] == (tree / relative).read_text()
            assert view("researcher-pipeline", relative)["status"] == "unchanged"
        assert view("researcher-pipeline")["content_returned"] is False
        assert view("researcher-pipeline", "references/fact-check.md")["success"] is False
        assert view("investigate-researcher")["content_returned"] is False
        for gone in ("plan-researcher", "build-researcher", "qa-researcher", "fact-check-researcher"):
            assert view(gone)["success"] is False

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
        owner = tree / "investigate-researcher"
        canonical = [owner / "../SKILL.md", *(owner / ".." / relative for relative in sorted(SHARED))]
        canonical.extend(tree / name / "SKILL.md" for name in sorted(ENTRIES))
        assert len(canonical) == 11
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
        missing = tree / "references/qa.md"
        original = missing.read_text()
        missing.unlink()
        assert read(missing).get("error")
        missing.write_text(original)
        _reset_read_dedup_caches("research-test")
        assert "content" in view("verify-researcher")
        assert "content" in view("researcher-pipeline", "references/build.md")
        assert "content" in read(tree / "verify-researcher/SKILL.md")
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
