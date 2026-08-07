# Bootstrap — new-repo Wave 0 (assistant-owned)

A human bootstraps a project by rhythm; you cannot. The repo does not
exist yet, so nothing can be grounded — not even the base plan session
— until Wave 0 lands. Every step below is **yours** (`gh` / `ghq` /
`pj` are assistant tools); the engineer first appears when a worktree
exists to code in.

This file is conventions only. **Concrete repo names, owners, and the
starter inventory are never written here** (this config repo is
public): discover them at runtime, exactly as the engineer's
`starter-catalog` technic prescribes — its discovery recipes, family
conventions (`<root>-starter` → `-with-<platform>` derivatives), and
fit evaluation apply to you unchanged.

## Decisions — fixed in the Brief, sanctioned by the plan approval

| Decision | How it is grounded |
| --- | --- |
| Group | `pj show --id <Group>`; missing → create it in step 1. |
| Repo name + owner | Owner comes from the runtime account context (`gh auth status`, existing ghq owners) — ask when more than one fits; the owner decides the ghq path. |
| Visibility | `--private` default; `--public` only on the user's say-so. |
| Starter or scratch | Run the starter-catalog discovery recipes (ghq + `gh repo list`), shortlist by platform distance, judge fit honestly — a wrong starter costs more than scratch. |
| Deploy target | Usually implied by the chosen platform derivative; LP/website need one, tools often none. |
| History posture | Plain clone keeps starter history; template instantiation starts squashed — state the choice in the plan, never default silently. |

## Steps — in this order

1. **Group missing** → the private `scaffold` skill's
   `ws-new.sh group projects <Group>` (dirs + group `AGENTS.md` +
   registry row).
2. **Create on GitHub first**:
   `gh repo create <owner>/<repo> --private` — with
   `--template <starter>` when the chosen starter is a template repo,
   or from a plain starter clone via `--source … --push` plus an
   `upstream` remote (family wiring per starter-catalog). Never
   `ws-new.sh repo` — its local `git init` bypasses the ghq layout and
   leaves an unlinked, remoteless repo.
3. **Clone via ghq**: `ghq get <owner>/<repo>` →
   `~/ghq/github.com/<owner>/<repo>`.
4. **Register + link**:
   `pj repo-set --project <Group> --name <repo> --owner <owner>`, then
   `pj link-repo --project <Group> --name <repo>` — materializes the
   `Projects/<Group>/github/<repo>` symlink.
5. **Repo `AGENTS.md`** — seed from the scaffold template when the
   starter lacks one; fill with real, tool-agnostic facts
   (architecture, build/test/run, conventions) and commit it. This
   commit is sanctioned by the plan approval.
6. **Verify**: the symlink resolves, `.git` exists, starter files are
   present, `AGENTS.md` is filled (not the stub).

Deploy credentials go through the Keychain shims — never a committed
`.env`. Wiring the deploy target is a normal Wave in the type leaf,
not part of Wave 0. Rebranding (README identity, package names) is the
first Wave of implementation, never part of bootstrap.

Then create the **base plan session inside the new repo** (see
`index.md`) — with a starter there is real code for the plan agent to
ground the Waves in; the type leaf's wave prompt takes over from here.
