---
name: qa-data-visualization
description: Read-only QA inspection of an immutable data visualization.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, data-visualization, axes, reproducibility, units]
    category: technic
---
<Scope>
Inspect the actual rendered visualization and its source/parameter record. Use
for audio visualizations and other data-led renders; do not independently decide
whether external facts are true.
</Scope>

<RequiredEvidence>
The immutable artifact and digest, source identity, deterministic derivation
parameters/time range, expected axes/scales/legend/units, and Researcher evidence
for factual interpretation or external data claims.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and remeasure format, dimensions, and declared source/time coverage;
   reconcile parameters with the observed output rather than trusting a report.
2. Check axes, scales, ticks, legends, units, labels, panel correspondence,
   blank regions, clipping, contrast, and whether normalization or truncation
   could mislead.
3. Spot-check source values against rendered positions/labels using the supplied
   deterministic derivation and Researcher evidence; record exact fields/regions.
4. Return evidence and findings to `qa-pipeline` for its verdict rollup.
</ChecksProcedure>

<FailOrCantVerify>
Unknown source/parameters, missing required Researcher evidence, unavailable
render, or irreconcilable source-to-render mapping is `can't_verify`. Do not
change scales, labels, data, parameters, re-render, or publish.
</FailOrCantVerify>
