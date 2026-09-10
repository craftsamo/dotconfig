# Analyzing error wording

Identify the operation, result claimed, reason and proposed recovery action.
Compare them with supplied evidence where requested. A timeout does not prove
non-delivery, an error string does not establish root cause, and a retry button
does not prove that repeating the operation is safe.

An unknown recovery path is an evidence gap, not a reason to invent instructions.
Distinguish readability concerns from system diagnosis. Quote only necessary,
sanitized text, keeping secret values and internal data out of the report.

QA: observed wording and inferred risk remain distinguishable. The report does
not verify transactions, promise recovery, repair the application or replace
the error message. Describing the text need not find a defect.
