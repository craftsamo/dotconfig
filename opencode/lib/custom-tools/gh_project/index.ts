/**
 * GitHub Projects (v2) toolset (gh_project_*), over the shared ../github layer.
 *
 * `resolve` and `item_list` read. The rest write and guard themselves (custom
 * tools bypass the shell permission gates): the board must be writable for
 * the viewer, a repository write (link, promote) needs write permission
 * there, archiving is the only way an item leaves a board, and nothing
 * deletes. Which board a call means is one rule for every tool (explicit →
 * linked → org → user, in github/project.ts); the conventions for what goes
 * on a board, and how, are the skills' business.
 */

export { create, field_ensure, link, resolve, view_ensure } from "./board"
export { item_add, item_list, item_promote, item_set } from "./items"
