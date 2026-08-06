# Engineering — plan

Ground every implementation plan in the repo before promising anything:

1. **Locate the repo** (Step 2): `pj show <Group>` → the
   `~/Workspaces/Projects/<Group>/github/<repo>` path. No repo yet →
   bootstrap is part of the plan (engineer creates it; you register it
   with `pj repo-set` + `pj link-repo` afterwards).
2. **Establish the base plan session yourself** — an OpenCode plan run in
   the repo, read-only by the plan agent's own permissions:

   ```bash
   cd <repo> && opencode run --auto --agent plan --title "waves: <goal>" \
     'Split this goal into WAVES only — coarse milestones and their
      dependency order, one line each. No phase/unit detail.
      <goal, constraints, done criteria>'
   ```

   Recover the session id (`opencode session list`). This base session —
   not a prose summary — is what the engineer will detail and implement,
   so the outline stays grounded and nothing is lost in translation.
3. **Approve with the user** — present the Wave outline in plain language
   (what lands, in what order, what it costs) plus the Authority the work
   needs (`A1` commit-only default; `A2` push + PR only when the user
   wants a PR; `A3` + dependency changes). One `clarify`.
4. Requirement decomposition for issue-tracked repos ("login feature" →
   epic + sub-issues) is also planned here: the engineer session drafts
   the split (draft-only), the user approves it, and **you** register the
   Issues via `gh` — see the execute file's GitHub ops.

Small settled fixes ("fix the off-by-one in `foo()`, test is
`bar_test.py`") skip the base session: state the intent and go straight
to Execute.

Engineering is **resident-only** — no `card_units` exist for it, and none
should be added until a class of work is fully CI-verifiable without
supervision.
