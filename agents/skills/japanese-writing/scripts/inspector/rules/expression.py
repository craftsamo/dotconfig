"""Expression habits: formatting excess, stock phrases, ending rhythm and stance.

Also provides the sentence-ending classifier shared with the revision mode.
"""

from dataclasses import dataclass
import re
import unicodedata

from .. import catalog
from ..document import MASK, TEXT_KINDS

MODE = "expression"
MORPHOLOGY = False

DATA = catalog.load("expression")
UNIT_KINDS = ("prose", "list", "list-continuation")
LIST_KINDS = ("list", "list-continuation")
GATE_CHARS = 300
BOLD_LIMIT = 3.0
LIST_LIMIT = 0.25
MIX_MIN_SENTENCES = 2
MIX_MIN_SHARE = 0.2

_EMOJI = re.compile(DATA["emoji"])
_EMPHASIS = re.compile(r"\*\*|__|\*")
_BOLD_SPAN = re.compile(r"\*\*[^*]+\*\*")
_LINK_BULLET = re.compile(r"\[[^\]]*\]\(https?://")
_METAPHORS = [dict(entry, regex=re.compile(entry["pattern"])) for entry in DATA["metaphor_verbs"]]
_FILLERS = [dict(entry, regex=re.compile(entry["pattern"])) for entry in DATA["meta_filler"]]
_ENDING_TRAIL = re.compile(r"[。！？!?\s*_]+$")
_DASH = re.compile(r"[—―]{1,2}")

_END = DATA["endings"]
_KIND_PATTERNS = [(kind, re.compile(pattern)) for kind, pattern in _END["kinds"]]
_POLITE_VERB = re.compile(_END["polite_verb"])
_PROGRESSIVE_STEM = re.compile(_END["progressive_stem"])
_PASSIVE_STEM = re.compile(_END["passive_stem"])
_STATE_STEMS = tuple(_END["stative"]) + tuple(_END["potential"])
_COPULA = re.compile(_END["copula"])
_PLAIN = re.compile(_END["plain"])
_POLITE = re.compile(_END["polite_register"])

KIND_LABELS = {
    "request": "依頼", "recommendation": "勧め", "conjecture": "推量・考え", "obligation": "義務",
    "evaluation": "評価", "past": "過去", "progressive": "〜ています", "state": "〜ます (状態)",
    "action": "〜します (動作)", "copula": "〜です", "plain": "常体", "nominal": "体言止めなど",
}
STANCE_LABELS = {"advice": "勧め", "rule": "決まり", "explanation": "説明"}
ASK_KINDS = ("recommendation", "request")


# ---- sentence endings (shared with revision) ----

def bare_end(text):
    """The sentence with emphasis, terminators and trailing brackets removed."""
    text = text.replace("**", "").replace("`", "").strip()
    text = text.rstrip("。．.！!？?").strip()
    while True:
        trimmed = re.sub(r"[（(][^（）()]*[）)]$", "", text).strip()
        if trimmed == text:
            break
        text = trimmed
    return re.sub(r"[」』）)]+$", "", text)


def register(text):
    """'polite', 'plain' or '' for the sentence's final form."""
    tail = bare_end(text)
    if _POLITE.search(tail):
        return "polite"
    if _PLAIN.search(tail):
        return "plain"
    return ""


def ending_kind(text):
    tail = bare_end(text)
    if not tail:
        return ""
    for kind, pattern in _KIND_PATTERNS:
        if pattern.search(tail):
            return kind
    verb = _POLITE_VERB.search(tail)
    if verb:
        stem = tail[:verb.start()]
        if _PROGRESSIVE_STEM.search(stem):
            return "progressive"
        # Passive and potential stems (〜されます, 〜られます) describe states, not reader actions.
        if _PASSIVE_STEM.search(stem) or stem.endswith(_STATE_STEMS):
            return "state"
        return "action"
    if _COPULA.search(tail):
        return "copula"
    if _PLAIN.search(tail):
        return "plain"
    return "nominal"


@dataclass(frozen=True)
class Unit:
    line: int
    column: int
    raw: str
    plain: str
    kind: str
    where: str
    full: bool


