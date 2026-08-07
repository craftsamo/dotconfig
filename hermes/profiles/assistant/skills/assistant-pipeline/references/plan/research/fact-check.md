# Fact-check — decision surface

Verification: a fixed list of external claims, cited sources, or
current specifications, each returned with a verdict (supported /
refuted / partly true / unverifiable), sources, and counterevidence.
The researcher owns origin tracing, corroboration, and verdict
craft; you own which claims are checked and what settles a verdict.

Researcher unit `fact-check` · QA `fact-check` · units: one fixed
claims list per unit; card-eligible as `claim-verification` once
every decision below is settled — the only research card
(`../../execute/research/index.md`).

## Fix before release

- **The claims list** — fixed and itemized. Each claim verbatim
  when it comes from a text or artifact; "check this article" is
  not a list — either extract the claims here, or name the artifact
  and scope extraction as the unit's first step ("the factual
  claims in the final voiceover, verbatim").
- **Source requirements** — what settles a verdict: a primary
  source directly, or ≥2 independent A/B sources; per-claim when
  stakes differ ("the pricing claims need the vendor page as of
  this month").
- **Freshness** — the as-of date verdicts must hold for;
  specifications and prices drift.
- **Consumer** — who reads the verdicts: your QA pass consuming a
  ledger, the user, or a downstream worker; a QA consumer makes the
  ledger file mandatory.
- **Durable path + ledger filename** — where the complete verdict
  ledger lands (default `claim-ledger.md`) when a consumer needs
  it; the reply carries the verdicts.
- **Scope** — verdicts on the listed claims only; topic context
  beyond them is a separate evidence-pack unit.

## Defaults

- Claims are preserved byte-for-byte with a separate neutral
  restatement; compound claims are split and the split is noted.
- Verdict strength tracks corroboration — a single B-source yes is
  "probably true", not "supported".
- `unverifiable` states what was searched and where the answer
  might live — never a bare shrug.

## Red flags

- The claims list is still moving ("also check whatever else looks
  off") — spec-gap finding; a card with a moving list is malformed,
  and a session brief needs the list fixed first.
- The unit wants artifact-quality judgment ("is the video's claim
  section well made?") — artifact-vs-brief verdicts are your own
  QA's; the researcher only transcribes and verifies the claims.
- Verification hiding a survey ("check whether competitors do
  this") — the population is a search sweep; verdicts apply to the
  QA-passed findings.
- No source requirements — "verify" without what counts as settled
  produces confident-sounding guesses.
