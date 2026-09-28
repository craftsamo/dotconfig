import importlib.util
import json
import os
from datetime import date, datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drafts = _load("workspace_drafts_test", ROOT / "drafts.py")
plugin = _load("workspace_drafts_plugin_test", ROOT / "__init__.py")
TODAY = date(2026, 9, 28)


def touch(path, data=b"x", day=TODAY):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    stamp = datetime.combine(day, datetime.min.time()).timestamp() + 3600
    os.utime(path, (stamp, stamp))
    return path


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "Workspaces"
    touch(root / "AGENTS.md")
    touch(root / ".agent" / "20260927-cross-scan" / "report.md", b"12345")
    touch(root / ".deliverables" / "old-job" / "a.png", b"xx", day=date(2026, 8, 1))
    touch(root / ".deliverables" / "AGENTS.md")
    touch(root / ".scratch" / "loose.py", day=date(2026, 9, 1))
    touch(root / ".inbox" / "incoming.pdf")                     # not a draft area
    group = root / "Projects" / "Acme"
    touch(group / "docs" / "spec.md")                           # canon, never listed
    touch(group / ".agent" / "20260920-landing-copy" / "draft.md", day=date(2026, 9, 10))
    touch(group / ".agent" / "20260920-landing-copy" / "v2" / "draft.md", day=date(2026, 9, 26))
    touch(group / ".agent" / "Evidence Pack" / "n.md")         # breaks the naming rule
    touch(group / ".agent" / "scratch" / "job-a" / "t.txt", day=date(2026, 8, 20))
    touch(group / ".agent" / "deliverables" / "job-a" / "final.txt")
    touch(root / "Personal" / "Budget" / ".agent" / "20260928-monthly" / "sum.md")
    target = touch(tmp_path / "elsewhere" / "big.bin", b"y" * 1000)
    (group / ".agent" / "20260925-linked").mkdir(parents=True)
    (group / ".agent" / "20260925-linked" / "ref").symlink_to(target.parent)
    return root


def listed(ws, **args):
    return drafts.run({"action": "list", "sort": "name", **args}, root=ws, today=TODAY)


def by_path(result):
    return {d["relative"]: d for d in result["drafts"]}


def test_every_draft_area_is_listed_and_canon_is_not(ws):
    rows = by_path(listed(ws))
    assert set(rows) == {
        ".agent/20260927-cross-scan", ".deliverables/old-job", ".scratch/loose.py",
        "Projects/Acme/.agent/20260920-landing-copy", "Projects/Acme/.agent/Evidence Pack",
        "Projects/Acme/.agent/scratch/job-a", "Projects/Acme/.agent/deliverables/job-a",
        "Projects/Acme/.agent/20260925-linked", "Personal/Budget/.agent/20260928-monthly",
    }


def test_current_draft_carries_start_date_size_and_newest_change(ws):
    row = by_path(listed(ws))["Projects/Acme/.agent/20260920-landing-copy"]
    assert row["group"] == "Projects/Acme" and row["layout"] == "current"
    assert row["started"] == "2026-09-20" and row["age_days"] == 8
    assert row["files"] == 2 and row["bytes"] == 2
    assert row["last_modified"] == "2026-09-26" and row["idle_days"] == 2
    assert row["flags"] == []


def test_flags_mark_misnamed_legacy_and_stale(ws):
    rows = by_path(listed(ws))
    assert rows["Projects/Acme/.agent/Evidence Pack"]["flags"] == ["misnamed"]
    assert rows[".deliverables/old-job"]["flags"] == ["legacy", "stale"]
    assert rows[".deliverables/old-job"]["legacy_area"] == ".deliverables"
    assert rows["Projects/Acme/.agent/scratch/job-a"]["layout"] == "legacy"
    assert rows["Projects/Acme/.agent/scratch/job-a"]["legacy_area"] == "scratch"
    assert rows[".scratch/loose.py"]["kind"] == "file"
    assert "stale" in rows[".scratch/loose.py"]["flags"]                     # 27 idle days


def test_symlinks_are_never_followed(ws):
    row = by_path(listed(ws))["Projects/Acme/.agent/20260925-linked"]
    assert row["bytes"] < 1000 and row["files"] == 1


