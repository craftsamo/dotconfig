#!/usr/bin/env python3
"""Helpers for a video inspection job (stdlib only).

The findings ledger (``ledger.json``) is the one source of every finding; the
inspection sheet and the acceptance check of the written report are derived
from it, so nothing is copied by hand. The ledger also carries the items the
job looks for (``aspects``), copied from a genre catalog by ``init``; every
later command reads only the ledger, so a job may add or drop an item by
editing that copy.

    inspection.py genres                                  the genre catalogs beside this script
    inspection.py aspects  <genre> [--json]               one catalog: aspect > kind > item, with routes
    inspection.py init     <ledger.json> --genre G [--aspects a,b] [--job J] [--language L] [--sheet-language L]
                                                      a fresh ledger holding the chosen aspects
    inspection.py upgrade  <ledger.json> --genre G        give a ledger made before aspects existed the catalog's aspects
    inspection.py focus    <ledger.json> --route R        the items R looks for, as lines for a leaf's focus or note
    inspection.py script   <captions.txt> <out.txt>       strip "[m:ss] " prefixes
    inspection.py validate <ledger.json> [--final]        schema; --final also refuses open/recheck findings
    inspection.py import   <ledger.json> <episode> <findings.md> --source NAME [--aspect A] [--kind K]
                                                      add a hands report's `m:ss | aspect|kind|item | ... ` lines
    inspection.py triage-speech <ledger.json> <episode> <speech dir> [--ignore FILE] [--max-jumps N]
                                                      keep only value mismatches and mid-line jumps
    inspection.py ask-draft  <ledger.json> <out.md>       `ID | problem` lines to reword as claims
    inspection.py ask-import <ledger.json> <asks.md>      store the reworded questions
    inspection.py kinds    <ledger.json>                  give findings imported without a kind one
    inspection.py export   <ledger.json> <out.json>       rows, formulas, options and colours for the spreadsheet
    inspection.py readback <ledger.json> <values.json>    take the spreadsheet's judgments into the ledger
    inspection.py listen   <ledger.json> [--terms FILE]   add ear-check candidates from each caption file
    inspection.py sheet    <ledger.json> <out.md> [--listen]   the Markdown inspection sheet
    inspection.py check    <ledger.json> <report>         does the report carry every kept finding?

``--terms`` names extra words to listen for: one term per line, or
``<episode label><TAB><term>`` for one episode only.

Ledger shape::

    {"job": "...", "genre": "explainer",
     "language": "<captions' BCP 47 tag>", "sheet_language": "<the user's tag>",
     "aspects": [{"id": "text", "label": {"en": "Text", "ja": "字"}, "route": "video-creator",
                  "kinds": [{"id": "typo", "label": {...}, "default": true,
                             "hint": "<regex placing an old finding here>",
                             "sources": ["<finding sources that mean this kind>"],
                             "items": [{"id": "misspelling", "look_for": "...",
                                        "route": "<optional override>", "certainty": "<optional default>"}]}],
                  "items": [...]}],
     "episodes": [{"label": "#1", "title": "...", "captions": "/abs/captions.txt",
                   "video": "<YouTube id or URL>", "thumbnail": "<optional URL>",
                   "language": "<optional per-episode override>",
                   "checked": ["text", "voice", "content", "thumbnail"]}],
     "findings": [{"id": "F001", "episode": "#1" | "all", "at": "1:15" | "0:50-0:54" | "",
                   "aspect": "<an aspect id of the ledger, or overall>",
                   "kind": "<optional: a kind id of that aspect>",
                   "item": "<optional: an item id of that aspect or kind>",
                   "problem": "...", "ask": "<the claim the sheet shows instead of problem>",
                   "evidence": "...", "certainty": "certain|confirm",
                   "quotes": ["verbatim words the report must keep"],
                   "source": "video-creator|audio-creator|image-creator|searcher|researcher|user|assistant",
                   "status": "open|recheck|keep|drop|hold",
                   "note": "<the user's memo>", "reply": "<the assistant's answer>"}],
     "listen": [{"episode": "#1", "at": "0:12", "term": "...", "result": null}]}

Aspects: a genre catalog is ``references/<genre>.json`` beside this script's
directory, in the same shape as ``aspects`` plus ``genre`` and ``label``.
``init`` copies the chosen aspects into the ledger; the ``overall`` aspect
(cross-episode findings) is always present and never in a catalog. Aspect,
kind and item ids share one namespace, because a report's second cell may
name any of them. An aspect either has ``kinds`` (then every finding of it
needs a kind on the sheet) or bare ``items``. ``kinds`` places a finding
imported without a kind: its item's kind when it names an item, else a
kind whose ``sources`` list the finding's source, else the first kind whose
``hint`` matches its wording, else the kind marked ``default``. An item's
``route`` names who looks for it (``focus`` groups by route) and a
``certainty`` of ``confirm`` caps every finding that names it: ``import``
lowers such a finding to ``confirm`` and ``validate`` refuses one left
``certain``, because an item that needs the user's eyes or ears is never
certain, whoever reports it. Two ids carry behaviour of their own: an
aspect named ``thumbnail`` links its findings to the thumbnail image, and
``triage-speech`` needs a ``voice`` aspect with ``reading`` and
``delivery`` kinds; a catalog that offers those checks uses those ids.

Statuses: ``open`` waits for the user, ``recheck`` waits for the assistant,
``keep`` is reported, ``drop`` is not, ``hold`` stays in the ledger unreported.
``checked`` lists the aspects whose check actually finished for that episode;
the sheet names the rest as unchecked, and ``--final`` requires the list.
``check`` finds each episode's section by the first line that starts with its
label (after an optional Markdown heading or list marker), so the report puts
every episode under a line beginning with its label.

Spreadsheet: ``export`` writes the findings tab (one row per live finding, the
time cell a HYPERLINK to the video at that second), the summary tab's
formulas, the dropdown options and the ``format`` block (the row bands per
episode and their two alternating backgrounds); it refuses a finding of an
aspect with kinds that has none. ``readback`` takes the tab
read back from the sheet (``{"values": [[header], [row], ...]}`` or a bare
list of rows) and maps each answer to a status: the user answers the claim
(YES = it is so = keep, NO = drop, can't tell = the assistant's turn), the
status is derived, never chosen on the sheet. So ``ask`` must state the
defect as a claim YES confirms, never as a question with two readings.
Column names and option labels come from ``SHEET_TEXT``, so the two sides
agree by construction.

Language: ``sheet_language`` picks the sheet's wording from ``SHEET_TEXT`` and
the aspect and kind labels from the ledger's ``label`` maps (English when
absent or unknown). ``language`` (per episode, else the
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

CATALOGS = Path(__file__).resolve().parent.parent / "references"
# The one aspect every ledger has and no catalog lists: cross-episode findings.
OVERALL = {"id": "overall", "label": {"en": "Overall", "ja": "全体"}, "route": "assistant", "items": []}
ROUTES = ("video-creator", "audio-creator", "image-creator", "searcher", "researcher", "assistant", "user")
IDENT = re.compile(r"^[a-z][a-z0-9-]*$")
CERTAINTIES = ("certain", "confirm")
STATUSES = ("open", "recheck", "keep", "drop", "hold")
# The sheet's judgment is the user's answer to the finding's claim, not a
# status: YES (it is so) keeps, NO drops, "can't tell" hands the finding to
# the assistant (recheck; hold shows the same answer once the assistant has
# given up on it), and a blank cell is open. ANSWERS lists the dropdown.
ANSWERS = ("keep", "drop", "recheck")
ANSWER_OF = {"open": None, "recheck": "recheck", "keep": "keep", "drop": "drop", "hold": "recheck"}
SUMMARY_COUNTS = ("total", "keep", "drop", "recheck", "open")
SOURCES = ("video-creator", "audio-creator", "image-creator", "searcher", "researcher", "user", "assistant")
ALL = "all"

TIME = re.compile(r"(?<![\d:])(?:(\d{1,2}):)?(\d{1,3}):(\d{2})(?![\d:])")
CAPTION_LINE = re.compile(r"^\[(\d{1,3}(?::\d{2}){1,2})\]\s?(.*)$")
LINE_PREFIX = r"^[ \t]*(?:#{1,6}[ \t]+|[-*+][ \t]+|\d+[.)][ \t]+|[^\w\s#][ \t]*)?"
YOUTUBE_ID = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])|^([A-Za-z0-9_-]{11})$")
LINK_LEAD = 2  # seconds before the finding's time a video link starts

# The spreadsheet's columns, in order; the letters are what the summary formulas use.
COLUMNS = ("id", "episode", "at", "kind", "text", "evidence", "judgment", "note", "reply")

# The review sheet's wording per reader language; English is the fallback.
SHEET_TEXT = {
    "en": {
        "judgments": {"keep": "YES", "drop": "NO", "recheck": "Can't tell"},
        "columns": {"id": "ID", "episode": "Episode", "at": "Time", "kind": "Kind",
                    "text": "Claim (YES = it is so)", "evidence": "Evidence", "judgment": "Answer",
                    "note": "Memo", "reply": "Reply"},
        "summary_columns": {"episode": "Episode", "title": "Title", "total": "Findings", "keep": "YES",
                            "drop": "NO", "recheck": "Can't tell", "open": "Unanswered"},
        "tabs": {"findings": "Findings", "summary": "Summary"}, "total": "Total", "thumb": "Thumbnail",
        "title": "Inspection sheet", "overall": "Overall",
        "intro": "Certain = reproduced on our side. Tick what needs your eyes or ears and send back the result.",
        "certain": "Certain", "confirm": "Needs your eyes or ears", "listen": "Listen for",
        "checked": "Checked: {done} / Not checked: {todo}", "unrecorded": "Checked aspects: not recorded",
        "none": "none", "join": ", ", "clean_checked": "No findings in the checked aspects",
        "clean_unrecorded": "No findings (checked aspects not recorded)", "evidence": " (evidence: {})",
        "colon": ": ", "gap": "  ",
    },
    "ja": {
        "judgments": {"keep": "YES", "drop": "NO", "recheck": "確認不可"},
        "columns": {"id": "ID", "episode": "回", "at": "時刻", "kind": "項目", "text": "内容（YES＝その通り）",
                    "evidence": "根拠", "judgment": "判定", "note": "メモ", "reply": "返答"},
        "summary_columns": {"episode": "回", "title": "題", "total": "所見", "keep": "YES", "drop": "NO",
                            "recheck": "確認不可", "open": "未回答"},
        "tabs": {"findings": "所見", "summary": "まとめ"}, "total": "合計", "thumb": "サムネ",
        "title": "確認用シート", "overall": "全体",
        "intro": "確実＝こちらで確かめ済み。要確認の所は、チェックを付けて結果を返してください。",
        "certain": "確実", "confirm": "要確認（目か耳で確かめる）", "listen": "耳で聞く所",
        "checked": "確認した観点：{done}　／　未確認：{todo}", "unrecorded": "確認した観点：未記録",
        "none": "なし", "join": "・", "clean_checked": "確認した観点では指摘なし",
        "clean_unrecorded": "指摘なし（確認範囲は未記録）", "evidence": "（根拠: {}）",
        "colon": "：", "gap": "　",
    },
}
# The two backgrounds the rows alternate between per episode, so an episode
# reads as one band; white and a light green, far enough apart to tell at a
# glance. The dropdown chips themselves stay uncoloured: the API cannot
# colour a chip, and a coloured cell behind a grey chip reads as a mistake.
EPISODE_TINTS = ("#FFFFFF", "#E6F4EA")


# --- aspects: the items a job looks for -------------------------------------
# A genre catalog and a ledger's ``aspects`` share one shape (module docstring).
# Everything below reads the ledger's copy, so a job that edited it is obeyed.


def aspect_problems(aspects, where: str = "aspects") -> list[str]:
    """Shape errors of an aspects list: ids, labels, routes, kinds and items,
    and the uniqueness of every id across the list."""
    errors: list[str] = []
    if not isinstance(aspects, list) or not aspects:
        return [f"{where} must be a nonempty list"]
    seen: set[str] = {OVERALL["id"]}  # one namespace: a report's second cell may name any level

    def claim(ident: str, what: str, owner: str) -> None:
        if ident in seen:
            errors.append(f"{owner}: duplicate {what} id {ident}")
        seen.add(ident)

    def check_items(items, owner: str) -> None:
        if not isinstance(items, list):
            errors.append(f"{owner}: items must be a list")
            return
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not IDENT.match(item["id"]):
                errors.append(f"{owner}: every item needs a lowercase id")
                continue
            iid = item["id"]
            claim(iid, "item", owner)
            if not isinstance(item.get("look_for"), str) or not item["look_for"].strip():
                errors.append(f"{owner}.{iid}: look_for is empty")
            if item.get("route") is not None and item["route"] not in ROUTES:
                errors.append(f"{owner}.{iid}: route must be one of {', '.join(ROUTES)}")
            if item.get("certainty") is not None and item["certainty"] not in CERTAINTIES:
                errors.append(f"{owner}.{iid}: certainty must be certain or confirm")

    def check_label(obj: dict, owner: str) -> None:
        label = obj.get("label")
        if not isinstance(label, dict) or not isinstance(label.get("en"), str) or not label["en"].strip():
            errors.append(f"{owner}: label needs at least an en wording")
        elif not all(isinstance(v, str) and v.strip() for v in label.values()):
            errors.append(f"{owner}: every label wording must be a nonempty string")

    for index, aspect in enumerate(aspects):
        owner = f"{where}[{index}]"
        if not isinstance(aspect, dict) or not isinstance(aspect.get("id"), str) or not IDENT.match(aspect["id"]):
            errors.append(f"{owner}: needs a lowercase id")
            continue
        aid = aspect["id"]
        owner = aid
        if aid == OVERALL["id"]:
            errors.append(f"{owner}: overall is built in, never listed")
        else:
            claim(aid, "aspect", where)
        check_label(aspect, owner)
        if aspect.get("route") not in ROUTES:
            errors.append(f"{owner}: route must be one of {', '.join(ROUTES)}")
        kinds = aspect.get("kinds")
        if kinds is not None:
            if not isinstance(kinds, list) or not kinds:
                errors.append(f"{owner}: kinds must be a nonempty list, or absent")
                continue
            if aspect.get("items"):
                errors.append(f"{owner}: an aspect with kinds keeps its items under the kinds")
            defaults = 0
            for kind in kinds:
                if not isinstance(kind, dict) or not isinstance(kind.get("id"), str) or not IDENT.match(kind["id"]):
                    errors.append(f"{owner}: every kind needs a lowercase id")
                    continue
                kid = kind["id"]
                claim(kid, "kind", owner)
                check_label(kind, f"{owner}.{kid}")
                if kind.get("route") is not None and kind["route"] not in ROUTES:
                    errors.append(f"{owner}.{kid}: route must be one of {', '.join(ROUTES)}")
                if kind.get("hint") is not None:
                    try:
                        re.compile(str(kind["hint"]))
                    except re.error as exc:
                        errors.append(f"{owner}.{kid}: hint is not a regex ({exc})")
                sources = kind.get("sources")
                if sources is not None and (not isinstance(sources, list) or not set(sources) <= set(SOURCES)):
                    errors.append(f"{owner}.{kid}: sources must list finding sources")
                defaults += 1 if kind.get("default") else 0
                check_items(kind.get("items", []), f"{owner}.{kid}")
            if defaults > 1:
                errors.append(f"{owner}: at most one default kind")
        else:
            check_items(aspect.get("items", []), owner)
    return errors


def catalog_path(genre: str) -> Path:
    return CATALOGS / f"{genre}.json"


def genres() -> list[str]:
    return sorted(p.stem for p in CATALOGS.glob("*.json"))


def load_catalog(genre: str) -> dict:
    if not IDENT.match(genre or ""):
        fail(f"genre must be a lowercase name, got {genre!r}")
    path = catalog_path(genre)
    if not path.is_file():
        fail(f"no catalog for genre {genre!r}; known: {', '.join(genres()) or 'none'}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read catalog {path}: {exc}")
    errors = [] if isinstance(data, dict) else ["catalog must be a JSON object"]
    if not errors:
        if data.get("genre") != genre:
            errors.append(f"catalog genre must be {genre!r}")
        label = data.get("label")
        if not isinstance(label, dict) or not isinstance(label.get("en"), str):
            errors.append("catalog label needs an en wording")
        errors += aspect_problems(data.get("aspects"))
    if errors:
        fail(f"catalog {path.name}: " + "; ".join(errors))
    return data


def aspects_of(data: dict) -> list[dict]:
    """The ledger's aspects plus the built-in overall, in sheet order."""
    return [a for a in data.get("aspects") or [] if isinstance(a, dict)] + [OVERALL]


