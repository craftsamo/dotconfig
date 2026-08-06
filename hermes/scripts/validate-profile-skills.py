#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Validate Hermes skill topology, metadata, routing, and Git ownership.

Workflow v5: the machine-readable authority is
skills/orchestration/references/workflow-contract.yaml (version 2). This
validator checks that contract's shape, the files it points at, and the
skill-tree topology (managed pipelines/technics vs runtime learned/ dirs,
frontmatter, plugin enablement, Git ownership boundaries).
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

import yaml


HERMES_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HERMES_ROOT.parent
WORKFLOW_CONTRACT = (
    HERMES_ROOT
    / "skills"
    / "orchestration"
    / "references"
    / "workflow-contract.yaml"
)
WORKER_PROFILES = (
    "engineer",
    "researcher",
    "searcher",
    "creator",
    "writer",
    "marketer",
)
ALL_PROFILES = ("assistant", *WORKER_PROFILES)
WORKER_MUTATION_GUARD_PLUGIN = "kanban-worker-mutation-guard"
EXPECTED_MODES = ["chat", "plan", "execute", "qa"]
EXPECTED_TIERS = ["inline", "resident", "kanban"]
EXPECTED_GRANT_KINDS = {"authority", "budget", "publish"}
EXPECTED_KANBAN_USES = {"fire_and_forget", "cron", "mass_parallel", "scheduled"}
EXPECTED_CAPABILITIES = {
    "creative",
    "writing",
    "research",
    "engineering",
    "marketing",
}
EXPECTED_BRIEF_FIELDS = {"goal", "context", "inputs", "deliverable", "constraints"}
QA_CONTRACT_FILES = {
    "index.md",
    "ascii-art.md",
    "ascii-video.md",
    "audio.md",
    "browser-media.md",
    "comic.md",
    "data-visualization.md",
    "excalidraw-diagram.md",
    "icon-set.md",
    "infographic.md",
    "pixel-art.md",
    "pixel-video.md",
    "prose.md",
    "raster-image.md",
    "script.md",
    "song.md",
    "sourced-asset.md",
    "svg-diagram.md",
    "text-visual.md",
    "video.md",
    "voice.md",
}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_unique_mapping,
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_workflow_contract(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, yaml.YAMLError) as error:
        errors.append(f"invalid workflow contract YAML: {path}: {error}")
        return None
    if not isinstance(data, dict):
        errors.append(f"workflow contract must be a mapping: {path}")
        return None
    return data


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


# ── Workflow contract (v2) ──────────────────────────────────────────────


