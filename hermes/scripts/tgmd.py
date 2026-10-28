#!/usr/bin/env python3
"""tgmd — the Markdown a script writes for Telegram, in the dialect Hermes' adapter renders.

A ``no_agent`` cron job's stdout and a webhook route's rendered text reach Telegram through
the same adapter as a reply. The adapter sends ordinary Markdown through two paths, chosen
per message by its content (``docs/ops/telegram-markdown.md``):

* the **plain** path, for prose, headings, lists, bold, code and links: standard Markdown is
  converted to MarkdownV2 and every stray punctuation character is escaped by the adapter —
  a producer writes nothing special, and a backslash it adds is shown as one;
* the **rich** path, for a message holding a pipe table, a task list, a line-start
  ``<details>`` or ``$$``: the Markdown goes to Telegram as written, so dynamic text inside
  such a message (a counterparty, an address, a category name) must be escaped by the
  producer, or an ``_``, ``*``, ``|`` or ``#`` in it becomes markup.

This module is the second path's toolkit: ``esc`` for a dynamic inline string; ``table``,
``details`` and ``task`` for the constructs that select the path; ``link`` / ``bold`` / ``italic``
/ ``strike`` / ``spoiler`` / ``code`` / ``heading`` for the inline pieces, ``quote`` / ``fence`` /
``ul`` / ``ol`` for the blocks around them; and ``clamp`` to keep a long report inside one message
with the rest attached as a file. Stdlib only, importable by path:

    import importlib.util, os
    _spec = importlib.util.spec_from_file_location(
        "tgmd", os.environ.get("TGMD_PATH", os.path.expanduser("~/.config/hermes/scripts/tgmd.py")))
    tgmd = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(tgmd)

or run as a command from a shell wrapper (``tgmd table``, ``tgmd details``, ``tgmd task``,
``tgmd list``, ``tgmd quote``, ``tgmd fence``, ``tgmd clamp``, ``tgmd esc``; ``--help`` lists them).
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Iterable, Optional, Sequence

# Every character the rich parser can read as markup outside code; ``<``/``>`` keep a literal
# tag out of the message, where the rich path would render it (or the plain fallback refuse it).
_ESCAPE_RE = re.compile(r"([\\`*_\[\]()~>#+\-=|{}.!<>])")
# ``\(`` … ``\)`` and ``\[`` … ``\]`` are inline-math markers to the adapter's check for math inside
# <details>, which crashes Telegram Desktop: it refuses the rich path for the whole message.
_MATH_MARKER_RE = re.compile(r"\\([()\[\]])")
_DETAILS_LINE_RE = re.compile(r"(?m)^<details\b")
_URL_UNSAFE = {" ": "%20", "(": "%28", ")": "%29", "|": "%7C", "<": "%3C", ">": "%3E"}
DEFAULT_LIMIT = 3800  # bytes: one message on the plain path (4096 UTF-16 units) after escaping


class Raw(str):
    """Markdown already rendered (by this module, or by hand): the helpers pass it through. Joining
    or formatting a Raw gives a plain ``str`` again — wrap the result (``Raw(f"{bold(x)} …")``)
    before handing it to a helper, or it is escaped a second time."""


def esc(text) -> str:
    """A dynamic inline string, safe inside a rich message; line breaks become spaces."""
    if isinstance(text, Raw):
        return str(text)
    flat = ("" if text is None else str(text)).replace("\r", " ").replace("\n", " ")
    return _ESCAPE_RE.sub(r"\\\1", flat)


def esc_in_details(text) -> str:
    """``esc`` for text inside ``<details>``: no escaped bracket (``\\(`` … ``\\)``, ``\\[`` … ``\\]``),
    which the adapter reads as math there and refuses. A ``Raw`` gets the same treatment, since a
    table cell or a link label it holds was escaped for the open."""
    return _MATH_MARKER_RE.sub(r"\1", esc(text))


def bold(text) -> Raw:
    return Raw(f"**{esc(text)}**")


def italic(text) -> Raw:
    return Raw(f"*{esc(text)}*")


def strike(text) -> Raw:
    return Raw(f"~~{esc(text)}~~")


def spoiler(text) -> Raw:
    """``||text||``; its pipes make it unfit for a table cell."""
    return Raw(f"||{esc(text)}||")


def code(text) -> Raw:
    """Inline code: nothing inside is escaped (a backslash would show), so a backtick in the text,
    which would end the span, becomes a straight quote; line breaks become spaces."""
    flat = ("" if text is None else str(text)).replace("\r", " ").replace("\n", " ").replace("`", "'")
    return Raw(f"`{flat}`")


def fence(text, lang: str = "") -> Raw:
    """A code block; nothing inside is escaped, and a backtick fence inside the text, which would end
    the block, becomes three straight quotes."""
    body = ("" if text is None else str(text)).replace("```", "\'\'\'").strip("\n")
    return Raw(f"```{lang}\n{body}\n```")


def link(label, url) -> Raw:
    """``[label](url)``; a character that would end the link or the table row holding it (a space,
    a parenthesis, a pipe, an angle bracket) is percent-encoded in the URL."""
    safe_url = "".join(_URL_UNSAFE.get(c, c) for c in str(url) if c not in "\r\n")
    return Raw(f"[{esc(label)}]({safe_url})")


def heading(text, level: int = 2) -> Raw:
    """``## text``; the plain path shows it bold, the rich one as a heading."""
    return Raw(f"{'#' * max(1, min(6, level))} {esc(text)}")


