#!/usr/bin/env python3
"""The wake gate of the Assistant's weekly X-ranking watch.

Compares the published defaults of github.com/xai-org/x-algorithm with the baseline
recorded beside it, ranking_baseline.json, which is refreshed in the same change
that updates Marketer's profiles/marketer/skills/pipeline/references/x-ranking.md.
Contract: docs/x-access.md "Ranking watch".
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.request

REPO = "xai-org/x-algorithm"
REF = "main"
BASELINE = Path(__file__).resolve().parent / "ranking_baseline.json"
TIMEOUT = 30
USER_AGENT = "hermes-x-ranking-watch"

PARAM_RE = re.compile(r'param!\(\s*(\w+),\s*([^,]+?),\s*"[^"]*",\s*([\s\S]*?)\);')


class WatchError(Exception):
    """Raised when ranking watch cannot fetch, parse, or evaluate ranking data."""


def fetch(url: str) -> str:
    """Fetch text from a URL with timeout and User-Agent; raise WatchError on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        raise WatchError(f"fetch failed for {url}: {e}") from e


def head_commit(ref: str = REF) -> tuple[str, str]:
    """GET commit API JSON and return (full sha, committer date ISO string)."""
    url = f"https://api.github.com/repos/{REPO}/commits/{ref}"
    raw = fetch(url)
    try:
        data = json.loads(raw)
        sha = data["sha"]
        date = data["commit"]["committer"]["date"]
        return sha, date
    except Exception as e:
        raise WatchError(f"invalid commit response from {url}: {e}") from e


def parse_params(text: str) -> dict[str, str]:
    """Parse every param!(Name, Type, "key", default); macro in param.rs."""
    params = {}
    for match in PARAM_RE.finditer(text):
        name = match.group(1)
        default = " ".join(match.group(3).split())
        params[name] = default
    return params


def watched(params: dict[str, str]) -> dict[str, str]:
    """Filter params for watched ranking metrics, returned sorted by key."""
    res = {}
    for k, v in params.items():
        if (
            k.endswith("Weight")
            or k.endswith("WeightBoost")
            or k.startswith("ColdStart")
            or k.startswith("Enable")
            or k in ("PhoenixScoresResultSize", "PopularPostsMaxResults")
        ):
            res[k] = v
    return {k: res[k] for k in sorted(res)}


def parse_max_post_age(config_rs: str) -> str:
    """Extract and collapse the right-hand side of pub const MAX_POST_AGE: u64 = ...;."""
    m = re.search(r"pub\s+const\s+MAX_POST_AGE\s*:\s*u64\s*=\s*([^;]+);", config_rs)
    if not m:
        raise WatchError("MAX_POST_AGE not found in config.rs")
    return " ".join(m.group(1).split())


def parse_updates(readme: str) -> list[str]:
    """Extract ### headings under the ## Notable Updates section of README."""
    m = re.search(r"(?m)^##\s+Notable Updates\s*$", readme)
    if not m:
        return []
    rest = readme[m.end():]
    next_section = re.search(r"(?m)^##\s+", rest)
    if next_section:
        section_text = rest[:next_section.start()]
    else:
        section_text = rest
    headings = []
    for line in section_text.splitlines():
        if line.startswith("### "):
            headings.append(line[4:].strip())
    return headings


def list_dir(tree: list[str], prefix: str) -> list[str]:
    """Return sorted file basenames directly under prefix ending in .rs, excluding mod.rs."""
    if not prefix.endswith("/"):
        prefix = prefix + "/"
    res = []
    for path in tree:
        if path.startswith(prefix):
            rel = path[len(prefix):]
            if "/" not in rel and rel.endswith(".rs") and rel != "mod.rs":
                res.append(rel)
    return sorted(res)


