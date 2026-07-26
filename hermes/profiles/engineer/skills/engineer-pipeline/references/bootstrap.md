# Bootstrap mode — establish a repo before OpenCode can help

Loaded when <ModeRouting> detects a bootstrap task: the body opens with
`Bootstrap — establish the repo, don't plan or ship.`. It runs only when
**no repo exists yet** — orient has already reported "no repo, bootstrap
needed" and the orchestrator has decided the target and the path (clone /
starter / greenfield). Every downstream OpenCode slice (plan, implement) is
meaningless without a repo; bootstrap creates the precondition.

This is the engineer's only **write** slice that does **not** use OpenCode —
OpenCode operates on a codebase, and there is none yet. Work with `git` /
`gh` / a scaffolder directly. Bootstrap establishes the repo skeleton and an
initial commit; it never plans Waves (that is plan) and never builds features
(that is implement).

## Authority — B1 / B2 (bootstrap presets, not A1-3)

The worktree-centric A1/A2/A3 don't apply — there is no worktree. Parse the
body's `Authority:` line as a bootstrap preset:

| Preset | Grants |
| --- | --- |
| `B1` (default) | Create the repo **locally only** — clone / scaffold / `git init` into the target ghq path, run the chosen starter's scaffolder (its dependency install is part of that choice), make the initial commit. No remote. |
| `B2` | B1 + `gh repo create` (the named repo + visibility from the body) + push the initial commit to it. |

- Missing or unparseable `Authority:` → assume **B1** (local only). Never
  create a remote or push without an explicit `B2`.
- The scaffolder for the chosen starter may install dependencies — that is
  inherent to selecting that starter and needs no separate grant. Do **not**
  add unrelated dependencies or run anything beyond establishing the skeleton.
- Anything outside the grant (remote creation/push at B1, a different repo
  name/visibility than the body states, destructive acts on existing dirs) →
  checkpoint-then-block (core <CheckpointThenBlock>), never improvise.
- **Never touch pj / the Workspaces registry** — registration
  (`pj repo-set` + `pj link-repo`) is the assistant's job after you report.

## Inputs (from the task body)

The orchestrator supplies these; block if a required one is missing:

- **Target** — `owner` + `repo` name, and the absolute ghq path to create at
  (`~/ghq/github.com/<owner>/<repo>`). This is the **durable home**, addressed
  by absolute path — the repo persists there regardless of the task workspace.
  The task runs in a **`scratch`** workspace: a `dir` workspace can't point at
  a not-yet-existing greenfield path (the worker is spawned with `cwd` = the
  workspace, which must exist), and a worktree needs a repo that doesn't exist
  yet. So create/clone/scaffold at the absolute ghq path (`git -C <path>` /
  `<scaffolder> <path>`), never relative to the scratch dir.
- **Path** — one of `clone <url|owner/repo>` / `starter <scaffolder + source>`
  / `greenfield`.
- **Visibility** (B2 only) — `public` / `private` for `gh repo create`.

Surveying starter candidates is the orchestrator's job (it may fan out to
searcher/researcher); bootstrap executes the single chosen path — it does not
shop for a starter itself.

## Procedure

1. **Guard.** Confirm the target ghq path does not already contain a repo
   (`git -C <path> rev-parse` fails / the dir is absent or empty). A
   non-empty target is a block, not an overwrite.
2. **Establish the repo** per the chosen path, into the target ghq path:
   - **clone** — `gh repo clone <owner>/<repo> <path>` (or `git clone <url>
     <path>`). History comes with it; usually no extra initial commit.
   - **starter** — run the scaffolder the body named into `<path>`, e.g.
     `npx degit <owner>/<repo>[/subdir] <path>` (template copy, no history),
     `npx create-next-app@latest <path> …` / `npm create vite@latest` /
     `cargo new` / `uv init` (framework CLIs), then `git init` if the
     scaffolder didn't. `gh repo create <name> --template <owner>/<repo>`
     is a **B2** action (it creates the remote).
   - **greenfield** — `git init <path>`, add a minimal skeleton the body
     asks for (README, `.gitignore`, license only if requested) — nothing
     speculative.
3. **Initial commit** — stage the skeleton and commit
   (`git -C <path> add -A && git -C <path> commit -m "chore: initial commit"`)
   unless a clone already carries history.
4. **Remote (B2 only)** — `gh repo create <owner>/<repo> --<visibility>
   --source <path> --remote origin --push` (or create-then-push). Skip
   entirely at B1.
5. **Report** the handoff facts (below). Do **not** run pj.

## Report format

```markdown
## Repo
<owner>/<repo> established at <ghq-path>
## Path taken
<clone|starter <name>|greenfield>, initial commit <sha>
## Remote
<url> (pushed)  —  or  "none (B1, local only)"
## Stack
<languages / framework / package manager the skeleton uses, 1-3 lines>
## Registration handoff
pj repo-set --project <suggested Group> --name <repo> --owner <owner> \
  --url <url|—> --ghq-path <ghq-path>   ;  then  pj link-repo …
(the assistant runs this — bootstrap only reports it)
```

## Report

- Final message = the establishment summary + the registration handoff facts
  (ghq path, remote url or none, suggested slug/Group).
- `kanban_complete` summary = 1-2 plain sentences the assistant can act on,
  e.g. "Repo acme/site established at ~/ghq/github.com/acme/site (Next.js),
  pushed to github.com/acme/site — ready to register in pj." — delivered
  verbatim to the requester's chat.

## MEMORY.md

Persist only durable facts worth carrying forward (the starter/stack chosen,
its build/test commands) — never the transient report. Task state lives in
the kanban thread.

## Pitfalls

- Opening OpenCode — there is no codebase yet; bootstrap is git/gh/scaffolder
  only. OpenCode starts at the plan slice, once the repo exists.
- Creating a remote or pushing at **B1** — local only until an explicit B2.
- Running pj / materializing the Workspaces symlink — that is the assistant's
  post-bootstrap step; you only report the handoff facts.
- Overwriting a non-empty target instead of blocking.
- Scaffolding speculative structure (folders, deps, boilerplate) the body
  didn't ask for — establish the minimum skeleton and stop; feature work is
  the implement slice.
- Planning Waves/Phases here — that is the plan slice, on the now-existing repo.
- Shopping for a starter — the orchestrator decided the path; execute the
  chosen one, block if it's missing.

## Verification

- The repo-exists guard ran; a non-empty target was blocked, not overwritten.
- The chosen path was executed into the target ghq path; an initial commit
  exists (or clone history is present).
- Remote/push happened only under B2, matching the body's name + visibility;
  nothing remote at B1.
- pj was NOT touched; the report carries the ghq path, remote url (or none),
  and a suggested Group/slug for the assistant to register.
- No OpenCode invocation; no speculative scaffolding beyond the asked skeleton.
