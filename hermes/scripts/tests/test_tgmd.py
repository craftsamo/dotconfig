"""tgmd: the Markdown a script writes for Telegram's rich path, checked against the runtime's own
adapter where it decides (which path a message takes, what it refuses) so a producer built on
the helpers lands as a table or a collapsible block, not as bullets or as a skipped delivery.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tgmd.py"
SPEC = importlib.util.spec_from_file_location("tgmd", SCRIPT)
assert SPEC and SPEC.loader
T = importlib.util.module_from_spec(SPEC)
sys.modules["tgmd"] = T
SPEC.loader.exec_module(T)


def test_esc_covers_every_markup_character_and_flattens_lines():
    assert T.esc("a_b *c* [d](e) #1 | x\ny") == r"a\_b \*c\* \[d\]\(e\) \#1 \| x y"
    assert T.esc(None) == "" and T.esc(12.5) == r"12\.5"


def test_esc_leaves_a_dollar_alone():
    """`$` is no markup to either path; `$$` alone would select the rich path (documented), and an
    escaped `$` the parser did not honour would show on every price."""
    assert T.esc("$5 or $6") == "$5 or $6"


def test_raw_passes_through_every_helper():
    raw = T.Raw("**done**")
    assert T.esc(raw) == "**done**" and T.esc_in_details(raw) == "**done**"
    assert T.table(["a", "b"], [[raw, 1]]) == "| a | b |\n| :--- | :--- |\n| **done** | 1 |"


def test_table_escapes_cells_and_aligns_columns():
    out = T.table(["Name", "Amount"], [["a|b", 1200], ["x_y", "¥3,000"]], aligns=["l", "right"])
    assert out == "| Name | Amount |\n| :--- | ---: |\n| a\\|b | 1200 |\n| x\\_y | ¥3,000 |"


@pytest.mark.parametrize("headers, rows, aligns", [
    (["a", "b"], [], ["l"]),              # aligns of another width
    (["a", "b"], [], ["l", "centre"]),    # unknown align
    (["a"], [["b"]], None),               # one column is prose to the adapter
    (["a", "b"], [["only one"]], None),   # a ragged row turns the table back into prose
])
def test_table_refuses_what_the_adapter_would_not_read_as_a_table(headers, rows, aligns):
    with pytest.raises(ValueError):
        T.table(headers, rows, aligns)


def test_link_encodes_what_would_end_the_link_or_its_table_row():
    assert T.link("Maps", "https://m/x(1) y|z\n") == "[Maps](https://m/x%281%29%20y%7Cz)"
    assert T.link("a_b", "https://m/") == r"[a\_b](https://m/)"


def test_details_wraps_paragraphs_in_blank_lines_and_keeps_math_markers_out():
    out = T.details("Open (3)", "a (b) [c]", T.table(["c", "e"], [["d (1)", "[f]"]]))
    assert out == ("<details><summary>Open (3)</summary>\n\na (b) [c]\n\n"
                   "| c | e |\n| :--- | :--- |\n| d (1) | [f] |\n\n</details>")


def test_heading_and_bold():
    assert T.heading("Weekly: 2026-10", 2) == r"## Weekly: 2026\-10"
    assert T.bold("1.5x") == r"**1\.5x**"


def test_the_other_inline_pieces():
    assert T.italic("a_b") == r"*a\_b*" and T.strike("a_b") == r"~~a\_b~~" and T.spoiler("x|y") == r"||x\|y||"


def test_code_and_fence_escape_nothing_but_keep_their_own_delimiter_out():
    assert T.code("a`b_c\nd") == "`a'b_c d`"
    assert T.fence("x\n```\ny", "sh") == "```sh\nx\n'''\ny\n```"


def test_quote_lists_and_tasks():
    assert T.quote("a_b", T.bold("c")) == "> a\\_b\n> **c**"
    assert T.ul(["a.", "#b"]) == "- a\\.\n- \\#b"
    assert T.ol(["a", T.link("m", "u")]) == "1. a\n2. [m](u)"
    assert T.task(["open_1", ("done (2)", True)]) == "- [ ] open\\_1\n- [x] done \\(2\\)"


SHORT = "# r\n\n| a | c |\n| :--- | :--- |\n| b | d |\n"
LONG = SHORT + "\n<details><summary>s</summary>\n\n" + "x" * 200 + "\n\n</details>\n"


def test_clamp_leaves_a_short_report_alone_and_cuts_a_long_one_before_its_details():
    assert T.clamp(SHORT, limit=100) == SHORT
    assert T.clamp(LONG, limit=100, attach="/tmp/r.md", note="Full candidate report:") == (
        SHORT + "\nFull candidate report:\nMEDIA:/tmp/r.md\n")
    assert T.clamp(LONG, limit=100).endswith("| b | d |\n\nFull report:\n")


def test_clamp_cuts_a_head_that_is_itself_too_long_at_a_line_that_fits():
    assert T.clamp("p1\n\np2\n\n" + "y" * 50 + "\n", limit=20) == "p1\n\np2\n\nFull report:\n"
    assert T.clamp("l1\nl2\n" + "y" * 50 + "\n", limit=10) == "l1\nl2\n\nFull report:\n"
    assert T.clamp("<details>\n" + "y" * 50 + "\n</details>\n", limit=10, attach="/f") == "Full report:\nMEDIA:/f\n"


def test_cli_table_details_clamp_and_esc():
    def run(*args, stdin):
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True,
                              text=True, check=True).stdout

    assert run("table", "--header", "a,b", "--align", "l,r", stdin="x_1\t2\n") == \
        "| a | b |\n| :--- | ---: |\n| x\\_1 | 2 |\n"
    assert run("details", "--title", "T", stdin="l1\nl2\n") == \
        "<details><summary>T</summary>\n\nl1\n\nl2\n\n</details>\n"
    assert run("clamp", "--limit", "4", "--attach", "/f", stdin="ab\n\n<details>\nz\n</details>\n") == \
        "ab\n\nFull report:\nMEDIA:/f\n"
    assert run("esc", stdin="a*b\n") == "a\\*b\n"
    assert run("task", stdin="[x] done\nopen_1\n") == "- [x] done\n- [ ] open\\_1\n"
    assert run("list", "--ordered", stdin="a\nb\n") == "1. a\n2. b\n"
    assert run("quote", stdin="a\n\nb\n") == "> a\n> b\n"
    assert run("fence", "--lang", "sh", stdin="ls\n") == "```sh\nls\n```\n"


# --- against the runtime's adapter -------------------------------------------------------------


@pytest.fixture(scope="module")
def tg():
    adapter = pytest.importorskip("plugins.platforms.telegram.adapter")
    return adapter.TelegramAdapter.__new__(adapter.TelegramAdapter)  # class-level regexes only


def test_a_table_details_or_task_list_selects_the_rich_path_and_prose_does_not(tg):
    assert tg._needs_rich_rendering(T.table(["a", "b"], [["c", "d"]]))
    assert tg._needs_rich_rendering(T.details("t", "p"))
    assert tg._needs_rich_rendering(T.task(["a"]))
    for prose in (f"{T.heading('h')}\n\n{T.ul(['a_b'])}", T.quote("q"), T.fence("x"), f"{T.bold('b')} {T.code('c')}"):
        assert not tg._needs_rich_rendering(prose), prose


def test_the_plain_path_keeps_code_and_fence_bodies_as_written(tg):
    """On the plain path the adapter protects code spans and fences and escapes only a backslash
    inside them, so an unescaped body is right there too."""
    out = tg.format_message(f"{T.code('a_b.c')}\n{T.fence('x_y')}")
    assert "`a_b.c`" in out and "x_y" in out


def test_escaped_brackets_in_details_would_make_the_adapter_skip_rich(tg):
    naive = "<details><summary>t</summary>\n\n" + T.esc("Open (3) [x]") + "\n\n</details>"
    assert tg._has_telegram_desktop_details_math_crash_shape(naive)
    built = T.details("Open (3)", "Open (3) [x]", T.table(["a", "b"], [["(1)", T.link("m [1]", "u")]]))
    assert not tg._has_telegram_desktop_details_math_crash_shape(built)


def test_a_literal_hash_prefix_in_a_cell_stays_prose_on_the_rich_path(tg):
    from plugins.platforms.telegram.rich_markdown import escape_literal_hash_prefixes
    cell = T.table(["ref", "sev"], [["#43 nanoid", "high"]])
    assert escape_literal_hash_prefixes(cell) == cell  # already escaped by esc, nothing to add


def test_the_plain_fallback_still_reads_an_escaped_table_as_text(tg):
    """When Telegram refuses the rich message the adapter re-sends through MarkdownV2; the escaped
    cells survive that conversion (as text with visible backslashes at worst, never an error)."""
    out = tg.format_message(T.table(["a", "b"], [["x_y", "1"]]))
    assert "x" in out and "y" in out
