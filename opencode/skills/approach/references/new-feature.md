<ScenarioPlaybook name="new-feature">
<UseWhen>

Apply on top of the general spine when adding a capability to an existing
system.

</UseWhen>

<Steps>

1. Understand the existing system:
   - Find the relevant areas and the existing patterns/conventions to follow.
   - Identify the seams where the feature plugs in; read nearby tests.
2. Design the smallest change:
   - Prefer the minimal, idiomatic change that fits existing patterns over a
     parallel new way.
   - Make scope explicit and defer scope creep to follow-ups.
3. Implement and integrate:
   - Build incrementally; keep the system working at each step.
   - Wire in at the identified seams; reuse existing helpers/abstractions.
4. Verify:
   - Add or extend tests; run the project's build/lint/test checks before
     claiming done.
   - Confirm no regressions in adjacent behavior.

</Steps>

<Gates>

- [ ] Existing patterns/conventions followed.
- [ ] Scope explicit; creep deferred to follow-ups.
- [ ] Tests added or updated; project checks pass.
- [ ] No nearby regressions.

</Gates>
</ScenarioPlaybook>
