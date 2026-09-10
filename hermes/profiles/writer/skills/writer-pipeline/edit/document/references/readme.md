# Editing a README

Preserve the documented project/version scope, prerequisites, commands and
maintenance links unless their change is requested and supported. Do not
replace a working entry path with a guessed "simpler" command or add badges,
licenses and support promises from a style example.

When authorized heading changes affect anchors, update the known internal
references and report the change; unseen inbound links remain unverified.
Keep code fences and identifiers separate from prose edits.

## Repair the scoped entry path

Within authorized sections, connect reader goal, minimal quick start and
supported expected result before deeper detail. Move troubleshooting toward
the entry path only when structure changes are released; a wording request
does not authorize moving installation or changing its anchors. Use this as
a guide to a specific reader obstruction, not a replacement README template.

Leave untouched sections and protected content unchanged. If the entry path
is already usable, a no-op is legitimate. Unsupported commands or result
claims are conflicts to flag, not invitations to guess an executable or run
the example. Keep the source's distinction between expected and observed.

## Worked example and retain condition

Fictional teaching material: the request allows clarifying the quick-start
paragraph only. The source says File > Open accepts the sample CSV and shows
column names. The installation section and its command fence are protected.

Before: "Open the sample through File > Open. It shows them in the preview."
After: "Open the sample CSV through File > Open. The preview shows its
column names."
The edit resolves the pronouns using supplied facts without changing the
action or making a verified-run claim. The command fence, installation
section and remaining text stay unchanged; no new command is introduced.

Retain "Open the sample CSV through File > Open" when its outcome is already
clear from adjacent text. Do not repeat the result simply to fill a quick-start
pattern. If the result is undocumented, flag that gap rather than write
"Setup succeeded." A wording-only edit can return unchanged text.

QA: compare only the authorized entry wording and its affected references;
preserve the prerequisite/result relationship and report out-of-scope gaps.

QA: the edited entry task is still findable and its conditions survive.
Commands match supplied evidence; the README edit itself proves neither
execution success nor actual repository integration or Markdown rendering.

Source: reader-path guidance adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
Scoped editing decisions and the fictional example are local applications, not upstream quotations.
