---
name: assess-engineer
description: "Assess engineering: investigate without target changes."
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: engineer-pipeline
    tags: [assess, engineering]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or scope changes, including within a turn.
Load the root with skill_view(name="engineer-pipeline") only if its full body
is not already present in the current context; reuse full-body instructions
only while present in the current context, not a past load or summary. This
entry is the mode procedure itself, not a second common mode index. Canonical
root fallback when skill_view returns unchanged without its earlier body is
`${HERMES_SKILL_DIR}/../SKILL.md`; recover this entry's own
body and its references from `${HERMES_SKILL_DIR}` via read_file and
next_offset. Stop the affected action when a required body is unavailable;
never take an alternate path or an artificial range to dodge this check.

Before the first wrapper call, or whenever transport context is lost, load
skill_view(name="engineer-pipeline", file_path="references/opencode.md") if
its full body is not already present, with fallback
`${HERMES_SKILL_DIR}/../references/opencode.md`; no generic per-mode common
transport copy. Reading the root or transport file is not implementation
approval. A cross-mode link requires loading that mode's owning entry and the
root before applying its details -- only the locally relevant details apply here.

</ReadBeforeWork>

# Assess

Answer a bounded question about an existing system, feasibility, a symptom or
someone's change. No unsolicited implementation, Issue write or PR. For a plan
to create/change a system, use [Plan](../plan-engineer/SKILL.md); advice may still end in
the reply. Read [OpenCode](../references/opencode.md) before delegating code investigation.

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
   [QA](../qa-engineer/SKILL.md) without automatically authorizing fixes.
   Inbound A2A has no browser/terminal/child work: return a bounded answer from
   available evidence or ask for a resident execution release.
5. Return findings, evidence, uncertainty and the useful next decision. No numeric
   confidence theater or claims that a proposed fix was tested. A confirmed bug
   is not implementation approval; request a release if the Client wants it fixed.

Environment knowledge is inspected through opencode-env/machine-env only when
needed. Starter investigation uses starter-catalog to propose actual candidates;
it does not create repositories, select a paid platform or establish a skeleton.

An image-creator/video-creator/audio-creator hands leaf's option-backed
reference catalog uses [Hands references](references/hands-references.md) instead of an
ad hoc file investigation.
