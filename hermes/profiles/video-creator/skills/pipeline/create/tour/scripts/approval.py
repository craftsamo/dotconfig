"""Proposal bytes bind consent scope, not the identity of the approving human."""

import json
import re

from tour import digest, local, require


def approved(path, expected):
    proposal = local(path, {".md"})
    require(re.fullmatch(r"proposal-v[1-9][0-9]*\.md", proposal.name), "versioned proposal-vN.md required")
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "approval SHA-256 required")
    require(digest(proposal) == expected, "proposal changed since approval")
    blocks = re.findall(r"```tour\n(.*?)\n```", proposal.read_text(), re.S)
    require(len(blocks) == 1, "proposal needs exactly one tour JSON block")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate proposal key")
            result[key] = value
        return result
    data = json.loads(blocks[0], object_pairs_hook=pairs)
    require(isinstance(data, dict) and set(data) <= {"form", "scope", "acquisition_sha256"} and "form" in data,
            "proposal needs form and optional scope")
    return data


def form_approval(form):
    data = approved(form.get("approved_plan"), form.get("approval_sha256"))
    actual = {k: v for k, v in form.items() if k not in ("approved_plan", "approval_sha256")}
    require(data["form"] == actual, "form differs from approved proposal; propose a new version")
    return data
