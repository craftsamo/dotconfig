#!/usr/bin/env python3
"""Read-only, advisory inspection of UTF-8 plain text or limited Markdown.

Protocol: python inspect_text.py --request < request.json. No file input/output,
network, automatic installation, rewriting, or quality/AI-authorship judgments.
Python >=3.10; optional morphology versions are pinned in requirements.txt.

Original implementation informed by coji/natural-japanese v1.5.0, inspected at
21e632661a910bf97289c501089ad11eb8b4d85f (textcore.py, terms.py and selected
lint.py reading-load/structure code). No upstream implementation is vendored.

Scanner contract (NOT full CommonMark): preserve physical lines and character
offsets; recognize backtick/tilde fences of >=3 characters (including indented
fences), four-space/tab code outside lists, initial --- frontmatter through ---
or ..., HTML comments, quotes with lazy continuation, lists with indented/lazy
continuation, ATX and single-line setext headings, and delimiter-backed pipe
tables. Inline code uses matching backtick runs on one physical line; balanced
parenthesized link destinations, reference labels, images, autolinks and HTML
tags are masked. Reference definitions are excluded. Escaped punctuation is
not formatting. Multiline inline constructs, general HTML blocks, nested
container parsing and multiline setext headings are not implemented.

Reading-load is prose-only and sentence candidates end at physical line breaks
or Japanese/ASCII sentence punctuation. Thus soft-wrapped sentences can be
under-counted; unrelated lines are never concatenated. Terms use prose,
headings and list text; structure uses the same scope, including continuation
lines in its eligible-line denominator but counting only list marker lines.
Masked inline regions are hard boundaries for lexical/morphology candidates.
Excerpts are slices of the ORIGINAL line, not reconstructed text. Columns are
1-based Unicode character positions, not byte offsets. Every result requires
human context; an empty findings list is not evidence of writing quality.
"""

import hashlib
from importlib import metadata
import json
import re
import sys


VERSION = "1.0.0"
MODES = ("reading-load", "outline", "terms", "structure")
PINS = {"SudachiPy": "0.6.11", "sudachidict_core": "20260723"}
MAX_TEXT = 131072
MAX_REQUEST = 1048576
MAX_OUTPUT = 262144
CAPS = {"findings": 100, "outline": 200, "terms": 200}
EXCERPT = 240
MASK = "\x00"
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)")
LIST = re.compile(r"^([ \t]*)(?:[-+*]|[0-9]{1,9}[.)])(?:[ \t]+|$)")
TERM = re.compile(r"[\u30a1-\u30fa\u30fc]{3,}|(?<![A-Za-z0-9_])[A-Z]{2,}[0-9]*(?![A-Za-z0-9_])")
KANJI = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3005]{7,}")
BOLD = re.compile(r"(?<!\*)(?P<stars>\*{2,3})[^\s*](?:[^*]*?[^\s*])?(?P=stars)(?!\*)|(?<![\w_])__[^\s_](?:[^_]*?[^\s_])?__(?![\w_])")
ANGLE_OPEN = re.compile(r"<(?:/?[A-Za-z]|[A-Za-z]+:)")
SUMMARY = re.compile(r"^(?:まとめ|おわりに|終わりに|結論|総括|summary\b|conclusion\b)", re.I)


