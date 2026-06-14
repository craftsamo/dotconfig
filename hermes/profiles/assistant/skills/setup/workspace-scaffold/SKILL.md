---
name: workspace-scaffold
description: Scaffold a group or repo in ~/Workspaces (nested layout) — make the dirs, git init a repo, and seed a tool-agnostic AGENTS.md from the template.
version: 1.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [workspace, scaffold, repo, setup]
    category: setup
---
# Workspace scaffold

Create new groups / repos under `~/Workspaces` with the standard nested layout and a
seeded `AGENTS.md`. The workspace map and rules live in `~/Workspaces/AGENTS.md`.

## When to Use
- The human asks to start/add a new group, project, or repo in `~/Workspaces`.
- Not for editing existing project code (that's a normal coder task).

## Layout (nested)
- Code: `~/Workspaces/Projects/<Group>/github/<repo>/` — repos flat under the group's
  `github/`; group also has `docs/ data/ teams/`. Each repo: own git + `AGENTS.md`.
- Personal (no git): `~/Workspaces/Personal/<Group>/{data,docs}/`.

## Procedure
1. Confirm with the human: code (Projects) or personal data (Personal)? the `<Group>`,
   and for a repo the `<repo>` name.
2. New group:
   `terminal(command="${HERMES_SKILL_DIR}/scripts/ws-new.sh group projects <Group>")`
   (or `group personal <Group>` for a no-git personal group).
3. New repo (Projects group must exist):
   `terminal(command="${HERMES_SKILL_DIR}/scripts/ws-new.sh repo <Group> <repo>")`
   It makes `Projects/<Group>/github/<repo>`, `git init`s it, and copies the repo
   `AGENTS.md` template.
4. Fill each new `AGENTS.md` with real, **tool-agnostic** facts (architecture,
   build/test/run, conventions) — no tool-specific or Hermes-specific text.
5. Report what was created; don't commit/push without the human's go-ahead.

## Pitfalls
- Keep repo `AGENTS.md` tool-agnostic — it's read by every agents.md-aware tool
  (Hermes/OpenCode/Codex/Cursor). Tool-specific guidance goes in that tool's own file.
- Never `git init` a Personal group — it holds sensitive, intentionally-untracked data.
- Groups/repos are local instance data; don't track them under the dotfiles repo.
- `<Group>`/`<repo>` names: letters/digits/`.`/`_`/`-` only (the helper rejects `/`,
  `..`, and leading `.`/`-`).

## Verification
- Dirs exist; a code repo has `.git` + an `AGENTS.md`; each `AGENTS.md` is filled in
  (not left as the template stub).
