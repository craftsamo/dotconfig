# Explanation

Identify the question the reader needs answered and the concepts needed to
follow the answer. Introduce an unfamiliar term before depending on it;
do not define terms that the brief establishes as familiar.

Connect the explanation to a concrete supplied or clearly hypothetical
example. A hypothetical case illustrates a mechanism, not an observed
result. Choose cause-to-effect, example-to-principle or another progression
that fits the topic; no fixed paragraph count or mandatory conclusion-first form.

QA: can the reader follow each dependency, and does the final explanation
answer the opening question without a new unsupported claim?

## Build the Explanation

If the reader lacks the concept, begin with their question, explain the
mechanism through a concrete case, then name its limits. Give the function
before the term; defining one unknown through two more unknowns only moves
the obstacle. For an expert reader, spend that space on the unfamiliar edge.
Use prose for cause and effect, not a list that leaves the relationship implicit.

Locally authored example (hypothetical, not a measured system):
Question: "Why can a second request be quicker?"
Explanation: "The service keeps a copy of the first response and can reuse it
for a matching request. This stored copy is a cache. Reuse avoids repeating
the calculation, but the copy may be out of date."
Reason: the reader meets an action and its consequence before the label;
the limitation prevents "cached" from becoming a promise of fresh results.
Do not replace this with "Caching uses memoization for low-latency retrieval"
unless the brief establishes those terms as shared knowledge.

Retain: a short definition already sufficient for the reader, or a parallel
list of independent cache policies. Neither needs expansion into a story.
Give the decisive mechanism more space than familiar background, without
forcing equal-length sections or a prescribed sequence of headings.

QA evidence: trace the opening question to its answer, quote the mechanism
and its limiting condition, and identify the example as supplied or hypothetical.
Read headings and paragraph openings for missing dependencies, then check
the full paragraphs; a smooth outline alone does not establish causality.

Local adaptation of [natural-japanese v1.5.0 writing constitution](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/writing-constitution.md)
(function before terminology, causal prose) and [readability principles](https://github.com/coji/natural-japanese/blob/v1.5.0/skills/natural-japanese/references/readability-principles.md)
(reader knowledge and paragraph focus); the example and sequence are local choices.