def _inline(raw, comment):
    """Mask in place by offset; parse code before comment markers inside code."""
    out = list(raw)
    runs = {}
    for match in re.finditer(r"`+", raw):
        runs.setdefault(len(match[0]), []).append((match.start(), match.end()))
    ends = {}
    run_ends = {start: end for positions in runs.values() for start, end in positions}
    for positions in runs.values():
        for left, right in zip(positions, positions[1:]):
            ends[left[0]] = right[1]
    i = 0
    no_angle_close = False
    while i < len(raw):
        end = i
        if comment or raw.startswith("<!--", i):
            close = raw.find("-->", i if comment else i + 4)
            end = len(raw) if close < 0 else close + 3
            comment = close < 0
        elif raw[i] == "\\" and i + 1 < len(raw) and raw[i + 1] in r"!\"#$%&'()*+,-./:;<=>?@[\]^_`{|}~":
            end = i + 2
        elif raw[i] == "`" and i in ends:
            end = ends[i]
        elif raw[i] == "`":
            # Skip the complete unmatched run, not a suffix of that run.
            i = run_ends.get(i, i + 1)
            continue
        elif raw.startswith("](", i):
            depth, end = 1, i + 2
            while end < len(raw) and depth:
                if raw[end] == "\\":
                    end += 2
                    continue
                if raw[end] == "(":
                    depth += 1
                elif raw[end] == ")":
                    depth -= 1
                end += 1
            end = min(end, len(raw))
        elif raw.startswith("][", i):
            close = raw.find("]", i + 2)
            end = len(raw) if close < 0 else close + 1
        elif raw.startswith("![", i):
            close = raw.find("]", i + 2)
            end = len(raw) if close < 0 else close
        elif not no_angle_close and raw[i] == "<" and ANGLE_OPEN.match(raw, i):
            close = raw.find(">", i + 1)
            if close >= 0:
                end = close + 1
            else:
                no_angle_close = True
        if end > i:
            out[i:end] = MASK * (end - i)
            i = end
        else:
            if raw[i] in "[]":
                out[i] = " "
            i += 1
    return "".join(out), comment


def _table_delimiter(text):
    cells = text.strip().strip("|").split("|")
    return len(cells) >= 2 and all(re.fullmatch(r"\s*:?-{3,}:?\s*", c) for c in cells)


def _scan(text):
    rows = []
    fence = None
    front = False
    comment = False
    quote = False
    list_indent = None
    list_blank = False
    for index, raw in enumerate(re.split(r"\r\n|\r|\n", text)):
        row = {"line": index + 1, "raw": raw, "text": "", "kind": "excluded", "level": 0}
        rows.append(row)
        if index == 0 and raw.strip() == "---":
            front = True
            continue
        if front:
            if raw.strip() in ("---", "..."):
                front = False
            continue
        if fence:
            match = FENCE.match(raw)
            if match and match[1][0] == fence[0] and len(match[1]) >= fence[1] and not match[2].strip():
                fence = None
            continue
        if not comment and re.match(r"^ {0,3}>", raw):
            quote = True
            continue
        if not raw.strip():
            quote = False
            list_blank = True
            continue
        if quote and not ATX.match(raw) and not LIST.match(raw) and not FENCE.match(raw):
            continue
        quote = False
        # A fence inside a comment is data; comment syntax inside a fence is data.
        match = FENCE.match(raw) if not comment else None
        if match:
            fence = (match[1][0], len(match[1]))
            continue
        indent = len(raw[:len(raw) - len(raw.lstrip(" \t"))].expandtabs(4))
        if not comment and indent >= (list_indent or 0) + 4:
            # Indented code must not open an HTML comment or become a list.
            continue
        clean, comment = _inline(raw, comment)
        if not clean.replace(MASK, " ").strip():
            continue
        if re.match(r"^ {0,3}\[[^\]]+\]:", raw):
            continue
        marker = LIST.match(clean)
        heading = ATX.match(clean)
        thematic = re.fullmatch(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})", clean)
        setext = re.fullmatch(r" {0,3}(?:=+|-+)[ \t]*", clean)
        if (thematic or setext) and list_indent is None:
            # Resolve setext against the previous eligible row in the second pass.
            row.update(kind="prose", text=clean)
            continue
        if marker:
            contained_fence = FENCE.match(raw[marker.end():])
            if contained_fence:
                fence = (contained_fence[1][0], len(contained_fence[1]))
                list_indent = len(raw[:marker.end()].expandtabs(4))
                list_blank = False
                row.update(kind="list", text=" " * len(raw))
                continue
            row["kind"] = "list"
            list_indent = len(raw[:marker.end()].expandtabs(4))
            list_blank = False
            clean = " " * marker.end() + clean[marker.end():]
        elif heading:
            row["kind"] = "heading"
            row["level"] = len(heading[1])
            clean = " " * heading.end() + clean[heading.end():]
            closing = re.search(r"[ \t]+#+[ \t]*$", clean)
            if closing:
                clean = clean[:closing.start()] + " " * (len(clean) - closing.start())
            list_indent = None
        elif list_indent is not None and (indent >= list_indent or not list_blank):
            row["kind"] = "list-continuation"
        elif raw.startswith("    ") or raw.startswith("\t"):
            continue
        else:
            row["kind"] = "prose"
            list_indent = None
        row["text"] = clean

    table = False
    for index, row in enumerate(rows):
        if row["kind"] == "prose" and _table_delimiter(row["text"]) and index and rows[index - 1]["kind"] == "prose" and "|" in rows[index - 1]["text"]:
            rows[index - 1]["kind"] = row["kind"] = "table"
            table = True
            continue
        if table and row["kind"] == "prose" and "|" in row["text"]:
            row["kind"] = "table"
            continue
        table = False
        if row["kind"] == "prose" and re.fullmatch(r" {0,3}(?:=+|-+)[ \t]*", row["text"]) and index and rows[index - 1]["kind"] == "prose":
            rows[index - 1]["kind"] = "heading"
            rows[index - 1]["level"] = 1 if "=" in row["text"] else 2
            row["kind"] = "excluded"
        elif row["kind"] == "prose" and re.fullmatch(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})", row["text"]):
            row["kind"] = "excluded"
    return rows


