# QA contract — guidance

The orchestrating assistant performs a read-only inspection of the
directives in the reply (or at their durable path), measured
against the brief's consumer and decision points.

## Scope
Inspect the guidance as findings-only verification: consumer fit,
directive traceability, checkability. Never rewrite directives or
close open choices yourself.

## Required inputs
The released brief (consumer + what they produce, decision points,
evidence base, directive form, done criteria); the complete
guidance (MUST / SHOULD / open choices / evidence base /
uncertainty); the file at the durable path when named.

## Checks
1. Read the complete guidance. The consumer is named; every
   decision point from the brief is closed by a directive or
   explicitly listed as an open choice — a silently missing
   decision point is a finding.
2. Traceability: every MUST and SHOULD cites scored evidence or a
   named parent result; spot-check the load-bearing traces (URLs
   resolve, the source supports the directive); taste without a
   trace is labeled opinion or absent.
3. Checkability: directives are testable parameters, not
   adjectives — the consumer could verify compliance without
   judgment calls; "make it punchy" is a finding.
4. Fitness: a stranger in the consumer's role could act without
   reading the sources; MUSTs are evidence-strong, SHOULDs carry
   reasoning and confidence, weakly supported directives appear
   under uncertainty, not as MUSTs.
5. Boundary: guidance only — no drafted artifact, no directives
   that overrule a QA contract or a worker's non-waivable floors,
   no evidence base beyond what the brief named (a breadth grab
   went unreported as a spec gap).

## Not verified / never do
An unclosed decision point, an untraced MUST, or guidance missing
from its named durable path means NOT verified — obtain the missing
piece or fail the unit plainly. Do not merge guidance into the
consuming brief yourself before it passes, and never craft the
artifact it guides.
