"""Opt-in, offline integration with the real Hermes source and the public
Searcher candidate docs (root kernel + 3 flat units), no private checkout.

Empty PYTHONPATH skips (offline default); an explicit PYTHONPATH lacking a
real Hermes source checkout fails. The candidate tree resolves relative to
this file in the public repo, never an absolute /Users path or live HOME.
Missing or unexpected candidate instructions fail rather than skip.

Only searcher-pipeline Markdown is copied, never config/persona/runtime
state; no synthetic SKILL.md fixtures land in the tracked tree - everything
lives under a temporary directory for the run.

Each case runs in a fresh child with HOME/HERMES_HOME set before Hermes
imports. Only plugin discovery/hooks and usage bookkeeping are mocked; the
scanner, index, lookup, read-dedup paths, and native file-read backend are
real - structural fixtures, not proof of model behavior.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import pytest


CHILDREN = ("lookup-searcher", "sweep-searcher", "hunt-searcher")
EXPECTED = {"searcher-pipeline"} | set(CHILDREN)
ALLOW = {"skills_list", "skill_view", "read_file"}
CASES = ("discovery", "reads_and_reuse", "recovery", "relocation")
TREE = Path("hermes/profiles/searcher/skills/searcher-pipeline")


@pytest.mark.parametrize("case", CASES)
def test_searcher_entry_runtime(case):
    raw = os.environ.get("PYTHONPATH", "")
    if not raw:
        pytest.skip("Set PYTHONPATH to the Hermes source checkout for runtime integration")
    roots = [Path(p).resolve() for p in raw.split(os.pathsep) if p]
    source = next((p for p in roots if (p / "agent/skill_utils.py").is_file()), None)
    if source is None:
        pytest.fail("PYTHONPATH must explicitly include the Hermes source checkout")

    repo_root = Path(__file__).resolve().parents[3]
    candidate_tree = (repo_root / TREE).resolve()
    assert (candidate_tree / "SKILL.md").is_file() and all(
        (candidate_tree / child / "SKILL.md").is_file() for child in CHILDREN
    ), "Searcher must have the kernel and all three entries"
    docs = sorted(candidate_tree.rglob("*.md"))
    assert len(docs) == 4, "Searcher must have exactly four instruction documents"

    with tempfile.TemporaryDirectory(prefix="searcher-entry-runtime-") as directory:
        sandbox = Path(directory).resolve()
        home = sandbox / "home"
        home.mkdir()
        hermes_home = home / ".hermes"
        hermes_home.mkdir()
        # Do not inherit tokens, config selectors, plugin paths or session IDs.
        env = {
            "HOME": str(home), "HERMES_HOME": str(hermes_home), "TMPDIR": str(sandbox),
            "XDG_CONFIG_HOME": str(home / ".config"), "XDG_CACHE_HOME": str(home / ".cache"),
            "PATH": "/usr/bin:/bin", "PYTHONPATH": str(source), "LANG": "en_US.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "TERMINAL_ENV": "local",
            "TERMINAL_CWD": str(home), "HERMES_NATIVE_FILE_READ": "1",
            "HERMES_PLATFORM": "telegram",
        }
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--child",
             case, str(sandbox), str(candidate_tree), str(source)],
            cwd=home, env=env, text=True, capture_output=True, timeout=120,
        )
        # Child emits only public case/name/count diagnostics, never file bodies.
        assert result.returncode == 0, result.stdout
        report = json.loads(result.stdout)
        assert report == {"case": case, "searcher_names": sorted(EXPECTED), "count": 4}


def _child(case, sandbox, candidate_tree, source):
    import logging
    import socket
    from contextlib import ExitStack
    from unittest.mock import patch

    logging.disable(logging.CRITICAL)
    home = sandbox / "home"
    assert Path.home().resolve() == home
    assert Path(os.environ["HERMES_HOME"]).resolve() == home / ".hermes"
    assert not any(name == "agent" or name.startswith("tools.") for name in sys.modules)

    def deny_network(*args, **kwargs):
        raise AssertionError("Network is forbidden in candidate integration")

    # Defense in depth: even dependencies bypassing the patched socket methods
    # cannot connect/bind, spawn a command, or open live user files.
    code_roots = (source, Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve(),
                  Path("/usr"), Path("/System/Library"), Path("/Library/Apple"))

    def audit(event, args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "socket.sendto",
                     "subprocess.Popen", "os.system", "os.posix_spawn"}:
            raise AssertionError("External execution/network forbidden")
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1:3]
            write = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            )
            if path.is_relative_to(sandbox):
                return
            if write:
                raise AssertionError("Write outside isolated temporary HOME forbidden")
            if path.is_relative_to(candidate_tree) and path.suffix == ".md":
                return
            if path.name in {".env", "auth.json", "config.yaml", "SOUL.md"}:
                raise AssertionError("Non-fixture configuration/credentials forbidden")
            if any(path.is_relative_to(root) for root in code_roots):
                return
            raise AssertionError("Read outside candidate docs/source/runtime forbidden")

    sys.addaudithook(audit)
    with ExitStack() as stack:
        for target, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"),
                             (socket.socket, "sendto"), (socket, "create_connection"),
                             (socket, "getaddrinfo")):
            stack.enter_context(patch.object(target, name, deny_network))

        skills = home / ".hermes/skills"
        tree = skills / "searcher-pipeline"
        docs = sorted(candidate_tree.rglob("*.md"))
        assert len(docs) == 4, "Candidate tree must hold exactly the root + 3 flat children"
        for path in docs:
            assert not path.is_symlink() and path.resolve().is_relative_to(candidate_tree)
            target = tree / path.relative_to(candidate_tree)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        assert (tree / "SKILL.md").is_file()
        for child in CHILDREN:
            assert (tree / child / "SKILL.md").is_file()
        # Synthetic, not copied from any private config.
        (home / ".hermes/config.yaml").write_text(
            "skills:\n  external_dirs: []\n  disabled: []\n  template_vars: true\n"
            "  inline_shell: false\nplugins:\n  enabled: []\n", encoding="utf-8",
        )

        import hermes_cli.plugins as plugins

        stack.enter_context(patch.object(plugins.PluginManager, "discover_and_load", return_value=None))
        stack.enter_context(patch.object(plugins, "discover_plugins", return_value=None))
        stack.enter_context(patch.object(plugins, "start_background_plugin_discovery", return_value=None))
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

        def index():
            return pb.build_skills_system_prompt(available_tools=ALLOW, available_toolsets={"skills", "file"})

        def rows(prompt):
            return dict(re.findall(r"^    - ([^: \n]+): (.*)$", prompt, re.MULTILINE))

        def view(name, file_path=None, task="entry-runtime"):
            assert registry.get_entry("skill_view").handler is st._skill_view_with_bump
            return json.loads(registry.dispatch("skill_view",
                {"name": name, "file_path": file_path}, task_id=task,
            ))

        def body_matches(payload, path, *, rendered=False):
            assert payload.get("success"), "Expected real skill body"
            expected = path.read_text(encoding="utf-8")
            if rendered:
                expected = expected.replace("${HERMES_SKILL_DIR}", str(path.parent))
            assert payload.get("content") == expected, "Body must match the candidate document"

        def check_discovery():
            files = list(su.iter_skill_index_files(skills, "SKILL.md"))
            assert len(files) == 4
            assert {su.parse_frontmatter(p.read_text(encoding="utf-8"))[0]["name"] for p in files} == EXPECTED
            found = st._find_all_skills()
            assert len(found) == 4 and {s["name"] for s in found} == EXPECTED
            prompt = index()
            visible = rows(prompt)
            assert len(visible) == 4 and set(visible) == EXPECTED
            assert len(set(visible.values())) == 4
            for name, desc in visible.items():
                assert 0 < len(desc) <= 60
                path = tree / ("SKILL.md" if name == "searcher-pipeline" else f"{name}/SKILL.md")
                fm, _ = su.parse_frontmatter(path.read_text(encoding="utf-8"))
                assert desc == su.extract_skill_description(fm)
                if name in CHILDREN:
                    assert name.split("-", 1)[0].lower() in desc.lower()
            listing = json.loads(st.skills_list())
            assert listing["count"] == 4 and {s["name"] for s in listing["skills"]} == EXPECTED
            return prompt

        try:
            if case == "discovery":
                check_discovery()

            elif case == "reads_and_reuse":
                # Direct child loads render their own ${HERMES_SKILL_DIR}, not the kernel's.
                for name in CHILDREN:
                    path = tree / name / "SKILL.md"
                    payload = json.loads(st.skill_view(name))
                    body_matches(payload, path, rendered=True)
                    assert payload["skill_dir"] == str(path.parent)
                    assert "${HERMES_SKILL_DIR}" not in payload["content"]

                task = "unit-switch"
                root_path = tree / "SKILL.md"
                body_matches(view("searcher-pipeline", task=task), root_path, rendered=True)
                repeat_root = view("searcher-pipeline", task=task)
                assert repeat_root["status"] == "unchanged" and repeat_root["content_returned"] is False

                # Explicit, scripted unit switch in the same task: authorized read of a
                # second unit, not evidence of model behavior - state only.
                lookup_first = view("lookup-searcher", task=task)
                body_matches(lookup_first, tree / "lookup-searcher/SKILL.md", rendered=True)
                sweep_first = view("sweep-searcher", task=task)
                body_matches(sweep_first, tree / "sweep-searcher/SKILL.md", rendered=True)
                assert sweep_first["content"] != lookup_first["content"]

                root_again = view("searcher-pipeline", task=task)
                assert root_again["status"] == "unchanged" and root_again["content_returned"] is False

                lookup_again = view("lookup-searcher", task=task)
                assert lookup_again["status"] == "unchanged" and lookup_again["content_returned"] is False

            elif case == "recovery":
                from agent.conversation_compression import _reset_read_dedup_caches
                from tools import file_tools as ft
                from tools import file_tools_paths as fp
                from tools import skill_manager_guards
                from tools.environments.local import LocalEnvironment
                from tools.file_operations import ShellFileOperations

                # No terminal environment creation/cleanup thread. The real native
                # backend reads the actual temp file, retaining pagination/dedup.
                backend = ShellFileOperations(object.__new__(LocalEnvironment), cwd=str(home))
                backend.env.cwd = str(home)
                assert backend._native_read_enabled()
                stack.enter_context(patch.object(ft, "_get_file_ops", return_value=backend))
                stack.enter_context(patch.object(fp, "_terminal_env_type_for_task", return_value="local"))
                stack.enter_context(patch.object(skill_manager_guards, "mark_background_review_skill_read", return_value=None))

                def read(path, task, **extra):
                    assert registry.get_entry("read_file").handler is ft._handle_read_file
                    args = {"path": str(path), **extra}
                    return json.loads(registry.dispatch("read_file", args, task_id=task))

                def strip_lines(content):
                    return re.sub(r"^\d+\|", "", content, flags=re.MULTILINE)

                def assert_file_body(payload, path):
                    assert not payload.get("error") and not payload.get("truncated")
                    content = strip_lines(payload["content"])
                    assert content.rstrip("\n") == path.read_text(encoding="utf-8").rstrip("\n")

                root_path = tree / "SKILL.md"
                # Real tools can exhaust recovery. This is not model-compliance evidence.
                for name in ("searcher-pipeline",) + CHILDREN:
                    path = tree / ("SKILL.md" if name == "searcher-pipeline" else f"{name}/SKILL.md")
                    task = f"recovery-{name}"
                    body_matches(view(name, task=task), path, rendered=True)
                    repeat = view(name, task=task)
                    assert repeat["status"] == "unchanged" and repeat["content_returned"] is False

                    assert_file_body(read(path, task), path)
                    assert view(name, task=task)["status"] == "unchanged"
                    reread = read(path, task)
                    assert reread["status"] == "unchanged" and reread["content_returned"] is False
                    assert "BLOCKED" in read(path, task)["error"]
                    _reset_read_dedup_caches(task)
                    body_matches(view(name, task=task), path, rendered=True)
                    assert_file_body(read(path, task), path)
                    _reset_read_dedup_caches(task)

                missing = json.loads(st.skill_view("searcher-pipeline", "missing/kernel/doc.md"))
                assert missing.get("success") is False and "content" not in missing

                # A chosen line limit uses a textual offset hint; structured
                # next_offset is returned by the character-budget cap instead.
                config = home / ".hermes/config.yaml"
                config.write_text(config.read_text() + "file_read_max_chars: 1200\n", encoding="utf-8")
                ft._max_read_chars_cached = None
                assert ft._get_max_read_chars() == 1200
                page_task = "recovery-pagination"
                lines, offset, pages = [], 1, 0
                while True:
                    page = read(root_path, page_task, offset=offset)
                    assert not page.get("error")
                    # Split while line-number prefixes still preserve a blank
                    # final line at a character-budget page boundary.
                    lines.extend(strip_lines(line) for line in page["content"].splitlines())
                    pages += 1
                    if not page.get("truncated"):
                        break
                    assert page["next_offset"] > offset
                    offset = page["next_offset"]
                assert pages > 1
                # Native numbering preserves the final newline as an empty line.
                assert "\n".join(lines) == root_path.read_text(encoding="utf-8")
                _reset_read_dedup_caches(page_task)

            elif case == "relocation":
                check_discovery()
                from hermes_constants import set_hermes_home_override, reset_hermes_home_override

                moved_home = sandbox / "moved-namespace"
                moved_home.mkdir()
                shutil.move(str(skills), str(moved_home / "skills"))
                token = set_hermes_home_override(str(moved_home))
                try:
                    assert set(rows(index())) == EXPECTED
                    assert {s["name"] for s in st._find_all_skills()} == EXPECTED
                    for name in CHILDREN:
                        target = moved_home / "skills/searcher-pipeline" / name / "SKILL.md"
                        result = view(name, task="moved-namespace-only")
                        body_matches(result, target, rendered=True)
                        assert result["skill_dir"] == str(target.parent)
                        assert str(tree) not in result["content"]
                finally:
                    pb.clear_skills_system_prompt_cache(clear_snapshot=True)
                    reset_hermes_home_override(token)
            else:
                raise AssertionError("Unknown test case")
        finally:
            st.reset_skill_view_dedup()
            st._SKILLS_CACHE.clear()
            pb.clear_skills_system_prompt_cache(clear_snapshot=True)


if __name__ == "__main__":
    # Do not let assertion rewriting or traceback locals expose fixture text.
    import traceback

    try:
        assert len(sys.argv) == 6 and sys.argv[1] == "--child"
        _child(sys.argv[2], *(Path(p).resolve() for p in sys.argv[3:]))
        print(json.dumps({"case": sys.argv[2], "searcher_names": sorted(EXPECTED), "count": 4}))
    except BaseException as error:
        frames = [(frame.f_code.co_name, line) for frame, line in traceback.walk_tb(error.__traceback__)]
        print(json.dumps({"case": sys.argv[2], "error_type": type(error).__name__, "frames": frames}))
        sys.exit(1)