def quote(*lines) -> Raw:
    """A blockquote, one ``> `` line per argument (each escaped unless ``Raw``). A collapsible block
    is ``details``: the quote that folds is MarkdownV2's alone, and the rich path does not read it."""
    return Raw("\n".join(f"> {esc(line)}" for line in lines))


def ul(items: Iterable) -> Raw:
    """A bullet list, each item escaped unless ``Raw``."""
    return Raw("\n".join(f"- {esc(item)}" for item in items))


def ol(items: Iterable) -> Raw:
    """A numbered list, each item escaped unless ``Raw``."""
    return Raw("\n".join(f"{n}. {esc(item)}" for n, item in enumerate(items, 1)))


def task(items: Iterable) -> Raw:
    """A task list: an item is a string (open) or a ``(text, done)`` pair. Selects the rich path."""
    def one(item):
        text, done = (item, False) if isinstance(item, str) else (item[0], bool(item[1]))
        return f"- [{'x' if done else ' '}] {esc(text)}"
    return Raw("\n".join(one(item) for item in items))


def table(headers: Sequence, rows: Iterable[Sequence], aligns: Optional[Sequence[str]] = None) -> Raw:
    """A pipe table. ``aligns`` holds ``left`` / ``right`` (or ``l`` / ``r``) per column. Every cell is
    escaped unless it is ``Raw`` (a ``link``, a ``bold``). Selects the rich path — from two columns
    on: the adapter reads a one-column table as prose and shows its pipes. A row of another width
    is refused (it would turn the table back into prose)."""
    headers = list(headers)
    if len(headers) < 2:
        raise ValueError("table: at least two columns (a one-column table is not one to Telegram)")
    aligns = list(aligns or ["left"] * len(headers))
    if len(aligns) != len(headers):
        raise ValueError(f"table: {len(headers)} headers but {len(aligns)} aligns")
    unknown = [a for a in aligns if a not in ("left", "right", "l", "r")]
    if unknown:
        raise ValueError(f"table: unknown align {unknown[0]!r} (left/right)")
    separator = ["---:" if a in ("right", "r") else ":---" for a in aligns]

    def row(cells, escape=True):
        cells = list(cells)
        if len(cells) != len(headers):
            raise ValueError(f"table: row of {len(cells)} cells under {len(headers)} headers: {cells!r}")
        values = [esc(c) if escape else str(c) for c in cells]
        return "| " + " | ".join(values) + " |"

    return Raw("\n".join([row(headers), row(separator, escape=False), *(row(r) for r in rows)]))


