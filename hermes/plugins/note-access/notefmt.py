"""note-access format: Markdown <-> the HTML note's editor stores (format 4.x).

note keeps an article body as editor HTML: top-level blocks that each carry one UUID as both
``name`` and ``id``. This module turns the Markdown the Assistant writes into exactly that
dialect, and a stored body back into the same Markdown, so a draft read and written again
round-trips. Anything note cannot hold is refused with the line it is on, never dropped.

Markdown (one block per paragraph, blank lines between blocks):

    ## heading / ### subheading          (note has these two levels only)
    plain text, **bold**, ~~strike~~, [link](https://…); a line break inside a paragraph is kept
    -> centred <-  /  -> right aligned   (alignment of a paragraph)
    - item / 1. item                     (flat lists; ol keeps its first number)
    > quoted paragraph … > — source      (a quote; a last line "— …" is its source)
    ```  code  ```                       (code block; a language tag is ignored)
    ---                                  (divider)
    [TOC]                                (table of contents)
    ![caption](path-or-url "alt")        (an image on its own line; [![…](…)](https://…) links it)
    <br>                                 (an empty paragraph)
    [label](note-block:<uuid>)           (a block kept as it is: embeds, files, sounds, …)

Ruby (｜漢字《かんじ》) and math ($${…}$$, or a paragraph between $$ lines) are plain text in
note and rendered when the article is published, so they pass through unchanged. A backslash
escapes a character that would otherwise be read as Markdown.
"""

from __future__ import annotations

import html
import re
import uuid

MAX_IMAGE_WIDTH = 620
ESCAPABLE = set("\\`*_{}[]()#+-.!~>|<—\"")
VOID = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "col", "area", "embed", "param"}
LINK_SCHEMES = ("http://", "https://", "mailto:")
BLOCK_SCHEME = "note-block:"


class FormatError(ValueError):
    pass


# --- Markdown -> blocks ---------------------------------------------------------------------------
#
# Inline nodes: ("text", s) | ("br",) | ("strong", [nodes]) | ("s", [nodes]) | ("a", href, [nodes]).
# Blocks: {"t": "p" | "h2" | "h3", "inline": nodes, "align"?: "center" | "right"}, {"t": "empty"},
# {"t": "ul" | "ol", "items": [nodes], "start"?: n}, {"t": "quote", "paras": [nodes], "source": nodes},
# {"t": "code", "text": s}, {"t": "hr"}, {"t": "toc"}, {"t": "image", "src", "caption", "alt"},
# {"t": "raw", "id", "label"}. Every block also carries "line" (1-based) when parsed from Markdown.

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
HR = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
UL = re.compile(r"^([-*+])[ \t]+(.*)$")
OL = re.compile(r"^(\d{1,9})\.[ \t]+(.*)$")
_IMG = r'!\[((?:\\.|[^\]\\])*)\]\(\s*(<[^<>\n]+>|\S+?)(?:\s+"((?:\\.|[^"\\])*)")?\s*\)'
IMAGE = re.compile(r"^" + _IMG + r"\s*$")
LINKED_IMAGE = re.compile(r"^\[" + _IMG + r"\]\((\S+?)\)\s*$")
INLINE_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
RAW = re.compile(r"^\[((?:\\.|[^\]\\])*)\]\(" + re.escape(BLOCK_SCHEME) + r"([0-9a-fA-F-]{8,64})\)\s*$")
TOC = re.compile(r"^\[TOC\]\s*$", re.IGNORECASE)
EMPTY = re.compile(r"^<br\s*/?>\s*$", re.IGNORECASE)
INDENTED_ITEM = re.compile(r"^[ \t]+(?:[-*+]|\d{1,9}\.)[ \t]+")


def _unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: m.group(1) if m.group(1) in ESCAPABLE else m.group(0), text)


def _starts_block(line: str) -> bool:
    return bool(FENCE.match(line) or HEADING.match(line) or HR.match(line) or line.startswith(">")
                or UL.match(line) or OL.match(line) or IMAGE.match(line) or LINKED_IMAGE.match(line)
                or RAW.match(line) or TOC.match(line) or EMPTY.match(line))


def _closer(text: str, marker: str, start: int) -> int:
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text.startswith(marker, i):
            return i
        i += 1
    return -1


