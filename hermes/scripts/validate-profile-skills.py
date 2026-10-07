#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6,<7"]
# ///
"""Validate Hermes skill topology, metadata, routing, and Git ownership.

The assistant profile owns a kernel and 19 flat, selectable entry skills
under profiles/assistant/skills/assistant-pipeline/. Each entry owns its
references; only common phase references remain beside the kernel.
The `default-pipeline` skill in the shared
skills/ dir is a thin CLI adapter over that tree. This validator checks the
tree topology, index routing completeness, worker
pipeline/technic topology, plugin enablement, and Git ownership boundaries.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Any

try:  # Hermes' YAML 1.1 reader when run on the Hermes test interpreter (no PyYAML there)
    import hermes_yaml as yaml
except ImportError:  # `uv run --script` with the inline PyYAML dependency
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
# Creator's hands (docs/hands/overview.md "Creator hands (v3)"): receive-only A2A
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
# Required Chat entry references and extra shared Execute files.
REQUIRED_MODE_FILES = {
    "chat": {"workspace-ops.md", "message-reply.md", "work-report.md", "cron.md", "lookups.md", "whatsapp.md",
             "signal.md", "discord.md", "telegram.md", "x.md", "note.md", "substack.md",
             "youtube.md", "google.md", "web3.md"},
    "execute": {"resident-sessions.md"},
}
# Verification contracts that must exist (migration-loss guard); extra
# leaves may grow beside them as long as the dir index routes them.
REQUIRED_QA_CONTRACTS = {
    "research": {
        "evidence-pack.md",
        "tradeoff-matrix.md",
        "fact-check.md",
        "guidance.md",
    },
    "search": {"lookup.md", "sweep.md", "hunt.md"},
    "writing": {"prose.md", "script.md"},
}
# Files beside the subject references in execute-assistant-creative/references/
# that are not hands subjects.
COMMISSIONING_SHARED_REFERENCES = {"media-ops.md"}


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


def validate_assistant_pipeline(errors: list[str]) -> int:
    """Validate the kernel, exhaustive entry set and owned reference trees.

    Returns the markdown reference file count.
    """
    # Hermes follows nested links but pathlib's recursive validation does
    # not, so reject them first.
    links = [path for path in ASSISTANT_PIPELINE.rglob("*") if path.is_symlink()]
    if links:
        for path in sorted(links):
            errors.append(f"assistant pipeline must not contain symlinks: {rel_pipeline(path)}")
        return 0
    skill = ASSISTANT_PIPELINE / "SKILL.md"
    if not skill.is_file():
        errors.append(f"missing assistant pipeline skill: {skill}")
        return 0
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
                    errors.append(f"no nesting below entry references: {rel_pipeline(leaf)}")
                elif leaf.suffix != ".md":
                    errors.append(f"non-markdown reference: {rel_pipeline(leaf)}")
                elif leaf.name == "index.md":
                    errors.append(f"entry index must be promoted to SKILL.md: {name}")

    # Scan every document, including unexpected/nested directories, so an
    # invalid shelf cannot hide an escaping Markdown link.
    files = 0
    for doc in sorted(ASSISTANT_PIPELINE.rglob("*.md")):
        files += doc.name != "SKILL.md"
        if doc.name == "SKILL.md" and doc.relative_to(ASSISTANT_PIPELINE).parts not in allowed:
            errors.append(f"unexpected skill root: {rel_pipeline(doc)}")
        for link, target in markdown_links(doc):
            if not target.is_relative_to(ASSISTANT_PIPELINE.resolve()):
                errors.append(f"assistant reference link escapes the pipeline: {link} in {rel_pipeline(doc)}")
            elif not target.is_file():
                errors.append(f"assistant reference link is broken: {link} in {rel_pipeline(doc)}")

    for capability, required in REQUIRED_QA_CONTRACTS.items():
        directory = assistant_entry_dir("quality-assurance", capability) / "references"
        present = (
            {p.name for p in directory.glob("*.md")} if directory.is_dir() else set()
        )
        for name in sorted(required - present):
            errors.append(
                f"QA contract file missing: {rel_pipeline(directory / name)}"
            )

    return files


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
            "hermes/plugins/guards/skill-topology/**",
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
        # Relative links into mutable stores have broken silently before; an
        # overlay link left behind by an older install is stale as well.
        if entry.is_symlink():
            errors.append(f"local skill root must not contain symlinks: {entry}")

    for path in sorted(skills.rglob("SKILL.md")):
        rel = path.relative_to(skills)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if rel.parts not in allowed:
            errors.append(f"unexpected skill root: {path}")


PRIVATE_OVERLAY = Path.home() / ".config" / "private"


def validate_git_boundary(
    managed: list[Path], learned: Path, errors: list[str]
) -> None:
    for path in managed:
        if path.is_symlink():
            errors.append(f"managed skill path must be a real directory, not a symlink: {path}")
        elif path.exists() and is_ignored(path):
            errors.append(f"managed skill path is gitignored: {path}")
    if not is_ignored(learned / ".gitignore-probe"):
        errors.append(f"learned skill path must be gitignored: {learned}")


def validate_plugin_source(errors: list[str]) -> None:
    for name in ("skill-topology",):
        plugin = HERMES_ROOT / "plugins" / "guards" / name
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

    learned, learned_roots = validate_learned_skills(learned_dir, errors)

    allowed = {(pipeline_name, "SKILL.md")}
    allowed.update(("technic", name, "SKILL.md") for name in leaves)
    creator_entries: set[str] = set()
    if profile == "creator" and pipeline.is_file() and (_pipeline_major_version(frontmatter(pipeline)) or 0) >= 9:
        creator_entries = set(CREATOR_ENTRIES.values())
        allowed.update((pipeline_name, name, "SKILL.md") for name in creator_entries)
        for name in creator_entries & (leaves.keys() | learned.keys()):
            errors.append(f"duplicate creator entry name: {name}")
    writing: dict[str, Path] = {}
    if profile == "writer":
        writing = validate_writer_leaves(pipeline_dir, errors)
        consultation = validate_writer_consultation(pipeline_dir, errors)
        entries = writing | consultation
        for name in entries.keys() & (leaves.keys() | learned.keys()):
            errors.append(f"duplicate writer skill name: {name}")
        allowed.update(path.relative_to(skills).parts for path in entries.values())
    entries: dict[str, Path] = {}
    if profile == "engineer":
        entries = validate_engineer_references(pipeline_dir, errors)
        for name in entries.keys() & (leaves.keys() | learned.keys()):
            errors.append(f"duplicate engineer skill name: {name}")
    if profile == "marketer":
        entries = validate_marketer_references(pipeline_dir, errors)
        for name in entries.keys() & (leaves.keys() | learned.keys()):
            errors.append(f"duplicate marketer skill name: {name}")
    if profile == "searcher":
        entries = validate_searcher_entries(pipeline_dir, errors)
        for name in entries.keys() & (leaves.keys() | learned.keys()):
            errors.append(f"duplicate searcher skill name: {name}")
    if profile == "researcher":
        entries = validate_researcher_entries(pipeline_dir, errors)
        for name in entries.keys() & (leaves.keys() | learned.keys()):
            errors.append(f"duplicate researcher skill name: {name}")
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

    if profile == "creator":
        validate_creator_references(pipeline_dir, errors)
    validate_git_boundary([pipeline_dir, technic_dir], learned_dir, errors)
    validate_plugin_enabled(profile, profile_root / "config.yaml", errors)
    return len(leaves) + len(writing) + len(entries) + len(creator_entries), len(learned)


SEARCHER_ENTRIES = ("plan-searcher", "build-searcher", "qa-searcher")
SEARCHER_UNITS = ("lookup", "sweep", "hunt")


def validate_searcher_entries(pipeline_dir: Path, errors: list[str]) -> dict[str, Path]:
    """Three phase owners retain retrieval units."""
    entries: dict[str, Path] = {}
    links = [path for path in pipeline_dir.rglob("*") if path.is_symlink()]
    if links:
        for path in sorted(links):
            errors.append(f"searcher pipeline must not contain symlinks: {path}")
        return entries

    expected = {"SKILL.md"} | {f"{name}/SKILL.md" for name in SEARCHER_ENTRIES}
    expected.update(f"{name}/references/{unit}.md" for name in SEARCHER_ENTRIES for unit in SEARCHER_UNITS)
    found = {
        path.relative_to(pipeline_dir).as_posix()
        for path in pipeline_dir.rglob("*")
        if path.is_file() and (
            path.name == "SKILL.md"
            or not any(part.startswith(".") for part in path.relative_to(pipeline_dir).parts)
        )
    }
    for path in sorted(expected - found):
        errors.append(f"missing searcher instruction: {path}")
    for path in sorted(found - expected):
        errors.append(f"unexpected searcher instruction: {path}")

    kernel = pipeline_dir / "SKILL.md"
    kernel_text = kernel.read_text(encoding="utf-8") if kernel.is_file() else ""
    for name in SEARCHER_ENTRIES:
        entry = pipeline_dir / name / "SKILL.md"
        if not entry.is_file():
            continue
        entries[name] = entry
        validate_skill(entry, name, errors, expected_category="searcher-pipeline")
        data = frontmatter(entry)
        version = data.get("version")
        if not isinstance(version, str) or not version.strip():
            errors.append(f"searcher entry version must be a nonempty string: {name}")
        description = data.get("description", "")
        unit = name.split("-", 1)[0]
        if not isinstance(description, str) or not re.match(rf"^{unit}\b", description, re.I):
            errors.append(f"searcher description must frontload {unit}: {name}")
        raw = entry.read_text(encoding="utf-8")
        if raw.find("\n---", 4) not in range(4, 4000):
            errors.append(f"searcher frontmatter exceeds 4000-character discovery prefix: {name}")
        text = raw.split("\n---\n", 1)[-1]
        read_before = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", text, re.S)
        block = " ".join(read_before.group(1).split()) if read_before else ""
        for required in (
            'skill_view(name="searcher-pipeline")',
            "${HERMES_SKILL_DIR}/../SKILL.md", "${HERMES_SKILL_DIR}/SKILL.md",
            "${HERMES_SKILL_DIR}/references/<unit>.md",
            "full-body", "current context", "not a past load or summary",
            "unchanged", "earlier body is unavailable", "read_file", "next_offset",
            "stop", "caller's release",
        ):
            if required not in block:
                errors.append(f"searcher entry ReadBeforeWork missing {required}: {name}")
        if any(section not in text for section in ("## Verification", "## Handoff", "## Output template")):
            errors.append(f"searcher entry must own its verification and handoff: {name}")
        if f"({name}/SKILL.md)" not in kernel_text:
            errors.append(f"searcher kernel does not route {name}")
        for unit in SEARCHER_UNITS:
            if f"(references/{unit}.md)" not in text:
                errors.append(f"searcher entry does not link owned reference {unit}: {name}")
            reference = pipeline_dir / name / "references" / f"{unit}.md"
            if reference.is_file():
                body = reference.read_text(encoding="utf-8")
                section = {"plan": "## Plan", "build": "## Output template", "qa": "## Verification"}[name.split("-", 1)[0]]
                if section not in body:
                    errors.append(f"searcher reference missing {section}: {reference.relative_to(pipeline_dir)}")

    for path in sorted(pipeline_dir.rglob("*.md")):
        if "goal_mode" in path.read_text(encoding="utf-8"):
            errors.append(f"searcher has no goal_mode loop: {path}")
        if path.name != "SKILL.md" and "name" in frontmatter(path):
            errors.append(f"searcher reference must not declare a skill name: {path}")
        for link, target in markdown_links(path):
            if not target.is_relative_to(pipeline_dir.resolve()):
                errors.append(f"searcher link escapes pipeline: {link} in {path}")
            elif not target.is_file():
                errors.append(f"broken searcher link: {link} in {path}")
    return entries


RESEARCHER_ENTRIES = {
    f"{phase}-researcher" for phase in ("plan", "build", "qa")
}
RESEARCHER_UNITS = ("evidence-pack", "tradeoff-matrix", "fact-check", "guidance")


def validate_researcher_entries(pipeline_dir: Path, errors: list[str]) -> dict[str, Path]:
    """Three phase owners, each with four unit guides; gathering stays shared."""
    entries: dict[str, Path] = {}
    for path in pipeline_dir.rglob("*"):
        if path.is_symlink():
            errors.append(f"researcher pipeline must not contain symlinks: {path}")
    if any(path.is_symlink() for path in pipeline_dir.rglob("*")):
        return entries
    expected = {"SKILL.md", "references/gather.md"} | {
        f"{name}/SKILL.md" for name in RESEARCHER_ENTRIES
    }
    expected.update(f"{name}/references/{unit}.md" for name in RESEARCHER_ENTRIES for unit in RESEARCHER_UNITS)
    found = {
        p.relative_to(pipeline_dir).as_posix() for p in pipeline_dir.rglob("*")
        if p.is_file() and (p.name == "SKILL.md" or not any(part.startswith(".") for part in p.relative_to(pipeline_dir).parts))
    }
    for path in sorted(expected - found):
        errors.append(f"missing researcher document: {path}")
    for path in sorted(found - expected):
        errors.append(f"unexpected researcher document: {path}")
    kernel = pipeline_dir / "SKILL.md"
    kernel_text = kernel.read_text(encoding="utf-8") if kernel.is_file() else ""
    for name in sorted(RESEARCHER_ENTRIES):
        path = pipeline_dir / name / "SKILL.md"
        if not path.is_file():
            continue
        entries[name] = path
        validate_skill(path, name, errors, expected_category="researcher-pipeline")
        data = frontmatter(path)
        description = data.get("description")
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
            errors.append(f"researcher entry needs a description: {name}")
        if not isinstance(data.get("version"), str) or not data["version"].strip():
            errors.append(f"researcher entry needs a version: {name}")
        text = path.read_text(encoding="utf-8")
        if text.find("\n---", 4) not in range(4, 4000):
            errors.append(f"researcher frontmatter exceeds discovery prefix: {name}")
        if f"({name}/SKILL.md)" not in kernel_text:
            errors.append(f"researcher kernel does not route {name}")
        block = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", text, re.S)
        before = " ".join(block.group(1).split()) if block else ""
        for required in (
            'skill_view(name="researcher-pipeline")',
            'skill_view(name="researcher-pipeline", file_path="references/gather.md")',
            "${HERMES_SKILL_DIR}/../SKILL.md",
            "${HERMES_SKILL_DIR}/../references/gather.md",
            "${HERMES_SKILL_DIR}/SKILL.md",
            "${HERMES_SKILL_DIR}/references/<unit>.md",
            "read_file", "next_offset", "stop",
        ):
            if required not in before:
                errors.append(f"researcher entry missing dependency/recovery {required}: {name}")
        if not re.search(r"reuse.*full.*(?:context|body)", before, re.I):
            errors.append(f"researcher entry missing full-body reuse contract: {name}")
        for section in ("## Output template", "## Verification", "## Handoff"):
            if section not in text:
                errors.append(f"researcher entry missing {section}: {name}")
        for unit in RESEARCHER_UNITS:
            if f"(references/{unit}.md)" not in text:
                errors.append(f"researcher entry does not link owned reference {unit}: {name}")
            reference = pipeline_dir / name / "references" / f"{unit}.md"
            if reference.is_file():
                body = reference.read_text(encoding="utf-8")
                section = {"plan": "## Plan", "build": "## Output template", "qa": "## Verification"}[name.split("-", 1)[0]]
                if section not in body:
                    errors.append(f"researcher reference missing {section}: {reference.relative_to(pipeline_dir)}")
    for doc in sorted(pipeline_dir.rglob("*.md")):
        if doc.is_symlink() or not doc.resolve().is_relative_to(pipeline_dir.resolve()):
            errors.append(f"researcher document escapes pipeline: {doc}")
            continue
        if doc.name != "SKILL.md" and "name" in frontmatter(doc):
            errors.append(f"researcher reference must not declare a skill name: {doc}")
        for link, target in markdown_links(doc):
            if not target.resolve().is_relative_to(pipeline_dir.resolve()) or not target.is_file():
                errors.append(f"broken/escaping researcher link: {doc.name}: {link}")
    return entries


ENGINEER_ENTRIES = {
    "plan-engineer": {"web-ui.md", "hands-references.md"},
    "build-engineer": {"web-ui.md", "hands-references.md"},
    "qa-engineer": {"web-ui.md", "hands-references.md"},
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
        for leaf in sorted(references):
            if f"](references/{leaf})" not in text:
                errors.append(f"engineer {name} entry does not route {leaf}")
    root = pipeline_dir.resolve()
    for path in pipeline_dir.rglob("*.md"):
        for link, target in markdown_links(path):
            if not target.is_relative_to(root):
                errors.append(f"engineer reference escapes pipeline: {path.name}: {link}")
            elif not target.is_file():
                errors.append(f"broken engineer reference link: {path.name}: {link}")
    return entries


MARKETER_ENTRY_REFERENCES = {
    "plan-marketer": {"discovery.md", "positioning.md", "offer.md", "channels.md", "campaign.md",
                      "strategy.md"},
    "review-marketer": {"content.md"},
    "analyze-marketer": {"measurement.md"},
}
MARKETER_SHARED_REFERENCES = {
    "platforms/x.md", "platforms/substack.md", "platforms/note.md",
    "platforms/zenn.md", "state.md", "x-ranking.md", "browsing.md",
}
MARKETER_REFERENCE_FILES = {
    f"references/{name}" for name in MARKETER_SHARED_REFERENCES
} | {
    f"{entry}/references/{name}"
    for entry, names in MARKETER_ENTRY_REFERENCES.items() for name in names
}


def validate_marketer_references(pipeline_dir: Path, errors: list[str]) -> dict[str, Path]:
    """Three advisory entries depend on one kernel and shared platform rules."""
    entries: dict[str, Path] = {}
    symlinks = [path for path in pipeline_dir.rglob("*") if path.is_symlink()]
    for path in symlinks:
        errors.append(f"marketer pipeline must not contain symlinks: {path}")
    if symlinks:
        return entries
    pipeline = pipeline_dir / "SKILL.md"
    major = _pipeline_major_version(frontmatter(pipeline) if pipeline.is_file() else {})
    if major is None:
        errors.append("invalid marketer pipeline version")
        return entries
    references = pipeline_dir / "references"
    if major < 7 and not any((references / mode).is_dir() for mode in
                             ("plan", "build", "quality-assurance", "analyze")):
        return entries
    if major < 9:
        errors.append("marketer advisory entries require pipeline version 9 or later")

    allowed_skills = {pipeline} | {
        pipeline_dir / name / "SKILL.md" for name in MARKETER_ENTRY_REFERENCES
    }
    for path in pipeline_dir.rglob("SKILL.md"):
        if path not in allowed_skills:
            errors.append(f"unexpected marketer skill root: {path.relative_to(pipeline_dir)}")
    found = {
        p.relative_to(pipeline_dir).as_posix()
        for p in pipeline_dir.rglob("*.md") if p.name != "SKILL.md"
    }
    for name in sorted(MARKETER_REFERENCE_FILES - found):
        errors.append(f"missing marketer reference: {name}")
    for name in sorted(found - MARKETER_REFERENCE_FILES):
        errors.append(f"unexpected marketer reference: {name}")

    for name in MARKETER_ENTRY_REFERENCES:
        entry = pipeline_dir / name / "SKILL.md"
        if not entry.is_file():
            errors.append(f"missing marketer entry skill: {name}")
            continue
        entries[name] = entry
        validate_skill(entry, name, errors, expected_category="marketer-pipeline")
        data = frontmatter(entry)
        if not isinstance(data.get("version"), str) or not data["version"].strip():
            errors.append(f"marketer entry version must be a nonempty string: {name}")
        description = data.get("description", "")
        prefix = f"{name.split('-', 1)[0]} marketing"
        if not isinstance(description, str) or not description.lower().startswith(prefix):
            errors.append(f"marketer entry description must frontload {prefix}: {name}")
        text = entry.read_text(encoding="utf-8")
        read_before = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", text, re.S)
        block = " ".join(read_before.group(1).split()) if read_before else ""
        for required in (
            'skill_view(name="marketer-pipeline")',
            "${HERMES_SKILL_DIR}/../SKILL.md", "${HERMES_SKILL_DIR}/SKILL.md",
            "read_file", "next_offset",
        ):
            if required not in block:
                errors.append(f"marketer entry missing dependency/recovery {required}: {name}")
        for label, pattern in (
            ("full-body reuse", r"reuse full-body.*current context"),
            ("not a summary", r"never a past load or summary"),
            ("per-turn selection", r"each user turn.*completion"),
            ("midturn selection", r"before a mode, target, platform or scope-changing action"),
            ("missing body recovery", r"unchanged.*earlier body is unavailable"),
            ("stop on missing body", r"body remains missing, stop"),
            ("preserve grants", r"does not restart.*reset approvals or expand a grant"),
        ):
            if not re.search(pattern, block, re.I):
                errors.append(f"marketer entry ReadBeforeWork missing {label}: {name}")
        for child in entry.parent.iterdir():
            if not child.name.startswith(".") and child.name not in {"SKILL.md", "references"}:
                errors.append(f"unexpected marketer entry child: {name}/{child.name}")

    root = pipeline_dir.resolve()
    links_by_doc: dict[Path, set[Path]] = {}
    for doc in sorted(pipeline_dir.rglob("*.md")):
        if not doc.is_file():
            continue
        linked = links_by_doc.setdefault(doc, set())
        for link, target in markdown_links(doc):
            if not target.is_relative_to(root):
                errors.append(f"marketer reference escapes pipeline: {link}")
            elif not target.is_file():
                errors.append(f"broken marketer reference: {link}")
            linked.add(target)
    # Ownership, not one fat root: kernel names the shared files and entries;
    # each entry names every detail it owns and its shared dependencies.
    root_links = links_by_doc.get(pipeline, set())
    for name in sorted(MARKETER_SHARED_REFERENCES):
        if (references / name).resolve() not in root_links:
            errors.append(f"marketer root does not link reference: {name}")
    for name, names in MARKETER_ENTRY_REFERENCES.items():
        entry = pipeline_dir / name / "SKILL.md"
        if entry.resolve() not in root_links:
            errors.append(f"marketer root does not route entry: {name}")
        if entry.is_file():
            own_links = links_by_doc.get(entry, set())
            expected = {entry.parent / "references" / filename for filename in names}
            expected.update(references / filename for filename in MARKETER_SHARED_REFERENCES)
            for target in sorted(expected):
                if target.resolve() not in own_links:
                    errors.append(f"marketer entry does not link reference: {name}: {target.name}")
    for directory in [references, *(path.parent / "references" for path in entries.values())]:
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix != ".md":
                errors.append(f"non-markdown marketer reference: {path.relative_to(pipeline_dir)}")
    if not (pipeline_dir / "scripts/browser-lease.py").is_file():
        errors.append("missing marketer browser lease helper")
    return entries


def validate_writer_read_contract(path: Path, pipeline_dir: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", text, re.S)
    block = " ".join(match.group(1).split()) if match else ""
    up = "/".join(".." for _ in path.parent.relative_to(pipeline_dir).parts)
    for required in (
        'skill_view(name="writer-pipeline")',
        f"${{HERMES_SKILL_DIR}}/{up}/SKILL.md",
        "as Writer", "current context", "past load or summary", "Re-evaluate",
        "Reuse", "unchanged", "read_file", "next_offset", "stop the affected action",
        "Client reading", "inherit Writer's role",
    ):
        if required not in block:
            errors.append(f"writer ReadBeforeWork missing {required}: {path}")


def validate_writer_consultation(pipeline_dir: Path, errors: list[str]) -> dict[str, Path]:
    """The sole advisory entry is not a form-based production operation."""
    path = pipeline_dir / "consult-writer" / "SKILL.md"
    if not path.is_file():
        errors.append(f"missing Writer advisory entry: {path}")
        return {}
    validate_skill(path, "consult-writer", errors, expected_category="writing")
    data = frontmatter(path)
    meta = hermes_meta(data)
    if not isinstance(data.get("description"), str) or not data["description"].startswith(
        "Writer advice before drafting:"
    ):
        errors.append(f"Writer consultation description must frontload pre-draft advice: {path}")
    if not isinstance(meta.get("output"), str) or not meta["output"].strip():
        errors.append(f"Writer consultation must describe its advisory output: {path}")
    if "form" in meta:
        errors.append(f"Writer consultation is not a production form: {path}")
    validate_writer_read_contract(path, pipeline_dir, errors)
    if (pipeline_dir / "references/consultation.md").exists():
        errors.append("retired Writer consultation reference must not duplicate the entry")
    return {"consult-writer": path}


def validate_writer_leaves(pipeline_dir: Path, errors: list[str]) -> dict[str, Path]:
    """Writer adopts form-based leaves without changing Creator's verb set."""
    leaves: dict[str, Path] = {}
    for path in sorted(pipeline_dir.rglob("SKILL.md")):
        rel = path.relative_to(pipeline_dir)
        if rel.parts in (("SKILL.md",), ("consult-writer", "SKILL.md")):
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
        validate_writer_read_contract(path, pipeline_dir, errors)
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


