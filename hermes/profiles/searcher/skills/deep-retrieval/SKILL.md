---
name: deep-retrieval
description: DEPRECATED compatibility stub — deep multi-hop retrieval now lives in searcher-pipeline's Hunt mode (references/hunt.md). Old dispatches pinning skills:["deep-retrieval"] land here harmlessly; new dispatches pin skills:["searcher-pipeline"] and signal exhaustive hunts with goal_mode:true instead.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [search, retrieval, deep-dive, deprecated]
    category: research
    related_skills: [searcher-pipeline]
---

This skill is a **deprecated stub** kept only so that older dispatches pinning
`skills: ["deep-retrieval"]` keep working.

Do this instead:

1. Load `searcher-pipeline` (`skill_view`) if it is not already in context.
2. Load its Hunt mode reference: `skill_view` with
   `name=searcher-pipeline`, `file_path=references/hunt.md`.
3. Follow Hunt — hop loop, coverage ledger, saturation stop, source-map
   hand-off — under the kernel's floors (link integrity, retrieval-not-
   synthesis).

Dispatchers: pin `skills: ["searcher-pipeline"]` on every searcher card and
use `goal_mode: true` (+ `goal_max_turns`) to signal an exhaustive hunt; do
not pin this stub.
