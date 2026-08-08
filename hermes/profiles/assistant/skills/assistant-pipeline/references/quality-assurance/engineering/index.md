# Engineering QA — the per-unit gate

The gate between units: unit N passes here before unit N+1 is
released (`../../execute/engineering/index.md`). Verification is
two-layer — the engineer's own loop already verifies each unit
inside OpenCode (repo checks + review agent); your gate is
**outcome-level and evidence-based**. Do not re-review diffs line by
line in chat. The common floor in `../index.md` applies; the
artifact here is the worktree + report, not a file in
`.deliverables/`.

## Gate procedure — every unit report

1. **Evidence check** — the report must name what landed
   (commits/branch/PR), the verification commands with their actual
   output, and the session ids. Anything missing means the unit is
   NOT gateable — ask for the evidence in a turn on the SAME unit;
   never gate on a summary.
2. **Spot-check** — re-run one named check read-only in the repo
   (`cd <repo> && <named command>`) or read the named log. Claimed
   output is not verified output.
3. **Scope check** — `git -C <repo> status` + `log --oneline`
   against the Authority's `scope:` / `do not touch:` boundaries;
   an out-of-scope change is a defect even when it works.
4. **Inspect the deliverable** — per `inspection.md`, keyed to the
   plan leaf's verification default. For UI work a rendered
   screenshot exists — code-only inspection is not verification.
5. **Verdict** — pass → close out per
   `../../execute/engineering/github-ops.md` (merge / purpose /
   epic acceptance: `acceptance.md`), then release the next unit.
   Fail → itemized course correction to the SAME session on the
   SAME unit.

## What the unit is judged against

| Unit | Standard |
| --- | --- |
| Purpose | the Issue body — its spec and done criteria; PR state matches the Authority (`A1` commit-only, `A2` branch + PR/stack) |
| Wave | the Wave's line in the base plan session + the plan's done criteria |
| Small job | the whole brief |

## Deep review — escalation, not default

Triggers: changes near `do not touch:` boundaries, dependency or
lockfile changes (`A3` work), security-sensitive surfaces (auth,
secrets, payments, data migrations), or a second failure on the
same unit. Then run a **fresh read-only OpenCode review run** in
the repo and take only the verdict:

```bash
cd <repo> && opencode run --auto --agent plan --title "review: <unit>" \
  'Review <range/PR> against <concern>. Findings only:
   file:line, severity, why. Do not edit anything.'
```

Never page whole diffs into chat context, and never widen a deep
review into a re-plan — findings go back as course corrections on
the unit.

## Failure discipline

- Defects go back as ONE itemized feedback turn: what fails, the
  evidence, the expected state. Unnamed aspects are accepted —
  don't drip-feed findings across turns.
- A second failure on the SAME defect is a plan signal, not a
  retry: pull the unit back to Plan (respec or resize) and tell
  the user.
- **You never repair** — no edits, commits, reverts, or `gh`
  mutations during QA; every fix flows through the engineer
  session. The write boundary applies to QA too.
- Depth scales with stakes (common floor): a scratch script gets
  steps 1–3; anything merged to a shared default branch, deployed,
  or user-facing gets the full contract.

## Leaves

| Leaf | Owns |
| --- | --- |
| `inspection.md` | archetype-keyed deliverable inspection — the receiving side of the plan leaves' verification defaults |
| `acceptance.md` | merge readiness, purpose acceptance, epic close — the verification side of close-out |
