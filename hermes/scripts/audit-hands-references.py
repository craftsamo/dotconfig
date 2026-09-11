#!/usr/bin/env python3
"""Read-only audit of Creator hands option-backed reference catalogs.

Scope: managed image-creator/video-creator/audio-creator pipeline
<verb>/<subject>/SKILL.md leaves only. Reuses validate_hands_form's exact
option-backing mapping (style -> styles, theme -> themes, else the field
name; style is always backed, other option fields only when their catalog
dir exists or the field carries a bare `references` marker key - never a
path/glob) and adds what that validator does not: orphan-catalog
candidates, empty-catalog files, missing body links, and - for the
image-creator card family only - a pass through the candidate's own
scripts/card.py (destination()/css_style()) for schema/adapter checks and
create/generate style-option parity.

Importing a candidate's card.py executes that file as trusted repository
Python (module-level code plus the two named function calls); this is not
a sandbox and provides no isolation beyond calling nothing else on it
(never create()/edit()/analyze(), which shell out to agent-browser/
ImageMagick). This tool itself never touches the network or a subprocess.

Usage:
    audit-hands-references.py [--root ROOT] [--leaf REPO/RELATIVE/LEAF] [--json]

Exit codes: 0 no errors (warnings permitted), 1 errors found,
2 invalid invocation (bad --root, or a --leaf that is missing, escapes
--root, or is not a hands <verb>/<subject> leaf directory).
"""

from __future__ import annotations

import sys

# Before importing anything else (including, later, a candidate's own
# card.py via importlib): never write __pycache__/.pyc.
sys.dont_write_bytecode = True

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
# .../hermes/scripts -> hermes -> dotconfig root.
DEFAULT_ROOT = SCRIPT_DIR.parent.parent

HANDS_PROFILES = ("image-creator", "video-creator", "audio-creator")
HANDS_VERBS = ("create", "generate", "edit", "source", "analyze")
HANDS_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# validate_hands_form's exact mapping (validate-profile-skills.py):
# style -> styles, theme -> themes, else the field name itself.
REFERENCE_DIR_MAP = {"style": "styles", "theme": "themes"}
# card.py's own `integer(spec.get("tiles", ...), 1, 4, "tiles")` bound.
CARD_MAX_TILES = 4


class InvalidInvocation(Exception):
    """--root/--leaf points somewhere this audit cannot run against."""


class Findings:
    """Ordered findings list; paths are reported relative to --root when
    possible for a stable, portable report."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self.items: list[dict[str, Any]] = []

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self._root.resolve()).as_posix()
        except (OSError, ValueError):
            return str(path)

    def error(self, code: str, path: Path, message: str) -> None:
        self.items.append(
            {"severity": "error", "code": code, "path": self._relative(path), "message": message}
        )

    def warning(self, code: str, path: Path, message: str) -> None:
        self.items.append(
            {"severity": "warning", "code": code, "path": self._relative(path), "message": message}
        )


# frontmatter / scalar parsing - safe, reports rather than raising


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def load_frontmatter(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Safe YAML frontmatter parse: (data, None) or (None, error message)."""
    text = read_text(path)
    if text is None:
        return None, "unreadable file"
    text = text.lstrip("\ufeff")
    if not text.startswith("---\n"):
        return None, "missing '---' frontmatter fence"
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, "unterminated frontmatter fence"
    try:
        data = yaml.safe_load(text[4:end])
    except yaml.YAMLError as exc:
        return None, f"invalid YAML: {exc}"
    if not isinstance(data, dict):
        return None, "frontmatter must be a mapping"
    return data, None


def hermes_meta(data: dict[str, Any]) -> dict[str, Any]:
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    hermes = metadata.get("hermes")
    return hermes if isinstance(hermes, dict) else {}


def parse_scalar_frontmatter(path: Path) -> tuple[dict[str, Any], list[str]]:
    """Mirror card.py's `destination()` manual reference parse (split on the
    '---' fence, one `key: value` scalar per line, last write wins) but
    return (scalars, duplicate-key names) instead of silently overwriting."""
    text = read_text(path)
    if text is None:
        raise ValueError("unreadable file")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("missing '---' frontmatter fence")
    data: dict[str, Any] = {}
    duplicates: list[str] = []
    for line in parts[1].strip().splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"invalid scalar line: {line!r}")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if key in data:
            duplicates.append(key)
        data[key] = int(value) if value.isdigit() else value
    return data, duplicates


