# Analyzing a README

For a structure question, examine how the text exposes project purpose,
prerequisites, first useful task and scope. Quote the entry path or the
missing connection; do not demand every conventional README section.

For correctness checks, compare commands, versions and links only with the
available specifications/evidence. Apparent syntax is not execution success,
and a URL written in the README is not proof it is accessible.

## Locate the reader's obstruction

For an entry-path question, trace reader goal through minimal quick start,
supported expected result and troubleshooting/detail. Identify the specific
connection a reader cannot make, not merely a missing conventional heading.
For correctness, use the supplied version and entry specification. These
guides do not require installation chapters for an already-installed audience.

Build a finding from quote to source/evidence, mismatch and consequence for
the requested task. Distinguish an actual defect from missing evidence and
optional preference. State a correction direction or needed evidence, not a
replacement draft. A plausible executable name does not prove the command
exists, and documented expected output does not establish a verified run.

## Worked example and retain condition

Fictional teaching material: a README says "Run `csv-viewer init` to open the
sample." The supplied entry specification says the product has no CLI and
samples open through File > Open. The question concerns the quick start.

Quote: "Run `csv-viewer init`."
Source: the supplied entry specification explicitly excludes a CLI.
Mismatch: the README documents an entry command contrary to that specification.
Consequence: readers may attempt an unsupported route before reaching the
sample. Recommend aligning the entry path with the supplied specification;
do not execute the command or provide a replacement quick-start draft.

If no entry specification is available, command support is unverified, not
disproved. Retain an API-first README for experienced library users when its
entry path fits their goal; preferring an installation-first order is optional
preference, not a demonstrated defect. An absent badge proves nothing about use.

QA: findings cover only the read entry path and the requested question; link
accessibility and setup success remain separate evidence questions.

QA: observations refer to the actual README and requested scope. Missing
environment information limits a runtime verdict, not all textual analysis.
The analysis itself does not need a new quick-start section or installation.

Source: reader-path guidance adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
Finding construction and the fictional example are local applications, not upstream quotations.
