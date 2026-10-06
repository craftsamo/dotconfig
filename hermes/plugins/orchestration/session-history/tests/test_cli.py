import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("session_history_cli_test", ROOT / "cli.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

H = 3600 * 1000


def usage(intervals, active, out=10, status="complete", diagnostics=()):
    return {"action": "usage", "window": {"from": "2026-09-28T00:00:00Z", "to": "2026-09-29T00:00:00Z",
                                          "timezone": "UTC"},
            "source": "db", "status": status, "diagnostics": list(diagnostics),
            "totals": {"sessions": 1, "active_seconds": active, "active_union_seconds": active,
                       "question_wait_seconds": 0, "tokens": {"input": 0, "output": out, "reasoning": 0,
                                                              "cache_read": 0, "cache_write": 0},
                       "intervals_ms": intervals},
            "groups": [{"key": {"profile": "engineer"}, "sessions": 1, "active_seconds": active,
                        "active_union_seconds": active, "question_wait_seconds": 0,
                        "tokens": {"input": 0, "output": out, "reasoning": 0, "cache_read": 0, "cache_write": 0}}]}


def test_summary_removes_overlap_between_tools():
    calls = {}

    def runner(name, result):
        def run(args, keep_intervals):
            calls[name] = (args, keep_intervals)
            return result
        return run

    result = cli.summary({"timezone": "UTC"}, runners={
        "opencode": runner("opencode", usage([[0, 2 * H]], 7200)),
        "hermes": runner("hermes", usage([[H, 3 * H]], 7200, status="partial")),
    })
    assert result["active_union_seconds"] == 3 * 3600          # 2 h + 2 h with 1 h shared
    assert result["status"] == "partial"
    assert calls["opencode"] == ({"action": "usage", "timezone": "UTC", "days": 1, "group_by": ["directory"]}, True)
    assert calls["hermes"][0]["group_by"] == ["profile"]
    assert all("intervals_ms" not in t["totals"] for t in result["tools"].values())
    text = cli.render_summary(result)
    assert "Combined (overlap removed): 3.0h" in text and cli.NOTE in text


def test_summary_survives_one_missing_tool():
    def missing(args, keep_intervals):
        raise cli.common.Unavailable("no Hermes state.db")

    result = cli.summary({"days": 2}, runners={"opencode": lambda a, keep_intervals: usage([[0, H]], 3600),
                                               "hermes": missing})
    assert result["status"] == "partial" and result["tools"]["hermes"] == {"error": "no Hermes state.db"}
    assert "Hermes: unavailable" in cli.render_summary(result)
    rich = cli.render_summary_rich(result)
    assert "| Hermes | unavailable |" in rich and "Hermes unavailable: no Hermes state.db" in rich


def test_rich_summary_is_tables_with_folded_breakdowns():
    def run(args, keep_intervals):
        result = usage([[0, H]], 3600, diagnostics=[{"code": "usage-crosses-window", "count": 2, "partial": True}])
        result["groups"][0]["key"] = {"directory": "/tmp/a|b"}
        result["totals"]["question_wait_seconds"] = 600
        return result
    result = cli.summary({"days": 1, "timezone": "UTC"}, runners={"opencode": run, "hermes": run})
    text = cli.render_summary_rich(result)
    assert text.startswith("## AI activity") and "```" not in text
    assert "| Tool | Active | Sessions | Output |" in text and "| OpenCode | 1.0h | 1 | 10 |" in text
    assert "<summary>OpenCode by directory</summary>" in text and "<summary>Hermes by profile</summary>" in text
    assert "`/tmp/a/b`" in text                                   # a pipe cannot break the row
    assert "waiting for your answer 10m" in text
    assert "`usage-crosses-window` ×2 (undercounts)" in text and "`/activity week`" in text
    assert text.count("<details>") == text.count("</details>") == 3


def test_caller_mistakes_are_not_hidden():
    with pytest.raises(ValueError):
        cli.summary({"days": 0})


def test_command_line(monkeypatch, capsys):
    monkeypatch.setattr(cli, "summary", lambda args: {"action": "summary", "window": None, "status": "complete",
                                                      "active_union_seconds": 0, "tools": {}, "args": args})
    assert cli.main(["--days", "7", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["args"] == {"days": 7}
    assert cli.main(["hermes", "list", "--from", "2026-09-02", "--to", "2026-09-01"]) == 1
    assert "error:" in capsys.readouterr().out
    seen = {}

    def run(args):
        seen.update(args)
        return usage([], 60)
    monkeypatch.setattr(cli.READERS["hermes"], "run", run)
    assert cli.main(["hermes", "usage", "--profile", "engineer,assistant", "--group-by", "profile"]) == 0
    assert seen == {"action": "usage", "profile": ["engineer", "assistant"], "group_by": ["profile"], "days": 1}
    assert "engineer" in capsys.readouterr().out


def test_table_alignment():
    lines = cli._table([("alpha", "1.5h", 3), ("b", "12m", 10)], ("name", "active", "n"))
    assert lines[1] == "alpha    1.5h   3" and lines[2] == "b         12m  10"
