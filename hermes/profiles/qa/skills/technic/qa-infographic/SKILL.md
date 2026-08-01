---
name: qa-infographic
description: Read-only QA inspection of an immutable information infographic.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, infographic, information-design, data-fidelity]
    category: technic
---

<Scope>
Inspect the delivered infographic and its actual rendered candidate, not the
Creator summary or a different preview. Verify information hierarchy, exact
labels, values, legends, and destination readability.
</Scope>

<RequiredEvidence>
The immutable artifact and digest, approved content/data ledger, destination
dimensions and legibility size, layout/style brief, and predeclared Researcher
evidence mapping sources to factual claims and numbers.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and remeasure the actual file, then read every label, number, unit,
   legend, heading, and annotation back against the approved ledger.
2. Trace each visual encoding (position, length, color, scale, icon) to its
   source field using the supplied Researcher mapping; check hierarchy and
   reading order without independently validating world facts.
3. Inspect native, destination, and small-size renders for clipping, overlap,
   contrast, misleading emphasis/normalization, and legibility of dense text.
4. Return location-specific evidence and findings to `qa-pipeline`'s rollup.
</ChecksProcedure>

<FailOrCantVerify>
Missing or unreadable source mapping, Researcher evidence for a gating factual
claim, exact readback, or required destination render is `can't_verify` for the
pipeline. Do not correct values, redesign hierarchy, re-export, or publish.
</FailOrCantVerify>
