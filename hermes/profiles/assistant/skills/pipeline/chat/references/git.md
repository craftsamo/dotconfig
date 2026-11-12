# Git

Load the skill for the work before the first call; each owns its tools'
mechanics, and this file holds only what is particular to Chat:

| Work | Skill |
| --- | --- |
| A repository's state, conflicts, conventions and origin | `skill_view(name="git-tools:repo")` |
| Listing, creating or removing a person's own task worktree | `skill_view(name="git-tools:worktree")` |

## What stays in Chat

- Read a repository's state with `git_repo_read` (`status`, `conflicts`,
  `conventions`, `origin`). Reading history and finding where a change came
  from stays inline too, with git's own reads in the terminal.
- List worktrees with `git_worktree_read` `list`. A person's own task
  worktree is created with `git_worktree_add` and, once landed, removed with
  `git_worktree_remove`, each change on its card. Removal never forces; the
  tool deletes the branch only once it has landed. An unlanded branch stays.
- A worktree an OpenCode session sits in is never yours to create or remove
  with these tools: `opencode_session workspace` and `opencode_session cleanup`
  manage it together with its sessions.

## Boundaries

Commits, rebases and pushes on target repositories are OpenCode's,
commissioned through the engineering pipeline, not Chat's. The terminal
runs only git's reads, `git fetch`, `git pull --ff-only` and `git clone`.
Resetting a clone or deleting an unlanded branch is the user's to do: tell
them the command, never run it yourself. Never use the package's command
line or installed directory as a way around the tools.

Every write waits for the user to answer its card; nothing writes where no
person can answer. Inbound A2A requests cannot use these tools, even to read.