def _morphology(needed):
    dependencies = {name: {"required": pin, "actual": None} for name, pin in PINS.items()}
    for name in PINS:
        try:
            dependencies[name]["actual"] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    info = {"available": False, "reason": "not_requested", "packages": dependencies}
    if not needed:
        return None, info
    if any(item["required"] != item["actual"] for item in dependencies.values()):
        info["reason"] = "missing_or_version_mismatch"
        return None, info
    try:
        from sudachipy import Dictionary

        tokenizer = Dictionary(dict="core").create()
    except Exception:
        info["reason"] = "initialization_failed"
        return None, info
    info.update(available=True, reason=None)
    return tokenizer, info


def _base(text=None):
    return {
        "status": "error", "schema_version": 1,
        "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None,
        "inspector_version": VERSION, "executed": [], "unverified": [],
        "findings": [], "outline": [], "terms": [], "structure": {},
        "truncation": {"applied": False, "counts": {}, "excerpt_clipped": 0, "term_clipped": 0, "output_budget_dropped": 0},
        "dependencies": {}, "error": None,
        "interpretation": "Advisory candidates only. No findings does not establish writing quality.",
        "limitations": ["Limited Markdown, not full CommonMark; see module docstring.", "Sentence candidates stop at physical line breaks; soft wraps may under-count.", "Summary headings use lexical prefixes, not semantic classification."],
    }


