# Quality engine — review passes (self-review and critique)

One playbook, two callers:

- **Write mode, "Self-review" step** — run the passes on your own draft,
  fix, re-check.
- **Assess mode, critique branch** — run the same passes on someone else's
  text and report findings instead of fixing.

The passes are the writer's quality floor and are **non-waivable**: no
deadline, brevity, or instruction — including the assistant's — skips
one. Never skip a pass because the text is short; short copy fails the
integrity pass as easily as a long article.

## Passes (run in this order)

1. **Structure pass** — does the text honor its type contract?
   - Prose types: the structure rules in `references/prose.md`
     (hook→value→proof→CTA / one-topic paragraphs / scannable sections).
   - Script type: the unit-integrity rules in `references/script.md`
     (continuous numbering, complete per-unit fields, verbatim text
     isolated from instructions, budgets respected).
2. **Norms pass** — the layered japanese-* checklists the kernel's
   TypeTable assigned to this deliverable (notation always for Japanese
   text; argumentation and rhythm only where the table says so). Load each
   assigned layer via `skill_view` if not already loaded.
3. **Humanizer pass** — load `humanizer`; strip AI-writing patterns:
   hollow intensifiers, symmetric filler, list-shaped prose, em-dash
   crutches, theatrical closers.
4. **Integrity pass** — every fact, quote, number, and URL traces to the
   brief or a retrieved source; assumptions are labeled; nothing invented.
   For scripts, also verify production constraints from the brief (unit
   counts, durations, character caps) are actually met, not approximated.

## Self-review usage (Write mode)

- Run all four passes on the complete draft — not per-section as you go.
- Fix everything a pass catches, then re-run the failed pass on the
  changed text once. One fix round is the norm; a draft still failing
  after two rounds signals a structure problem — go back to the outline,
  don't polish sentences.
- What each pass changed does not go in the final message; only surviving
  assumptions and open gaps do (kernel delivery rules).

## Critique usage (Assess mode)

- **Findings, not rewrites.** Never deliver a corrected full text; the
  requester owns the edit.
- Each finding: location (section/line/unit), the pass that caught it,
  severity, and a concrete fix in one sentence (a one-line rewrite sample
  is fine; a rewritten paragraph is not).
- Severity scale:
  - `blocker` — factual error, invented source, contract violation
    (missing unit, instruction text leaking into verbatim dialogue).
  - `should-fix` — norms violations that damage credibility or reading
    flow (notation inconsistency, unsupported assertion, AI-pattern
    prose).
  - `polish` — improvements a deadline could skip.
- End with one verdict line: `ship as-is` / `fix blockers` /
  `restructure` — plus the single highest-leverage fix.

## Pitfalls

- Running the humanizer pass first — it hides structure problems under
  smoother sentences. Order matters.
- Letting the norms pass drift into taste: cite the specific checklist
  item (skill + rule) for every norms finding.
- In critique, "rewriting to show" — one sample line is illustration;
  two is a rewrite.