def _bracket_end(text: str, start: int) -> int:
    """Index of the ']' closing the '[' at start, or -1."""
    depth, i = 0, start
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def parse_inline(text: str, line: int = 0) -> list:
    out: list = []
    buf: list[str] = []

    def flush():
        if buf:
            out.append(("text", "".join(buf)))
            buf.clear()

    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text) and text[i + 1] in ESCAPABLE:
            buf.append(text[i + 1])
            i += 2
            continue
        if c == "\n":
            flush()
            out.append(("br",))
            i += 1
            continue
        if c == "<":
            br = INLINE_BR.match(text, i)
            if br:
                flush()
                out.append(("br",))
                i = br.end()
                continue
        for marker, tag in (("**", "strong"), ("~~", "s")):
            if text.startswith(marker, i):
                end = _closer(text, marker, i + 2)
                if end > i + 2:
                    flush()
                    out.append((tag, parse_inline(text[i + 2:end], line)))
                    i = end + 2
                    break
        else:
            if c == "[":
                end = _bracket_end(text, i)
                if end > i and text.startswith("(", end + 1):
                    close = text.find(")", end + 2)
                    href = text[end + 2:close].strip() if close > 0 else ""
                    if close > 0 and href and " " not in href:
                        if not href.lower().startswith(LINK_SCHEMES):
                            raise FormatError(f"line {line}: a link must start with https://, http:// or mailto: "
                                              f"({href[:60]})")
                        flush()
                        out.append(("a", href, parse_inline(text[i + 1:end], line)))
                        i = close + 1
                        continue
            buf.append(c)
            i += 1
            continue
    flush()
    return out


def parse_markdown(text: str) -> list[dict]:
    """The blocks of a Markdown body; raises FormatError naming the line of anything note cannot hold."""
    if not isinstance(text, str):
        raise FormatError("body must be Markdown text")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        line, number = lines[i], i + 1
        if not line.strip():
            i += 1
            continue
        fence = FENCE.match(line)
        if fence:
            mark = fence.group(1)
            body, i = [], i + 1
            while i < len(lines) and not re.match(r"^ {0,3}" + re.escape(mark[0]) + "{" + str(len(mark)) + r",}\s*$",
                                                  lines[i]):
                body.append(lines[i])
                i += 1
            if i >= len(lines):
                raise FormatError(f"line {number}: the code block is never closed with {mark}")
            blocks.append({"t": "code", "text": "\n".join(body), "line": number})
            i += 1
            continue
        if TOC.match(line):
            blocks.append({"t": "toc", "line": number})
            i += 1
            continue
        if EMPTY.match(line):
            blocks.append({"t": "empty", "line": number})
            i += 1
            continue
        if HR.match(line):
            blocks.append({"t": "hr", "line": number})
            i += 1
            continue
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if level not in (2, 3):
                raise FormatError(f"line {number}: note has two heading levels, ## and ###; "
                                  f"{'#' * level} is not one of them")
            content = (heading.group(2) or "").strip()
            if not content:
                raise FormatError(f"line {number}: an empty heading")
            blocks.append({"t": f"h{level}", "inline": parse_inline(content, number), "line": number})
            i += 1
            continue
        image = IMAGE.match(line) or LINKED_IMAGE.match(line)
        if image:
            src = image.group(2)
            if src.startswith("<") and src.endswith(">"):
                src = src[1:-1].strip()
            block = {"t": "image", "caption": _unescape(image.group(1)).strip(), "src": src,
                     "alt": _unescape(image.group(3) or ""), "line": number}
            if image.re is LINKED_IMAGE:
                link = image.group(4)
                if not link.lower().startswith(LINK_SCHEMES):
                    raise FormatError(f"line {number}: an image link must start with https://, http:// or mailto:")
                block["link"] = link
            blocks.append(block)
            i += 1
            continue
        raw = RAW.match(line)
        if raw:
            blocks.append({"t": "raw", "id": raw.group(2).lower(), "label": _unescape(raw.group(1)), "line": number})
            i += 1
            continue
        if line.startswith(">"):
            quoted = []
            while i < len(lines) and lines[i].startswith(">"):
                quoted.append(re.sub(r"^> ?", "", lines[i]))
                i += 1
            blocks.append(_quote(quoted, number))
            continue
        if UL.match(line) or OL.match(line):
            block, i = _list(lines, i)
            blocks.append(block)
            continue
        if line[:1] in (" ", "\t") and INDENTED_ITEM.match(line):
            raise FormatError(f"line {number}: note lists are flat; nested items are not possible")
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not _starts_block(lines[i]):
            para.append(lines[i].strip())
            i += 1
        blocks.append(_paragraph(para, number))
    return blocks


