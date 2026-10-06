import importlib.util
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("note_access_format_test", ROOT / "notefmt.py")
fmt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fmt)

SAMPLE = (Path(__file__).resolve().parent / "fixtures" / "editor_sample.html").read_text(encoding="utf-8")
UUID = re.compile(r'(name|id)="[0-9a-f-]{36}"')


def no_ids(text: str) -> str:
    return UUID.sub("", text)


def assets(info):
    return {url: {"url": url, **dims} for url, dims in info["images"].items()}


def roundtrip(markdown: str) -> str:
    """Markdown -> note HTML -> Markdown, with any local image standing in as an uploaded asset."""
    blocks = fmt.parse_markdown(markdown)
    images = {b["src"]: {"url": b["src"], "width": 620, "height": 465} for b in blocks if b["t"] == "image"}
    body, _ = fmt.render_html(blocks, images)
    return fmt.html_to_markdown(body)[0]


def test_the_editor_sample_round_trips_exactly():
    markdown, info = fmt.html_to_markdown(SAMPLE)
    assert info["warnings"] == []
    assert len(info["raw"]) == 4 and len(info["images"]) == 3
    body, length = fmt.markdown_to_html(markdown, assets(info), info["raw"])
    assert no_ids(body) == no_ids(SAMPLE)  # byte for byte, apart from fresh block ids
    assert length > 0
    assert fmt.html_to_markdown(body)[0] == markdown


def test_the_sample_reads_as_the_documented_markdown():
    markdown, _ = fmt.html_to_markdown(SAMPLE)
    for line in ("[TOC]", "## 大見出し：テキスト装飾", "### 小見出し：文章の配置",
                 "通常の文章です。**ここは太字**、~~ここは取り消し線~~、[ここはリンク](https://note.com/)です。",
                 "-> この段落は中央寄せにします。 <-", "-> この段落は右寄せにします。", "- 箇条書き 1", "1. 番号付き 1",
                 "> これは引用ブロックです。", "```\n// コードブロック", "---", "<br>", "[sound](note-block:",
                 "[file: sample-file.zip](note-block:", "[embed: youtube https://www.youtube.com/watch?v=jNQXAC9IVRw]"):
        assert line in markdown, line


def test_render_matches_the_editor_dialect():
    body, length = fmt.markdown_to_html("## 見出し\n\n本文 **太字**\n二行目\n\n-> 中央 <-\n\n1. a\n2. b\n\n> 引用\n>\n> — 出典\n\n"
                                        "```\nx < 1\n```\n\n---\n\n[TOC]\n\n<br>\n")
    assert no_ids(body) == (
        "<h2  >見出し</h2><p  >本文 <strong>太字</strong><br>二行目</p>"
        '<p style="text-align: center;"  >中央</p>'
        '<ol data-start="1"  ><li><p  >a</p></li><li><p  >b</p></li></ol>'
        "<figure  ><blockquote><p  >引用</p></blockquote><figcaption>出典</figcaption></figure>"
        "<pre  ><code>x &lt; 1</code></pre><hr  ><table-of-contents  ><br></table-of-contents><p  ><br></p>")
    assert length == len("見出し") + len("本文 太字\n二行目") + len("中央") + 2 + len("引用") + len("x < 1")
    ids = re.findall(r'name="([0-9a-f-]{36})" id="\1"', body)
    assert len(ids) == len(set(ids)) == 12


@pytest.mark.parametrize("markdown", [
    "plain\n",
    "a **b** ~~c~~ [d](https://e.example/f?g=1)\n",
    "line one\nline two\n",
    "a\n<br>b\n",                       # two breaks in a row
    "<br>starts with a break\n",
    "- a\n- b\n\n1. c\n2. d\n",
    "3. starts at three\n4. next\n",
    "- one item\n  continued\n",
    "> one\n>\n> two\n>\n> — [src](https://s.example/)\n",
    "> just a quote\n",
    "-> right only\n",
    "-> centred\nover two lines <-\n",
    "````\n```inner fences```\n````\n",
    "![cap](pic.png \"alt text\")\n",
    "[![cap](pic.png)](https://link.example/)\n",
    "ルビ｜漢字《かんじ》と数式 $${E=mc^2}$$\n",
    "$$\ny = x^2\n$$\n",
])
def test_markdown_round_trips(markdown):
    assert roundtrip(markdown) == markdown


@pytest.mark.parametrize("text", [
    "- not a list", "1. not a list", "# not a heading", "> not a quote", "--- not a rule", "---", "```",
    "[TOC]", "<br>", "-> not aligned", "![not](an image)", "[x](note-block:1234567890ab)",
    "a * b ** c ~ d ~~ e [f] g \\ h", "ends with <-", "— not a source",
])
def test_literal_text_that_looks_like_markdown_survives(text):
    body = f'<p name="u" id="u">{text.replace("<", "&lt;")}</p>'
    markdown = fmt.html_to_markdown(body)[0]
    blocks = fmt.parse_markdown(markdown)
    assert [b["t"] for b in blocks] == ["p"]
    assert fmt.inline_text(blocks[0]["inline"]) == text