def validate_hands_routing(
    hands_leaves: dict[str, dict[str, Path]], errors: list[str]
) -> None:
    """Every installed hands subject has exactly one Assistant commissioning
    reference (execute-assistant-creative/references/<subject>.md) and every
    installed leaf is named in it, so no leaf is unreachable from the
    commissioning side; a reference for a subject no hands serves is an
    orphan. Paths are derived from the current ASSISTANT_PIPELINE global at
    call time so tests can patch it."""
    refs = assistant_entry_dir("execute", "creative") / "references"
    subjects: dict[str, str] = {}
    for profile, leaves in hands_leaves.items():
        for name, path in leaves.items():
            subjects.setdefault(path.parent.name, profile)
    present = (
        {p.stem for p in refs.glob("*.md") if p.name not in COMMISSIONING_SHARED_REFERENCES}
        if refs.is_dir() else set()
    )
    for subject in sorted(subjects.keys() - present):
        errors.append(
            f"hands subject has no commissioning reference: {subjects[subject]}/{subject}"
        )
    for subject in sorted(present - subjects.keys()):
        errors.append(f"commissioning reference has no hands subject: {subject}.md")
    for profile, leaves in hands_leaves.items():
        for name, path in sorted(leaves.items()):
            ref = refs / f"{path.parent.name}.md"
            if ref.is_file() and not re.search(
                rf"(?<![\w-]){re.escape(name)}(?![\w-])", ref.read_text(encoding="utf-8")
            ):
                errors.append(
                    f"commissioning reference does not name installed leaf: {profile}: {name}"
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
    learned, learned_roots = validate_learned_skills(learned_dir, errors)

    allowed = {(pipeline_name, "SKILL.md")}
    allowed.update(
        (pipeline_name, *path.relative_to(pipeline_dir).parts) for path in leaves.values()
    )
    allowed.update(learned_roots)
    validate_allowed_skill_roots(skills, allowed, errors)
    validate_git_boundary([pipeline_dir], learned_dir, errors)
    validate_plugin_enabled(profile, profile_root / "config.yaml", errors)
    return leaves, len(learned)


# ── Creator references (v10 advisor tree) ───────────────────────────────
#
# Creator advises the Assistant: a kernel, two entries (propose / revise) and
# one capability reference per served hands subject under
# `references/<hands>/<subject>.md` (subjects read from the hands leaves on
# disk, never hardcoded).

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


CREATOR_ENTRIES = {
    "propose": "propose-creator",
    "revise": "revise-creator",
}
CREATOR_PIPELINE_MAJOR = 10


def validate_creator_references(pipeline_dir: Path, errors: list[str]) -> None:
    """Validate the v10 advisor tree: the kernel links both entries and every
    capability reference; references hold exactly one file per served hands
    subject, flat under its hands directory, with links that stay inside the
    pipeline."""
    pipeline = pipeline_dir / "SKILL.md"
    major = _pipeline_major_version(frontmatter(pipeline) if pipeline.is_file() else {})
    if major != CREATOR_PIPELINE_MAJOR:
        errors.append(f"creator pipeline must be version {CREATOR_PIPELINE_MAJOR}: {major}")
        return
    kernel_links = {target for _, target in markdown_links(pipeline)}
    validate_creator_reference_links(pipeline, pipeline_dir, errors)

    for name in CREATOR_ENTRIES.values():
        index = pipeline_dir / name / "SKILL.md"
        if not index.is_file():
            errors.append(f"missing creator entry skill: {name}/SKILL.md")
            continue
        validate_skill(index, name, errors, expected_category="creator-pipeline")
        if _pipeline_major_version(frontmatter(index)) is None:
            errors.append(f"invalid creator entry version: {name}")
        if not str(frontmatter(index).get("description", "")).strip():
            errors.append(f"missing creator entry description: {name}")
        if index.resolve() not in kernel_links:
            errors.append(f"creator kernel does not link entry: {name}")
        text = index.read_text(encoding="utf-8")
        context = re.search(r"<ReadBeforeWork>(.*?)</ReadBeforeWork>", text, re.S)
        block = " ".join(context.group(1).split()) if context else ""
        for required in (
            'skill_view(name="creator-pipeline")',
            "full body", "Reuse", "unchanged", "read_file",
            "next_offset", "stop", "${HERMES_SKILL_DIR}/../SKILL.md",
            "${HERMES_SKILL_DIR}/SKILL.md",
        ):
            if required not in block:
                errors.append(f"creator entry ReadBeforeWork missing {required}: {name}")
        for child in index.parent.iterdir():
            if not child.name.startswith(".") and child.name != "SKILL.md":
                errors.append(f"unexpected creator entry child: {name}/{child.name}")
        validate_creator_reference_links(index, pipeline_dir, errors)

    for child in pipeline_dir.iterdir():
        if not child.name.startswith(".") and child.name not in {
            "SKILL.md", "references", *CREATOR_ENTRIES.values()
        }:
            errors.append(f"unexpected creator pipeline child: {child.name}")

    references = pipeline_dir / "references"
    hands_subjects = collect_hands_subjects()
    if references.is_dir():
        for shared in sorted(references.iterdir()):
            if shared.name.startswith("."):
                continue
            if not shared.is_dir() or shared.name not in HANDS_PROFILES:
                errors.append(f"unexpected creator reference: {shared.name}")
    for hands, expected in hands_subjects.items():
        directory = references / hands
        found: set[str] = set()
        if directory.is_dir():
            for leaf in sorted(directory.iterdir()):
                if leaf.name.startswith("."):
                    continue
                rel = f"{hands}/{leaf.name}"
                if leaf.is_dir():
                    errors.append(f"no nesting below a creator reference hands dir: {rel}")
                    continue
                if leaf.suffix != ".md" or leaf.name == "SKILL.md":
                    errors.append(f"unexpected file in creator references: {rel}")
                    continue
                if not leaf.read_text(encoding="utf-8").strip():
                    errors.append(f"empty creator reference file: {rel}")
                found.add(leaf.stem)
                if leaf.resolve() not in kernel_links:
                    errors.append(f"creator kernel does not link {hands}/{leaf.stem}")
                validate_creator_reference_links(leaf, pipeline_dir, errors)
        for missing in sorted(expected - found):
            errors.append(f"creator references missing hands subject: {hands}/{missing}")
        for orphan in sorted(found - expected):
            errors.append(f"creator references have orphan hands subject: {hands}/{orphan}")


# ── Creative Client references ───────────────────────────────────────────
#
# The plain-language guides in plan-assistant-creative/references/ carry no
# parity with the hands: a guide's name need not equal a hands subject, and an
# absent guide does not mean a capability is unavailable. Paths are derived
# from the current ASSISTANT_PIPELINE global at call time so tests can patch it.

# Headings every plain-language creative guide must carry verbatim;
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
    "legacy",
)
# A backtick-quoted local path reference: requires a directory component
# (so bare produced-artifact names like `proposal.md` are not treated as
# references) and an .md/.md-index target; SKILL.md and non-.md paths
# (scripts, form fields) are excluded explicitly.
CREATIVE_BACKTICK_REF = re.compile(r"`([^`\s]+)`")


