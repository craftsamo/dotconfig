#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Validate Hermes skill topology, metadata, routing, and Git ownership."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

import yaml


HERMES_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HERMES_ROOT.parent
WORKER_PROFILES = (
    "planner",
    "engineer",
    "researcher",
    "searcher",
    "creator",
    "writer",
    "marketer",
)
ALL_PROFILES = ("assistant", *WORKER_PROFILES)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").lstrip("\ufeff")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    data = yaml.safe_load(text[4:end])
    return data if isinstance(data, dict) else {}


def hermes_category(data: dict[str, Any]) -> str | None:
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    hermes = metadata.get("hermes")
    if not isinstance(hermes, dict):
        return None
    category = hermes.get("category")
    return str(category) if category is not None else None


def capability_names(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        cell = cells[1]
        if len(cell) > 2 and cell.startswith("`") and cell.endswith("`"):
            names.add(cell[1:-1])
    return names


def relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def is_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "--", relative(path)],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


def tracked_learned_files() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--",
            "hermes/skills/learned/**",
            "hermes/profiles/*/skills/learned/**",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def untracked_managed_files() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "hermes/skills/orchestration/**",
            "hermes/skills/workspaces/**",
            "hermes/profiles/*/skills/*-pipeline/**",
            "hermes/profiles/*/skills/technic/**",
            "hermes/profiles/assistant/skills/desks/**",
            "hermes/plugins/skill-topology/**",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def validate_skill(
    path: Path,
    expected_name: str,
    errors: list[str],
    expected_category: str | None = None,
) -> None:
    data = frontmatter(path)
    if not data:
        errors.append(f"missing or invalid frontmatter: {path}")
        return
    if data.get("name") != expected_name:
        errors.append(f"frontmatter name must be {expected_name}: {path}")
    if expected_category and hermes_category(data) != expected_category:
        errors.append(
            f"metadata.hermes.category must be {expected_category}: {path}"
        )


def validate_allowed_skill_roots(
    skills: Path,
    allowed: set[tuple[str, ...]],
    errors: list[str],
) -> None:
    for entry in skills.iterdir():
        if entry.is_symlink():
            errors.append(f"local skill root must not contain symlinks: {entry}")

    for path in sorted(skills.rglob("SKILL.md")):
        rel = path.relative_to(skills)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.parts not in allowed:
            errors.append(f"unexpected skill root: {path}")


def validate_git_boundary(
    managed: list[Path], learned: Path, errors: list[str]
) -> None:
    for path in managed:
        if path.exists() and is_ignored(path):
            errors.append(f"managed skill path is gitignored: {path}")
    if not is_ignored(learned / ".gitignore-probe"):
        errors.append(f"learned skill path must be gitignored: {learned}")


def validate_plugin_source(errors: list[str]) -> None:
    plugin = HERMES_ROOT / "plugins" / "skill-topology"
    manifest = plugin / "plugin.yaml"
    implementation = plugin / "__init__.py"
    if not manifest.is_file():
        errors.append(f"skill-topology manifest not found: {manifest}")
    elif load_yaml(manifest).get("name") != "skill-topology":
        errors.append(f"skill-topology manifest has the wrong name: {manifest}")
    if not implementation.is_file():
        errors.append(f"skill-topology implementation not found: {implementation}")


def validate_plugin_enabled(config: Path, errors: list[str]) -> None:
    if not config.is_file():
        errors.append(f"profile config not found: {config}")
        return
    enabled = load_yaml(config).get("plugins", {}).get("enabled", [])
    if not isinstance(enabled, list) or "skill-topology" not in enabled:
        errors.append(f"skill-topology plugin is not enabled: {config}")


def validate_worker(
    profile: str,
    errors: list[str],
    dispatch: Path | None = None,
) -> tuple[int, int]:
    profile_root = HERMES_ROOT / "profiles" / profile
    skills = profile_root / "skills"
    pipeline_name = f"{profile}-pipeline"
    pipeline_dir = skills / pipeline_name
    pipeline = pipeline_dir / "SKILL.md"
    technic_dir = skills / "technic"
    learned_dir = skills / "learned"

    if not pipeline.is_file():
        errors.append(f"missing root pipeline: {pipeline}")
    else:
        validate_skill(pipeline, pipeline_name, errors)

    if not technic_dir.is_dir():
        errors.append(f"missing technic directory: {technic_dir}")

    leaves: dict[str, Path] = {}
    if technic_dir.is_dir():
        for path in sorted(technic_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors, expected_category="technic")
            if name in leaves:
                errors.append(f"duplicate technic name {name}: {leaves[name]} and {path}")
            leaves[name] = path

    learned: dict[str, Path] = {}
    if learned_dir.is_dir():
        for path in sorted(learned_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors)
            learned[name] = path

    allowed = {(pipeline_name, "SKILL.md")}
    allowed.update(("technic", name, "SKILL.md") for name in leaves)
    allowed.update(("learned", name, "SKILL.md") for name in learned)
    validate_allowed_skill_roots(skills, allowed, errors)

    capabilities = pipeline_dir / "references" / "capabilities.md"
    if capabilities.is_file():
        routed = capability_names(capabilities)
        for name in sorted(routed - leaves.keys()):
            errors.append(f"capability has no technic directory: {name}")
        for name in sorted(leaves.keys() - routed):
            errors.append(f"technic missing from capability table: {name}")

    if dispatch:
        resolved = dispatch if dispatch.is_absolute() else HERMES_ROOT / dispatch
        if not resolved.is_file():
            errors.append(f"dispatch reference not found: {resolved}")
        else:
            dispatch_text = resolved.read_text(encoding="utf-8")
            for name in sorted(leaves):
                if f"`{name}`" not in dispatch_text:
                    errors.append(f"dispatch reference does not name {name}")

    validate_git_boundary([pipeline_dir, technic_dir], learned_dir, errors)
    validate_plugin_enabled(profile_root / "config.yaml", errors)
    return len(leaves), len(learned)