def aspect_ids(data: dict) -> list[str]:
    return [a["id"] for a in aspects_of(data) if isinstance(a.get("id"), str)]


def reviewed(data: dict) -> list[str]:
    """The aspects an episode's ``checked`` may list: every one but overall."""
    return [a for a in aspect_ids(data) if a != OVERALL["id"]]


def kinds_of(data: dict) -> dict[str, str]:
    """kind id → aspect id."""
    return {k["id"]: a["id"] for a in aspects_of(data) for k in a.get("kinds") or []
            if isinstance(k, dict) and isinstance(k.get("id"), str)}


def items_of(data: dict) -> dict[str, tuple[str, str | None]]:
    """item id → (aspect id, kind id or None)."""
    found: dict[str, tuple[str, str | None]] = {}
    for aspect in aspects_of(data):
        for item in aspect.get("items") or []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                found[item["id"]] = (aspect["id"], None)
        for kind in aspect.get("kinds") or []:
            if not isinstance(kind, dict):
                continue
            for item in kind.get("items") or []:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    found[item["id"]] = (aspect["id"], kind.get("id"))
    return found


def find_aspect(data: dict, aid: str) -> dict | None:
    return next((a for a in aspects_of(data) if a.get("id") == aid), None)


def find_kind(data: dict, kid: str) -> dict | None:
    for aspect in aspects_of(data):
        for kind in aspect.get("kinds") or []:
            if isinstance(kind, dict) and kind.get("id") == kid:
                return kind
    return None


