"""Offline mechanical tests of public Creator discovery and instruction reads.

Requires the provisioned Hermes venv and an explicit source PYTHONPATH. No private
root, live profile, agent, provider, model selection or media execution is used.
Each case starts a fresh child before Hermes imports, copying only Markdown from
the four candidate pipelines. Like test_assistant_entry_runtime, plugin hooks,
bookkeeping and terminal acquisition are isolated, not the scanner/read handlers.
Tool errors prove failed reads, not that an LLM obeys the documented stop policy.
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


HANDS = ("image-creator", "video-creator", "audio-creator")
ENTRIES = {"plan-creator", "build-creator", "qa-creator"}
CREATOR_NAMES = ENTRIES | {"creator-pipeline"}
ALLOW = {"skills_list", "skill_view", "read_file"}
CASES = (
    "discovery", "direct_qa", "subject_change_music", "subject_change_clip",
    "proposal_approval_phases", "hands_options", "hands_inline_format",
    "canonical_recovery", "migration_no_alias", "external_form",
)


@pytest.mark.parametrize("case", CASES)
def test_creator_entry_runtime_offline_mechanical(case):
    candidate = Path(__file__).resolve().parents[2]
    roots = [Path(p).resolve() for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    source = next((p for p in roots if (p / "agent/skill_utils.py").is_file()), None)
    if source is None:
        pytest.fail("PYTHONPATH must explicitly include the local Hermes source checkout")
    for profile in ("creator", *HANDS):
        assert (candidate / f"profiles/{profile}/skills/{profile}-pipeline/SKILL.md").is_file()
    with tempfile.TemporaryDirectory(prefix="creator-entry-runtime-") as directory:
        sandbox = Path(directory).resolve()
        home = sandbox / "home"
        hermes_home = home / ".hermes"
        hermes_home.mkdir(parents=True)
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
             case, str(sandbox), str(candidate), str(source)],
            cwd=home, env=env, text=True, capture_output=True, timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout) == {"case": case, "offline_mechanical": True}


def _child(case, sandbox, candidate, source):
    import logging
    import socket
    from contextlib import ExitStack
    from unittest.mock import patch

    logging.disable(logging.CRITICAL)
    home = sandbox / "home"
    assert Path.home().resolve() == home
    assert Path(os.environ["HERMES_HOME"]).resolve() == home / ".hermes"
    assert not any(name == "agent" or name.startswith("tools.") for name in sys.modules)
    candidate_trees = {
        profile: candidate / f"profiles/{profile}/skills/{profile}-pipeline"
        for profile in ("creator", *HANDS)
    }
    code_roots = (source, Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve(),
                  Path("/usr"), Path("/System/Library"), Path("/Library/Apple"))

    def audit(event, args):
        if event.startswith("socket.") or event in {
            "subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork",
        }:
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
            if any(path.is_relative_to(tree) for tree in candidate_trees.values()) and path.suffix == ".md":
                return
            if path.name in {".env", "auth.json", "config.yaml", "SOUL.md"}:
                raise AssertionError("Non-fixture configuration/credentials forbidden")
            if any(path.is_relative_to(root) for root in code_roots):
                return
            raise AssertionError("Read outside candidate docs/source/runtime forbidden")

    sys.addaudithook(audit)
    with ExitStack() as stack:
        owner = "video-creator" if case.startswith("hands_") else "creator"
        skills = home / ".hermes/skills"
        trees = {}
        for profile, original in candidate_trees.items():
            tree = (skills if profile == owner else sandbox / "external") / original.name
            trees[profile] = tree
            for path in original.rglob("*.md"):
                assert not path.is_symlink() and path.resolve().is_relative_to(original)
                target = tree / path.relative_to(original)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
            assert (tree / "SKILL.md").is_file()
            assert all(p.suffix == ".md" for p in tree.rglob("*") if p.is_file())
        # Synthetic isolation settings only, never a serialized candidate config.
        (home / ".hermes/config.yaml").write_text(
            "skills:\n  external_dirs: []\n  disabled: []\n  template_vars: true\n"
            "  inline_shell: false\nplugins:\n  enabled: []\n", encoding="utf-8",
        )

        import hermes_cli.plugins as plugins

        stack.enter_context(patch.object(plugins.PluginManager, "discover_and_load", return_value=None))
        for name in ("discover_plugins", "start_background_plugin_discovery"):
            stack.enter_context(patch.object(plugins, name, return_value=None))
        stack.enter_context(patch.object(plugins, "invoke_hook", return_value=[]))

        from agent import skill_utils as su

        external = [trees[p] for p in HANDS] if owner == "creator" else []
        stack.enter_context(patch.object(su, "get_external_skills_dirs", return_value=external))
        stack.enter_context(patch.object(su, "get_project_skills_dirs", return_value=[]))

        from agent import prompt_builder as pb
        from tools import skills_tool as st
        from tools import skills_tool_plugin as sp
        from tools import skill_usage
        from tools.registry import registry

        assert Path(su.__file__).resolve().is_relative_to(source)
        assert Path(st.__file__).resolve().is_relative_to(source)
        for name in ("bump_use", "bump_view"):
            stack.enter_context(patch.object(skill_usage, name, return_value=None))
        for module in (sp, st):
            stack.enter_context(patch.object(module, "_mark_background_review_read", return_value=None))
        st._SKILLS_CACHE.clear()
        st.reset_skill_view_dedup()
        pb.clear_skills_system_prompt_cache(clear_snapshot=True)
        tree = trees["creator"]
        calls = []

        def dispatch(tool, args, task="creator-entry-runtime"):
            # This is the test's read-only tool surface, not a production ACL claim.
            assert tool in ALLOW, "Only instruction discovery/reads are allowed"
            calls.append((tool, args.copy(), task))
            return json.loads(registry.dispatch(tool, args, task_id=task))

        def view(name, file_path=None, task="creator-entry-runtime"):
            assert registry.get_entry("skill_view").handler is st._skill_view_with_bump
            return dispatch("skill_view", {"name": name, "file_path": file_path}, task)

        def body_matches(payload, path):
            assert payload.get("success"), payload
            expected = path.read_text(encoding="utf-8")
            # Hermes expands a SKILL body from its owner, not the last viewed root.
            if path.name == "SKILL.md":
                expected = expected.replace("${HERMES_SKILL_DIR}", str(path.parent))
            assert payload.get("content") == expected, "Expected full actual candidate body"
            return payload["content"]

        def unchanged(payload):
            assert payload["status"] == "unchanged" and payload["content_returned"] is False
            assert "content" not in payload

        def read(path, task="creator-entry-runtime"):
            from tools import file_tools as ft
            from tools import file_tools_paths as fp
            from tools import skill_manager_guards
            from tools.environments.local import LocalEnvironment
            from tools.file_operations import ShellFileOperations

            backend = ShellFileOperations(object.__new__(LocalEnvironment), cwd=str(home))
            backend.env.cwd = str(home)
            assert backend._native_read_enabled()
            with patch.object(ft, "_get_file_ops", return_value=backend), \
                 patch.object(fp, "_terminal_env_type_for_task", return_value="local"), \
                 patch.object(skill_manager_guards, "mark_background_review_skill_read", return_value=None):
                assert registry.get_entry("read_file").handler is ft._handle_read_file
                return dispatch("read_file", {"path": str(path)}, task)

        def file_body_matches(payload, path):
            assert not payload.get("error") and not payload.get("truncated"), payload
            content = re.sub(r"^\d+\|", "", payload["content"], flags=re.MULTILINE)
            assert content.rstrip("\n") == path.read_text(encoding="utf-8").rstrip("\n")

        try:
            if case == "discovery":
                expected = set(CREATOR_NAMES)
                for profile in HANDS:
                    expected.add(f"{profile}-pipeline")
                    leaves = list(trees[profile].glob("*/*/SKILL.md"))
                    assert leaves, profile
                    for leaf in leaves:
                        name = f"{leaf.parent.parent.name}-{leaf.parent.name}"
                        fm, _ = su.parse_frontmatter(leaf.read_text(encoding="utf-8"))
                        assert fm["name"] == name and name not in expected
                        expected.add(name)
                        body_matches(view(name), leaf)
                files = [p for root in (skills, *external)
                         for p in su.iter_skill_index_files(root, "SKILL.md")]
                assert len(files) == len(expected)
                assert not any("references" in p.parts for p in files)
                found = st._find_all_skills()
                assert len(found) == len(expected) and {s["name"] for s in found} == expected
                prompt = pb.build_skills_system_prompt(
                    available_tools=ALLOW, available_toolsets={"skills", "file"},
                )
                rows = re.findall(r"^    - ([^: \n]+): (.*)$", prompt, re.MULTILINE)
                assert len(rows) == len(expected) and {n for n, _ in rows} == expected
                visible = dict(rows)
                assert len({visible[n] for n in CREATOR_NAMES}) == 4
                relevant = {"creator-pipeline": "creator", "plan-creator": "plan",
                            "build-creator": "dispatch", "qa-creator": "evidence"}
                for name, word in relevant.items():
                    desc = visible[name]
                    assert 0 < len(desc) <= 60 and word in desc.lower()
                    path = tree / ("SKILL.md" if name == "creator-pipeline" else f"{name}/SKILL.md")
                    fm, _ = su.parse_frontmatter(path.read_text(encoding="utf-8"))
                    assert desc == su.extract_skill_description(fm)
                listing = dispatch("skills_list", {})
                assert listing["count"] == len(expected)
                assert {s["name"] for s in listing["skills"]} == expected

            elif case == "direct_qa":
                entry = body_matches(view("qa-creator"), tree / "qa-creator/SKILL.md")
                assert 'skill_view(name="creator-pipeline")' in entry
                assert "<Goal>" not in entry
                assert [args["name"] for _, args, _ in calls] == ["qa-creator"]
                # A direct child read did not preload the kernel: its first read is full.
                body_matches(view("creator-pipeline"), tree / "SKILL.md")
                relative = "references/image-creator/card.md"
                body_matches(view("qa-creator", relative), tree / "qa-creator" / relative)

            elif case.startswith("subject_change_"):
                task = "same-plan-task"
                for name, path in (("creator-pipeline", tree / "SKILL.md"),
                                   ("plan-creator", tree / "plan-creator/SKILL.md")):
                    body_matches(view(name, task=task), path)
                card = "references/image-creator/card.md"
                previous = body_matches(view("plan-creator", card, task), tree / "plan-creator" / card)
                next_ref = ("references/audio-creator/music.md" if case.endswith("music")
                            else "references/video-creator/clip.md")
                unchanged(view("creator-pipeline", task=task))
                unchanged(view("plan-creator", task=task))
                current = body_matches(view("plan-creator", next_ref, task), tree / "plan-creator" / next_ref)
                assert current != previous
                unchanged(view("plan-creator", card, task))

            elif case == "proposal_approval_phases":
                # Scripted read sequence only; no approval, model or production is simulated.
                body_matches(view("creator-pipeline"), tree / "SKILL.md")
                bodies, details = [], []
                relative = "references/audio-creator/music.md"
                for name in ("plan-creator", "build-creator", "qa-creator"):
                    bodies.append(body_matches(view(name), tree / name / "SKILL.md"))
                    details.append(body_matches(view(name, relative), tree / name / relative))
                    unchanged(view("creator-pipeline"))
                assert len(set(bodies)) == len(set(details)) == 3
                assert "approved_plan" in details[1] and "approval_sha256" in details[1]
                assert "proposal round" in details[2] and "rendered take" in details[2]
                for name in ENTRIES:
                    unchanged(view(name))
                # Reads leave every original phase/reference byte intact in the sandbox.
                for name in ENTRIES:
                    for path in ("SKILL.md", relative):
                        assert (tree / name / path).read_bytes() == (candidate_trees["creator"] / name / path).read_bytes()

            elif case == "hands_options":
                root = trees[owner]
                task = "own-hands-job"
                assert not external
                found = {s["name"] for s in st._find_all_skills()}
                assert "video-creator-pipeline" in found and not found.intersection(CREATOR_NAMES)
                body_matches(view("video-creator-pipeline", task=task), root / "SKILL.md")
                leaf = root / "generate/music-video"
                body_matches(view("generate-music-video", task=task), leaf / "SKILL.md")
                fm, _ = su.parse_frontmatter((leaf / "SKILL.md").read_text(encoding="utf-8"))
                option = fm["metadata"]["hermes"]["form"]["pace"]
                assert option["required"] is False
                assert option["references"] == "references/pace/*.md"
                first, changed = ("references/pace/steady.md", "references/pace/snappy.md")
                before = body_matches(view("generate-music-video", first, task), leaf / first)
                unchanged(view("video-creator-pipeline", task=task))
                unchanged(view("generate-music-video", task=task))
                after = body_matches(view("generate-music-video", changed, task), leaf / changed)
                assert before != after
                assert [args["file_path"] for _, args, _ in calls if args.get("file_path")] == [first, changed]
                # The caller fetched only the two selected options, not the catalog.
                assert len(list((leaf / "references").rglob("*.md"))) > 2

            elif case == "hands_inline_format":
                root = trees[owner]
                body_matches(view("video-creator-pipeline"), root / "SKILL.md")
                path = root / "edit/clip/SKILL.md"
                payload = view("edit-clip")
                body_matches(payload, path)
                fm, _ = su.parse_frontmatter(payload["content"])
                field = fm["metadata"]["hermes"]["form"]["format"]
                assert field["required"] is False and {"mp4", "gif"} <= set(field["options"])
                # Format guidance is inline in this real leaf, not a fictitious ref.
                assert "references" not in field
                unchanged(view("video-creator-pipeline"))
                unchanged(view("edit-clip"))
                file_body_matches(read(path), path)
                assert "disclose GIF's" in payload["content"]
                assert not any(args.get("file_path") for _, args, _ in calls)

            elif case == "canonical_recovery":
                for name, relative in (("creator-pipeline", None), ("qa-creator", None),
                                       ("qa-creator", "references/audio-creator/music.md")):
                    base = tree if name == "creator-pipeline" else tree / name
                    path = base / (relative or "SKILL.md")
                    body_matches(view(name, relative), path)
                    unchanged(view(name, relative))
                    unchanged(view(name, relative))
                    file_body_matches(read(path), path)
                    unchanged(view(name, relative))
                # Canonical read_file also works without any preceding skill_view.
                first_path = tree / "plan-creator/references/video-creator/clip.md"
                file_body_matches(read(first_path), first_path)
                missing = read(tree / "qa-creator/references/audio-creator/missing.md")
                assert missing.get("error") and not missing.get("content")
                assert missing.get("status") != "unchanged"

            elif case == "migration_no_alias":
                for phase, entry in (("plan", "plan-creator"), ("build", "build-creator"),
                                     ("quality-assurance", "qa-creator")):
                    old = f"references/{phase}/index.md"
                    assert not (tree / old).exists()
                    result = view("creator-pipeline", old)
                    assert result.get("success") is False and "content" not in result
                    assert read(tree / old).get("error")
                    body_matches(view(entry), tree / entry / "SKILL.md")

            elif case == "external_form":
                assert trees["image-creator"] in external
                body_matches(view("plan-creator"), tree / "plan-creator/SKILL.md")
                path = trees["image-creator"] / "create/card/SKILL.md"
                payload = view("create-card")
                body_matches(payload, path)
                fm, _ = su.parse_frontmatter(payload["content"])
                hands = fm["metadata"]["hermes"]
                assert hands["hands"] == "image-creator"
                assert hands["form"]["title"]["required"] is True
                assert payload["skill_dir"] == str(path.parent)
                with pytest.raises(AssertionError, match="Only instruction"):
                    dispatch("terminal", {"command": "forbidden"})
                assert {tool for tool, _, _ in calls} <= ALLOW
                assert "image-creator-pipeline" not in {args.get("name") for _, args, _ in calls}
                with pytest.raises(AssertionError, match="External execution/network"):
                    socket.socket()
                with pytest.raises(AssertionError, match="External execution/network"):
                    subprocess.run([sys.executable, "-V"], check=True)
            else:
                raise AssertionError("Unknown offline mechanical case")
        finally:
            st.reset_skill_view_dedup()
            st._SKILLS_CACHE.clear()
            pb.clear_skills_system_prompt_cache(clear_snapshot=True)


if __name__ == "__main__":
    import traceback

    try:
        assert len(sys.argv) == 6 and sys.argv[1] == "--child"
        _child(sys.argv[2], *(Path(p).resolve() for p in sys.argv[3:]))
        print(json.dumps({"case": sys.argv[2], "offline_mechanical": True}))
    except BaseException as error:
        frames = [(frame.f_code.co_name, line) for frame, line in traceback.walk_tb(error.__traceback__)]
        print(json.dumps({"case": sys.argv[2], "error_type": type(error).__name__,
                          "message": str(error), "frames": frames}))
        sys.exit(1)
