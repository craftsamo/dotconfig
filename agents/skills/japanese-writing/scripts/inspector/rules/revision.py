"""Original → rewrite comparison: changed markers, words, structure, logic and endings.

Both texts go through ``Document`` so code, URLs and markup never count as words.
Positions always refer to the rewritten text.
"""

from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from .. import catalog
from ..document import TEXT_KINDS
from .expression import KIND_LABELS, STANCE_LABELS, UNIT_KINDS, ending_units, stance_flags

MODE = "revision"
MORPHOLOGY = False

DATA = catalog.load("revision")
LIST_CAP = 100
FINDING_CAP = 60
SPAN_TEXT = 120
# Character-level diffs run only below this length product (sentence blocks, ending pairs).
PIECE_DIFF_LIMIT = 250_000
CHAR_DIFF_LIMIT = 100_000
CHUNK_CHARS = 800
MATCH_CANDIDATES = 8
COMMON_BIGRAM = 200
CHANGE_RATIO = 0.45
PARAGRAPH_KINDS = ("prose", "list", "list-continuation")

_MARKERS = [(kind, label, re.compile(pattern, re.M)) for kind, label, pattern in DATA["markers"]]
_CONTENT = re.compile(DATA["content_word"])
_LOGIC = [(kind, re.compile(pattern)) for kind, pattern in DATA["logic"]]
_EMPHASIS = re.compile(r"\*\*|__")
_PIECE = re.compile(r"[^。！？\n]+[。！？\n]*|[。！？\n]+")
_STANCE_CONFLICTS = {
    "advice": ("action",),
    "rule": ("recommendation", "evaluation"),
    "explanation": ("recommendation", "request"),
}
# Lower values sort first when findings exceed the cap.
_PRIORITY = {
    "lost_content_word": 0, "marker_count_change": 1, "stance_ending_change": 2,
    "new_content_word": 3, "logic_candidate": 4,
}
_LOGIC_REASONS = {
    "leading_connective": "文頭の接続語「{0}」が前の文との関係に合っているか確認する (revision.md R4)",
    "topic_mo": "文頭近くの「{0}」の「も」が何と並ぶのか、前の文から読み取れるか確認する (revision.md R4)",
    "preview_only": "予告だけで中身のない文の候補 ({0})。続く内容とまとめられるか確認する (revision.md R4)",
    "leading_demonstrative": "文頭の指示語「{0}」が指す内容が直前の文にあるか確認する (revision.md R4)",
}


@dataclass
class Flat:
    """Normalized text joined by newlines, with (line, 0-based column) per character."""

    text: str
    positions: list

    def locate(self, index):
        if not self.text:
            return 1, 1
        line, column = self.positions[min(max(index, 0), len(self.text) - 1)]
        return line, column + 1


def flatten(doc):
    chars, positions = [], []
    for row in doc.rows_of(TEXT_KINDS):
        visible = row.visible
        removed = {i for m in _EMPHASIS.finditer(visible) for i in range(m.start(), m.end())}
        line_chars, line_positions, gap = [], [], None
        for i, char in enumerate(visible):
            if i in removed:
                continue
            if char.isspace():
                if line_chars and gap is None:
                    gap = i
                continue
            if gap is not None:
                line_chars.append(" ")
                line_positions.append((row.line, gap))
                gap = None
            line_chars.append(char)
            line_positions.append((row.line, i))
        if not line_chars:
            continue
        if chars:
            chars.append("\n")
            positions.append((positions[-1][0], positions[-1][1] + 1))
        chars.extend(line_chars)
        positions.extend(line_positions)
    return Flat("".join(chars), positions)


def _pieces(text):
    return _PIECE.findall(text)