def find_item(data: dict, iid: str) -> dict | None:
    for aspect in aspects_of(data):
        for item in aspect.get("items") or []:
            if isinstance(item, dict) and item.get("id") == iid:
                return item
        for kind in aspect.get("kinds") or []:
            for item in (kind.get("items") or []) if isinstance(kind, dict) else []:
                if isinstance(item, dict) and item.get("id") == iid:
                    return item
    return None


def has_kinds(data: dict, aid: str) -> bool:
    aspect = find_aspect(data, aid)
    return bool(aspect and aspect.get("kinds"))


def wording(obj: dict, language: str | None) -> str:
    """An aspect's or kind's label in the sheet language, else English."""
    label = obj.get("label") or {}
    return str(label.get(primary(language)) or label.get("en") or obj.get("id", ""))


def infer_kind(data: dict, finding: dict) -> str | None:
    """A kind for a finding that has none, from its source and wording; None
    for an aspect that has no kinds or when nothing places it."""
    aspect = find_aspect(data, str(finding.get("aspect")))
    if not aspect or not aspect.get("kinds"):
        return None
    placed = items_of(data).get(str(finding.get("item"))) if finding.get("item") else None
    if placed and placed[0] == aspect["id"] and placed[1]:
        return placed[1]
    kinds = [k for k in aspect["kinds"] if isinstance(k, dict)]
    for kind in kinds:
        if finding.get("source") in (kind.get("sources") or []):
            return kind["id"]
    text = " ".join(str(finding.get(k) or "") for k in ("problem", "evidence", "ask"))
    for kind in kinds:
        if kind.get("hint") and re.search(str(kind["hint"]), text, re.I):
            return kind["id"]
    return next((k["id"] for k in kinds if k.get("default")), None)

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


def video_id(value: str | None) -> str | None:
    match = YOUTUBE_ID.search(str(value or "").strip())
    return (match.group(1) or match.group(2)) if match else None


def video_url(episode: dict, at: str | None = None) -> str | None:
    """The video at the finding's first time, LINK_LEAD seconds early; the start without a time."""
    vid = video_id(episode.get("video"))
    if not vid:
        return None
    stamps = times_in(str(at or ""))
    if not stamps:
        return f"https://youtu.be/{vid}"
    return f"https://youtu.be/{vid}?t={max(0, stamps[0] - LINK_LEAD)}"


def thumbnail_url(episode: dict) -> str | None:
    if episode.get("thumbnail"):
        return str(episode["thumbnail"])
    vid = video_id(episode.get("video"))
    return f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg" if vid else None


def finding_url(finding: dict, episode: dict | None) -> str | None:
    if not episode:
        return None
    if finding.get("aspect") == "thumbnail" and not times_in(str(finding.get("at") or "")):
        return thumbnail_url(episode)
    return video_url(episode, finding.get("at"))


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
    if "aspects" not in data:
        return ["ledger has no aspects: make it with `inspection.py init --genre <genre>`"]
    errors = aspect_problems(data["aspects"])
    if errors:
        return errors
    aspects, kinds, items = aspect_ids(data), kinds_of(data), items_of(data)
    checkable = reviewed(data)
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
        if checked is not None and (not isinstance(checked, list) or not set(checked) <= set(checkable)):
            errors.append(f"episode {label}: checked must list aspects from {', '.join(checkable)}")
        elif final and checked is None:
            errors.append(f"episode {label}: checked is not recorded")
        if episode.get("video") and not video_id(episode["video"]):
            errors.append(f"episode {label}: video must be a YouTube id or URL")
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
        aspect = finding.get("aspect")
        if aspect not in aspects:
            errors.append(f"{where}: aspect must be one of {', '.join(aspects)}")
        kind = finding.get("kind")
        if kind is not None and kinds.get(kind) != aspect:
            errors.append(f"{where}: kind {kind!r} is not a kind of aspect {aspect!r}")
        item = finding.get("item")
        if item is not None and (item not in items or items[item][0] != aspect
                                 or (items[item][1] is not None and kind is not None and items[item][1] != kind)):
            errors.append(f"{where}: item {item!r} is not an item of {aspect!r}/{kind!r}")
        elif item is not None and (find_item(data, item) or {}).get("certainty") == "confirm" \
                and finding.get("certainty") == "certain":
            errors.append(f"{where}: item {item!r} needs the user's eyes or ears; certainty must be confirm")
        for field in ("ask", "note", "reply"):
            if finding.get(field) is not None and not isinstance(finding[field], str):
                errors.append(f"{where}: {field} must be a string")
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
        if final and finding.get("status", "open") in ("open", "recheck"):
            errors.append(f"{where}: still {finding.get('status', 'open')} (settle keep, drop or hold before the report)")
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


