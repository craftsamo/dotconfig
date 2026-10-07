# Work report

Build a periodic work report (週報, 週次報告, 月報, 活動報告, weekly or monthly
report) for a counterpart on request, or record feedback the next report must
answer. The user submits it after one review: numbers come from records you
read yourself, each with its source; the prose answers the reader's questions
in the report's format; nothing leaves the machine without approval.

A report is your own work: it takes many turns, and you do it yourself in
this session — never a resident session, a card or a specialist. Start only
on an explicit request, never at the end of ordinary tasks. For a quick "what
did I do this week", use `/repos commits week`, `/activity week` and `/drafts`
instead.

## Engine

Everything runs through the **`work_report` tool** (`action` plus arguments;
its description lists them). Never run the `wr` script in a terminal, write a
wrapper for it, or parse its files with an inline interpreter. The period is
`YYYYMMDD-YYYYMMDD`, end exclusive; without it the last complete period. Edit
`draft.md` with the file tools; everything else is written by the tool.

## Workflow

1. **Period.** `status`; tell the user the dates you are reporting.
2. **Collect.** `collect`, then `leads` for the whole report.
3. **Understand the period per Group.** `sessions` for every Group with
   activity and with `unassigned`; `session` when a digest is not enough.
   Note what was done, what reached the outside world, what was promised or
   decided, and which sources each Group relies on.
4. **Read the numbers yourself.** For each metric `status` lists as missing,
   take the source from the leads and sessions (a spreadsheet, a chat app, a
   ledger under a Group's `data/`, a dashboard) and read it for the period now,
   read-only, with the tool that fits (the browser for web apps; a learned
   skill may describe a given source). Never write, send or edit anything in a
   source. Save what you read (the CSV export, the chat list or thread text,
   the page text) to a file, then `record` the number with its Group, source,
   method and that file as `evidence`; `count_file`/`count_time` counts a JSONL
   ledger instead; a `reason` says why a number cannot be established. A number
   you did not read in this run is not a record: never copy one from an earlier
   report, a session's claim or memory, and never estimate.
5. **Feedback.** If feedback for the previous period arrived, save it under
   `<previous period>/feedback/` and write `feedback/interpretation.md` with a
   「次回の報告で回答すること」 list; the draft answers those items.
6. **Draft.** `draft` (or `refresh`). Replace every `<!-- wr:todo … -->` in
   `draft.md`: text above `<!-- wr:detail -->` goes to both reports, below it
   to the LLM report only. Follow each section's `rule`. A result is only
   something that left the machine (merged, published, sent, paid). Decisions
   are the user's: propose them. Costs, if any, stay inside
   `<!-- wr:private -->…<!-- /wr:private -->`.
7. **Build and check.** `build`, `check`; fix `draft.md` or re-`record`, never
   the outputs. Then `render` and look at both PDFs.
8. **One approval.** Send the user the report PDF (and the LLM PDF) with the
   sources you read per number and what stays open: numbers with only a reason,
   proposals to confirm. Apply corrections and rebuild.
9. **Submit.** After approval, `submit`. Sending the files to anyone is a
   separate, explicit approval.

## Rules

- Build each report from facts, sessions and sources. Do not read an earlier
  version of the same period's report (a previous draft, a set aside by an
  older tool, a submission) as a source; it would carry its mistakes over.
- Session contents are read to understand the period, never quoted into a
  report and never shown in chat beyond a short summary.
- A report names no local path, file name or session id: call a source what it
  is (「営業台帳（表計算）」「WhatsApp の会話」). `record` refuses a path in
  source, method or note, and `check` and `render` refuse a report that names
  one; a path the author needs stays inside `wr:private`.
- Read-only everywhere except the report's own directory; never write to a
  source you read.
- `draft.md` is the authored file; `inputs.toml` is written only by `record`.
  Outputs, facts, session digests and submissions are generated or frozen.
- The definition names no source and no project; sources are found each
  period. Report definitions and formats are the user's files; `validate`
  says what is wrong with them.
- A correction after submitting is a new version whose report says what changed.
- Contents are sensitive business data: summarize in chat, never paste raw
  facts, sessions, feedback or ledgers.
