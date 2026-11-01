import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rw = _load("ranking_watch", ROOT / "ranking_watch.py")


def test_parse_params():
    text = """
    param!(FavoriteWeight, f64, "favorite_weight", 0.66);
    param!(
        AllowedTags,
        Vec<String>,
        "allowed_tags",
        vec![
            "alpha".to_string(),
            "beta".to_string()
        ]
    );
    param!(
        SpacesTest,
        i32,
        "spaces",
        1  +
        2
    );
    """
    params = rw.parse_params(text)
    assert params["FavoriteWeight"] == "0.66"
    assert params["AllowedTags"] == 'vec![ "alpha".to_string(), "beta".to_string() ]'
    assert params["SpacesTest"] == "1 + 2"


def test_watched():
    sample = {
        "FavoriteWeight": "0.66",
        "HeavyRankerWeightBoost": "1.5",
        "ColdStartFollowerCap": "50000",
        "EnableFairShareRanking": "true",
        "PhoenixScoresResultSize": "2800",
        "PopularPostsMaxResults": "500",
        "UnrelatedParam": "123",
        "WeightUnrelated": "456",
    }
    w = rw.watched(sample)
    assert list(w.keys()) == sorted([
        "ColdStartFollowerCap",
        "EnableFairShareRanking",
        "FavoriteWeight",
        "HeavyRankerWeightBoost",
        "PhoenixScoresResultSize",
        "PopularPostsMaxResults",
    ])
    assert "UnrelatedParam" not in w
    assert "WeightUnrelated" not in w


def test_parse_max_post_age_and_updates():
    config = "pub const MAX_POST_AGE: u64 = 48 * 60 * 60;\n"
    assert rw.parse_max_post_age(config) == "48 * 60 * 60"
    with pytest.raises(rw.WatchError):
        rw.parse_max_post_age("pub const OTHER: u64 = 100;")

    readme = """# Title
## Notable Updates
### October 26th, 2026
Some description here
### October 13th, 2026
More description
## Next Section
### Not in notable updates
"""
    assert rw.parse_updates(readme) == ["October 26th, 2026", "October 13th, 2026"]
    assert rw.parse_updates("# No updates section") == []


def test_compare():
    base_values = {
        "params": {"FavoriteWeight": "0.5", "RemovedWeight": "1.0"},
        "max_post_age": "24 * 60 * 60",
        "notable_updates": ["Update 1", "Old Update"],
        "filters": ["filter_old.rs"],
        "sources": ["source_old.rs"],
    }
    cur_values = {
        "params": {"FavoriteWeight": "0.66", "AddedWeight": "2.0"},
        "max_post_age": "48 * 60 * 60",
        "notable_updates": ["Update 1", "New Update"],
        "filters": ["filter_new.rs"],
        "sources": ["source_new.rs"],
    }

    # Identical values return empty list
    assert rw.compare(base_values, base_values) == []

    lines = rw.compare(base_values, cur_values)
    assert "changed FavoriteWeight: 0.5 → 0.66" in lines
    assert "added AddedWeight = 2.0" in lines
    assert "removed RemovedWeight (was 1.0)" in lines
    assert "changed MAX_POST_AGE: 24 * 60 * 60 → 48 * 60 * 60" in lines
    assert "new update heading: New Update" in lines
    assert "removed update heading: Old Update" in lines
    assert "added filter filter_new.rs" in lines
    assert "removed filter filter_old.rs" in lines
    assert "added source source_new.rs" in lines
    assert "removed source source_old.rs" in lines