def _paragraph(lines: list[str], number: int) -> dict:
    block = {"t": "p", "line": number}
    if lines[0].startswith("-> "):
        lines = [lines[0][3:]] + lines[1:]
        if lines[-1].endswith(" <-"):
            lines[-1] = lines[-1][:-3]
            block["align"] = "center"
        else:
            block["align"] = "right"
    block["inline"] = parse_inline("\n".join(lines), number)
    return block


def _quote(lines: list[str], number: int) -> dict:
    paras, current = [], []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        elif current:
            paras.append(current)
            current = []
    if current:
        paras.append(current)
    if not paras:
        raise FormatError(f"line {number}: an empty quote")
    source = None
    last = paras[-1]
    if len(last) == 1 and last[0].startswith(("— ", "-- ")):
        source = parse_inline(last[0][2:].strip() if last[0].startswith("— ") else last[0][3:].strip(), number)
        paras = paras[:-1]
        if not paras:
            raise FormatError(f"line {number}: a quote holds only its source")
    for para in paras:
        for line in para:
            if _starts_block(line) and not line.startswith(("$$",)):
                if HEADING.match(line) or UL.match(line) or OL.match(line) or FENCE.match(line) or IMAGE.match(line) \
                        or line.startswith(">"):
                    raise FormatError(f"line {number}: a note quote holds paragraphs only "
                                      "(no headings, lists, code, images or nested quotes)")
    return {"t": "quote", "paras": [parse_inline("\n".join(p), number) for p in paras], "source": source,
            "line": number}


def _list(lines: list[str], i: int) -> tuple[dict, int]:
    number = i + 1
    ordered = bool(OL.match(lines[i]))
    pattern = OL if ordered else UL
    first = pattern.match(lines[i])
    marker = None if ordered else first.group(1)
    block = {"t": "ol" if ordered else "ul", "items": [], "line": number}
    if ordered:
        block["start"] = int(first.group(1))
    while i < len(lines):
        match = pattern.match(lines[i])
        if not match or (not ordered and match.group(1) != marker):
            break
        item, i = [match.group(2).strip()], i + 1
        while i < len(lines) and lines[i].strip() and lines[i][:1] in (" ", "\t"):
            if INDENTED_ITEM.match(lines[i]):
                raise FormatError(f"line {i + 1}: note lists are flat; nested items are not possible")
            item.append(lines[i].strip())
            i += 1
        if not item[0] and len(item) == 1:
            raise FormatError(f"line {number}: an empty list item")
        block["items"].append(parse_inline("\n".join(item), number))
    return block, i  # a blank line ends the list: note keeps separate lists apart


# --- blocks -> note HTML --------------------------------------------------------------------------

def _id() -> str:
    return str(uuid.uuid4())


def _attrs(block_id: str) -> str:
    return f'name="{block_id}" id="{block_id}"'


def inline_html(nodes: list) -> str:
    out = []
    for node in nodes:
        kind = node[0]
        if kind == "text":
            out.append(html.escape(node[1], quote=False))
        elif kind == "br":
            out.append("<br>")
        elif kind == "strong":
            out.append(f"<strong>{inline_html(node[1])}</strong>")
        elif kind == "s":
            out.append(f"<s>{inline_html(node[1])}</s>")
        elif kind == "a":
            out.append(f'<a href="{html.escape(node[1], quote=True)}" target="_blank" rel="nofollow noopener">'
                       f"{inline_html(node[2])}</a>")
    return "".join(out)


def inline_text(nodes: list) -> str:
    out = []
    for node in nodes:
        if node[0] == "text":
            out.append(node[1])
        elif node[0] == "br":
            out.append("\n")
        else:
            out.append(inline_text(node[-1]))
    return "".join(out)


def _p(nodes: list, extra: str = "") -> str:
    block_id = _id()
    return f"<p{extra} {_attrs(block_id)}>{inline_html(nodes) or '<br>'}</p>"


def scaled(width: int, height: int) -> tuple[int, int]:
    """The size note shows a body image at: at most MAX_IMAGE_WIDTH wide, proportions kept."""
    if width <= MAX_IMAGE_WIDTH:
        return width, height
    return MAX_IMAGE_WIDTH, max(1, round(height * MAX_IMAGE_WIDTH / width))


