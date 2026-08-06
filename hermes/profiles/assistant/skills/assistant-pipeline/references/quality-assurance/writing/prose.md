# QA contract — prose

The orchestrating assistant performs a read-only inspection of the prose deliverable at its durable path.

## Scope
Inspect the complete Writer text as findings-only critique. Route by type
(marketing, technical prose/article, or documentation), and load applicable
Japanese notation/tech-prose/rhythm norms and `humanizer` when the text is
Japanese or the Writer contract requires them. Never rewrite paragraphs.

## Required inputs
The complete text at its durable path, deliverable type, audience, purpose,
medium, tone, length budget, constraints, and research evidence supplied in the
flow for every external fact, quote, number, or URL claim.

## Checks
1. Read the complete artifact file at its durable path. Check the type structure:
   marketing hook/value/proof/CTA; technical claim/argument/close; documentation
   scannable task order and headings.
2. Check audience, purpose, tone/register, length, terminology, Japanese norms
   when applicable, and AI-pattern prose using the loaded norms and humanizer
   contracts; report location and the named pass for each finding.
3. Trace factual assertions, quotes, numbers, and URLs to supplied brief or
   research evidence supplied in the flow. Treat unsupported or refuted claims as
   verdict/feedback findings.
4. Record findings only in the verdict/feedback; provide no replacement
   paragraphs or independent verdict vocabulary.

## Not verified / never do
Truncated/incomplete text, missing type brief, unavailable norms needed for a
gating Japanese review, or missing research evidence supplied in the flow means
NOT verified — obtain the missing input or state plainly it cannot be checked. Do
not rewrite, line-edit, fact-research, restructure, or publish the prose.
