#!/usr/bin/env python3
"""Checks for an official vendor mark sourced by source-icon.

    brand-check.py render <file.svg> [<file.svg> ...]
        Parses each SVG, requires a viewBox, rasterizes it with rsvg-convert
        into a 256 px box (aspect ratio kept) over a mid-grey backdrop and
        counts ink: pixels that differ from the backdrop. A valid SVG can still
        be blank (bad viewBox, white-on-white, zero-size paths); byte size is
        not evidence. Prints one RESULT line per file; exits 1 if any fails.

    brand-check.py provenance --file <delivered> --source-url <url>
        [--archive <vendor.zip> --member <path inside the zip>]
        --terms <text file with the usage-terms summary> --out <provenance.json>
        Proves the delivered file is the vendor's bytes: sha256 of the file
        (and of the archive), the archive's integrity test, and a byte compare
        against the member inside it. Writes provenance.json (never
        overwrites) and prints one RESULT line.

Stdlib only plus rsvg-convert and magick. No network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

BOX = 256
BACKDROP = "#808080"
MIN_INK = 1.0  # percent of the rendered box that must differ from the backdrop


def fail(message: str) -> None:
    print(f"brand-check: {message}", file=sys.stderr)
    raise SystemExit(1)


def tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        fail(f"{name} is not installed")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def render_one(svg: Path) -> dict:
    row = {"file": str(svg), "parses": False, "viewbox": None, "ink_percent": 0.0, "ok": False}
    try:
        root = ET.parse(svg).getroot()
    except (ET.ParseError, OSError) as exc:
        row["error"] = f"does not parse: {exc}"
        return row
    row["parses"] = True
    if not root.tag.endswith("svg"):
        row["error"] = "root element is not <svg>"
        return row
    row["viewbox"] = root.get("viewBox")
    if not row["viewbox"]:
        row["error"] = "no viewBox"
        return row
    with tempfile.TemporaryDirectory(prefix="brand-check-") as temp:
        mark = Path(temp) / "mark.png"
        flat = Path(temp) / "flat.png"
        result = subprocess.run(
            [tool("rsvg-convert"), "--keep-aspect-ratio", "-w", str(BOX), "-h", str(BOX),
             "-f", "png", "-o", str(mark), str(svg)],
            capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        if result.returncode != 0 or not mark.is_file():
            row["error"] = "rsvg-convert failed: " + (result.stderr.strip().splitlines() or ["?"])[-1]
            return row
        subprocess.run(
            [tool("magick"), str(mark), "-background", BACKDROP, "-flatten", "-alpha", "off", str(flat)],
            check=True, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
        # Ink = pixels that differ from a solid backdrop-coloured copy.
        out = subprocess.run(
            [tool("magick"), str(flat), "(", "+clone", "-fill", BACKDROP, "-colorize", "100", ")",
             "-compose", "difference", "-composite", "-colorspace", "gray", "-threshold", "2%",
             "-format", "%[fx:mean*100] %w %h", "info:"],
            check=True, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL).stdout.split()
    row["ink_percent"] = round(float(out[0]), 2)
    row["rendered"] = f"{out[1]}x{out[2]}"
    row["ok"] = row["ink_percent"] >= MIN_INK
    if not row["ok"]:
        row["error"] = f"renders blank ({row['ink_percent']}% ink < {MIN_INK}%)"
    return row


def render(files: list[str]) -> int:
    if not files:
        fail("give at least one .svg")
    rows = [render_one(Path(f)) for f in files]
    for row in rows:
        status = "PASS" if row["ok"] else "FAIL"
        print(f"RESULT: {status} file={row['file']} parses={str(row['parses']).lower()} "
              f"viewbox={row['viewbox'] or 'none'} ink={row['ink_percent']}%"
              + (f" error={row['error']}" if not row["ok"] else ""))
    return 0 if all(r["ok"] for r in rows) else 1


def provenance(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if out.exists():
        fail(f"{out} exists; provenance is never overwritten")
    delivered = Path(args.file)
    if not delivered.is_file():
        fail(f"no such file: {delivered}")
    terms = Path(args.terms)
    if not terms.is_file() or not terms.read_text(encoding="utf-8").strip():
        fail("--terms must name a non-empty summary file")
    record = {
        "file": delivered.name,
        "file_sha256": sha256(delivered),
        "source_url": args.source_url,
        "terms": terms.read_text(encoding="utf-8").strip(),
        "modified": False,
    }
    if args.archive:
        archive = Path(args.archive)
        if not args.member:
            fail("--member is required with --archive")
        if not zipfile.is_zipfile(archive):
            fail(f"not a zip archive: {archive}")
        with zipfile.ZipFile(archive) as bundle:
            bad = bundle.testzip()
            if bad is not None:
                fail(f"archive integrity test failed at {bad}")
            try:
                original = bundle.read(args.member)
            except KeyError:
                fail(f"no member {args.member!r} in {archive.name}")
        if original != delivered.read_bytes():
            fail("delivered file differs from the archive member; the mark was modified")
        record.update(archive=archive.name, archive_sha256=sha256(archive), member=args.member,
                      archive_test="ok", identical_to_member=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RESULT: PASS provenance={out} file_sha256={record['file_sha256']}"
          + (f" archive_sha256={record['archive_sha256']} identical_to_member=true" if args.archive else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("render")
    r.add_argument("files", nargs="+")
    p = sub.add_parser("provenance")
    p.add_argument("--file", required=True)
    p.add_argument("--source-url", required=True)
    p.add_argument("--archive")
    p.add_argument("--member")
    p.add_argument("--terms", required=True)
    p.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    return render(args.files) if args.command == "render" else provenance(args)


if __name__ == "__main__":
    raise SystemExit(main())