def _terminated(sentence):
    visible = sentence.row.visible
    return sentence.end < len(visible) and visible[sentence.end] in "。！？!?"


def ending_units(doc):
    """Sentence-final units of prose and list rows, split again at em dashes."""
    units = []
    for sentence in doc.sentences(UNIT_KINDS):
        row, text = sentence.row, sentence.text
        full = _terminated(sentence)
        cuts = [0] + [p for m in _DASH.finditer(text) for p in (m.start(), m.end())] + [len(text)]
        parts = [(cuts[n], cuts[n + 1]) for n in range(0, len(cuts), 2) if text[cuts[n]:cuts[n + 1]].strip()]
        for n, (left, right) in enumerate(parts):
            last = n == len(parts) - 1
            kind = ending_kind(text[left:right])
            if not kind or (not last and kind == "nominal"):
                continue
            start = sentence.start + left + len(text[left:right]) - len(text[left:right].lstrip())
            end = sentence.start + right
            units.append(Unit(
                line=row.line, column=start + 1, raw=row.raw[start:end].strip(),
                plain=text[left:right].replace("**", "").strip(), kind=kind,
                where="list" if row.kind in LIST_KINDS else "prose", full=full or not last,
            ))
    return units


def stance_flags(units, stance):
    """(flag kind, units) pairs per the document stance, then register mixing."""
    action = [u for u in units if u.kind == "action"]
    ask = [u for u in units if u.kind in ASK_KINDS]
    recommend = [u for u in ask if u.kind == "recommendation"]
    evaluation = [u for u in units if u.kind == "evaluation"]
    flags = []
    if stance == "advice" and action:
        flags.append(("action_in_advice", action))
    elif stance == "rule" and (recommend or evaluation):
        flags.append(("recommendation_in_rule", sorted(recommend + evaluation, key=_unit_order)))
    elif stance == "explanation":
        body = [u for u in ask if u is not units[-1]]
        if body:
            flags.append(("ask_in_explanation", body))
    elif stance is None and action and ask:
        flags.append(("action_mixed_with_ask", sorted(action + ask, key=_unit_order)))
    elif stance is None and action and evaluation:
        flags.append(("action_mixed_with_evaluation", sorted(action + evaluation, key=_unit_order)))
    full = [u for u in units if u.full]
    plain = [u for u in full if register(u.plain) == "plain"]
    polite = [u for u in full if register(u.plain) == "polite"]
    if plain and len(polite) > len(plain):
        flags.append(("plain_among_polite", plain))
    elif polite and len(plain) > len(polite):
        flags.append(("polite_among_plain", polite))
    return flags


def _unit_order(unit):
    return unit.line, unit.column


# ---- helpers ----

def _without_emphasis(text):
    """``text`` minus emphasis markers, with a map back to original offsets."""
    removed = set()
    for match in _EMPHASIS.finditer(text):
        removed.update(range(match.start(), match.end()))
    keep = [i for i in range(len(text)) if i not in removed]
    return "".join(text[i] for i in keep), keep


def _span(offsets, start, end):
    return offsets[start], offsets[end - 1] + 1


# ---- document-level formatting density ----

def _density(inspection):
    rows = inspection.doc.rows_of(TEXT_KINDS)
    chars = sum(len(re.sub(r"\s+", "", row.raw)) for row in rows)
    bold = sum(len(_BOLD_SPAN.findall(row.text)) for row in rows)
    lists = sum(
        1 for row in rows
        if row.kind == "list" and not _LINK_BULLET.match(row.raw[row.content_start:])
    )
    bold_rate = bold / chars * 1000 if chars else 0.0
    list_ratio = lists / len(rows) if rows else 0.0
    inspection.executed("excess_bold", "excess_list")
    if chars > GATE_CHARS and bold_rate > BOLD_LIMIT:
        inspection.finding(
            MODE, "excess_bold", "warn", 1, 1, f"太字 {bold} 箇所 / {chars} 字",
            f"太字が 1000 字あたり {bold_rate:.1f} 箇所ある。目安は 1000 字あたり 3 以下。"
            "要点だけに絞れるか確認する (expression.md X10)",
        )
    if chars > GATE_CHARS and list_ratio > LIST_LIMIT:
        inspection.finding(
            MODE, "excess_list", "warn", 1, 1, f"箇条書き {lists} 行 / {len(rows)} 行",
            f"箇条書きの行が全体の {list_ratio * 100:.1f}% を占める。目安は 25% 以下。"
            "理由や経緯は文章で書けるか確認する (expression.md X10)",
        )
    return {"char_count": chars, "list_ratio": round(list_ratio, 3), "bold_per_1000": round(bold_rate, 2)}


