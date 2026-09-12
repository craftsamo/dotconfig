"""Offline integration with the current public candidate and real Hermes source.

Run with the provisioned Hermes venv and source PYTHONPATH. The Marketer tree
comes from this test's own checkout, not a private overlay or live profile.
Only marketer-pipeline Markdown is copied, never config/persona/runtime state.

Each case runs in a fresh child with HOME/HERMES_HOME set before Hermes imports.
Only plugin discovery/hooks, usage bookkeeping and terminal backend acquisition
are isolated; the file backend is the real native ShellFileOperations reader. No
agent, provider, chat, credential, session DB or model is started. Assertions
exercise the actual scanner/index/lookup/read-dedup contracts, never a
simulated model turn or LLM entry-selection outcome.
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


# Split, flat entries: no mode/domain matrix like the Assistant pipeline.
ENTRIES = {"plan-marketer", "build-marketer", "qa-marketer", "analyze-marketer"}
EXPECTED = ENTRIES | {"marketer-pipeline"}
ALLOW = {"skills_list", "skill_view", "read_file"}
CASES = ("discovery", "entry_reads", "contained_paths", "dedup_reset", "index_cache")
TREE = Path("hermes/profiles/marketer/skills/marketer-pipeline")
# Each entry is its mode procedure; only state and platforms stay shared.
OWN_REF = {"build-marketer": "references/draft.md", "qa-marketer": "references/saved-draft.md"}


@pytest.mark.parametrize("case", CASES)
def test_marketer_entry_runtime(case):
    candidate = Path(__file__).resolve().parents[3]
    assert (candidate / TREE / "SKILL.md").is_file()
    # Resolve source without importing Hermes (imports can capture HOME).
    roots = [Path(p).resolve() for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    source = next((p for p in roots if (p / "agent/skill_utils.py").is_file()), None)
    if source is None:
        pytest.fail("PYTHONPATH must explicitly include the Hermes source checkout")
    with tempfile.TemporaryDirectory(prefix="marketer-entry-runtime-") as directory:
        sandbox = Path(directory).resolve()
        home = sandbox / "home"
        home.mkdir()
        (home / ".hermes").mkdir()
        # Do not inherit tokens, config selectors, plugin paths or session IDs.
        env = {
            "HOME": str(home), "HERMES_HOME": str(home / ".hermes"),
            "XDG_CONFIG_HOME": str(home / ".config"), "XDG_CACHE_HOME": str(home / ".cache"),
            "TMPDIR": str(sandbox), "PATH": "/usr/bin:/bin",
            "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "TERMINAL_ENV": "local", "TERMINAL_CWD": str(home),
            "HERMES_NATIVE_FILE_READ": "1", "HERMES_PLATFORM": "telegram", "LANG": "en_US.UTF-8",
        }
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--child",
             case, str(sandbox), str(candidate / TREE), str(source)],
            cwd=home, env=env, text=True, capture_output=True, timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report == {"case": case, "marketer_names": sorted(EXPECTED), "count": 5}


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
        for name in ("connect", "connect_ex", "sendto"):
            stack.enter_context(patch.object(socket.socket, name, deny_network))
        for name in ("create_connection", "getaddrinfo"):
            stack.enter_context(patch.object(socket, name, deny_network))

        skills = home / ".hermes/skills"
        tree = skills / "marketer-pipeline"
        for path in candidate_tree.rglob("*.md"):
            assert not path.is_symlink() and path.resolve().is_relative_to(candidate_tree)
            target = tree / path.relative_to(candidate_tree)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        assert (tree / "SKILL.md").is_file()
        # Synthetic, not copied from either candidate's private config.
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
            return json.loads(registry.dispatch("skill_view", {"name": name, "file_path": file_path}, task_id=task))

        def body_matches(payload, path, *, rendered=False):
            assert payload.get("success"), "Expected real skill body"
            expected = path.read_text(encoding="utf-8")
            if rendered:
                expected = expected.replace("${HERMES_SKILL_DIR}", str(path.parent))
            assert payload.get("content") == expected, "Body must match the candidate document"

        def check_discovery():
            files = list(su.iter_skill_index_files(skills, "SKILL.md"))
            assert len(files) == 5
            assert {su.parse_frontmatter(p.read_text(encoding="utf-8"))[0]["name"] for p in files} == EXPECTED
            found = st._find_all_skills()
            assert len(found) == 5 and {s["name"] for s in found} == EXPECTED
            prompt = index()
            visible = rows(prompt)
            assert len(visible) == 5 and set(visible) == EXPECTED and len(set(visible.values())) == 5
            for name, desc in visible.items():
                assert 0 < len(desc) <= 60
                path = tree / ("SKILL.md" if name == "marketer-pipeline" else f"{name}/SKILL.md")
                fm, _ = su.parse_frontmatter(path.read_text(encoding="utf-8"))
                assert desc == su.extract_skill_description(fm)
                assert "skill" not in desc.lower(), "Split entry must not describe itself as a generic skill"
                if name != "marketer-pipeline":
                    assert name.split("-", 1)[0] in desc[:60].lower(), "Phase must be distinguishable up front"
            listing = json.loads(st.skills_list())
            assert listing["count"] == 5 and {s["name"] for s in listing["skills"]} == EXPECTED
            return prompt

        def phase_turn(entry, task):
            body_matches(view(entry, task=task), tree / entry / "SKILL.md", rendered=True)
            own_ref = OWN_REF.get(entry)
            if own_ref is None:
                return None
            own_view = view(entry, own_ref, task)
            body_matches(own_view, tree / entry / own_ref)
            return own_view

        try:
            if case == "discovery":
                check_discovery()

            elif case == "entry_reads":
                # A scripted sequence of real tool calls, not a simulated model
                # turn or evidence about LLM entry-selection.
                task = "scripted-followups"
                kernel = view("marketer-pipeline", task=task)
                body_matches(kernel, tree / "SKILL.md", rendered=True)
                phase_turn("plan-marketer", task)
                build_own = phase_turn("build-marketer", task)
                assert "explicit approval" in build_own["content"].lower()
                qa_own = phase_turn("qa-marketer", task)
                assert "unpublished-state evidence" in qa_own["content"]
                phase_turn("analyze-marketer", task)
                # The harness retained the complete kernel, so later turns need
                # no kernel read. This assertion tests tool behavior, not intent.
                assert kernel["content"]
                assert view("marketer-pipeline", task=task)["content_returned"] is False

                # A target platform change only re-fetches the changed shared doc.
                note = view("marketer-pipeline", "references/platforms/note.md", "target-change")
                body_matches(note, tree / "references/platforms/note.md")
                zenn = view("marketer-pipeline", "references/platforms/zenn.md", "target-change")
                body_matches(zenn, tree / "references/platforms/zenn.md")
                assert note["content"] != zenn["content"]
                repeat_note = view("marketer-pipeline", "references/platforms/note.md", "target-change")
                assert repeat_note["content_returned"] is False

            elif case == "contained_paths":
                deep = max(tree.rglob("*.md"), key=lambda p: len(p.relative_to(tree).parts))
                assert len(deep.relative_to(tree).parts) >= 3
                body_matches(json.loads(st.skill_view("marketer-pipeline", str(deep.relative_to(tree)))), deep)
                synthetic = tree / "references/depth/one/two/three/doc.md"
                synthetic.parent.mkdir(parents=True)
                synthetic.write_text("Synthetic deeply contained body.\n", encoding="utf-8")
                body_matches(view("marketer-pipeline", str(synthetic.relative_to(tree))), synthetic)
                outside = skills / "outside.md"
                outside.write_text("Synthetic outside body.\n", encoding="utf-8")
                (tree / "escape.md").symlink_to(outside)
                for name, bad in (
                    ("marketer-pipeline", "../outside.md"), ("marketer-pipeline", str(outside)),
                    ("marketer-pipeline", "escape.md"), ("marketer-pipeline", "missing/deep/doc.md"),
                    ("build-marketer", "references/missing-file.md"),
                ):
                    result = json.loads(st.skill_view(name, bad))
                    assert result.get("success") is False and "content" not in result

            elif case == "dedup_reset":
                from agent.conversation_compression import _reset_read_dedup_caches
                from tools import file_tools as ft
                from tools import file_tools_paths as fp
                from tools import file_tools_read_tracking as tracking
                from tools import skill_manager_guards
                from tools.environments.local import LocalEnvironment
                from tools.file_operations import ShellFileOperations

                # No terminal environment creation/cleanup thread. The real native
                # backend reads the actual temp file, retaining pagination/redaction.
                backend = ShellFileOperations(object.__new__(LocalEnvironment), cwd=str(home))
                backend.env.cwd = str(home)
                assert backend._native_read_enabled()
                stack.enter_context(patch.object(ft, "_get_file_ops", return_value=backend))
                stack.enter_context(patch.object(fp, "_terminal_env_type_for_task", return_value="local"))
                stack.enter_context(patch.object(skill_manager_guards, "mark_background_review_skill_read", return_value=None))

                def read_full(path, task):
                    assert registry.get_entry("read_file").handler is ft._handle_read_file
                    offset, chunks = 1, []
                    while True:
                        payload = json.loads(registry.dispatch("read_file", {"path": str(path), "offset": offset}, task_id=task))
                        assert not payload.get("error")
                        chunks.append(re.sub(r"^\d+\|", "", payload["content"], flags=re.MULTILINE))
                        if not payload.get("truncated"):
                            return "".join(chunks)
                        offset = payload["next_offset"]  # real hint only, never guessed or respelled

                task = "isolated-recovery"
                root_path = tree / "SKILL.md"
                child_ref = OWN_REF["build-marketer"]
                child_path = tree / "build-marketer" / child_ref

                body_matches(view("marketer-pipeline", task=task), root_path, rendered=True)
                body_matches(view("build-marketer", child_ref, task), child_path)
                # Root and child dedup independently: both were just loaded, so
                # both repeats are now unchanged with no content.
                for name, ref in (("marketer-pipeline", None), ("build-marketer", child_ref)):
                    repeat = view(name, ref, task)
                    assert repeat["status"] == "unchanged" and repeat["content_returned"] is False
                    assert "content" not in repeat

                assert read_full(root_path, task).rstrip("\n") == root_path.read_text(encoding="utf-8").rstrip("\n")
                assert read_full(child_path, task).rstrip("\n") == child_path.read_text(encoding="utf-8").rstrip("\n")
                assert view("marketer-pipeline", task=task)["status"] == "unchanged"
                reread = json.loads(registry.dispatch("read_file", {"path": str(root_path)}, task_id=task))
                assert reread["status"] == "unchanged" and reread["content_returned"] is False
                blocked = json.loads(registry.dispatch("read_file", {"path": str(root_path)}, task_id=task))
                assert "BLOCKED" in blocked["error"]

                _reset_read_dedup_caches(task)
                body_matches(view("marketer-pipeline", task=task), root_path, rendered=True)
                body_matches(view("build-marketer", child_ref, task), child_path)
                assert read_full(root_path, task).rstrip("\n") == root_path.read_text(encoding="utf-8").rstrip("\n")
                _reset_read_dedup_caches(task)
                tracking._read_tracker.clear()

            elif case == "index_cache":
                before = check_discovery()
                added = tree / "synthetic-new-entry/SKILL.md"
                added.parent.mkdir()
                added.write_text(
                    "---\nname: synthetic-new-entry\ndescription: Synthetic cache invalidation probe.\n---\n# Probe\n",
                    encoding="utf-8",
                )
                assert added in set(su.iter_skill_index_files(skills, "SKILL.md"))
                assert index() == before, "In-process prompt cache remains stale on disk additions"
                pb.clear_skills_system_prompt_cache(clear_snapshot=True)
                assert set(rows(index())) == EXPECTED | {"synthetic-new-entry"}
            else:
                raise AssertionError("Unknown test case")
        finally:
            st.reset_skill_view_dedup()
            st._SKILLS_CACHE.clear()
            pb.clear_skills_system_prompt_cache(clear_snapshot=True)


if __name__ == "__main__":
    # Do not let assertion rewriting or traceback locals expose candidate text.
    import traceback

    try:
        assert len(sys.argv) == 6 and sys.argv[1] == "--child"
        _child(sys.argv[2], *(Path(p).resolve() for p in sys.argv[3:]))
        print(json.dumps({"case": sys.argv[2], "marketer_names": sorted(EXPECTED), "count": 5}))
    except BaseException as error:
        frames = [(frame.f_code.co_name, line) for frame, line in traceback.walk_tb(error.__traceback__)]
        print(json.dumps({"case": sys.argv[2], "error_type": type(error).__name__, "frames": frames}))
        sys.exit(1)
