#!/usr/bin/env python3
"""Validate the pipeline/technic topology of a Hermes worker profile."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


HERMES_ROOT = Path(__file__).resolve().parents[1]


def frontmatter_value(path: Path, key: str) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    match = re.search(rf"^\s*{re.escape(key)}:\s*([^#\n]+)", text[4:end], re.MULTILINE)
    return match.group(1).strip().strip('"\'') if match else None


def capability_names(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        match = re.fullmatch(r"`([^`]+)`", cells[1])
        if match:
            names.add(match.group(1))
    return names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", help="profile directory name, for example creator")
    parser.add_argument(
        "--dispatch",
        type=Path,
        help="optional dispatch reference that must name every canonical technic",
    )
    args = parser.parse_args()

    skills = HERMES_ROOT / "profiles" / args.profile / "skills"
    pipeline = skills / f"{args.profile}-pipeline" / "SKILL.md"
    technic_dir = skills / "technic"
    capabilities = pipeline.parent / "references" / "capabilities.md"
    errors: list[str] = []

    if not pipeline.is_file():
        errors.append(f"missing root pipeline: {pipeline}")
    elif frontmatter_value(pipeline, "name") != f"{args.profile}-pipeline":
        errors.append(f"pipeline frontmatter name must be {args.profile}-pipeline")

    top_level_skills = [
        path for path in skills.glob("*/SKILL.md") if path.parent.name != f"{args.profile}-pipeline"
    ]
    for path in top_level_skills:
        errors.append(f"non-pipeline root skill must move under technic/: {path}")

    leaves: dict[str, Path] = {}
    if not technic_dir.is_dir():
        errors.append(f"missing technic directory: {technic_dir}")
    else:
        for path in sorted(technic_dir.glob("*/SKILL.md")):
            name = frontmatter_value(path, "name")
            category = frontmatter_value(path, "category")
            if not name:
                errors.append(f"missing frontmatter name: {path}")
                continue
            if path.parent.name != name:
                errors.append(f"directory/name mismatch: {path.parent.name} != {name}")
            if category != "technic":
                errors.append(f"technic category must be 'technic': {path}")
            if name in leaves:
                errors.append(f"duplicate technic name {name}: {leaves[name]} and {path}")
            leaves[name] = path

        nested = [path for path in technic_dir.glob("*/*/SKILL.md")]
        for path in nested:
            errors.append(f"technic must be a direct leaf under technic/: {path}")

    if not capabilities.is_file():
        errors.append(f"missing capability registry: {capabilities}")
    else:
        routed = capability_names(capabilities)
        missing_files = routed - leaves.keys()
        missing_routes = leaves.keys() - routed
        for name in sorted(missing_files):
            errors.append(f"capability has no technic directory: {name}")
        for name in sorted(missing_routes):
            errors.append(f"technic missing from capability table: {name}")

    if args.dispatch:
        dispatch = args.dispatch
        if not dispatch.is_absolute():
            dispatch = HERMES_ROOT / dispatch
        if not dispatch.is_file():
            errors.append(f"dispatch reference not found: {dispatch}")
        else:
            dispatch_text = dispatch.read_text(encoding="utf-8")
            for name in sorted(leaves):
                if f"`{name}`" not in dispatch_text:
                    errors.append(f"dispatch reference does not name {name}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print(
        f"PASS: {args.profile} has one root pipeline and "
        f"{len(leaves)} routed technic leaves"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
