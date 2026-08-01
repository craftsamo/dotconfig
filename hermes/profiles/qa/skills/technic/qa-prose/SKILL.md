---
name: qa-prose
description: Read-only QA inspection of an immutable prose deliverable.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [qa, technic, prose, copywriting, documentation, humanizer]
    category: technic
---
<Scope>
Inspect the complete attached Writer text as findings-only critique. Route by
type (marketing, technical prose/article, or documentation), and load applicable
Japanese notation/tech-prose/rhythm norms and `humanizer` when the text is
Japanese or the Writer contract requires them. Never rewrite paragraphs.
</Scope>

<RequiredEvidence>
The immutable complete text and digest, deliverable type, audience, purpose,
medium, tone, length budget, constraints, and Researcher evidence for every
external fact, quote, number, or URL claim.
</RequiredEvidence>

<ChecksProcedure>
1. Hash and read the complete attachment. Check the type structure: marketing
   hook/value/proof/CTA; technical claim/argument/close; documentation scannable
   task order and headings.
2. Check audience, purpose, tone/register, length, terminology, Japanese norms
   when applicable, and AI-pattern prose using the loaded norms and humanizer
   contracts; report location and the named pass for each finding.
3. Trace factual assertions, quotes, numbers, and URLs to supplied brief or
   Researcher evidence. Treat unsupported or refuted claims as pipeline findings.
4. Return findings only to `qa-pipeline`'s verdict rollup; provide no replacement
   paragraphs or independent verdict vocabulary.
</ChecksProcedure>

<FailOrCantVerify>
Truncated/incomplete text, missing type brief, unavailable norms needed for a
gating Japanese review, or missing Researcher evidence is `can't_verify`. Do not
rewrite, line-edit, fact-research, restructure, or publish the prose.
</FailOrCantVerify>
