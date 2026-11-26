"""Notation checks: Japanese technical and business prose house defaults.

Most rules are data-driven regexes from ``data/notation.json`` run over a
per-row view of the literal text. A few rules need context that a single
pattern cannot express and have dedicated functions below.
"""

import re
import unicodedata

from .. import catalog
from ..document import MASK, TEXT_KINDS

MODE = "notation"
MORPHOLOGY = False

CODE = "\ue000"
CONTEXT = 6
_DATA = catalog.load("notation")
_CLASSES = _DATA["classes"]
_RULES = {rule["id"]: rule for rule in _DATA["rules"]}
_BARE_URL = re.compile(r"https?://[!-~]+")
_URL_TRAIL = ".,;:!?)]}'\"*_"


def _expand(pattern, extra=None):
    for name, value in {**_CLASSES, **(extra or {})}.items():
        pattern = pattern.replace("{" + name + "}", value)
    return pattern


def _compile_patterns(rule):
    extra = {}
    if "units" in rule:
        extra["UNITS"] = "|".join(re.escape(u) for u in sorted(rule["units"], key=len, reverse=True))
    compiled = []
    for entry in rule["patterns"]:
        pattern, suggest = (entry, None) if isinstance(entry, str) else entry
        compiled.append((re.compile(_expand(pattern, extra)), suggest))
    return compiled


_TABLE = {rule["id"]: _compile_patterns(rule) for rule in _DATA["rules"] if "patterns" in rule}
_JA = re.compile(_CLASSES["JA"])
_ALNUM_BOUNDARY = re.compile(
    _expand("(?<={JA})(?=[A-Za-z{CODE}])|(?<=[A-Za-z{CODE}])(?={JA})", {"CODE": CODE})
)
_SLASH = re.compile(r"(?<!\s)(\s*)/(\s*)")
_ACCESS_KEY = re.compile(_RULES["paren_outer_space"]["access_key"])
_PHOTO_MM = re.compile(_RULES["number_unit_space"]["photo_mm"])
_HEADING_POLITE = re.compile(_RULES["heading_polite_ending"]["pattern"])
_FULL_PAREN = re.compile(r"（[^（）\n\u0000\ue000]+）")
_HALF_PAREN = re.compile(r"\([^()\n\u0000\ue000]+\)")
_KATA = _CLASSES["KATA"]


def _long_vowel_patterns(rule):
    exceptions = set(rule["exceptions"])

    def bounded(words):
        words = sorted((w for w in words if w not in exceptions), key=len, reverse=True)
        return re.compile(f"(?<!{_KATA})(?:{'|'.join(map(re.escape, words))})(?!{_KATA})")

    return bounded(rule["missing"]), bounded(rule["extra"])


_LONG_MISSING, _LONG_EXTRA = _long_vowel_patterns(_RULES["long_vowel"])


class _Emitter:
    """Builds findings for one inspection and drops repeated (rule, line, column)."""

    def __init__(self, inspection):
        self.inspection = inspection
        self.seen = set()
        self.counts = {rule_id: 0 for rule_id in _RULES}

    def emit(self, rule_id, row, start, end, suggest=""):
        key = (rule_id, row.line, start)
        if key in self.seen:
            return
        self.seen.add(key)
        self.counts[rule_id] += 1
        rule = _RULES[rule_id]
        found = row.raw[start:end]
        reason = rule["reason"].format(found=found, suggest=suggest) + f" (notation.md {rule['anchor']})"
        excerpt = row.raw[max(0, start - CONTEXT):end + CONTEXT].strip()
        self.inspection.finding(MODE, rule_id, rule["severity"], row.line, start + 1, excerpt, reason)


def _view(row):
    """Literal text with inline code and bare URLs as ``CODE`` (half-width text) and other masks kept."""
    chars = list(row.literal)
    for run in re.finditer(f"{MASK}+", row.text):
        if row.masked_code_at(run.start()):
            chars[run.start():run.end()] = CODE * (run.end() - run.start())
    view = "".join(chars)
    for url in _BARE_URL.finditer(view):
        end = url.start() + len(url[0].rstrip(_URL_TRAIL))
        chars[url.start():end] = CODE * (end - url.start())
    return "".join(chars)


def _masked(view, start, end):
    segment = view[start:end]
    return MASK in segment or CODE in segment


def _keep_space_inside_brackets(view, match):
    pairs = _RULES["space_inside_brackets"]["empty_pairs"]
    text = match[0]
    if text[0] in pairs:
        opener, closer_at = text[0], match.end()
        opener_at = match.start()
    else:
        opener_at, closer_at = match.start() - 1, match.end() - 1
        opener = view[opener_at] if opener_at >= 0 else ""
    if opener not in pairs or closer_at >= len(view) or view[closer_at] != pairs[opener]:
        return True
    # "( )" is a placeholder anywhere; "[ ]" is exempt only as a task box at row start.
    return opener == "[" and bool(view[:opener_at].strip())