def test_quote_whose_last_paragraph_starts_like_a_source():
    body = ('<figure name="u" id="u"><blockquote><p name="a" id="a">x</p><p name="b" id="b">— y</p></blockquote>'
            "<figcaption></figcaption></figure>")
    markdown = fmt.html_to_markdown(body)[0]
    block = fmt.parse_markdown(markdown)[0]
    assert block["source"] is None and fmt.inline_text(block["paras"][1]) == "— y"


def test_breaks_never_leave_a_blank_line_inside_a_paragraph():
    body = '<p name="u" id="u">a<br><br><br>b<br> <br>c</p>'
    markdown = fmt.html_to_markdown(body)[0]
    assert "\n\n" not in markdown.strip()
    assert fmt.inline_text(fmt.parse_markdown(markdown)[0]["inline"]) == "a\n\n\nb\n\nc"


@pytest.mark.parametrize("markdown, message", [
    ("# h1\n", "two heading levels"),
    ("#### h4\n", "two heading levels"),
    ("- a\n  - nested\n", "flat"),
    ("  - indented\n", "flat"),
    ("[x](javascript:alert(1))\n", "https://"),
    ("```\nnever closed\n", "never closed"),
    ("> - list in quote\n", "paragraphs only"),
    ("[![x](a.png)](ftp://x)\n", "image link"),
])
def test_what_note_cannot_hold_is_refused_with_its_line(markdown, message):
    with pytest.raises(fmt.FormatError, match=message):
        fmt.parse_markdown(markdown)


def test_kept_blocks_and_images_must_be_known():
    with pytest.raises(fmt.FormatError, match="not a block of this draft"):
        fmt.markdown_to_html("[x](note-block:0123456789ab)\n")
    with pytest.raises(fmt.FormatError, match="not prepared"):
        fmt.markdown_to_html("![x](a.png)\n")


def test_unknown_blocks_are_kept_verbatim_and_unknown_inline_keeps_its_text():
    body = ('<p name="a" id="a">x <em>y</em></p><div name="0123456789ab" id="0123456789ab"><b>z</b></div>'
            '<ul name="0123456789bb" id="0123456789bb"><li><p name="c" id="c">1</p><ul><li><p>2</p></li></ul></li></ul>')
    blocks, info = fmt.blocks_from_html(body)
    assert [b["t"] for b in blocks] == ["p", "raw", "raw"]
    assert info["warnings"] == ["<em> formatting is not kept (its text is)"]
    markdown = fmt.blocks_to_markdown(blocks)
    rebuilt, _ = fmt.markdown_to_html(markdown, raw=info["raw"])
    assert '<div name="0123456789ab" id="0123456789ab"><b>z</b></div>' in rebuilt
    assert '<ul name="0123456789bb" id="0123456789bb"><li>' in rebuilt


def test_linked_images_read_back_as_linked_images():
    body = ('<figure name="u" id="u"><a href="https://x.example/" target="_blank" rel="nofollow noopener">'
            '<img src="https://assets.st-note.com/img/1-a.png" alt="alt" width="620" height="325"></a>'
            "<figcaption>cap</figcaption></figure>")
    markdown, info = fmt.html_to_markdown(body)
    assert markdown == '[![cap](https://assets.st-note.com/img/1-a.png "alt")](https://x.example/)\n'
    assert info["images"] == {"https://assets.st-note.com/img/1-a.png": {"width": 620, "height": 325}}


def test_image_paths_with_spaces_use_angle_brackets():
    block = fmt.parse_markdown("![c](<My Pictures/a b.png>)\n")[0]
    assert block["src"] == "My Pictures/a b.png"


@pytest.mark.parametrize("size, shown", [((800, 600), (620, 465)), ((1240, 400), (620, 200)), ((300, 200), (300, 200))])
def test_body_images_are_shown_at_most_620_wide(size, shown):
    assert fmt.scaled(*size) == shown


def test_text_is_escaped_in_html():
    body, _ = fmt.markdown_to_html('<script>alert("x")</script> & [a](https://x.example/?a=1&b="2")\n')
    assert "<script>" not in body and "&lt;script&gt;" in body
    assert 'href="https://x.example/?a=1&amp;b=&quot;2&quot;"' in body


def test_image_alt_and_caption_with_quotes_and_backslashes_survive_repeated_edits():
    u = "0b2f7c1e-4a5d-4e6f-8a9b-1c2d3e4f5a6b"
    body = (f'<figure name="{u}" id="{u}"><img src="https://assets.st-note.com/img/1-a.png" alt='
            '"A &quot;quote&quot; \\ back" width="620" height="325"><figcaption>c [x] \\ "y"</figcaption></figure>')
    markdown, info = fmt.html_to_markdown(body)
    for _ in range(3):
        rebuilt, _ = fmt.markdown_to_html(markdown, assets(info))
        assert no_ids(rebuilt) == no_ids(body.replace('"620" height="325">', '"620" height="325" contenteditable="false" '
                                                        'draggable="false">'))
        markdown = fmt.html_to_markdown(rebuilt)[0]


