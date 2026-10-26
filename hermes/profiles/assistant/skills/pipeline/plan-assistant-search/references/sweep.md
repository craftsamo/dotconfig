# Sweep — decision surface

An enumeration or survey: "collect / enumerate / survey as many as
possible" — candidates, examples, instances — or a quantified
observation of public web state. The searcher owns the coverage
matrix, dedup, and saturation mechanics; its Plan proposes population, coverage
and fields for Client agreement against your purpose and consumer.

Searcher unit `sweep` · QA `sweep` · units: one enumeration per
unit, run as a resident session.

## Agree before Build

These are proposal choices, not required inputs for a purpose-first Plan.
The caller may author them fully; otherwise Searcher proposes them for Client
agreement. Follow the parent entry's agreement and preliminary Build gates;
retain same-role unit boundaries.

- **The population** — one line naming what counts as a member and
  what plainly does not; the boundary cases decide the dedup
  identity ("self-hosted CI runners" — managed services in or
  out?).
- **Coverage claim & floor** — the explicit floor count and the
  claim the result must be measurable against ("≥15 candidates" /
  "all providers with a published ja pricing page").
- **Per-item fields** — fixed by the consumer's needs: each item's
  required fields, each with source URL and date ("name, pricing
  URL, free-tier limit, as-of date").
- **Scope exclusions** — regions, dates, license classes,
  already-known items not to re-enumerate.
- **Freshness window** — how old a source may be before the item is
  flagged or excluded.
- **Durable path** — enumeration tables land in a file; the reply
  carries the coverage statement.

## Defaults

- Every item carries source URL + date even when unnamed in the
  per-item fields — undated enumerations cannot be QA'd.
- Stop at floor + saturation: once the floor is met and new cells
  stop producing members, the sweep ends with an honest coverage
  statement — exhaustiveness beyond the claim is a hunt, not a
  bigger sweep.
- Unknown population size → ground with a lookup unit first
  (`../SKILL.md` Grounding) rather than guessing a floor.

## Red flags

- No floor count or measurable claim: specialist Plan proposes coverage from
  purpose; Build release without settled coverage is a spec-gap finding.
- Per-item fields undecided: specialist Plan proposes them from consumer needs;
  agree before Build rather than retrieve a table that must be rebuilt.
- The sweep wants the items ranked, scored, or recommended —
  selection is a researcher unit consuming the sweep as a part.
- A coverage claim spanning several populations ("all CI tools and
  their plugins and their pricing history") — granularity finding;
  one population per unit.