# ---- sentence rhythm and register ----

def _end_type(text):
    tail = _ENDING_TRAIL.sub("", text)
    return next((end for end in DATA["sentence_endings"] if tail.endswith(end)), None)


def _end_repetition(inspection):
    inspection.executed("sentence_end_repetition")
    sentences = [s for s in inspection.doc.sentences(UNIT_KINDS) if len(s.text.strip()) > 3]
    run = 1
    for index in range(1, len(sentences)):
        current = _end_type(sentences[index].text)
        if current is not None and current == _end_type(sentences[index - 1].text):
            run += 1
            if run == 3:
                trio = sentences[index - 2:index + 1]
                last = sentences[index]
                inspection.span_finding(
                    MODE, "sentence_end_repetition", "warn", last.row, last.start, last.end,
                    f"文末「{current}」が 3 文続いている。言い切りや問いかけを混ぜて単調さを避けられるか"
                    "確認する (expression.md X7)",
                    [s.line for s in trio],
                )
        else:
            run = 1
    return len(sentences)


def _style_mix(inspection):
    inspection.executed("ending_style_mix")
    forms = {"polite": [], "plain": []}
    for sentence in inspection.doc.sentences(("prose",)):
        form = register(sentence.text) if _terminated(sentence) else ""
        if form:
            forms[form].append(sentence)
    polite, plain = len(forms["polite"]), len(forms["plain"])
    if not polite or not plain:
        return
    minority = "plain" if plain < polite else "polite"
    if polite == plain:
        minority = "plain" if forms["plain"][0].line > forms["polite"][0].line else "polite"
    count = len(forms[minority])
    if count < MIX_MIN_SENTENCES or count / (polite + plain) < MIX_MIN_SHARE:
        return
    first = forms[minority][0]
    label = "常体" if minority == "plain" else "敬体"
    inspection.span_finding(
        MODE, "ending_style_mix", "info", first.row, first.start, first.end,
        f"本文に敬体 {polite} 文と常体 {plain} 文が混在し、少ない{label}が {count} 文ある。"
        "引用や意図した使い分けか確認する (notation.md N9)",
        [s.line for s in forms[minority]],
    )


_STANCE_REASONS = {
    "action_in_advice": "勧めの文書で主語のない「〜します」の文末。読み手の行動なら勧めの形に、"
                        "仕組みや手順の説明ならそのままでよいか確認する (revision.md R3)",
    "recommendation_in_rule": "決まりの文書に勧め・評価の文末がある。決まりを述べる文なら「〜します」に"
                              "できるか確認する。理由の文は残す (revision.md R3)",
    "ask_in_explanation": "説明の文書の途中に勧め・依頼の文末がある。事実や結果を述べる文書で読み手に"
                          "求める必要があるか確認する (revision.md R3)",
}


def _stance_conflicts(inspection):
    if inspection.stance is None:
        return
    inspection.executed("stance_ending_conflict")
    units = ending_units(inspection.doc)
    for kind, flagged in stance_flags(units, inspection.stance):
        if kind not in _STANCE_REASONS:
            continue
        for unit in flagged:
            inspection.finding(
                MODE, "stance_ending_conflict", "info", unit.line, unit.column, unit.raw,
                _STANCE_REASONS[kind],
            )


# ---- per-row vocabulary ----

