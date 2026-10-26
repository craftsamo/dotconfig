# Release notes

Use the supplied change scope, release/version status, affected users and
known adoption steps. These notes explain changes; a promotional announcement
with a new angle is copy, not a reason to embellish a factual changelog.

Group changes by user impact when useful. Make breaking behavior, migration
requirements and known limitations findable. Explain what changed and what
the reader needs to do, without turning internal commit subjects into the
whole narrative or inventing benefits.

Preserve the distinction between planned, unreleased and shipped changes.
Do not infer a release date from a branch name, a commit timestamp or the
current date. Do not invent migration commands or claim compatibility with
versions/platforms absent from the supplied evidence.

## Describe the user's changed behavior

Translate an implementation change into the supported before/after behavior
for affected users. Attach release status and version scope where they govern
availability. Explain impact concretely, and include action only when readers
need to do something and the supplied material supports that action. This is
an entry-writing guide, not a mandatory set of changelog categories.

Keep planned, unreleased and shipped entries visibly separate. A merged change
may still be unreleased. Do not give all entries the same weight: a breaking
input change needs its condition and adoption path near the claim; an internal
cleanup with no documented user effect does not justify a fabricated benefit.
No date, migration command or "no action required" assurance comes from silence.

## Worked example and retain condition

Fictional teaching material: release material marks v2.4 shipped. CSV exports
now include a header row; positional importers must be configured to skip it.
Export scheduling is planned, with no date. No migration command is supplied.

An entry can read: "v2.4, shipped: CSV exports now include a header row.
If your importer treats the first row as data, configure it to skip the
header before importing these exports. Export scheduling remains planned;
no availability date is supplied."
This names the changed output, affected workflow and conditional action
without promising scheduling or inventing a shell command for every importer.

Retain a short "Corrected the Export button label" when that is the entire
supplied user-visible change. It does not need a migration section or a
performance claim. "Scheduling is now available" would misstate the plan;
a commit date cannot resolve the missing release date.

QA: for entries in scope, connect behavior, status and impact to their source;
check adoption wording only where action is supported and necessary.

QA: every change and adoption claim traces to the release material, status
is accurate, and important qualifications remain attached. A polished draft
is not a published release or permission to tag, post or ship software.

Source: selective emphasis and explicit uncertainty adapted from [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md).
Release-entry construction and the fictional example are local applications, not upstream quotations.
