# Sheet design by use case

Use when creating a sheet or tab, or when proposing a restructure. Each rule
gives one reason. The sheets are edited by people in the browser and by you
through the API, often at the same time, so rules that keep either side from
breaking the other come first. Sources: Google's Sheets help and API guides,
ICAEW's 20 principles for good spreadsheet practice (2024), and Wickham's
"Tidy Data".

## Rules for every sheet

- **One header row, one record per row.** No merged cells, blank spacer rows,
  repeated headers or subtotal rows inside data. Filters, sorts, pivots and
  API reads all assume a plain rectangle. Put decoration on presentation tabs.
- **A stable text ID column, first and frozen.** Never derive identity from
  the row number, `ROW()`, sort order or a name that can change. Sorting and
  inserting move rows; an ID stays with its record.
- **Typed columns.** One meaning and one type per column. Phones, ids, postal
  codes and barcodes are text (write them with `raw`), because leading zeros
  and `+` disappear otherwise. Dates are real dates. Status is a single-choice
  dropdown, not free text and not a multi-select chip.
- **Checkboxes only for yes/no.** An unchecked box cannot mean both "not
  done" and "does not apply". Give "not applicable" its own column or status.
- **Inputs apart from formulas.** Keep calculated columns out of the columns
  people and you write, and protect them. A pasted value silently replaces a
  formula.
- **Document the columns.** A `README` (or legend) tab lists each column's
  meaning, type, allowed values, what blank means, who writes it, the time
  zone and the units. People and agents read the same contract.
- **Set locale and time zone before data goes in.** They decide how dates and
  numbers are read for everyone. Changing them later re-reads the whole file.
- **Protect structure, not secrets.** Protect headers, IDs, formulas and
  option lists with real editor limits; a warning-only protection blocks
  nothing. Protected or hidden cells are still readable and exportable.
- **Personal views over shared sorting.** Give filter views ("my queue",
  "needs approval") instead of sorting or filtering the shared view. Sort
  whole rows only, never one column.
- **Conditional formatting shows problems.** Duplicate IDs, missing required
  fields, overdue dates, contradictions such as "sent" without a date. Colour
  is a signal, never the stored state.
- **Name a version before bulk changes.** The user can return to it; you
  cannot.
- **Native table or plain range.** A table suits a human-facing tracker or
  catalogue (column types, dropdown and checkbox columns, banding, its own
  views); append to it with `table`. Column types only warn on bad input, so
  validate your own writes. A file another system reads as CSV gets a plain
  `Export` tab instead. Chart, pivot and conditional-format ranges cannot use
  table references, so give them explicit ranges.

## A. Outreach and sales ledger

- **Tabs:** `Leads` (one row per lead), option lists, `Summary`. When a lead
  gets several messages or replies, add `Interactions` (one row per contact:
  id, lead id, time, sender, direction, text) rather than more columns.
- **Columns:** lead id, name, phone as text, source link, status dropdown,
  sender, last contact date, next action date, consent kept apart from
  progress, notes. Messages in a fixed set of languages get one column each,
  with the approved text separate from drafts.
- **Ownership:** each column has one writer, for example drafts by you and
  status and sent dates by the sender. Write only your own columns, check the
  key and the target cells, and read back. Duplicate-send prevention needs a
  single sender, not a cell check.
- **Views:** freeze the header and the id and name columns. Add filter views
  for "to send", "needs review" and "follow-up due".
- **Summary:** `COUNTIFS` on a separate tab. Keep "leads contacted" apart
  from "messages sent"; they count different things.

## B. Checklist and progress tracker

- **Tabs:** one tab per project with the same columns, a `Progress` tab and
  option lists. With many projects, one `Items` tab with a project column
  scales better.
- **Columns:** item id with a project prefix (`SOH-01`), item, owner
  dropdown, due date, an applicable column or `N/A` status, the fixed tick
  columns, notes.
- **Completion:** done items ÷ applicable items, never ticks ÷ all rows.
  Show `N/A` when nothing applies. Derive "complete" from the ticks, or keep
  a separate manual status such as "blocked", never both editable.
- **Protect** ids, item definitions and the `Progress` formulas; leave owner,
  ticks, dates and notes editable.
- **Highlight** overdue applicable items, blocked items and missing owners.

## C. Report source and dashboard

- **Tabs:** `Raw_<source>` (one event per row, never edited by hand),
  `Overrides` (keyed corrections that survive a re-import), `Summary`,
  `Dashboard`.
- **Columns:** event id, date and time, category from a list, measures with
  units, where the row came from.
- **Totals:** `COUNTIFS` for a few fixed figures, `QUERY` for repeatable
  grouped tables, pivots for exploring. Periods run from the start date up to,
  not including, the next start; state the week start and the time zone.
- **Refresh:** mark a refresh with an id and a status so readers do not see
  half-replaced data.

## D. Master data, inventory and catalogue

- One authoritative tab per entity with an immutable id; movements and
  history live in their own tabs.
- Other tabs refer to the id, never to a name or row position, with exact
  lookups (`XLOOKUP`, or `VLOOKUP(…, FALSE)`). Flag missing matches and
  duplicate ids.
- Deactivate instead of deleting a referenced record.
- `IMPORTRANGE` copies with a delay and opens the whole source file to the
  destination's editors. Import one bounded range once per file and look it
  up locally.

## E. Receiving or handing over a list

- Keep the received file as it came. Work in `Incoming_Raw` → `Validated` →
  `Export`, with a `Manifest` tab (batch id, source, received time, counts
  received, accepted, rejected and duplicated).
- Record provenance on every row: batch id, source file, source row and
  source id beside your own id.
- Write identifiers, phones and partner text as text (`raw`). Keep the
  original text next to any parsed value.
- The `Export` tab is plain: row-one header, no merges, totals or notes
  above it. After exporting, check the header, column order, row count,
  leading zeros, dates and line breaks. A Drive CSV export holds the first
  tab only.
- Hand over a frozen copy, not a tab people are still editing, and import a
  new batch into staging instead of over a worked tab.