def render_html(blocks: list[dict], images: dict | None = None, raw: dict | None = None) -> tuple[str, int]:
    """(body HTML, text length). images maps an image block's src to {"url", "width", "height"} (the
    note asset it became); raw maps a kept block's id to its stored HTML."""
    images, raw = images or {}, raw or {}
    parts, length = [], 0
    for block in blocks:
        kind = block["t"]
        block_id = _id()
        if kind == "p":
            align = block.get("align")
            parts.append(_p(block["inline"], f' style="text-align: {align};"' if align else ""))
            length += len(inline_text(block["inline"]))
        elif kind == "empty":
            parts.append(f"<p {_attrs(block_id)}><br></p>")
        elif kind in ("h2", "h3"):
            parts.append(f"<{kind} {_attrs(block_id)}>{inline_html(block['inline'])}</{kind}>")
            length += len(inline_text(block["inline"]))
        elif kind in ("ul", "ol"):
            start = f' data-start="{block.get("start", 1)}"' if kind == "ol" else ""
            items = "".join(f"<li>{_p(item)}</li>" for item in block["items"])
            parts.append(f"<{kind}{start} {_attrs(block_id)}>{items}</{kind}>")
            length += sum(len(inline_text(item)) for item in block["items"])
        elif kind == "quote":
            paras = "".join(_p(para) for para in block["paras"])
            source = inline_html(block["source"]) if block.get("source") else ""
            parts.append(f"<figure {_attrs(block_id)}><blockquote>{paras}</blockquote>"
                         f"<figcaption>{source}</figcaption></figure>")
            length += sum(len(inline_text(para)) for para in block["paras"])
        elif kind == "code":
            parts.append(f"<pre {_attrs(block_id)}><code>{html.escape(block['text'], quote=False)}</code></pre>")
            length += len(block["text"])
        elif kind == "hr":
            parts.append(f"<hr {_attrs(block_id)}>")
        elif kind == "toc":
            parts.append(f"<table-of-contents {_attrs(block_id)}><br></table-of-contents>")
        elif kind == "image":
            asset = images.get(block["src"])
            if not asset:
                raise FormatError(f"line {block.get('line', 0)}: the image {block['src'][:80]} was not prepared")
            img = (f'<img src="{html.escape(asset["url"], quote=True)}" '
                   f'alt="{html.escape(block.get("alt") or "", quote=True)}" width="{int(asset["width"])}" '
                   f'height="{int(asset["height"])}" contenteditable="false" draggable="false">')
            if block.get("link"):
                img = (f'<a href="{html.escape(block["link"], quote=True)}" target="_blank" rel="nofollow noopener">'
                       f"{img}</a>")
            parts.append(f"<figure {_attrs(block_id)}>{img}"
                         f"<figcaption>{html.escape(block.get('caption') or '', quote=False)}</figcaption></figure>")
        elif kind == "raw":
            stored = raw.get(block["id"])
            if stored is None:
                raise FormatError(f"line {block.get('line', 0)}: {BLOCK_SCHEME}{block['id']} is not a block of this "
                                  "draft; kept blocks (embeds, files, sounds…) can only stay where the draft has them")
            parts.append(stored)
    return "".join(parts), length


# --- note HTML -> blocks --------------------------------------------------------------------------

class Node:
    __slots__ = ("tag", "attrs", "children", "start", "end", "text")

    def __init__(self, tag, attrs=None, start=0, text=None):
        self.tag, self.attrs, self.children, self.start, self.end, self.text = tag, attrs or {}, [], start, start, text

    def find(self, tag):
        for child in self.children:
            if child.tag == tag:
                return child
            found = child.find(tag) if child.tag else None
            if found:
                return found
        return None

    def elements(self):
        return [c for c in self.children if c.tag]

    def content_text(self) -> str:
        if self.tag is None:
            return self.text
        if self.tag == "br":
            return "\n"
        return "".join(c.content_text() for c in self.children)


TAG = re.compile(r"<(/?)([a-zA-Z][\w:-]*)((?:\s+[^\s=>/]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'>]+))?)*)\s*/?>"
                 r"|<!--.*?-->", re.DOTALL)
ATTR = re.compile(r"([^\s=>/]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'>]+)))?")


