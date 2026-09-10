# README

Use the supplied project purpose, supported versions, intended users and
verified entry commands. An existing README or repository convention wins
over a generic outline; do not invent badges, support promises or licenses.

Explain what the project does and the first useful task. Put prerequisites
before commands and name their expected outcomes only when supplied evidence
supports them. Link to detailed documentation rather than reproducing it in
every section. Keep installation, configuration and usage distinguishable.

For a source-only deliverable, use the requested Markdown dialect or a
portable subset. Do not claim links, code or embedded media were rendered or
executed. A plausible command derived from a product name is not evidence.

## Build the entry path

Choose the opening from the reader's goal: evaluating suitability needs a
capability boundary; getting started needs the shortest supported path to a
useful result. Follow that path with recognizable troubleshooting symptoms
and links to deeper configuration or reference material. This is a guide to
reader decisions, not a requirement to replace the repository's sections.

A minimal quick start includes the prerequisites its actions depend on and
the expected result supported by the material. Separate optional setup from
required setup rather than presenting every feature as an initial task.
If no executable entry is supplied, describe the known entry point and name
the missing instructions; never derive an executable from the project name.

## Worked example and retain condition

Fictional teaching material: a CSV viewer's supplied onboarding note says
users can open the sample through File > Open; the preview shows column
names. Its troubleshooting note says an empty preview can mean no file was
selected. No installation command or run receipt is supplied.

An entry passage could read: "Inspect a CSV's columns before importing it.
Open the supplied sample through File > Open. The onboarding note describes
a preview of the column names. If the preview is empty, check whether a file
was selected; see the supplied troubleshooting section for other cases."
The goal, small action, expected result and supported recovery are connected
without claiming that Writer opened the app or verified the behavior.

Retain a library README's existing API-first entry when its readers already
have the package installed. Adding a guessed `csv-viewer init` would be a
fabricated capability, not a more helpful quick start.

QA: for the released entry section, follow goal through prerequisite, action
and supported result; do not require unrelated installation chapters.

QA: a reader can locate the entry task, prerequisites and scope. Commands,
versions and environment names match the supplied material. Unverified setup
or destination rendering is named as a gap, not hidden behind a quick-start
example. Repository integration remains the engineer's work.

Source: reader-path distinctions adapted from [natural-japanese v1.5.0 guide](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/doctypes/guide.md).
README sequencing and the fictional example are local applications, not upstream quotations.