# --- marks a reader would see ---------------------------------------------------------------------

@pytest.mark.parametrize("markdown, message", [
    ("text\n\n[[image:save-location]]\n", "insertion marker"),
    ("see [[table:prices]] below\n", "insertion marker"),
    ("| a | b |\n", "no tables"),
    ("a | b\n---|---\n", "no tables"),
    ("> | quoted | table |\n", "no tables"),
    ("x <!-- hidden --> y\n", "HTML comment"),
])
def test_marks_a_reader_would_see_are_refused_with_their_line(markdown, message):
    with pytest.raises(fmt.FormatError, match=r"line \d+: .*" + message):
        fmt.parse_markdown(markdown)
    assert fmt.parse_markdown(markdown, refuse_marks=False)


def test_marks_inside_code_or_escaped_are_text():
    for markdown in ("```\n| a | b |\n[[image:x]]\n<!-- c -->\n```\n", "\\[\\[image:x\\]\\]\n", "\\| a | b |\n",
                     "\\<!-- not a comment -->\n", "one | two\n"):
        assert fmt.scan(markdown) == [] or all(i["kind"] not in fmt.REFUSED for i in fmt.scan(markdown)), markdown
        fmt.parse_markdown(markdown)


@pytest.mark.parametrize("markdown, kind", [
    ("an *italic* word\n", "italic"),
    ("日本語の*強調*です\n", "italic"),
    ("run `ls` here\n", "code"),
    ("a <span>tag</span>\n", "html"),
    ("a claim[^1]\n", "footnote"),
    ("inline ![x](https://x.example/a.png) image\n", "image"),
    ("<https://example.com>\n", "autolink"),
])
def test_markdown_note_has_no_form_for_is_named_and_saved_as_typed(markdown, kind):
    found = fmt.scan(markdown)
    assert [i["kind"] for i in found] == [kind] and found[0]["line"] == 1
    fmt.parse_markdown(markdown)   # saved as typed, not refused


def test_what_note_does_hold_is_not_named():
    markdown = ("## h\n\n**bold** ~~strike~~ [l](https://x.example/) a<br>b\n\n- a\n\n> q\n>\n> — s\n\n"
                "![c](a.png \"alt\")\n\n[TOC]\n\n<br>\n\n---\n\na * b * c 2 ** 3\n")
    assert fmt.scan(markdown) == []


@pytest.mark.parametrize("text", ["| a | b |", "|---|---|", "a | b |", ":--|--:", "x <!-- y --> z", "[[image:x]]"])
def test_stored_text_that_looks_like_a_mark_round_trips_as_text(text):
    body = f'<p name="u" id="u">{text.replace("<", "&lt;")}</p>'
    markdown = fmt.html_to_markdown(body)[0]
    blocks = fmt.parse_markdown(markdown)
    assert fmt.inline_text(blocks[0]["inline"]) == text


@pytest.mark.parametrize("body", [
    '<h2 name="u" id="u">| a | b |</h2>',
    '<ul name="u" id="u"><li><p name="a" id="a">| a | b |</p></li><li><p name="b" id="b">x &lt;!-- y</p></li></ul>',
    '<figure name="u" id="u"><blockquote><p name="a" id="a">| a | b |</p></blockquote>'
    '<figcaption>[[image:x]] &lt;!-- c</figcaption></figure>',
    '<p style="text-align: center;" name="u" id="u">| a | b |</p>',
    '<p style="text-align: right;" name="u" id="u">|---|---|</p>',
    '<p name="u" id="u"><a href="https://e.example/[[image:x]]">l</a> <a href="https://e.example/&lt;!--">m</a></p>',
    '<p name="u" id="u"><a href="https://e.example/a*b*c">l</a></p>',
])
def test_every_block_that_only_looks_like_a_mark_round_trips(body):
    markdown = fmt.html_to_markdown(body)[0]
    assert all(i["kind"] not in fmt.REFUSED for i in fmt.scan(markdown)), markdown
    again = fmt.html_to_markdown(fmt.markdown_to_html(markdown)[0])[0]
    assert again == markdown


def test_a_link_address_is_never_read_as_a_mark():
    assert fmt.scan("[l](https://e.example/[[image:x]]) and [m](https://e.example/a*b*)\n") == []


def test_an_unclosed_fence_hides_nothing_from_the_save():
    assert fmt.scan("```\n| a | b |\n") == []
    with pytest.raises(fmt.FormatError, match="never closed"):
        fmt.parse_markdown("```\n| a | b |\n")