def test_filters_by_group_layout_and_flags(ws):
    assert {d["group"] for d in listed(ws, group="acme")["drafts"]} == {"Projects/Acme"}
    assert {d["group"] for d in listed(ws, group="(unassigned)")["drafts"]} == {"(unassigned)"}
    assert all(d["layout"] == "legacy" for d in listed(ws, layout="legacy")["drafts"])
    both = listed(ws, flags=["legacy", "stale"])["drafts"]
    assert {d["relative"] for d in both} == {".deliverables/old-job", ".scratch/loose.py",
                                             "Projects/Acme/.agent/scratch/job-a"}
    assert listed(ws, stale_days=60)["totals"]["stale"] == 0


def test_summary_groups_and_totals(ws):
    result = drafts.run({"action": "summary"}, root=ws, today=TODAY)
    assert result["source"] == "filesystem" and result["status"] == "complete"
    assert result["totals"]["drafts"] == 9 and result["totals"]["legacy"] == 4
    groups = {g["group"]: g for g in result["groups"]}
    assert groups["Projects/Acme"]["drafts"] == 5 and groups["Projects/Acme"]["misnamed"] == 1
    assert "drafts" not in result


def test_list_sorts_and_limits(ws):
    result = drafts.run({"action": "list", "sort": "idle", "limit": 2}, root=ws, today=TODAY)
    assert result["truncated"] is True and len(result["drafts"]) == 2
    assert result["drafts"][0]["relative"] == ".deliverables/old-job"


def test_scan_reads_no_file_contents(ws, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("file contents were opened")
    monkeypatch.setattr(Path, "read_bytes", refuse)
    monkeypatch.setattr(Path, "read_text", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    drafts.run({"action": "list"}, root=ws, today=TODAY)


@pytest.mark.parametrize("args", [{"action": "move"}, {"action": "list", "flags": ["old"]},
                                  {"action": "list", "limit": 0}, {"action": "list", "group": " "},
                                  {"action": "summary", "stale_days": "7"}])
def test_rejects_bad_requests(ws, args):
    with pytest.raises(ValueError):
        drafts.run(args, root=ws, today=TODAY)


def test_missing_root_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        drafts.run({"action": "summary"}, root=tmp_path / "none")


def test_render_and_cli(ws, capsys):
    text = drafts.render(listed(ws), max_rows=3)
    assert "9 drafts" in text and "… 6 more rows" in text
    assert drafts.main(["list", "--root", str(ws), "--legacy", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["totals"]["drafts"] == 4
    assert drafts.main(["--root", str(ws / "missing")]) == 2


def test_tool_and_command_use_the_same_reader(ws, monkeypatch):
    monkeypatch.setenv("WORKSPACES_ROOT", str(ws))
    result = json.loads(plugin.workspace_drafts({"action": "summary"}))
    assert result["root"] == str(ws)
    assert json.loads(plugin.workspace_drafts({"action": "delete"}))["error"]
    assert plugin.drafts_text("").startswith("```\nDrafts: 9")
    assert "20260920-landing-copy" in plugin.drafts_text("Acme")
    assert "legacy" in plugin.drafts_text("legacy")


def test_chat_text_stays_narrow_and_names_drafts_inside_their_group(ws):
    summary = drafts.render_chat(drafts.run({"action": "summary"}, root=ws, today=TODAY))
    assert max(len(line) for line in summary.splitlines()) <= 40
    assert "Acme" in summary and "Projects/" not in summary
    assert "Budget*" in summary and "* Personal" in summary and "(root)" in summary
    one = drafts.render_chat(listed(ws, group="Acme"))
    assert "\nscratch/job-a\n" in one and ".agent" not in one
    mixed = drafts.render_chat(listed(ws, flags=["legacy"]), max_rows=2)
    assert "(root): deliverables/old-job" in mixed or "Acme: scratch/job-a" in mixed
    assert "showing 2 of 4" in mixed


class Ctx:
    def __init__(self, profile):
        self.profile_name, self.tools, self.commands = profile, [], []

    def register_tool(self, **kw):
        self.tools.append(kw)

    def register_command(self, name, handler, **kw):
        self.commands.append(name)


@pytest.mark.parametrize("profile,expected", [("assistant", True), ("engineer", True), ("creator", False)])
def test_registration_is_limited_to_engineer_and_assistant(profile, expected):
    ctx = Ctx(profile)
    plugin.register(ctx)
    assert bool(ctx.tools) is expected and bool(ctx.commands) is expected
    if expected:
        assert ctx.tools[0]["toolset"] == "workspace_drafts" and ctx.commands == ["drafts"]
        assert ctx.tools[0]["schema"]["parameters"]["additionalProperties"] is False
