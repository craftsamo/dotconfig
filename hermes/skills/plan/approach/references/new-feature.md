<ScenarioPlaybook name="new-feature">

Apply on top of the general spine when adding a capability to an existing system.

<Steps>

1. **Understand the existing:**
   - Find the relevant areas and the existing patterns/conventions to follow.
   - Identify the seams where the feature plugs in; read nearby tests.
2. **Design the smallest change:**
   - Prefer the minimal, idiomatic change that fits existing patterns over a parallel new way.
   - Make scope explicit; resist scope creep (record follow-ups separately).
3. **Implement & integrate:**
   - Build incrementally; keep the system working at each step.
   - Wire in at the identified seams; reuse existing helpers/abstractions.
4. **Verify:**
   - Add/extend tests; run the project's checks (build/lint/test) before claiming done.
   - Confirm no regressions in adjacent behavior.

</Steps>

<Gates>

- [ ] Followed existing patterns/conventions
- [ ] Scope explicit; creep deferred to follow-ups
- [ ] Tests added/updated; project checks pass
- [ ] No regressions nearby

</Gates>
</ScenarioPlaybook>