def snapshot(commit: str | None = None) -> dict:
    """Read param.rs, config.rs, README.md, and tree at one commit; return snapshot dict."""
    sha, committed_at = head_commit(commit or REF)

    tree_url = f"https://api.github.com/repos/{REPO}/git/trees/{sha}?recursive=1"
    tree_raw = fetch(tree_url)
    try:
        tree_data = json.loads(tree_raw)
    except Exception as e:
        raise WatchError(f"invalid tree response from {tree_url}: {e}") from e

    if tree_data.get("truncated"):
        raise WatchError(f"git tree response from {tree_url} was truncated")

    paths = [item["path"] for item in tree_data.get("tree", []) if "path" in item]

    param_url = f"https://raw.githubusercontent.com/{REPO}/{sha}/home-mixer/params/param.rs"
    config_url = f"https://raw.githubusercontent.com/{REPO}/{sha}/home-mixer/params/config.rs"
    readme_url = f"https://raw.githubusercontent.com/{REPO}/{sha}/README.md"

    param_rs = fetch(param_url)
    config_rs = fetch(config_url)
    readme = fetch(readme_url)

    all_params = parse_params(param_rs)
    if len(all_params) < 50:
        raise WatchError(f"param.rs no longer parses: found only {len(all_params)} params")

    w_params = watched(all_params)
    max_post_age = parse_max_post_age(config_rs)
    notable_updates = parse_updates(readme)
    filters = list_dir(paths, "home-mixer/filters/")
    sources = list_dir(paths, "home-mixer/sources/")

    return {
        "commit": sha,
        "committed_at": committed_at,
        "values": {
            "filters": filters,
            "max_post_age": max_post_age,
            "notable_updates": notable_updates,
            "params": w_params,
            "sources": sources,
        },
    }


def compare(base_values: dict, cur_values: dict) -> list[str]:
    """Compare baseline and current values, returning human-readable diff lines."""
    lines = []

    base_params = base_values.get("params", {})
    cur_params = cur_values.get("params", {})
    all_keys = sorted(set(base_params) | set(cur_params))
    for k in all_keys:
        if k in base_params and k in cur_params:
            if base_params[k] != cur_params[k]:
                lines.append(f"changed {k}: {base_params[k]} → {cur_params[k]}")
        elif k in cur_params and k not in base_params:
            lines.append(f"added {k} = {cur_params[k]}")
        elif k in base_params and k not in cur_params:
            lines.append(f"removed {k} (was {base_params[k]})")

    base_age = base_values.get("max_post_age")
    cur_age = cur_values.get("max_post_age")
    if base_age != cur_age:
        lines.append(f"changed MAX_POST_AGE: {base_age} → {cur_age}")

    base_updates = base_values.get("notable_updates", [])
    cur_updates = cur_values.get("notable_updates", [])
    for h in cur_updates:
        if h not in base_updates:
            lines.append(f"new update heading: {h}")
    for h in base_updates:
        if h not in cur_updates:
            lines.append(f"removed update heading: {h}")

    base_filters = set(base_values.get("filters", []))
    cur_filters = set(cur_values.get("filters", []))
    for f in sorted(cur_filters - base_filters):
        lines.append(f"added filter {f}")
    for f in sorted(base_filters - cur_filters):
        lines.append(f"removed filter {f}")

    base_sources = set(base_values.get("sources", []))
    cur_sources = set(cur_values.get("sources", []))
    for s in sorted(cur_sources - base_sources):
        lines.append(f"added source {s}")
    for s in sorted(base_sources - cur_sources):
        lines.append(f"removed source {s}")

    return lines


def report(base: dict, cur: dict, lines: list[str]) -> str:
    """Format markdown report for the Assistant."""
    base_sha = base.get("commit", "")
    cur_sha = cur.get("commit", "")
    base_short = base_sha[:7]
    cur_short = cur_sha[:7]
    base_date = base.get("committed_at", "")
    cur_date = cur.get("committed_at", "")
    bullets = "\n".join(f"- {line}" for line in lines)
    return (
        f"# X ranking defaults changed\n\n"
        f"Baseline: {base_short} ({base_date}) — current: {cur_short} ({cur_date})\n\n"
        f"https://github.com/{REPO}/compare/{base_sha}...{cur_sha}\n\n"
        f"{bullets}\n\n"
        f"The baseline is hermes/plugins/social/x-access/ranking_baseline.json; "
        f'refresh it with "ranking_watch.py refresh" in the same change that updates '
        f"profiles/marketer/skills/pipeline/references/x-ranking.md."
    )


def _default_state() -> Path:
    """Return default path to the ranking watch state JSON file."""
    root = Path(os.environ.get("HERMES_LOCAL") or Path.home() / ".hermes" / "local")
    return root / "x-access" / "ranking_watch.json"


