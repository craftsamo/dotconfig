---
name: workspace-scaffold
description: Scaffold a new repo or personal area in ~/Workspaces (flat layout) — make the dirs, git init a repo, and seed a tool-agnostic AGENTS.md from the template.
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [workspace, scaffold, repo, setup]
    category: setup
---
# Workspace scaffold

Create new repos / areas under `~/Workspaces` with the standard flat layout and a
seeded `AGENTS.md`. The workspace map and rules live in `~/Workspaces/AGENTS.md`.

## When to Use
- The human asks to start/add a new project, repo, or personal area in `~/Workspaces`.
- Not for editing existing project code (that's a normal coder task).

## Layout (flat)
- Code: `~/Workspaces/Projects/github/<owner>/<repo>/` — each repo: own git + `AGENTS.md`.
- Project docs (out-of-codebase): `~/Workspaces/Projects/docs/<project>/`.
- Personal (no git): `~/Workspaces/Personal/{data,docs,Peoples}/`.

## Procedure
1. Confirm with the human: is this code (Projects) or personal data (Personal)?
   the name, and for a repo the `<owner>/<repo>`.
2. New code repo — run the helper:
   `terminal(command="${HERMES_SKILL_DIR}/scripts/ws-new.sh repo <owner>/<repo>")`
   It makes `Projects/github/<owner>/<repo>`, `git init`s it, and copies the repo
   `AGENTS.md` template.
3. Fill the new `AGENTS.md` with real, **tool-agnostic** project facts (architecture,
   build/test/run, conventions, paths) — no tool-specific or Hermes-specific text.
4. Personal area:
   `terminal(command="${HERMES_SKILL_DIR}/scripts/ws-new.sh personal <name>")`
   makes `Personal/<name>/` for data (no git).
5. Report what was created; don't commit/push without the human's go-ahead.

## Pitfalls
- Keep repo `AGENTS.md` tool-agnostic — it's read by every agents.md-aware tool
  (Hermes/OpenCode/Codex/Cursor). Tool-specific guidance goes in that tool's own file.
- Never `git init` a Personal area — it holds sensitive, intentionally-untracked data.
- These are local instance data; don't track them under the dotfiles repo.

## Verification
- Dirs exist; a code repo has `.git` + an `AGENTS.md`; the `AGENTS.md` is filled in
  (not left as the template stub).
