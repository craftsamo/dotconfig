---
name: debug-validation-contract
description: >-
  Use when a validator, schema or parser rejects input that the product contract
  intentionally permits, especially when exact bytes, hashes, approvals or
  immutable artifacts must survive the fix (バリデーションが正当な入力を拒否する,
  契約上有効な入力が弾かれる, 制御文字, ハッシュ不一致, "validator rejects valid
  input", "schema rejects", "control characters", "exact bytes must be
  preserved"). Produces an evidence-backed causal chain and the smallest
  semantics-preserving fix direction; never repairs the input to pass validation.
license: MIT
---

<Goal>

Diagnose failures where a generic validator rejects input that the product
contract intentionally permits, especially when exact bytes, hashes, approvals,
or immutable artifacts must survive the fix.

Produce an evidence-backed causal chain, a bounded blast-radius analysis, and
the smallest semantics-preserving code/test direction. Do not "repair" the
input to make validation pass.

</Goal>

<Procedure>

1. **Freeze the contract before debugging.** Read the governing schema and the
   actual rejected artifact. If approval or integrity uses a digest, compute it
   before any probe and compare it with the recorded digest. Treat input
   rewriting, newline replacement, and reserialization as behavior changes.

2. **Reproduce at the narrowest permitted seam.** Prefer the pure validator or
   model function over the full side-effecting pipeline. If the brief forbids
   rerunning the entry point, use its saved exact output and invoke only a
   read-only validation seam; state that the full pipeline was not rerun.

3. **Trace the executing path, not similarly named prose.** Follow the entry
   point through imports to the exact predicate that raises. Name each link as
   `file:line -> function -> value -> predicate`. Explain why the input satisfies
   the predicate numerically or structurally; a location without mechanism is
   not a diagnosis.

4. **Map every caller before changing a shared helper.** Use content search for
   both imports and symbol calls, then classify each field by schema role:
   visible text, path, identifier, selector, URL, command argument, metadata, or
   evidence prose. A shared default may protect stricter consumers that never
   appear in the failing path.

5. **Establish the test baseline and the missing assertion.** Run the nearest
   existing suite unchanged, inspect tests for the validator symbol and error
   text, and report whether the suite is green because the edge case is absent.
   A green broad suite is not evidence that the contract is correct.

6. **Choose the narrowest semantic exception.** Prefer a default-off keyword
   on the shared helper plus explicit opt-in at contract-valid fields. Keep the
   return value and length accounting unchanged. Use a local validator only
   when changing the shared helper would create a public-API or ownership
   boundary; do not duplicate validation merely to avoid tracing callers.

7. **Decide normalization from the integrity boundary.** If exact bytes are
   approved before parsing, reject uncontracted alternate encodings rather than
   normalizing them after approval. Canonicalization is safe only when the
   contract explicitly defines it before hashing. See
   `references/text-control-characters.md` for the line-ending decision table.

8. **Specify focused regression tests before implementation.** Cover:
   - the newly valid value through the real schema call site;
   - exact value preservation through serialize/reload or freeze-to-temp;
   - NUL and unsafe controls still rejected on the opted-in path;
   - the shared default still rejects the exception for non-opted consumers;
   - equality/hash/approval checks still detect changed content.

9. **Check collision risk twice.** Inspect the relevant-path diff before the
   diagnosis and again before reporting. Distinguish direct path collision from
   a dirty shared worktree; recommend an isolated worktree or exact-path staging
   when unrelated work is active.

10. **Verify in widening rings after implementation.** Run the focused
    regression, the helper's direct consumers, then the repository-prescribed
    suite. Report actual counts and warnings; do not substitute a later full
    pipeline run when that run remains separately authorized.

</Procedure>

<ReportShape>

Lead with whether the cause is settled and whether the fix is one bounded unit.
Then report, in order:

1. immutable input/hash evidence and reproduction constraint;
2. numbered causal chain with exact paths and lines;
3. directly affected fields and unchanged shared-helper consumers;
4. minimal code direction and normalization decision;
5. focused tests and exact verification commands;
6. direct collision risk versus dirty-worktree risk;
7. residual work that the validator fix does not establish.

</ReportShape>

<Pitfalls>

- **Do not widen a helper before searching every import and call site** — path,
  selector, URL, and command fields may rely on the old strict default.
- **Do not normalize approved content after verifying its hash** — the frozen
  value can diverge from the bytes the approver accepted.
- **Do not test only that the error disappears** — pin exact preservation and
  the unsafe controls that must remain red.
- **Do not rerun a side-effecting pipeline when the brief permits only read-only
  diagnosis** — invoke the pure validation seam or rely on retained exact output.
- **Do not call a green suite proof of correctness when it lacks the failing
  input** — state the coverage gap and add the missing regression first.
- **Do not equate "no relevant file diff" with a clean worktree** — unrelated
  active changes still create staging and commit-contamination risk.

</Pitfalls>

<Verification>

- The report identifies the exact predicate and explains mechanically why the
  valid input triggers it.
- Every shared caller is classified before a signature/default change is
  recommended.
- The fix direction preserves input bytes and keeps strict behavior default-on.
- Tests cover valid exception, invalid controls, unchanged default, and
  integrity/equality behavior.
- No forbidden input, approved artifact, or side-effecting output was modified
  during diagnosis.

</Verification>