def _read_reported_lines(state_path: Path) -> list[str] | None:
    try:
        if not state_path.is_file():
            return None
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        lines = data.get("lines")
        if not isinstance(lines, list) or not all(isinstance(x, str) for x in lines):
            return None
        return lines
    except Exception:
        return None


def _write_state(state_path: Path, commit: str, lines: list[str]) -> None:
    temp_path: Path | None = None
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "commit": commit,
            "lines": sorted(lines),
            "reported_at": datetime.now(timezone.utc).isoformat(),
        }
        content = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile("w", dir=state_path.parent, delete=False, encoding="utf-8") as f:
            temp_path = Path(f.name)
            f.write(content)
        os.replace(temp_path, state_path)
    except Exception as e:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        sys.stderr.write(f"ranking_watch: warning: failed to write state to {state_path}: {e}\n")


def _run(argv: list[str]) -> None:
    if not argv or argv[0].startswith("-"):
        args_to_parse = ["check", *argv]
    else:
        args_to_parse = argv

    parser = argparse.ArgumentParser(prog="ranking_watch.py", description="X ranking defaults watch")
    subparsers = parser.add_subparsers(dest="command")

    p_check = subparsers.add_parser("check", help="Compare current ranking defaults against baseline")
    p_check.add_argument("--baseline", type=Path, default=BASELINE, help="Path to ranking baseline JSON")
    p_check.add_argument("--state", type=Path, default=_default_state(), help="Path to ranking watch state JSON")

    p_refresh = subparsers.add_parser("refresh", help="Update ranking baseline file")
    p_refresh.add_argument("--baseline", type=Path, default=BASELINE, help="Path to ranking baseline JSON")
    p_refresh.add_argument("--commit", default=None, help="Pin to a specific commit SHA")

    p_show = subparsers.add_parser("show", help="Print snapshot JSON to stdout")
    p_show.add_argument("--commit", default=None, help="Pin to a specific commit SHA")

    p_forget = subparsers.add_parser("forget", help="Delete ranking watch state file")
    p_forget.add_argument("--state", type=Path, default=_default_state(), help="Path to ranking watch state JSON")

    opts = parser.parse_args(args_to_parse)

    if opts.command == "check":
        if not opts.baseline.is_file():
            raise WatchError(f"baseline file not found at {opts.baseline}")
        try:
            with open(opts.baseline, "r", encoding="utf-8") as f:
                base = json.load(f)
        except Exception as e:
            raise WatchError(f"invalid baseline JSON at {opts.baseline}: {e}") from e

        if not isinstance(base, dict) or "values" not in base or "commit" not in base:
            raise WatchError(f"invalid baseline structure in {opts.baseline}")

        cur = snapshot()
        lines = compare(base.get("values", {}), cur.get("values", {}))
        if not lines:
            try:
                opts.state.unlink(missing_ok=True)
            except OSError:
                pass
            print(json.dumps({"wakeAgent": False}))
            sys.exit(0)

        stored_lines = _read_reported_lines(opts.state)
        if stored_lines is not None and sorted(lines) == stored_lines:
            print(json.dumps({"wakeAgent": False}))
            sys.exit(0)

        print(report(base, cur, lines))
        _write_state(opts.state, cur.get("commit", ""), lines)
        sys.exit(0)

    elif opts.command == "refresh":
        snap = snapshot(commit=opts.commit)
        content = json.dumps(snap, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        try:
            opts.baseline.write_text(content, encoding="utf-8")
        except Exception as e:
            raise WatchError(f"failed to write baseline to {opts.baseline}: {e}") from e
        short_sha = snap["commit"][:7]
        print(f"baseline: {short_sha} ({snap['committed_at']})")
        sys.exit(0)

    elif opts.command == "show":
        snap = snapshot(commit=opts.commit)
        print(json.dumps(snap, indent=2, ensure_ascii=False, sort_keys=True))
        sys.exit(0)

    elif opts.command == "forget":
        if opts.state.is_file() or opts.state.is_symlink():
            try:
                opts.state.unlink()
                print(f"forgot {opts.state}")
            except OSError as e:
                raise WatchError(f"failed to delete state file at {opts.state}: {e}") from e
        else:
            print("nothing to forget")
        sys.exit(0)

    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    try:
        _run(argv)
    except WatchError as e:
        sys.stderr.write(f"ranking_watch: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
