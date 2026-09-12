# Hands option-backed references

Give OpenCode the agreed scope, outcome, evidence and acceptance checks from
[Plan](../../plan-engineer/references/hands-references.md), plus the candidate worktree's
`opencode/skills/hermes/hands-references/SKILL.md` path to read. That Skill
owns authoring and verification detail; do not copy its body into the prompt.
Its candidate path is usable without a global Skill install or wrapper change.

1. Load machine-env for dotconfig ownership and self-modification boundaries.
   Bind the job to the intended dotconfig task worktree, NOT the upstream
   hermes-agent source checkout. A branch in live ~/.config is not isolation:
   existing ~/.hermes symlinks can expose edits before merge. Do not redirect
   live links or use install.sh to test a candidate.
2. After explicit implementation approval, use opencode_call agent="build"
   with the existing approval/conversation/worktree binding. Engineer performs
   no target edits itself. A request to change Engineer's own pipeline or agent
   platform requires explicit self-modification scope even through OpenCode;
   ordinary implementation approval does not override machine-env's guard.
3. Require the Skill's Verify evidence from this candidate, using the documented
   Hermes test environment. Additional runtime changes, installations or paid
   media tests are not implied by a reference-maintenance release.
4. Send results to [QA](../../qa-engineer/references/hands-references.md). Deliver through
   the normal task-branch push/PR contract; merge, deployment, linking and gateway
   restart remain separately gated. Do not change broker or maintainer policy
   merely because an option was added.
