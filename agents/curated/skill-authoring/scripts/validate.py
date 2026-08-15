# SPDX-License-Identifier: MIT
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "PyYAML>=6.0,<7",
# ]
# ///
"""Validate one Agent Skill without modifying it.

Usage:
    uv run scripts/validate.py <skill-directory>

Exit codes:
    0: no errors (warnings may be present)
    1: one or more validation errors
    2: invalid command-line usage
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml
from yaml.constructor import ConstructorError
from yaml.resolver import BaseResolver

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500
MAX_SKILL_LINES = 500

PORTABLE_FRONTMATTER_FIELDS = {
    "allowed-tools",
    "compatibility",
    "description",
    "license",
    "metadata",
    "name",
}
RESOURCE_DIRECTORIES = ("agents", "assets", "references", "scripts")
AUXILIARY_DOCUMENTS = {
    "changelog.md",
    "installation_guide.md",
    "quick_reference.md",
    "readme.md",
}
EXCLUDED_PARTS = {".git", "__pycache__", "node_modules"}

FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)",
    re.DOTALL,
)
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
BACKTICK_RUN_RE = re.compile(r"`+")
INLINE_LINK_START_RE = re.compile(r"!?\[[^\]\r\n]*\]\(")
REFERENCE_DEFINITION_RE = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*(.+?)\s*$")
REFERENCE_LINK_RE = re.compile(r"!?\[([^\]]+)\]\[([^\]]*)\]")
RESOURCE_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])((?:agents|assets|references|scripts)/[A-Za-z0-9._@+()/-]+)"
)
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
BLOCKQUOTE_PREFIX_RE = re.compile(r"^\s{0,3}>\s?")
LIST_PREFIX_RE = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+")
PLACEHOLDER_LINE_RE = re.compile(
    r"^(?:(?:[-*+]|\d+[.)])\s+|>\s*)*(?:#{1,6}\s+)?(?:\[?TODO(?:\]|:)|FIXME(?:\s*:|$))",
    re.IGNORECASE,
)
HTML_PLACEHOLDER_RE = re.compile(
    r"<!--\s*(?:TODO|FIXME)(?:\s*:|\s*-->)", re.IGNORECASE
)


@dataclass(frozen=True)
class Finding:
    level: str
    message: str
    path: Path | None = None
    line: int | None = None


class FrontmatterLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous mapping keys."""


def _construct_unique_string_mapping(
    loader: FrontmatterLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "frontmatter mapping keys must be strings",
                key_node.start_mark,
            )
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate frontmatter key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


FrontmatterLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_string_mapping
)


