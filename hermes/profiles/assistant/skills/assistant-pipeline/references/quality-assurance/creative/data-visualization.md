# QA contract — data visualization

The orchestrating assistant performs a read-only inspection of the data visualization artifact at its durable path.

## Scope
Inspect the actual rendered visualization and its source/parameter record. Use
for audio visualizations and other data-led renders; do not independently decide
whether external facts are true.

## Required inputs
The visualization artifact file at its durable path, source identity,
deterministic derivation parameters/time range, expected axes/scales/legend/units,
and research evidence supplied in the flow for factual interpretation or external
data claims.

## Checks
1. Remeasure format, dimensions, and declared source/time coverage; reconcile
   parameters with the observed output rather than trusting a report.
2. Check axes, scales, ticks, legends, units, labels, panel correspondence,
   blank regions, clipping, contrast, and whether normalization or truncation
   could mislead.
3. Spot-check source values against rendered positions/labels using the supplied
   deterministic derivation and research evidence supplied in the flow; record
   exact fields/regions.
4. Record evidence and findings in the verdict/feedback.

## Not verified / never do
Unknown source/parameters, missing required research evidence supplied in the
flow, unavailable render, or irreconcilable source-to-render mapping means NOT
verified — obtain the missing input or state plainly it cannot be checked. Do not
change scales, labels, data, parameters, re-render, or publish.
