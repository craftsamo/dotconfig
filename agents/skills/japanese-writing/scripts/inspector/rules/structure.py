"""Counts and proportions of formatting (bold, list markers, headings) in eligible text.

Material for judging formatting density in context; no findings are emitted.
"""

import re

from ..document import MASK, TEXT_KINDS

MODE = "structure"
MORPHOLOGY = False
BOLD = re.compile(
    r"(?<!\*)(?P<stars>\*{2,3})[^\s*](?:[^*]*?[^\s*])?(?P=stars)(?!\*)"
    r"|(?<![\w_])__[^\s_](?:[^_]*?[^\s_])?__(?![\w_])"
)
SUMMARY_HEADING = re.compile(
    r"^(?:まとめ|おわりに|終わりに|結論|総括|summary\b|conclusion\b)", re.I,
)
COUNT_KEYS = (
    "eligible_lines", "eligible_characters", "bold_spans", "bold_lines",
    "list_lines", "headings", "summary_headings",
)
SCOPE = (
    "Prose, headings, list markers and list continuations only; inline exclusions removed. "
    "Characters exclude whitespace but include remaining Markdown markers."
)
RATIOS = (
    ("bold_lines", "eligible_lines"),
    ("list_lines", "eligible_lines"),
    ("headings", "eligible_lines"),
    ("summary_headings", "headings"),
)


def run(inspection):
    counts = _counts(inspection.doc)
    inspection.section("structure", {
        "counts": counts,
        "proportions": {name: _proportion(counts, name, denominator) for name, denominator in RATIOS},
        "density": _density(counts),
        "scope": SCOPE,
        "requires_context": True,
    })
    inspection.executed("structure")


def _counts(doc):
    counts = dict.fromkeys(COUNT_KEYS, 0)
    for row in doc.rows_of(TEXT_KINDS):
        bold = len(BOLD.findall(row.text))
        heading = row.kind == "heading"
        counts["eligible_lines"] += 1
        counts["eligible_characters"] += sum(not c.isspace() and c != MASK for c in row.text)
        counts["bold_spans"] += bold
        counts["bold_lines"] += bool(bold)
        counts["list_lines"] += row.kind == "list"
        counts["headings"] += heading
        counts["summary_headings"] += heading and bool(SUMMARY_HEADING.match(row.visible.strip().strip("*_")))
    return counts


def _proportion(counts, numerator, denominator):
    value = counts[numerator] / counts[denominator] if counts[denominator] else None
    return {
        "numerator": counts[numerator], "denominator": counts[denominator],
        "denominator_name": denominator, "value": value,
    }


def _density(counts):
    characters, lines = counts["eligible_characters"], counts["eligible_lines"]
    return {
        "bold_per_1000_chars": round(counts["bold_spans"] / characters * 1000, 2) if characters else 0.0,
        "list_line_ratio": round(counts["list_lines"] / lines, 3) if lines else 0.0,
    }