def _emoji(inspection, row):
    found = list(_EMOJI.finditer(row.visible))
    if found:
        sample = " ".join(m[0] for m in found[:3])
        inspection.finding(
            MODE, "emoji", "warn", row.line, found[0].start() + 1, row.raw.strip(),
            f"絵文字 ({sample}) がある。本文の装飾として必要か、言葉で表せるか確認する (expression.md X10)",
        )


def _longest_matches(text, words):
    """Occurrences of ``words``, dropping any that lie inside a longer occurrence."""
    spans = []
    for word in words:
        start = text.find(word)
        while start >= 0:
            spans.append((start, start + len(word), word))
            start = text.find(word, start + 1)
    spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
    kept, reach = [], -1
    for span in spans:
        if span[1] <= reach:
            continue
        kept.append(span)
        reach = span[1]
    return kept


def _slop(inspection, row, clean, offsets):
    reported = set()
    for start, end, word in sorted(_longest_matches(clean, DATA["slop_vocabulary"])):
        if word in reported:
            continue
        reported.add(word)
        left, right = _span(offsets, start, end)
        inspection.span_finding(
            MODE, "slop_vocabulary", "warn", row, left, right,
            f"「{word}」は雰囲気だけを足す語になりやすい。字義どおりでなければ具体的な語に"
            "置き換えられるか確認する (expression.md X2)",
        )


def _metaphors(inspection, row, clean, offsets):
    spans = {}
    for entry in _METAPHORS:
        outer = spans.get(entry.get("within"))
        match = next(
            (m for m in entry["regex"].finditer(clean)
             if not outer or not (outer[0] <= m.start() and m.end() <= outer[1])),
            None,
        )
        if not match:
            continue
        spans[entry["id"]] = match.span()
        left, right = _span(offsets, *match.span())
        inspection.span_finding(
            MODE, "metaphor_verb", "warn", row, left, right,
            f"比喩や直訳調の言い回し ({entry['label']}) がある。字義どおりでなければ"
            "具体的な動作や結果に書き換えられるか確認する (expression.md X5)",
        )


def _fillers(inspection, sentence):
    clean, offsets = _without_emphasis(sentence.text)
    lead = len(clean) - len(clean.lstrip())
    clean, offsets = clean[lead:], offsets[lead:]
    for entry in _FILLERS:
        match = entry["regex"].search(clean)
        if not match or match.end() == match.start():
            continue
        left, right = _span(offsets, *match.span())
        inspection.span_finding(
            MODE, "meta_filler", "warn", sentence.row, sentence.start + left, sentence.start + right,
            f"前置きや締めの決まり文句 ({entry['label']}) がある。中身のない前置きなら削り、"
            "評価を含むなら内容を直接書く (expression.md X1)",
        )


def _row_checks(inspection):
    inspection.executed("emoji", "slop_vocabulary", "metaphor_verb", "meta_filler")
    for row in inspection.doc.rows_of(TEXT_KINDS + ("table",)):
        _emoji(inspection, row)
        if row.kind == "table":
            continue
        clean, offsets = _without_emphasis(row.visible)
        _slop(inspection, row, clean, offsets)
        _metaphors(inspection, row, clean, offsets)
    for sentence in inspection.doc.sentences(UNIT_KINDS):
        _fillers(inspection, sentence)


# ---- bold that does not render ----
#
# A "**" run must be left-flanking to open and right-flanking to close. The
# check accepts a pair only when it works under both the GFM punctuation set
# (ASCII punctuation plus Unicode P*) and current CommonMark (Unicode P* and S*).

_STARS = re.compile(r"(?<![*\\])\*\*(?!\*)")
_CLOSERS = DATA["bold_brackets"]
_TRAILING_MARKS = "。、．，！？!?"
_BOLD_ADVICE = {
    "bracket": "太字をかっこの内側に移す",
    "punctuation": "句読点を太字の外に出す",
    "strip": "太字の内側の空白を除く",
    "space": "記号の外側に半角スペースを入れる",
}


def _blank(char):
    return not char or char.isspace()