# discovery


def hands_pipeline_dir(root: Path, profile: str) -> Path:
    # Resolved so every caller compares against the same symlink-normalized
    # path (macOS /tmp -> /private/var/... otherwise splits a resolved leaf
    # path from an unresolved pipeline root under relative_to()).
    return (root / "hermes" / "profiles" / profile / "skills" / f"{profile}-pipeline").resolve()


def discover_leaves(root: Path) -> list[tuple[str, Path, Path]]:
    """Every <verb>/<subject>/SKILL.md leaf across all hands pipelines below
    --root. Returns (profile, pipeline_dir, leaf_path)."""
    leaves: list[tuple[str, Path, Path]] = []
    for profile in HANDS_PROFILES:
        pipeline_dir = hands_pipeline_dir(root, profile)
        if not pipeline_dir.is_dir():
            continue
        for path in sorted(pipeline_dir.rglob("SKILL.md")):
            rel = path.relative_to(pipeline_dir)
            if len(rel.parts) != 3 or rel.parts[0] not in HANDS_VERBS:
                continue
            leaves.append((profile, pipeline_dir, path))
    return leaves


def classify_leaf(root: Path, leaf_dir: Path) -> tuple[str, Path, str, str]:
    """(profile, pipeline_dir, verb, subject) for a <verb>/<subject> leaf
    directory, or raise InvalidInvocation when it names no such leaf."""
    resolved = leaf_dir.resolve()
    for profile in HANDS_PROFILES:
        pipeline_dir = hands_pipeline_dir(root, profile)
        try:
            rel = resolved.relative_to(pipeline_dir)
        except (OSError, ValueError):
            continue
        if len(rel.parts) == 2 and rel.parts[0] in HANDS_VERBS:
            return profile, pipeline_dir, rel.parts[0], rel.parts[1]
    raise InvalidInvocation(
        f"--leaf is not a hands <verb>/<subject> leaf directory: {leaf_dir}"
    )


def resolve_leaf(root: Path, leaf_arg: str) -> Path:
    candidate = Path(leaf_arg)
    leaf_path = candidate if candidate.is_absolute() else root / leaf_arg
    if not leaf_path.is_dir():
        raise InvalidInvocation(f"--leaf directory does not exist: {leaf_arg}")
    leaf_path = leaf_path.resolve()
    try:
        leaf_path.relative_to(root.resolve())
    except (OSError, ValueError):
        raise InvalidInvocation(f"--leaf directory is outside --root: {leaf_arg}")
    if not (leaf_path / "SKILL.md").is_file():
        raise InvalidInvocation(f"--leaf directory has no SKILL.md: {leaf_arg}")
    classify_leaf(root, leaf_path)
    return leaf_path


# card family adapter (destination()/css_style() only - see module docstring)


class CardAdapters:
    """Loads each hands pipeline's own scripts/card.py at most once, via
    importlib against the candidate file on disk, and calls nothing beyond
    destination()/css_style()."""

    def __init__(self, findings: Findings) -> None:
        self._findings = findings
        self._cache: dict[Path, Any] = {}

    def get(self, pipeline_dir: Path) -> Any | None:
        if pipeline_dir in self._cache:
            return self._cache[pipeline_dir]
        script = pipeline_dir / "scripts" / "card.py"
        module = None
        if not script.is_file():
            self._findings.error(
                "card-adapter-missing", script,
                "card family leaf audited but scripts/card.py is missing",
            )
        else:
            spec = importlib.util.spec_from_file_location(
                f"_audit_card_adapter_{id(script)}", script
            )
            if spec and spec.loader:
                try:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                except Exception as exc:  # noqa: BLE001 - candidate adapter, report not raise
                    self._findings.error(
                        "card-adapter-load-failed", script, f"import failed: {exc}"
                    )
                    module = None
            else:
                self._findings.error(
                    "card-adapter-load-failed", script, "could not build import spec"
                )
        self._cache[pipeline_dir] = module
        return module


