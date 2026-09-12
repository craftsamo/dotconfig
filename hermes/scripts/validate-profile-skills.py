#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Validate Hermes skill topology, metadata, routing, and Git ownership.

The assistant profile owns a kernel and 19 flat, selectable entry skills
under profiles/assistant/skills/assistant-pipeline/. Each entry owns its
references; only common phase references remain beside the kernel.
The closed kanban card catalog belongs to the creative and search Execute
entries. The `default-pipeline` skill in the shared
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
    "ui-review",
    "ux-persona",
)
REVIEW_PROFILES = {"ui-review", "ux-persona"}
# Creator's hands (PROFILES.md "Creator hands (v3)"): receive-only A2A
# producers whose skills are `<hands>-pipeline/<verb>/<subject>/SKILL.md`
# leaves, one deliverable and one form each. Add a profile here when its
# skeleton lands; subjects must stay unique across every listed hands.
HANDS_PROFILES = ("image-creator", "video-creator", "audio-creator")
HANDS_VERBS = ("create", "generate", "edit", "source", "analyze")
HANDS_COSTS = ("free", "metered")
HANDS_FIELD_TYPES = ("text", "image", "file", "path", "int")
HANDS_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
WRITER_VERBS = ("write", "edit", "analyze")
ALL_PROFILES = ("assistant", *WORKER_PROFILES, *HANDS_PROFILES)
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
CAPABILITY_MODES = {"plan", "execute", "quality-assurance"}
ASSISTANT_ENTRY_PREFIXES = {
    "plan": "plan", "execute": "execute", "quality-assurance": "qa"
}
ASSISTANT_ENTRIES = {
    "chat-assistant": ("chat", None),
    **{
        f"{prefix}-assistant-{capability}": (mode, capability)
        for mode, prefix in ASSISTANT_ENTRY_PREFIXES.items()
        for capability in EXPECTED_CAPABILITIES
    },
}
ASSISTANT_CARD_UNITS = {
    "execute-assistant-creative": {
        "anchored-image-batch": "creator", "deterministic-render": "creator"
    },
    "execute-assistant-search": {
        "survey-enumeration": "searcher", "exhaustive-hunt": "searcher"
    },
}
# The sanctioned (mode, capability, subdir) shelf below entry references:
# creative's legacy/, the flat home of retained production references with
# fixed house prescriptions removed. Plan, execute and quality-assurance
# each have one shelf; it never nests and never carries card_units.
CREATIVE_LEGACY_SHELVES = {
    ("plan", "creative", "legacy"),
    ("execute", "creative", "legacy"),
    ("quality-assurance", "creative", "legacy"),
}
# Required Chat entry references and extra shared Execute files.
REQUIRED_MODE_FILES = {
    "chat": {"workspace-ops.md", "cron.md", "lookups.md"},
    "execute": {"resident-sessions.md", "kanban-lite.md", "scheduled.md"},
}
# Verification contracts that must exist (migration-loss guard); extra
# leaves may grow beside them as long as the dir index routes them.
REQUIRED_QA_CONTRACTS = {
    # Creative's floor is qa-assistant-creative/references/legacy/.
    "creative": {
        "ascii-art.md",
        "ascii-video.md",
        "assembly.md",
        "browser-media.md",
        "comic.md",
        "data-visualization.md",
        "excalidraw-diagram.md",
        "infographic.md",
        "pixel-art.md",
        "pixel-video.md",
        "raster-image.md",
        "sourced-asset.md",
        "svg-diagram.md",
        "text-visual.md",
        "video.md",
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
# Capabilities whose required QA contract floor lives under legacy/
# rather than directly in qa-assistant-<capability>/references/.
QA_CONTRACT_LEGACY_CAPABILITIES = {"creative"}


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


def assistant_entry_dir(
    mode: str, capability: str | None = None, pipeline: Path | None = None
) -> Path:
    """Resolve an entry against the current root, never an import-time path."""
    name = (
        "chat-assistant" if mode == "chat" and capability is None
        else f"{ASSISTANT_ENTRY_PREFIXES.get(mode)}-assistant-{capability}"
    )
    if name not in ASSISTANT_ENTRIES:
        raise ValueError(f"unknown assistant entry: {mode}/{capability}")
    return (ASSISTANT_PIPELINE if pipeline is None else pipeline) / name


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


def validate_creative_legacy_shelf(shelf: Path, mode: str, errors: list[str]) -> int:
    """Retained legacy references stay flat and cannot register new cards."""
    validate_index_routes(shelf, errors)
    files = 0
    for entry in sorted(shelf.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            errors.append(
                f"no nesting below the creative legacy shelf: {rel_pipeline(entry)}"
            )
            continue
        if entry.name == "SKILL.md":
            errors.append(
                f"creative legacy shelf must not contain SKILL.md: "
                f"{rel_pipeline(entry)}"
            )
            continue
        if entry.suffix != ".md":
            errors.append(f"non-markdown reference: {rel_pipeline(entry)}")
            continue
        files += 1
        if "card_units" in frontmatter(entry):
            errors.append(
                f"card_units are not permitted in the creative legacy shelf ({mode}): "
                f"{rel_pipeline(entry)}"
            )
    return files


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
    """Best-effort card catalog from the two authorized Execute entries.

    Used when validating a single worker profile without the full assistant
    pass; schema errors are ignored here (the --all pass reports them).
    """
    catalog: dict[str, str] = {}
    for name in sorted(ASSISTANT_CARD_UNITS):
        path = ASSISTANT_PIPELINE / name / "SKILL.md"
        if not path.is_file():
            continue
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
    """Validate the kernel, exhaustive entry set and owned reference trees.

    Returns (markdown reference file count, card catalog name -> assignee).
    """
    catalog: dict[str, str] = {}
    # Only the outer private-overlay link is permitted. Hermes follows nested
    # links but pathlib's recursive validation does not, so reject them first.
    links = [path for path in ASSISTANT_PIPELINE.rglob("*") if path.is_symlink()]
    if links:
        for path in sorted(links):
            errors.append(f"assistant pipeline must not contain symlinks: {rel_pipeline(path)}")
        return 0, catalog
    skill = ASSISTANT_PIPELINE / "SKILL.md"
    if not skill.is_file():
        errors.append(f"missing assistant pipeline skill: {skill}")
        return 0, catalog
    validate_skill(skill, "assistant-pipeline", errors, expected_category="orchestration")

    allowed = {("SKILL.md",)} | {(name, "SKILL.md") for name in ASSISTANT_ENTRIES}
    for child in sorted(ASSISTANT_PIPELINE.iterdir()):
        if child.name.startswith("."):
            continue
        if child.name == "tests" and child.is_dir():
            continue
        if child.name not in {"SKILL.md", "references", *ASSISTANT_ENTRIES}:
            errors.append(f"unexpected assistant pipeline child: {child.name}")

    references = ASSISTANT_PIPELINE / "references"
    shared_files = {
        f"{mode}/{name}"
        for mode in CAPABILITY_MODES
        for name in {"index.md", *REQUIRED_MODE_FILES.get(mode, set())}
    }
    for rel in sorted(shared_files):
        if not (references / rel).is_file():
            errors.append(f"missing shared mode file: references/{rel}")
    if references.is_dir():
        for path in sorted(references.rglob("*")):
            rel = path.relative_to(references).as_posix()
            if any(part.startswith(".") for part in Path(rel).parts):
                continue
            if (path.is_dir() and rel in CAPABILITY_MODES) or rel in shared_files:
                continue
            errors.append(f"unexpected shared reference: references/{rel}")
    for mode in sorted(CAPABILITY_MODES):
        index = references / mode / "index.md"
        if not index.is_file():
            continue
        validate_index_routes(index.parent, errors)
        text = index.read_text(encoding="utf-8")
        for name, (entry_mode, _) in ASSISTANT_ENTRIES.items():
            if entry_mode == mode and not re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text):
                errors.append(f"shared {mode} index does not route {name}")
        if any(
            re.search(r"(?:chat-assistant|(?:plan|execute|qa)-assistant-[a-z]+)", call)
            for call in re.findall(r"skill_view\s*\([^)]*\)", text, re.S)
        ):
            errors.append(f"shared {mode} index must not recursively load an entry")

    units: dict[str, Path] = {}
    for name, (mode, capability) in sorted(ASSISTANT_ENTRIES.items()):
        entry = ASSISTANT_PIPELINE / name
        entry_skill = entry / "SKILL.md"
        if not entry_skill.is_file():
            errors.append(f"missing assistant entry skill: {name}/SKILL.md")
            continue
        validate_skill(entry_skill, name, errors, expected_category="assistant-pipeline")
        data = frontmatter(entry_skill)
        version = data.get("version")
        if not isinstance(version, str) or not version.strip():
            errors.append(f"assistant entry version must be a nonempty string: {name}")
        description = data.get("description", "")
        phase = "quality assurance" if mode == "quality-assurance" else mode
        prefix = phase if capability is None else f"{phase} {capability}"
        prefix_pattern = re.escape(prefix).replace(r"\ ", r"[\s:-]+")
        if mode == "quality-assurance":
            prefix_pattern = rf"(?:quality[\s-]+assurance|qa)[\s:-]+{capability}"
        if not isinstance(description, str) or not re.match(
            rf"^{prefix_pattern}\b", description, re.I
        ):
            errors.append(f"assistant entry description must frontload {prefix}: {name}")
        text = entry_skill.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
        dependencies = ['skill_view(name="assistant-pipeline")']
        paths = ["SKILL.md"]
        if mode != "chat":
            paths.append(f"references/{mode}/index.md")
            dependencies.append(
                f'skill_view(name="assistant-pipeline", file_path="{paths[-1]}")'
            )
        for call in dependencies:
            if call not in text:
                errors.append(f"assistant entry missing dependency {call}: {name}")
        read_before = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", text, re.S)
        block = " ".join(read_before.group(1).split()) if read_before else ""
        for label, pattern in (
            ("full body reuse", r"full[- ]bod(?:y|ies)"),
            ("reuse instruction", r"\bre-?use\b"),
            ("not a past summary", r"(?:not|never|no)\b[^.!?]*\bsummar(?:y|ies)"),
            ("unchanged response", r"unchanged"),
            ("missing earlier body", r"(?:earlier|previous|context)"),
            ("missing body condition", r"(?:missing|unavailable|not\s+(?:available|present))"),
            ("read_file fallback", r"read_file"),
            ("stop if unavailable", r"\bstop\b"),
        ):
            if not re.search(pattern, block, re.I):
                errors.append(f"assistant entry ReadBeforeWork missing {label}: {name}")
        for path in paths:
            canonical = f"${{HERMES_SKILL_DIR}}/../{path}"
            if canonical not in block:
                errors.append(f"assistant entry missing canonical fallback {canonical}: {name}")
        for child in sorted(entry.iterdir()):
            if child.name.startswith("."):
                continue
            if child.name not in {"SKILL.md", "references"}:
                errors.append(f"unexpected assistant entry child: {rel_pipeline(child)}")
        own_refs = entry / "references"
        if capability == "creative" and not (own_refs / "legacy" / "index.md").is_file():
            errors.append(f"missing creative legacy index: {name}/references/legacy/index.md")
        if mode == "chat":
            for filename in sorted(REQUIRED_MODE_FILES["chat"]):
                if not (own_refs / filename).is_file():
                    errors.append(f"missing chat reference: {name}/references/{filename}")
        if own_refs.is_dir():
            for leaf in sorted(own_refs.iterdir()):
                if leaf.name.startswith("."):
                    continue
                if mode == "chat" and leaf.name not in REQUIRED_MODE_FILES["chat"]:
                    errors.append(f"unexpected chat reference: {rel_pipeline(leaf)}")
                route = f"references/{leaf.name}" + ("/index.md" if leaf.is_dir() else "")
                if route not in text:
                    errors.append(f"entry SKILL.md does not route {route}: {name}")
                if leaf.is_dir():
                    if (mode, capability, leaf.name) in CREATIVE_LEGACY_SHELVES:
                        validate_creative_legacy_shelf(leaf, mode, errors)
                    else:
                        errors.append(f"no nesting below entry references: {rel_pipeline(leaf)}")
                elif leaf.suffix != ".md":
                    errors.append(f"non-markdown reference: {rel_pipeline(leaf)}")
                elif leaf.name == "index.md":
                    errors.append(f"entry index must be promoted to SKILL.md: {name}")
        if name in ASSISTANT_CARD_UNITS:
            entry_catalog: dict[str, str] = {}
            validate_card_units(entry_skill, units, errors, entry_catalog)
            if entry_catalog != ASSISTANT_CARD_UNITS[name]:
                errors.append(f"assistant entry card catalog must be {ASSISTANT_CARD_UNITS[name]}: {name}")
            catalog.update(entry_catalog)

    # Scan every document, including unexpected/nested directories, so an
    # invalid shelf cannot hide a declaration or an escaping Markdown link.
    files = 0
    card_paths = {ASSISTANT_PIPELINE / name / "SKILL.md" for name in ASSISTANT_CARD_UNITS}
    for doc in sorted(ASSISTANT_PIPELINE.rglob("*.md")):
        files += doc.name != "SKILL.md"
        if doc.name == "SKILL.md" and doc.relative_to(ASSISTANT_PIPELINE).parts not in allowed:
            errors.append(f"unexpected skill root: {rel_pipeline(doc)}")
        if doc not in card_paths and "card_units" in frontmatter(doc):
            errors.append(f"card_units are only legal on creative/search Execute SKILL.md: {rel_pipeline(doc)}")
        for link, target in markdown_links(doc):
            if not target.is_relative_to(ASSISTANT_PIPELINE.resolve()):
                errors.append(f"assistant reference link escapes the pipeline: {link} in {rel_pipeline(doc)}")
            elif not target.is_file():
                errors.append(f"assistant reference link is broken: {link} in {rel_pipeline(doc)}")

    for capability, required in REQUIRED_QA_CONTRACTS.items():
        directory = assistant_entry_dir("quality-assurance", capability) / "references"
        if capability in QA_CONTRACT_LEGACY_CAPABILITIES:
            directory = directory / "legacy"
        present = (
            {p.name for p in directory.glob("*.md")} if directory.is_dir() else set()
        )
        for name in sorted(required - present):
            errors.append(
                f"QA contract file missing: {rel_pipeline(directory / name)}"
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


def learned_skill_files(learned_dir: Path) -> list[Path]:
    """``learned/<name>/SKILL.md`` and ``learned/<category>/<name>/SKILL.md`` —
    ``skill_manage`` nests an optional ``category`` under ``skills.create_dir``."""
    if not learned_dir.is_dir():
        return []
    return sorted(
        path for path in learned_dir.glob("*/SKILL.md")
    ) + sorted(
        path for path in learned_dir.glob("*/*/SKILL.md")
    )


def validate_learned_skills(
    learned_dir: Path, errors: list[str]
) -> tuple[dict[str, Path], set[tuple[str, ...]]]:
    """Validate every learned skill; return ``{name: path}`` and the allowed
    root tuples (relative to the skills dir) for :func:`validate_allowed_skill_roots`."""
    learned: dict[str, Path] = {}
    allowed: set[tuple[str, ...]] = set()
    for path in learned_skill_files(learned_dir):
        name = path.parent.name
        validate_skill(path, name, errors)
        learned[name] = path
        allowed.add(("learned", *path.relative_to(learned_dir).parts))
    return learned, allowed


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


LEARNED_CREATE_DIR = "skills/learned"


def validate_plugin_enabled(profile: str, config: Path, errors: list[str]) -> None:
    if not config.is_file():
        errors.append(f"profile config not found: {config}")
        return
    data = load_yaml(config)
    enabled = data.get("plugins", {}).get("enabled", [])
    if not isinstance(enabled, list) or "skill-topology" not in enabled:
        errors.append(f"skill-topology plugin is not enabled: {config}")
    # Placement of runtime-authored skills is skills.create_dir, not the
    # plugin: skill_manage consults it on every create shape (flat and
    # operations[]), where a tool_request rewrite only saw the flat one.
    skills_cfg = data.get("skills")
    create_dir = skills_cfg.get("create_dir") if isinstance(skills_cfg, dict) else None
    if create_dir != LEARNED_CREATE_DIR:
        errors.append(
            f"skills.create_dir must be {LEARNED_CREATE_DIR!r}, got {create_dir!r}: {config}"
        )
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

    if not technic_dir.is_dir() and profile not in REVIEW_PROFILES:
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

    learned, learned_roots = validate_learned_skills(learned_dir, errors)

    allowed = {(pipeline_name, "SKILL.md")}
    allowed.update(("technic", name, "SKILL.md") for name in leaves)
    writing: dict[str, Path] = {}
    if profile == "writer":
        writing = validate_writer_leaves(pipeline_dir, errors)
        for name in writing.keys() & (leaves.keys() | learned.keys()):
            errors.append(f"duplicate writer skill name: {name}")
        allowed.update(path.relative_to(skills).parts for path in writing.values())
    entries: dict[str, Path] = {}
    if profile == "engineer":
        entries = validate_engineer_references(pipeline_dir, errors)
        for name in entries.keys() & (leaves.keys() | learned.keys()):
            errors.append(f"duplicate engineer skill name: {name}")
        allowed.update(path.relative_to(skills).parts for path in entries.values())
    allowed.update(learned_roots)
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
    if profile == "creator":
        validate_creator_references(pipeline_dir, errors)
    if profile == "marketer":
        validate_marketer_references(pipeline_dir, errors)
    validate_git_boundary([pipeline_dir, technic_dir], learned_dir, errors)
    validate_plugin_enabled(profile, profile_root / "config.yaml", errors)
    return len(leaves) + len(writing) + len(entries), len(learned)


ENGINEER_ENTRIES = {
    "plan-engineer": {"web-ui.md", "hands-references.md"},
    "build-engineer": {"web-ui.md", "hands-references.md"},
    "qa-engineer": {"web-ui.md", "ux-persona.md", "personas.md", "hands-references.md"},
    "assess-engineer": {"hands-references.md"},
}
ENGINEER_SHARED_REFERENCES = {"opencode.md", "shared/design-catalog.md"}


def validate_engineer_references(pipeline_dir: Path, errors: list[str]) -> dict[str, Path]:
    """Four discoverable mode entries depend on one kernel and shared transport."""
    entries: dict[str, Path] = {}
    links = [path for path in pipeline_dir.rglob("*") if path.is_symlink()]
    if links:
        for path in sorted(links):
            errors.append(f"engineer pipeline must not contain symlinks: {path.relative_to(pipeline_dir)}")
        return entries
    expected = {f"references/{name}" for name in ENGINEER_SHARED_REFERENCES} | {
        f"{entry}/references/{name}"
        for entry, names in ENGINEER_ENTRIES.items() for name in names
    }
    found = {
        path.relative_to(pipeline_dir).as_posix()
        for path in pipeline_dir.rglob("*.md") if path.name != "SKILL.md"
    }
    for name in sorted(expected - found):
        errors.append(f"missing engineer reference: {name}")
    for name in sorted(found - expected):
        errors.append(f"unexpected engineer reference: {name}")
    allowed_skills = {"SKILL.md"} | {f"{name}/SKILL.md" for name in ENGINEER_ENTRIES}
    for path in pipeline_dir.rglob("SKILL.md"):
        if path.relative_to(pipeline_dir).as_posix() not in allowed_skills:
            errors.append(f"unexpected engineer entry skill: {path.relative_to(pipeline_dir)}")
    kernel = pipeline_dir / "SKILL.md"
    kernel_text = kernel.read_text(encoding="utf-8") if kernel.is_file() else ""
    for name, references in ENGINEER_ENTRIES.items():
        skill = pipeline_dir / name / "SKILL.md"
        if f"]({name}/SKILL.md)" not in kernel_text:
            errors.append(f"engineer kernel does not route {name}")
        if not skill.is_file():
            errors.append(f"missing engineer entry skill: {name}/SKILL.md")
            continue
        entries[name] = skill
        validate_skill(skill, name, errors, expected_category="engineer-pipeline")
        data = frontmatter(skill)
        if not isinstance(data.get("version"), str) or not data["version"].strip():
            errors.append(f"engineer entry version must be a nonempty string: {name}")
        description = data.get("description", "")
        mode = name.split("-", 1)[0]
        if not isinstance(description, str) or not re.match(rf"^{mode} engineering\b", description, re.I):
            errors.append(f"engineer entry description must frontload {mode} engineering: {name}")
        text = skill.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
        read_before = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", text, re.S)
        block = " ".join(read_before.group(1).split()) if read_before else ""
        for required in (
            'skill_view(name="engineer-pipeline")',
            'skill_view(name="engineer-pipeline", file_path="references/opencode.md")',
            "${HERMES_SKILL_DIR}/../SKILL.md",
            "${HERMES_SKILL_DIR}/../references/opencode.md",
            "read_file", "next_offset", "unchanged",
        ):
            if required not in block:
                errors.append(f"engineer entry ReadBeforeWork missing {required}: {name}")
        for label, pattern in (
            ("current full-body reuse", r"reuse full-body instructions.*current context"),
            ("no summary reuse", r"not a past load or summary"),
            ("stop on missing body", r"stop.*(?:unavailable|missing)"),
            ("no implicit approval", r"not implementation approval"),
            ("entry re-evaluation", r"re-evaluate.*within a turn"),
        ):
            if not re.search(pattern, block, re.I):
                errors.append(f"engineer entry ReadBeforeWork missing {label}: {name}")
        for leaf in sorted(references - {"personas.md"}):
            if f"](references/{leaf})" not in text:
                errors.append(f"engineer {name} entry does not route {leaf}")
    personas = pipeline_dir / "qa-engineer/references/ux-persona.md"
    if personas.is_file() and "](personas.md)" not in personas.read_text(encoding="utf-8"):
        errors.append("engineer ux-persona reference does not route personas.md")
    root = pipeline_dir.resolve()
    for path in pipeline_dir.rglob("*.md"):
        if "card_units" in frontmatter(path):
            errors.append(f"engineer defines no card units: {path.relative_to(pipeline_dir)}")
        for link, target in markdown_links(path):
            if not target.is_relative_to(root):
                errors.append(f"engineer reference escapes pipeline: {path.name}: {link}")
            elif not target.is_file():
                errors.append(f"broken engineer reference link: {path.name}: {link}")
    return entries


MARKETER_REFERENCE_FILES = {
    "plan/index.md", "plan/discovery.md", "plan/positioning.md", "plan/offer.md",
    "plan/channels.md", "plan/campaign.md", "build/index.md", "build/parts.md",
    "build/draft.md", "build/measurement.md", "quality-assurance/index.md",
    "quality-assurance/strategy.md", "quality-assurance/content.md",
    "quality-assurance/saved-draft.md", "analyze/index.md", "platforms/x.md",
    "platforms/substack.md", "platforms/note.md", "platforms/zenn.md", "state.md",
}


def validate_marketer_references(pipeline_dir: Path, errors: list[str]) -> None:
    """Marketer's four modes share platform procedures, not Creator hands."""
    pipeline = pipeline_dir / "SKILL.md"
    major = _pipeline_major_version(frontmatter(pipeline) if pipeline.is_file() else {})
    if major is None:
        errors.append("invalid marketer pipeline version")
        return
    references = pipeline_dir / "references"
    if major < 7 and not any((references / mode).is_dir() for mode in
                             ("plan", "build", "quality-assurance", "analyze")):
        return
    found = {p.relative_to(references).as_posix() for p in references.rglob("*.md")}
    for name in sorted(MARKETER_REFERENCE_FILES - found):
        errors.append(f"missing marketer reference: {name}")
    for name in sorted(found - MARKETER_REFERENCE_FILES):
        errors.append(f"unexpected marketer reference: {name}")
    root = pipeline_dir.resolve()
    linked = set()
    for doc in [pipeline, *sorted(references.rglob("*.md"))]:
        if not doc.is_file():
            continue
        for link, target in markdown_links(doc):
            if not target.is_relative_to(root):
                errors.append(f"marketer reference escapes pipeline: {link}")
            elif not target.is_file():
                errors.append(f"broken marketer reference: {link}")
            if doc == pipeline:
                linked.add(target)
    for name in sorted(MARKETER_REFERENCE_FILES):
        if (references / name).resolve() not in linked:
            errors.append(f"marketer root does not link reference: {name}")
    if not (pipeline_dir / "scripts/browser-lease.py").is_file():
        errors.append("missing marketer browser lease helper")
    acceptance = HERMES_ROOT / "profiles/writer/skills/writer-pipeline/references/acceptance"
    for name in ("index.md", "prose.md", "script.md"):
        if not (acceptance / name).is_file():
            errors.append(f"missing shared writing acceptance: {name}")


def validate_writer_leaves(pipeline_dir: Path, errors: list[str]) -> dict[str, Path]:
    """Writer adopts form-based leaves without changing Creator's verb set."""
    leaves: dict[str, Path] = {}
    for path in sorted(pipeline_dir.rglob("SKILL.md")):
        rel = path.relative_to(pipeline_dir)
        if rel.parts == ("SKILL.md",):
            continue
        if len(rel.parts) != 3 or rel.parts[0] not in WRITER_VERBS:
            errors.append(f"writer leaf must sit at write|edit|analyze/<subject>/SKILL.md: {path}")
            continue
        verb, subject, _ = rel.parts
        if not HANDS_NAME.fullmatch(subject):
            errors.append(f"writer subject must be a slug: {path}")
            continue
        name = f"{verb}-{subject}"
        validate_skill(path, name, errors, expected_category="writing")
        data = frontmatter(path)
        meta = hermes_meta(data)
        if not isinstance(data.get("description"), str) or not data["description"].strip():
            errors.append(f"writer leaf must carry a description: {path}")
        if not isinstance(meta.get("output"), str) or not meta["output"].strip():
            errors.append(f"writer leaf must describe metadata.hermes.output: {path}")
        text = path.read_text(encoding="utf-8")
        for section in ("Procedure", "QA", "Report"):
            if f"<{section}>" not in text or f"</{section}>" not in text:
                errors.append(f"writer leaf must own <{section}>: {path}")
        form = meta.get("form")
        if not isinstance(form, dict) or not form:
            errors.append(f"writer leaf must declare metadata.hermes.form: {path}")
            continue
        if "note" not in form:
            errors.append(f"writer form must carry a note field: {path}")
        for key, field in form.items():
            if not isinstance(key, str) or not HANDS_NAME.fullmatch(key.replace("_", "-")):
                errors.append(f"writer form field name must be a slug: {key}: {path}")
            if not isinstance(field, dict):
                errors.append(f"writer field must be a mapping: {key}: {path}")
                continue
            if not isinstance(field.get("required"), bool):
                errors.append(f"writer field must set required: true|false: {key}: {path}")
            if field.get("type", "text") not in ("text", "file", "path", "int"):
                errors.append(f"unknown writer field type: {key}: {path}")
            if not isinstance(field.get("label"), str) or not field["label"].strip():
                errors.append(f"writer field must carry a label: {key}: {path}")
            if "other" in field and not isinstance(field["other"], bool):
                errors.append(f"writer field other must be a boolean: {key}: {path}")
            options = field.get("options")
            if options is not None and (
                not isinstance(options, list) or not options
                or any(not isinstance(option, str) or not HANDS_NAME.fullmatch(option) for option in options)
            ):
                errors.append(f"writer options must be a non-empty list of string slugs: {key}: {path}")
                continue
            if "references" not in field:
                continue
            pattern = field["references"]
            if (
                not isinstance(pattern, str) or not pattern.startswith("references/")
                or Path(pattern).name != "*.md" or pattern.count("*") != 1
                or ".." in Path(pattern).parts or any(char in pattern for char in "?[]")
                or not options
            ):
                errors.append(f"writer references must name a local references/.../*.md option set: {key}: {path}")
                continue
            reference_root = path.parent / Path(pattern).parent
            for option in options:
                backing = reference_root / f"{option}.md"
                if not backing.resolve().is_relative_to(path.parent.resolve()) or not backing.is_file():
                    errors.append(f"writer option {option} has no local reference: {path}")
                elif f"]({backing.relative_to(path.parent).as_posix()})" not in text:
                    errors.append(f"writer option {option} needs a direct body link: {path}")
        leaves[name] = path
    return leaves


# ── Creator hands (v3) ──────────────────────────────────────────────────
#
# One leaf = one deliverable = one form. The front matter is the ONLY
# representation of the leaf's contract (no generated index, no preset
# layer), so it is what gets validated: the path names the leaf
# (`<verb>/<subject>` ⇒ `name: <verb>-<subject>`), the verb is one of the
# closed set, the cost class is declared, and the form is a dict of fields
# each carrying `required`. A `style` field's options must be backed by
# `references/styles/<option>.md`; every leaf carries a `note` escape
# hatch. Subjects are unique across all hands because Creator reads every
# hands' tree through one `skills.external_dirs` list.


def hermes_meta(data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    hermes = metadata.get("hermes")
    return hermes if isinstance(hermes, dict) else {}


def validate_hands_form(
    form: Any, leaf_dir: Path, path: Path, errors: list[str]
) -> None:
    if not isinstance(form, dict) or not form:
        errors.append(f"hands leaf must declare a non-empty metadata.hermes.form: {path}")
        return
    if "note" not in form:
        errors.append(f"hands form must carry a `note` field: {path}")
    for key, field in form.items():
        if not HANDS_NAME.match(str(key).replace("_", "-")):
            errors.append(f"hands form field name must be a slug: {key}: {path}")
        if not isinstance(field, dict):
            errors.append(f"hands form field {key} must be a mapping: {path}")
            continue
        if not isinstance(field.get("required"), bool):
            errors.append(f"hands form field {key} must set required: true|false: {path}")
        field_type = field.get("type", "text")
        if field_type not in HANDS_FIELD_TYPES:
            errors.append(
                f"hands form field {key} has unknown type {field_type!r}: {path}"
            )
        options = field.get("options")
        if options is not None:
            if not isinstance(options, list) or not options:
                errors.append(f"hands form field {key} options must be a non-empty list: {path}")
            else:
                reference_dir = {"style": "styles", "theme": "themes"}.get(key, str(key))
                reference_root = leaf_dir / "references" / reference_dir
                if key != "style" and "references" not in field and not reference_root.is_dir():
                    continue
                for option in options:
                    if not isinstance(option, str) or not HANDS_NAME.fullmatch(option):
                        errors.append(f"{key} reference option must be a slug: {option}: {path}")
                        continue
                    backing = reference_root / f"{option}.md"
                    if not backing.is_file():
                        errors.append(
                            f"{key} option {option} has no references/{reference_dir}/{option}.md: {path}"
                        )


def validate_hands_leaves(
    pipeline_dir: Path, profile: str, errors: list[str]
) -> dict[str, Path]:
    """Validate every `<verb>/<subject>/SKILL.md` under a hands pipeline root
    and return name -> path. Support dirs (references/assets/scripts) of
    the root itself are not leaf roots."""
    leaves: dict[str, Path] = {}
    for path in sorted(pipeline_dir.rglob("SKILL.md")):
        rel = path.relative_to(pipeline_dir)
        if rel.parts == ("SKILL.md",):
            continue
        if len(rel.parts) != 3:
            errors.append(
                f"hands leaf must sit at <verb>/<subject>/SKILL.md: {path}"
            )
            continue
        verb, subject, _ = rel.parts
        if verb not in HANDS_VERBS:
            errors.append(f"hands verb must be one of {'|'.join(HANDS_VERBS)}: {path}")
            continue
        if not HANDS_NAME.match(subject):
            errors.append(f"hands subject must be a slug: {path}")
            continue
        name = f"{verb}-{subject}"
        validate_skill(path, name, errors, expected_category="hands")
        data = frontmatter(path)
        meta = hermes_meta(data)
        if not str(data.get("description", "")).strip():
            errors.append(f"hands leaf must carry a description: {path}")
        if meta.get("hands") != profile:
            errors.append(f"metadata.hermes.hands must be {profile}: {path}")
        if meta.get("cost") not in HANDS_COSTS:
            errors.append(f"metadata.hermes.cost must be one of {'|'.join(HANDS_COSTS)}: {path}")
        if not str(meta.get("output", "")).strip():
            errors.append(f"metadata.hermes.output must describe the deliverable: {path}")
        validate_hands_form(meta.get("form"), path.parent, path, errors)
        leaves[name] = path
    return leaves


def validate_hands_subjects(
    leaves_by_profile: dict[str, dict[str, Path]], errors: list[str]
) -> None:
    owners: dict[str, str] = {}
    for profile, leaves in leaves_by_profile.items():
        for name in leaves:
            subject = name.split("-", 1)[1]
            owner = owners.setdefault(subject, profile)
            if owner != profile:
                errors.append(
                    f"hands subject {subject} is owned by both {owner} and {profile}"
                )


# Second table cell only: `| Deliverable | <profile>: <name> | Notes |`. An
# engine-variant suffix after the name (e.g. `generate-sfx (fal:...)`) is
# discarded by \b; several rows serving the same (profile, name) pair are
# expected and allowed (engine variants), not a duplicate-route error.
HANDS_ROUTING_ROW = re.compile(
    r"^\|[^|\n]+\|\s*(image-creator|video-creator|audio-creator):\s*([a-z]+-[a-z-]+)\b",
    re.MULTILINE,
)


def validate_hands_routing(
    hands_leaves: dict[str, dict[str, Path]], errors: list[str]
) -> None:
    """Cross-check the creator capabilities.md routing table against the
    hands leaves actually installed on disk (leaves_by_profile from
    validate_hands, same shape validate_hands_subjects already takes).
    Path is derived from the current HERMES_ROOT global at call time (never
    cached at import time) so tests can patch it."""
    table = (
        HERMES_ROOT
        / "profiles/creator/skills/creator-pipeline/references/capabilities.md"
    )
    if not table.is_file():
        errors.append(f"missing creator capabilities routing table: {table}")
        return
    text = table.read_text(encoding="utf-8")
    installed = {
        name: profile for profile, leaves in hands_leaves.items() for name in leaves
    }
    documented: set[tuple[str, str]] = set()
    for profile, name in HANDS_ROUTING_ROW.findall(text):
        owner = installed.get(name)
        if owner is None:
            errors.append(
                f"capabilities.md routes to a hands leaf that is not installed: {profile}: {name}"
            )
            continue
        if owner != profile:
            errors.append(
                f"capabilities.md assigns {name} to {profile} but it is installed under {owner}"
            )
            continue
        documented.add((profile, name))
    for profile, leaves in hands_leaves.items():
        for name in leaves:
            if (profile, name) not in documented:
                errors.append(
                    f"installed hands leaf has no capabilities.md route: {profile}: {name}"
                )


def validate_hands(profile: str, errors: list[str]) -> tuple[dict[str, Path], int]:
    profile_root = HERMES_ROOT / "profiles" / profile
    skills = profile_root / "skills"
    pipeline_name = f"{profile}-pipeline"
    pipeline_dir = skills / pipeline_name
    pipeline = pipeline_dir / "SKILL.md"
    learned_dir = skills / "learned"

    if not pipeline.is_file():
        errors.append(f"missing root pipeline: {pipeline}")
        return {}, 0
    validate_skill(pipeline, pipeline_name, errors, expected_category="hands")
    if (skills / "technic").exists():
        errors.append(f"hands profile must not carry a technic directory: {skills / 'technic'}")

    leaves = validate_hands_leaves(pipeline_dir, profile, errors)

    learned: dict[str, Path] = {}
    if learned_dir.is_dir():
        for path in sorted(learned_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors)
            learned[name] = path

    allowed = {(pipeline_name, "SKILL.md")}
    allowed.update(
        (pipeline_name, *path.relative_to(pipeline_dir).parts) for path in leaves.values()
    )
    allowed.update(("learned", name, "SKILL.md") for name in learned)
    validate_allowed_skill_roots(skills, allowed, errors)
    validate_git_boundary([pipeline_dir], learned_dir, errors)
    validate_plugin_enabled(profile, profile_root / "config.yaml", errors)
    return leaves, len(learned)


# ── Creator references (v8 broker tree) ─────────────────────────────────
#
# Migrating off the v7 monolith reference files onto a plain Markdown
# broker tree: `references/{plan,build,quality-assurance}/index.md` plus
# one flat `<hands>/<subject>.md` leaf per hands subject (subjects read
# dynamically from the hands leaves on disk, never hardcoded).

CREATOR_REFERENCE_PHASES = ("plan", "build", "quality-assurance")
# Ordinary `[text](dest)`, an optional "title"/'title', or a `<dest>` target.
LOCAL_LINK = re.compile(
    r"\]\(\s*(<[^>]*>|[^\s)]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)


def _pipeline_major_version(data: dict[str, Any]) -> int | None:
    """Strict leading major version (`8`, `8.0.0`, ...); `None` when the
    `version` field is missing or not a clean numeric-dot string/number
    (e.g. `v8.0.0`) — never silently treated as pre-v8."""
    version = data.get("version")
    if isinstance(version, bool):
        return None
    if isinstance(version, int):
        return version
    if isinstance(version, float):
        return int(version)
    if isinstance(version, str):
        match = re.fullmatch(r"(\d+)(?:\.\d+)*", version.strip())
        if match:
            return int(match.group(1))
    return None


def collect_hands_subjects() -> dict[str, set[str]]:
    """Subjects (deduped across verbs) served by each hands profile, read
    from `<hands>-pipeline/<verb>/<subject>/SKILL.md` below HERMES_ROOT."""
    subjects: dict[str, set[str]] = {}
    for profile in HANDS_PROFILES:
        pipeline_dir = (
            HERMES_ROOT / "profiles" / profile / "skills" / f"{profile}-pipeline"
        )
        found: set[str] = set()
        if pipeline_dir.is_dir():
            for path in pipeline_dir.rglob("SKILL.md"):
                rel = path.relative_to(pipeline_dir)
                if rel.parts == ("SKILL.md",):
                    continue
                if len(rel.parts) != 3:
                    continue
                verb, subject, _ = rel.parts
                if verb not in HANDS_VERBS:
                    continue
                found.add(subject)
        subjects[profile] = found
    return subjects


def markdown_links(doc: Path) -> list[tuple[str, Path]]:
    """Local (non-web, non-anchor-only) Markdown links in doc, as
    (raw link text, resolved target path)."""
    text = doc.read_text(encoding="utf-8")
    links: list[tuple[str, Path]] = []
    for raw in LOCAL_LINK.findall(text):
        link = raw.strip()
        if link.startswith("<") and link.endswith(">"):
            link = link[1:-1]
        if not link or link.startswith("#"):
            continue
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", link):
            continue  # scheme (http:, https:, mailto:, ...)
        target = link.split("#", 1)[0]
        if not target:
            continue
        links.append((link, (doc.parent / target).resolve()))
    return links


def validate_creator_reference_links(
    doc: Path, pipeline_dir: Path, errors: list[str]
) -> None:
    root = pipeline_dir.resolve()
    rel_doc = doc.relative_to(pipeline_dir)
    for link, target in markdown_links(doc):
        try:
            target.relative_to(root)
        except ValueError:
            errors.append(
                f"creator reference link escapes the pipeline: {link} in {rel_doc}"
            )
            continue
        if not target.is_file():
            errors.append(f"creator reference link is broken: {link} in {rel_doc}")


def validate_creator_references(pipeline_dir: Path, errors: list[str]) -> None:
    """Validate the v8 broker tree. Build-alongside: while no phase
    directory exists yet and the root major version is below 8, the v7
    monolith files stay accepted. Any phase directory, or major >= 8,
    switches on full-tree validation for all three phases at once.
    """
    pipeline = pipeline_dir / "SKILL.md"
    major = _pipeline_major_version(frontmatter(pipeline) if pipeline.is_file() else {})
    if major is None:
        errors.append("invalid creator pipeline version")
        return
    references = pipeline_dir / "references"
    phase_dirs = {phase: references / phase for phase in CREATOR_REFERENCE_PHASES}

    if not any(d.is_dir() for d in phase_dirs.values()) and major < 8:
        return  # v7 baseline: still on the monolith references/{phase}.md files

    hands_subjects = collect_hands_subjects()
    phase_subject_paths: dict[str, dict[str, Path]] = {
        phase: {} for phase in CREATOR_REFERENCE_PHASES
    }

    for phase, phase_dir in phase_dirs.items():
        if not phase_dir.is_dir():
            errors.append(f"missing creator reference phase: {phase}")
            for hands, subjects in hands_subjects.items():
                for subject in sorted(subjects):
                    errors.append(
                        f"creator reference phase {phase} missing hands subject: "
                        f"{hands}/{subject}"
                    )
            continue

        if not (phase_dir / "index.md").is_file():
            errors.append(f"missing creator reference phase index.md: {phase}")

        for entry in sorted(phase_dir.iterdir()):
            if entry.name.startswith(".") or entry.name == "index.md":
                continue
            if entry.is_file():
                errors.append(
                    f"unexpected file in creator reference phase {phase}: {entry.name}"
                )
                continue
            if entry.name not in HANDS_PROFILES:
                errors.append(
                    f"unknown hands directory in creator reference phase "
                    f"{phase}: {entry.name}"
                )
                continue
            hands = entry.name
            expected = hands_subjects.get(hands, set())
            found: set[str] = set()
            for leaf in sorted(entry.iterdir()):
                if leaf.name.startswith("."):
                    continue
                if leaf.is_dir():
                    errors.append(
                        f"no nesting below a creator reference hands dir: "
                        f"{phase}/{hands}/{leaf.name}"
                    )
                    continue
                if leaf.name == "SKILL.md":
                    errors.append(
                        f"creator reference tree must not contain SKILL.md: "
                        f"{phase}/{hands}/{leaf.name}"
                    )
                    continue
                if leaf.suffix != ".md":
                    errors.append(
                        f"non-markdown file in creator reference tree: "
                        f"{phase}/{hands}/{leaf.name}"
                    )
                    continue
                if not leaf.read_text(encoding="utf-8").strip():
                    errors.append(
                        f"empty creator reference file: {phase}/{hands}/{leaf.name}"
                    )
                subject = leaf.stem
                found.add(subject)
                phase_subject_paths[phase][f"{hands}/{subject}"] = leaf

            for missing in sorted(expected - found):
                errors.append(
                    f"creator reference phase {phase} missing hands subject: "
                    f"{hands}/{missing}"
                )
            for orphan in sorted(found - expected):
                errors.append(
                    f"creator reference phase {phase} has orphan hands subject: "
                    f"{hands}/{orphan}"
                )

        for hands, subjects in hands_subjects.items():
            if (phase_dir / hands).is_dir() or not subjects:
                continue
            for subject in sorted(subjects):
                errors.append(
                    f"creator reference phase {phase} missing hands subject: "
                    f"{hands}/{subject}"
                )

    for phase, phase_dir in phase_dirs.items():
        if not phase_dir.is_dir():
            continue
        index = phase_dir / "index.md"
        if index.is_file():
            linked = {target for _, target in markdown_links(index)}
            for key, path in phase_subject_paths[phase].items():
                if path.resolve() not in linked:
                    errors.append(
                        f"phase {phase} index.md does not link {key}: "
                        f"{path.relative_to(pipeline_dir)}"
                    )
        for doc in sorted(phase_dir.rglob("*.md")):
            validate_creator_reference_links(doc, pipeline_dir, errors)

    if major >= 8:
        for phase in CREATOR_REFERENCE_PHASES:
            monolith = references / f"{phase}.md"
            if monolith.is_file():
                errors.append(
                    f"stale monolith reference file on v8: "
                    f"{monolith.relative_to(pipeline_dir)}"
                )


# ── Creative three-layer alignment ────────────────────────────────────────────
#
# Plan decides, creator produces, QA verifies. The 1:1 parity contract is
# scoped to plan-assistant-creative/references/legacy/ and the matching QA shelf,
# the flat shelves that still carry the original creator-technic-aligned
# leaves: they must pair 1:1 with creator technics, and the legacy QA
# index's Covers column must map every canonical family to exactly one
# contract. The plain-language guides in plan-assistant-creative/references/
# (this migration's new client-facing surface) carry no such parity —
# a new guide's name need not equal a creator hand, and an absent guide
# does not mean the capability is unavailable. Families served by
# Creator's hands (speech, icon, ...) are not technics and carry no leaf
# or QA-index row in legacy. Paths below are derived from the current ASSISTANT_PIPELINE
# / HERMES_ROOT globals at call time (never cached at import time) so
# tests can patch them without stale module-level Path objects.

CREATIVE_LEGACY_NON_FAMILY_LEAVES = {
    "index.md",
    "asset-set.md",
    "composite-media.md",
}
# Headings every new plain-language creative guide must carry verbatim;
# reference-research.md is a cross-family reference, not a guide itself.
CREATIVE_GUIDE_HEADINGS = (
    "## Use",
    "## Client decisions",
    "## References",
    "## Acceptance",
)
CREATIVE_GUIDE_EXCLUDED_ROOTS = {"reference-research.md"}
# Retired creative shelves/leaves: an active reference must never point
# at them again.
CREATIVE_RETIRED_REFERENCE_SEGMENTS = (
    "house-formats",
    "expressions",
    "production-facts.md",
)
# A backtick-quoted local path reference: requires a directory component
# (so bare produced-artifact names like `proposal.md` are not treated as
# references) and an .md/.md-index target; SKILL.md and non-.md paths
# (scripts, form fields) are excluded explicitly.
CREATIVE_BACKTICK_REF = re.compile(r"`([^`\s]+)`")


def validate_creative_new_guides(plan_dir: Path, errors: list[str]) -> None:
    """Every plain-language guide directly under the Plan entry's references
    (not reference-research.md or anything under legacy/) must carry
    the four client-facing headings verbatim."""
    for path in sorted(plan_dir.glob("*.md")):
        if path.name in CREATIVE_GUIDE_EXCLUDED_ROOTS:
            continue
        text = path.read_text(encoding="utf-8")
        for heading in CREATIVE_GUIDE_HEADINGS:
            if not re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE):
                errors.append(
                    f"creative guide missing heading {heading!r}: "
                    f"{rel_pipeline(path)}"
                )


def creative_doc_references(doc: Path) -> list[tuple[str, Path]]:
    """Local Markdown-link and backtick-path references in a creative doc,
    as (raw link text, resolved target path). Backtick paths need a `/`
    and an .md (or .../index.md) suffix to count as a reference, so plain
    prose mentions of produced artifact names, SKILL.md, scripts and form
    fields are not treated as broken links."""
    refs = list(markdown_links(doc))
    text = doc.read_text(encoding="utf-8")
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", text)
    for raw in CREATIVE_BACKTICK_REF.findall(text):
        link = raw.strip().split("#", 1)[0]
        if any(char in link for char in "<>${}*"):
            continue  # illustrative template, not a concrete document path
        if "/" not in link or not link.endswith(".md"):
            continue
        if Path(link).name == "SKILL.md":
            continue
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", link):
            continue  # scheme (http:, https:, mailto:, ...)
        refs.append((link, (doc.parent / link).resolve()))
    return refs


def validate_creative_references(pipeline_dir: Path, errors: list[str]) -> None:
    """Local document references across the three creative entries, legacy shelves
    included), confined to the pipeline root and never pointing at a
    retired shelf."""
    root = pipeline_dir.resolve()
    for mode in ("plan", "execute", "quality-assurance"):
        tree = assistant_entry_dir(mode, "creative", pipeline_dir)
        if not tree.is_dir():
            continue
        for doc in sorted(tree.rglob("*.md")):
            rel_doc = doc.relative_to(pipeline_dir).as_posix()
            for link, target in creative_doc_references(doc):
                if any(seg in Path(link.split("#", 1)[0]).parts
                       for seg in CREATIVE_RETIRED_REFERENCE_SEGMENTS):
                    errors.append(
                        f"creative reference points at a retired shelf "
                        f"{link!r}: {rel_doc}"
                    )
                    continue
                try:
                    target.relative_to(root)
                except ValueError:
                    errors.append(
                        f"creative reference escapes the pipeline: "
                        f"{link} in {rel_doc}"
                    )
                    continue
                if not target.is_file():
                    errors.append(
                        f"creative reference is broken: {link} in {rel_doc}"
                    )


def validate_creative_alignment(errors: list[str]) -> None:
    plan_dir = assistant_entry_dir("plan", "creative") / "references"
    qa_dir = assistant_entry_dir("quality-assurance", "creative") / "references"
    technic_dir = HERMES_ROOT / "profiles" / "creator" / "skills" / "technic"
    legacy_dir = plan_dir / "legacy"
    if plan_dir.is_dir():
        validate_creative_new_guides(plan_dir, errors)
    validate_creative_references(ASSISTANT_PIPELINE, errors)
    if not (technic_dir.is_dir() and plan_dir.is_dir()):
        return  # missing roots are reported by the profile validators
    if not legacy_dir.is_dir():
        errors.append(f"missing creative plan legacy shelf: {legacy_dir}")
        return

    technics = {path.parent.name for path in technic_dir.glob("*/SKILL.md")}
    canonical = technics

    legacy_leaves = {
        path.name for path in legacy_dir.glob("*.md")
    } - CREATIVE_LEGACY_NON_FAMILY_LEAVES
    expected = {f"{name.removeprefix('creator-')}.md" for name in technics}
    for name in sorted(expected - legacy_leaves):
        errors.append(f"creative legacy leaf missing for canonical family: {name}")
    for name in sorted(legacy_leaves - expected):
        errors.append(f"creative legacy leaf has no canonical family: {name}")

    qa_legacy_dir = qa_dir / "legacy"
    qa_index = qa_dir.parent / "SKILL.md"
    if not qa_index.is_file():
        errors.append(f"missing creative QA index: {qa_index}")
        return
    qa_legacy_index = qa_legacy_dir / "index.md"
    if not qa_legacy_index.is_file():
        errors.append(f"missing creative QA legacy index: {qa_legacy_index}")
        return
    covered: list[str] = []
    for line in qa_legacy_index.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3 or cells[1] == "Contract":
            continue
        contract = cells[1].strip("`")
        if contract.endswith(".md") and not (qa_legacy_dir / contract).is_file():
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
# Every engineering Client guide has matching outcome acceptance expectations.
# Technical decomposition and UI evaluation now belong to Engineer, not this
# Assistant-side correspondence check.

def validate_engineering_alignment(errors: list[str]) -> None:
    plan_dir = assistant_entry_dir("plan", "engineering") / "references"
    qa_inspection = assistant_entry_dir("quality-assurance", "engineering") / "references" / "inspection.md"
    if not (plan_dir.is_dir() and qa_inspection.is_file()):
        return  # missing roots are reported by the tree validators

    leaves = {path.stem for path in plan_dir.glob("*.md")}
    rows: set[str] = set()
    for line in qa_inspection.read_text(encoding="utf-8").splitlines():
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
# Every writing Plan reference must declare its QA contract via a
# "QA `<contract>`" mapping line, the named contract file must exist,
# and every writing QA contract must be claimed by at least one leaf —
# a new text type can never ship with an ungated contract mapping.

def validate_writing_alignment(errors: list[str]) -> None:
    plan_dir = assistant_entry_dir("plan", "writing") / "references"
    qa_dir = assistant_entry_dir("quality-assurance", "writing") / "references"
    if not (plan_dir.is_dir() and qa_dir.is_dir()):
        return  # missing roots are reported by the tree validators

    contracts = {
        path.stem for path in qa_dir.glob("*.md")
    }
    claimed: set[str] = set()
    for leaf in sorted(plan_dir.glob("*.md")):
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

def validate_search_alignment(errors: list[str]) -> None:
    plan_dir = assistant_entry_dir("plan", "search") / "references"
    qa_dir = assistant_entry_dir("quality-assurance", "search") / "references"
    if not (plan_dir.is_dir() and qa_dir.is_dir()):
        return  # missing roots are reported by the tree validators

    contracts = {
        path.stem for path in qa_dir.glob("*.md")
    }
    claimed: set[str] = set()
    for leaf in sorted(plan_dir.glob("*.md")):
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

def validate_research_alignment(errors: list[str]) -> None:
    plan_dir = assistant_entry_dir("plan", "research") / "references"
    qa_dir = assistant_entry_dir("quality-assurance", "research") / "references"
    if not (plan_dir.is_dir() and qa_dir.is_dir()):
        return  # missing roots are reported by the tree validators

    contracts = {
        path.stem for path in qa_dir.glob("*.md")
    }
    claimed: set[str] = set()
    for leaf in sorted(plan_dir.glob("*.md")):
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
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors, expected_category=category)
            groups[category][name] = path
    groups["learned"], learned_roots = validate_learned_skills(learned_dir, errors)

    allowed: set[tuple[str, ...]] = {("assistant-pipeline", "SKILL.md")}
    allowed.update(("assistant-pipeline", name, "SKILL.md") for name in ASSISTANT_ENTRIES)
    for category in ("desks", "technic"):
        allowed.update((category, name, "SKILL.md") for name in groups[category])
    allowed.update(learned_roots)
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

    learned, learned_roots = validate_learned_skills(learned_dir, errors)

    allowed = {("default-pipeline", "SKILL.md")}
    allowed.update(learned_roots)
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
        hands_leaves: dict[str, dict[str, Path]] = {}
        for profile in HANDS_PROFILES:
            leaves, learned = validate_hands(profile, errors)
            hands_leaves[profile] = leaves
            summaries.append(f"{profile}={len(leaves)} leaves/{learned} learned")
        validate_hands_subjects(hands_leaves, errors)
        validate_hands_routing(hands_leaves, errors)
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
    elif args.profile in HANDS_PROFILES:
        if args.dispatch:
            parser.error("--dispatch is only valid for worker profiles")
        leaves, learned = validate_hands(args.profile, errors)
        summaries.append(f"{args.profile}={len(leaves)} leaves/{learned} learned")
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
