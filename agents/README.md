# Shared agent skills

`agents/skills/` is the one skill tree every AI CLI on this machine reads.
It backs `~/.agents/skills`, the cross-agent convention defined by the
[Agent Skills](https://agentskills.io/client-implementation/adding-skills-support)
client guide, and doubles as the install target of the `skills` CLI.

| Symlink             | Target          |
| ------------------- | --------------- |
| `~/.agents/skills`  | `agents/skills/` |
| `~/.claude/skills`  | `agents/skills/` |

Only `skills/` is linked. The `skills` CLI keeps its update state in
`~/.agents/.skill-lock.json`, which is per-machine and stays outside the repo.

## Who reads what

| CLI            | Reads `~/.agents/skills` | Own skill dir                 |
| -------------- | ------------------------ | ----------------------------- |
| Codex          | yes (canonical path)     | `~/.codex/skills` (legacy)    |
| opencode       | yes                      | `~/.config/opencode/skills`   |
| GitHub Copilot | yes                      | `~/.copilot/skills`           |
| Grok Build     | yes (AGENTS.md compat)   | `~/.grok/skills`              |
| Gemini CLI     | yes (alias)              | `~/.gemini/skills`            |
| Claude Code    | **no**                   | `~/.claude/skills` — bridged  |

Claude Code only scans `~/.claude/skills`, so `install.sh` points that
symlink at this directory instead of giving Claude a private tree.

Skill directories must be **flat** — `agents/skills/<name>/SKILL.md`. Codex
and Claude Code do not descend into nested groups, so a shared skill cannot
be filed under a category subdirectory the way opencode allows.

## What lives here

Only skills that any agent can actually follow. A skill that names opencode
subagents (`explore-medium`, `reviewer`, ...) or opencode-only tools
(`git_commit_lint`, `github_project_*`) stays in
[`opencode/skills/`](../opencode/skills) — sharing it would tell other agents
to call tools they do not have.

## Tracking policy

`agents/skills/**` is git-ignored by default, because the `skills` CLI
installs third-party skills into the same directory. Own skills opt in once:

```sh
git add -f agents/skills/<name>/SKILL.md
```

Tracked files are unaffected by the ignore rule afterwards.

Third-party skills are restored from their source rather than committed. The
HyperFrames set (`hyperframes*`, `media-use`) is reinstalled with the
HyperFrames CLI (`npm i -g hyperframes`):

```sh
hyperframes skills          # install the full set into every supported CLI
hyperframes skills update   # update installed skills, drop unpublished ones
```

Note that the global `~/.agents/.skill-lock.json` written by the `skills` CLI
records installs but has no restore command — it cannot be used to rebuild
this directory on a fresh machine.
