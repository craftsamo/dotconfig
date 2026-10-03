"""Reading load: places in prose sentences that a reader may have to parse twice.

These are pointers for revision, never part of the naturalness score. Length and
kanji-run checks are pattern based; the rest need Sudachi.
"""

import re

from .. import catalog
from ..morphology import SegmentTooLarge

MODE = "reading-load"
MORPHOLOGY = True

PATTERN_RULES = ("sentence_too_long", "kanji_run")
MORPH_RULES = ("buried_list", "double_negative", "no_chain")
PROPER_NOUN_FILTER = "kanji_run_proper_noun_filter"
SYMBOL_POS = ("補助記号", "空白")
EXCERPT = 40


def _reading_length(sentence):
    return len(re.sub(r"\s{2,}", " ", sentence.text).strip())


def _excerpt(sentence, start=0, end=None):
    return sentence.raw[start:end].strip()[:EXCERPT]


class _Context:
    def __init__(self, inspection):
        self.inspection = inspection
        self.data = catalog.load("reading-load")
        self.max_chars = self.data["sentence_max_chars"][inspection.genre]
        self.kanji = re.compile(self.data["kanji_run"])
        self.counts = {}

    def emit(self, rule, sentence, start, excerpt, reason):
        self.counts[rule] = self.counts.get(rule, 0) + 1
        self.inspection.finding(MODE, rule, "info", sentence.line, sentence.start + start + 1, excerpt, reason)

    def tokenize(self, sentence):
        try:
            return self.inspection.morph.tokenize(sentence.text)
        except SegmentTooLarge:
            for check in MORPH_RULES + (PROPER_NOUN_FILTER,):
                self.inspection.unverified(check, "segment_exceeds_40000_utf8_bytes", sentence.line)
            return None


def _sentence_too_long(ctx, sentence, length):
    if length > ctx.max_chars:
        reason = f"一文が {length} 字ある (目安 {ctx.max_chars} 字)。一文に一つの内容か確認する (readability.md B1)"
        ctx.emit("sentence_too_long", sentence, 0, _excerpt(sentence), reason)


def _kanji_run(ctx, sentence, tokens):
    for match in ctx.kanji.finditer(sentence.text):
        start, end = match.span()
        if tokens and any(t.end > start and t.begin < end and t.pos[1] == "固有名詞" for t in tokens):
            continue
        guide = ctx.data["kanji_run_guide"]
        reason = f"漢字が {end - start} 字続く (目安 {guide} 字)。語の切れ目が読み取れるか確認する (readability.md C1)"
        ctx.emit("kanji_run", sentence, start, sentence.raw[start:end], reason)


def _ends_with_noun(segment, pairs):
    i = len(segment) - 1
    while i >= 0:
        token = segment[i]
        if token.surface in pairs:
            closer, opener, depth = token.surface, pairs[token.surface], 1
            i -= 1
            while i >= 0 and depth:
                depth += {closer: 1, opener: -1}.get(segment[i].surface, 0)
                i -= 1
            if depth:
                return False
            continue
        if token.pos[0] not in SYMBOL_POS:
            return token.pos[0] == "名詞"
        i -= 1
    return False


def _segments(tokens):
    segments, current = [], []
    for token in tokens:
        if token.surface == "、":
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return segments


def _buried_list_candidate(tokens, pairs):
    """Return (items, begin, end) for the longest run of noun phrases joined by 、."""
    segments = _segments(tokens)
    best, run = None, []
    for index, segment in enumerate(segments):
        if not segment or not _ends_with_noun(segment, pairs):
            run = []
            continue
        run.append(index)
        if len(run) >= 2 and index + 1 < len(segments):
            items = len(run) + 1
            tail = segments[index + 1] or segment
            if best is None or items > best[0]:
                best = (items, segments[run[0]][0].begin, tail[-1].end)
    return best


def _buried_list(ctx, sentence, tokens, length):
    candidate = _buried_list_candidate(tokens, ctx.data["bracket_pairs"])
    if candidate is None:
        return
    items, begin, end = candidate
    limits = ctx.data["buried_list_min_chars"]
    if length >= (limits["three_or_fewer"] if items <= 3 else limits["four_or_more"]):
        reason = (f"名詞句が読点で {items} 個並ぶ (一文 {length} 字)。"
                  "箇条書きに開くと並びが追いやすいか確認する (readability.md F1)")
        ctx.emit("buried_list", sentence, begin, _excerpt(sentence, begin, end), reason)


def _double_negative(ctx, sentence, tokens):
    data = ctx.data
    negations = [i for i, t in enumerate(tokens)
                 if t.pos[0] in ("助動詞", "形容詞") and t.normalized_form in data["negation_forms"]]
    conditional = re.compile(data["conditional_negation"])
    for a, b in zip(negations, negations[1:]):
        span = "".join(t.surface for t in tokens[a:b + 1])
        if (b - a > data["negation_max_gap"]
                or any(t.pos[0] == "補助記号" for t in tokens[a + 1:b])
                or any(s in span for s in data["obligation_substrings"])
                or conditional.match(span)):
            continue
        reason = "否定が二重に掛かっている。肯定に直すなら真偽が逆転しないか確かめる (readability.md A1)"
        ctx.emit("double_negative", sentence, tokens[a].begin,
                 sentence.raw[tokens[a].begin:tokens[b].end], reason)
        return


def _no_chain(ctx, sentence, tokens):
    data = ctx.data
    size, gap = data["no_chain_length"], data["no_chain_max_gap"]
    indices = [i for i, t in enumerate(tokens) if t.surface == "の" and t.pos[:2] == ("助詞", "格助詞")]
    for k in range(len(indices) - size + 1):
        window = indices[k:k + size]
        if any(right - left > gap for left, right in zip(window, window[1:])):
            continue
        if any(t.pos[0] == "補助記号" for t in tokens[window[0] + 1:window[-1]]):
            continue
        begin, end = tokens[window[0]].begin, tokens[window[-1]].end
        reason = "格助詞「の」が 3 回以上続く。どこかを動詞の形に開けないか確認する (readability.md C2)"
        ctx.emit("no_chain", sentence, begin, sentence.raw[begin:end], reason)
        return


def run(inspection):
    ctx = _Context(inspection)
    inspection.executed(*PATTERN_RULES)
    morph_ok = inspection.needs_morphology(*MORPH_RULES, PROPER_NOUN_FILTER)
    sentences = inspection.doc.sentences()
    for sentence in sentences:
        length = _reading_length(sentence)
        tokens = ctx.tokenize(sentence) if morph_ok else None
        _sentence_too_long(ctx, sentence, length)
        _kanji_run(ctx, sentence, tokens)
        if tokens is None:
            continue
        _buried_list(ctx, sentence, tokens, length)
        _double_negative(ctx, sentence, tokens)
        _no_chain(ctx, sentence, tokens)
    inspection.stats(MODE, {"total": sum(ctx.counts.values()), "sentences": len(sentences),
                            "genre": inspection.genre, "by_rule": ctx.counts})
