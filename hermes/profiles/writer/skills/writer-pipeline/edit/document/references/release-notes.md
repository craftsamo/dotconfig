# Editing release notes

Preserve release/version status, actual change scope, migration requirements
and known limitations. Do not convert unreleased work into shipped behavior,
add a release date from the current date, or invent an adoption command.

If a correction changes a compatibility claim, keep that correction traceable
to the supplied evidence. Summarize internal detail without enlarging the
feature or burying a breaking change. Promotional rewriting is a different
purpose and needs a new decision.

## Clarify impact without expanding the release

Within the released entry, explain user-visible changed behavior before
internal implementation detail. Keep status and affected users attached;
clarify an adoption action only when it is necessary and supplied. These are
editing guides, not a reason to impose categories or migrate every entry.
Separate planned, unreleased and shipped wording even after compression.

Leave untouched sections and protected content unchanged. A no-op is legitimate
for a clear factual entry. Do not invent a date, budget, compatibility range
or executable migration command. If protected release status conflicts with
the supplied correction, flag it instead of silently promoting availability.

## Worked example and retain condition

Fictional teaching material: v2.4's supplied shipped notes say CSV exports now
include a header; positional importers must skip it. The request permits
clarifying only the adoption sentence. Version/status and the separate planned
scheduling entry are protected; no importer-specific command is supplied.

Before: "Update your importer for this."
After: "If your importer treats the first row as data, configure it to skip
the new header row."
The edit names the affected reader and required action using supplied behavior.
It leaves the version, shipped status, planned scheduling and untouched entries
unchanged. It neither tells unaffected users to migrate nor invents a command.

Retain "Corrected the Export button label" when no adoption action is needed.
Adding "Upgrade immediately" would create urgency unsupported by the change.
A planned entry stays planned even if other entries in the section shipped;
today's date does not establish its release date.

QA: compare changed behavior and adoption wording with the release source;
check status boundaries around any authorized move, not unrelated releases.

QA: changed statements still match the release material; dates, qualifiers
and important adoption conditions survive. Editing this file neither tags
a release nor updates a public changelog or package registry.

Source: selective emphasis and uncertainty guidance adapted from [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md).
Release-edit decisions and the fictional example are local applications, not upstream quotations.