def validate_creative_new_guides(plan_dir: Path, errors: list[str]) -> None:
    """Every plain-language guide directly under the Plan entry's references
    (not reference-research.md) must carry the four client-facing headings
    verbatim."""
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
    """Local document references across the three creative entries, confined
    to the pipeline root and never pointing at a retired shelf."""
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
    if plan_dir.is_dir():
        validate_creative_new_guides(plan_dir, errors)
    validate_creative_references(ASSISTANT_PIPELINE, errors)


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


def validate_assistant_dm_topics(config: Path, errors: list[str]) -> None:
    """Pinned Telegram DM topics are skill-less surfaces (Inbox, Admin).

    The topic-bound desk skills were retired on 2026-09-14; every pinned topic
    is governed by its ``channel_prompts`` contract only, and the chat-wide
    ``assistant-pipeline`` binding stays the single skill surface. A ``skill``
    key on a topic would silently resurrect a per-topic skill layer, so it is
    rejected outright. ``Inbox`` must keep its literal name: the secrets helper
    derives ``TELEGRAM_CRON_THREAD_ID`` from it by name.
    """
    if not config.is_file():
        return
    data = load_yaml(config)
    dm_topics = (
        data.get("platforms", {})
        .get("telegram", {})
        .get("extra", {})
        .get("dm_topics", [])
    )
    names: list[str] = []
    for chat in dm_topics if isinstance(dm_topics, list) else []:
        for topic in chat.get("topics", []) if isinstance(chat, dict) else []:
            if not isinstance(topic, dict):
                continue
            name = topic.get("name")
            if isinstance(name, str):
                names.append(name)
            if topic.get("skill"):
                errors.append(
                    f"Telegram topic {name!r} binds a skill ({topic['skill']}); "
                    "pinned topics are skill-less (desks retired 2026-09-14)"
                )
    if dm_topics and "Inbox" not in names:
        errors.append(
            "Telegram dm_topics must keep a topic named 'Inbox' "
            "(profile-secrets.sh derives TELEGRAM_CRON_THREAD_ID from it)"
        )


