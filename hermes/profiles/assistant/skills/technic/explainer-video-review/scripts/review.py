#!/usr/bin/env python3
"""Helpers for an explainer-video review job (stdlib only).

The findings ledger (``ledger.json``) is the one source of every finding; the
review sheet and the acceptance check of the written report are derived from
it, so nothing is copied by hand.

    review.py script   <captions.txt> <out.txt>       strip "[m:ss] " prefixes
    review.py validate <ledger.json> [--final]        schema; --final also refuses open findings
    review.py import   <ledger.json> <episode> <findings.md> --source NAME
                                                      add a hands report's `m:ss | aspect | ... ` lines
    review.py listen   <ledger.json> [--terms FILE]   add ear-check candidates from each caption file
    review.py sheet    <ledger.json> <out.md>         the user's review sheet
    review.py check    <ledger.json> <report>         does the report carry every kept finding?

``--terms`` names extra words to listen for: one term per line, or
``<episode label><TAB><term>`` for one episode only.

Ledger shape::

    {"job": "...", "language": "<captions' BCP 47 tag>", "sheet_language": "<the user's tag>",
     "episodes": [{"label": "#1", "title": "...", "captions": "/abs/captions.txt",
                   "language": "<optional per-episode override>",
                   "checked": ["text", "voice", "content", "thumbnail"]}],
     "findings": [{"id": "F001", "episode": "#1" | "all", "at": "1:15" | "0:50-0:54" | "",
                   "aspect": "text|voice|content|thumbnail|portrait|overall",
                   "problem": "...", "evidence": "...", "certainty": "certain|confirm",
                   "quotes": ["verbatim words the report must keep"],
                   "source": "video-creator|audio-creator|image-creator|searcher|researcher|user|assistant",
                   "status": "open|keep|drop"}],
     "listen": [{"episode": "#1", "at": "0:12", "term": "...", "result": null}]}

``checked`` lists the aspects whose check actually finished for that episode;
the sheet names the rest as unchecked, and ``--final`` requires the list.
``check`` finds each episode's section by the first line that starts with its
label (after an optional Markdown heading or list marker), so the report puts
every episode under a line beginning with its label.

Language: ``sheet_language`` picks the sheet's wording from ``SHEET_TEXT``
(English when absent or unknown). ``language`` (per episode, else the
ledger's) picks how ``listen`` finds names and numbers in caption lines from
``TERM_PATTERNS``; a language without its own entry gets numbers, acronyms and
capitalised words only, so add its names with ``--terms``. Adding a language
is one entry in each table.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

ASPECTS = ("text", "voice", "content", "thumbnail", "portrait", "overall")
CERTAINTIES = ("certain", "confirm")
STATUSES = ("open", "keep", "drop")
SOURCES = ("video-creator", "audio-creator", "image-creator", "searcher", "researcher", "user", "assistant")
ALL = "all"

TIME = re.compile(r"(?<![\d:])(?:(\d{1,2}):)?(\d{1,3}):(\d{2})(?![\d:])")
CAPTION_LINE = re.compile(r"^\[(\d{1,3}(?::\d{2}){1,2})\]\s?(.*)$")
LINE_PREFIX = r"^[ \t]*(?:#{1,6}[ \t]+|[-*+][ \t]+|\d+[.)][ \t]+|[^\w\s#][ \t]*)?"
REVIEWED = ("text", "voice", "content", "thumbnail", "portrait")

# The review sheet's wording per reader language; English is the fallback.
SHEET_TEXT = {
    "en": {
        "aspects": {"text": "Text", "voice": "Voice", "content": "Content", "thumbnail": "Thumbnail",
                    "portrait": "Portrait", "overall": "Overall"},
        "title": "Review sheet", "overall": "Overall",
        "intro": "Certain = reproduced on our side. Tick what needs your eyes or ears and send back the result.",
        "certain": "Certain", "confirm": "Needs your eyes or ears", "listen": "Listen for",
        "checked": "Checked: {done} / Not checked: {todo}", "unrecorded": "Checked aspects: not recorded",
        "none": "none", "join": ", ", "clean_checked": "No findings in the checked aspects",
        "clean_unrecorded": "No findings (checked aspects not recorded)", "evidence": " (evidence: {})",
        "colon": ": ", "gap": "  ",
    },
    "ja": {
        "aspects": {"text": "字", "voice": "声", "content": "中身", "thumbnail": "サムネ",
                    "portrait": "似顔絵", "overall": "全体"},
        "title": "確認用シート", "overall": "全体",
        "intro": "確実＝こちらで確かめ済み。要確認・耳で聞く所は、チェックを付けて結果を返してください。",
        "certain": "確実", "confirm": "要確認（目か耳で確かめる）", "listen": "耳で聞く所",
        "checked": "確認した観点：{done}　／　未確認：{todo}", "unrecorded": "確認した観点：未記録",
        "none": "なし", "join": "・", "clean_checked": "確認した観点では指摘なし",
        "clean_unrecorded": "指摘なし（確認範囲は未記録）", "evidence": "（根拠: {}）",
        "colon": "：", "gap": "　",
    },
}

# How `listen` finds names and numbers per caption language.
NUMBER = re.compile(r"[0-9][0-9,.]*(?:\s?%)?")
ACRONYM = re.compile(r"\b[A-Z][A-Z0-9&]{1,}\b")
CAPITALISED = re.compile(r"\b[A-Z][\w'’\-]*(?:\s+[A-Z][\w'’\-]*)*")
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9&.+\-]*[A-Za-z0-9]|[A-Za-z]")
JA_NUMBER = re.compile(r"約?[0-9][0-9,.]*\s*(?:[万億兆]+)?\s*(?:ドル|円|倍|年|月|日|位|件|台|人|社|%|％)?")
JA_KANJI_NUMBER = re.compile(r"約?[〇一二三四五六七八九十百千万億兆・]{2,}(?:ドル|円|倍|年|件|台|人|社)?")
JA_KATAKANA_NAME = re.compile(r"[ァ-ヴー]+(?:・[ァ-ヴー]+)+|[ァ-ヴー]{6,}")
TERM_PATTERNS = {
    # Japanese captions: Latin-script words are the foreign terms; numbers carry their units.
    "ja": (LATIN, JA_NUMBER, JA_KANJI_NUMBER, JA_KATAKANA_NAME),
}
DEFAULT_TERM_PATTERNS = (NUMBER, ACRONYM, CAPITALISED)


def primary(tag: str | None) -> str:
    return str(tag or "").strip().lower().replace("_", "-").split("-")[0]


def sheet_text(data: dict) -> dict:
    return SHEET_TEXT.get(primary(data.get("sheet_language")), SHEET_TEXT["en"])


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(2)


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def seconds(token: str) -> int | None:
    match = TIME.fullmatch(nfkc(token).strip())
    if not match:
        return None
    hours, minutes, secs = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(secs)


def times_in(text: str) -> list[int]:
    out = []
    for match in TIME.finditer(nfkc(text)):
        hours, minutes, secs = match.groups()
        out.append(int(hours or 0) * 3600 + int(minutes) * 60 + int(secs))
    return out


def clock(value: int) -> str:
    hours, rest = divmod(value, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def load(path: str) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read ledger {path}: {exc}")
    if not isinstance(data, dict):
        fail("ledger must be a JSON object")
    data.setdefault("episodes", [])
    data.setdefault("findings", [])
    data.setdefault("listen", [])
    return data


def save(path: str, data: dict) -> None:
    target = Path(path)
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
    fd, temp = tempfile.mkstemp(prefix=".ledger-", suffix=".json", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(temp, mode)
        os.replace(temp, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp)
        raise


def problems(data: dict, final: bool) -> list[str]:
    errors = []
    labels = []
    for index, episode in enumerate(data["episodes"]):
        label = episode.get("label") if isinstance(episode, dict) else None
        if not isinstance(label, str) or not label.strip():
            errors.append(f"episodes[{index}] needs a label")
            continue
        if label in labels:
            errors.append(f"duplicate episode label {label}")
        labels.append(label)
        checked = episode.get("checked")
        if checked is not None and (not isinstance(checked, list) or not set(checked) <= set(REVIEWED)):
            errors.append(f"episode {label}: checked must list aspects from {', '.join(REVIEWED)}")
        elif final and checked is None:
            errors.append(f"episode {label}: checked is not recorded")
    known = set(labels) | {ALL}
    ids = set()
    for index, finding in enumerate(data["findings"]):
        where = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{where} must be an object")
            continue
        fid = finding.get("id")
        if not isinstance(fid, str) or not fid:
            errors.append(f"{where} needs an id")
        elif fid in ids:
            errors.append(f"duplicate finding id {fid}")
        else:
            ids.add(fid)
            where = fid
        if finding.get("episode") not in known:
            errors.append(f"{where}: unknown episode {finding.get('episode')!r}")
        if finding.get("aspect") not in ASPECTS:
            errors.append(f"{where}: aspect must be one of {', '.join(ASPECTS)}")
        if finding.get("certainty") not in CERTAINTIES:
            errors.append(f"{where}: certainty must be certain or confirm")
        if finding.get("status", "open") not in STATUSES:
            errors.append(f"{where}: status must be one of {', '.join(STATUSES)}")
        if finding.get("source") not in SOURCES:
            errors.append(f"{where}: source must be one of {', '.join(SOURCES)}")
        if not str(finding.get("problem", "")).strip():
            errors.append(f"{where}: problem is empty")
        at = str(finding.get("at") or "")
        if at and not times_in(at):
            errors.append(f"{where}: at {at!r} holds no m:ss time")
        quotes = finding.get("quotes", [])
        if not isinstance(quotes, list) or not all(isinstance(q, str) and q for q in quotes):
            errors.append(f"{where}: quotes must be a list of nonempty strings")
        if final and finding.get("status", "open") == "open":
            errors.append(f"{where}: still open (settle keep or drop before the report)")
    for index, item in enumerate(data["listen"]):
        if (not isinstance(item, dict) or item.get("episode") not in known
                or seconds(str(item.get("at", ""))) is None
                or not isinstance(item.get("term"), str) or not item["term"].strip()):
            errors.append(f"listen[{index}] needs a known episode, an m:ss time and a term")
    return errors


def cmd_validate(args) -> int:
    errors = problems(load(args.ledger), args.final)
    for error in errors:
        print(error)
    print(json.dumps({"ok": not errors, "errors": len(errors)}))
    return 0 if not errors else 1


def cmd_script(args) -> int:
    lines = []
    for raw in Path(args.captions).read_text(encoding="utf-8").splitlines():
        match = CAPTION_LINE.match(raw.strip())
        text = match.group(2) if match else raw.strip()
        if text:
            lines.append(text)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "lines": len(lines), "out": args.out}, ensure_ascii=False))
    return 0


# Quotation marks a hands report may put around verbatim on-screen words, in
# whatever language the video uses; each pair's inner text becomes a quote the
# written report must keep. Add a pair here for another writing system.
QUOTE_PAIRS = (("\"", "\""), ("“", "”"), ("„", "“"), ("«", "»"), ("「", "」"), ("『", "』"))
QUOTE = re.compile("|".join(
    f"{re.escape(open_)}([^{re.escape(open_ + close)}\\n]+){re.escape(close)}" for open_, close in QUOTE_PAIRS
))


def quotes_in(text: str) -> list[str]:
    return [next(group for group in match.groups() if group) for match in QUOTE.finditer(text)]


# A blank/separator row, or a header row whose second cell names the aspect column.
HEADER_OR_RULE = re.compile(r"^[\s|:\-]*$|^\|?[^|]*\|\s*aspect\s*\|", re.I)


def report_rows(path: str, base: str | None = None) -> tuple[list[dict], list[str]]:
    """``m:ss | aspect | problem | evidence | certain|confirm`` lines. Markdown
    table pipes, a header and separator rows are ignored; a stray ``|`` inside
    the problem is kept in it. Any other line that does not parse is returned
    so the caller sees what was not imported."""
    rows, skipped = [], []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if "|" not in line or HEADER_OR_RULE.match(line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            skipped.append(line)
            continue
        at, aspect = cells[0], cells[1].lower().strip(" .")
        evidence, certainty = cells[-2], cells[-1].lower().strip(" .")
        problem = " | ".join(cells[2:-2]).strip()
        at = "" if at in ("", "-", "—") else at
        if aspect not in ASPECTS or certainty not in CERTAINTIES or not problem or (at and not times_in(at)):
            skipped.append(line)
            continue
        looks_like_path = "/" in evidence or bool(Path(evidence).suffix)
        if base and looks_like_path and not Path(evidence).is_absolute():
            evidence = str(Path(base) / evidence)
        rows.append({"at": at, "aspect": aspect, "problem": problem, "evidence": evidence,
                     "certainty": certainty, "quotes": quotes_in(problem)})
    return rows, skipped


def cmd_import(args) -> int:
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    if args.episode not in {e["label"] for e in data["episodes"]} | {ALL}:
        fail(f"unknown episode {args.episode!r}")
    if args.source not in SOURCES:
        fail(f"source must be one of {', '.join(SOURCES)}")
    base = args.base if args.base is not None else str(Path(args.findings).resolve().parent)
    rows, skipped = report_rows(args.findings, base)
    numbers = [int(m.group(1)) for f in data["findings"] if (m := re.fullmatch(r"F(\d+)", str(f.get("id"))))]
    next_number = max(numbers, default=0) + 1
    seen = {(f["episode"], f.get("at", ""), f["problem"]) for f in data["findings"]}
    added = []
    for row in rows:
        key = (args.episode, row["at"], row["problem"])
        if key in seen:
            continue
        seen.add(key)
        fid = f"F{next_number:03d}"
        next_number += 1
        data["findings"].append({"id": fid, "episode": args.episode, **row,
                                 "source": args.source, "status": "open"})
        added.append(fid)
    save(args.ledger, data)
    print(json.dumps({"ok": not skipped, "added": added, "not_imported": skipped}, ensure_ascii=False))
    return 0 if not skipped else 1


def caption_lines(path: str) -> list[tuple[str, str]]:
    lines = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        match = CAPTION_LINE.match(raw.strip())
        if match and match.group(2).strip():
            lines.append((match.group(1), match.group(2).strip()))
    return lines


SENTENCE_START = re.compile(r"(?:^|[.!?]\s+)$")


def candidates(text: str, language: str | None = None) -> list[str]:
    patterns = TERM_PATTERNS.get(primary(language), DEFAULT_TERM_PATTERNS)
    found = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            term = match.group(0).strip()
            if pattern is CAPITALISED and SENTENCE_START.search(text[:match.start()]) and " " not in term:
                continue  # a single capitalised word opening a sentence is not a name
            if len(term) >= 2 and term not in found:
                found.append(term)
    return found


def read_terms(path: str | None) -> list[tuple[str | None, str]]:
    if not path:
        return []
    terms = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        episode, sep, term = line.partition("\t")
        terms.append((episode.strip(), term.strip()) if sep else (None, line))
    return terms


def cmd_listen(args) -> int:
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    extra = read_terms(args.terms)
    seen = {(item["episode"], seconds(item["at"]), item["term"]) for item in data["listen"]}
    added = 0
    for episode in data["episodes"]:
        captions = episode.get("captions")
        if not captions:
            continue
        label = episode["label"]
        language = episode.get("language") or data.get("language")
        wanted = [term for scope, term in extra if scope in (None, label)]
        for at, text in caption_lines(captions):
            terms = candidates(text, language) + [term for term in wanted if term in text]
            for term in dict.fromkeys(terms):
                key = (label, seconds(at), term)
                if key in seen:
                    continue
                seen.add(key)
                data["listen"].append({"episode": label, "at": clock(seconds(at)), "term": term, "result": None})
                added += 1
    order = {episode["label"]: index for index, episode in enumerate(data["episodes"])}
    data["listen"].sort(key=lambda item: (order.get(item["episode"], 0), seconds(item["at"]) or 0))
    save(args.ledger, data)
    print(json.dumps({"ok": True, "added": added, "listen": len(data["listen"])}))
    return 0


def first_time(finding: dict) -> int:
    found = times_in(str(finding.get("at") or ""))
    return found[0] if found else -1


def finding_line(finding: dict, box: bool, words: dict) -> str:
    at = str(finding.get("at") or "").strip()
    head = f"{at}{words['gap']}" if at else ""
    evidence = str(finding.get("evidence") or "").strip()
    tail = words["evidence"].format(evidence) if evidence else ""
    prefix = "- [ ] " if box else "- "
    aspect = words["aspects"][finding["aspect"]]
    return f"{prefix}{head}{aspect}{words['colon']}{finding['problem']}{tail} `{finding['id']}`"


def cmd_sheet(args) -> int:
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    words = sheet_text(data)
    live = [f for f in data["findings"] if f.get("status", "open") != "drop"]
    out = [f"# {words['title']} — {data.get('job', '')}".rstrip(" —"), "", words["intro"], ""]
    sections = [(ALL, words["overall"], "", None)] + [
        (e["label"], e["label"], e.get("title", ""), e.get("checked")) for e in data["episodes"]
    ]
    for label, heading, title, checked in sections:
        mine = sorted((f for f in live if f["episode"] == label), key=first_time)
        listen = [item for item in data["listen"] if item["episode"] == label]
        if label == ALL and not mine:
            continue
        out.append(f"## {heading} {title}".rstrip())
        if label != ALL:
            if checked is None:
                out.append(words["unrecorded"])
            else:
                done = words["join"].join(words["aspects"][a] for a in REVIEWED if a in checked) or words["none"]
                todo = words["join"].join(words["aspects"][a] for a in REVIEWED if a not in checked) or words["none"]
                out.append(words["checked"].format(done=done, todo=todo))
        certain = [f for f in mine if f["certainty"] == "certain"]
        confirm = [f for f in mine if f["certainty"] == "confirm"]
        if not mine and not listen:
            out.append("- " + (words["clean_checked"] if checked else words["clean_unrecorded"]))
        if certain:
            out.append(f"### {words['certain']}")
            out.extend(finding_line(f, False, words) for f in certain)
        if confirm:
            out.append(f"### {words['confirm']}")
            out.extend(finding_line(f, True, words) for f in confirm)
        if listen:
            out.append(f"### {words['listen']}")
            for item in listen:
                done = item.get("result")
                mark = "x" if done else " "
                result = f"{words['gap']}→ {done}" if done else ""
                out.append(f"- [{mark}] {item['at']}{words['gap']}{item['term']}{result}")
        out.append("")
    Path(args.out).write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "findings": len(live), "listen": len(data["listen"]), "out": args.out}, ensure_ascii=False))
    return 0


def label_positions(text: str, labels: list[str]) -> dict[str, int]:
    """First line that starts with each label; a mention inside a sentence or an
    overview line naming several episodes does not open that episode's section."""
    def bounded(label: str) -> str:
        name = nfkc(label)
        return re.escape(name) + (r"(?!\d)" if name[-1:].isdigit() else r"(?![0-9A-Za-z])")

    positions = {}
    for label in labels:
        others = [re.compile(bounded(other)) for other in labels if other != label]
        fallback = None
        for match in re.finditer(LINE_PREFIX + bounded(label), text, re.M):
            line_end = text.find("\n", match.end())
            rest = text[match.end():line_end if line_end != -1 else len(text)]
            if not any(other.search(rest) for other in others):
                positions[label] = match.start()
                break
            if fallback is None:
                fallback = match.start()
        else:
            if fallback is not None:
                positions[label] = fallback
    return positions


