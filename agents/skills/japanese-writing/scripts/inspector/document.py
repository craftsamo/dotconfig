"""Line-preserving view of limited Markdown.

Every row keeps the original physical line (``raw``) and a masked copy
(``text``) of the same length, so offsets found in the masked text are valid
in the original. Masked spans use ``MASK``; ``visible()`` turns them into
spaces for pattern matching.

Recognized: front matter, backtick/tilde fences, indented code outside
lists, HTML comments, block quotes with lazy continuation, lists with
continuation lines, ATX and single-line setext headings, pipe tables,
inline code, link destinations, reference labels, images, autolinks and
inline HTML tags. Not a full CommonMark parser.
"""

from dataclasses import dataclass
import re

MASK = "\x00"
PROSE_KINDS = ("prose",)
TEXT_KINDS = ("prose", "heading", "list", "list-continuation")

_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
_ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+|$)")
_LIST = re.compile(r"^([ \t]*)(?:[-+*]|[0-9]{1,9}[.)])(?:[ \t]+|$)")
_ANGLE_OPEN = re.compile(r"<(?:/?[A-Za-z]|[A-Za-z]+:)")
_THEMATIC = re.compile(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})")
_SETEXT = re.compile(r" {0,3}(?:=+|-+)[ \t]*")
_ESCAPABLE = set(r"!\"#$%&'()*+,-./:;<=>?@[\]^_`{|}~")
_FULL_STOPS = set("。！？")


@dataclass
class Row:
    line: int
    raw: str
    text: str
    kind: str = "excluded"
    level: int = 0
    content_start: int = 0

    @property
    def visible(self):
        return self.text.replace(MASK, " ")

    @property
    def literal(self):
        """Original characters with masked spans kept as ``MASK``.

        Unlike ``visible`` this keeps brackets and punctuation exactly as
        written; only the leading block marker (``#``, ``-``, ``1.``) is
        blanked. Notation checks need this view.
        """
        if not self.text.strip():
            return " " * len(self.raw)
        lead = self.content_start
        chars = [" " if i < lead else (MASK if t == MASK else r) for i, (r, t) in enumerate(zip(self.raw, self.text))]
        literal = "".join(chars)
        if self.kind == "heading":
            closing = re.search(r"[ \t]+#+[ \t]*$", literal)
            if closing:
                literal = literal[:closing.start()] + " " * (len(literal) - closing.start())
        return literal

    def masked_code_at(self, index):
        """True when ``index`` lies in a masked inline-code span."""
        if not 0 <= index < len(self.text) or self.text[index] != MASK:
            return False
        left = index
        while left > 0 and self.text[left - 1] == MASK:
            left -= 1
        return self.raw[left] == "`"


@dataclass(frozen=True)
class Sentence:
    """A sentence candidate inside one physical line.

    ``start``/``end`` are 0-based offsets into the row, already trimmed of
    surrounding whitespace and masked spans. ``text`` is the visible text
    (masked spans as spaces); ``raw`` is the original slice.
    """

    row: Row
    start: int
    end: int

    @property
    def line(self):
        return self.row.line

    @property
    def text(self):
        return self.row.visible[self.start:self.end]

    @property
    def raw(self):
        return self.row.raw[self.start:self.end]


def _mask_inline(raw, in_comment):
    out = list(raw)
    runs = {}
    for match in re.finditer(r"`+", raw):
        runs.setdefault(len(match[0]), []).append((match.start(), match.end()))
    closes = {}
    run_end = {start: end for spans in runs.values() for start, end in spans}
    for spans in runs.values():
        for left, right in zip(spans, spans[1:]):
            closes[left[0]] = right[1]
    i = 0
    angle_unclosed = False
    while i < len(raw):
        end = i
        if in_comment or raw.startswith("<!--", i):
            close = raw.find("-->", i if in_comment else i + 4)
            end = len(raw) if close < 0 else close + 3
            in_comment = close < 0
        elif raw[i] == "\\" and i + 1 < len(raw) and raw[i + 1] in _ESCAPABLE:
            end = i + 2
        elif raw[i] == "`" and i in closes:
            end = closes[i]
        elif raw[i] == "`":
            i = run_end.get(i, i + 1)
            continue
        elif raw.startswith("](", i):
            depth, end = 1, i + 2
            while end < len(raw) and depth:
                if raw[end] == "\\":
                    end += 2
                    continue
                depth += {"(": 1, ")": -1}.get(raw[end], 0)
                end += 1
            end = min(end, len(raw))
        elif raw.startswith("][", i):
            close = raw.find("]", i + 2)
            end = len(raw) if close < 0 else close + 1
        elif raw.startswith("![", i):
            close = raw.find("]", i + 2)
            end = len(raw) if close < 0 else close
        elif not angle_unclosed and raw[i] == "<" and _ANGLE_OPEN.match(raw, i):
            close = raw.find(">", i + 1)
            if close >= 0:
                end = close + 1
            else:
                angle_unclosed = True
        if end > i:
            out[i:end] = MASK * (end - i)
            i = end
        else:
            if raw[i] in "[]":
                out[i] = " "
            i += 1
    return "".join(out), in_comment