def validate_workflow_contract_data(
    data: dict[str, Any], errors: list[str]
) -> int | None:
    version = data.get("version")
    if version != 2:
        errors.append("workflow contract version must be 2")

    orchestration = data.get("orchestration")
    if not isinstance(orchestration, dict):
        errors.append("workflow contract orchestration must be a mapping")
        orchestration = {}
    if orchestration.get("front_door") != "assistant":
        errors.append("workflow contract front door must be assistant")
    if orchestration.get("modes") != EXPECTED_MODES:
        errors.append(
            "workflow contract modes must be chat, plan, execute, and qa"
        )
    if orchestration.get("tiers") != EXPECTED_TIERS:
        errors.append(
            "workflow contract tiers must be inline, resident, and kanban"
        )
    if orchestration.get("default_heavy_tier") != "resident":
        errors.append("workflow contract default heavy tier must be resident")
    if orchestration.get("approval_gates") != ["plan"]:
        errors.append("workflow contract approval gates must be exactly plan")
    if orchestration.get("card_registration_owner") != "assistant":
        errors.append("workflow contract card registration owner must be assistant")
    if orchestration.get("worker_card_creation") != "forbidden":
        errors.append("workflow contract must forbid worker card creation")
    if orchestration.get("qa_owner") != "assistant":
        errors.append("workflow contract qa owner must be assistant")

    grants = data.get("grants")
    if not isinstance(grants, dict) or set(grants) != EXPECTED_GRANT_KINDS:
        errors.append(
            "workflow contract grants must be authority, budget, and publish"
        )
        grants = {}
    authority = grants.get("authority", {})
    if isinstance(authority, dict):
        if authority.get("presets") != ["A1", "A2", "A3"]:
            errors.append("authority grant presets must be A1, A2, A3")
        if authority.get("default") != "A1":
            errors.append("authority grant default must be A1")
    publish = grants.get("publish", {})
    if isinstance(publish, dict) and publish.get("default") != "draft_only":
        errors.append("publish grant default must be draft_only")

    specialists = data.get("specialists")
    if not isinstance(specialists, dict):
        errors.append("workflow contract specialists must be a mapping")
        specialists = {}
    if set(specialists) != set(WORKER_PROFILES):
        errors.append(
            "workflow contract specialists must be exactly: "
            + ", ".join(WORKER_PROFILES)
        )
    references = HERMES_ROOT / "skills" / "orchestration" / "references"
    for name, spec in specialists.items():
        if not isinstance(spec, dict):
            errors.append(f"specialist {name} must be a mapping")
            continue
        if spec.get("pipeline") != f"{name}-pipeline":
            errors.append(f"specialist {name} pipeline must be {name}-pipeline")
        capability = spec.get("capability")
        if capability not in EXPECTED_CAPABILITIES:
            errors.append(f"specialist {name} has an unknown capability: {capability}")
        elif not (references / f"{capability}.md").is_file():
            errors.append(
                f"specialist {name} capability reference missing: {capability}.md"
            )
        grant = spec.get("grant")
        if grant is not None and grant not in EXPECTED_GRANT_KINDS:
            errors.append(f"specialist {name} has an unknown grant kind: {grant}")

    resident = data.get("resident_session")
    if not isinstance(resident, dict):
        errors.append("workflow contract resident_session must be a mapping")
        resident = {}
    wrapper = resident.get("wrapper")
    if not isinstance(wrapper, str) or not (
        HERMES_ROOT / "profiles" / wrapper
    ).is_file():
        errors.append(f"resident session wrapper script missing: {wrapper}")
    if resident.get("lifecycle") != "close_on_acceptance":
        errors.append("resident session lifecycle must be close_on_acceptance")
    brief = resident.get("brief_fields", {})
    required = set(brief.get("required", [])) if isinstance(brief, dict) else set()
    if required != EXPECTED_BRIEF_FIELDS:
        errors.append(
            "resident session brief required fields must be goal, context, "
            "inputs, deliverable, and constraints"
        )

    kanban = data.get("kanban")
    if not isinstance(kanban, dict):
        errors.append("workflow contract kanban must be a mapping")
        kanban = {}
    if set(kanban.get("uses", [])) != EXPECTED_KANBAN_USES:
        errors.append(
            "kanban uses must be fire_and_forget, cron, mass_parallel, and "
            "scheduled"
        )
    if kanban.get("pipeline_pin") != "required":
        errors.append("kanban pipeline pin must be required")
    for key in ("block_resolver", "scheduled_sweeper"):
        script = kanban.get(key)
        if not isinstance(script, str) or not (
            HERMES_ROOT / "profiles" / script
        ).is_file():
            errors.append(f"kanban {key} script missing: {script}")
    markers = kanban.get("retired_markers")
    if not isinstance(markers, list) or not markers or any(
        not isinstance(marker, str) for marker in markers
    ):
        errors.append("kanban retired_markers must be a non-empty string list")

    qa_dir = references / "qa"
    present = {path.name for path in qa_dir.glob("*.md")} if qa_dir.is_dir() else set()
    for name in sorted(QA_CONTRACT_FILES - present):
        errors.append(f"QA contract file missing: references/qa/{name}")
    for name in sorted(present - QA_CONTRACT_FILES):
        errors.append(f"unexpected QA contract file: references/qa/{name}")

    return version if isinstance(version, int) else None


