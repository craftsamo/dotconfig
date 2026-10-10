/**
 * Git workflow toolset.
 *
 * Deterministic, read/index-only mechanics that the git-commit and
 * git-pullrequest skills delegate to. The conventions (when/how to commit or
 * open a PR) live in those skills; the mechanics live here.
 *
 * Safety: these tools run git/gh as child processes, which do NOT pass
 * through the shell permission gates, so they are deliberately limited to read
 * and index operations, plus `commit`, which only records what is staged and
 * refuses to amend, skip hooks or stage on its own. They never push, rewrite
 * history, or merge — those stay as gated commands the agent issues directly.
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