def details(title, *parts) -> Raw:
    """A collapsible ``<details>`` block. Each part is a paragraph: a string is escaped (and
    flattened to one line), a ``Raw`` (a ``table``) is kept; every part loses the escaped brackets
    the adapter would read as math. Parts are separated by blank lines, which the rich parser
    needs around a table. Selects the rich path."""
    body = "\n\n".join(esc_in_details(p) for p in parts)
    return Raw(f"<details><summary>{esc_in_details(title)}</summary>\n\n{body}\n\n</details>")


def clamp(text: str, limit: int = DEFAULT_LIMIT, attach: Optional[str] = None,
          note: str = "Full report:") -> str:
    """``text`` when it fits ``limit`` UTF-8 bytes (the default fits one message on the plain path,
    whose limit is 4096 UTF-16 units); otherwise its head — up to the first ``<details>`` line, and
    when that is still too long, to the last blank line (else line) that fits — followed by
    ``note`` and, with ``attach``, a ``MEDIA:<path>`` line so Hermes sends the file with it."""
    def size(s: str) -> int:
        return len(s.encode("utf-8"))

    if size(text) <= limit:
        return text
    cut = _DETAILS_LINE_RE.search(text)
    head = text[:cut.start()] if cut else text
    if size(head) > limit:
        head = head.encode("utf-8")[:limit].decode("utf-8", "ignore")
        for sep in ("\n\n", "\n"):
            if sep in head:
                head = head[:head.rfind(sep)]
                break
    tail = f"{note}\nMEDIA:{attach}\n" if attach else f"{note}\n"
    return head.rstrip("\n") + "\n\n" + tail if head.strip() else tail


def _split_list(value: Optional[str]) -> Optional[list]:
    return [v.strip() for v in value.split(",")] if value else None


def _cli_table(args) -> str:
    rows = [line.split("\t") for line in sys.stdin.read().splitlines() if line.strip()]
    return table(_split_list(args.header), rows, _split_list(args.align))


def _cli_details(args) -> str:
    return details(args.title, *[line for line in sys.stdin.read().splitlines()])


def _cli_lines(args) -> str:
    lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
    if args.command == "task":
        return task([(line[4:], line[:3].lower() == "[x]") if line[:3] in ("[ ]", "[x]", "[X]") else line
                     for line in lines])
    if args.command == "quote":
        return quote(*lines)
    return ol(lines) if args.ordered else ul(lines)


def _cli_fence(args) -> str:
    return fence(sys.stdin.read(), args.lang)


def _cli_clamp(args) -> str:
    return clamp(sys.stdin.read(), args.limit, args.attach, args.note)


def _cli_esc(args) -> str:
    return "\n".join(esc(line) for line in sys.stdin.read().splitlines())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="tgmd", description="Telegram Markdown pieces for a script; input on stdin.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("table", help="TSV rows on stdin -> pipe table")
    p.add_argument("--header", required=True, help="comma-separated column names")
    p.add_argument("--align", help="comma-separated l/r per column")
    p.set_defaults(fn=_cli_table)
    p = sub.add_parser("details", help="lines on stdin -> collapsible block")
    p.add_argument("--title", required=True)
    p.set_defaults(fn=_cli_details)
    p = sub.add_parser("task", help="lines on stdin ('[x] done' or 'open') -> task list")
    p.set_defaults(fn=_cli_lines)
    p = sub.add_parser("list", help="lines on stdin -> bullet list")
    p.add_argument("--ordered", action="store_true", help="numbered instead")
    p.set_defaults(fn=_cli_lines)
    p = sub.add_parser("quote", help="lines on stdin -> blockquote")
    p.set_defaults(fn=_cli_lines)
    p = sub.add_parser("fence", help="text on stdin -> code block")
    p.add_argument("--lang", default="")
    p.set_defaults(fn=_cli_fence)
    p = sub.add_parser("clamp", help="a report on stdin -> one message, the rest attached")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    p.add_argument("--attach", help="file to attach as MEDIA: when the report is cut")
    p.add_argument("--note", default="Full report:")
    p.set_defaults(fn=_cli_clamp)
    p = sub.add_parser("esc", help="lines on stdin -> escaped lines")
    p.set_defaults(fn=_cli_esc)
    args = parser.parse_args(argv)
    sys.stdout.write(args.fn(args))
    if args.command != "clamp":
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