def validate_assistant(errors: list[str]) -> tuple[int, int, int]:
    profile_root = HERMES_ROOT / "profiles" / "assistant"
    skills = profile_root / "skills"
    technic_dir = skills / "technic"
    learned_dir = skills / "learned"

    refs = validate_assistant_pipeline(errors)
    if not technic_dir.is_dir():
        errors.append(f"missing assistant technic directory: {technic_dir}")
    if (skills / "desks").exists():
        errors.append(
            f"stale assistant desks directory: {skills / 'desks'} "
            "(desk skills retired 2026-09-14; remove the overlay link)"
        )

    technics: dict[str, Path] = {}
    if technic_dir.is_dir():
        for path in sorted(technic_dir.glob("*/SKILL.md")):
            name = path.parent.name
            validate_skill(path, name, errors, expected_category="technic")
            technics[name] = path
    learned, learned_roots = validate_learned_skills(learned_dir, errors)

    allowed: set[tuple[str, ...]] = {("assistant-pipeline", "SKILL.md")}
    allowed.update(("assistant-pipeline", name, "SKILL.md") for name in ASSISTANT_ENTRIES)
    allowed.update(("technic", name, "SKILL.md") for name in technics)
    allowed.update(learned_roots)
    validate_allowed_skill_roots(skills, allowed, errors)

    config = profile_root / "config.yaml"
    private_technics = validate_assistant_private_technics(
        assistant_private_technic_dir(), config, errors
    )
    validate_assistant_dm_topics(config, errors)

    validate_git_boundary([ASSISTANT_PIPELINE, technic_dir], learned_dir, errors)
    if config.is_file():
        validate_plugin_enabled("assistant", config, errors)
        validate_assistant_messaging_config(config, errors)
    example_config = profile_root / "config.example.yaml"
    validate_plugin_enabled("assistant", example_config, errors)
    validate_assistant_messaging_config(example_config, errors)
    validate_assistant_dm_topics(example_config, errors)
    return (
        refs,
        len(technics) + private_technics,
        len(learned),
    )


