"""Document skeleton (headings, paragraph leads, list blocks) and heading statistics.

The skeleton is material for judging order and coverage; no findings are emitted.
"""

from collections import Counter
import re
from statistics import pstdev

from .. import catalog
from ..document import MASK
from ..report import EXCERPT

MODE = "outline"
MORPHOLOGY = True
LIST_KINDS = ("list", "list-continuation")
TEMPLATE_HIT_CAP = 20


def run(inspection):
    data = catalog.load("outline")
    headings = _headings(inspection.doc)
    entries = [_heading_entry(inspection, heading) for heading in headings]
    entries += _lead_entries(inspection)
    entries += _bullet_entries(inspection.doc)
    entries.sort(key=lambda entry: (entry["line"], entry["column"]))
    inspection.section("outline", entries)
    inspection.section("heading_stats", _heading_stats(inspection, headings, data))
    inspection.executed("outline", "heading_stats")


def _headings(doc):
    found = []
    for row in doc.rows_of(("heading",)):
        visible = row.visible
        text = visible.strip()
        found.append({
            "row": row,
            "line": row.line,
            "level": row.level,
            "column": len(visible) - len(visible.lstrip()) + 1 if text else 1,
            "text": text,
            "literal": row.literal.replace(MASK, " ").strip(),
        })
    return found


def _entry(kind, level, line, column, excerpt):
    return {
        "kind": kind, "level": level, "line": line, "column": column,
        "excerpt": excerpt, "requires_context": True,
    }


def _heading_entry(inspection, heading):
    excerpt = inspection.clip(heading["text"])
    return _entry("heading", heading["level"], heading["line"], heading["column"], excerpt)


def _lead_entries(inspection):
    doc = inspection.doc
    first_sentence = {}
    for sentence in doc.sentences():
        first_sentence.setdefault(sentence.line, sentence)
    entries = []
    for paragraph in doc.paragraphs():
        sentence = first_sentence.get(paragraph[0].line)
        if sentence is None:
            continue
        start = _lead_start(sentence)
        excerpt = sentence.row.raw[start:_lead_end(sentence)].strip()
        entries.append(_entry("lead", None, sentence.line, start + 1, inspection.clip(excerpt)))
    return entries


def _code_spans(row, start, end):
    """Masked inline-code spans lying inside ``row.text[start:end]``."""
    return [
        (match.start(), match.end()) for match in re.finditer(f"{MASK}+", row.text[start:end])
        if row.masked_code_at(start + match.start())
    ]


def _lead_start(sentence):
    """Include inline code that opens the sentence; other masked spans stay out."""
    spans = _code_spans(sentence.row, 0, sentence.start)
    return spans[0][0] if spans else sentence.start


def _lead_end(sentence):
    """End after the sentence mark, or after trailing inline code when there is no mark."""
    visible = sentence.row.visible
    # Only whitespace or masked spans separate a trimmed sentence from its mark.
    tail = visible[sentence.end:]
    gap = len(tail) - len(tail.lstrip())
    if gap < len(tail):
        return sentence.end + gap + 1
    spans = _code_spans(sentence.row, sentence.end, len(visible))
    return sentence.end + spans[-1][1] if spans else sentence.end


def _bullet_entries(doc):
    """One entry per list block; blank lines inside a loose list do not split it."""
    entries, block, gap = [], [], False
    for row in doc.rows:
        if row.kind in LIST_KINDS and block and gap and not _continues(block, row):
            entries.append(_bullet_entry(block))
            block = []
        if row.kind in LIST_KINDS:
            block.append(row)
            gap = False
        elif block and not row.raw.strip():
            gap = True
        elif block:
            entries.append(_bullet_entry(block))
            block, gap = [], False
    if block:
        entries.append(_bullet_entry(block))
    return entries


def _continues(block, row):
    return row.kind == "list-continuation" or _marker_type(row) == _marker_type(block[0])


def _marker_type(row):
    return "ordered" if row.raw.lstrip()[:1].isdigit() else "bullet"


def _bullet_entry(block):
    first = block[0]
    items = sum(row.kind == "list" for row in block)
    column = len(first.raw) - len(first.raw.lstrip()) + 1
    return _entry("bullets", None, first.line, column, f"(箇条書き {items} 項目)")


def _heading_stats(inspection, headings, data):
    analysis = _analyze(inspection, headings, data)
    levels = sorted({heading["level"] for heading in headings})
    by_level = {}
    for level in levels:
        indexes = [i for i, heading in enumerate(headings) if heading["level"] == level]
        subset = None if analysis is None else [analysis[i] for i in indexes]
        by_level[str(level)] = _group([headings[i] for i in indexes], subset, data)
    return {
        "total_headings": len(headings),
        "level_distribution": {str(level): sum(h["level"] == level for h in headings) for level in levels},
        "by_level": by_level,
        "overall": _group(headings, analysis, data),
    }


def _analyze(inspection, headings, data):
    """Per-heading (nominal ending, POS signature), or None when Sudachi is missing."""
    if not headings:
        inspection.executed("heading_morphology")
        return []
    if not inspection.needs_morphology("heading_morphology"):
        return None
    results = []
    for heading in headings:
        tokens = inspection.tokens("heading_morphology", heading["line"], heading["text"]) or []
        results.append((_nominal_ending(tokens, data), _signature(tokens, data)))
    return results


def _nominal_ending(tokens, data):
    trailing = set(data["trailing_symbol_pos"])
    content = list(tokens)
    while content and content[-1].pos[0] in trailing:
        content.pop()
    return bool(content) and content[-1].pos[0] == data["nominal_pos"]


def _signature(tokens, data):
    kept = set(data["signature_pos"])
    return tuple(token.pos[0] for token in tokens if token.pos[0] in kept)


def _group(headings, analysis, data):
    count = len(headings)
    if count == 0:
        return {
            "count": 0, "length_mean": 0.0, "length_cv": 0.0, "nominal_ending_ratio": 0.0,
            "dominant_pos_signature_ratio": 0.0, "template_hits": [], "template_hit_count": 0,
            "structural_pattern_ratio": 0.0,
        }
    lengths = [len(heading["text"]) for heading in headings]
    average = sum(lengths) / count
    cv = pstdev(lengths) / average if average > 0 and count > 1 else 0.0
    nominal = dominant = None
    if analysis is not None:
        nominal = round(sum(ending for ending, _ in analysis) / count, 3)
        signatures = Counter(signature for _, signature in analysis if signature)
        dominant = round(max(signatures.values()) / count, 3) if signatures else 0.0
    structural = sum(_structural(heading["literal"], data) for heading in headings)
    hits = [hit for hit in (_template_hit(heading, data) for heading in headings) if hit]
    return {
        "count": count,
        "length_mean": round(average, 2),
        "length_cv": round(cv, 3),
        "nominal_ending_ratio": nominal,
        "dominant_pos_signature_ratio": dominant,
        "template_hits": hits[:TEMPLATE_HIT_CAP],
        "template_hit_count": len(hits),
        "structural_pattern_ratio": round(structural / count, 3),
    }


def _template_hit(heading, data):
    stripped = re.sub(data["template_prefix_strip"], "", heading["text"]).strip().lower()
    for word in data["template_heading_words"]:
        if stripped.startswith(word):
            return {"line": heading["line"], "text": heading["text"][:EXCERPT], "matched": word}
    return None


def _structural(text, data):
    return any(re.search(pattern, text) for pattern in data["structural_patterns"].values())
