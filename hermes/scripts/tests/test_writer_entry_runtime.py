"""Offline candidate integration; run with the Hermes venv and source PYTHONPATH.

Each case imports real discovery/index/registry/dedup in a fresh child HOME.
Only candidate Writer Markdown is copied. Caller configs are parsed BEFORE the
child audit, passing only disabled-name lists, never full config or runtime state.
Plugin discovery/hooks, IPv6 probing, usage and terminal acquisition are isolated;
read_file uses the real native ShellFileOperations backend and pagination.
These are runtime plumbing and textual-contract tests, NOT LLM selection,
context-retention, production execution, acceptance or live-cutover evidence.
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


ROOT = "writer-pipeline"
PRODUCTION = {f"{verb}-{subject}": f"{verb}/{subject}/SKILL.md"
              for verb in ("write", "edit", "analyze")
              for subject in ("post", "article", "document", "message", "copy", "script")}
PATHS = {ROOT: "SKILL.md", "consult-writer": "consult-writer/SKILL.md", **PRODUCTION}
ENTRIES = set(PATHS) - {ROOT}
CASES = ("discovery", "owner_reads", "caller_marketer", "caller_assistant")


@pytest.mark.parametrize("case", CASES)
def test_writer_entry_runtime(case):
    public = Path(__file__).resolve().parents[3]
    candidate = public / "hermes/profiles/writer/skills/writer-pipeline"
    roots = [Path(p).resolve() for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    source = next((p for p in roots if (p / "agent/skill_utils.py").is_file()), None)
    assert source is not None, "PYTHONPATH must explicitly include the Hermes source checkout"
    disabled = []
    if case.startswith("caller_"):
        import yaml

        caller = case.removeprefix("caller_")
        filename = "config.example.yaml" if caller == "assistant" else "config.yaml"
        config = public / "hermes/profiles" / caller / filename
        assert not config.is_symlink(), "Use the public candidate config, not a live link"
        disabled = yaml.safe_load(config.read_text(encoding="utf-8"))["skills"]["disabled"]
        assert isinstance(disabled, list) and all(isinstance(n, str) for n in disabled)
        assert ENTRIES <= set(disabled) and ROOT not in disabled
    with tempfile.TemporaryDirectory(prefix="writer-entry-runtime-") as directory:
        sandbox = Path(directory).resolve()
        home = sandbox / "home"
        (home / ".hermes").mkdir(parents=True)
        env = {
            "HOME": str(home), "HERMES_HOME": str(home / ".hermes"),
            "XDG_CONFIG_HOME": str(home / ".config"), "XDG_CACHE_HOME": str(home / ".cache"),
            "TMPDIR": str(sandbox), "PATH": "/usr/bin:/bin", "PYTHONPATH": str(source),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "LANG": "en_US.UTF-8",
            "TERMINAL_ENV": "local", "TERMINAL_CWD": str(home),
            "HERMES_NATIVE_FILE_READ": "1", "HERMES_PLATFORM": "a2a",
        }
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--child", case,
             str(sandbox), str(candidate), str(source), json.dumps(disabled)],
            cwd=home, env=env, text=True, capture_output=True, timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout) == {"case": case, "passed": True}


def _child(case, sandbox, candidate, source, disabled):
    import logging
    import socket
    from contextlib import ExitStack
    from unittest.mock import patch

    logging.disable(logging.CRITICAL)
    home = sandbox / "home"
    hermes = home / ".hermes"
    assert Path.home().resolve() == home and Path(os.environ["HERMES_HOME"]).resolve() == hermes
    assert not any(n == "agent" or n.startswith("tools.") for n in sys.modules)
    code_roots = (source, Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(),
                  Path("/usr"), Path("/System/Library"), Path("/Library/Apple"))
    violations, writes = [], []

    def deny(*args, **kwargs):
        violations.append("network/process")
        raise AssertionError("Network and subprocesses forbidden")

    def audit(event, args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "socket.sendto",
                     "subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork"}:
            deny()
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if path.name in {".env", "auth.json", "jobs.json", "state.db", "executions.db"}:
                allowed = False
            elif path.is_relative_to(sandbox):
                if write:
                    writes.append(str(path))
                return
            else:
                allowed = not write and (
                    path in {Path(__file__).resolve(), Path("/proc/1/cgroup")}
                    or path.is_relative_to(candidate) and path.suffix == ".md"
                    or path.name not in {"config.yaml", "SOUL.md"}
                    and any(path.is_relative_to(root) for root in code_roots))
            if not allowed:
                violations.append(str(path))
                raise AssertionError(f"Non-fixture file access forbidden: {path}")

    sys.addaudithook(audit)
    with ExitStack() as stack:
        # urllib3's import-time IPv6 probe binds loopback; no socket is needed here.
        stack.enter_context(patch.object(socket, "has_ipv6", False))
        for name in ("connect", "connect_ex", "sendto"):
            stack.enter_context(patch.object(socket.socket, name, deny))
        for name in ("create_connection", "getaddrinfo"):
            stack.enter_context(patch.object(socket, name, deny))
        caller = case.startswith("caller_")
        tree = (sandbox / "external" if caller else hermes / "skills") / ROOT
        for path in candidate.rglob("*.md"):
            assert not path.is_symlink() and path.resolve().is_relative_to(candidate)
            target = tree / path.relative_to(candidate)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        (hermes / "config.yaml").write_text(json.dumps({
            "skills": {"external_dirs": [str(tree)] if caller else [], "disabled": disabled,
                       "template_vars": True, "inline_shell": False},
            "plugins": {"enabled": []}, "file_read_max_chars": 1500,
        }), encoding="utf-8")

        import hermes_cli.plugins as plugins

        stack.enter_context(patch.object(plugins.PluginManager, "discover_and_load", return_value=None))
        for name in ("discover_plugins", "start_background_plugin_discovery", "invoke_hook"):
            stack.enter_context(patch.object(plugins, name, return_value=[]))
        from agent import skill_utils as su
        from agent import prompt_builder as pb
        from tools import skills_tool as st, skills_tool_plugin as sp, skill_usage
        from tools.registry import registry

        stack.enter_context(patch.object(su, "get_project_skills_dirs", return_value=[]))
        for name in ("bump_use", "bump_view"):
            stack.enter_context(patch.object(skill_usage, name, return_value=None))
        for module in (st, sp):
            stack.enter_context(patch.object(module, "_mark_background_review_read", return_value=None))
        st._SKILLS_CACHE.clear()
        st.reset_skill_view_dedup()
        pb.clear_skills_system_prompt_cache(clear_snapshot=True)

        def view(name, file_path=None, task="writer-owner"):
            assert registry.get_entry("skill_view").handler is st._skill_view_with_bump
            return json.loads(registry.dispatch("skill_view", {"name": name, "file_path": file_path}, task_id=task))

        def body(payload, path):
            assert payload.get("success") and "content" in payload, payload
            expected = path.read_text(encoding="utf-8")
            if path.name == "SKILL.md":
                expected = expected.replace("${HERMES_SKILL_DIR}", str(path.parent))
            assert payload["content"] == expected

        def unchanged(payload):
            assert payload["status"] == "unchanged" and payload["content_returned"] is False
            assert "content" not in payload

        prompt = pb.build_skills_system_prompt(
            available_tools={"skills_list", "skill_view", "read_file"}, available_toolsets={"skills", "file"})
        rows = re.findall(r"^    - ([^: \n]+): (.*)$", prompt, re.MULTILINE)
        expected = {ROOT} if caller else set(PATHS)
        assert len(rows) == len(expected) and {n for n, _ in rows} == expected
        found = st._find_all_skills()
        assert len(found) == len(expected) and {s["name"] for s in found} == expected
        listing = json.loads(registry.dispatch("skills_list", {}, task_id="writer-index"))
        assert listing["count"] == len(expected) and {s["name"] for s in listing["skills"]} == expected

        if case == "discovery":
            files = list(su.iter_skill_index_files(hermes / "skills", "SKILL.md"))
            assert len(files) == len({p.resolve() for p in files}) == 20
            assert {p.relative_to(tree).as_posix() for p in files} == set(PATHS.values())
            assert len({d for _, d in rows}) == 20
            for name, desc in rows:
                path = tree / PATHS[name]
                text = path.read_text(encoding="utf-8")
                fm, _ = su.parse_frontmatter(text)
                assert su.parse_frontmatter(text[:4000])[0] == fm
                assert fm["name"] == name and 0 < len(desc) <= 60
                assert desc == su.extract_skill_description(fm)
                loaded = view(name)
                body(loaded, path)
                if name == ROOT:
                    assert "the `HERMES_SKILL_DIR` placeholder" in loaded["content"]
                assert loaded["skill_dir"] == str(path.parent)
                assert loaded["path"] == str(path.relative_to(hermes / "skills"))
                assert loaded["metadata"] == fm["metadata"]
                if name in ENTRIES:
                    assert "<ReadBeforeWork>" in text and "</ReadBeforeWork>" in text
                    assert "When executing this" in text and "as Writer" in text
                    assert "next_offset" in text and "stop the affected action and report it" in text
                if name in PRODUCTION:
                    version = "1.1.0" if name in {"edit-article", "analyze-article"} else "1.0.0"
                    assert (fm["version"], fm["author"], fm["license"]) == (version, "CraftSamo", "MIT")
                    meta = fm["metadata"]["hermes"]
                    assert meta["category"] == "writing" and isinstance(meta["output"], str) and meta["output"]
                    assert isinstance(meta["form"], dict) and meta["form"]
                    assert all(isinstance(f["required"], bool) and f["label"] for f in meta["form"].values())
                    assert all(f"<{tag}>" in text for tag in ("Procedure", "QA", "Report"))
            assert "advice before drafting" in dict(rows)["consult-writer"].lower()
            assert "form" not in view("consult-writer", task="advisory-shape")["metadata"]["hermes"]

        elif caller:
            assert set(su.get_external_skills_dirs()) == {tree}
            for name in ENTRIES:
                result = view(name)
                assert result.get("success") is False and "content" not in result, result
                assert "disabled" in result["error"] or "not found" in result["error"].lower()
                if name == "consult-writer":
                    assert "disabled" in result["error"]
            for branch in ("index", "prose", "script"):
                relative = f"references/acceptance/{branch}.md"
                body(view(ROOT, relative), tree / relative)
            body(view(ROOT), tree / "SKILL.md")
            missing = tree / "references/acceptance/script.md"
            missing.unlink()
            result = view(ROOT, "references/acceptance/script.md")
            assert result.get("success") is False and "content" not in result
            assert "never accept on resemblance" in (tree / "references/acceptance/index.md").read_text()

        elif case == "owner_reads":
            body(view("consult-writer"), tree / PATHS["consult-writer"])
            body(view(ROOT), tree / PATHS[ROOT])
            body(view("write-document"), tree / PATHS["write-document"])
            unchanged(view("write-document"))
            for name, relative in (("write-document", "references/readme.md"),
                                   ("write-script", None), ("write-script", "references/narration.md"),
                                   ("write-document", "references/guide.md")):
                path = tree / PATHS[name]
                body(view(name, relative), path.parent / relative if relative else path)
                unchanged(view(name, relative))
            # A briefing-only form read cannot recursively load/execute the kernel.
            before = len(writes)
            with patch.object(st, "skill_view", wraps=st.skill_view) as calls:
                form = view("write-document", task="readonly-advice")
                body(form, tree / PATHS["write-document"])
                assert calls.call_count == 1 and len(writes) == before
            clause = " ".join(form["content"].split())
            assert "When executing this leaf as Writer" in clause
            assert "A Client reading a form or reference for briefing does not execute this procedure" in clause
            body(view(ROOT, task="readonly-advice"), tree / PATHS[ROOT])

            from agent.conversation_compression import _reset_read_dedup_caches
            from tools import file_tools as ft, file_tools_paths as fp, skill_manager_guards
            from tools.environments.local import LocalEnvironment
            from tools.file_operations import ShellFileOperations

            backend = ShellFileOperations(object.__new__(LocalEnvironment), cwd=str(home))
            backend.env.cwd = str(home)
            assert backend._native_read_enabled()
            stack.enter_context(patch.object(ft, "_get_file_ops", return_value=backend))
            stack.enter_context(patch.object(fp, "_terminal_env_type_for_task", return_value="local"))
            stack.enter_context(patch.object(skill_manager_guards, "mark_background_review_skill_read", return_value=None))

            def read(offset=1):
                assert registry.get_entry("read_file").handler is ft._handle_read_file
                return json.loads(registry.dispatch("read_file", {"path": str(tree / "SKILL.md"), "offset": offset}, task_id="writer-owner"))

            # Discarded earlier bodies are NOT recovered by an unchanged stub.
            unchanged(view(ROOT))
            for recovery in range(2):
                chunks, offset = [], 1
                while True:
                    page = read(offset)
                    assert not page.get("error") and "content" in page
                    chunks.extend(re.sub(r"^\d+\|", "", page["content"], flags=re.MULTILINE).splitlines())
                    if not page.get("truncated"):
                        break
                    assert page["next_offset"] > offset
                    offset = page["next_offset"]
                assert offset > 1, "Exercise real char-budget truncation, not artificial ranges"
                assert chunks == (tree / "SKILL.md").read_text(encoding="utf-8").splitlines()
                unchanged(read())
                blocked = read()
                assert "BLOCKED" in blocked["error"] and "content" not in blocked
                assert "stop and report the missing body" in (tree / "SKILL.md").read_text()
                _reset_read_dedup_caches("writer-owner")
                body(view(ROOT), tree / "SKILL.md")
                body(view("write-document"), tree / PATHS["write-document"])
        assert not violations, violations


if __name__ == "__main__":
    assert len(sys.argv) == 7 and sys.argv[1] == "--child"
    _child(sys.argv[2], *(Path(p).resolve() for p in sys.argv[3:6]), json.loads(sys.argv[6]))
    print(json.dumps({"case": sys.argv[2], "passed": True}))
