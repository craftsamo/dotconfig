"""Mechanical naturalness score derived from naturalness findings.

score = max(100 - (critical*8 + warn*4 + info*0.5) * 1000 / max(chars, 1000), 20)

Only default-lane naturalness findings count; experimental structure
heuristics, reading-load pointers and other modes never do. The value is a
starting point for a diagnosis, not a verdict on authorship or quality.
"""

WEIGHTS = {"critical": 8.0, "warn": 4.0, "info": 0.5}
FLOOR = 20.0
MIN_CHARS = 100
BANDS = ((90, "natural"), (70, "minor"), (50, "needs_revision"), (0, "strong"))


def band(value):
    return next(name for floor, name in BANDS if value >= floor)


def compute(findings, doc_chars, scored_rules, complete):
    counts = {severity: 0 for severity in WEIGHTS}
    for finding in findings:
        if finding["mode"] == "naturalness" and finding["rule_id"] in scored_rules:
            counts[finding["severity"]] += 1
    result = {"value": None, "band": None, "deduction": None, "counts": counts,
              "doc_chars": doc_chars, "complete": complete, "reason": None}
    if doc_chars < MIN_CHARS:
        result["reason"] = "too_short"
        return result
    if not complete:
        result["reason"] = "naturalness_unverified"
        return result
    raw = sum(WEIGHTS[s] * n for s, n in counts.items())
    deduction = raw * 1000 / max(doc_chars, 1000)
    value = round(max(100 - deduction, FLOOR), 1)
    result.update(value=value, band=band(value), deduction=round(deduction, 2))
    return result