def cmd_check(args) -> int:
    data = load(args.ledger)
    errors = problems(data, final=True)
    if errors:
        fail("ledger is not final: " + "; ".join(errors))
    report = nfkc(Path(args.report).read_text(encoding="utf-8"))
    kept = [f for f in data["findings"] if f.get("status") == "keep"]
    labels = [e["label"] for e in data["episodes"]]
    positions = label_positions(report, labels)
    starts = sorted(positions.values())

    def section(label: str) -> tuple[int, int]:
        if label == ALL:
            return 0, len(report)
        start = positions[label]
        later = [p for p in starts if p > start]
        return start, later[0] if later else len(report)

    missing_episodes, missing_times, missing_quotes, unchecked = [], [], [], []
    expected = set()
    for finding in kept:
        label = finding["episode"]
        stamps = times_in(str(finding.get("at") or ""))
        expected.update(stamps)
        expected.update(times_in(str(finding.get("evidence") or "")))
        quotes = finding.get("quotes", [])
        if not stamps and not quotes:
            unchecked.append(finding["id"])
        if label != ALL and label not in positions:
            missing_episodes.append(label)
            continue
        lo, hi = section(label)
        body = report[lo:hi]
        if stamps and stamps[0] not in times_in(body):
            missing_times.append(f"{finding['id']} {label} {clock(stamps[0])}")
        for quote in quotes:
            if nfkc(quote) not in body:
                missing_quotes.append(f'{finding["id"]} {label} "{quote}"')
    unexpected = sorted({clock(t) for t in times_in(report)} - {clock(t) for t in expected})
    result = {
        "ok": not (missing_episodes or missing_times or missing_quotes or unexpected),
        "kept": len(kept),
        "missing_episodes": sorted(set(missing_episodes)),
        "missing_times": missing_times,
        "missing_quotes": missing_quotes,
        "unexpected_times": unexpected,
        "unchecked": unchecked,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("script")
    p.add_argument("captions")
    p.add_argument("out")
    p.set_defaults(func=cmd_script)
    p = sub.add_parser("import")
    p.add_argument("ledger")
    p.add_argument("episode")
    p.add_argument("findings")
    p.add_argument("--source", required=True)
    p.add_argument("--base", help="directory relative evidence paths start from (default: the findings file's)")
    p.set_defaults(func=cmd_import)
    p = sub.add_parser("validate")
    p.add_argument("ledger")
    p.add_argument("--final", action="store_true")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("listen")
    p.add_argument("ledger")
    p.add_argument("--terms")
    p.set_defaults(func=cmd_listen)
    p = sub.add_parser("sheet")
    p.add_argument("ledger")
    p.add_argument("out")
    p.set_defaults(func=cmd_sheet)
    p = sub.add_parser("check")
    p.add_argument("ledger")
    p.add_argument("report")
    p.set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