def destination_combinations(
    name: str, scalars: dict[str, Any], backing: Path, findings: Findings
) -> list[dict[str, Any]]:
    """Specs to exercise through the adapter's own destination(). The
    default spec (the reference's own declared tiles/tile, if any) is
    always tested first, so a bad default is never hidden behind a range
    check. x-carousel additionally walks its declared tiles/tile-option
    combinations, capped at card.py's own 1..CARD_MAX_TILES bound; an
    invalid, descending or excess range is a finding, not a silent skip or
    an unbounded loop."""
    combos = [{"destination": name}]
    if name != "x-carousel":
        return combos
    tiles, max_tiles = scalars.get("tiles"), scalars.get("max_tiles")
    options = [o for o in str(scalars.get("tile_options") or "").split("|") if o]
    if not isinstance(tiles, int) or not isinstance(max_tiles, int) or not options:
        findings.error(
            "destination-carousel-range-invalid", backing,
            "x-carousel needs integer tiles/max_tiles and a tile_options list",
        )
        return combos
    if tiles < 1 or max_tiles < tiles:
        findings.error(
            "destination-carousel-range-invalid", backing,
            f"tiles/max_tiles must be ascending and >=1: tiles={tiles} max_tiles={max_tiles}",
        )
        return combos
    if max_tiles > CARD_MAX_TILES:
        findings.error(
            "destination-carousel-range-excess", backing,
            f"max_tiles={max_tiles} exceeds card.py's own 1..{CARD_MAX_TILES} tiles bound",
        )
        return combos
    combos += [
        {"destination": name, "tiles": n, "tile": tile}
        for n in range(tiles, max_tiles + 1)
        for tile in options
    ]
    return combos


def audit_destination_catalog(
    option: str,
    backing: Path,
    pipeline_dir: Path,
    adapters: CardAdapters,
    findings: Findings,
) -> None:
    try:
        scalars, duplicates = parse_scalar_frontmatter(backing)
    except ValueError as exc:
        findings.error("destination-frontmatter-invalid", backing, str(exc))
        return
    for dup in duplicates:
        findings.error(
            "destination-duplicate-scalar-key", backing,
            f"duplicate scalar key {dup!r} (card.py's manual parser silently keeps the last one)",
        )
    for required in ("width", "height", "status"):
        if required not in scalars:
            findings.error(
                "destination-missing-field", backing,
                f"missing required scalar field: {required}",
            )
    has_width = "display_width_css_px" in scalars
    has_gap = "display_gap_css_px" in scalars
    if has_width != has_gap:
        findings.error(
            "destination-unpaired-display-dims", backing,
            "display_width_css_px and display_gap_css_px must be declared together",
        )
    adapter = adapters.get(pipeline_dir)
    if adapter is None:
        return
    for spec in destination_combinations(option, scalars, backing, findings):
        try:
            result = adapter.destination(spec)
        except Exception as exc:  # noqa: BLE001 - candidate adapter, report not raise
            findings.error(
                "destination-adapter-failed", backing,
                f"destination({spec!r}) raised: {exc}",
            )
            continue
        for required in ("width", "height", "status"):
            if required not in result:
                findings.error(
                    "destination-adapter-missing-field", backing,
                    f"destination({spec!r}) result missing {required!r}",
                )


def audit_style_catalog(
    option: str,
    backing: Path,
    leaf_path: Path,
    pipeline_dir: Path,
    adapters: CardAdapters,
    findings: Findings,
) -> None:
    # css_style() always resolves against create/card/references (card.py's
    # module-level REFERENCES constant): generate-card's own-named style
    # options are backdrop prompt prose, not duplicated CSS, so only
    # create-card's options exercise the CSS-fence check.
    if leaf_path.parent.parent.name != "create":
        return
    adapter = adapters.get(pipeline_dir)
    if adapter is None:
        return
    try:
        adapter.css_style({"style": option})
    except Exception as exc:  # noqa: BLE001 - candidate adapter, report not raise
        findings.error("style-css-adapter-failed", backing, f"css_style() raised: {exc}")


