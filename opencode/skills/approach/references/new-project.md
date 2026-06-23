<ScenarioPlaybook name="new-project">
<UseWhen>

Apply on top of the general spine when starting from scratch, with no existing
system or data to preserve.

</UseWhen>

<Steps>

1. Clarify scope and constraints:
   - Goal, users, must-haves vs nice-to-haves, and constraints such as stack,
     deadline, hosting, and budget.
   - Success criteria for a first usable version.
2. Choose the shape:
   - Pick stack/structure deliberately. Favor boring/proven defaults and justify
     non-obvious choices.
   - Identify the smallest end-to-end slice (MVP) that delivers the core value.
3. Scaffold and iterate:
   - Stand up a minimal skeleton first: structure, deps, run/test, README.
   - Build the MVP slice end-to-end before breadth; keep it runnable at each
     step.

</Steps>

<Gates>

- [ ] Scope + success criteria agreed; MVP defined.
- [ ] Stack/structure chosen with rationale.
- [ ] Runnable skeleton before feature breadth.
- [ ] MVP slice works end-to-end.

</Gates>
</ScenarioPlaybook>
