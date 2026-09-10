# Zenn Articles

Input is Markdown source. Documentary check: 2026-09-08, against the official
guide below; no editor preview or publishing test was performed.

| Expression | Source handling |
| --- | --- |
| Headings, ordered/unordered lists, quotes | Standard Markdown forms |
| Bold, italic, links | Markdown emphasis and `[label](URL)` |
| Code | Fenced code; language/filename annotations only in the documented format |
| Tables | Markdown tables; preserve data and explanatory qualifications |
| Images | Markdown image with actual source and descriptive alt text |
| Captions | Follow the guide's caption convention; keep distinct from alt text |
| Embeds/cards | Only documented URL/service forms; unknown services remain unverified |
| Arbitrary HTML | Not assumed supported; use documented syntax or another representation |
| HTML comments | Even where supported, never use them to conceal unresolved production work |

Explain the technical setting and relevant versions before relying on them.
Separate runnable project-specific examples, illustrative snippets and
actual observed output. Do not invent successful command output or require
Zenn CLI frontmatter when the delivery is an editor-bound article. Repository
metadata follows the supplied publishing workflow, which Writer does not run.

Prefer a small explanatory example to unexplained code volume. Keep warnings
near the operation they constrain. Verify currently needed custom syntax
against the guide; no memorized character or image cap is a platform guarantee.

Source: https://zenn.dev/zenn/articles/markdown-guide

## Connect Code to the Claim

If a paragraph depends on code, establish the relevant technical context
and explain exactly which expression supports which claim. Introduce an
unfamiliar operation through what it does, then name it. Keep environment
conditions beside the result they qualify, not in a distant closing note.
Do not expand a small example into an undocumented project setup.

Locally authored example (illustrative Python, not an executed run):
For `names = ["Ada", "Bo"]` and `len(names)`, explain: "Here `len(names)`
counts the two list entries. It does not measure the characters in each name."
Reason: the prose points to the exact expression and bounds its meaning.
An accompanying "this speeds up processing" would need separate evidence;
neither a correct snippet nor its code fence demonstrates performance.
When describing supplied output, attribute the run and its actual environment.

Retain: valid supplied Markdown, a useful table, and an already clear code
fence. Do not flatten them for an abstract preference for prose or add CLI
frontmatter to simulate technical completeness. A known term need not receive
a beginner definition when the brief establishes an expert audience.
Explain a tricky branch more fully than a familiar assignment.

QA evidence: pair each technical claim with the relevant snippet, source or
attributed output. Identify unsupported conclusions separately from syntax
issues; check whether shortened prose still carries version and input limits.
Quote an ambiguous referent such as "this" and name the competing code objects.
Source-level checks do not certify execution or a rendered Zenn page.

Local adaptation of [natural-japanese v1.5.0 readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(nearby referents, reader knowledge) and [genre notes](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/genre-notes.md)
(technical precision); Zenn decisions and the example are local, not upstream platform advice.
