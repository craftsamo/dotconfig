# Assess

Answer a bounded question about an existing system, feasibility, a symptom or
someone's change. No unsolicited implementation, Issue write or PR. For a plan
to create/change a system, use [Plan](../plan/index.md); advice may still end in
the reply. Read [OpenCode](../opencode.md) before delegating code investigation.

1. Identify the decision being informed, the actual target and the needed evidence.
   Missing paths, reproduction inputs or expected behavior are questions; do not
   guess another project or require irrelevant implementation fields.
2. Select the fitting read-only OpenCode agent: plan for facts/feasibility, debug
   for root cause, review for a change. Supply current sources and the requirement.
   Safe independent observations can run locally; tests may have side effects,
   so inspect their scope before execution. Do not install, regenerate or repair
   the target just to obtain an answer.
3. Diagnose from reproduction and evidence, not an error label alone. A feasibility
   answer separates known capabilities, assumptions, constraints and untested parts.
   A review presents ranked actionable findings with file/line or runtime evidence.
4. Visual/UX review of a running test target follows
   [QA](../quality-assurance/index.md) without automatically authorizing fixes.
   Inbound A2A has no browser/terminal/child work: return a bounded answer from
   available evidence or ask for a resident execution release.
5. Return findings, evidence, uncertainty and the useful next decision. No numeric
   confidence theater or claims that a proposed fix was tested. A confirmed bug
   is not implementation approval; request a release if the Client wants it fixed.

Environment knowledge is inspected through opencode-env/machine-env only when
needed. Starter investigation uses starter-catalog to propose actual candidates;
it does not create repositories, select a paid platform or establish a skeleton.
