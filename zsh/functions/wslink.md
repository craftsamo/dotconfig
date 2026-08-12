# wslink — workspace repo-link manager

`wslink` manages the symlinks that group your `~/ghq` clones under
`~/Workspaces/Projects/<group>/github/<repo>`: an fzf browser plus a small CLI,
backed by the projects registry (`pj`). It exists so that linking a freshly
cloned repo into its workspace group is one quick step instead of a chore you
forget after every `ghq get`.

Implementation: [`wslink.zsh`](./wslink.zsh) — plain zsh over `pj`, `ghq`, `jq`
and `fzf`, no daemons. Loaded automatically by [`config.zsh`](../config.zsh).
`wslink help` prints the full reference.

## Requirements

`fzf` (browser), `jq` (registry JSON), `ghq` (clone listing) and `pj` (the
projects registry CLI). [`bin/pj`](../../bin/pj) is a launcher: the registry
skill itself lives in the private overlay (`~/.config/private`), so it
resolves the implementation there (`PJ_BIN` overrides) and fails with a clear
message when the overlay is not installed.

## Quick start

```sh
ghq get github.com/acme/widget        # clone as usual
wslink add widget -p Personal         # register + symlink into Personal/github
wslink                                # or: interactive wizard (also C-s)
wslink ls -l                          # list every link with status
wslink sync                           # fix unlinked registered repos; report drift
```

`C-s` opens the wizard from any prompt (terminal flow control is disabled in
[`zsh_user_key_bindings.zsh`](./zsh_user_key_bindings.zsh) so the key reaches zle).

## Model

A *link* is a symlink `Projects/<group>/github/<name>` → a `~/ghq/<host>/<owner>/<name>`
clone. The registry (`pj`) records which repo belongs to which group; `wslink`
keeps the filesystem symlinks and the registry in step. A *group* is a `pj`
project that has a `dir_path`.

| Sigil | State          | Meaning                                            |
| ----- | -------------- | -------------------------------------------------- |
| `●`   | ok             | symlink present and points at the registered clone |
| `○`   | declared       | registered, clone present, no symlink yet          |
| `+`   | unregistered   | a ghq clone with no registry row / link            |
| `✗`   | broken-link    | symlink target is missing                          |
| `≠`   | wrong-target   | symlink points somewhere other than the clone      |
| `?`   | orphan-link    | symlink with no registry row                       |
| `!`   | conflict       | a real file/dir occupies the link path             |
| `…`   | missing-clone  | registered, but the clone is not on disk           |

## Wizard (bare `wslink` / C-s)

A nested, step-by-step flow (modelled on `secret`): a full-width action menu,
then compact full-width pickers — no side preview, so long names never get cut
off. One action per invocation; press `C-s` again for the next.

```
wslink › choose an action
  Add      pick a group → pick clone(s) (Tab=multi) → confirm
  Update   pick group ([all] ok) → pick link → Repair / Repoint / Move
  Delete   pick group ([all] ok) → pick link(s) (Tab=multi) → confirm
  List     pick group ([all] ok) → wslink ls -l
  Show     pick group ([all] ok) → pick link → details (incl. git status)
  Sync     pick group ([all] ok) → wslink sync
```

`Delete` always unlinks **and** removes the registry row (the entry disappears);
use `wslink rm --keep-registry` on the CLI if you want to keep the registry row.

## CLI

```sh
wslink ls [-p GROUP] [-l]                        # list links (+status); -l = long
wslink show NAME [-p GROUP]                       # details of one link
wslink add [-p GROUP] [REPO…]                     # register + symlink clone(s)
wslink update NAME [-p GROUP] [--repair|--repoint|--move GROUP]
wslink rm NAME [-p GROUP] [--keep-registry] [-f]  # unlink (+ remove registry row)
wslink sync [-p GROUP]                            # link the unlinked; report drift
wslink help
```

`GROUP` resolution: `-p NAME` > the group whose `github/` dir contains the
current directory > (interactive) an fzf picker. `REPO` is a clone name, or
`owner/name` when the basename is ambiguous across owners.

`update` modes: `--repair` (default) recreates a missing/wrong symlink from the
registry; `--repoint` aims the same link name at a different clone; `--move`
relocates the link (and its registry row) to another group.

## Safety

- The `~/ghq` clone itself is **never** deleted — `wslink` only ever creates or
  removes **symlinks**.
- A real file or directory sitting at a link path is never overwritten; the
  operation aborts and reports it.
- Registry changes always go through `pj`; the SQLite DB is never hand-edited.
- Destructive actions (`rm`, and Delete/Move in the browser) confirm first
  (`-f` skips the prompt for `rm`).

## Non-interactive use

[`bin/wslink`](../../bin/wslink) sources `wslink.zsh` and dispatches, so the CLI
works from scripts, `zsh -c`, and opencode where `config.zsh` has not loaded the
function. It is also what the fzf preview invokes (`wslink __preview …`), so the
preview only ever sees names and paths. Interactive shells call the function
directly (it outranks the `bin/` command on `PATH`).
