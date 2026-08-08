# Evidence-pack — decision surface

Deep synthesis: one open question answered with verified evidence —
landscape analysis, "what do we actually know about X", the default
depth unit. The researcher owns gathering strategy, trust scoring,
corroboration, and counterevidence mechanics; you own what question
is being answered and what "answered" means.

Researcher unit `evidence-pack` · QA `evidence-pack` · units: one
question per unit; never card-eligible — synthesis whose framing may
move with the user stays resident on purpose.

## Fix before release

- **The question** — one line, settled; sub-questions itemized when
  the user has them. "Research X" or "look into X" is not a
  question — a spec-gap finding, not a draft synthesis.
- **Decision context** — what the caller will decide or do with the
  answer; it sizes depth and settles which sub-questions are
  load-bearing.
- **Done criteria** — which sub-questions must close, and what an
  honest "we don't know" looks like for the rest.
- **Source policy** — freshness window, reliability floor for
  load-bearing claims, required source classes (primary docs,
  papers, filings) when the domain demands them.
- **Effort bound** — stakes-sized: a planning input is hours, not
  an exhaustive survey; say which.
- **Inputs** — QA-passed search parts and prior results pasted into
  the brief; breadth gaps found mid-unit come back as a search
  request, not researcher grinding.
- **Durable path** — long reports and source tables land in a file;
  the conclusion and key findings live in the reply.

## Defaults

- Output keeps the categories: Summary / Sources / Observations /
  Corroboration / Uncertainty / Implications — with per-claim
  confidence; the conclusion leads, the evidence follows.
- Single-source claims are marked single-source; counterevidence is
  searched, not just confirmation.
- The researcher informs the caller's decision without taking it
  over — implications, not directives (directives are a guidance
  unit).

## Red flags

- The question wants a list ("all providers that…") — that is a
  search sweep; release it to the searcher first and feed the
  QA-passed table in as a part.
- The question wants a winner between named options — a
  tradeoff-matrix unit, not a pack.
- Specific claims to verify are hiding in the brief — split them
  into a fact-check unit; verdicts have their own contract.
- Several questions under one umbrella ("X, and also how it affects
  Y and Z") — granularity finding; one question per unit.
