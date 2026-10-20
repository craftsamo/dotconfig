/**
 * GitHub Issues toolset (gh_issue_*), over the shared ../github layer.
 *
 * Reads (`view`, `list`) are free of side effects. Writes (`create`,
 * `update`, `comment`, `relate`, `develop`) run gh as a child process and so
 * bypass the shell permission gates; they guard themselves instead: write
 * permission on the repository is checked first, a repository the viewer does
 * not own is reported as `foreign`, closing needs a reason, relations already
 * in place are left alone, and nothing deletes.
 *
 * The planning model (parent issue + sub-issues, milestone for time, blocked
 * by for order, kind as Issue Type or type:* label) is the skills' business;
 * the tools expose GitHub's own primitives and do not enforce a hierarchy.
 */

export { develop } from "./develop"
export { list, view } from "./read"
export { relate } from "./relate"
export { comment, create, update } from "./write"
