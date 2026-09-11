# Hands option-backed references

Read when an Assess request is about image-creator/video-creator/audio-creator
hands leaves' local option-backed references: styles, themes, destinations,
packs, contents and similar catalogs. Excludes Writer's language references,
Creator's broker guidance and any Assistant deliverable guide; those stay with
their own workflows. Ask OpenCode to read the candidate checkout's
`opencode/skills/hermes/hands-references/SKILL.md` (hermes-hands-references)
for procedural detail. Pass that path and the job-specific question, not a
copied Skill body or an invented wrapper parameter. A candidate path works
even before global discovery includes the new Skill. Engineer owns the decision
being informed and can read the same file for independent inspection.

1. Resolve the target from the question and available sources first. If no leaf
   is chosen, agree a bounded inventory of the relevant hands; do not demand a
   filename from the Client. Adding/improving moves to
   [Plan](../plan/hands-references.md) only when requested. Producing media or
   retiring an option uses a different workflow.
2. Run the Skill's read-only audit from the candidate root
   (`python3 hermes/scripts/audit-hands-references.py --root . [--leaf REPO/RELATIVE/LEAF] --json`)
   using the documented Hermes-venv Python. Exit 0 means no structural errors,
   not verified quality; UNVERIFIED is useful uncertainty, not itself a defect.
   The adapter imports trusted candidate Python, not sandboxed third-party code.
   Missing tools do not authorize installation. Inbound A2A cannot run the audit;
   follow the parent mode's resident-session boundary.
3. Read the flagged leaf's Procedure, current references and consumers before
   concluding. Do not repair anything: an audit request is not permission to
   repair, and this mode never edits. Orphan candidates may be legitimate support
   documents. Separate structural findings, evidence gaps and actual prose
   contradictions; file/heading parity is not a quality judgment.
4. Return findings, evidence and the useful next decision under the normal
   [Assess](index.md) contract. A confirmed gap is not implementation approval.
