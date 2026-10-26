# Rendered Web UI - acceptance

Machines measure, you compare against what the user approved, and the user
judges the look when something new appears.

## Where the results are

The build runs OpenCode's `web_ui_check` tool on the changed pages; ask it to
pass `baseline` = `~/Workspaces/Projects/<Group>/assets/ui-baseline/<repo>/`
when that directory exists. With the job directory as the run's `output_dir`,
each check lands in `<job>/ui-check/<timestamp>/`: the tool's summary is in the
run's reply, `report.json` holds the measurements, `screens/` the screenshots
and `compare/` one baseline | current | diff image per page with
`compare.json`. The summary's `Output:` line names where a check actually
wrote. A summary that says the check could not run is not a pass.

## 1. Mechanical failures

Every failure the change introduced is fixed, or named with a reason the user
accepted. A rendered change without a check is a defect: send it back.

## 2. Baseline comparison

Look at the comparison images of pages with a change, a few at a time (only
the newest three images in a request stay visible). For each change, decide
whether the approved scope explains it: the page the plan said would change, in
the way it said. A change on a page that should not change, or a different kind
of change (layout, spacing, type, color, density) than agreed, is not explained.

## 3. The user's look approval

Show the user the comparison images, or the new screenshots, and ask only
when:

- no baseline exists yet for a page in scope (first build), or
- a change is not explained by the approved scope, or
- the approved change itself is a new look the user has not seen.

Otherwise do not ask: report the comparison in one line. A change the user
rejects goes back to the build session as a concrete correction.

## Baseline promotion

When the user approves a look, copy the approved screenshots from that check's
`screens/` into the baseline directory, replacing same-named files, and check
the file count. That approval is the promotion consent for these files only.
Never promote screenshots the user has not seen. Never open a development
target in your own logged-in browser profile.
