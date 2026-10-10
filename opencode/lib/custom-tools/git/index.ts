/**
 * Git workflow toolset.
 *
 * Deterministic, read/index-only mechanics that the git-commit and
 * git-pullrequest skills delegate to. The conventions (when/how to commit or
 * open a PR) live in those skills; the mechanics live here.
 *
 * Safety: these tools run git/gh as child processes, which do NOT pass
 * through the shell permission gates. Most are read-only or touch only the
 * index (`stage_hunks`). The exceptions are bounded on purpose:
 * - `commit` records only what is staged; it cannot amend, skip hooks or stage.
 * - `worktree` creates and removes task worktrees; it never discards
 *   uncommitted changes and deletes a branch only once it has landed.
 * - `verify_commits` runs a caller-given command, so its permission is `ask`.
 * None of them pushes, rewrites history or merges — those stay gated shell
 * commands. Read-only agents deny the writing ones (opencode.jsonc,
 * agents/*.md, and Hermes' run rulesets).
 */

export { amend_check } from "./amend"
export { commit } from "./commit"
export { conflicts } from "./conflicts"
export { stage_hunks } from "./hunks"
export { history_digest } from "./history"
export { commit_lint } from "./lint"
export { provenance } from "./provenance"
export { related_scan } from "./related"
export { secret_scan } from "./secrets"
export { state } from "./state"
export { verify_commits } from "./verify"
export { worktree } from "./worktree"