def assistant_private_technic_dir() -> Path:
    """The Assistant's private technic shelf, mirrored at the public path."""
    return PRIVATE_OVERLAY / "hermes" / "profiles" / "assistant" / "skills" / "technic"


_SKIPPED_SKILL_PARTS = {"__pycache__", "node_modules"}


def _skill_dir_names(root: Path) -> dict[str, Path]:
    """Name -> SKILL.md for every visible skill below ``root``, keyed by both
    directory name and frontmatter ``name`` (``skill_view`` matches either)."""
    names: dict[str, Path] = {}
    if not root.is_dir():
        return names
    for path in sorted(root.rglob("SKILL.md")):
        rel = path.relative_to(root).parts
        if any(part.startswith(".") or part in _SKIPPED_SKILL_PARTS for part in rel):
            continue
        names.setdefault(path.parent.name, path)
        try:
            declared = frontmatter(path).get("name")
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        if isinstance(declared, str) and declared.strip():
            names.setdefault(declared.strip(), path)
    return names


def _configured_external_dirs(config: Path) -> list[Path]:
    if not config.is_file():
        return []
    skills_cfg = load_yaml(config).get("skills")
    entries = skills_cfg.get("external_dirs") if isinstance(skills_cfg, dict) else None
    dirs: list[Path] = []
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str) and entry.strip():
            dirs.append(Path(entry.strip()).expanduser().resolve())
    return dirs