def _serialize(report):
    return json.dumps(report, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def _finish(report):
    truncation = report["truncation"]
    for key, cap in CAPS.items():
        total = len(report[key])
        report[key] = report[key][:cap]
        truncation["counts"][key] = {"total": total, "returned": len(report[key]), "omitted": total - len(report[key])}
    # Escaping controls and non-BMP text can exceed simple character estimates.
    # Drop deterministic tail entries until the actual UTF-8 wire size fits.
    while len(_serialize(report)) >= MAX_OUTPUT - 256:
        key = max(CAPS, key=lambda name: len(report[name]))
        if not report[key]:
            raise RuntimeError("Report metadata exceeds output budget")
        report[key].pop()
        count = truncation["counts"][key]
        count["returned"] -= 1
        count["omitted"] += 1
        truncation["output_budget_dropped"] += 1
    truncation["applied"] = bool(truncation["excerpt_clipped"] or truncation["term_clipped"] or any(c["omitted"] for c in truncation["counts"].values()))
    if report["status"] != "error":
        report["status"] = "partial" if report["unverified"] or truncation["applied"] else "ok"
    return report


def inspect_text(text, modes=None):
    """Return schema v1; invalid API arguments raise ValueError, never truncate input."""
    if type(text) is not str:
        raise ValueError("text must be a string")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("text must contain valid Unicode scalars") from exc
    if size > MAX_TEXT:
        raise ValueError("text exceeds 131072 UTF-8 bytes")
    if modes is None:
        modes = list(MODES)
    if type(modes) is not list or any(type(m) is not str or m not in MODES for m in modes):
        raise ValueError("modes must be a list of supported mode strings")
    if len(set(modes)) != len(modes):
        raise ValueError("modes must not contain duplicates")
    report = _base(text)
    report["status"] = "ok"
    tokenizer, report["dependencies"] = _morphology(bool(set(modes) & {"reading-load", "terms"}))
    checks = {"reading-load": ["sentence_length", "kanji_run"], "outline": ["outline"], "terms": ["term_inventory"], "structure": ["structure"]}
    for mode in MODES:
        if mode in modes:
            report["executed"].extend(checks[mode])
    for mode, check in (("reading-load", "no_particle_chain"), ("reading-load", "double_negative"), ("terms", "proper_noun_inventory")):
        if mode in modes:
            if tokenizer is not None:
                report["executed"].append(check)
            else:
                report["unverified"].append({"check": check, "reason": report["dependencies"]["reason"]})

    def excerpt(raw, start=0, end=None):
        value = raw[start:end]
        if len(value) > EXCERPT:
            report["truncation"]["excerpt_clipped"] += 1
        return value[:EXCERPT]

    def finding(rule, row, start, end, reason):
        report["findings"].append({"rule_id": rule, "line": row["line"], "column": start + 1, "excerpt": excerpt(row["raw"], start, end), "reason": reason, "requires_context": True})

    rows = _scan(text)
    inventory = {}
    previous_prose = False
    counts = {"eligible_lines": 0, "eligible_characters": 0, "bold_spans": 0, "bold_lines": 0, "list_lines": 0, "headings": 0, "summary_headings": 0}
    for row in rows:
        kind, clean, raw = row["kind"], row["text"], row["raw"]
        if kind not in ("prose", "heading", "list", "list-continuation"):
            previous_prose = False
            continue
        visible = clean.replace(MASK, " ")
        if "outline" in modes and (kind == "heading" or kind == "prose" and not previous_prose):
            start = len(visible) - len(visible.lstrip())
            report["outline"].append({"kind": "heading" if kind == "heading" else "paragraph", "level": row["level"], "line": row["line"], "column": start + 1, "excerpt": excerpt(raw, start), "requires_context": True})
        previous_prose = kind == "prose"
        bold_spans = list(BOLD.finditer(clean))
        if "structure" in modes:
            counts["eligible_lines"] += 1
            counts["eligible_characters"] += sum(not c.isspace() and c != MASK for c in clean)
            bold = len(bold_spans)
            counts["bold_spans"] += bold
            counts["bold_lines"] += bool(bold)
            counts["list_lines"] += kind == "list"
            counts["headings"] += kind == "heading"
            counts["summary_headings"] += kind == "heading" and bool(SUMMARY.match(visible.strip().strip("*_")))
        lexical = list(clean)
        for span in bold_spans:
            width = len(span["stars"]) if span["stars"] else 2
            lexical[span.start():span.start() + width] = " " * width
            lexical[span.end() - width:span.end()] = " " * width
        clean = "".join(lexical)
        candidates = []
        if "terms" in modes:
            candidates.extend((m.start(), m.end(), "acronym" if m[0].isascii() else "katakana") for m in TERM.finditer(clean))
        # Keep masked gaps and sentence boundaries intact. Sudachi has a ~49KiB
        # per-tokenization limit; oversized segments are explicitly unverified.
        for segment in re.finditer(r"[^\x00。！？.!?]+", clean):
            start, end = segment.span()
            piece = segment[0]
            relevant = "terms" in modes or "reading-load" in modes and kind == "prose"
            tokens = []
            if tokenizer is not None and relevant:
                if len(piece.encode("utf-8")) > 40000:
                    note = {"check": "morphology_segment", "line": row["line"], "reason": "segment_exceeds_40000_utf8_bytes"}
                    if note not in report["unverified"]:
                        report["unverified"].append(note)
                else:
                    try:
                        tokens = list(tokenizer.tokenize(piece))
                    except Exception as exc:
                        raise RuntimeError("Morphology execution failed") from exc
            if "terms" in modes:
                candidates.extend((start + token.begin(), start + token.end(), "proper_noun") for token in tokens if token.part_of_speech()[:2] == ("名詞", "固有名詞"))
            if "reading-load" not in modes or kind != "prose":
                continue
            for match in KANJI.finditer(piece):
                finding("kanji_run", row, start + match.start(), start + match.end(), "Seven or more adjacent kanji: check word boundaries in context; retain proper nouns and established terms.")
            no_chain = []
            negatives = []
            for token_index, token in enumerate(tokens):
                pos = token.part_of_speech()
                if pos[0] in ("補助記号", "空白"):
                    no_chain = []
                    negatives = []
                if token.surface() == "の" and pos[:2] == ("助詞", "格助詞"):
                    if no_chain and token_index - no_chain[-1][0] > 3:
                        no_chain = []
                    no_chain.append((token_index, token))
                    if len(no_chain) == 3:
                        finding("no_particle_chain", row, start + no_chain[0][1].begin(), start + token.end(), "Three nearby genitive particles: check attachment in context; a chain is not necessarily a defect.")
                if token.dictionary_form() in ("ない", "ぬ", "ず") and pos[0] in ("助動詞", "形容詞"):
                    if negatives and token_index - negatives[-1][0] <= 8:
                        finding("double_negative", row, start + negatives[-1][1].begin(), start + token.end(), "Nearby negations may be nested. Preserve modality, reservations, conditions and obligations; do not automatically turn them into an affirmative.")
                        negatives = []
                    else:
                        negatives = [(token_index, token)]
        if "reading-load" in modes and kind == "prose":
            for sentence in re.finditer(r"[^。！？.!?]+", clean):
                length = sum(not c.isspace() and c != MASK for c in sentence[0])
                if length > 90:
                    start = sentence.start()
                    while start < sentence.end() and (clean[start].isspace() or clean[start] == MASK):
                        start += 1
                    finding("sentence_length", row, start, sentence.end(), f"Sentence candidate has {length} visible non-whitespace characters (>90); review its relationships in context, not length alone.")
        # One occurrence per exact span even when morphology and regex agree.
        seen_spans = set()
        for start, end, category in sorted(candidates):
            if (start, end) in seen_spans:
                continue
            seen_spans.add((start, end))
            term = raw[start:end]
            if term not in inventory:
                if len(term) > EXCERPT:
                    report["truncation"]["term_clipped"] += 1
                inventory[term] = {"term": term[:EXCERPT], "kind": category, "line": row["line"], "column": start + 1, "count": 0, "excerpt": excerpt(raw, start, end), "requires_context": True}
            inventory[term]["count"] += 1
    report["terms"] = list(inventory.values())
    report["findings"].sort(key=lambda f: (f["line"], f["column"], f["rule_id"]))
    if "structure" in modes:
        proportions = {}
        for numerator, denominator in (("bold_lines", "eligible_lines"), ("list_lines", "eligible_lines"), ("headings", "eligible_lines"), ("summary_headings", "headings")):
            proportions[numerator] = {"numerator": counts[numerator], "denominator": counts[denominator], "denominator_name": denominator, "value": counts[numerator] / counts[denominator] if counts[denominator] else None}
        report["structure"] = {"counts": counts, "proportions": proportions, "scope": "Prose, headings, list markers and list continuations only; inline exclusions removed. Characters exclude whitespace but include remaining Markdown markers.", "requires_context": True}
    return _finish(report)


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON field")
        obj[key] = value
    return obj


def main():
    text = None
    try:
        if sys.argv[1:] != ["--request"]:
            raise ValueError("usage: python inspect_text.py --request")
        data = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(data) > MAX_REQUEST:
            raise ValueError("request exceeds 1048576 bytes")
        request = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON number")))
        if type(request) is not dict or set(request) - {"text", "modes"} or "text" not in request:
            raise ValueError("request must contain text and optionally modes, with no other fields")
        if "modes" in request and type(request["modes"]) is not list:
            raise ValueError("modes must be a list")
        if type(request["text"]) is str:
            request["text"].encode("utf-8")
            text = request["text"]
        report = inspect_text(request["text"], request.get("modes"))
        code = 0
    except (ValueError, UnicodeError, RecursionError):
        report = _finish(_base(text))
        report["error"] = {"code": "invalid_request", "message": "Invalid UTF-8 JSON request, fields, modes, arguments, or input size; see protocol contract."}
        code = 1
    except Exception:
        report = _finish(_base(text))
        report["error"] = {"code": "runtime_failure", "message": "Inspector execution failed; no complete result is available."}
        code = 1
    sys.stdout.buffer.write(_serialize(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
