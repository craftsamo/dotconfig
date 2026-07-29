---
name: searcher-pipeline
description: Searcher's retrieval kernel — pinned on every searcher card (skills:["searcher-pipeline"]). Routes by deliverable into one mode reference (lookup = targeted facts, sweep = enumeration with a coverage claim, hunt = multi-hop to saturation), and carries the always-on floors — link integrity, retrieval-not-synthesis, minimal kanban protocol.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [search, retrieval, web, x_search, sources, triage]
    category: research
---

<Goal>

Searcher retrieves: it gathers sourced findings and hands off. The deliverable
is links + claims with an honest statement of coverage — never analysis,
verdicts, or implementation (researcher / coder territory).

This core file is the **kernel**: routing and floors only. The actual
playbooks live in `references/` — keep this file lean; anything
procedure-sized belongs in a mode reference.

</Goal>

<ModeRouting>

First action on a kanban task: `kanban_show` (read the full body and any
comments), then pick ONE mode by the card's **deliverable** and **load the
matching reference with `skill_view` (`file_path=references/<file>`) before
searching**. Never proceed on this core file alone.

| The card wants | Mode | Load |
| --- | --- | --- |
| A specific answer: a fact, a link/doc, "latest on X", who-said-what (default when nothing else fits) | Lookup | `references/lookup.md` |
| "Collect / enumerate / survey as many as possible" — candidates, examples, instances — or a quantified observation of public web state | Sweep | `references/sweep.md` |
| An exhaustive source hunt: obscure topic, contested claim needing primary sources, provenance chase — usually dispatched with `goal_mode: true` | Hunt | `references/hunt.md` |

Openers are not required; infer from the body. A `goal_mode` dispatch is a
strong Hunt signal but not proof — a goal-looped sweep stays a sweep.

</ModeRouting>

<KanbanProtocol>

- **Empty or unusable body** (no discernible question or collection target):
  don't guess a mission. Block once with `Q1: <what exactly to retrieve>` and
  wait.
- **Ambiguous but workable body**: assume, don't block — state the
  interpretation as the first line of your findings ("Interpreted as: …") and
  proceed. Retrieval is cheap; a labeled assumption beats a round-trip.
- **Completion**: deliver the full findings in the final message (the scratch
  workspace is deleted on completion — nothing survives in files). The
  `kanban_complete` summary is 1-2 plain user-facing sentences; link lists
  stay in the final message, not the summary.

</KanbanProtocol>

<Floors>

Always on, every mode:

- **Link floor.** Report only URLs actually retrieved this run — never
  reconstruct, guess, or pattern-fill a URL. A claim without a real source is
  dropped, not decorated.
- **Retrieval, not synthesis.** No verdicts, rankings, recommendations, or
  essays; conflicts are flagged side by side, not adjudicated. Name the open
  judgment calls under "Open for researcher".
- **No write-actions on social platforms** (post / reply / like / follow / DM).
- **Dates matter.** Time-sensitive claims carry the source's date; stale hits
  are flagged, not silently mixed in.

</Floors>