def validate_assistant_private_technics(
    technic_dir: Path, config: Path, errors: list[str]
) -> int:
    """Validate the private technic shelf the Assistant reads via external_dirs.

    It mirrors the public ``technic/``: flat ``<name>/SKILL.md`` leaves with
    ``metadata.hermes.category: technic``, real files only, and names unique
    across every skill source the Assistant indexes (a duplicate makes
    ``skill_view`` refuse an ambiguous name). Returns the leaf count.
    """
    external = _configured_external_dirs(config)
    # Listing an ancestor would index assistant-pipeline a second time.
    pipeline = ASSISTANT_PIPELINE.resolve() if ASSISTANT_PIPELINE.exists() else None
    for directory in external:
        if pipeline is not None and pipeline.is_relative_to(directory):
            errors.append(
                f"external_dirs entry also contains assistant-pipeline: {directory}"
            )
    resolved = technic_dir.resolve() if technic_dir.exists() else None
    listed = resolved is not None and resolved in external
    if not technic_dir.exists():
        target = technic_dir.expanduser().resolve()
        if target in external:
            errors.append(f"external_dirs lists a missing private technic directory: {technic_dir}")
        return 0
    if technic_dir.is_symlink() or not technic_dir.is_dir():
        errors.append(f"private technic directory must be a real directory: {technic_dir}")
        return 0

    links = sorted(path for path in technic_dir.rglob("*") if path.is_symlink())
    for path in links:
        errors.append(f"private technic must not contain symlinks: {path}")
    if links:
        return 0

    leaves: dict[str, Path] = {}
    for path in sorted(technic_dir.glob("*/SKILL.md")):
        name = path.parent.name
        if name.startswith("."):
            continue
        validate_skill(path, name, errors, expected_category="technic")
        leaves[name] = path
    for path in sorted(technic_dir.rglob("SKILL.md")):
        rel = path.relative_to(technic_dir).parts
        if any(part.startswith(".") for part in rel):
            continue
        if len(rel) != 2:
            errors.append(f"unexpected private technic root: {path}")
    if leaves and not listed:
        errors.append(
            f"private technic directory is not in skills.external_dirs: {technic_dir} ({config})"
        )

    # Every other source the Assistant indexes: its own skills dir and the
    # remaining external dirs.
    others: dict[str, Path] = {}
    sources = [config.parent / "skills", *(d for d in external if d != resolved)]
    for source in sources:
        for name, path in _skill_dir_names(source).items():
            others.setdefault(name, path)
    for name in ("assistant-pipeline", *ASSISTANT_ENTRIES):
        others.setdefault(name, ASSISTANT_PIPELINE)
    for name, path in sorted(leaves.items()):
        if name in others:
            errors.append(
                f"private technic name {name} is not unique: {path} and {others[name]}"
            )
    return len(leaves)


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
        refs, technics, learned = validate_assistant(errors)
        summaries.append(
            f"assistant-pipeline={refs} refs; "
            f"assistant={technics} technics/{learned} learned"
        )
        for profile in WORKER_PROFILES:
            technics, learned = validate_worker(profile, errors)
            kind = "unit entries" if profile == "searcher" else "technics"
            summaries.append(f"{profile}={technics} {kind}/{learned} learned")
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
        refs, technics, learned = validate_assistant(errors)
        summaries.append(
            f"assistant-pipeline={refs} refs; "
            f"assistant={technics} technics/{learned} learned"
        )
    elif args.profile in HANDS_PROFILES:
        if args.dispatch:
            parser.error("--dispatch is only valid for worker profiles")
        leaves, learned = validate_hands(args.profile, errors)
        summaries.append(f"{args.profile}={len(leaves)} leaves/{learned} learned")
    else:
        technics, learned = validate_worker(
            args.profile, errors, args.dispatch
        )
        kind = "unit entries" if args.profile == "searcher" else "technics"
        summaries.append(f"{args.profile}={technics} {kind}/{learned} learned")

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
