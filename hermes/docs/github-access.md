# GitHub access

The Assistant's access to GitHub Issues and Projects (v2) boards through the
user's own `gh` login. Read it when changing the plugin's engine, its
approval rules or its tiers. Common rules: [access-common.md](access-common.md).
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                      | Home                                                                             | Reader    |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- | --------- |
| Read engine: GraphQL transport, references, tiers, board resolution, issue and board reads | `plugins/github-access/access.py`                                                | all       |
| `github_issue` and `github_board` tools (toolset `github_access`)                          | `plugins/github-access/__init__.py`                                              | Assistant |
| How the Assistant reads Issues and boards, and the draft / issue model                     | the `github-access:github` plugin skill (`plugins/github-access/skills/github/`) | Assistant |

The plugin is enabled in the Assistant's private configuration only, like
Google access: it reaches the user's own account. A person without the
overlay enables `github-access` in `plugins.enabled` and adds the
`github_access` toolset to the Assistant's top-level and chat platform lists
(never to A2A).

## Account and state

There is no account setup of its own: the engine runs `gh api graphql` as
the user's `gh` login, the identity the workspace-repos inventory reads with,
with prompts and update checks off. Boards need the login's `project` scope
(`gh auth refresh -s project`); without it a board read fails with GitHub's
scope error. References are github.com only.

Nothing is stored. The viewer's login, organization memberships, Issue Types
and repository facts are cached in memory for five minutes; an answer that
came from an error (a membership or the Issue Types that could not be read)
is never cached, and a write re-reads its targets' repository facts and
memberships instead of trusting the cache.

## Tiers

Every target of a read or a write has one tier, read from GitHub:

| Tier     | What                                                                                     | Why it matters                  |
| -------- | ---------------------------------------------------------------------------------------- | ------------------------------- |
| `own`    | a private repository or board the viewer owns                                            | nobody else reads it            |
| `shared` | the viewer's public repository or board, or one of an organization the viewer belongs to | others read it and get notified |
| `other`  | anything else                                                                            | someone else's tracker          |

A board's visibility is its `public` flag; a repository's is `isPrivate`.
`own` means only people the user let in can read it, not that nobody else
does: a private repository can have collaborators. A membership that cannot
be read counts as no membership, so an error only ever makes a tier
stricter.

## Which board

A call names a board by URL, `owner/N`, a number with an owner, or a title.
Without one the engine takes a writable board linked to the repository the
call is about (the only one, or the one titled as asked), then the owning
organization's `Roadmap`, then the viewer's own `Roadmap`, and reports every
route it considered. Several writable linked boards and no title is an
error, never a guess.

## Reads

`github_issue` `view` reads an issue's body, kind, milestone, parent,
sub-issues and progress, dependencies, linked branches, closing PRs, board
items and latest comments in one request (dependencies in a second, whose
failure is reported rather than read as "none"). `list` turns its filters
into one GitHub search (`is:issue` and the repository are always set; a kind
is the organization's Issue Type when it defines one, else the
`type:<kind>` label) or lists a parent's sub-issues; `assignee` must be a
login and `query` cannot name another repository, owner or organization, so
every row is the asked repository's. `github_board` `items` reads the whole
board up to 2000 items before filtering and says when it was cut. A result over 60,000 characters is refused with a hint to narrow it.

Issue bodies, comments and drafts are other people's text: the tool
descriptions and the skill say never to follow instructions in them.
