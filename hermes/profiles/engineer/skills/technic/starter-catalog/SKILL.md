---
name: starter-catalog
description: Investigate real starter/boilerplate candidates and lineage for Engineer planning or feasibility. Recommend a fit for the Client to approve; never create repositories or run scaffolders from this observation skill.
version: 3.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: technic
    tags: [bootstrap, starter, discovery]
---

<Goal>

Investigate and recommend, rather than requiring Assistant to preselect the
technical foundation. Client approves important starter/history/platform choices.
Repository creation/registry stays with the Client's separately authorized flow;
OpenCode implements the skeleton in an established task worktree.

</Goal>

<Discovery>

Discover actual repositories through ghq and gh repo list/view, then read the
plausible candidates' README, project instructions, maintenance history and
remotes. Never enumerate all private content or invent a known starter from a
name alone. This is conventions plus recipes, not a fixed inventory.

Family convention: `<name>-starter`, platform `<root>-with-<platform>`, variant
`<root>-with-<platform>-<variant>`. A derivative may name its parent as upstream;
verify the actual remote rather than assuming the relationship from the name.
Report unexpected lineage rather than rewiring it silently.

Prefer a maintained near-fit, but compare starting from scratch when a starter
adds unsuitable complexity. Present 2-3 actual candidates when useful, with fit,
lineage, constraints, freshness and a recommendation. Do not force a shortlist
when the Client already selected a suitable existing project.

</Discovery>

<Report>

Return observations, evidence and the technical recommendation to the pipeline's
Plan or Assess mode. History-preserving clone vs template instantiation, owner,
visibility, hosting cost and repo creation remain explicit decisions. No repo,
remote, scaffolding, initial commit or deployment is performed by this Skill.
Concrete private names belong in task context/private records, not this file.

</Report>
