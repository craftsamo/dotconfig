# Research capability — plan / execute / qa

Load when the work needs external information: retrieval (facts, links,
enumerations, source hunts) or depth (analysis, synthesis, comparison,
verification). Two specialists share this capability:

| Need | Route |
| --- | --- |
| A quick fact/link, one source, ~a minute | inline — answer it yourself |
| Several parallel lookups for a waiting user | inline — `delegate_task` (max 3, anonymous, stateless) |
| Durable retrieval: enumerations/surveys with a coverage claim, exhaustive multi-hop hunts | **searcher** session (or kanban card for fire-and-forget hunts) |
| Depth: analysis, synthesis, tradeoffs, evaluation, claim verification, evidence-backed guidance | **researcher** session |

Searcher's deliverable is the facts with sources; researcher's is a
verified conclusion. A crafted artifact (台本, copy, media) built on that
conclusion is writer/creator work consuming it.

## Plan

- Fix the question before the session: what decision does this research
  serve, and what does "answered" look like (the done criteria)? For
  enumerations give a floor count and per-item fields ("≥15 candidates,
  each with pricing URL and date"). For comparisons name the axes.
- Uncertain scope → open the researcher session with the open question and
  let its first reply size the work before you promise depth to the user.

## Execute

Start the session with the SessionBrief; the pipeline routes internally by
deliverable (evidence-pack / tradeoff-matrix / fact-check / guidance for
researcher; lookup / survey / hunt for searcher) — write what you want,
not how.

- Follow-ups sharpen scope in place: "その3件を深掘り", "2024年以前は除外".
  The session keeps its source trail, so refinement is cheap.
- An exhaustive hunt that should grind unattended is the classic kanban
  case: `assignee: searcher`, `skills: ["searcher-pipeline"]`,
  `goal_mode: true` (+ `goal_max_turns`) — fire, forget, read the
  completion.
- Research feeding another specialist: wait for the turn, QA it, then
  paste the conclusions (not a pointer) into the consuming session's
  brief.

## QA

- Sources exist and support the claims — spot-check the load-bearing ones
  (links resolve, quotes match, dates/versions right).
- Coverage claims match the ask (floor counts met; exclusions honored).
- Conclusions distinguish evidence from inference; uncertainty is stated,
  not smoothed over.
- Defects (dead links, thin coverage, unsupported leaps) go back as a
  feedback turn.

## Pitfalls

- Sending a 30-second lookup to a session or the board.
- Deep multi-hop research inline — it floods your own context; that is
  exactly what the specialists are for.
- Briefs that ask "research X" with no decision context or done criteria.
- Forwarding conclusions whose load-bearing sources you never opened.