def _keep_paren_outer_space(view, match):
    if match[0] == "(":
        return not _ACCESS_KEY.match(view, match.start())
    return not any(_ACCESS_KEY.fullmatch(view, match.end() - width, match.end()) for width in (3, 4))


def _keep_number_unit_space(view, match):
    return not (match["unit"] == "mm" and _PHOTO_MM.match(view, match.start()))


def _keep_ideographic_space(view, match):
    return bool(view[:match.start()].strip())


_FILTERS = {
    "space_inside_brackets": _keep_space_inside_brackets,
    "paren_outer_space": _keep_paren_outer_space,
    "number_unit_space": _keep_number_unit_space,
    "ideographic_space": _keep_ideographic_space,
}


def _suggestion(rule, match, template):
    if template is not None:
        return match.expand(template)
    if rule.get("suggest") == "nfkc":
        return unicodedata.normalize("NFKC", match[0])
    return ""


def _table_rule(emitter, rule_id, row, view):
    rule = _RULES[rule_id]
    keep = _FILTERS.get(rule_id)
    for pattern, template in _TABLE[rule_id]:
        for match in pattern.finditer(view):
            if _masked(view, match.start(), match.end()) or (keep and not keep(view, match)):
                continue
            emitter.emit(rule_id, row, match.start(), match.end(), _suggestion(rule, match, template))


def _space_ja_alnum(emitter, row, view):
    for boundary in _ALNUM_BOUNDARY.finditer(view):
        left = boundary.start() - 1
        start = left if view[left] != CODE else left + 1
        emitter.emit("space_ja_alnum", row, start, start + 1)


def _space_around_slash(emitter, row, view):
    for match in _SLASH.finditer(view):
        before, after = match.span(1), match.span(2)
        if before[0] == before[1] and after[0] == after[1]:
            continue
        left = view[before[0] - 1] if before[0] else " "
        right = view[after[1]] if after[1] < len(view) else " "
        if _JA.fullmatch(left) or _JA.fullmatch(right) or (left.isdigit() and right.isdigit()):
            emitter.emit("space_around_slash", row, match.start(), match.end())


def _straight_double_quote(emitter, row, view):
    quotes = [i for i, char in enumerate(view) if char == '"']
    for opening, closing in zip(quotes[::2], quotes[1::2]):
        if _JA.search(view, opening + 1, closing):
            emitter.emit("straight_double_quote", row, opening, closing + 1)


def _long_vowel(emitter, row, view):
    for match in _LONG_MISSING.finditer(view):
        emitter.emit("long_vowel", row, match.start(), match.end(), match[0] + "ー")
    for match in _LONG_EXTRA.finditer(view):
        emitter.emit("long_vowel", row, match.start(), match.end(), match[0][:-1])


def _heading_polite_ending(emitter, row, view):
    if row.kind != "heading":
        return
    match = _HEADING_POLITE.search(view.rstrip(f" \t\u3000{MASK}"))
    if match:
        emitter.emit("heading_polite_ending", row, match.start(), match.end())


def _half_paren_hits(row, view):
    hits = []
    for match in _HALF_PAREN.finditer(view):
        inner = match[0][1:-1]
        if not inner.strip() or _ACCESS_KEY.fullmatch(match[0]):
            continue
        if _JA.search(inner) or _JA.search(view, max(0, match.start() - 2), min(len(view), match.end() + 2)):
            hits.append((row, match.start(), match.end()))
    return hits


def _paren_style_mix(emitter, full_hits, half_hits):
    if not full_hits or not half_hits:
        return
    minority = full_hits if len(full_hits) < len(half_hits) else half_hits
    if len(full_hits) == len(half_hits):
        minority = half_hits if half_hits[0][0].line > full_hits[0][0].line else full_hits
    row, start, end = minority[0]
    summary = f"全角 {len(full_hits)} 箇所 / 半角 {len(half_hits)} 箇所"
    emitter.emit("paren_style_mix", row, start, end, summary)


_DEDICATED = {
    "space_ja_alnum": _space_ja_alnum,
    "paren_style_mix": None,
    "space_around_slash": _space_around_slash,
    "straight_double_quote": _straight_double_quote,
    "long_vowel": _long_vowel,
    "heading_polite_ending": _heading_polite_ending,
}


def run(inspection):
    emitter = _Emitter(inspection)
    full_hits, half_hits = [], []
    for row in inspection.doc.rows_of(TEXT_KINDS):
        if not row.text.strip():
            continue
        view = _view(row)
        full_hits.extend((row, m.start(), m.end()) for m in _FULL_PAREN.finditer(view))
        half_hits.extend(_half_paren_hits(row, view))
        for rule_id in _RULES:
            if rule_id in _DEDICATED:
                fn = _DEDICATED[rule_id]
                if fn is not None:
                    fn(emitter, row, view)
            else:
                _table_rule(emitter, rule_id, row, view)
    _paren_style_mix(emitter, full_hits, half_hits)
    inspection.executed(*_RULES)
    inspection.stats(MODE, {"rules_checked": len(_RULES), "by_rule": emitter.counts})
