# Plan a Fact Check

Use for specific external claims, cited sources or current specifications.
The output is claim-level verdicts, never a survey or an artifact-quality gate.

## Plan

1. Identify the claims from supplied text or an artifact inspected only for
   its factual claims and context. Preserve each source claim byte-for-byte in
   a verbatim code span/block, including punctuation and Unicode. Do not normalize
   apostrophes, quotes, dashes, spacing, numbers or capitalization.
2. Propose individually checkable subclaims for compound sentences, retaining
   the exact original plus a separate neutral investigation restatement and
   mapping. Agree the fixed claims list and source requirements before Build;
   an unavailable or moving list is a spec gap, not license to check a vibe.
3. Define recency/context, source coverage, exclusions, budget and closure:
   every input claim receives a confidence-rated `supported`, `refuted`,
   `partly true` or `unverifiable` verdict, evidence, counterevidence and gaps.
   Research stops at a stable verdict, not an exhaustive topic survey.
4. Name the consumer and output. If downstream QA consumes the results, settle
   the durable path and requested filename (default `claim-ledger.md`) for the
   complete verdict ledger, not just a one-line conclusion. Missing durable
   destination is a blocking input for that required delivery, never a guessed path.

State explicitly that extracting claims from text/image/video/audio does not
authorize judging craft, rendering, mechanical specifications, completeness or
fit to the brief. If the claims list sprouts a topic survey, report the
granularity issue and propose a separate evidence-pack unit for agreement.
No external verification occurs in Plan without an approved preliminary Build.