def audit_card_style_parity(
    style_options: dict[str, tuple[Path, set[str]]], findings: Findings
) -> None:
    create = style_options.get("create-card")
    generate = style_options.get("generate-card")
    if not create and not generate:
        return
    if not create or not generate:
        # One side is missing (deleted leaf, malformed form, no style
        # options) even though the whole tree was scanned: parity cannot be
        # checked, and staying silent would read the same as a checked
        # pass. Same honest-uncertainty finding as the --leaf-scoped case.
        present_name = "create-card" if create else "generate-card"
        present_path = (create or generate)[0]
        findings.warning(
            "card-style-parity-unverified", present_path,
            f"style option parity not checked: only {present_name} declares a style "
            "catalog; its create/generate counterpart is missing or has no style options",
        )
        return
    create_path, create_set = create
    _generate_path, generate_set = generate
    if create_set and generate_set and create_set != generate_set:
        findings.error(
            "card-style-parity", create_path,
            "create-card/generate-card style options differ: "
            f"{sorted(create_set)} vs {sorted(generate_set)}",
        )


# per-leaf audit


def audit_leaf(
    profile: str,
    pipeline_dir: Path,
    leaf_path: Path,
    adapters: CardAdapters,
    style_options: dict[str, tuple[Path, set[str]]],
    findings: Findings,
) -> None:
    rel = leaf_path.relative_to(pipeline_dir)
    verb, subject = rel.parts[0], rel.parts[1]
    name = f"{verb}-{subject}"
    is_card_family = profile == "image-creator" and subject == "card"

    data, error = load_frontmatter(leaf_path)
    if error is not None:
        findings.error("invalid-frontmatter", leaf_path, error)
        return
    meta = hermes_meta(data)
    form = meta.get("form")
    if not isinstance(form, dict) or not form:
        findings.error(
            "missing-form", leaf_path, "metadata.hermes.form must be a non-empty mapping"
        )
        return
    body_text = read_text(leaf_path) or ""

    for key, field in form.items():
        if not isinstance(field, dict):
            findings.error("invalid-field", leaf_path, f"form field {key!r} must be a mapping")
            continue
        options = field.get("options")
        if options is None:
            continue
        if not isinstance(options, list) or not options:
            findings.error(
                "invalid-options", leaf_path, f"form field {key!r} options must be a non-empty list"
            )
            continue
        # The key becomes a path component below; validate it is a slug
        # BEFORE building any path from it (an arbitrary key such as
        # "../../etc" must never reach the filesystem).
        if not isinstance(key, str) or not HANDS_NAME.match(key.replace("_", "-")):
            findings.error("invalid-field-key", leaf_path, f"form field key must be a slug: {key!r}")
            continue

        reference_dir = REFERENCE_DIR_MAP.get(key, key)
        reference_root = leaf_path.parent / "references" / reference_dir
        # validate_hands_form's exact gate: style is always backed; any
        # other option field is backed only when its catalog directory
        # already exists or the field declares a `references` key (checked
        # for presence only - a bare marker, never a path or glob).
        backed = key == "style" or "references" in field or reference_root.is_dir()
        if not backed:
            continue

        # A leaf may document its whole catalog with one templated pointer
        # (references/styles/<style>.md) instead of a literal link per
        # option; either counts as a real link from the body.
        templated_link = f"references/{reference_dir}/<" in body_text

        declared_files: set[str] = set()
        for option in options:
            if not isinstance(option, str) or not HANDS_NAME.fullmatch(option):
                findings.error(
                    "invalid-option-slug", leaf_path, f"{key} option must be a slug: {option!r}"
                )
                continue
            declared_files.add(f"{option}.md")
            backing = reference_root / f"{option}.md"
            if not backing.is_file():
                findings.error(
                    "missing-backed-option", leaf_path,
                    f"{key} option {option!r} has no references/{reference_dir}/{option}.md",
                )
                continue
            content = read_text(backing)
            if content is None:
                findings.error(
                    "unreadable-backing-file", backing, "could not read backing catalog file"
                )
                continue
            if not content.strip():
                findings.error(
                    "empty-catalog-file", backing, f"{key} option {option!r} backing file is empty"
                )
            rel_link = backing.relative_to(leaf_path.parent).as_posix()
            if not templated_link and f"]({rel_link})" not in body_text:
                findings.warning(
                    "missing-body-link", leaf_path,
                    f"{key} option {option!r} backing file is not linked from the leaf body: {rel_link}",
                )
            if is_card_family and key == "destination":
                audit_destination_catalog(option, backing, pipeline_dir, adapters, findings)
            elif is_card_family and key == "style":
                audit_style_catalog(option, backing, leaf_path, pipeline_dir, adapters, findings)

        # Orphan candidates: extra files in a recognized, option-backed
        # catalog directory that no declared option names. A file elsewhere
        # under references/ (e.g. a shared spec.md, not inside a catalog
        # subdirectory) is never inspected here. Not deletion permission -
        # an orphan may still be a linked support doc read from elsewhere.
        if reference_root.is_dir():
            for entry in sorted(reference_root.glob("*.md")):
                if entry.name not in declared_files:
                    findings.warning(
                        "orphan-catalog-candidate", entry,
                        f"file in references/{reference_dir}/ is not a declared {key} option; "
                        "may be a linked support doc, not deletion permission",
                    )

        if is_card_family and key == "style":
            style_options[name] = (leaf_path, {o for o in options if isinstance(o, str)})