def test_check_cli(monkeypatch, tmp_path, capsys):
    base_data = {
        "commit": "1111111111111111111111111111111111111111",
        "committed_at": "2026-10-01T00:00:00Z",
        "values": {
            "filters": ["f1.rs"],
            "max_post_age": "48 * 60 * 60",
            "notable_updates": ["Update 1"],
            "params": {"FavoriteWeight": "0.5"},
            "sources": ["s1.rs"],
        },
    }
    baseline_file = tmp_path / "ranking_baseline.json"
    baseline_file.write_text(json.dumps(base_data), encoding="utf-8")

    # 1. Identical values with different commit -> {"wakeAgent": false}
    cur_identical = {
        "commit": "2222222222222222222222222222222222222222",
        "committed_at": "2026-10-02T00:00:00Z",
        "values": json.loads(json.dumps(base_data["values"])),
    }
    monkeypatch.setattr(rw, "snapshot", lambda commit=None: cur_identical)
    with pytest.raises(SystemExit) as exc:
        rw.main(["check", "--baseline", str(baseline_file)])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.out == '{"wakeAgent": false}\n'

    # 2. Changed weight -> report starting with # X ranking defaults changed
    cur_changed = {
        "commit": "2222222222222222222222222222222222222222",
        "committed_at": "2026-10-02T00:00:00Z",
        "values": {
            "filters": ["f1.rs"],
            "max_post_age": "48 * 60 * 60",
            "notable_updates": ["Update 1"],
            "params": {"FavoriteWeight": "0.66"},
            "sources": ["s1.rs"],
        },
    }
    monkeypatch.setattr(rw, "snapshot", lambda commit=None: cur_changed)
    with pytest.raises(SystemExit) as exc:
        rw.main(["check", "--baseline", str(baseline_file)])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("# X ranking defaults changed")
    assert "FavoriteWeight: 0.5 → 0.66" in captured.out

    # 3. Fetch failure -> exit 1, stderr starts with ranking_watch:, stdout empty
    monkeypatch.setattr(
        rw,
        "snapshot",
        lambda commit=None: (_ for _ in ()).throw(rw.WatchError("fetch failed for https://example.com")),
    )
    with pytest.raises(SystemExit) as exc:
        rw.main(["check", "--baseline", str(baseline_file)])
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("ranking_watch:")
    assert captured.out == ""

    # 4. Fewer than 50 params -> exit 1
    monkeypatch.undo()
    monkeypatch.setattr(rw, "head_commit", lambda ref=rw.REF: ("abcdef123", "2026-10-01T00:00:00Z"))
    tree_payload = json.dumps({"truncated": False, "tree": []})
    monkeypatch.setattr(
        rw,
        "fetch",
        lambda url: tree_payload if "trees" in url else "pub const MAX_POST_AGE: u64 = 48;\nparam!(A, i32, \"a\", 1);",
    )
    with pytest.raises(SystemExit) as exc:
        rw.main(["check", "--baseline", str(baseline_file)])
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("ranking_watch:")


def test_baseline_marketer_reference_consistency():
    baseline_path = ROOT / "ranking_baseline.json"
    assert baseline_path.is_file()
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)

    ref_path = ROOT.parents[2] / "profiles/marketer/skills/pipeline/references/x-ranking.md"
    assert ref_path.is_file()
    ref_text = ref_path.read_text(encoding="utf-8")

    short_sha = baseline["commit"][:7]
    assert short_sha in ref_text

    mapping = {
        "like": "FavoriteWeight",
        "reply": "ReplyWeight",
        "quote": "QuoteWeight",
        "repost": "RetweetWeight",
        "share via copy link": "ShareViaCopyLinkWeight",
        "share via DM": "ShareViaDmWeight",
        "follow author": "FollowAuthorWeight",
        "report": "ReportWeight",
        "mute author": "MuteAuthorWeight",
        "not interested": "NotInterestedWeight",
        "block author": "BlockAuthorWeight",
    }

    note_weights = {}
    for line in ref_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| ---") or "Positive" in line:
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) >= 2 and parts[0] and parts[1]:
            val = parts[1].replace("\u2212", "-")
            try:
                note_weights[parts[0]] = float(val)
            except ValueError:
                pass
        if len(parts) >= 4 and parts[2] and parts[3]:
            val = parts[3].replace("\u2212", "-")
            try:
                note_weights[parts[2]] = float(val)
            except ValueError:
                pass

    base_params = baseline["values"]["params"]
    for action, param_name in mapping.items():
        assert action in note_weights, f"action {action} not found in x-ranking.md table"
        assert param_name in base_params, f"param {param_name} not found in baseline"
        assert note_weights[action] == float(base_params[param_name]), (
            f"weight mismatch for {action} ({param_name}): "
            f"note has {note_weights[action]}, baseline has {base_params[param_name]}"
        )


def test_shell_script():
    script_path = ROOT.parents[2] / "profiles/assistant/scripts/x-ranking-watch.sh"
    assert script_path.is_file()
    assert os.access(script_path, os.X_OK)
    text = script_path.read_text(encoding="utf-8")
    assert "ranking_watch.py" in text
    assert '"$engine" check' in text or 'ranking_watch.py" check' in text

    code_lines = [
        line for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any("wakeAgent" in line for line in code_lines)