def _is_table_delimiter(text):
    cells = text.strip().strip("|").split("|")
    return len(cells) >= 2 and all(re.fullmatch(r"\s*:?-{3,}:?\s*", c) for c in cells)


def split_lines(text):
    """Split on physical newlines only (``\\n``, ``\\r\\n``, ``\\r``)."""
    return re.split(r"\r\n|\r|\n", text)


def scan(text):
    rows = []
    fence = None
    front = False
    comment = False
    quote = False
    list_indent = None
    list_blank = False
    for index, raw in enumerate(split_lines(text)):
        row = Row(index + 1, raw, "")
        rows.append(row)
        if index == 0 and raw.strip() == "---":
            front = True
            continue
        if front:
            if raw.strip() in ("---", "..."):
                front = False
            continue
        if fence:
            match = _FENCE.match(raw)
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
        if quote and not _ATX.match(raw) and not _LIST.match(raw) and not _FENCE.match(raw):
            continue
        quote = False
        # A fence inside a comment is data; comment syntax inside a fence is data.
        match = _FENCE.match(raw) if not comment else None
        if match:
            fence = (match[1][0], len(match[1]))
            continue
        indent = len(raw[:len(raw) - len(raw.lstrip(" \t"))].expandtabs(4))
        if not comment and indent >= (list_indent or 0) + 4:
            continue
        clean, comment = _mask_inline(raw, comment)
        if not clean.replace(MASK, " ").strip():
            continue
        if re.match(r"^ {0,3}\[[^\]]+\]:", raw):
            continue
        marker = _LIST.match(clean)
        heading = _ATX.match(clean)
        if (_THEMATIC.fullmatch(clean) or _SETEXT.fullmatch(clean)) and list_indent is None:
            row.kind, row.text = "prose", clean
            continue
        if marker:
            inner_fence = _FENCE.match(raw[marker.end():])
            list_indent = len(raw[:marker.end()].expandtabs(4))
            list_blank = False
            if inner_fence:
                fence = (inner_fence[1][0], len(inner_fence[1]))
                row.kind, row.text = "list", " " * len(raw)
                continue
            row.kind = "list"
            row.content_start = min(marker.end(), (_LIST.match(raw) or marker).end())
            clean = " " * marker.end() + clean[marker.end():]
        elif heading:
            row.kind, row.level = "heading", len(heading[1])
            row.content_start = min(heading.end(), (_ATX.match(raw) or heading).end())
            clean = " " * heading.end() + clean[heading.end():]
            closing = re.search(r"[ \t]+#+[ \t]*$", clean)
            if closing:
                clean = clean[:closing.start()] + " " * (len(clean) - closing.start())
            list_indent = None
        elif list_indent is not None and (indent >= list_indent or not list_blank):
            row.kind = "list-continuation"
        elif raw.startswith("    ") or raw.startswith("\t"):
            continue
        else:
            row.kind = "prose"
            list_indent = None
        row.text = clean

    in_table = False
    for index, row in enumerate(rows):
        previous = rows[index - 1] if index else None
        if row.kind == "prose" and _is_table_delimiter(row.text) and previous and previous.kind == "prose" and "|" in previous.text:
            previous.kind = row.kind = "table"
            in_table = True
            continue
        if in_table and row.kind == "prose" and "|" in row.text:
            row.kind = "table"
            continue
        in_table = False
        if row.kind == "prose" and _SETEXT.fullmatch(row.text) and previous and previous.kind == "prose":
            previous.kind, previous.level = "heading", 1 if "=" in row.text else 2
            row.kind = "excluded"
        elif row.kind == "prose" and _THEMATIC.fullmatch(row.text):
            row.kind = "excluded"
    return rows


def _is_sentence_end(visible, i):
    char = visible[i]
    if char in _FULL_STOPS:
        return True
    if char in "?!":
        # Half-width marks end Japanese sentences under the house notation
        # ("保存しますか? 次へ"), but not URLs, code-like text or "?!" runs.
        following = visible[i + 1] if i + 1 < len(visible) else " "
        preceding = visible[i - 1] if i else " "
        return following.isspace() or (not following.isascii() and not preceding.isascii())
    return False


class Document:
    def __init__(self, text):
        self.text = text
        self.rows = scan(text)

    def rows_of(self, kinds):
        return [row for row in self.rows if row.kind in kinds]

    def sentences(self, kinds=PROSE_KINDS):
        found = []
        for row in self.rows_of(kinds):
            visible = row.visible
            start = 0
            for i in range(len(visible) + 1):
                if i == len(visible) or _is_sentence_end(visible, i):
                    left, right = start, i
                    while left < right and visible[left].isspace():
                        left += 1
                    while right > left and visible[right - 1].isspace():
                        right -= 1
                    if right > left:
                        found.append(Sentence(row, left, right))
                    start = i + 1
        return found

    def paragraphs(self, kinds=PROSE_KINDS):
        """Runs of consecutive rows of the given kinds; anything else separates them."""
        groups, current = [], []
        for row in self.rows:
            if row.kind in kinds:
                current.append(row)
            elif current:
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        return groups

    def char_count(self):
        return len(self.text)
