# Analyzing release notes

Check stated change scope, release status, user impact and migration guidance
against supplied release material when in scope. Do not infer a release date
or availability from a commit, branch name or the current date.

Locate hidden breaking conditions, conflicting versions or claims that go
beyond the evidence. Distinguish a factual changelog from promotional copy;
the absence of sales language is not a defect.

## Trace availability and adoption separately

For each entry in scope, distinguish user-visible changed behavior, release
status, impact and action if needed. Compare planned, unreleased and shipped
states with supplied release material, not commit chronology. An internal
change needs no invented user benefit; these guides do not require migration
instructions for a label correction or a promotional ending.

Build a finding from quote to source/evidence, mismatch and consequence for
the affected user. Classify an actual defect separately from missing evidence
and optional preference for different categories. Recommend checking a status
or correcting scope, not a replacement draft. Do not infer dates, supply
migration commands or treat analysis as release verification.

## Worked example and retain condition

Fictional teaching material: notes headed "v2.4, shipped" include "Schedule
CSV exports automatically." The supplied release material marks only header
rows shipped; scheduling remains planned, with no availability date.

Quote: "Schedule CSV exports automatically" under "v2.4, shipped."
Source: the release material distinguishes shipped headers from planned
scheduling and supplies no scheduling date.
Mismatch: placement presents planned behavior as available in this version.
Consequence: users may look for a feature they cannot yet rely on. Recommend
reconciling the status and grouping with the source, not guessing a date or
rewriting the notes as an announcement.

Retain a concise label-fix entry without an adoption action. A migration
section is optional preference unless the change and sources establish need.
If release records are absent, availability remains unverified, not disproved.
A document's failure to mention a platform does not prove incompatibility.

QA: limit findings to the supplied release scope and affected user conditions;
do not require the analysis report to contain new release entries or actions.

QA: findings anchor to the notes and known sources. Do not assert the software
actually shipped, runs correctly or supports a platform without evidence.
An analysis report neither rewrites the notes nor publishes a release.

Source: explicit uncertainty and selective emphasis adapted from [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md).
Release analysis and the fictional example are local applications, not upstream quotations.
