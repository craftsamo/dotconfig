/**
 * Shared GitHub layer behind the gh_issue_* and gh_project_* tools (not a
 * tool module itself; the plugin registers ../gh_issue and ../gh_project).
 *
 * - board.ts    adding an issue or PR to a board and setting its fields
 * - gql.ts      GraphQL over `gh api graphql`, with pagination
 * - refs.ts     parsers for issue / repository / project references
 * - repo.ts     the repository context: owner type, viewer permission
 * - project.ts  which board a call means (explicit → linked → org → user) and its fields
 * - items.ts    one flat shape for project items and their content
 * - issues.ts   issue detail and search reads
 * - kind.ts     an issue's kind as an Issue Type (organizations) or a `type:*` label
 *
 * Everything goes through `gh`, so the fake `gh` of the tests covers it.
 */

export * from "./board"
export * from "./gql"
export * from "./issues"
export * from "./items"
export * from "./kind"
export * from "./project"
export * from "./refs"
export * from "./repo"