def cmd_genres(args) -> int:
    print(json.dumps({"ok": True, "genres": genres(), "catalogs": str(CATALOGS)}, ensure_ascii=False))
    return 0


def item_route(aspect: dict, kind: dict | None, item: dict) -> str:
    return str(item.get("route") or (kind or {}).get("route") or aspect.get("route"))


def walk_items(data: dict):
    """(aspect, kind or None, item) for every item of the ledger, in order."""
    for aspect in aspects_of(data):
        for item in aspect.get("items") or []:
            if isinstance(item, dict):
                yield aspect, None, item
        for kind in aspect.get("kinds") or []:
            if not isinstance(kind, dict):
                continue
            for item in kind.get("items") or []:
                if isinstance(item, dict):
                    yield aspect, kind, item


def cmd_aspects(args) -> int:
    catalog = load_catalog(args.genre)
    if args.json:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        return 0
    print(f"{catalog['genre']} — {wording(catalog, None)}")
    for aspect in catalog["aspects"]:
        print(f"  {aspect['id']}  {wording(aspect, None)}  [{aspect['route']}]")
        for kind in aspect.get("kinds") or []:
            flags = " (default)" if kind.get("default") else ""
            print(f"    {kind['id']}  {wording(kind, None)}{flags}")
            for item in kind.get("items") or []:
                route = f" [{item['route']}]" if item.get("route") else ""
                cert = f" ({item['certainty']})" if item.get("certainty") else ""
                print(f"      {item['id']}{route}{cert}: {item['look_for']}")
        for item in aspect.get("items") or []:
            route = f" [{item['route']}]" if item.get("route") else ""
            cert = f" ({item['certainty']})" if item.get("certainty") else ""
            print(f"    {item['id']}{route}{cert}: {item['look_for']}")
    return 0


def cmd_init(args) -> int:
    target = Path(args.ledger)
    if target.exists():
        fail(f"{target} exists; init never overwrites a ledger")
    catalog = load_catalog(args.genre)
    available = [a["id"] for a in catalog["aspects"]]
    chosen = [a.strip() for a in (args.aspects or "").split(",") if a.strip()] or available
    unknown = [a for a in chosen if a not in available]
    if unknown:
        fail(f"not in the {args.genre} catalog: {', '.join(unknown)}; it offers {', '.join(available)}")
    aspects = [json.loads(json.dumps(a)) for a in catalog["aspects"] if a["id"] in chosen]
    data = {"job": args.job or "", "genre": args.genre}
    if args.language:
        data["language"] = args.language
    if args.sheet_language:
        data["sheet_language"] = args.sheet_language
    data.update({"aspects": aspects, "episodes": [], "findings": [], "listen": []})
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    save(str(target), data)
    print(json.dumps({"ok": True, "genre": args.genre, "aspects": [a["id"] for a in aspects],
                      "items": sum(1 for _ in walk_items(data)), "out": str(target)}, ensure_ascii=False))
    return 0


def cmd_upgrade(args) -> int:
    """A ledger made before aspects existed takes the whole catalog; its
    findings already use the catalog's aspect and kind ids."""
    data = load(args.ledger)
    if "aspects" in data:
        fail("the ledger already has aspects; edit them rather than upgrading")
    catalog = load_catalog(args.genre)
    data["genre"] = args.genre
    data["aspects"] = [json.loads(json.dumps(a)) for a in catalog["aspects"]]
    errors = problems(data, final=False)
    if errors:
        fail("the ledger's findings do not fit the catalog: " + "; ".join(errors))
    save(args.ledger, data)
    print(json.dumps({"ok": True, "genre": args.genre, "aspects": [a["id"] for a in data["aspects"]],
                      "findings": len(data["findings"])}, ensure_ascii=False))
    return 0