# orchestration


def audit(root: Path, leaf_arg: str | None) -> Findings:
    findings = Findings(root)
    adapters = CardAdapters(findings)
    style_options: dict[str, tuple[Path, set[str]]] = {}

    if leaf_arg is not None:
        leaf_dir = resolve_leaf(root, leaf_arg)
        profile, pipeline_dir, _verb, _subject = classify_leaf(root, leaf_dir)
        targets = [(profile, pipeline_dir, leaf_dir / "SKILL.md")]
    else:
        targets = discover_leaves(root)
        if not targets:
            # A wrong or empty --root (e.g. one level too deep, already
            # inside hermes/) otherwise silently reports zero findings and
            # exits 0, indistinguishable from a genuinely clean audit.
            raise InvalidInvocation(
                f"no managed hands leaf targets found under --root: {root}"
            )

    for profile, pipeline_dir, leaf_path in targets:
        audit_leaf(profile, pipeline_dir, leaf_path, adapters, style_options, findings)

    if leaf_arg is None:
        audit_card_style_parity(style_options, findings)
    elif style_options:
        # The scoped leaf carries a style catalog but its create/generate
        # counterpart is out of scope: say so explicitly rather than let a
        # clean report imply parity was checked and passed.
        only_name, (only_path, _options) = next(iter(style_options.items()))
        findings.warning(
            "card-style-parity-unverified", only_path,
            f"style option parity with create-card/generate-card not checked: "
            f"only {only_name} is in --leaf scope",
        )

    return findings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT,
        help="dotconfig root (default: derived from this script's own location)",
    )
    parser.add_argument(
        "--leaf",
        help="repo-relative <verb>/<subject> hands leaf directory to scope the audit to",
    )
    parser.add_argument("--json", action="store_true", help="emit a JSON findings report instead of text")
    return parser


def render_text(findings: Findings, root: Path, leaf: str | None) -> str:
    lines = [f"root: {root}"]
    if leaf:
        lines.append(f"leaf: {leaf}")
    if not findings.items:
        lines.append("no findings")
    for item in findings.items:
        lines.append(f"{item['severity']}: {item['code']}: {item['path']}: {item['message']}")
    errors = sum(1 for i in findings.items if i["severity"] == "error")
    warnings = sum(1 for i in findings.items if i["severity"] == "warning")
    lines.append(f"totals: {errors} error(s), {warnings} warning(s)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"audit-hands-references: --root is not a directory: {root}", file=sys.stderr)
        return 2

    try:
        findings = audit(root, args.leaf)
    except InvalidInvocation as exc:
        print(f"audit-hands-references: {exc}", file=sys.stderr)
        return 2

    errors = sum(1 for item in findings.items if item["severity"] == "error")
    warnings = sum(1 for item in findings.items if item["severity"] == "warning")

    if args.json:
        payload = {
            "root": str(root),
            "leaf": args.leaf,
            "findings": findings.items,
            "totals": {"error": errors, "warning": warnings, "count": len(findings.items)},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(findings, root, args.leaf))

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