def char_opcodes(a, b):
    """Character opcodes, diffing sentence pieces first so large texts stay tractable."""
    if a == b:
        return [("equal", 0, len(a), 0, len(b))] if a else []
    a_pieces, b_pieces = _pieces(a), _pieces(b)
    a_start, b_start = _starts(a_pieces), _starts(b_pieces)
    head = 0
    while head < min(len(a_pieces), len(b_pieces)) and a_pieces[head] == b_pieces[head]:
        head += 1
    tail = 0
    while (tail < min(len(a_pieces), len(b_pieces)) - head
           and a_pieces[-1 - tail] == b_pieces[-1 - tail]):
        tail += 1
    i_end, j_end = len(a_pieces) - tail, len(b_pieces) - tail
    opcodes = []
    if head:
        opcodes.append(("equal", 0, a_start[head], 0, b_start[head]))
    middle_a, middle_b = a_pieces[head:i_end], b_pieces[head:j_end]
    if len(middle_a) * len(middle_b) > PIECE_DIFF_LIMIT:
        # Piece matching is quadratic on repetitive text; fall back to proportional chunks.
        blocks = [("replace", head, i_end, head, j_end)]
    else:
        blocks = [(t, head + i1, head + i2, head + j1, head + j2) for t, i1, i2, j1, j2
                  in SequenceMatcher(None, middle_a, middle_b, autojunk=False).get_opcodes()]
    for tag, i1, i2, j1, j2 in blocks:
        x1, x2, y1, y2 = a_start[i1], a_start[i2], b_start[j1], b_start[j2]
        if tag == "equal":
            opcodes.append((tag, x1, x2, y1, y2))
        elif (x2 - x1) * (y2 - y1) <= CHAR_DIFF_LIMIT:
            opcodes.extend(_char_diff(a, b, x1, x2, y1, y2))
        else:
            opcodes.extend(_chunked_diff(a, b, a_start[i1:i2 + 1], b_start[j1:j2 + 1]))
    if tail:
        opcodes.append(("equal", a_start[i_end], len(a), b_start[j_end], len(b)))
    return opcodes


def _char_diff(a, b, x1, x2, y1, y2, junk=False):
    if x1 == x2 and y1 == y2:
        return []
    if x1 == x2 or y1 == y2:
        tag = "insert" if x1 == x2 else "delete"
        return [(tag, x1, x2, y1, y2)]
    # Without the junk heuristic, repetitive text makes matching blocks cubic;
    # chunks of large blocks accept the coarser diff to stay within the deadline.
    inner = SequenceMatcher(None, a[x1:x2], b[y1:y2], autojunk=junk).get_opcodes()
    return [(t, x1 + p1, x1 + p2, y1 + q1, y1 + q2) for t, p1, p2, q1, q2 in inner]


def _chunked_diff(a, b, a_bounds, b_bounds):
    """Split a large changed block at proportional sentence boundaries and diff each chunk."""
    opcodes = []
    x0, y0, a_end, b_end = a_bounds[0], b_bounds[0], a_bounds[-1], b_bounds[-1]
    while x0 < a_end or y0 < b_end:
        x1 = next((p for p in a_bounds if p >= x0 + CHUNK_CHARS), a_end)
        if x1 == a_end:
            y1 = b_end
        else:
            target = y0 + (x1 - x0) * (b_end - y0) / (a_end - x0)
            y1 = min((p for p in b_bounds if p >= y0), key=lambda p: (abs(p - target), p))
        opcodes.extend(_char_diff(a, b, x0, x1, y0, y1, junk=True))
        x0, y0 = x1, y1
    return opcodes


def _starts(pieces):
    starts = [0]
    for piece in pieces:
        starts.append(starts[-1] + len(piece))
    return starts


def _mapper(opcodes, side):
    """Map an index on one side of ``opcodes`` to the other side in O(log n)."""
    src, dst = (1, 3) if side == "old" else (3, 1)
    starts = [op[src] for op in opcodes]
    fallback = opcodes[-1][dst + 1] if opcodes else 0

    def mapped(index):
        # Opcodes tile each side contiguously, so the last one starting at or
        # before ``index`` is the only one that can contain it.
        slot = bisect_right(starts, index) - 1
        if slot < 0 or index >= opcodes[slot][src + 1]:
            return fallback
        op = opcodes[slot]
        return op[dst] + (index - op[src]) if op[0] == "equal" else op[dst]
    return mapped


