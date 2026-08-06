# QA contract — browser media

The orchestrating assistant performs a read-only inspection of the runnable browser media candidate at its durable path.

## Scope
Load and inspect the real browser source at the target viewport. Use for HTML
motion and p5.js experiences; an exported video additionally composes the
`qa-video` contract.

## Required inputs
The browser source and assets at their durable paths, target viewport and resize
behavior, required interactions/states, deterministic seed/timeline,
console/performance thresholds when briefed, and expected export contract.
Research evidence supplied in the flow is required for external factual claims.

## Checks
1. Run the actual source at every declared viewport and record load behavior,
   asset/font resolution, console errors, network failures, and initial state.
2. Exercise each required interaction, resize path, state, seed/timeline, and
   animation extreme; capture evidence without modifying source or state files.
3. Measure the briefed performance threshold and inspect layout, clipping, safe
   areas, deterministic repeatability, and required browser compatibility.
4. If an export exists, hand its temporal inspection to `qa-video`; record this
   source/state evidence and findings in the verdict/feedback.

## Not verified / never do
Source/assets cannot load, required state or viewport cannot be exercised,
determinism/performance cannot be measured, or research evidence supplied in the
flow is missing for a gating claim means NOT verified — obtain the missing input
or state plainly it cannot be checked. Never edit source, dependencies, assets,
seed, timeline, or export; never publish.