def _is_excluded(path: Path, root: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _validate_symlinks(skill_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in skill_root.rglob("*"):
        if _is_excluded(path, skill_root) or not path.is_symlink():
            continue
        if _is_within(path, skill_root):
            findings.append(
                Finding(
                    "WARNING",
                    "internal symlink may not survive Skill packaging",
                    path,
                )
            )
        else:
            findings.append(
                Finding("ERROR", "symlink resolves outside the Skill", path)
            )
    return findings


def _read_text(path: Path, findings: list[Finding]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        findings.append(Finding("ERROR", f"cannot read UTF-8 text: {exc}", path))
        return None


def _parse_frontmatter(
    content: str, skill_md: Path, findings: list[Finding]
) -> tuple[dict[str, object] | None, str]:
    match = FRONTMATTER_RE.match(content)
    if not match:
        findings.append(
            Finding(
                "ERROR",
                "SKILL.md must start with YAML frontmatter delimited by '---'",
                skill_md,
                1,
            )
        )
        return None, ""

    try:
        parsed = yaml.load(match.group("yaml"), Loader=FrontmatterLoader)
    except yaml.YAMLError as exc:
        findings.append(Finding("ERROR", f"invalid YAML frontmatter: {exc}", skill_md))
        return None, content[match.end() :]

    if not isinstance(parsed, dict):
        findings.append(
            Finding("ERROR", "frontmatter must be a YAML mapping", skill_md, 1)
        )
        return None, content[match.end() :]

    return parsed, content[match.end() :]


def _validate_frontmatter(
    frontmatter: dict[str, object], skill_root: Path, skill_md: Path
) -> list[Finding]:
    findings: list[Finding] = []
    unknown = sorted(set(frontmatter) - PORTABLE_FRONTMATTER_FIELDS)
    if unknown:
        findings.append(
            Finding(
                "WARNING",
                "non-portable frontmatter field(s): " + ", ".join(unknown),
                skill_md,
                1,
            )
        )

    name = frontmatter.get("name")
    if name is None:
        findings.append(Finding("ERROR", "missing required field 'name'", skill_md, 1))
    elif not isinstance(name, str):
        findings.append(Finding("ERROR", "'name' must be a string", skill_md, 1))
    else:
        normalized_name = name.strip()
        if not normalized_name:
            findings.append(Finding("ERROR", "'name' must not be empty", skill_md, 1))
        elif len(normalized_name) > MAX_NAME_LENGTH:
            findings.append(
                Finding(
                    "ERROR",
                    f"'name' exceeds {MAX_NAME_LENGTH} characters",
                    skill_md,
                    1,
                )
            )
        elif not SKILL_NAME_RE.fullmatch(normalized_name):
            findings.append(
                Finding(
                    "ERROR",
                    "'name' must use lowercase letters, digits, and single hyphens",
                    skill_md,
                    1,
                )
            )
        if normalized_name and normalized_name != skill_root.name:
            findings.append(
                Finding(
                    "WARNING",
                    f"portable 'name' ({normalized_name}) should match directory ({skill_root.name}); confirm client-specific nested layout",
                    skill_md,
                    1,
                )
            )

    description = frontmatter.get("description")
    if description is None:
        findings.append(
            Finding("ERROR", "missing required field 'description'", skill_md, 1)
        )
    elif not isinstance(description, str):
        findings.append(
            Finding("ERROR", "'description' must be a string", skill_md, 1)
        )
    else:
        stripped_description = description.strip()
        if not stripped_description:
            findings.append(
                Finding("ERROR", "'description' must not be empty", skill_md, 1)
            )
        elif len(stripped_description) > MAX_DESCRIPTION_LENGTH:
            findings.append(
                Finding(
                    "ERROR",
                    f"'description' exceeds {MAX_DESCRIPTION_LENGTH} characters",
                    skill_md,
                    1,
                )
            )
        if "<" in stripped_description or ">" in stripped_description:
            findings.append(
                Finding(
                    "ERROR",
                    "'description' must not contain angle brackets",
                    skill_md,
                    1,
                )
            )
        lowered_description = stripped_description.lower()
        scaffold_description = (
            lowered_description in {"todo", "todo:", "[todo]", "fixme", "fixme:"}
            or lowered_description.startswith(
                ("todo:", "fixme:", "[todo:", "[fixme:")
            )
            or "complete and informative explanation of what the skill does"
            in lowered_description
        )
        if scaffold_description:
            findings.append(
                Finding(
                    "ERROR",
                    "'description' contains an unresolved scaffold placeholder",
                    skill_md,
                    1,
                )
            )

    compatibility = frontmatter.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, str):
            findings.append(
                Finding("ERROR", "'compatibility' must be a string", skill_md, 1)
            )
        elif len(compatibility.strip()) > MAX_COMPATIBILITY_LENGTH:
            findings.append(
                Finding(
                    "ERROR",
                    f"'compatibility' exceeds {MAX_COMPATIBILITY_LENGTH} characters",
                    skill_md,
                    1,
                )
            )

    license_value = frontmatter.get("license")
    if license_value is not None and not isinstance(license_value, str):
        findings.append(Finding("ERROR", "'license' must be a string", skill_md, 1))

    allowed_tools = frontmatter.get("allowed-tools")
    if allowed_tools is not None and not isinstance(allowed_tools, str):
        findings.append(
            Finding("WARNING", "portable 'allowed-tools' is a string", skill_md, 1)
        )

    metadata = frontmatter.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            findings.append(
                Finding("WARNING", "portable 'metadata' is a string map", skill_md, 1)
            )
        elif any(not isinstance(key, str) or not isinstance(value, str) for key, value in metadata.items()):
            findings.append(
                Finding(
                    "WARNING",
                    "portable 'metadata' values are strings; confirm client-specific extensions",
                    skill_md,
                    1,
                )
            )

    return findings


def _validate_placeholders(body: str, skill_md: Path) -> list[Finding]:
    findings: list[Finding] = []
    fence: tuple[str, int] | None = None
    for line_number, line in enumerate(body.splitlines(), start=1):
        stripped = line.strip()
        fence_line = _markdown_container_content(line)
        fence_match = FENCE_RE.match(fence_line)
        if fence_match:
            run = fence_match.group(1)
            if fence is None:
                fence = (run[0], len(run))
            elif (
                run[0] == fence[0]
                and len(run) >= fence[1]
                and not fence_line[fence_match.end() :].strip()
            ):
                fence = None
            continue
        if fence is not None:
            continue
        if PLACEHOLDER_LINE_RE.match(stripped) or HTML_PLACEHOLDER_RE.search(line):
            findings.append(
                Finding(
                    "ERROR",
                    "unresolved TODO/FIXME scaffold placeholder",
                    skill_md,
                    line_number,
                )
            )
        lowered = stripped.lower()
        if "replace with the first main section" in lowered or lowered.startswith(
            "this is a placeholder"
        ):
            findings.append(
                Finding(
                    "ERROR",
                    "unresolved scaffold instruction",
                    skill_md,
                    line_number,
                )
            )
    return findings


def _markdown_link_target(raw_target: str) -> tuple[str, bool] | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    elif re.search(r"\s+[\"']", target):
        target = re.split(r"\s+[\"']", target, maxsplit=1)[0]

    if not target or target.startswith("#"):
        return None
    if any(marker in target for marker in ("$", "*", "{", "}", "<", ">")):
        return None
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", target):
        return None

    if re.match(r"^[A-Za-z]:[\\/]", target):
        return target, True

    parsed = urlsplit(target)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
        if not path:
            return None
        return path, bool(parsed.netloc) or path.startswith(("/", "~"))
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    return path, path.startswith(("/", "~"))


def _markdown_container_content(line: str) -> str:
    content = line
    while True:
        prefix = BLOCKQUOTE_PREFIX_RE.match(content)
        if prefix:
            content = content[prefix.end() :]
            continue
        prefix = LIST_PREFIX_RE.match(content)
        if prefix:
            content = content[prefix.end() :]
            continue
        break
    return content


def _iter_markdown_lines(text: str):
    fence: tuple[str, int] | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        fence_line = _markdown_container_content(line)
        fence_match = FENCE_RE.match(fence_line)
        if fence_match:
            run = fence_match.group(1)
            if fence is None:
                fence = (run[0], len(run))
            elif (
                run[0] == fence[0]
                and len(run) >= fence[1]
                and not fence_line[fence_match.end() :].strip()
            ):
                fence = None
            continue
        if fence is None:
            yield line_number, line


def _code_spans(line: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    cursor = 0
    while opener := BACKTICK_RUN_RE.search(line, cursor):
        opener_length = len(opener.group(0))
        for closer in BACKTICK_RUN_RE.finditer(line, opener.end()):
            if len(closer.group(0)) != opener_length:
                continue
            spans.append((line[opener.end() : closer.start()], opener.start(), closer.end()))
            cursor = closer.end()
            break
        else:
            break
    return spans


def _mask_code_spans(line: str) -> tuple[list[str], str]:
    spans = _code_spans(line)
    masked = list(line)
    for _, start, end in spans:
        masked[start:end] = " " * (end - start)
    return [content for content, _, _ in spans], "".join(masked)


def _iter_inline_link_targets(line: str):
    for match in INLINE_LINK_START_RE.finditer(line):
        index = match.end()
        depth = 1
        escaped = False
        while index < len(line):
            character = line[index]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    yield line[match.end() : index], match.start()
                    break
            index += 1


def _reference_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def _validate_markdown_target(
    raw_target: str,
    markdown_file: Path,
    line_number: int,
    skill_root: Path,
    findings: list[Finding],
) -> None:
    parsed_target = _markdown_link_target(raw_target)
    if parsed_target is None:
        return
    target, is_absolute = parsed_target
    if is_absolute:
        findings.append(
            Finding(
                "WARNING",
                f"absolute local Markdown link is not portable: {target}",
                markdown_file,
                line_number,
            )
        )
        return

    resolved = (markdown_file.parent / target).resolve()
    if not _is_within(resolved, skill_root):
        findings.append(
            Finding(
                "ERROR",
                f"local Markdown link escapes the Skill: {target}",
                markdown_file,
                line_number,
            )
        )
    elif not resolved.exists():
        findings.append(
            Finding(
                "ERROR",
                f"local Markdown link does not exist: {target}",
                markdown_file,
                line_number,
            )
        )


def _validate_resource_target(
    target: str,
    markdown_file: Path,
    line_number: int,
    skill_root: Path,
    findings: list[Finding],
) -> None:
    if target.endswith("/"):
        return
    resolved = (skill_root / target).resolve()
    if not _is_within(resolved, skill_root):
        findings.append(
            Finding(
                "ERROR",
                f"referenced resource escapes the Skill: {target}",
                markdown_file,
                line_number,
            )
        )
    elif not resolved.exists():
        findings.append(
            Finding(
                "ERROR",
                f"referenced resource does not exist: {target}",
                markdown_file,
                line_number,
            )
        )


def _validate_links(skill_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    markdown_files = sorted(
        path
        for path in skill_root.rglob("*.md")
        if path.is_file() and not _is_excluded(path, skill_root)
    )

    for markdown_file in markdown_files:
        if not _is_within(markdown_file, skill_root):
            findings.append(
                Finding(
                    "ERROR",
                    "Markdown file resolves outside the Skill",
                    markdown_file,
                )
            )
            continue
        text = _read_text(markdown_file, findings)
        if text is None:
            continue
        markdown_lines = list(_iter_markdown_lines(text))
        definitions: dict[str, tuple[str, int]] = {}

        for line_number, line in markdown_lines:
            _, prose = _mask_code_spans(line)
            definition_match = REFERENCE_DEFINITION_RE.match(prose)
            if definition_match:
                label = _reference_label(definition_match.group(1))
                definitions[label] = (definition_match.group(2), line_number)
                _validate_markdown_target(
                    definition_match.group(2),
                    markdown_file,
                    line_number,
                    skill_root,
                    findings,
                )

        for line_number, line in markdown_lines:
            code_spans, prose = _mask_code_spans(line)
            for code in code_spans:
                if INLINE_LINK_START_RE.search(code):
                    continue
                for resource_match in RESOURCE_TOKEN_RE.finditer(code):
                    _validate_resource_target(
                        resource_match.group(1),
                        markdown_file,
                        line_number,
                        skill_root,
                        findings,
                    )

            for raw_target, _ in _iter_inline_link_targets(prose):
                _validate_markdown_target(
                    raw_target,
                    markdown_file,
                    line_number,
                    skill_root,
                    findings,
                )

            if REFERENCE_DEFINITION_RE.match(prose):
                continue
            for reference_match in REFERENCE_LINK_RE.finditer(prose):
                label = reference_match.group(2) or reference_match.group(1)
                normalized_label = _reference_label(label)
                if normalized_label not in definitions:
                    findings.append(
                        Finding(
                            "ERROR",
                            f"reference-style Markdown link is undefined: {label}",
                            markdown_file,
                            line_number,
                        )
                    )

    return findings


def validate_skill(skill_directory: str | Path) -> list[Finding]:
    skill_root = Path(skill_directory).expanduser().resolve()
    findings: list[Finding] = []

    if not skill_root.exists():
        return [Finding("ERROR", "skill directory does not exist", skill_root)]
    if not skill_root.is_dir():
        return [Finding("ERROR", "skill path is not a directory", skill_root)]

    skill_md = skill_root / "SKILL.md"
    if not skill_md.is_file():
        case_variants = [
            path.name
            for path in skill_root.iterdir()
            if path.is_file() and path.name.lower() == "skill.md"
        ]
        detail = (
            f"; found wrong-case file(s): {', '.join(sorted(case_variants))}"
            if case_variants
            else ""
        )
        return [
            Finding("ERROR", f"root SKILL.md is required{detail}", skill_root)
        ]

    findings.extend(_validate_symlinks(skill_root))
    if not _is_within(skill_md, skill_root):
        return findings

    nested_skill_files = sorted(
        path
        for path in skill_root.rglob("SKILL.md")
        if path != skill_md and not _is_excluded(path, skill_root)
    )
    for nested in nested_skill_files:
        findings.append(
            Finding(
                "ERROR",
                "nested SKILL.md found; supporting material must use another filename",
                nested,
            )
        )

    content = _read_text(skill_md, findings)
    if content is None:
        return findings

    frontmatter, body = _parse_frontmatter(content, skill_md, findings)
    if frontmatter is not None:
        findings.extend(_validate_frontmatter(frontmatter, skill_root, skill_md))

    if not body.strip():
        findings.append(Finding("ERROR", "SKILL.md body must not be empty", skill_md))
    else:
        findings.extend(_validate_placeholders(body, skill_md))

    line_count = len(content.splitlines())
    if line_count > MAX_SKILL_LINES:
        findings.append(
            Finding(
                "WARNING",
                f"SKILL.md has {line_count} lines; consider progressive disclosure above {MAX_SKILL_LINES}",
                skill_md,
            )
        )

    for root_file in sorted(path for path in skill_root.iterdir() if path.is_file()):
        if root_file.name.lower() in AUXILIARY_DOCUMENTS:
            findings.append(
                Finding(
                    "WARNING",
                    f"auxiliary document is usually unnecessary inside a Skill: {root_file.name}",
                    root_file,
                )
            )

    for directory_name in RESOURCE_DIRECTORIES:
        resource_dir = skill_root / directory_name
        if resource_dir.is_symlink() and not _is_within(resource_dir, skill_root):
            continue
        if resource_dir.is_dir() and not any(
            path.is_file() and not _is_excluded(path, skill_root)
            for path in resource_dir.rglob("*")
        ):
            findings.append(
                Finding(
                    "WARNING",
                    f"empty resource directory: {directory_name}/",
                    resource_dir,
                )
            )

    findings.extend(_validate_links(skill_root))
    return findings


def _display_path(path: Path | None, skill_root: Path) -> str:
    if path is None:
        return "."
    try:
        return str(path.resolve().relative_to(skill_root)) or "."
    except ValueError:
        return str(path)


def print_findings(findings: list[Finding], skill_root: Path) -> None:
    ordering = {"ERROR": 0, "WARNING": 1}
    for finding in sorted(
        findings,
        key=lambda item: (
            ordering.get(item.level, 2),
            _display_path(item.path, skill_root),
            item.line or 0,
            item.message,
        ),
    ):
        location = _display_path(finding.path, skill_root)
        if finding.line is not None:
            location = f"{location}:{finding.line}"
        print(f"{finding.level}: {location}: {finding.message}")

    errors = sum(finding.level == "ERROR" for finding in findings)
    warnings = sum(finding.level == "WARNING" for finding in findings)
    print(f"Validation complete: {errors} error(s), {warnings} warning(s)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_directory", help="directory containing SKILL.md")
    args = parser.parse_args(argv)

    skill_root = Path(args.skill_directory).expanduser().resolve()
    findings = validate_skill(skill_root)
    print_findings(findings, skill_root)
    return 1 if any(finding.level == "ERROR" for finding in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