def parse_html(source: str) -> Node:
    """A small, offset-keeping tree of an editor body (well-formed HTML from note's own editor)."""
    root = Node("#root", start=0)
    stack = [root]
    pos = 0
    for match in TAG.finditer(source or ""):
        if match.start() > pos:
            stack[-1].children.append(Node(None, start=pos, text=html.unescape(source[pos:match.start()])))
        pos = match.end()
        if match.group(0).startswith("<!--"):
            continue
        closing, tag = match.group(1) == "/", match.group(2).lower()
        if closing:
            for depth in range(len(stack) - 1, 0, -1):
                if stack[depth].tag == tag:
                    for node in stack[depth:]:
                        node.end = match.end()
                    del stack[depth:]
                    break
            continue
        attrs = {}
        for a in ATTR.finditer(match.group(3) or ""):
            value = a.group(2) if a.group(2) is not None else a.group(3) if a.group(3) is not None else a.group(4) or ""
            attrs[a.group(1).lower()] = html.unescape(value)
        node = Node(tag, attrs, start=match.start())
        node.end = match.end()
        stack[-1].children.append(node)
        if tag not in VOID:
            stack.append(node)
    if pos < len(source or ""):
        stack[-1].children.append(Node(None, start=pos, text=html.unescape(source[pos:])))
    for node in stack[1:]:
        node.end = len(source or "")
    root.end = len(source or "")
    return root


INLINE_TAGS = {"strong": "strong", "b": "strong", "s": "s", "del": "s", "strike": "s", "a": "a", "br": "br",
               "span": None}


def _inline(node: Node, warnings: list[str]) -> list:
    out: list = []
    for child in node.children:
        if child.tag is None:
            text = child.text.replace("\n", " ")
            if text:
                out.append(("text", text))
        elif child.tag == "br":
            out.append(("br",))
        elif INLINE_TAGS.get(child.tag) == "strong":
            out.append(("strong", _inline(child, warnings)))
        elif INLINE_TAGS.get(child.tag) == "s":
            out.append(("s", _inline(child, warnings)))
        elif child.tag == "a" and child.attrs.get("href"):
            out.append(("a", child.attrs["href"], _inline(child, warnings)))
        else:
            if child.tag not in ("span", "a"):
                warnings.append(f"<{child.tag}> formatting is not kept (its text is)")
            out.extend(_inline(child, warnings))
    # Whitespace beside a break or at an edge is not text a reader sees (Markdown lines are read
    # without it), and the editor ends some lines with a stray <br>.
    tidy = []
    for n, node in enumerate(out):
        if node[0] == "text" and not node[1].strip():
            before = tidy[-1] if tidy else ("br",)
            after = out[n + 1] if n + 1 < len(out) else ("br",)
            if before == ("br",) or after == ("br",):
                continue
        tidy.append(node)
    while tidy and tidy[-1] == ("br",):
        tidy.pop()
    return tidy


def _only_paragraphs(node: Node) -> bool:
    return all(c.tag == "p" or (c.tag is None and not c.text.strip()) for c in node.children)