def _inside(blocks, start, end):
    """True when [start, end) lies inside one of the sorted, disjoint ``blocks``."""
    slot = bisect_right(blocks, (start, float("inf"))) - 1
    return slot >= 0 and blocks[slot][0] <= start and end <= blocks[slot][1]


def _unit_starts(flat, units):
    """Index of each unit's first character in ``flat`` (None when not found)."""
    where = {}
    for index, position in enumerate(flat.positions):
        where.setdefault(position, index)
    return [
        next((where[(u.line, c)] for c in range(u.column - 1, u.column + 3) if (u.line, c) in where), None)
        for u in units
    ]


def _trim(text):
    return text if len(text) <= SPAN_TEXT else text[:SPAN_TEXT // 2 - 1] + "…" + text[-SPAN_TEXT // 2:]


class Comparison:
    def __init__(self, inspection):
        self.inspection = inspection
        self.stance = inspection.stance
        self.old = flatten(inspection.original)
        self.new = flatten(inspection.doc)
        self.opcodes = char_opcodes(self.old.text, self.new.text)
        self.equal_old = [(op[1], op[2]) for op in self.opcodes if op[0] == "equal"]
        self.equal_new = [(op[3], op[4]) for op in self.opcodes if op[0] == "equal"]
        self.to_new = _mapper(self.opcodes, "old")
        self.to_old = _mapper(self.opcodes, "new")
        self.omitted = {}
        self.findings = []

    def cap(self, name, items):
        if len(items) > LIST_CAP:
            self.omitted[name] = self.omitted.get(name, 0) + len(items) - LIST_CAP
        return items[:LIST_CAP]

    def add(self, rule, index_or_position, excerpt, reason):
        line, column = (
            index_or_position if isinstance(index_or_position, tuple) else self.new.locate(index_or_position)
        )
        self.findings.append((_PRIORITY[rule], line, column, rule, excerpt, reason))

    # ---- markers ----

    def markers(self):
        changed = []
        for kind, label, regex in _MARKERS:
            old_hits = [m[0] for m in regex.finditer(self.old.text)]
            new_hits = [m[0] for m in regex.finditer(self.new.text)]
            if len(old_hits) == len(new_hits):
                continue
            changed.append({
                "kind": kind, "original": len(old_hits), "rewrite": len(new_hits),
                "original_hits": self.cap(f"markers.{kind}.original_hits", old_hits),
                "rewrite_hits": self.cap(f"markers.{kind}.rewrite_hits", new_hits),
            })
            if kind in DATA["reported_markers"]:
                self._marker_finding(kind, label, regex, len(old_hits), len(new_hits))
        return changed

    def _marker_finding(self, kind, label, regex, before, after):
        places = [m.start() for m in regex.finditer(self.new.text) if not _inside(self.equal_new, *m.span())]
        places += [
            self.to_new(m.start()) for m in regex.finditer(self.old.text)
            if not _inside(self.equal_old, *m.span())
        ]
        self.add(
            "marker_count_change", min(places) if places else (1, 1), f"{label} {before} → {after}",
            f"{label}の表現が {before} 件から {after} 件に変わった。言い換えで主張の強さや確度が"
            "変わっていないか確認する (revision.md R1)",
        )

    # ---- content words ----

    def words(self):
        new_first, lost_first = {}, {}
        for match in _CONTENT.finditer(self.new.text):
            if match[0] not in self.old.text:
                new_first.setdefault(match[0], match.start())
        for match in _CONTENT.finditer(self.old.text):
            if match[0] not in self.new.text:
                lost_first.setdefault(match[0], match.start())
        for word, index in lost_first.items():
            self.add(
                "lost_content_word", self.to_new(index), word,
                f"元の文章の語「{word}」が書き直し後に見当たらない。意味や情報が落ちていないか"
                "確認する (revision.md R1, R2)",
            )
        for word, index in new_first.items():
            self.add(
                "new_content_word", index, word,
                f"元の文章にない語「{word}」が加わった。元にない情報や解釈を足していないか"
                "確認する (revision.md R2)",
            )
        return self.cap("new_words", sorted(new_first)), self.cap("lost_words", sorted(lost_first))

    # ---- structure ----

    def structure(self):
        old_doc, new_doc = self.inspection.original, self.inspection.doc
        notes = []
        old_lists, new_lists = len(old_doc.rows_of(("list",))), len(new_doc.rows_of(("list",)))
        if old_lists and not new_lists:
            notes.append({"kind": "list_removed", "detail": f"{old_lists} → 0"})
        old_paras = len(old_doc.paragraphs(PARAGRAPH_KINDS))
        new_paras = len(new_doc.paragraphs(PARAGRAPH_KINDS))
        if new_paras < old_paras:
            notes.append({"kind": "paragraphs_reduced", "detail": f"{old_paras} → {new_paras}"})
        old_count, new_count = len(old_doc.sentences(UNIT_KINDS)), len(new_doc.sentences(UNIT_KINDS))
        if old_count != new_count:
            notes.append({"kind": "sentences_changed", "detail": f"{old_count} → {new_count}"})
        return notes

    # ---- added spans ----

    def spans(self):
        found = []
        text = self.new.text
        for tag, i1, i2, j1, j2 in self.opcodes:
            if tag not in ("insert", "replace"):
                continue
            offset = max(0, j1 - 3)
            window = text[offset:j2 + 3]
            # A marker counts only when it overlaps the added text, not merely the ±3 window.
            kinds = [
                kind for kind, _, regex in _MARKERS
                if any(m.start() < j2 - offset and m.end() > j1 - offset for m in regex.finditer(window))
            ]
            segment = text[j1:j2]
            words = [w for w in _CONTENT.findall(segment) if w not in self.old.text]
            if kinds or words:
                line, _ = self.new.locate(j1 + 1 if segment.startswith("\n") else j1)
                found.append({
                    "line": line, "added": _trim(segment), "was": _trim(self.old.text[i1:i2]),
                    "kinds": kinds, "new_words": words,
                })
        return self.cap("spans", found)

    # ---- logic candidates ----

    def logic(self):
        before = {_sentence_text(s) for s in self.inspection.original.sentences(UNIT_KINDS)}
        found = []
        for sentence in self.inspection.doc.sentences(UNIT_KINDS):
            text = _sentence_text(sentence)
            for kind, regex in _LOGIC:
                match = regex.search(text)
                if not match:
                    continue
                found.append({"kind": kind, "line": sentence.line, "column": sentence.start + 1,
                              "excerpt": self.inspection.clip(sentence.raw)})
                if text not in before:
                    self.add("logic_candidate", (sentence.line, sentence.start + 1), sentence.raw,
                             _LOGIC_REASONS[kind].format(match[0][:20]))
        return self.cap("logic", found)

    # ---- endings ----

    def endings(self):
        old_units, new_units = ending_units(self.inspection.original), ending_units(self.inspection.doc)
        changes = []
        for before, after in _ending_pairs(old_units, new_units, self._aligned(old_units, new_units)):
            changes.append({
                "original": before.raw,
                "original_kind": before.kind + ("_in_list" if before.where == "list" else ""),
                "rewrite": after.raw, "rewrite_kind": after.kind,
            })
            if after.kind in _STANCE_CONFLICTS.get(self.stance, ()):
                self.add(
                    "stance_ending_change", (after.line, after.column), after.raw,
                    f"文末が「{KIND_LABELS[before.kind]}」から「{KIND_LABELS[after.kind]}」に変わった。"
                    f"{STANCE_LABELS[self.stance]}の文書の立場と合うか確認する (revision.md R3)",
                )
        return {
            "changes": self.cap("endings.changes", changes),
            "flags": self._flags(new_units, "endings.flags"),
            "original_flags": self._flags(old_units, "endings.original_flags"),
        }

    def _aligned(self, old_units, new_units):
        """For each rewrite unit, the original units at its diff-mapped position."""
        old_starts = _unit_starts(self.old, old_units)
        order = sorted((start, n) for n, start in enumerate(old_starts) if start is not None)
        keys = [start for start, _ in order]
        aligned = []
        for start in _unit_starts(self.new, new_units):
            if start is None or not order:
                aligned.append(set())
                continue
            slot = bisect_right(keys, self.to_old(start)) - 1
            aligned.append({order[k][1] for k in (slot, slot + 1) if 0 <= k < len(order)})
        return aligned

    def _flags(self, units, name):
        flags = [
            {"kind": kind, "lines": sorted({u.line for u in flagged})}
            for kind, flagged in stance_flags(units, self.stance)
        ]
        for flag in flags:
            flag["lines"] = self.cap(f"{name}.{flag['kind']}.lines", flag["lines"])
        return flags

    def emit(self):
        ordered = sorted(self.findings)
        for _, line, column, rule, excerpt, reason in ordered[:FINDING_CAP]:
            self.inspection.finding(MODE, rule, "info", line, column, excerpt, reason)
        return len(ordered[:FINDING_CAP]), max(0, len(ordered) - FINDING_CAP)


def _sentence_text(sentence):
    visible = sentence.row.visible
    end = sentence.end
    if end < len(visible) and visible[end] in "。！？!?":
        end += 1
    return _EMPHASIS.sub("", visible[sentence.start:end]).strip()


def _bigrams(text):
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _ending_pairs(old_units, new_units, aligned):
    """(original unit, rewrite unit) pairs whose closest match changed its ending kind.

    Candidates are the original units sharing the most rare bigrams plus the units the
    character diff aligns with (``aligned[n]``); the first highest ratio wins.
    """
    exact, index = {}, defaultdict(list)
    for position, unit in enumerate(old_units):
        exact.setdefault(unit.plain, position)
        for bigram in _bigrams(unit.plain):
            index[bigram].append(position)
    matcher = SequenceMatcher(None, autojunk=False)
    for number, unit in enumerate(new_units):
        if unit.plain in exact:
            continue
        counts = Counter()
        for bigram in _bigrams(unit.plain):
            postings = index.get(bigram, ())
            if len(postings) <= COMMON_BIGRAM:
                counts.update(postings)
        candidates = set(sorted(counts, key=lambda p: (-counts[p], p))[:MATCH_CANDIDATES]) | aligned[number]
        best, score = None, 0.0
        matcher.set_seq2(unit.plain)
        for position in sorted(candidates):
            if len(old_units[position].plain) * len(unit.plain) > CHAR_DIFF_LIMIT:
                continue
            matcher.set_seq1(old_units[position].plain)
            ratio = matcher.ratio()
            if ratio > score:
                best, score = old_units[position], ratio
        if best is not None and score >= CHANGE_RATIO and best.kind != unit.kind:
            yield best, unit


def run(inspection):
    checks = ["revision", "lost_content_word", "new_content_word", "marker_count_change", "logic_candidate"]
    if inspection.original is None:
        for check in checks:
            inspection.unverified(check, "original_missing")
        return
    inspection.executed(*checks)
    if inspection.stance is not None:
        inspection.executed("stance_ending_change")
    comparison = Comparison(inspection)
    markers = comparison.markers()
    new_words, lost_words = comparison.words()
    section = {
        "stance": inspection.stance,
        "markers": markers,
        "new_words": new_words,
        "lost_words": lost_words,
        "structure": comparison.structure(),
        "spans": comparison.spans(),
        "logic": comparison.logic(),
        "endings": comparison.endings(),
        "omitted": comparison.omitted,
    }
    inspection.section("revision", section)
    emitted, dropped = comparison.emit()
    inspection.section_omitted(sum(comparison.omitted.values()) + dropped)
    inspection.stats(MODE, {
        "markers_changed": len(markers),
        "new_words": len(new_words) + comparison.omitted.get("new_words", 0),
        "lost_words": len(lost_words) + comparison.omitted.get("lost_words", 0),
        "spans": len(section["spans"]) + comparison.omitted.get("spans", 0),
        "logic": len(section["logic"]) + comparison.omitted.get("logic", 0),
        "ending_changes": len(section["endings"]["changes"]) + comparison.omitted.get("endings.changes", 0),
        "flags": len(section["endings"]["flags"]),
        "original_flags": len(section["endings"]["original_flags"]),
        "findings": emitted,
        "findings_omitted": dropped,
    })
