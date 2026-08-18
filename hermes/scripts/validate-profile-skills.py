#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Validate Hermes skill topology, metadata, routing, and Git ownership.

Workflow v5 (assistant-pipeline): the assistant profile owns the front-door
reference tree at profiles/assistant/skills/assistant-pipeline/references/
— modes chat / plan / execute / quality-assurance, each with optional
capability subdirectories and work-category leaves. The kanban card catalog
is the union of `card_units` front matter across the execute mode tree and
is validated structurally here. The `default-pipeline` skill in the shared
skills/ dir is a thin CLI adapter over that tree. This validator checks the
tree topology, the catalog schema, index routing completeness, worker
pipeline/technic topology, plugin enablement, and Git ownership boundaries.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


HERMES_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HERMES_ROOT.parent
ASSISTANT_PIPELINE = (
    HERMES_ROOT / "profiles" / "assistant" / "skills" / "assistant-pipeline"
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
EXPECTED_MODES = ("chat", "plan", "execute", "quality-assurance")
EXPECTED_CAPABILITIES = {
    "creative",
    "writing",
    "research",
    "search",
    "engineering",
    "marketing",
}
# Capability subdirectories are allowed in these modes; chat stays flat.
CAPABILITY_MODES = {"plan", "execute", "quality-assurance"}
# The one sanctioned (mode, capability, subdir) below a capability dir:
# the genre-preset shelf (Format × Theme catalog for creative planning).
PRESET_SHELF = ("plan", "creative", "formats")
# Files that must exist directly inside a mode dir (beyond index.md).
REQUIRED_MODE_FILES = {
    "chat": {"workspace-ops.md", "cron.md", "lookups.md"},
    "execute": {"resident-sessions.md", "kanban-lite.md", "scheduled.md"},
}
# Verification contracts that must exist (migration-loss guard); extra
# leaves may grow beside them as long as the dir index routes them.
REQUIRED_QA_CONTRACTS = {
    "creative": {
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
        "raster-image.md",
        "song.md",
        "sourced-asset.md",
        "svg-diagram.md",
        "text-visual.md",
        "video.md",
        "voice.md",
    },
    "research": {
        "evidence-pack.md",
        "tradeoff-matrix.md",
        "fact-check.md",
        "guidance.md",
    },
    "search": {"lookup.md", "sweep.md", "hunt.md"},
    "writing": {"prose.md", "script.md"},
}
CARD_UNIT_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


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


# ── Assistant pipeline tree ─────────────────────────────────────────────


def rel_pipeline(path: Path) -> str:
    return path.relative_to(ASSISTANT_PIPELINE).as_posix()


def validate_index_routes(directory: Path, errors: list[str]) -> None:
    """Every non-index .md beside an index.md must be named in it."""
    index = directory / "index.md"
    if not index.is_file():
        errors.append(f"missing index.md: {rel_pipeline(directory)}")
        return
    index_text = index.read_text(encoding="utf-8")
    for leaf in sorted(directory.glob("*.md")):
        if leaf.name == "index.md":
            continue
        if leaf.name not in index_text:
            errors.append(
                f"index.md does not route {leaf.name}: {rel_pipeline(directory)}"
            )


def validate_card_units(
    path: Path,
    seen: dict[str, Path],
    errors: list[str],
    catalog: dict[str, str] | None = None,
) -> int:
    units = frontmatter(path).get("card_units")
    if units is None:
        return 0
    if not isinstance(units, list) or not units:
        errors.append(f"card_units must be a non-empty list: {rel_pipeline(path)}")
        return 0
    count = 0
    for unit in units:
        if not isinstance(unit, dict):
            errors.append(f"card_units entry must be a mapping: {rel_pipeline(path)}")
            continue
        name = unit.get("name")
        if not isinstance(name, str) or not CARD_UNIT_NAME.match(name):
            errors.append(
                f"card_units name must be kebab-case: {name!r} in {rel_pipeline(path)}"
            )
            continue
        if name in seen:
            errors.append(
                f"duplicate card unit {name}: {rel_pipeline(seen[name])} "
                f"and {rel_pipeline(path)}"
            )
        seen[name] = path
        assignee = unit.get("assignee")
        if assignee not in WORKER_PROFILES:
            errors.append(
                f"card unit {name} assignee must be a worker profile "
                f"({assignee!r}): {rel_pipeline(path)}"
            )
        elif catalog is not None:
            catalog[name] = assignee
        inputs = unit.get("required_inputs")
        if (
            not isinstance(inputs, list)
            or not inputs
            or any(not isinstance(item, str) or not item for item in inputs)
        ):
            errors.append(
                f"card unit {name} required_inputs must be a non-empty "
                f"string list: {rel_pipeline(path)}"
            )
        if not isinstance(unit.get("unit_cap"), str) or not unit["unit_cap"]:
            errors.append(
                f"card unit {name} unit_cap must be a non-empty string: "
                f"{rel_pipeline(path)}"
            )
        runtime_cap = unit.get("runtime_cap")
        if not isinstance(runtime_cap, int) or isinstance(runtime_cap, bool) or (
            runtime_cap <= 0
        ):
            errors.append(
                f"card unit {name} runtime_cap must be a positive integer: "
                f"{rel_pipeline(path)}"
            )
        count += 1
    return count


def collect_card_catalog() -> dict[str, str]:
    """Best-effort card catalog (unit name -> assignee) from the execute tree.

    Used when validating a single worker profile without the full assistant
    pass; schema errors are ignored here (the --all pass reports them).
    """
    catalog: dict[str, str] = {}
    execute = ASSISTANT_PIPELINE / "references" / "execute"
    if not execute.is_dir():
        return catalog
    for path in sorted(execute.rglob("*.md")):
        units = frontmatter(path).get("card_units")
        if not isinstance(units, list):
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            name = unit.get("name")
            assignee = unit.get("assignee")
            if isinstance(name, str) and assignee in WORKER_PROFILES:
                catalog[name] = assignee
    return catalog


def validate_assistant_pipeline(
    errors: list[str],
) -> tuple[int, dict[str, str]]:
    """Validate the assistant-pipeline skill and its reference tree.

    Returns (markdown reference file count, card catalog name -> assignee).
    """
    catalog: dict[str, str] = {}
    skill = ASSISTANT_PIPELINE / "SKILL.md"
    if not skill.is_file():
        errors.append(f"missing assistant pipeline skill: {skill}")
        return 0, catalog
    validate_skill(skill, "assistant-pipeline", errors, expected_category="orchestration")

    references = ASSISTANT_PIPELINE / "references"
    if not references.is_dir():
        errors.append(f"missing assistant pipeline references: {references}")
        return 0, catalog

    for entry in sorted(references.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_file():
            errors.append(f"references root must hold mode dirs only: {entry.name}")
        elif entry.name not in EXPECTED_MODES:
            errors.append(f"unexpected mode directory: {entry.name}")
    for mode in EXPECTED_MODES:
        if not (references / mode).is_dir():
            errors.append(f"missing mode directory: {mode}")

    files = 0
    units: dict[str, Path] = {}
    for mode in EXPECTED_MODES:
        mode_dir = references / mode
        if not mode_dir.is_dir():
            continue
        validate_index_routes(mode_dir, errors)
        for name in sorted(REQUIRED_MODE_FILES.get(mode, set())):
            if not (mode_dir / name).is_file():
                errors.append(f"missing required mode file: {mode}/{name}")
        for entry in sorted(mode_dir.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_file():
                if entry.suffix != ".md":
                    errors.append(f"non-markdown reference: {rel_pipeline(entry)}")
                    continue
                files += 1
                if mode == "execute":
                    validate_card_units(entry, units, errors, catalog)
                elif "card_units" in frontmatter(entry):
                    errors.append(
                        f"card_units are only legal under execute/: "
                        f"{rel_pipeline(entry)}"
                    )
                continue
            # capability subdirectory
            if mode not in CAPABILITY_MODES:
                errors.append(
                    f"{mode}/ must stay flat; unexpected dir: {rel_pipeline(entry)}"
                )
                continue
            if entry.name not in EXPECTED_CAPABILITIES:
                errors.append(f"unexpected capability dir: {rel_pipeline(entry)}")
                continue
            validate_index_routes(entry, errors)
            for leaf in sorted(entry.iterdir()):
                if leaf.name.startswith("."):
                    continue
                if leaf.is_dir():
                    # The genre-preset shelf is the one sanctioned subdir:
                    # plan/creative/formats/ holds Format × Theme presets
                    # extracted from accepted productions (references only —
                    # never technics, never family leaves). Flat, .md only,
                    # routed by its own index.md.
                    if (mode, entry.name, leaf.name) == PRESET_SHELF:
                        validate_index_routes(leaf, errors)
                        for preset in sorted(leaf.iterdir()):
                            if preset.name.startswith("."):
                                continue
                            if preset.is_dir():
                                errors.append(
                                    f"no nesting below the preset shelf: "
                                    f"{rel_pipeline(preset)}"
                                )
                            elif preset.suffix != ".md":
                                errors.append(
                                    f"non-markdown reference: "
                                    f"{rel_pipeline(preset)}"
                                )
                            else:
                                files += 1
                        continue
                    errors.append(
                        f"no nesting below capability dirs: {rel_pipeline(leaf)}"
                    )
                    continue
                if leaf.suffix != ".md":
                    errors.append(f"non-markdown reference: {rel_pipeline(leaf)}")
                    continue
                files += 1
                if mode == "execute":
                    validate_card_units(leaf, units, errors, catalog)
                elif "card_units" in frontmatter(leaf):
                    errors.append(
                        f"card_units are only legal under execute/: "
                        f"{rel_pipeline(leaf)}"
                    )

    qa_root = references / "quality-assurance"
    for capability, required in REQUIRED_QA_CONTRACTS.items():
        directory = qa_root / capability
        present = (
            {p.name for p in directory.glob("*.md")} if directory.is_dir() else set()
        )
        for name in sorted(required - present):
            errors.append(
                f"QA contract file missing: quality-assurance/{capability}/{name}"
            )

    return files, catalog


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
            "hermes/skills/default-pipeline/**",
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
        # Private-overlay dirs (desks, assistant-pipeline) are sanctioned
        # symlinks into ~/.config/private; anything else stays forbidden
        # (relative links into mutable stores have broken silently before).
        if entry.is_symlink() and not is_overlay_link(entry):
            errors.append(f"local skill root must not contain symlinks: {entry}")

    for path in sorted(skills.rglob("SKILL.md")):
        rel = path.relative_to(skills)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.parts not in allowed:
            errors.append(f"unexpected skill root: {path}")


PRIVATE_OVERLAY = Path.home() / ".config" / "private"


def is_overlay_link(path: Path) -> bool:
    """True for a managed dir provided by the private overlay (a symlink into
    ~/.config/private). Such paths are gitignored here on purpose — their
    content is tracked by the private-dotconfig repo instead."""
    if not path.is_symlink():
        return False
    try:
        target = path.resolve(strict=True)
    except OSError:
        return False
    return target.is_relative_to(PRIVATE_OVERLAY.resolve())


def validate_git_boundary(
    managed: list[Path], learned: Path, errors: list[str]
) -> None:
    for path in managed:
        if path.is_symlink() and not is_overlay_link(path):
            errors.append(
                f"managed skill path is a symlink outside the private overlay: {path}"
            )
        elif path.exists() and not path.is_symlink() and is_ignored(path):
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


def validate_assistant_messaging_config(
    config: Path, errors: list[str]
) -> None:
    """Pin the Assistant's Telegram/Discord front-door parity and routing."""
    if not config.is_file():
        errors.append(f"profile config not found: {config}")
        return

    data = load_yaml(config)
    platform_toolsets = data.get("platform_toolsets", {})
    if not isinstance(platform_toolsets, dict):
        errors.append(f"platform_toolsets must be a mapping: {config}")
        return

    telegram_tools = platform_toolsets.get("telegram")
    discord_tools = platform_toolsets.get("discord")
    if not isinstance(discord_tools, list) or not discord_tools:
        errors.append(f"Assistant Discord toolset must be non-empty: {config}")
    elif discord_tools != telegram_tools:
        errors.append(
            f"Assistant Discord toolset must match Telegram exactly: {config}"
        )

    discord = data.get("discord", {})
    if not isinstance(discord, dict):
        errors.append(f"discord config must be a mapping: {config}")
        return
    allowed_raw = discord.get("allowed_channels")
    if isinstance(allowed_raw, str):
        allowed_channels = {
            channel.strip() for channel in allowed_raw.split(",") if channel.strip()
        }
    elif isinstance(allowed_raw, list):
        allowed_channels = {str(channel) for channel in allowed_raw if str(channel)}
    else:
        allowed_channels = set()
    if not allowed_channels:
        errors.append(f"Assistant Discord channels must be allowlisted: {config}")
    if discord.get("require_mention") is not True:
        errors.append(f"Assistant Discord must require channel mentions: {config}")
    if discord.get("auto_thread") is not True:
        errors.append(f"Assistant Discord auto-threading must stay enabled: {config}")

    bindings = discord.get("channel_skill_bindings", [])
    pipeline_channels: set[str] = set()
    if isinstance(bindings, list):
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            skills = binding.get("skills")
            if binding.get("skill") == "assistant-pipeline" or (
                isinstance(skills, list) and "assistant-pipeline" in skills
            ):
                pipeline_channels.add(str(binding.get("id")))
    for channel in sorted(allowed_channels - pipeline_channels):
        errors.append(
            f"Assistant Discord channel {channel} must bind assistant-pipeline: {config}"
        )

    prompts = discord.get("channel_prompts", {})
    prompt_channels: set[str] = set()
    if isinstance(prompts, dict):
        prompt_channels = {
            str(channel)
            for channel, prompt in prompts.items()
            if isinstance(prompt, str) and prompt.strip()
        }
    for channel in sorted(allowed_channels - prompt_channels):
        errors.append(
            f"Assistant Discord channel {channel} must have a channel prompt: {config}"
        )
    discord_dm_channels = pipeline_channels - allowed_channels
    if not discord_dm_channels:
        errors.append(f"Assistant Discord must bind at least one DM channel: {config}")
    for channel in sorted(pipeline_channels - prompt_channels):
        errors.append(
            f"Assistant Discord binding {channel} must have a channel prompt: {config}"
        )

    telegram = data.get("telegram", {})
    telegram_bindings = (
        telegram.get("channel_skill_bindings", [])
        if isinstance(telegram, dict)
        else []
    )
    telegram_pipeline_chats: set[str] = set()
    if isinstance(telegram_bindings, list):
        for binding in telegram_bindings:
            if not isinstance(binding, dict):
                continue
            skills = binding.get("skills")
            if binding.get("skill") == "assistant-pipeline" or (
                isinstance(skills, list) and "assistant-pipeline" in skills
            ):
                telegram_pipeline_chats.add(str(binding.get("id")))

    telegram_prompts = (
        telegram.get("channel_prompts", {}) if isinstance(telegram, dict) else {}
    )
    telegram_prompt_chats: set[str] = set()
    if isinstance(telegram_prompts, dict):
        telegram_prompt_chats = {
            str(chat)
            for chat, prompt in telegram_prompts.items()
            if isinstance(prompt, str) and prompt.strip()
        }

    platforms = data.get("platforms", {})
    telegram_platform = (
        platforms.get("telegram", {}) if isinstance(platforms, dict) else {}
    )
    telegram_extra = (
        telegram_platform.get("extra", {})
        if isinstance(telegram_platform, dict)
        else {}
    )
    dm_topics = (
        telegram_extra.get("dm_topics", [])
        if isinstance(telegram_extra, dict)
        else []
    )
    telegram_root_chats: set[str] = set()
    if isinstance(dm_topics, list):
        telegram_root_chats = {
            str(chat.get("chat_id"))
            for chat in dm_topics
            if isinstance(chat, dict) and chat.get("chat_id") is not None
        }
    if not telegram_root_chats:
        errors.append(f"Assistant Telegram root chat must be configured: {config}")
    for chat in sorted(telegram_root_chats - telegram_pipeline_chats):
        errors.append(
            f"Assistant Telegram chat {chat} must bind assistant-pipeline: {config}"
        )
    for chat in sorted(telegram_root_chats - telegram_prompt_chats):
        errors.append(
            f"Assistant Telegram chat {chat} must have a channel prompt: {config}"
        )


def validate_worker_card_gate(
    profile: str, catalog: dict[str, str], errors: list[str]
) -> None:
    """The kernel's unit gate must mirror the assistant's card catalog.

    A worker with catalog units must name each of them (backticked) in its
    kernel; a worker with none must declare itself card-free. Every kernel
    must carry the capability-refusal call, and none may claim another
    profile's unit.
    """
    pipeline = (
        HERMES_ROOT
        / "profiles"
        / profile
        / "skills"
        / f"{profile}-pipeline"
        / "SKILL.md"
    )
    if not pipeline.is_file():
        return
    # Normalize whitespace so prose wrapped across lines still matches.
    text = " ".join(pipeline.read_text(encoding="utf-8").split())
    mine = sorted(name for name, who in catalog.items() if who == profile)
    theirs = sorted(name for name, who in catalog.items() if who != profile)
    for name in mine:
        if f"`{name}`" not in text:
            errors.append(
                f"{profile} kernel does not name its catalog unit `{name}`"
            )
    if not mine and "defines no card units" not in text:
        errors.append(
            f"{profile} has no catalog units; its kernel must declare "
            f'"defines no card units"'
        )
    if "kanban_block(kind=capability)" not in text:
        errors.append(
            f"{profile} kernel must refuse non-catalog cards with "
            f"kanban_block(kind=capability)"
        )
    for name in theirs:
        if f"`{name}`" in text:
            errors.append(
                f"{profile} kernel names another profile's catalog unit `{name}`"
            )


def validate_worker(
    profile: str,
    errors: list[str],
    dispatch: Path | None = None,
    catalog: dict[str, str] | None = None,
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

    if catalog is not None:
        validate_worker_card_gate(profile, catalog, errors)
    validate_git_boundary([pipeline_dir, technic_dir], learned_dir, errors)
    validate_plugin_enabled(profile, profile_root / "config.yaml", errors)
    return len(leaves), len(learned)


# ── Creative three-layer alignment ──────────────────────────────────────
#
# Plan decides, creator produces, QA verifies — all keyed by the creator's
# canonical families. The assistant's plan/creative family leaves must pair
# 1:1 with creator technics (plus core:tts as voice.md), and the creative
# QA index's Covers column must map every canonical family to exactly one
# contract.

CREATIVE_PLAN_DIR = ASSISTANT_PIPELINE / "references" / "plan" / "creative"
CREATIVE_QA_DIR = (
    ASSISTANT_PIPELINE / "references" / "quality-assurance" / "creative"
)
CREATIVE_NON_FAMILY_LEAVES = {"index.md", "composite-media.md", "asset-set.md"}
CREATIVE_EXTRA_FAMILIES = {"voice.md": "core:tts"}


def validate_creative_alignment(errors: list[str]) -> None:
    technic_dir = HERMES_ROOT / "profiles" / "creator" / "skills" / "technic"
    if not (technic_dir.is_dir() and CREATIVE_PLAN_DIR.is_dir()):
        return  # missing roots are reported by the profile validators

    technics = {path.parent.name for path in technic_dir.glob("*/SKILL.md")}
    canonical = technics | set(CREATIVE_EXTRA_FAMILIES.values())

    leaves = {
        path.name for path in CREATIVE_PLAN_DIR.glob("*.md")
    } - CREATIVE_NON_FAMILY_LEAVES
    expected = {
        f"{name.removeprefix('creator-')}.md" for name in technics
    } | set(CREATIVE_EXTRA_FAMILIES)
    for name in sorted(expected - leaves):
        errors.append(f"creative plan leaf missing for canonical family: {name}")
    for name in sorted(leaves - expected):
        errors.append(f"creative plan leaf has no canonical family: {name}")

    qa_index = CREATIVE_QA_DIR / "index.md"
    if not qa_index.is_file():
        errors.append(f"missing creative QA index: {qa_index}")
        return
    covered: list[str] = []
    for line in qa_index.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3 or cells[1] == "Contract":
            continue
        contract = cells[1].strip("`")
        if contract.endswith(".md") and not (CREATIVE_QA_DIR / contract).is_file():
            errors.append(f"creative QA route names missing contract: {contract}")
        covered.extend(re.findall(r"`([^`]+)`", cells[2]))
    for name in sorted(canonical):
        count = covered.count(name)
        if count == 0:
            errors.append(f"creative QA Covers misses canonical family: {name}")
        elif count > 1:
            errors.append(
                f"creative QA Covers lists {name} {count} times (must be once)"
            )
    for name in sorted(set(covered) - canonical):
        errors.append(f"creative QA Covers names unknown family: {name}")


# ── Engineering plan-QA alignment ───────────────────────────────────────
#
# Every plan/engineering archetype leaf must have a matching inspection
# row in the engineering QA inspection leaf (its verification default's
# receiving side), and vice versa — a new archetype without an inspection
# row would ship with an ungated verification default.

ENGINEERING_PLAN_DIR = ASSISTANT_PIPELINE / "references" / "plan" / "engineering"
ENGINEERING_QA_INSPECTION = (
    ASSISTANT_PIPELINE
    / "references"
    / "quality-assurance"
    / "engineering"
    / "inspection.md"
)


def validate_engineering_alignment(errors: list[str]) -> None:
    if not (ENGINEERING_PLAN_DIR.is_dir() and ENGINEERING_QA_INSPECTION.is_file()):
        return  # missing roots are reported by the tree validators

    leaves = {path.stem for path in ENGINEERING_PLAN_DIR.glob("*.md")} - {"index"}
    rows: set[str] = set()
    for line in ENGINEERING_QA_INSPECTION.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0] in ("Archetype", ""):
            continue
        rows.add(cells[0])
    for name in sorted(leaves - rows):
        errors.append(f"engineering QA inspection misses plan archetype: {name}")
    for name in sorted(rows - leaves):
        errors.append(f"engineering QA inspection row has no plan leaf: {name}")


# ── Writing plan-QA alignment ───────────────────────────────────────────
#
# Every plan/writing type leaf must declare its QA contract via a
# "QA `<contract>`" mapping line, the named contract file must exist,
# and every writing QA contract must be claimed by at least one leaf —
# a new text type can never ship with an ungated contract mapping.

WRITING_PLAN_DIR = ASSISTANT_PIPELINE / "references" / "plan" / "writing"
WRITING_QA_DIR = (
    ASSISTANT_PIPELINE / "references" / "quality-assurance" / "writing"
)


def validate_writing_alignment(errors: list[str]) -> None:
    if not (WRITING_PLAN_DIR.is_dir() and WRITING_QA_DIR.is_dir()):
        return  # missing roots are reported by the tree validators

    contracts = {
        path.stem for path in WRITING_QA_DIR.glob("*.md")
    } - {"index"}
    claimed: set[str] = set()
    for leaf in sorted(WRITING_PLAN_DIR.glob("*.md")):
        if leaf.name == "index.md":
            continue
        match = re.search(r"QA `([a-z-]+)`", leaf.read_text(encoding="utf-8"))
        if not match:
            errors.append(f"writing plan leaf missing QA mapping line: {leaf.name}")
            continue
        contract = match.group(1)
        if contract not in contracts:
            errors.append(
                f"writing plan leaf {leaf.name} names missing QA contract: {contract}"
            )
        claimed.add(contract)
    for name in sorted(contracts - claimed):
        errors.append(f"writing QA contract claimed by no plan leaf: {name}")


# ── Search plan-QA alignment ────────────────────────────────────────────
#
# Every search plan leaf must name the QA contract that gates its unit
# (the literal `QA `contract`` mapping line), and every search QA
# contract must be claimed by at least one leaf — a new retrieval unit
# can never ship with an ungated contract mapping.

SEARCH_PLAN_DIR = ASSISTANT_PIPELINE / "references" / "plan" / "search"
SEARCH_QA_DIR = (
    ASSISTANT_PIPELINE / "references" / "quality-assurance" / "search"
)


def validate_search_alignment(errors: list[str]) -> None:
    if not (SEARCH_PLAN_DIR.is_dir() and SEARCH_QA_DIR.is_dir()):
        return  # missing roots are reported by the tree validators

    contracts = {
        path.stem for path in SEARCH_QA_DIR.glob("*.md")
    } - {"index"}
    claimed: set[str] = set()
    for leaf in sorted(SEARCH_PLAN_DIR.glob("*.md")):
        if leaf.name == "index.md":
            continue
        match = re.search(r"QA `([a-z-]+)`", leaf.read_text(encoding="utf-8"))
        if not match:
            errors.append(f"search plan leaf missing QA mapping line: {leaf.name}")
            continue
        contract = match.group(1)
        if contract not in contracts:
            errors.append(
                f"search plan leaf {leaf.name} names missing QA contract: {contract}"
            )
        claimed.add(contract)
    for name in sorted(contracts - claimed):
        errors.append(f"search QA contract claimed by no plan leaf: {name}")


# ── Research plan-QA alignment ──────────────────────────────────────────
#
# Every research plan leaf must name the QA contract that gates its unit
# (the literal `QA `contract`` mapping line), and every research QA
# contract must be claimed by at least one leaf — a new depth unit can
# never ship with an ungated contract mapping.

RESEARCH_PLAN_DIR = ASSISTANT_PIPELINE / "references" / "plan" / "research"
RESEARCH_QA_DIR = (
    ASSISTANT_PIPELINE / "references" / "quality-assurance" / "research"
)


def validate_research_alignment(errors: list[str]) -> None:
    if not (RESEARCH_PLAN_DIR.is_dir() and RESEARCH_QA_DIR.is_dir()):
        return  # missing roots are reported by the tree validators

    contracts = {
        path.stem for path in RESEARCH_QA_DIR.glob("*.md")
    } - {"index"}
    claimed: set[str] = set()
    for leaf in sorted(RESEARCH_PLAN_DIR.glob("*.md")):
        if leaf.name == "index.md":
            continue
        match = re.search(r"QA `([a-z-]+)`", leaf.read_text(encoding="utf-8"))
        if not match:
            errors.append(f"research plan leaf missing QA mapping line: {leaf.name}")
            continue
        contract = match.group(1)
        if contract not in contracts:
            errors.append(
                f"research plan leaf {leaf.name} names missing QA contract: {contract}"
            )
        claimed.add(contract)
    for name in sorted(contracts - claimed):
        errors.append(f"research QA contract claimed by no plan leaf: {name}")


def validate_assistant(
    errors: list[str],
) -> tuple[int, dict[str, str], int, int, int]:
    profile_root = HERMES_ROOT / "profiles" / "assistant"
    skills = profile_root / "skills"
    desks_dir = skills / "desks"
    technic_dir = skills / "technic"
    learned_dir = skills / "learned"

    refs, catalog = validate_assistant_pipeline(errors)
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

    allowed: set[tuple[str, ...]] = {("assistant-pipeline", "SKILL.md")}
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

    validate_git_boundary(
        [ASSISTANT_PIPELINE, desks_dir, technic_dir], learned_dir, errors
    )
    if config.is_file():
        validate_plugin_enabled("assistant", config, errors)
        validate_assistant_messaging_config(config, errors)
    example_config = profile_root / "config.example.yaml"
    validate_plugin_enabled("assistant", example_config, errors)
    validate_assistant_messaging_config(example_config, errors)
    return (
        refs,
        catalog,
        len(groups["desks"]),
        len(groups["technic"]),
        len(groups["learned"]),
    )


def validate_shared(errors: list[str]) -> tuple[int, int]:
    skills = HERMES_ROOT / "skills"
    default_pipeline = skills / "default-pipeline"
    learned_dir = skills / "learned"

    managed: dict[str, Path] = {}
    default_skill = default_pipeline / "SKILL.md"
    if default_skill.is_file():
        validate_skill(
            default_skill,
            "default-pipeline",
            errors,
            expected_category="orchestration",
        )
        managed["default-pipeline"] = default_skill
    else:
        errors.append(f"missing default pipeline skill: {default_skill}")

    learned: dict[str, Path] = {}
    if learned_dir.is_dir():
        for path in sorted(learned_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors)
            learned[name] = path

    allowed = {("default-pipeline", "SKILL.md")}
    allowed.update(("learned", name, "SKILL.md") for name in learned)
    validate_allowed_skill_roots(skills, allowed, errors)
    validate_git_boundary([default_pipeline], learned_dir, errors)
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
        validate_plugin_source(errors)
        managed, learned = validate_shared(errors)
        summaries.append(f"shared={managed} managed/{learned} learned")
        refs, catalog, desks, technics, learned = validate_assistant(errors)
        summaries.append(
            f"assistant-pipeline={refs} refs/{len(catalog)} card-units; "
            f"assistant={desks} desks/{technics} technics/{learned} learned"
        )
        for profile in WORKER_PROFILES:
            technics, learned = validate_worker(profile, errors, catalog=catalog)
            summaries.append(f"{profile}={technics} technics/{learned} learned")
        validate_creative_alignment(errors)
        validate_engineering_alignment(errors)
        validate_writing_alignment(errors)
        validate_search_alignment(errors)
        validate_research_alignment(errors)
        for path in tracked_learned_files():
            errors.append(f"learned skill file must not be tracked: {path}")
        for path in untracked_managed_files():
            message = f"managed skill file is untracked: {path}"
            (errors if args.strict_git else warnings).append(message)
    elif args.profile == "assistant":
        refs, catalog, desks, technics, learned = validate_assistant(errors)
        summaries.append(
            f"assistant-pipeline={refs} refs/{len(catalog)} card-units; "
            f"assistant={desks} desks/{technics} technics/{learned} learned"
        )
    else:
        technics, learned = validate_worker(
            args.profile, errors, args.dispatch, catalog=collect_card_catalog()
        )
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