def blocks_from_html(source: str) -> tuple[list[dict], dict]:
    """(blocks, info) of a stored body. info: "raw" {block id: stored HTML} for blocks Markdown cannot
    express (kept by reference), "images" {url: {width, height}}, "warnings" [text]."""
    root = parse_html(source)
    blocks: list[dict] = []
    info = {"raw": {}, "images": {}, "warnings": []}

    def keep(node: Node, label: str):
        block_id = (node.attrs.get("name") or node.attrs.get("id") or "").lower()
        if not re.fullmatch(r"[0-9a-f-]{8,64}", block_id):
            info["warnings"].append(f"a <{node.tag}> block without an id cannot be kept on update")
            block_id = f"missing-{len(info['raw'])}"
        info["raw"][block_id] = source[node.start:node.end]
        blocks.append({"t": "raw", "id": block_id, "label": " ".join(label.split())})

    for node in root.children:
        if node.tag is None:
            if node.text.strip():
                blocks.append({"t": "p", "inline": [("text", node.text.strip())]})
            continue
        tag = node.tag
        if tag == "p":
            inline = _inline(node, info["warnings"])
            if not inline:
                blocks.append({"t": "empty"})
                continue
            block = {"t": "p", "inline": inline}
            style = node.attrs.get("style", "").replace(" ", "").lower()
            if "text-align:center" in style:
                block["align"] = "center"
            elif "text-align:right" in style:
                block["align"] = "right"
            blocks.append(block)
        elif tag in ("h2", "h3"):
            blocks.append({"t": tag, "inline": _inline(node, info["warnings"])})
        elif tag in ("h1", "h4", "h5", "h6"):
            keep(node, f"heading: {node.content_text().strip()[:60]}")
        elif tag in ("ul", "ol"):
            items, flat = [], True
            for li in node.elements():
                kids = li.elements()
                if li.tag != "li" or any(k.tag in ("ul", "ol") for k in kids) or not _only_paragraphs(li) or len(kids) > 1:
                    flat = False
                    break
                items.append(_inline(kids[0], info["warnings"]) if kids else [])
            if not flat:
                keep(node, f"list: {node.content_text().strip()[:60]}")
                continue
            block = {"t": tag, "items": items}
            if tag == "ol":
                start = node.attrs.get("data-start") or node.attrs.get("start") or "1"
                block["start"] = int(start) if start.isdigit() else 1
            blocks.append(block)
        elif tag == "figure":
            img = next((c for c in node.elements() if c.tag == "img"), None)
            link = None
            anchor = next((c for c in node.elements() if c.tag == "a"), None)
            if img is None and anchor is not None and anchor.attrs.get("href") \
                    and [c.tag for c in anchor.elements()] == ["img"] \
                    and not any(c.tag is None and c.text.strip() for c in anchor.children):
                img, link = anchor.elements()[0], anchor.attrs["href"]
            quote = next((c for c in node.elements() if c.tag == "blockquote"), None)
            caption = next((c for c in node.elements() if c.tag == "figcaption"), None)
            if node.attrs.get("embedded-service"):
                service = node.attrs["embedded-service"]
                src = node.attrs.get("data-src")
                label = f"embed: {service}" + (f" {src}" if src and src != "null" else "")
                if service == "attachment":
                    name = node.find("strong")
                    label = f"file: {name.content_text().strip() if name else 'attachment'}"
                elif service == "note-sound":
                    label = "sound"
                keep(node, label)
            elif img is not None and quote is None and len(node.elements()) <= 2:
                url = img.attrs.get("src", "")
                width, height = img.attrs.get("width", ""), img.attrs.get("height", "")
                if width.isdigit() and height.isdigit():
                    info["images"][url] = {"width": int(width), "height": int(height)}
                block = {"t": "image", "src": url, "alt": " ".join(img.attrs.get("alt", "").split()),
                         "caption": " ".join(caption.content_text().split()) if caption else ""}
                if link:
                    block["link"] = link
                blocks.append(block)
            elif quote is not None and _only_paragraphs(quote):
                paras = [_inline(p, info["warnings"]) for p in quote.elements()]
                source_nodes = _inline(caption, info["warnings"]) if caption else []
                blocks.append({"t": "quote", "paras": paras or [[]], "source": source_nodes or None})
            else:
                text = node.content_text().strip()[:60]
                keep(node, f"figure: {text}" if text else "figure")
        elif tag == "pre":
            code = node.find("code") or node
            blocks.append({"t": "code", "text": code.content_text()})
        elif tag == "hr":
            blocks.append({"t": "hr"})
        elif tag == "table-of-contents":
            blocks.append({"t": "toc"})
        else:
            keep(node, f"{tag}: {node.content_text().strip()[:60]}")
    return blocks, info


# --- blocks -> Markdown ---------------------------------------------------------------------------

def _escape_text(text: str) -> str:
    return re.sub(r"<(?=br\s*/?>)", r"\\<", re.sub(r"([\\*~\[\]])", r"\\\1", text), flags=re.IGNORECASE)


def inline_markdown(nodes: list) -> str:
    """Inline nodes as Markdown. A break is a newline, except where that would leave a blank or
    whitespace-only line (which ends a paragraph): there it is written ``<br>``."""
    out: list[str] = []

    def line_so_far() -> str:
        text = "".join(out)
        return text[text.rfind("\n") + 1:]

    for node in nodes:
        kind = node[0]
        if kind == "text":
            out.append(_escape_text(node[1]))
        elif kind == "br":
            current = line_so_far()
            if current and not current.strip():
                out[:] = ["".join(out).rstrip(" \t")]
            if not current.strip() or current.endswith("<br>"):
                out.append("<br>")
            else:
                out.append("\n")
        elif kind == "strong":
            inner = inline_markdown(node[1])
            out.append(f"**{inner}**" if inner else "")
        elif kind == "s":
            inner = inline_markdown(node[1])
            out.append(f"~~{inner}~~" if inner else "")
        elif kind == "a":
            href = node[1].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
            out.append(f"[{inline_markdown(node[2])}]({href})")
    return "".join(out)


