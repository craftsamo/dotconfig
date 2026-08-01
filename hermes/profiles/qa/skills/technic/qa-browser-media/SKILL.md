---
name: qa-browser-media
description: Read-only QA inspection of a runnable browser media candidate.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, browser, html, interaction, deterministic]
    category: technic
---
<Scope>
Load and inspect the real immutable browser source at the target viewport. Use
for HTML motion and p5.js experiences; an exported video additionally composes
the `qa-video` contract.
</Scope>

<RequiredEvidence>
The immutable source/assets and digest, target viewport and resize behavior,
required interactions/states, deterministic seed/timeline, console/performance
thresholds when briefed, and expected export contract. Researcher evidence is
required for external factual claims.
</RequiredEvidence>

<ChecksProcedure>
1. Run the actual source at every declared viewport and record load behavior,
   asset/font resolution, console errors, network failures, and initial state.
2. Exercise each required interaction, resize path, state, seed/timeline, and
   animation extreme; capture evidence without modifying source or state files.
3. Measure the briefed performance threshold and inspect layout, clipping,
   safe areas, deterministic repeatability, and required browser compatibility.
4. If an export exists, hand its temporal inspection to `qa-video`; return this
   source/state evidence and findings to `qa-pipeline`.
</ChecksProcedure>

<FailOrCantVerify>
Source/assets cannot load, required state or viewport cannot be exercised,
determinism/performance cannot be measured, or Researcher evidence is missing
for a gating claim: `can't_verify`. Never edit source, dependencies, assets,
seed, timeline, or export; never publish.
</FailOrCantVerify>
