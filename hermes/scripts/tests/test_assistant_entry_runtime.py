"""Opt-in, offline integration with the paired candidate and real Hermes source.

Run with the Hermes venv and source PYTHONPATH, plus HERMES_PRIVATE_ROOT pointing
at the private candidate checkout. An absent variable skips; an invalid explicit
path fails. Nothing falls back to ~/.config/private or a live Hermes profile.

Only assistant-pipeline Markdown is copied, never config/persona/runtime state.
Writer acceptance is an explicit synthetic external fixture: its absence is a
load failure, not permission to waive acceptance. Portable topology validation
owns configured external-root/ownership exceptions separately; these tests do
not disable or replace the real scanner, index, lookup, or read-dedup paths.

Each case runs in a fresh child with HOME/HERMES_HOME set before Hermes imports.
Only plugin discovery/hooks, usage bookkeeping and terminal backend acquisition
are isolated. The file backend is the real native ShellFileOperations reader.
No agent, provider, chat, credential, session DB or model is started. In particular,
local transcript pruning is NOT evidence about Codex's hidden provider context.

Optional HERMES_ENTRY_ARTIFACT_DIR writes the rendered index and a small probe
manifest outside the repository, under the OS temporary directory only. They
are inputs for separate fresh-context selection probes, not chat-test results.
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


DOMAINS = ("engineering", "creative", "writing", "research", "search", "marketing")
MODES = {"plan": "plan", "execute": "execute", "qa": "quality-assurance"}
ENTRIES = {"chat-assistant"} | {
    f"{mode}-assistant-{domain}" for mode in MODES for domain in DOMAINS
}
EXPECTED = ENTRIES | {"assistant-pipeline"}
ALLOW = {"skills_list", "skill_view", "read_file"}
CASES = (
    "discovery", "entry_reads", "contained_paths", "writer_present",
    "writer_missing_skill", "writer_missing_file", "dedup_reset",
    "proactive_prune", "index_cache", "relocation",
)
TREE = Path("hermes/profiles/assistant/skills/assistant-pipeline")


@pytest.mark.parametrize("case", CASES)
def test_assistant_entry_runtime(case):
    private = os.environ.get("HERMES_PRIVATE_ROOT")
    if private is None:
        pytest.skip("Set HERMES_PRIVATE_ROOT to the paired private candidate for runtime integration")
    candidate = Path(private).resolve() if private else None
    if candidate is None or not (candidate / TREE / "SKILL.md").is_file():
        pytest.fail("HERMES_PRIVATE_ROOT must name an existing paired candidate checkout")
    # Resolve source without importing Hermes (imports can capture HOME).
    roots = [Path(p).resolve() for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    source = next((p for p in roots if (p / "agent/skill_utils.py").is_file()), None)
    if source is None:
        pytest.fail("PYTHONPATH must explicitly include the Hermes source checkout")
    with tempfile.TemporaryDirectory(prefix="assistant-entry-runtime-") as directory:
        sandbox = Path(directory).resolve()
        home = sandbox / "home"
        home.mkdir()
        hermes_home = home / ".hermes"
        hermes_home.mkdir()
        # Do not inherit tokens, config selectors, plugin paths or session IDs.
        env = {
            "HOME": str(home), "HERMES_HOME": str(hermes_home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "TMPDIR": str(sandbox), "PATH": "/usr/bin:/bin",
            "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "TERMINAL_ENV": "local", "TERMINAL_CWD": str(home),
            "HERMES_NATIVE_FILE_READ": "1", "HERMES_PLATFORM": "telegram",
            "LANG": "en_US.UTF-8",
        }
        result = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), "--child",
             case, str(sandbox), str(candidate / TREE), str(source)],
            cwd=home, env=env, text=True, capture_output=True, timeout=120,
        )
        # Child emits only public case/name/count diagnostics, never private bodies.
        assert result.returncode == 0, result.stdout
        report = json.loads(result.stdout)
        assert report == {"case": case, "assistant_names": sorted(EXPECTED), "count": 20}
        if case == "discovery" and "HERMES_ENTRY_ARTIFACT_DIR" in os.environ:
            output = Path(os.environ["HERMES_ENTRY_ARTIFACT_DIR"]).resolve()
            temp_root = Path(tempfile.gettempdir()).resolve()
            public = Path(__file__).resolve().parents[3]
            assert output.is_relative_to(temp_root), "Artifacts must stay in OS temporary storage"
            assert not output.is_relative_to(public) and not output.is_relative_to(candidate)
            assert output.is_dir(), "Artifact directory must already exist"
            for name in ("assistant-entry-index.txt", "assistant-entry-cases.json"):
                target = output / name
                assert not target.is_symlink(), "Refuse artifact symlinks"
                shutil.copyfile(sandbox / name, target)


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
        tree = skills / "assistant-pipeline"
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

        external = []
        stack.enter_context(patch.object(su, "get_external_skills_dirs", side_effect=lambda: list(external)))
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
            assert len(files) == 20
            assert {su.parse_frontmatter(p.read_text(encoding="utf-8"))[0]["name"] for p in files} == EXPECTED
            found = st._find_all_skills()
            assert len(found) == 20 and {s["name"] for s in found} == EXPECTED
            prompt = index()
            visible = rows(prompt)
            assert len(visible) == 20 and set(visible) == EXPECTED
            assert len(set(visible.values())) == 20
            for name, desc in visible.items():
                assert 0 < len(desc) <= 60
                path = tree / ("SKILL.md" if name == "assistant-pipeline" else f"{name}/SKILL.md")
                fm, _ = su.parse_frontmatter(path.read_text(encoding="utf-8"))
                assert desc == su.extract_skill_description(fm)
                if name in ENTRIES:
                    assert name.split("-", 1)[0].lower() in desc.lower()
                    if name != "chat-assistant":
                        assert name.rsplit("-", 1)[1] in desc.lower()
            listing = json.loads(st.skills_list())
            assert listing["count"] == 20 and {s["name"] for s in listing["skills"]} == EXPECTED
            return prompt

        try:
            if case == "discovery":
                prompt = check_discovery()
                (sandbox / "assistant-entry-index.txt").write_text(prompt + "\n", encoding="utf-8")
                (sandbox / "assistant-entry-cases.json").write_text(json.dumps({
                    "kind": "selection-probe-inputs-not-chat-evidence", "allow": sorted(ALLOW),
                    "cases": [{"entry": name, "mode": name.split("-", 1)[0],
                               "domain": None if name == "chat-assistant" else name.rsplit("-", 1)[1]}
                              for name in sorted(ENTRIES)],
                    "runtime_cases": list(CASES), "assistant_count": 20,
                }, indent=2) + "\n", encoding="utf-8")

            elif case == "entry_reads":
                # Direct child loads do not auto-load dependencies. Read them explicitly,
                # exactly as a caller following each entry's declared dependency calls.
                for name in sorted(ENTRIES):
                    path = tree / name / "SKILL.md"
                    payload = json.loads(st.skill_view(name))
                    body_matches(payload, path, rendered=True)
                    assert payload["skill_dir"] == str(path.parent)
                    assert "${HERMES_SKILL_DIR}" not in payload["content"]
                    assert str(path.parent) in payload["content"]
                    body_matches(view("assistant-pipeline", task=name), tree / "SKILL.md", rendered=True)
                    if name != "chat-assistant":
                        common = f"references/{MODES[name.split('-', 1)[0]]}/index.md"
                        body_matches(view("assistant-pipeline", common, name), tree / common)
                    refs = sorted((path.parent / "references").rglob("*.md"))
                    if refs:
                        relative = str(refs[0].relative_to(path.parent))
                        body_matches(view(name, relative, name), refs[0])

            elif case == "contained_paths":
                # Depth is not a lookup limit; the file must remain in the named skill.
                deep = max(tree.rglob("*.md"), key=lambda p: len(p.relative_to(tree).parts))
                assert len(deep.relative_to(tree).parts) >= 4
                relative = str(deep.relative_to(tree))
                body_matches(json.loads(st.skill_view("assistant-pipeline", relative)), deep)
                synthetic = tree / "references/depth/one/two/three/four/five/doc.md"
                synthetic.parent.mkdir(parents=True)
                synthetic.write_text("Synthetic deeply contained body.\n", encoding="utf-8")
                body_matches(view("assistant-pipeline", str(synthetic.relative_to(tree))), synthetic)
                outside = skills / "outside.md"
                outside.write_text("Synthetic outside body.\n", encoding="utf-8")
                (tree / "escape.md").symlink_to(outside)
                for bad in ("../outside.md", str(outside), "escape.md"):
                    result = json.loads(st.skill_view("assistant-pipeline", bad))
                    assert result.get("success") is False and "content" not in result
                # Nested references aren't all advertised by linked_files (flat glob),
                # but the actual contained file_path read above must work.
                result = json.loads(st.skill_view("assistant-pipeline", "missing/deep/doc.md"))
                assert result.get("success") is False

            elif case.startswith("writer_"):
                qa = view("qa-assistant-writing")
                body_matches(qa, tree / "qa-assistant-writing/SKILL.md", rendered=True)
                calls = re.findall(r'skill_view\(name="([^"]+)", file_path="([^"]+)"\)', qa["content"])
                writer_calls = [(name, path) for name, path in calls if name == "writer-pipeline"]
                assert writer_calls, "QA must declare a Writer acceptance dependency"
                writer = sandbox / "external/writer-pipeline"
                if case != "writer_missing_skill":
                    writer.mkdir(parents=True)
                    (writer / "SKILL.md").write_text(
                        "---\nname: writer-pipeline\ndescription: Synthetic shared acceptance fixture.\n---\n"
                        "# Synthetic Writer reference root\n", encoding="utf-8",
                    )
                    external.append(writer)
                if case == "writer_present":
                    paths = {p for _, p in writer_calls} | {
                        "references/acceptance/prose.md", "references/acceptance/script.md",
                    }
                    for relative in paths:
                        target = writer / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(f"# Synthetic acceptance\nFixture branch: {relative}\n", encoding="utf-8")
                        body_matches(view("writer-pipeline", relative), target)
                    assert set(rows(index())) == EXPECTED | {"writer-pipeline"}
                    for branch in ("prose", "script"):
                        relative = f"references/{branch}.md"
                        body_matches(view("qa-assistant-writing", relative), tree / "qa-assistant-writing" / relative)
                else:
                    for name, relative in writer_calls:
                        result = view(name, relative)
                        assert result.get("success") is False and "content" not in result
                    assert "BLOCKED" in qa["content"]
                    # This proves unresolved tool loads + the documented stop policy,
                    # not that an LLM obeyed the policy or performed acceptance.

            elif case in {"dedup_reset", "proactive_prune"}:
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
                task = "isolated-recovery"
                path = tree / "SKILL.md"
                first = view("assistant-pipeline", task=task)
                body_matches(first, path, rendered=True)
                repeat = view("assistant-pipeline", task=task)
                assert repeat["status"] == "unchanged" and repeat["content_returned"] is False
                assert "content" not in repeat

                if case == "proactive_prune":
                    from agent.context_compressor import ContextCompressor

                    call = {"id": "load-kernel", "type": "function", "function": {
                        "name": "skill_view", "arguments": json.dumps({"name": "assistant-pipeline"}),
                    }}
                    messages = [
                        {"role": "user", "content": "Synthetic unrelated request."},
                        {"role": "assistant", "content": None, "tool_calls": [call]},
                        {"role": "tool", "tool_call_id": "load-kernel", "content": json.dumps(first)},
                    ]
                    # Control: a just-loaded skill is protected. Aged >10 messages
                    # then exercises real deterministic proactive pruning, no summary model.
                    compressor = ContextCompressor(
                        model="offline-fixture", config_context_length=100000,
                        protect_first_n=0, protect_last_n=2, quiet_mode=True,
                        proactive_prune_tokens=1, proactive_prune_min_result_chars=200,
                        proactive_prune_min_reclaim_tokens=1,
                    )
                    assert compressor.prune_tool_results_only(messages, current_tokens=1000)[1] == 0
                    messages += [{"role": "user" if i % 2 == 0 else "assistant",
                                  "content": f"Synthetic unrelated turn {i}."} for i in range(14)]
                    pruned, count = compressor.prune_tool_results_only(messages, current_tokens=1000)
                    assert count == 1 and pruned[2]["content"] != messages[2]["content"]
                    assert "SKILL_PRUNED" in pruned[2]["content"]
                    assert view("assistant-pipeline", task=task)["status"] == "unchanged"

                def read():
                    assert registry.get_entry("read_file").handler is ft._handle_read_file
                    return json.loads(registry.dispatch("read_file", {"path": str(path)}, task_id=task))

                def assert_file_body(payload):
                    assert not payload.get("error") and not payload.get("truncated")
                    content = re.sub(r"^\d+\|", "", payload["content"], flags=re.MULTILINE)
                    assert content.rstrip("\n") == path.read_text(encoding="utf-8").rstrip("\n"), "Canonical read must recover full body"

                assert_file_body(read())
                assert view("assistant-pipeline", task=task)["status"] == "unchanged"
                reread = read()
                assert reread["status"] == "unchanged" and reread["content_returned"] is False
                assert "BLOCKED" in read()["error"]
                _reset_read_dedup_caches(task)
                body_matches(view("assistant-pipeline", task=task), path, rendered=True)
                assert_file_body(read())
                assert read()["status"] == "unchanged"
                _reset_read_dedup_caches(task)
                tracking._read_tracker.clear()

            elif case == "index_cache":
                before = check_discovery()
                added = tree / "synthetic-new-entry/SKILL.md"
                added.parent.mkdir()
                added.write_text("---\nname: synthetic-new-entry\ndescription: Synthetic cache invalidation probe.\n---\n# Probe\n", encoding="utf-8")
                assert added in set(su.iter_skill_index_files(skills, "SKILL.md"))
                assert index() == before, "In-process prompt cache remains stale on disk additions"
                pb.clear_skills_system_prompt_cache(clear_snapshot=True)
                assert set(rows(index())) == EXPECTED | {"synthetic-new-entry"}

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
                    for name in sorted(ENTRIES):
                        target = moved_home / "skills/assistant-pipeline" / name / "SKILL.md"
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
    # Do not let assertion rewriting or traceback locals expose candidate text.
    import traceback

    try:
        assert len(sys.argv) == 6 and sys.argv[1] == "--child"
        _child(sys.argv[2], *(Path(p).resolve() for p in sys.argv[3:]))
        print(json.dumps({"case": sys.argv[2], "assistant_names": sorted(EXPECTED), "count": 20}))
    except BaseException as error:
        frames = [(frame.f_code.co_name, line) for frame, line in traceback.walk_tb(error.__traceback__)]
        print(json.dumps({"case": sys.argv[2], "error_type": type(error).__name__, "frames": frames}))
        sys.exit(1)