def _guard_line(line: str) -> str:
    """Escape a paragraph line that Markdown would otherwise read as the start of another block
    (lines are read without their surrounding spaces)."""
    line = line.strip()
    ol = re.match(r"^(\d{1,9})\.([ \t])", line)
    if ol:
        return f"{ol.group(1)}\\.{line[len(ol.group(1)) + 1:]}"
    if _starts_block(line) or line.startswith("-> "):
        return "\\" + line if line[:1] in ESCAPABLE else line
    return line


def _guard(text: str) -> str:
    return "\n".join(_guard_line(line) for line in text.split("\n"))


def blocks_to_markdown(blocks: list[dict], raw_labels: bool = True) -> str:
    out = []
    for block in blocks:
        kind = block["t"]
        if kind == "p":
            text = _guard(inline_markdown(block["inline"]))
            align = block.get("align")
            if align == "center":
                text = f"-> {text} <-"
            elif align == "right":
                text = f"-> {text}"
                if text.endswith(" <-"):
                    text = text[:-2] + "\\<-"
            out.append(text)
        elif kind == "empty":
            out.append("<br>")
        elif kind in ("h2", "h3"):
            prefix = "##" if kind == "h2" else "###"
            out.append(f"{prefix} {inline_markdown(block['inline']).replace(chr(10), ' ')}")
        elif kind in ("ul", "ol"):
            lines = []
            for n, item in enumerate(block["items"]):
                marker = f"{block.get('start', 1) + n}." if kind == "ol" else "-"
                body = _guard(inline_markdown(item)).split("\n")
                lines.append(f"{marker} {body[0]}" + "".join(f"\n{' ' * (len(marker) + 1)}{rest}" for rest in body[1:]))
            out.append("\n".join(lines))
        elif kind == "quote":
            paras = []
            for para in block["paras"]:
                text = _guard(inline_markdown(para))
                paras.append("\n".join(f"> {line}" if line else ">" for line in text.split("\n")))
            if paras and paras[-1].startswith(("> — ", "> -- ")) and "\n" not in paras[-1]:
                paras[-1] = "> \\" + paras[-1][2:]
            if block.get("source"):
                paras.append(f"> — {inline_markdown(block['source']).replace(chr(10), ' ')}")
            out.append("\n>\n".join(paras))
        elif kind == "code":
            fence = "```"
            while fence in block["text"]:
                fence += "`"
            out.append(f"{fence}\n{block['text']}\n{fence}")
        elif kind == "hr":
            out.append("---")
        elif kind == "toc":
            out.append("[TOC]")
        elif kind == "image":
            caption = re.sub(r"([\\\[\]])", r"\\\1", block.get("caption") or "")
            alt = block.get("alt") or ""
            title = ' "' + re.sub(r'([\\"])', r"\\\1", alt) + '"' if alt else ""
            image = f"![{caption}]({block['src']}{title})"
            if block.get("link"):
                href = block["link"].replace(" ", "%20").replace("(", "%28").replace(")", "%29")
                image = f"[{image}]({href})"
            out.append(image)
        elif kind == "raw":
            label = re.sub(r"([\\\[\]])", r"\\\1", block.get("label") or "block")
            out.append(f"[{label}]({BLOCK_SCHEME}{block['id']})")
    return "\n\n".join(out) + ("\n" if out else "")


def html_to_markdown(source: str) -> tuple[str, dict]:
    blocks, info = blocks_from_html(source)
    return blocks_to_markdown(blocks), info


def markdown_to_html(text: str, images: dict | None = None, raw: dict | None = None) -> tuple[str, int]:
    return render_html(parse_markdown(text), images, raw)


def plain_text(source: str) -> str:
    """The readable text of a stored body (for excerpts)."""
    blocks = [node.content_text() for node in parse_html(source).children]
    return re.sub(r"\s+", " ", " ".join(blocks)).strip()