def _punctuation(char, commonmark):
    if not char:
        return False
    category = unicodedata.category(char)[0]
    if commonmark:
        return category in "PS"
    return category == "P" or (char.isascii() and not char.isalnum() and not char.isspace())


def _flanking(inner, outer):
    """``inner`` is the character inside the emphasis, ``outer`` the one outside."""
    if _blank(inner):
        return False
    return all(not _punctuation(inner, mode) or _blank(outer) or _punctuation(outer, mode)
               for mode in (False, True))


def _renders(text, opening, closing):
    before, first = text[opening - 1:opening], text[opening + 2:opening + 3]
    last, after = text[closing - 1:closing], text[closing + 2:closing + 3]
    return _flanking(first, before) and _flanking(last, after)


def _star_pairs(row):
    """Consecutive ``**`` delimiters outside masked spans, paired in order."""
    marks = [m.start() for m in _STARS.finditer(row.raw) if MASK not in row.text[m.start():m.end()]]
    return list(zip(marks[0::2], marks[1::2]))


def _closes_at_end(inner):
    opener, closer, depth = inner[0], _CLOSERS[inner[0]], 0
    for index, char in enumerate(inner):
        depth += (char == opener) - (char == closer)
        if depth == 0:
            return index == len(inner) - 1
    return False


def _repairs(raw, opening, closing):
    """Candidate replacements for ``raw[opening:closing + 2]``, most specific first."""
    inner = raw[opening + 2:closing]
    if len(inner) >= 3 and inner[0] in _CLOSERS and _closes_at_end(inner):
        yield "bracket", f"{inner[0]}**{inner[1:-1]}**{inner[-1]}"
    if len(inner) >= 2 and inner[-1] in _TRAILING_MARKS:
        yield "punctuation", f"**{inner[:-1]}**{inner[-1]}"
    core = inner.strip() if _blank(inner[:1]) or _blank(inner[-1:]) else inner
    left = "" if _flanking(core[:1], raw[opening - 1:opening]) else " "
    right = "" if _flanking(core[-1:], raw[closing + 2:closing + 3]) else " "
    yield ("strip" if core != inner and not left and not right else "space"), f"{left}**{core}**{right}"


def _repair(raw, opening, closing):
    for how, replacement in _repairs(raw, opening, closing):
        candidate = raw[:opening] + replacement + raw[closing + 2:]
        new_open = opening + replacement.index("**")
        new_close = opening + replacement.rindex("**")
        if _renders(candidate, new_open, new_close):
            return replacement, how
    return None, None


def _clip(text):
    return text if len(text) <= 30 else f"{text[:12]}...{text[-12:]}"


def bold_problems(row):
    """[(column, found, suggestion or "", how or None)] for pairs that would not render."""
    problems = []
    raw = row.raw
    for opening, closing in _star_pairs(row):
        if _renders(raw, opening, closing):
            continue
        replacement, how = _repair(raw, opening, closing)
        before, after = raw[max(0, opening - 4):opening], raw[closing + 2:closing + 6]
        found = before + _clip(raw[opening:closing + 2]) + after
        suggestion = before + _clip(replacement) + after if replacement else ""
        problems.append((opening + 1, found, suggestion, how))
    return problems


def _bold_not_rendered(inspection):
    inspection.executed("bold_not_rendered")
    for row in inspection.doc.rows_of(TEXT_KINDS + ("table",)):
        for column, found, suggestion, how in bold_problems(row):
            if suggestion:
                advice, excerpt = f"{_BOLD_ADVICE[how]}: {suggestion}", f"{found} → {suggestion}"
            else:
                advice, excerpt = "前後の文字を見て手で直す", found
            inspection.finding(
                MODE, "bold_not_rendered", "critical", row.line, column, excerpt,
                f"「**」が記号や空白と接し、太字にならず記号のまま表示される。{advice} (notation.md N11)",
            )


def run(inspection):
    stats = _density(inspection)
    stats["sentences"] = _end_repetition(inspection)
    _bold_not_rendered(inspection)
    _row_checks(inspection)
    _style_mix(inspection)
    _stance_conflicts(inspection)
    inspection.stats(MODE, stats)
