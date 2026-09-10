# Editing Blog Drafts

Preserve the existing engine's syntax and metadata. A source edit must not
silently change slugs, redirects, asset URLs, code blocks or custom shortcodes.
Unknown rendering behavior stays unverified rather than being normalized to
the editor's preferred Markdown dialect.

Changing destination is a format migration requiring explicit scope. Identify
unsupported features and propose replacements without discarding their meaning.
Keep production notes and unresolved asset IDs separate from publishable text.
No CMS configuration, plugin installation, deployment or live edit is authorized.

## Revise Only the Reader Obstacle

If wording scope covers a sentence with an unclear actor or referent,
clarify that relationship using supplied context. Structure changes such as
moving the answer or renaming sections need their own authorization; a
proofread does not become a reader-journey redesign. Unknown audience and
house notation are reasons to preserve supplied usage, not invent conventions.

Locally authored example (wording scope, context names the browser's cache):
Before: "It keeps the old page, so it can show it again."
After: "The browser's cache keeps the old page, so the browser can show it again."
Reason: repeating the object costs words but removes competing referents;
shortness alone is not the goal. Apply this only if that actor is established
in the source, not inferred from the article's topic.
In proofread scope, this already grammatical sentence is an optional suggestion,
not an applied correction. Protected quotations remain unchanged.

Retain: clear prose, the author's familiar terminology and useful uneven
section lengths. Do not sweep all headings into a single conclusion format
or convert independent lists to paragraphs merely to make the style uniform.
If nothing within scope warrants correction, preserve a verified no-op,
including layout and the trailing newline.

QA evidence: show the changed passage, its source referent and the specific
reader ambiguity removed. Compare protected text and untouched sections with
the original. State missing context rather than silently selecting an actor;
source wording checks do not establish unknown CMS rendering or house rules.

Local adaptation of [natural-japanese v1.5.0 revision guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/revision-guide.md)
(selective revision, keep good passages) and [readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(clear referents before brevity); blog scope decisions and the example are locally authored.
