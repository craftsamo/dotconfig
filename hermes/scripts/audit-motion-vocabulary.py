#!/usr/bin/env python3
"""Read-only audit of the motion vocabulary and the web motion catalog.

The video-creator kernel's motion vocabulary is one core file that routes to
neighbouring files (references/motion-vocabulary*.md). This audit checks what
editing can silently break:

- every table row has as many cells as its header;
- the core's "More names" table and the neighbouring files match both ways;
- the core stays under 70 KB and each neighbour under 48 KB (every authored
  plan reads the core, each neighbour is read whole for one decision);
- every "vs `name`" and "core: `name`" reference names an existing entry;
- The tell stays descriptive: no digits outside backticks, no caution or
  advice phrasing (the vocabulary is rule-free);
- builds in the neighbouring files stay seekable: no Math.random, live
  observers, event listeners or per-frame lerp;
- with --source, no row shares an 8-word run with the supplied source prose
  (names may be borrowed, wording may not);
- with a web motion catalog present, every web entry names an existing
  vocabulary entry and its Japanese aliases appear on that entry.

Usage:
    audit-motion-vocabulary.py [--root REPO] [--web DIR] [--source FILE ...] [--json]

Exit codes: 0 no errors (warnings permitted), 1 errors found,
2 invalid invocation (missing --root vocabulary, --web or --source path).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VOCAB_DIR = Path("hermes/profiles/video-creator/skills/video-creator-pipeline/references")
WEB_DIR = Path("agents/curated/web-motion-catalog/references")
CORE = "motion-vocabulary.md"
CORE_LIMIT, NEIGHBOUR_LIMIT = 70_000, 48_000
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
REF = re.compile(r"(?:vs|core:) `([^`]+)`")
ROUTE = re.compile(r'file_path="references/(motion-vocabulary-[a-z-]+\.md)"')


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split(" | ")]


def english(name: str) -> str:
    return name.split("（")[0].strip()


def aliases(name: str) -> set[str]:
    m = re.search(r"（(.*)）", name)
    return {a.strip() for a in m.group(1).split("、")} if m else set()


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
    w = words(text)
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def audit(root: Path, web: Path | None, sources: list[Path]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    vdir = root / VOCAB_DIR
    files = sorted(vdir.glob("motion-vocabulary*.md"))
    texts = {f.name: f.read_text(encoding="utf-8") for f in files}
    core = texts.get(CORE, "")

    # entries
    entries: dict[str, list[tuple[str, str]]] = {}
    for name, text in texts.items():
        for no, header, row in tables(text):
            if header[0] in ("Name", "Idea"):
                entries.setdefault(english(row[0]), []).append((name, row[0]))

    # shape, tells, builds
    for name, text in texts.items():
        for no, header, row in tables(text):
            where = f"{name}:{no}"
            if len(row) != len(header):
                errors.append(f"{where}: {len(row)} cells under a {len(header)}-cell header")
                continue
            if "The tell" in header:
                tell = row[header.index("The tell")].replace(FLASH, "")
                bare = DIMENSION.sub("", re.sub(r"`[^`]*`", "", tell))
                if re.search(r"\d", bare):
                    errors.append(f"{where}: digit in The tell of {english(row[0])}")
                if CAUTION.search(tell):
                    errors.append(f"{where}: caution or advice in The tell of {english(row[0])}")
            if name != CORE and "Built with" in header:
                if LIVE.search(row[header.index("Built with")]):
                    errors.append(f"{where}: live, non-seekable build in {english(row[0])}")
        for ref in REF.findall(text):
            if ref not in entries:
                errors.append(f"{name}: reference to unknown entry `{ref}`")

    # routing and size
    routed = set(ROUTE.findall(core))
    neighbours = {n for n in texts if n != CORE}
    for missing in sorted(neighbours - routed):
        errors.append(f"{CORE}: More names does not route {missing}")
    for missing in sorted(routed - neighbours):
        errors.append(f"{CORE}: routes to missing {missing}")
    for name, text in texts.items():
        limit = CORE_LIMIT if name == CORE else NEIGHBOUR_LIMIT
        if len(text.encode()) >= limit:
            errors.append(f"{name}: {len(text.encode())} bytes, limit {limit}")
    for en, where in sorted(entries.items()):
        if len({f for f, _ in where}) > 1:
            warnings.append(f"entry `{en}` appears in {', '.join(sorted({f for f, _ in where}))}")

    # source overlap
    if sources:
        source = set().union(*(shingles(p.read_text(encoding="utf-8")) for p in sources))
        for name, text in texts.items():
            for no, line in enumerate(text.splitlines(), 1):
                hit = shingles(line) & source
                if hit:
                    errors.append(f"{name}:{no}: shares wording with the source: \"{sorted(hit)[0]}\"")

    # web catalog sync
    web_entries = 0
    if web is not None:
        for f in sorted(web.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            for no, header, row in tables(text):
                if header[0] != "Name":
                    continue
                web_entries += 1
                where = f"{f.name}:{no}"
                if len(row) != len(header):
                    errors.append(f"web {where}: {len(row)} cells under a {len(header)}-cell header")
                en = english(row[0])
                if en not in entries:
                    errors.append(f"web {where}: `{en}` is not a motion vocabulary entry")
                    continue
                known = set().union(*(aliases(n) for _, n in entries[en]))
                for alias in sorted(aliases(row[0]) - known):
                    errors.append(f"web {where}: alias {alias} of `{en}` is missing from the vocabulary")
                if sources:
                    hit = shingles(" ".join(row)) & source
                    if hit:
                        errors.append(f"web {where}: shares wording with the source: \"{sorted(hit)[0]}\"")

    return {"files": len(texts), "entries": len(entries), "web_entries": web_entries,
            "errors": errors, "warnings": warnings}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2],
                        help="repository root (default: this checkout)")
    parser.add_argument("--web", type=Path, help="web motion catalog references dir "
                        "(default: agents/curated/web-motion-catalog/references when present)")
    parser.add_argument("--source", type=Path, action="append", default=[],
                        help="text file of third-party source prose to check wording against (repeatable)")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if not (root / VOCAB_DIR / CORE).is_file():
        print(f"no motion vocabulary under {root}", file=sys.stderr)
        return 2
    web = args.web
    if web is None and (root / WEB_DIR).is_dir():
        web = root / WEB_DIR
    if web is not None and not web.is_dir():
        print(f"no web catalog at {web}", file=sys.stderr)
        return 2
    for src in args.source:
        if not src.is_file():
            print(f"no source file {src}", file=sys.stderr)
            return 2
    report = audit(root, web, args.source)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for e in report["errors"]:
            print(f"ERROR {e}")
        for w in report["warnings"]:
            print(f"WARN  {w}")
        print(f"{report['files']} files, {report['entries']} entries, {report['web_entries']} web entries, "
              f"{len(report['errors'])} errors, {len(report['warnings'])} warnings")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
