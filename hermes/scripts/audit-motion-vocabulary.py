#!/usr/bin/env python3
"""Read-only audit of the shared motion-vocabulary skill.

The skill (agents/curated/motion-vocabulary) keeps names in references/*.md
(Name, Feel, For, Looks like, The tell) and how each entry is built per
medium in references/<medium>/*.md (video, and web when present). SKILL.md
routes to every file. This audit checks what editing can silently break:

- every table row has as many cells as its header;
- SKILL.md links every reference file and nothing that is missing;
- size limits: core names under 60 KB, other names under 45 KB, video builds
  under 25 KB, web builds under 48 KB (each file is read whole for one
  decision, and every authored plan reads the core);
- every "vs `name`" and "core: `name`" reference names an existing entry;
- The tell stays descriptive: no digits outside backticks, no caution or
  advice phrasing (the vocabulary is rule-free);
- every medium row names an entry of the same area's names file, and motion
  entries (tables with a Feel column) missing a video row are reported;
- video builds stay seekable: no Math.random, live observers, event
  listeners or per-frame lerp (the core's older builds are exempt);
- with --source, no row shares an eight-word run with the supplied source
  prose (names may be borrowed, wording may not).

Usage:
    audit-motion-vocabulary.py [--root REPO] [--source FILE ...] [--json]

Exit codes: 0 no errors (warnings permitted), 1 errors found,
2 invalid invocation (missing vocabulary under --root, or a missing --source).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path("agents/curated/motion-vocabulary")
CORE = "core.md"
MEDIA = ("video", "web")
LIMITS = {"core": 60_000, "names": 45_000, "video": 25_000, "web": 48_000}
FLASH = "never more than 3 flashes in any one second, and no saturated red full-frame flash"
CAUTION = re.compile(
    r"\btoo (?:deep|short|long|fast|slow|many|wide|much|few|big|small|strong)\b|\bsuit(?:s|ed)?\b|"
    r"\bkept for\b|\bsparing|\bhard to follow|\bfeels? (?:restless|drowsy|laggy)|\btires\b|"
    r"\blooks broken|\bwreck|\bhurts?\b|\bloses? track|\bforgotten default|\bunless chosen|"
    r"\bneeds a rule|\brather than on every|\bon frequent interactions|\bsense something wrong|"
    r"\b(?:should|avoid|must|make sure|caution|best practice)\b", re.I)
LIVE = re.compile(r"Math\.random|IntersectionObserver|addEventListener|requestAnimationFrame|\blerp\b|"
                  r"\bonscroll\b|:hover\b", re.I)
DIMENSION = re.compile(r"\b\d(?:\.\d)?D\b")
REF = re.compile(r"\b(?:vs|core:) `([^`]+)`")
LINK = re.compile(r"\]\(references/([a-z-]+(?:/[a-z-]+)?\.md)\)")


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split(" | ")]


def english(name: str) -> str:
    return name.split("（")[0].strip()


def tables(text: str):
    """Yield (line_no, header_cells, row_cells) for every table row."""
    header = None
    for no, line in enumerate(text.splitlines(), 1):
        if not line.startswith("|"):
            header = None
            continue
        c = cells(line)
        if header is None:
            header = c
            continue
        if all(re.fullmatch(r":?-+:?", x) for x in c):
            continue
        yield no, header, c


def words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split()


def shingles(text: str, n: int = 8) -> set[str]:
    """Runs of n words; runs that are mostly numbers (a shared easing curve) are not wording."""
    w = words(text)
    runs = (w[i:i + n] for i in range(len(w) - n + 1))
    return {" ".join(r) for r in runs if sum(t.isdigit() for t in r) * 2 < n}


def audit(root: Path, sources: list[Path]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    refs = root / SKILL_DIR / "references"
    names = {f.name: f.read_text(encoding="utf-8") for f in sorted(refs.glob("*.md"))}
    media = {f"{m}/{f.name}": f.read_text(encoding="utf-8")
             for m in MEDIA for f in sorted((refs / m).glob("*.md"))}
    every = {**names, **media}

    # entries per names file
    area_entries: dict[str, set[str]] = {}
    motion_entries: dict[str, set[str]] = {}
    entries: dict[str, list[str]] = {}
    for name, text in names.items():
        for _, header, row in tables(text):
            if header[0] in ("Name", "Idea"):
                area_entries.setdefault(name, set()).add(english(row[0]))
                entries.setdefault(english(row[0]), []).append(name)
                if "Feel" in header:
                    motion_entries.setdefault(name, set()).add(english(row[0]))

    for name, text in every.items():
        medium = name.split("/")[0] if "/" in name else None
        for no, header, row in tables(text):
            where = f"{name}:{no}"
            if len(row) != len(header):
                errors.append(f"{where}: {len(row)} cells under a {len(header)}-cell header")
                continue
            if medium is None and "The tell" in header:
                tell = row[header.index("The tell")].replace(FLASH, "")
                bare = DIMENSION.sub("", re.sub(r"`[^`]*`", "", tell))
                if re.search(r"\d", bare):
                    errors.append(f"{where}: digit in The tell of {english(row[0])}")
                if CAUTION.search(tell):
                    errors.append(f"{where}: caution or advice in The tell of {english(row[0])}")
            if medium is not None and header[0] in ("Name", "Idea"):
                area = name.split("/", 1)[1]
                if english(row[0]) not in area_entries.get(area, set()):
                    errors.append(f"{where}: `{english(row[0])}` is not an entry of {area}")
            if medium == "video" and name != f"video/{CORE}" and "Built with" in header:
                if LIVE.search(row[header.index("Built with")]):
                    errors.append(f"{where}: live, non-seekable build in {english(row[0])}")
        for ref in REF.findall(text):
            if ref not in entries:
                errors.append(f"{name}: reference to unknown entry `{ref}`")

    # every motion entry has a row in each medium that covers its area
    for m in MEDIA:
        for area, ents in sorted(motion_entries.items()):
            key = f"{m}/{area}"
            if key not in media:
                continue
            built = {english(r[0]) for _, h, r in tables(media[key]) if h[0] in ("Name", "Idea")}
            missing = sorted(ents - built)
            if missing and m == "video":
                warnings.append(f"{key}: no build for {', '.join(missing[:8])}{' ...' if len(missing) > 8 else ''}")

    # routing from SKILL.md
    skill = (root / SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    linked = set(LINK.findall(skill))
    for missing in sorted(set(every) - linked):
        errors.append(f"SKILL.md does not route references/{missing}")
    for missing in sorted(linked - set(every)):
        errors.append(f"SKILL.md routes to missing references/{missing}")

    # size
    for name, text in every.items():
        kind = name.split("/")[0] if "/" in name else ("core" if name == CORE else "names")
        size = len(text.encode())
        if size >= LIMITS[kind]:
            errors.append(f"{name}: {size} bytes, limit {LIMITS[kind]}")
    for en, where in sorted(entries.items()):
        if len(set(where)) > 1:
            warnings.append(f"entry `{en}` appears in {', '.join(sorted(set(where)))}")

    # source overlap
    if sources:
        source = set().union(*(shingles(p.read_text(encoding="utf-8")) for p in sources))
        for name, text in every.items():
            for no, line in enumerate(text.splitlines(), 1):
                hit = shingles(line) & source
                if hit:
                    errors.append(f"{name}:{no}: shares wording with the source: \"{sorted(hit)[0]}\"")

    return {"names_files": len(names), "medium_files": len(media), "entries": len(entries),
            "errors": errors, "warnings": warnings}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="repository root (default: this checkout)")
    parser.add_argument("--source", type=Path, action="append", default=[],
                        help="text file of third-party source prose to check wording against (repeatable)")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if not (root / SKILL_DIR / "references" / CORE).is_file() or not (root / SKILL_DIR / "SKILL.md").is_file():
        print(f"no motion vocabulary under {root}", file=sys.stderr)
        return 2
    for src in args.source:
        if not src.is_file():
            print(f"no source file {src}", file=sys.stderr)
            return 2
    report = audit(root, args.source)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for e in report["errors"]:
            print(f"ERROR {e}")
        for w in report["warnings"]:
            print(f"WARN  {w}")
        print(f"{report['names_files']} names files, {report['medium_files']} medium files, "
              f"{report['entries']} entries, {len(report['errors'])} errors, {len(report['warnings'])} warnings")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
