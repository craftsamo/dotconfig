"""Inventory of terms a reader may need explained: acronyms, katakana words, proper nouns.

Only prose, headings and list text are scanned; code, URLs, tables and quotes are
masked or excluded, also for occurrence counts.
"""

import re

from .. import catalog
from ..document import TEXT_KINDS
from ..report import EXCERPT

MODE = "terms"
MORPHOLOGY = True
_SEGMENT = re.compile(r"[^。！？]+")
_PAREN_AFTER = re.compile(r"[ \t]?[(（]")


def run(inspection):
    data = catalog.load("terms")
    rows = inspection.doc.rows_of(TEXT_KINDS)
    inspection.executed("term_inventory")
    use_morphology = inspection.needs_morphology("proper_noun_inventory")
    first_seen = {}
    for row in rows:
        for start, end, kind in _candidates(inspection, row, data, use_morphology):
            first_seen.setdefault(row.visible[start:end], (row, start, end, kind))
    by_line = {row.line: row for row in rows}
    # Terms never contain a newline, so counting in the joined text cannot cross rows.
    corpus = "\n".join(row.visible for row in rows)
    entries = [_entry(inspection, corpus, by_line, term, *found, data) for term, found in first_seen.items()]
    entries.sort(key=lambda entry: (entry["line"], entry["column"]))
    inspection.section("terms", entries)


def _candidates(inspection, row, data, use_morphology):
    visible = row.visible
    found = [(m.start(), 0, m.end(), "acronym") for m in re.finditer(data["acronym"], visible)]
    for segment in _SEGMENT.finditer(visible):
        tokens = None
        if use_morphology and segment[0].strip():
            tokens = inspection.tokens("proper_noun_inventory", row.line, segment[0])
        if tokens is None:
            matches = re.finditer(data["katakana_fallback"], segment[0])
            spans = ((m.start(), m.end(), "katakana") for m in matches)
        else:
            spans = _walk(tokens, data)
        found.extend((segment.start() + start, 1, segment.start() + end, kind) for start, end, kind in spans)
    return [(start, end, kind) for start, _, end, kind in sorted(found)]


def _walk(tokens, data):
    """Katakana runs (minimum length) and proper-noun runs from Sudachi tokens."""
    katakana = re.compile(data["katakana_surface"])
    latin = re.compile(data["latin_name_surface"])

    def is_katakana(token):
        return katakana.fullmatch(token.surface) is not None

    def is_name(token):
        if token.pos[:2] == ("名詞", "固有名詞"):
            return True
        return len(token.surface) >= 2 and latin.fullmatch(token.surface) is not None

    index = 0
    while index < len(tokens):
        token = tokens[index]
        test = is_katakana if is_katakana(token) else is_name if is_name(token) else None
        if test is None:
            index += 1
            continue
        last = index
        while last + 1 < len(tokens) and test(tokens[last + 1]):
            last += 1
        span = (token.begin, tokens[last].end)
        if test is is_name:
            yield (*span, "proper_noun")
        elif span[1] - span[0] >= data["katakana_min_length"]:
            yield (*span, "katakana")
        index = last + 1


def _entry(inspection, corpus, by_line, term, row, start, end, kind, data):
    count = corpus.count(term)
    if len(term) > EXCERPT:
        inspection.report["truncation"]["term_clipped"] += 1
    window = data["context_window"]
    context = row.raw[max(0, start - window):end + window].strip()
    return {
        "term": term[:EXCERPT],
        "kind": kind,
        "line": row.line,
        "column": start + 1,
        "count": count,
        "has_gloss_hint": _gloss_hint(by_line, row, start, end, data),
        "context": inspection.clip(context),
        "requires_context": True,
    }


def _gloss_hint(by_line, row, start, end, data):
    if _PAREN_AFTER.match(row.visible, end):
        return True
    previous, following = by_line.get(row.line - 1), by_line.get(row.line + 1)
    before = previous.visible + "\n" if previous else ""
    text = before + row.visible + ("\n" + following.visible if following else "")
    width = data["gloss_window"]
    window = text[max(0, len(before) + start - width):len(before) + end + width]
    return any(marker in window for marker in data["gloss_markers"])
