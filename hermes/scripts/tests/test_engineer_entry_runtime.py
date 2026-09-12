"""Offline real-Hermes discovery/read tests, not evidence of model selection.

Set PYTHONPATH to the provisioned Hermes source and use its Python. Each case
copies only candidate Markdown into a fresh HOME before importing Hermes. No
credentials, real config, agent, browser, OpenCode runner or network is used.
Scripted mode transitions test the read contract; they do not execute a job or
establish that a model follows the approval and recovery instructions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import pytest


ENTRIES = {"plan-engineer", "build-engineer", "qa-engineer", "assess-engineer"}
EXPECTED = ENTRIES | {"engineer-pipeline"}
TREE = Path(__file__).resolve().parents[2] / "profiles/engineer/skills/engineer-pipeline"


def test_explicit_runtime_gate_rejects_missing_source(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_PUBLIC_ROOT", str(tmp_path))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    with pytest.raises(pytest.fail.Exception, match="PYTHONPATH must explicitly include"):
        test_engineer_entry_runtime("discovery")


def test_runtime_integration_is_optional_without_explicit_gate(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_PUBLIC_ROOT", raising=False)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    with pytest.raises(pytest.skip.Exception, match="Set PYTHONPATH"):
        test_engineer_entry_runtime("discovery")


@pytest.mark.parametrize("case", ["discovery", "direct", "transitions", "recovery", "missing", "relocation"])
def test_engineer_entry_runtime(case):
    roots = [Path(p).resolve() for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    source = next((p for p in roots if (p / "agent/skill_utils.py").is_file()), None)
    if source is None:
        if "HERMES_PUBLIC_ROOT" in os.environ:
            pytest.fail("PYTHONPATH must explicitly include the provisioned Hermes source checkout")
        pytest.skip("Set PYTHONPATH to the provisioned Hermes source for runtime integration")
    with tempfile.TemporaryDirectory(prefix="engineer-entry-runtime-") as directory:
        sandbox = Path(directory).resolve()
        home = sandbox / "home"
        (home / ".hermes").mkdir(parents=True)
        env = {
            "HOME": str(home), "HERMES_HOME": str(home / ".hermes"),
            "XDG_CONFIG_HOME": str(home / ".config"), "XDG_CACHE_HOME": str(home / ".cache"),
            "TMPDIR": str(sandbox), "PATH": "/usr/bin:/bin", "PYTHONPATH": str(source),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "TERMINAL_ENV": "local",
            "TERMINAL_CWD": str(home), "HERMES_NATIVE_FILE_READ": "1",
            "HERMES_PLATFORM": "telegram", "LANG": "en_US.UTF-8",
        }
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--child",
             case, str(sandbox), str(TREE.resolve()), str(source)],
            cwd=home, env=env, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stdout
        assert json.loads(result.stdout) == {"case": case, "names": sorted(EXPECTED)}


def _child(case, sandbox, candidate, source):
    import logging
    from contextlib import ExitStack
    from unittest.mock import patch

    logging.disable(logging.CRITICAL)
    home = sandbox / "home"
    assert Path.home().resolve() == home
    assert not any(name == "agent" or name.startswith("tools.") for name in sys.modules)
    code_roots = (source, Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve(),
                  Path("/usr"), Path("/System/Library"), Path("/Library/Apple"))

    def audit(event, args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "socket.sendto",
                     "subprocess.Popen", "os.system", "os.posix_spawn"}:
            raise AssertionError("Network and external execution forbidden")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            )
            if path.is_relative_to(sandbox):
                return
            if write:
                raise AssertionError("Write outside isolated HOME forbidden")
            if path.is_relative_to(candidate) and path.suffix == ".md":
                return
            if path.name in {".env", "auth.json", "config.yaml", "SOUL.md"}:
                raise AssertionError("Live configuration/credentials forbidden")
            if not any(path.is_relative_to(root) for root in code_roots):
                raise AssertionError("Read outside candidate/source/runtime forbidden")

    sys.addaudithook(audit)
    skills = home / ".hermes/skills"
    tree = skills / "engineer-pipeline"
    for path in candidate.rglob("*.md"):
        assert not path.is_symlink() and path.resolve().is_relative_to(candidate)
        target = tree / path.relative_to(candidate)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    (home / ".hermes/config.yaml").write_text(
        "skills:\n  external_dirs: []\n  disabled: []\n  template_vars: true\n"
        "  inline_shell: false\nplugins:\n  enabled: []\n", encoding="utf-8",
    )

    with ExitStack() as stack:
        import hermes_cli.plugins as plugins

        stack.enter_context(patch.object(plugins.PluginManager, "discover_and_load", return_value=None))
        for name in ("discover_plugins", "start_background_plugin_discovery"):
            stack.enter_context(patch.object(plugins, name, return_value=None))
        stack.enter_context(patch.object(plugins, "invoke_hook", return_value=[]))
        from agent import skill_utils as su

        stack.enter_context(patch.object(su, "get_external_skills_dirs", return_value=[]))
        stack.enter_context(patch.object(su, "get_project_skills_dirs", return_value=[]))
        from agent import prompt_builder as pb
        from tools import skills_tool as st
        from tools import skills_tool_plugin as sp
        from tools import skill_usage
        from tools.registry import registry

        for name in ("bump_use", "bump_view"):
            stack.enter_context(patch.object(skill_usage, name, return_value=None))
        stack.enter_context(patch.object(sp, "_mark_background_review_read", return_value=None))
        stack.enter_context(patch.object(st, "_mark_background_review_read", return_value=None))
        st._SKILLS_CACHE.clear()
        st.reset_skill_view_dedup()
        pb.clear_skills_system_prompt_cache(clear_snapshot=True)

        def view(name, file_path=None, task="engineer-entry"):
            assert registry.get_entry("skill_view").handler is st._skill_view_with_bump
            return json.loads(registry.dispatch("skill_view", {
                "name": name, "file_path": file_path,
            }, task_id=task))

        def body(payload, path, owner=None):
            assert payload.get("success"), "Missing skill body"
            expected = path.read_text(encoding="utf-8")
            if owner is not None:
                expected = expected.replace("${HERMES_SKILL_DIR}", str(owner))
            assert payload.get("content") == expected

        if case == "discovery":
            assert {s["name"] for s in st._find_all_skills()} == EXPECTED
            assert len(list(su.iter_skill_index_files(skills, "SKILL.md"))) == 5
            prompt = pb.build_skills_system_prompt(
                available_tools={"skills_list", "skill_view", "read_file"},
                available_toolsets={"skills", "file"},
            )
            rows = dict(re.findall(r"^    - ([^: \n]+): (.*)$", prompt, re.MULTILINE))
            assert set(rows) == EXPECTED and len(set(rows.values())) == 5
            for name in ENTRIES:
                assert rows[name].lower().startswith(name.split("-", 1)[0] + " engineering")
                assert 0 < len(rows[name]) <= 60
            # Scanner visibility and cached prompt visibility are different contracts.
            added = tree / "synthetic-entry/SKILL.md"
            added.parent.mkdir()
            added.write_text("---\nname: synthetic-entry\ndescription: Synthetic index change.\n---\n")
            assert added in set(su.iter_skill_index_files(skills, "SKILL.md"))
            assert "synthetic-entry" not in pb.build_skills_system_prompt(
                available_tools={"skills_list", "skill_view", "read_file"},
                available_toolsets={"skills", "file"},
            )
        elif case == "direct":
            for name in sorted(ENTRIES):
                entry = tree / name
                payload = view(name, task=name)
                body(payload, entry / "SKILL.md", entry)
                assert payload["skill_dir"] == str(entry)
                # Dependencies are not auto-loaded by a child view; explicitly follow them.
                body(view("engineer-pipeline", task=name), tree / "SKILL.md", tree)
                body(view("engineer-pipeline", "references/opencode.md", name), tree / "references/opencode.md")
                for reference in (entry / "references").glob("*.md"):
                    body(view(name, f"references/{reference.name}", name), reference)
        elif case == "transitions":
            # Scripted Assess -> Plan -> approved Build -> QA, retaining the same task.
            # This checks available bodies, not an LLM's interpretation of approval.
            body(view("engineer-pipeline"), tree / "SKILL.md", tree)
            body(view("engineer-pipeline", "references/opencode.md"), tree / "references/opencode.md")
            for name in ("assess-engineer", "plan-engineer", "build-engineer", "qa-engineer"):
                body(view(name), tree / name / "SKILL.md", tree / name)
                if name == "plan-engineer":
                    for detail in ("hands-references.md", "web-ui.md"):
                        path = f"references/{detail}"
                        body(view(name, path), tree / name / path)
            assert view("plan-engineer")["content_returned"] is False
            # An unloaded reference is still readable after its root/entry was loaded.
            body(view("qa-engineer", "references/personas.md"), tree / "qa-engineer/references/personas.md")
        elif case in {"recovery", "missing"}:
            from agent.conversation_compression import _reset_read_dedup_caches
            from tools import file_tools as ft
            from tools import file_tools_paths as fp
            from tools import skill_manager_guards
            from tools.environments.local import LocalEnvironment
            from tools.file_operations import ShellFileOperations

            backend = ShellFileOperations(object.__new__(LocalEnvironment), cwd=str(home))
            backend.env.cwd = str(home)
            assert backend._native_read_enabled()
            stack.enter_context(patch.object(ft, "_get_file_ops", return_value=backend))
            stack.enter_context(patch.object(fp, "_terminal_env_type_for_task", return_value="local"))
            stack.enter_context(patch.object(skill_manager_guards, "mark_background_review_skill_read", return_value=None))

            def read(path):
                return json.loads(registry.dispatch("read_file", {"path": str(path)}, task_id="engineer-entry"))

            content = view("plan-engineer")["content"]
            assert str(tree / "plan-engineer") in content
            assert "Stop the affected action" in content
            path = tree / "SKILL.md"
            if case == "recovery":
                body(view("engineer-pipeline"), path, tree)
                assert view("engineer-pipeline")["status"] == "unchanged"
                payload = read(path)
                assert not payload.get("error") and not payload.get("truncated")
                raw = re.sub(r"^\d+\|", "", payload["content"], flags=re.MULTILINE)
                assert raw.rstrip("\n") == path.read_text().rstrip("\n")
                assert read(path)["content_returned"] is False
                assert "BLOCKED" in read(path)["error"]
                _reset_read_dedup_caches("engineer-entry")
                body(view("engineer-pipeline"), path, tree)
            else:
                kernel = path.read_bytes()
                path.unlink()
                result = view("engineer-pipeline")
                assert result.get("success") is False and "content" not in result
                assert read(path).get("error")
                path.write_bytes(kernel)
                transport = tree / "references/opencode.md"
                body(json.loads(st.skill_view("engineer-pipeline", "references/opencode.md")), transport)
                transport.unlink()
                # The child stays visible; missing dependencies must not become success.
                assert json.loads(st.skill_view("plan-engineer")).get("success")
                missing = json.loads(st.skill_view("engineer-pipeline", "references/opencode.md"))
                assert missing.get("success") is False and "content" not in missing
                assert read(transport).get("error")
        elif case == "relocation":
            from hermes_constants import set_hermes_home_override, reset_hermes_home_override

            moved = sandbox / "relocated"
            moved.mkdir()
            skills.rename(moved / "skills")
            token = set_hermes_home_override(str(moved))
            try:
                assert {s["name"] for s in st._find_all_skills()} == EXPECTED
                for name in ENTRIES:
                    owner = moved / "skills/engineer-pipeline" / name
                    payload = view(name)
                    body(payload, owner / "SKILL.md", owner)
                    assert str(tree) not in payload["content"]
            finally:
                reset_hermes_home_override(token)
        else:
            raise AssertionError("Unknown runtime case")


if __name__ == "__main__":
    import traceback

    try:
        assert len(sys.argv) == 6 and sys.argv[1] == "--child"
        _child(sys.argv[2], *(Path(p).resolve() for p in sys.argv[3:]))
        print(json.dumps({"case": sys.argv[2], "names": sorted(EXPECTED)}))
    except BaseException as error:
        frames = [(frame.f_code.co_name, line) for frame, line in traceback.walk_tb(error.__traceback__)]
        print(json.dumps({"case": sys.argv[2], "error_type": type(error).__name__, "frames": frames}))
        sys.exit(1)