def cmd_focus(args) -> int:
    """The items one route looks for, one line each as
    ``aspect/kind/item: look_for``, for a leaf's focus or note; a hands report
    that echoes the item id lets ``import`` place the finding."""
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    if args.route not in ROUTES:
        fail(f"route must be one of {', '.join(ROUTES)}")
    lines = []
    for aspect, kind, item in walk_items(data):
        if item_route(aspect, kind, item) != args.route:
            continue
        path = "/".join(part for part in (aspect["id"], kind["id"] if kind else None, item["id"]) if part)
        cert = " (confirm: needs the user's eyes or ears)" if item.get("certainty") == "confirm" else ""
        lines.append(f"{path}: {item['look_for']}{cert}")
    Path(args.out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(json.dumps({"ok": bool(lines), "route": args.route, "items": len(lines), "out": args.out}, ensure_ascii=False))
    return 0 if lines else 1


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


FILE_NAME = re.compile(r"^\S+\.[A-Za-z][A-Za-z0-9]{0,4}$")


def is_url(item: str) -> bool:
    return "://" in item or item.lower().startswith(("http:", "https:", "www."))


def evidence_pieces(evidence: str) -> list[str]:
    text = str(evidence or "")
    pieces = re.split(r";\s+", text) if "://" in text else text.split(";")  # a URL may hold ';'
    return [piece.strip() for piece in pieces if piece.strip()]


def resolve_evidence(evidence: str, base: str | None) -> str:
    """Prefix ``base`` to each ``;``-separated piece that reads as a relative file
    path. A URL, an absolute path, a measurement or a plain word stays as it is."""
    if not base:
        return evidence
    pieces = []
    for item in evidence_pieces(evidence):
        looks_like_path = not is_url(item) and " " not in item and ("/" in item or bool(Path(item).suffix))
        if looks_like_path and not Path(item).is_absolute():
            item = str(Path(base) / item)
        pieces.append(item)
    return "; ".join(pieces)


ITEM_PREFIX = re.compile(r"^([a-z][a-z0-9-]*)\s*[:：]\s*(.+)$", re.S)


def report_rows(data: dict, path: str, base: str | None = None, aspect: str | None = None,
                kind: str | None = None) -> tuple[list[dict], list[str]]:
    """``m:ss | aspect|kind|item | problem | evidence | certain|confirm`` lines.
    Markdown table pipes, a header and separator rows are ignored; a stray
    ``|`` inside the problem is kept in it. The second cell may name an
    aspect, a kind or an item of the ledger; ``aspect`` / ``kind`` override it
    (a speech report puts a speaker label there). A problem that starts with
    ``<item id>:`` names its item too. Any other line that does not parse is
    returned so the caller sees what was not imported."""
    kinds, items = kinds_of(data), items_of(data)
    aspects = aspect_ids(data)
    rows, skipped = [], []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if "|" not in line or HEADER_OR_RULE.match(line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            skipped.append(line)
            continue
        at, column = cells[0], cells[1].lower().strip(" .")
        evidence, certainty = cells[-2], cells[-1].lower().strip(" .")
        problem = " | ".join(cells[2:-2]).strip()
        at = "" if at in ("", "-", "—") else at
        row_item = None
        prefixed = ITEM_PREFIX.match(problem)
        if prefixed and prefixed.group(1) in items:
            row_item, problem = prefixed.group(1), prefixed.group(2).strip()
        elif column in items:
            row_item = column
        if row_item:
            item_aspect, item_kind = items[row_item]
        else:
            item_aspect, item_kind = None, None
        row_kind = kind or (column if column in kinds else None) or item_kind
        row_aspect = aspect or (kinds[column] if column in kinds else column if column in aspects else None) or item_aspect
        if (row_aspect not in aspects or certainty not in CERTAINTIES or not problem
                or (at and not times_in(at)) or (row_kind and kinds.get(row_kind) != row_aspect)
                or (row_item and (item_aspect != row_aspect or (item_kind and item_kind != row_kind)))):
            skipped.append(line)
            continue
        row = {"at": at, "aspect": row_aspect, "problem": problem,
               "evidence": resolve_evidence(evidence, base), "certainty": certainty, "quotes": quotes_in(problem)}
        if row_kind:
            row["kind"] = row_kind
        if row_item:
            row["item"] = row_item
            item = find_item(data, row_item) or {}
            if item.get("certainty") == "confirm":  # an item that needs the user's eyes or ears
                row["certainty"] = "confirm"
        rows.append(row)
    return rows, skipped


def cmd_import(args) -> int:
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    aspects, kinds = aspect_ids(data), kinds_of(data)
    if args.episode not in {e["label"] for e in data["episodes"]} | {ALL}:
        fail(f"unknown episode {args.episode!r}")
    if args.source not in SOURCES:
        fail(f"source must be one of {', '.join(SOURCES)}")
    if args.aspect and args.aspect not in aspects:
        fail(f"aspect must be one of {', '.join(aspects)}")
    if args.kind and args.kind not in kinds:
        fail(f"kind must be one of {', '.join(kinds)}")
    if args.kind and args.aspect and kinds[args.kind] != args.aspect:
        fail(f"kind {args.kind} belongs to aspect {kinds[args.kind]}")
    base = args.base if args.base is not None else str(Path(args.findings).resolve().parent)
    rows, skipped = report_rows(data, args.findings, base, args.aspect or (kinds[args.kind] if args.kind else None),
                                args.kind)
    added = add_findings(data, args.episode, rows, args.source)
    save(args.ledger, data)
    print(json.dumps({"ok": not skipped, "added": added, "not_imported": skipped}, ensure_ascii=False))
    return 0 if not skipped else 1


def add_findings(data: dict, episode: str, rows: list[dict], source: str) -> list[str]:
    """Append rows as open findings with fresh ids; a row already in the ledger
    (same episode, time and problem) is left alone."""
    numbers = [int(m.group(1)) for f in data["findings"] if (m := re.fullmatch(r"F(\d+)", str(f.get("id"))))]
    next_number = max(numbers, default=0) + 1
    seen = {(f["episode"], f.get("at", ""), f["problem"]) for f in data["findings"]}
    added = []
    for row in rows:
        key = (episode, row["at"], row["problem"])
        if key in seen:
            continue
        seen.add(key)
        fid = f"F{next_number:03d}"
        next_number += 1
        data["findings"].append({"id": fid, "episode": episode, **row, "source": source, "status": "open"})
        added.append(fid)
    return added


# --- speech triage ----------------------------------------------------------
# A speech report is candidates read off ASR over music, so most lines are
# noise. Two shapes survive: a value the script states that the ASR heard as
# another value (or a Latin-script term it did not hear at all), and a pitch or
# level jump inside one caption line (a jump at a line start is usually the
# next speaker). Everything else is dropped before the user sees it.

KANJI_DIGITS = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
KANJI_SMALL = {"十": 10, "百": 100, "千": 1000}
KANJI_BIG = {"万": 10**4, "億": 10**8, "兆": 10**12}
NUMBER_TOKEN = re.compile(r"(?:\d+(?:\.\d+)?|[〇零一二三四五六七八九])+(?:[十百千万億兆](?:\d+(?:\.\d+)?|[〇零一二三四五六七八九])*)*|[十百千万億兆]+")
LATIN_TERM = re.compile(r"[A-Za-z][A-Za-z0-9]*")
JUMP_ST = re.compile(r"([+-]\d+(?:\.\d+)?)\s*st\b(?=[^;()]*(?:vs|直前|前区間))")
JUMP_DB = re.compile(r"([+-]\d+(?:\.\d+)?)\s*dB\b(?=[^;()]*(?:vs|直前|前区間))")


def number_value(token: str) -> float | None:
    """``1040億`` → 1.04e11, ``2万3千`` → 23000, ``五十二`` → 52, ``2024`` → 2024."""
    total = 0.0
    section = 0.0
    digits = ""
    for ch in token:
        if ch.isdigit() or ch == ".":
            digits += ch
        elif ch in KANJI_DIGITS:
            digits += str(KANJI_DIGITS[ch])
        elif ch in KANJI_SMALL:
            section += (float(digits) if digits else 1) * KANJI_SMALL[ch]
            digits = ""
        elif ch in KANJI_BIG:
            total += (section + (float(digits) if digits else 1)) * KANJI_BIG[ch]
            section, digits = 0.0, ""
    try:
        return total + section + (float(digits) if digits else 0.0)
    except ValueError:
        return None


def numbers_in(text: str) -> set[float]:
    found = set()
    for match in NUMBER_TOKEN.finditer(nfkc(text).replace(",", "")):
        value = number_value(match.group(0))
        if value is not None:
            found.add(value)
    return found


def latin_terms(text: str) -> set[str]:
    """Latin-script terms a non-Latin script spells out: a single capital, an
    acronym, or a word with an inner capital (``A``, ``TV``, ``ChatGPT``); an
    ordinary lower-case word is not one."""
    found = set()
    for word in LATIN_TERM.findall(nfkc(text)):
        if len(word) == 1 and word.isupper() or word.isupper() or any(c.isupper() for c in word[1:]):
            found.add(word.lower())
    return found


QUOTE_OR_EMPTY = re.compile("|".join(
    f"{re.escape(open_)}([^{re.escape(open_ + close)}\\n]*){re.escape(close)}" for open_, close in QUOTE_PAIRS
))


def script_and_heard(problem: str) -> tuple[str, str] | None:
    """A reading line quotes the script's words, then what the ASR heard
    (``「script」→「heard」``; ``「」`` for nothing). Several pairs split in
    halves; with an odd count the last two quotes are the pair. One quote is
    no pair, so it is not a reading finding."""
    quotes = [next((g for g in m.groups() if g is not None), "") for m in QUOTE_OR_EMPTY.finditer(problem)]
    if len(quotes) < 2:
        return None
    if len(quotes) >= 4 and len(quotes) % 2 == 0:
        half = len(quotes) // 2
        return " ".join(quotes[:half]), " ".join(quotes[half:])
    return quotes[-2], quotes[-1]


def reading_mismatch(problem: str, ignore: list[str], weak: bool) -> bool:
    pair = script_and_heard(problem)
    if pair is None:
        return False
    script, heard = pair
    if any(term.lower() in script.lower() for term in ignore):
        return False
    script_numbers, heard_numbers = numbers_in(script), numbers_in(heard)
    # A one-character script quote is a token fragment, not a value.
    if len(script.strip()) >= 2 and script_numbers - heard_numbers and (heard_numbers or weak):
        return True
    return bool(latin_terms(script) - latin_terms(heard) - {term.lower() for term in ignore})


def jump_values(text: str) -> tuple[float, float]:
    """The largest pitch (semitones) and level (dB) change against the previous segment."""
    pitch = max((abs(float(m.group(1))) for m in JUMP_ST.finditer(text)), default=0.0)
    level = max((abs(float(m.group(1))) for m in JUMP_DB.finditer(text)), default=0.0)
    return pitch, level


def mid_line(at: int, starts: list[int]) -> bool | None:
    """Whether ``at`` falls inside a caption line rather than at one's start;
    None when the captions are unknown."""
    if not starts:
        return None
    earlier = [s for s in starts if s <= at]
    later = [s for s in starts if s > at]
    if not earlier:
        return False
    return at - earlier[-1] > 1 and (not later or later[0] - at > 1)


def triage_speech(findings: list[dict], prosody: list[dict], starts: list[int], ignore: list[str],
                  pitch_jump: float, level_jump: float, max_jumps: int, skip_head: int, weak: bool) -> dict:
    reading = [row for row in findings if reading_mismatch(row["problem"], ignore, weak)]
    scored = []
    for row in prosody:
        at = times_in(row["at"])
        if not at:
            continue
        pitch, level = jump_values(row["problem"] + " " + row["evidence"])
        score = max(pitch / pitch_jump if pitch_jump else 0, level / level_jump if level_jump else 0)
        inside = mid_line(at[0], starts)
        if score < 1 or at[0] < skip_head or (starts and at[0] >= starts[-1]) or inside is False:
            continue
        scored.append((score, at[0], row))
    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen: list[tuple[float, int, dict]] = []
    for item in scored:  # one jump and its recovery a second later are one place to listen
        if len(chosen) < max_jumps and all(abs(item[1] - other[1]) > 2 for other in chosen):
            chosen.append(item)
    delivery = [row for _, _, row in sorted(chosen, key=lambda item: item[1])]
    for row in reading:
        row.update({"aspect": "voice", "kind": "reading", "certainty": "confirm"})
    for row in delivery:
        row.update({"aspect": "voice", "kind": "delivery", "certainty": "confirm"})
    return {"reading": reading, "delivery": delivery,
            "dropped": len(findings) + len(prosody) - len(reading) - len(delivery)}


def cmd_triage_speech(args) -> int:
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    episode = next((e for e in data["episodes"] if e["label"] == args.episode), None)
    if episode is None:
        fail(f"unknown episode {args.episode!r}")
    kinds = kinds_of(data)
    if kinds.get("reading") != "voice" or kinds.get("delivery") != "voice":
        fail("the ledger's aspects have no voice aspect with reading and delivery kinds; the speech triage needs them")
    folder = Path(args.speech_dir)
    findings_path, prosody_path = folder / args.findings, folder / args.prosody
    findings = report_rows(data, str(findings_path), None, "voice")[0] if findings_path.exists() else []
    prosody = report_rows(data, str(prosody_path), None, "voice")[0] if prosody_path.exists() else []
    if not findings and not prosody:
        fail(f"no {args.findings} or {args.prosody} in {folder}")
    starts = []
    if episode.get("captions") and Path(episode["captions"]).exists():
        starts = sorted(s for s in (seconds(at) for at, _ in caption_lines(episode["captions"])) if s is not None)
    ignore = [term for _, term in read_terms(args.ignore)]
    result = triage_speech(findings, prosody, starts, ignore, args.pitch_jump, args.level_jump,
                           args.max_jumps, args.skip_head, args.weak)
    kept = result["reading"] + result["delivery"]
    items = items_of(data)
    for row in kept:  # the triage's kind wins over an item of the other kind
        if row.get("item") and items.get(row["item"], (None, None))[1] != row["kind"]:
            row.pop("item")
    lines = [f"{row['at']} | {row['kind']} | {row['problem']} | {row['evidence']} | confirm" for row in kept]
    (folder / args.out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    added = add_findings(data, args.episode, kept, "audio-creator")
    save(args.ledger, data)
    print(json.dumps({"ok": True, "reading": [r["at"] for r in result["reading"]],
                      "delivery": [r["at"] for r in result["delivery"]], "dropped": result["dropped"],
                      "added": added, "out": str(folder / args.out)}, ensure_ascii=False))
    return 0


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


def live(data: dict) -> list[dict]:
    return [f for f in data["findings"] if f.get("status", "open") != "drop"]


def episode_of(data: dict, finding: dict) -> dict | None:
    return next((e for e in data["episodes"] if e["label"] == finding["episode"]), None)


def kind_label(data: dict, finding: dict) -> str:
    """The sheet's kind cell: the kind's label, else the aspect's."""
    language = data.get("sheet_language")
    kind = find_kind(data, str(finding.get("kind"))) if finding.get("kind") else None
    if kind:
        return wording(kind, language)
    aspect = find_aspect(data, str(finding.get("aspect")))
    return wording(aspect, language) if aspect else str(finding.get("aspect", ""))


def kind_options(data: dict) -> list[str]:
    """The kind column's dropdown: every kind's label, and the label of each
    aspect without kinds, in ledger order."""
    language = data.get("sheet_language")
    options = []
    for aspect in aspects_of(data):
        if aspect.get("kinds"):
            options.extend(wording(k, language) for k in aspect["kinds"] if isinstance(k, dict))
        else:
            options.append(wording(aspect, language))
    return options


def sheet_answer(finding: dict, words: dict) -> str:
    """The answer cell: a reproduced finding comes pre-answered YES (the user
    may still flip it); an unanswered one is blank."""
    status = finding.get("status", "open")
    if status == "open" and finding.get("certainty") == "certain":
        status = "keep"
    answer = ANSWER_OF[status]
    return words["judgments"][answer] if answer else ""


def public_evidence(evidence: str) -> str:
    """Evidence fit for the sheet: URLs and measurements stay; anything that
    reads as a file path or file name goes."""
    kept = []
    for item in evidence_pieces(evidence):
        if is_url(item):
            kept.append(item)
        elif not ("/" in item or "\\" in item or item.startswith(("~", ".")) or FILE_NAME.match(item)):
            kept.append(item)
    return "; ".join(kept)


def cmd_ask_draft(args) -> int:
    data = load(args.ledger)
    lines = [f"{f['id']} | {f.get('ask') or f['problem']}" for f in live(data)
             if f.get("status", "open") in ("open", "recheck") and f.get("certainty") == "confirm"]
    Path(args.out).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(json.dumps({"ok": True, "findings": len(lines), "out": args.out}))
    return 0


def cmd_ask_import(args) -> int:
    data = load(args.ledger)
    by_id = {f["id"]: f for f in data["findings"]}
    stored, skipped = [], []
    for raw in Path(args.asks).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or "|" not in line:
            continue
        fid, _, ask = (cell.strip() for cell in line.partition("|"))
        if fid in by_id and ask:
            by_id[fid]["ask"] = ask
            stored.append(fid)
        else:
            skipped.append(line)
    save(args.ledger, data)
    print(json.dumps({"ok": not skipped, "stored": stored, "not_imported": skipped}, ensure_ascii=False))
    return 0 if not skipped else 1


def cell_text(value: str) -> str:
    """Text safe to enter as a user would: a leading formula character is quoted."""
    text = str(value or "")
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def formula_text(value: str) -> str:
    return str(value).replace('"', '""')


def criterion(value: str) -> str:
    """A COUNTIFS criterion that matches the text exactly: ``=`` forces equality
    and ``~`` escapes the wildcards and itself."""
    escaped = re.sub(r"([*?~])", r"~\1", str(value))
    return formula_text("=" + escaped)


def hyperlink(url: str, label: str) -> str:
    return f'=HYPERLINK("{formula_text(url)}","{formula_text(label)}")'


def column_letter(name: str) -> str:
    return chr(ord("A") + COLUMNS.index(name))


def export_rows(data: dict, words: dict) -> list[list[str]]:
    order = {e["label"]: i for i, e in enumerate(data["episodes"])}
    rows = []
    for finding in sorted(live(data), key=lambda f: (order.get(f["episode"], -1), first_time(f), f["id"])):
        episode = episode_of(data, finding)
        at = str(finding.get("at") or "").strip()
        is_thumb = finding["aspect"] == "thumbnail" and not times_in(at)
        label = at or (words["thumb"] if is_thumb else "")
        url = finding_url(finding, episode)
        at_cell = hyperlink(url, label or url) if url else cell_text(label)
        rows.append([
            finding["id"],
            words["overall"] if finding["episode"] == ALL else finding["episode"],
            at_cell,
            kind_label(data, finding),
            cell_text(finding.get("ask") or finding["problem"]),
            cell_text(public_evidence(finding.get("evidence", ""))),
            sheet_answer(finding, words),
            cell_text(finding.get("note", "")),
            cell_text(finding.get("reply", "")),
        ])
    return rows


def summary_rows(data: dict, words: dict) -> list[list[str]]:
    tab = words["tabs"]["findings"].replace("'", "''")
    episode_col = f"'{tab}'!${column_letter('episode')}:${column_letter('episode')}"
    judgment_col = f"'{tab}'!${column_letter('judgment')}:${column_letter('judgment')}"
    rows = []
    labels = [(e["label"], e) for e in data["episodes"]] + [(ALL, None)]
    for label, episode in labels:
        shown = words["overall"] if label == ALL else label
        if episode is None:
            if not any(f["episode"] == ALL for f in live(data)):
                continue
            title = ""
        else:
            url = video_url(episode)
            title = hyperlink(url, episode.get("title") or shown) if url else cell_text(episode.get("title", ""))
        row = [cell_text(shown), title, f'=COUNTIFS({episode_col},"{criterion(shown)}")']
        for answer in ANSWERS + ("open",):
            option = criterion(words["judgments"][answer]) if answer != "open" else "="  # "=" matches a blank cell
            row.append(f'=COUNTIFS({episode_col},"{criterion(shown)}",{judgment_col},"{option}")')
        rows.append(row)
    first, last = 2, 1 + len(rows)
    total = [words["total"], ""]
    for index in range(2, 2 + len(SUMMARY_COUNTS)):
        letter = chr(ord("A") + index)
        total.append(f"=SUM({letter}{first}:{letter}{last})")
    rows.append(total)
    return rows


def cmd_kinds(args) -> int:
    """Give every finding of an aspect with kinds a kind; the sheet's kind
    column holds kinds only, so a finding without one cannot be exported."""
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    inferred, unresolved = {}, []
    for finding in data["findings"]:
        if finding.get("kind") or not has_kinds(data, str(finding.get("aspect"))):
            continue
        kind = infer_kind(data, finding)
        if kind:
            finding["kind"] = kind
            inferred[finding["id"]] = kind
        else:
            unresolved.append(finding["id"])
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    save(args.ledger, data)
    print(json.dumps({"ok": not unresolved, "inferred": inferred, "unresolved": unresolved}, ensure_ascii=False))
    return 0 if not unresolved else 1


def episode_bands(rows: list[list[str]], words: dict) -> list[dict]:
    """Sheet row ranges per episode (header is row 1), tinted alternately."""
    bands = []
    for index, row in enumerate(rows, start=2):
        if bands and bands[-1]["episode"] == row[1]:
            bands[-1]["last_row"] = index
        else:
            bands.append({"episode": row[1], "first_row": index, "last_row": index,
                          "colour": EPISODE_TINTS[len(bands) % len(EPISODE_TINTS)]})
    return bands


def cmd_export(args) -> int:
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    missing = [f["id"] for f in live(data) if has_kinds(data, str(f.get("aspect"))) and not f.get("kind")]
    if missing:
        fail(f"findings without a kind (run `inspection.py kinds` first): {', '.join(missing)}")
    words = sheet_text(data)
    judgments = [words["judgments"][a] for a in ANSWERS]
    kinds = kind_options(data)
    summary_header = [words["summary_columns"][c] for c in ("episode", "title") + SUMMARY_COUNTS]
    rows = export_rows(data, words)
    out = {
        "job": data.get("job", ""),
        "tabs": {
            "findings": {"title": words["tabs"]["findings"],
                         "header": [words["columns"][c] for c in COLUMNS], "rows": rows},
            "summary": {"title": words["tabs"]["summary"], "header": summary_header,
                        "rows": summary_rows(data, words)},
        },
        "columns": {name: column_letter(name) for name in COLUMNS},
        "owner": {"user": [column_letter("judgment"), column_letter("note")], "assistant": [column_letter("reply")]},
        "judgments": judgments,
        "kinds": kinds,
        "format": {"episodes": episode_bands(rows, words)},
        "value_input": "USER_ENTERED",
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "findings": len(out["tabs"]["findings"]["rows"]),
                      "episodes": len(data["episodes"]), "out": args.out}, ensure_ascii=False))
    return 0


def readback_rows(payload) -> list[list[str]]:
    if isinstance(payload, dict):
        for key in ("values", "rows", "data"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list) or not payload or not all(isinstance(row, list) for row in payload):
        fail("readback needs a list of rows (the first row the header), or an object with a values list")
    return [[str(cell) if cell is not None else "" for cell in row] for row in payload]


def cmd_readback(args) -> int:
    data = load(args.ledger)
    words = sheet_text(data)
    try:
        payload = json.loads(Path(args.values).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {args.values}: {exc}")
    rows = readback_rows(payload)
    header = [cell.strip() for cell in rows[0]]
    names = {}
    for table in SHEET_TEXT.values():
        for name, label in table["columns"].items():
            names.setdefault(label, name)
    index = {names[label]: i for i, label in enumerate(header) if label in names}
    for required in ("id", "judgment"):
        if required not in index:
            fail(f"header has no {required} column (got {header})")
    statuses = {}
    for table in SHEET_TEXT.values():
        for status, label in table["judgments"].items():
            statuses.setdefault(label.lower(), status)
    by_id = {f["id"]: f for f in data["findings"]}
    counts = {status: 0 for status in STATUSES}
    unknown_ids, unknown_judgments, blank, recheck = [], [], [], []

    def cell(row, name):
        pos = index.get(name)
        return row[pos].strip() if pos is not None and pos < len(row) else ""

    for row in rows[1:]:
        fid = cell(row, "id")
        if not fid:
            continue
        finding = by_id.get(fid)
        if finding is None:
            unknown_ids.append(fid)
            continue
        for field in ("note", "reply"):  # a blank cell never erases what the ledger holds
            value = cell(row, field)
            if value:
                finding[field] = value
        judgment = cell(row, "judgment")
        if not judgment:
            blank.append(fid)
            continue
        status = statuses.get(judgment.lower())
        if status is None:
            unknown_judgments.append(f"{fid}: {judgment}")
            continue
        if status == "recheck" and finding.get("status") == "hold":
            status = "hold"  # the assistant already gave up on it; the same answer again changes nothing
        finding["status"] = status
        counts[status] += 1
        if status == "recheck":
            recheck.append({"id": fid, "episode": finding["episode"], "at": finding.get("at", ""),
                            "note": finding.get("note", "")})
    save(args.ledger, data)
    result = {"ok": not (unknown_ids or unknown_judgments), "counts": counts, "blank": blank,
              "recheck": recheck, "unknown_ids": unknown_ids, "unknown_judgments": unknown_judgments}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def finding_line(data: dict, finding: dict, box: bool, words: dict, episode: dict | None = None) -> str:
    at = str(finding.get("at") or "").strip()
    url = finding_url(finding, episode)
    if at and url:
        head = f"[{at}]({url}){words['gap']}"
    elif at:
        head = f"{at}{words['gap']}"
    elif url and finding["aspect"] == "thumbnail":
        head = f"[{words['thumb']}]({url}){words['gap']}"
    else:
        head = ""
    evidence = public_evidence(finding.get("evidence") or "")
    tail = words["evidence"].format(evidence) if evidence else ""
    prefix = "- [ ] " if box else "- "
    text = finding.get("ask") or finding["problem"]
    return f"{prefix}{head}{kind_label(data, finding)}{words['colon']}{text}{tail} `{finding['id']}`"


def cmd_sheet(args) -> int:
    data = load(args.ledger)
    errors = problems(data, final=False)
    if errors:
        fail("; ".join(errors))
    words = sheet_text(data)
    shown = live(data)
    out = [f"# {words['title']} — {data.get('job', '')}".rstrip(" —"), "", words["intro"], ""]
    sections = [(ALL, words["overall"], "", None, None)] + [
        (e["label"], e["label"], e.get("title", ""), e.get("checked"), e) for e in data["episodes"]
    ]
    for label, heading, title, checked, episode in sections:
        mine = sorted((f for f in shown if f["episode"] == label), key=first_time)
        listen = [item for item in data["listen"] if item["episode"] == label] if args.listen else []
        if label == ALL and not mine:
            continue
        url = video_url(episode) if episode else None
        out.append(f"## {heading} {f'[{title}]({url})' if title and url else title}".rstrip())
        if label != ALL:
            if checked is None:
                out.append(words["unrecorded"])
            else:
                names = {a["id"]: wording(a, data.get("sheet_language")) for a in aspects_of(data)}
                done = words["join"].join(names[a] for a in reviewed(data) if a in checked) or words["none"]
                todo = words["join"].join(names[a] for a in reviewed(data) if a not in checked) or words["none"]
                out.append(words["checked"].format(done=done, todo=todo))
        certain = [f for f in mine if f["certainty"] == "certain"]
        confirm = [f for f in mine if f["certainty"] == "confirm"]
        if not mine and not listen:
            out.append("- " + (words["clean_checked"] if checked else words["clean_unrecorded"]))
        if certain:
            out.append(f"### {words['certain']}")
            out.extend(finding_line(data, f, False, words, episode) for f in certain)
        if confirm:
            out.append(f"### {words['confirm']}")
            out.extend(finding_line(data, f, True, words, episode) for f in confirm)
        if listen:
            out.append(f"### {words['listen']}")
            for item in listen:
                done = item.get("result")
                mark = "x" if done else " "
                result = f"{words['gap']}→ {done}" if done else ""
                out.append(f"- [{mark}] {item['at']}{words['gap']}{item['term']}{result}")
        out.append("")
    Path(args.out).write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "findings": len(shown), "listen": len(data["listen"]), "out": args.out}, ensure_ascii=False))
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
    p = sub.add_parser("genres")
    p.set_defaults(func=cmd_genres)
    p = sub.add_parser("aspects")
    p.add_argument("genre")
    p.add_argument("--json", action="store_true", help="the catalog itself rather than a readable tree")
    p.set_defaults(func=cmd_aspects)
    p = sub.add_parser("init")
    p.add_argument("ledger")
    p.add_argument("--genre", required=True)
    p.add_argument("--aspects", help="comma-separated aspect ids to copy from the catalog (default: all)")
    p.add_argument("--job")
    p.add_argument("--language", help="the captions' BCP 47 tag")
    p.add_argument("--sheet-language", help="the user's BCP 47 tag")
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("upgrade")
    p.add_argument("ledger")
    p.add_argument("--genre", required=True)
    p.set_defaults(func=cmd_upgrade)
    p = sub.add_parser("focus")
    p.add_argument("ledger")
    p.add_argument("out")
    p.add_argument("--route", required=True, help="who looks: " + ", ".join(ROUTES))
    p.set_defaults(func=cmd_focus)
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
    p.add_argument("--aspect", help="aspect for every line, when the report's second cell is not one")
    p.add_argument("--kind", help="kind for every line (implies its aspect)")
    p.set_defaults(func=cmd_import)
    p = sub.add_parser("triage-speech")
    p.add_argument("ledger")
    p.add_argument("episode")
    p.add_argument("speech_dir", help="the hands' deliver directory for this episode's speech check")
    p.add_argument("--findings", default="findings.md")
    p.add_argument("--prosody", default="prosody.md")
    p.add_argument("--out", default="triage.md", help="kept lines, written into the speech directory")
    p.add_argument("--ignore", help="terms file: a script quote holding one of them is not a reading finding")
    p.add_argument("--max-jumps", type=int, default=2, help="delivery candidates kept per episode")
    p.add_argument("--pitch-jump", type=float, default=6.0, help="semitones against the previous segment")
    p.add_argument("--level-jump", type=float, default=8.0, help="dB against the previous segment")
    p.add_argument("--skip-head", type=int, default=20, help="seconds at the start no jump is taken from")
    p.add_argument("--weak", action="store_true", help="also keep a script number the ASR did not hear at all")
    p.set_defaults(func=cmd_triage_speech)
    p = sub.add_parser("ask-draft")
    p.add_argument("ledger")
    p.add_argument("out")
    p.set_defaults(func=cmd_ask_draft)
    p = sub.add_parser("ask-import")
    p.add_argument("ledger")
    p.add_argument("asks")
    p.set_defaults(func=cmd_ask_import)
    p = sub.add_parser("kinds")
    p.add_argument("ledger")
    p.set_defaults(func=cmd_kinds)
    p = sub.add_parser("export")
    p.add_argument("ledger")
    p.add_argument("out")
    p.set_defaults(func=cmd_export)
    p = sub.add_parser("readback")
    p.add_argument("ledger")
    p.add_argument("values")
    p.set_defaults(func=cmd_readback)
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
    p.add_argument("--listen", action="store_true", help="also list the caption terms to listen for")
    p.set_defaults(func=cmd_sheet)
    p = sub.add_parser("check")
    p.add_argument("ledger")
    p.add_argument("report")
    p.set_defaults(func=cmd_check)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