def validate_workflow_contract(errors: list[str]) -> int | None:
    if not WORKFLOW_CONTRACT.is_file():
        errors.append(f"workflow contract not found: {WORKFLOW_CONTRACT}")
        return None
    data = load_workflow_contract(WORKFLOW_CONTRACT, errors)
    if data is None:
        return None
    return validate_workflow_contract_data(data, errors)


# ── Git ownership ───────────────────────────────────────────────────────


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
            "hermes/profiles/*/skills/*-pipeline/**",
            "hermes/profiles/*/skills/technic/**",
            "hermes/profiles/assistant/skills/desks/**",
            "hermes/plugins/skill-topology/**",
            f"hermes/plugins/{WORKER_MUTATION_GUARD_PLUGIN}/**",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


# ── Skill topology ──────────────────────────────────────────────────────


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
    for name in ("skill-topology", WORKER_MUTATION_GUARD_PLUGIN):
        plugin = HERMES_ROOT / "plugins" / name
        manifest = plugin / "plugin.yaml"
        implementation = plugin / "__init__.py"
        if not manifest.is_file():
            errors.append(f"{name} manifest not found: {manifest}")
        elif load_yaml(manifest).get("name") != name:
            errors.append(f"{name} manifest has the wrong name: {manifest}")
        if not implementation.is_file():
            errors.append(f"{name} implementation not found: {implementation}")


def validate_plugin_enabled(profile: str, config: Path, errors: list[str]) -> None:
    if not config.is_file():
        errors.append(f"profile config not found: {config}")
        return
    enabled = load_yaml(config).get("plugins", {}).get("enabled", [])
    if not isinstance(enabled, list) or "skill-topology" not in enabled:
        errors.append(f"skill-topology plugin is not enabled: {config}")
    if profile in WORKER_PROFILES and (
        not isinstance(enabled, list) or WORKER_MUTATION_GUARD_PLUGIN not in enabled
    ):
        errors.append(
            f"{WORKER_MUTATION_GUARD_PLUGIN} plugin is not enabled: {config}"
        )


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
                errors.append(
                    f"duplicate technic name {name}: {leaves[name]} and {path}"
                )
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
    validate_plugin_enabled(profile, profile_root / "config.yaml", errors)
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
        validate_plugin_enabled("assistant", config, errors)
    validate_plugin_enabled("assistant", profile_root / "config.example.yaml", errors)
    return len(groups["desks"]), len(groups["technic"]), len(groups["learned"])


def validate_shared(errors: list[str]) -> tuple[int, int]:
    skills = HERMES_ROOT / "skills"
    orchestration = skills / "orchestration"
    learned_dir = skills / "learned"

    managed: dict[str, Path] = {}
    orchestration_skill = orchestration / "SKILL.md"
    if orchestration_skill.is_file():
        validate_skill(orchestration_skill, "orchestration", errors)
        managed["orchestration"] = orchestration_skill
    else:
        errors.append(f"missing shared orchestration skill: {orchestration_skill}")

    learned: dict[str, Path] = {}
    if learned_dir.is_dir():
        for path in sorted(learned_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors)
            learned[name] = path

    allowed = {("orchestration", "SKILL.md")}
    allowed.update(("learned", name, "SKILL.md") for name in learned)
    validate_allowed_skill_roots(skills, allowed, errors)
    validate_git_boundary([orchestration], learned_dir, errors)
    validate_plugin_enabled("default", HERMES_ROOT / "config.yaml", errors)
    return len(managed), len(learned)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", nargs="?", choices=ALL_PROFILES)
    parser.add_argument(
        "--all", action="store_true", help="validate shared and all profiles"
    )
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
        workflow_version = validate_workflow_contract(errors)
        if workflow_version is not None:
            summaries.append(f"workflow-contract=v{workflow_version}")
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