def validate_assistant(errors: list[str]) -> tuple[int, int, int]:
    profile_root = HERMES_ROOT / "profiles" / "assistant"
    skills = profile_root / "skills"
    desks_dir = skills / "desks"
    technic_dir = skills / "technic"
    learned_dir = skills / "learned"

    if not (HERMES_ROOT / "skills" / "orchestration" / "SKILL.md").is_file():
        errors.append("assistant pipeline equivalent is missing: shared orchestration")
    if not desks_dir.is_dir():
        errors.append(f"missing assistant desks directory: {desks_dir}")
    if not technic_dir.is_dir():
        errors.append(f"missing assistant technic directory: {technic_dir}")

    groups: dict[str, dict[str, Path]] = {"desks": {}, "technic": {}, "learned": {}}
    for category, directory in (
        ("desks", desks_dir),
        ("technic", technic_dir),
        ("learned", learned_dir),
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(
                path,
                name,
                errors,
                expected_category=category if category != "learned" else None,
            )
            groups[category][name] = path

    allowed: set[tuple[str, ...]] = set()
    for category, skills_by_name in groups.items():
        allowed.update((category, name, "SKILL.md") for name in skills_by_name)
    validate_allowed_skill_roots(skills, allowed, errors)

    config = profile_root / "config.yaml"
    if config.is_file():
        data = load_yaml(config)
        dm_topics = (
            data.get("platforms", {})
            .get("telegram", {})
            .get("extra", {})
            .get("dm_topics", [])
        )
        for chat in dm_topics if isinstance(dm_topics, list) else []:
            for topic in chat.get("topics", []) if isinstance(chat, dict) else []:
                skill = topic.get("skill") if isinstance(topic, dict) else None
                if skill and skill not in groups["desks"]:
                    errors.append(f"Telegram topic binds a non-desk skill: {skill}")

    validate_git_boundary([desks_dir, technic_dir], learned_dir, errors)
    if config.is_file():
        validate_plugin_enabled(config, errors)
    validate_plugin_enabled(profile_root / "config.example.yaml", errors)
    return len(groups["desks"]), len(groups["technic"]), len(groups["learned"])


def validate_shared(errors: list[str]) -> tuple[int, int]:
    skills = HERMES_ROOT / "skills"
    orchestration = skills / "orchestration"
    workspaces = skills / "workspaces"
    learned_dir = skills / "learned"

    managed: dict[str, Path] = {}
    orchestration_skill = orchestration / "SKILL.md"
    if orchestration_skill.is_file():
        validate_skill(orchestration_skill, "orchestration", errors)
        managed["orchestration"] = orchestration_skill
    else:
        errors.append(f"missing shared orchestration skill: {orchestration_skill}")

    for path in sorted(workspaces.glob("*/SKILL.md")):
        name = path.parent.name
        validate_skill(path, name, errors)
        managed[name] = path

    learned: dict[str, Path] = {}
    if learned_dir.is_dir():
        for path in sorted(learned_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors)
            learned[name] = path

    allowed = {("orchestration", "SKILL.md")}
    allowed.update(("workspaces", name, "SKILL.md") for name in managed if name != "orchestration")
    allowed.update(("learned", name, "SKILL.md") for name in learned)
    validate_allowed_skill_roots(skills, allowed, errors)
    validate_git_boundary([orchestration, workspaces], learned_dir, errors)
    validate_plugin_enabled(HERMES_ROOT / "config.yaml", errors)
    return len(managed), len(learned)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", nargs="?", choices=ALL_PROFILES)
    parser.add_argument("--all", action="store_true", help="validate shared and all profiles")
    parser.add_argument(
        "--strict-git",
        action="store_true",
        help="fail instead of warn when managed skill files are untracked",
    )
    parser.add_argument(
        "--dispatch",
        type=Path,
        help="optional dispatch reference that must name every profile technic",
    )
    args = parser.parse_args()

    if args.all == bool(args.profile):
        parser.error("choose exactly one profile or --all")
    if args.all and args.dispatch:
        parser.error("--dispatch requires one worker profile")
    if args.strict_git and not args.all:
        parser.error("--strict-git requires --all")
    if args.profile == "assistant" and args.dispatch:
        parser.error("--dispatch is only valid for worker profiles")

    errors: list[str] = []
    warnings: list[str] = []
    summaries: list[str] = []

    if args.all:
        validate_plugin_source(errors)
        managed, learned = validate_shared(errors)
        summaries.append(f"shared={managed} managed/{learned} learned")
        desks, technics, learned = validate_assistant(errors)
        summaries.append(
            f"assistant={desks} desks/{technics} technics/{learned} learned"
        )
        for profile in WORKER_PROFILES:
            technics, learned = validate_worker(profile, errors)
            summaries.append(f"{profile}={technics} technics/{learned} learned")
        for path in tracked_learned_files():
            errors.append(f"learned skill file must not be tracked: {path}")
        for path in untracked_managed_files():
            message = f"managed skill file is untracked: {path}"
            (errors if args.strict_git else warnings).append(message)
    elif args.profile == "assistant":
        desks, technics, learned = validate_assistant(errors)
        summaries.append(
            f"assistant={desks} desks/{technics} technics/{learned} learned"
        )
    else:
        technics, learned = validate_worker(args.profile, errors, args.dispatch)
        summaries.append(f"{args.profile}={technics} technics/{learned} learned")

    for warning in warnings:
        print(f"WARN: {warning}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print(f"PASS: {'; '.join(summaries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
