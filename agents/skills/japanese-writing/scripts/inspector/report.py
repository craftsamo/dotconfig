"""Report assembly shared by every mode: findings, sections, limits."""

import hashlib
import json

from . import VERSION
from .morphology import SegmentTooLarge

SCHEMA_VERSION = 2
SEVERITIES = ("info", "warn", "critical")
EXCERPT = 240
MAX_OUTPUT = 262144
CAPS = {"findings": 200, "outline": 200, "terms": 200}

INTERPRETATION = (
    "Advisory candidates for a writer to judge in context. Fix, keep with a "
    "reason, or mark as missing information; zero findings does not prove quality."
)
LIMITATIONS = [
    "Limited Markdown, not full CommonMark.",
    "Sentence candidates never span physical lines; soft-wrapped sentences are split.",
    "Word lists and thresholds are heuristics calibrated on a small corpus.",
]


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None


def base(text=None, original=None):
    return {
        "status": "error",
        "schema_version": SCHEMA_VERSION,
        "inspector_version": VERSION,
        "input_sha256": sha256(text),
        "original_sha256": sha256(original),
        "request": {},
        "executed": [],
        "unverified": [],
        "findings": [],
        "score": None,
        "outline": [],
        "heading_stats": {},
        "terms": [],
        "structure": {},
        "revision": {},
        "stats": {},
        "truncation": {"applied": False, "counts": {}, "excerpt_clipped": 0, "term_clipped": 0,
                       "output_budget_dropped": 0, "section_omitted": 0},
        "dependencies": {},
        "error": None,
        "interpretation": INTERPRETATION,
        "limitations": LIMITATIONS,
    }


class Inspection:
    """Mutable state handed to each mode's ``run(inspection)``."""

    def __init__(self, document, morphology, genre, experimental, original=None, stance=None):
        self.doc = document
        self.original = original
        self.stance = stance
        self.morph = morphology
        self.genre = genre
        self.experimental = experimental
        self.report = base(document.text, original.text if original else None)
        self.report["status"] = "ok"

    def clip(self, value):
        if len(value) > EXCERPT:
            self.report["truncation"]["excerpt_clipped"] += 1
        return value[:EXCERPT]

    def executed(self, *checks):
        for check in checks:
            if check not in self.report["executed"]:
                self.report["executed"].append(check)

    def unverified(self, check, reason, line=None):
        note = {"check": check, "reason": reason}
        if line is not None:
            note["line"] = line
        if note not in self.report["unverified"]:
            self.report["unverified"].append(note)

    def tokens(self, check, line, text):
        """Tokens for ``text`` or ``None`` (recording why) when unavailable."""
        if not self.morph.available:
            self.unverified(check, self.morph.reason)
            return None
        try:
            return self.morph.tokenize(text)
        except SegmentTooLarge:
            self.unverified(check, "segment_exceeds_40000_utf8_bytes", line)
            return None

    def needs_morphology(self, *checks):
        """Record checks as executed or unverified; True when they can run."""
        if self.morph.available:
            self.executed(*checks)
            return True
        for check in checks:
            self.unverified(check, self.morph.reason)
        return False

    def finding(self, mode, rule_id, severity, line, column, excerpt, reason, related_lines=None):
        if severity not in SEVERITIES:
            raise ValueError(severity)
        self.report["findings"].append({
            "mode": mode,
            "rule_id": rule_id,
            "severity": severity,
            "line": line,
            "column": column,
            "excerpt": self.clip(excerpt),
            "reason": reason,
            "related_lines": sorted(set(related_lines)) if related_lines else None,
            "requires_context": True,
        })

    def span_finding(self, mode, rule_id, severity, row, start, end, reason, related_lines=None):
        """Finding anchored at ``row.raw[start:end]`` (0-based offsets)."""
        self.finding(mode, rule_id, severity, row.line, start + 1, row.raw[start:end].strip(), reason, related_lines)

    def section(self, name, value):
        self.report[name] = value

    def section_omitted(self, count):
        """Record entries a mode dropped from its own section or findings."""
        self.report["truncation"]["section_omitted"] += count

    def stats(self, mode, values):
        self.report["stats"].setdefault(mode, {}).update(values)


def serialize(report):
    return json.dumps(report, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def finish(report):
    truncation = report["truncation"]
    for key, cap in CAPS.items():
        total = len(report[key])
        report[key] = report[key][:cap]
        truncation["counts"][key] = {"total": total, "returned": len(report[key]), "omitted": total - len(report[key])}
    # Drop deterministic tail entries until the real UTF-8 size fits.
    while len(serialize(report)) >= MAX_OUTPUT - 256:
        key = max(CAPS, key=lambda name: len(report[name]))
        if not report[key]:
            raise RuntimeError("report metadata exceeds output budget")
        report[key].pop()
        count = truncation["counts"][key]
        count["returned"] -= 1
        count["omitted"] += 1
        truncation["output_budget_dropped"] += 1
    truncation["applied"] = bool(
        truncation["excerpt_clipped"] or truncation["term_clipped"] or truncation["section_omitted"]
        or any(c["omitted"] for c in truncation["counts"].values())
    )
    if report["status"] != "error":
        report["status"] = "partial" if report["unverified"] or truncation["applied"] else "ok"
    return report
