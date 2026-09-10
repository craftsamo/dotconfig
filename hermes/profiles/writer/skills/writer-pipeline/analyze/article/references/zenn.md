# Analyzing Zenn Articles

Separate technical reasoning from Markdown syntax and verified execution.
Check whether stated prerequisites, versions, snippets and reported results
support the requested conclusion. Do not run code merely because it appears
in the article, or infer that a fenced example was tested.

The official guide documents Markdown and Zenn extensions. Compare syntax
against that guide where relevant; a syntactically plausible source is not
an observed preview. Missing images or an unresolved embed remain outside
visual assessment even if the surrounding explanation is clear.
Documented source forms include headings, lists, bold/italic, links, fenced
code, tables, quotes, images and supported-service embeds. Arbitrary HTML
is not assumed; a documented syntax feature is not an executed preview.

Documentary source (checked 2026-09-08):
https://zenn.dev/zenn/articles/markdown-guide

## Test the Explanation Against Its Snippet

If the requested analysis concerns a technical claim, identify the exact
code expression, input and version context it depends on. Assess what the
source shows separately from what it claims was run. Undefined terms or
ambiguous referents matter when they prevent this reader from following the
code/claim relationship, not because technical writing must avoid jargon.

Locally authored example (hypothetical Python excerpt, no execution):
Quote: "`len(names)` counts the letters in each name." The supplied snippet
defines `names = ["Ada", "Bo"]`.
Finding: the expression counts list entries rather than characters within
each entry. Reader impact: someone following the explanation would choose
the wrong operation for per-name lengths. Cite both the expression and the
claim; report the mismatch without editing code or providing a replacement
article. This semantic reading is not a measured run or performance result.

Retain: valid supplied Markdown, accurate technical repetition and a fence
that already has enough explanation for its stated expert audience. Do not
recommend replacing all tables or callouts with prose. If a snippet merely
illustrates an idea and is labeled accordingly, lack of run output is not
automatically a defect unless the article promises reproducible execution.

QA evidence: quote each disputed claim with its relevant code and technical
conditions, state the reasoning and reader impact, and name unknown runtime
facts. Distinguish a definite mismatch from uncertain library behavior that
needs documentation. Leave source and production notes unchanged; source
syntax, semantic reasoning and an unperformed Zenn preview remain separate.

Local adaptation of [natural-japanese v1.5.0 readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(clear referents, fact versus inference) and [genre notes](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md)
(technical precision); Zenn analysis choices and the example are local adaptations.
