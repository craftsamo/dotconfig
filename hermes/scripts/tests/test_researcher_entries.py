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
ENTRIES = {
    "evidence-pack-researcher", "tradeoff-matrix-researcher",
    "fact-check-researcher", "guidance-researcher",
}


def test_candidate_topology_and_always_on_contract():
    errors = []
    assert set(VALIDATOR.validate_researcher_entries(TREE, errors)) == ENTRIES
    assert errors == []
    config = yaml.safe_load((PROFILE / "config.yaml").read_text())
    prompt = config["agent"]["system_prompt"]
    for name in ENTRIES:
        assert name in prompt
    for token in ("every", "turn", "mid", "read_file", "next_offset", "stop", "scope"):
        assert token in prompt.lower()
    assert "kanban_block(kind=capability)" in prompt
    assert "artifact-vs-brief quality verdicts" in prompt
    assert "terminal" not in config["toolsets"]


def test_worker_integration(tmp_path, monkeypatch):
    root = tmp_path / "hermes"
    shutil.copytree(PROFILE, root / "profiles/researcher")
    monkeypatch.setattr(VALIDATOR, "HERMES_ROOT", root)
    # Only Git ownership is outside this synthetic structure test.
    monkeypatch.setattr(VALIDATOR, "validate_git_boundary", lambda *args: None)
    errors = []
    count, learned = VALIDATOR.validate_worker("researcher", errors, catalog={})
    assert count == 4 and learned == 0
    assert errors == []


@pytest.mark.parametrize("mutation,expected", [
    ("missing_entry", "missing researcher document"),
    ("old_reference", "unexpected researcher document"),
    ("hidden_skill", "unexpected researcher document"),
    ("wrong_name", "frontmatter name must be"),
    ("missing_dependency", "missing dependency/recovery"),
    ("missing_recovery", "missing dependency/recovery"),
    ("missing_output", "missing ## Output template"),
    ("card", "defines no card units"),
    ("escaping_link", "broken/escaping researcher link"),
    ("missing_gather", "missing researcher document"),
])
def test_invalid_entries(tmp_path, mutation, expected):
    tree = tmp_path / "researcher-pipeline"
    shutil.copytree(TREE, tree)
    path = tree / "fact-check-researcher/SKILL.md"
    text = path.read_text()
    if mutation == "missing_entry":
        path.unlink()
    elif mutation in {"old_reference", "hidden_skill"}:
        target = tree / ("references/fact-check.md" if mutation == "old_reference"
                         else "references/hidden/SKILL.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    elif mutation == "missing_gather":
        (tree / "references/gather.md").unlink()
    else:
        if mutation == "wrong_name":
            text = text.replace("name: fact-check-researcher", "name: different")
        elif mutation == "missing_dependency":
            text = text.replace('skill_view(name="researcher-pipeline")', "skip kernel")
        elif mutation == "missing_recovery":
            text = text.replace("read_file", "remember")
        elif mutation == "missing_output":
            text = text.replace("## Output template", "## Unspecified output")
        elif mutation == "card":
            text = text.replace("version: 1.0.0", "version: 1.0.0\ncard_units: []")
        elif mutation == "escaping_link":
            text += "\n[Outside](../../../outside.md)\n"
        path.write_text(text)
    errors = []
    VALIDATOR.validate_researcher_entries(tree, errors)
    assert any(expected in error for error in errors), errors


def test_preserved_unit_boundaries():
    fact = (TREE / "fact-check-researcher/SKILL.md").read_text()
    assert "byte-for-byte" in fact and "claim-ledger.md" in fact
    assert "not an artifact-quality gate" in fact
    matrix = (TREE / "tradeoff-matrix-researcher/SKILL.md").read_text()
    assert "closed option set" in matrix and "Unknown" in matrix
    guidance = (TREE / "guidance-researcher/SKILL.md").read_text()
    assert "named consumer" in guidance and "don't craft" in guidance
    for name in ENTRIES:
        text = (TREE / name / "SKILL.md").read_text()
        assert "not a new grant" in text
        assert "kanban_attach" not in text and "**Card runtime:**" not in text


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
        assert set(rows) == names and len(set(rows.values())) == 5
        assert all(0 < len(desc) <= 60 for desc in rows.values())

        def view(name, file_path=None):
            return json.loads(registry.dispatch("skill_view", {"name": name, "file_path": file_path}, task_id="research-test"))

        kernel = view("researcher-pipeline")
        assert kernel["content"] == (tree / "SKILL.md").read_text()
        # A new unit is independently readable even after the kernel was loaded.
        for name in sorted(ENTRIES):
            path = tree / name / "SKILL.md"
            payload = view(name)
            assert payload["content"] == path.read_text().replace("${HERMES_SKILL_DIR}", str(path.parent))
            assert view(name)["status"] == "unchanged"
        gather = view("researcher-pipeline", "references/gather.md")
        assert gather["content"] == (tree / "references/gather.md").read_text()
        assert view("researcher-pipeline")["content_returned"] is False
        assert view("researcher-pipeline", "references/fact-check.md")["success"] is False

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
        path = tree / "fact-check-researcher/SKILL.md"

        def read():
            return json.loads(registry.dispatch("read_file", {"path": str(path)}, task_id="research-test"))

        recovered = read()
        assert not recovered.get("error") and not recovered.get("truncated")
        assert re.sub(r"^\d+\|", "", recovered["content"], flags=re.M).rstrip() == path.read_text().rstrip()
        assert read()["status"] == "unchanged"
        assert "BLOCKED" in read()["error"]
        # Exercise the exact child-relative canonical fallbacks, not just named reads.
        for relative, expected in (("../SKILL.md", tree / "SKILL.md"),
                                   ("../references/gather.md", tree / "references/gather.md")):
            payload = json.loads(registry.dispatch(
                "read_file", {"path": str(path.parent / relative)}, task_id="research-test"
            ))
            assert not payload.get("error") and not payload.get("truncated")
            raw = re.sub(r"^\d+\|", "", payload["content"], flags=re.M)
            assert raw.rstrip() == expected.read_text().rstrip()
        _reset_read_dedup_caches("research-test")
        assert "content" in view("fact-check-researcher")
        assert "content" in read()
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
