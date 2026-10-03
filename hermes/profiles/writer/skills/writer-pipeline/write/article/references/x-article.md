# X Articles

An X Article uses the dedicated rich-text editor. It is not a long post or
a thread; do not promise raw Markdown import. The canonical source is
Markdown, and each element is applied with the editor's own control when the
article is assembled. Editor controls observed 2026-10-01 (toolbar and the
挿入 menu; rendering of each was not separately tested):

| Expression | Editor control | Source handling |
| --- | --- | --- |
| Bold, italic, strikethrough | Toolbar | `**bold**`, `*italic*`, `~~strike~~` |
| Headings | 本文 style menu | `##` / `###` headings |
| Quote | Toolbar | `>` quote block |
| Bulleted and numbered lists | Toolbar | `-` and `1.` lists |
| Links | Toolbar | Markdown links on the words they belong to, not bare URL lines |
| Link preview card | 挿入 → リンクのプレビュー | A URL on its own line only when a card is wanted; say so in the notes |
| Table | 挿入 → 表 | Markdown pipe table; rebuilt as the native table |
| Code | 挿入 → コード | Fenced code block |
| Math | 挿入 → LaTeX | `$...$` / `$$...$$` only for a real formula |
| Divider | 挿入 → 仕切り | `---` |
| Images, GIFs | 挿入 → メディア / GIF画像 | `[[image:id]]` marker at the claim it supports, with production notes |
| X post embed | 挿入 → ポスト | `[[embed:id]]` marker with the post URL in the notes |
| Emoji | Toolbar | Plain text; use only if the voice does |
| Image alt/caption, HTML/comments | Not observed | Record the desired content; assume no hidden comments |

Use these as the content needs them: a comparison readers check goes in a
table, a calculation can be a formula or code, a cited source is a link.
Do not drop a supported element because the voice is casual.

An explanatory or comparison article normally interleaves figures through
the body (one per distinct job: where the difference is, how it works, its
size, a threshold) rather than a text wall; plan them as markers even when no
asset exists yet, and report needs-assets.

Keep the opening understandable outside the article's full context, but do
not turn every article into a promotional hook. Preserve useful headings
and complete reasoning; do not split the draft into posts to fit an assumed
limit. A request for a thread belongs to the Post family instead.

Provide readable source plus any required editor operations, not a claim of
uploaded rich text. Article eligibility and account-specific capabilities
must be checked before publishing. Subscription requirements can change;
neither this skill nor a successful source draft grants access or approval.

Source: https://help.x.com/en/using-x/articles

## Deliver the Title's Promise

If a section may be entered through a shared excerpt or heading, give its
opening enough compact standalone context to identify the subject and claim.
Do not repeat the entire introduction. Make the title's promise specific to
what the body establishes, then carry the mechanism and caveat into the
section where they matter. A promotional hook is not a required opening.

Locally authored example (hypothetical explanatory article):
Title: "Why a saved page can show yesterday's information."
Section opening: "A saved copy can be older than the live page. Reusing that
copy avoids a new fetch, but does not establish what the site shows now."
Reason: the section names the object instead of opening with "This changes
everything," and its caveat survives excerpting. The title promises an
explanation, not an unsupported fix for every browser or a viral result.

Retain: a restrained opening that already orients the reader, a useful
descriptive heading, and enough detail to follow a technical distinction.
Compact does not mean post-sized: do not delete necessary conditions or
split the article into a thread. A conclusion can stop at the supported
implication without a follow, subscribe or purchase appeal.

QA evidence: connect the title's key promise to a quoted body passage.
Read each section opening on its own, identifying any missing subject or
ambiguous backward reference, then check it in full context before changing it.
Trace caveats through the closing claim; strong wording is not engagement
evidence. Keep rich-text assembly and account access explicitly unverified.

Local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
(informative openings, bounded endings) and [readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(paragraph orientation); X Article context choices and the example are locally authored.
