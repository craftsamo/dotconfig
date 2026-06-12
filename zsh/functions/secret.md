# secret — macOS Keychain secrets CLI

`secret` manages development secrets (API keys, tokens, passwords) in the
macOS Keychain from the terminal: an fzf wizard, per-project organisation,
encrypted import/export, and one master password for every custom keychain.

Implementation: [`secret.zsh`](./secret.zsh) — plain zsh on top of the
built-in `/usr/bin/security`, no daemons. Loaded automatically by
[`config.zsh`](../config.zsh). `secret help` prints the full reference.

## Requirements

From the [Brewfile](../../Brewfile): `fzf` (interactive UI), `jq`
(JSON import/export), `age` (encrypted exports).

## Quick start

```sh
secret                          # fzf wizard: Get / Add / Update / List / Show / Delete / Export / Import
secret set STRIPE_KEY -j "prod key, rotate in dashboard" -D "api key"
secret get STRIPE_KEY           # value on stdout   (-c: clipboard, auto-clears in 45 s)
secret ls --long                # names + kind + modified + comment
eval "$(secret env -p global)"  # inject a whole project as environment variables
```

Project resolution: `-p NAME` > `git config secret.project` > the git
repository name > `global`. Run `secret link NAME` once per clone of a
multi-repo product so they all share one project (`secret link` alone
shows how the current directory resolves, `--unset` removes the mapping).

## Data model

One keychain item per secret — fully visible and editable in Keychain Access:

| Attribute | Value                                                                        |
| --------- | ---------------------------------------------------------------------------- |
| service   | `secret.<project>` (shared) or `secret.<project>/<scope>` (scoped) — lookup key together with account |
| account   | the variable name (`TAVILY_API_KEY`) — **unique key, do not repurpose**      |
| label     | `NAME` / `<scope>/NAME` inside the project's own keychain, prefixed with `<project>/` elsewhere |
| kind      | free text shown in the GUI, default `ENV` (`-D`)                             |
| comment   | free-form description (`-j`), shown by `show` / `ls --long` / the GUI        |

## Keychains

**One project = one keychain**: project `P` lives in
`~/Library/Keychains/P.keychain-db`, so Keychain Access always shows exactly
one project per keychain (`global` included). `-k NAME|PATH` overrides the
mapping; `-k default` targets the login keychain, which only ever holds the
`keychain-password` bootstrap items.

- Missing keychains are **created automatically on first write** — silently
  when a master password is set, interactively on a terminal otherwise.
- Files that exist but were never **registered in the user search list**
  (app/system keychains like `metadata`, `parallels_shared`) are refused;
  opt in deliberately with `secret keychain register NAME`.
- `secret projects` lists registered keychain names without dumping them,
  so locked keychains never trigger unlock prompts; `export --all` spans
  every registered keychain.

### Scopes — per-repository overrides

Linked repositories share the project's **shared layer**; values that must
differ per repository (`DATABASE_URL`, `PORT`, ...) go into a **scope**,
named after the repository:

```sh
cd ~/Github/example-project/learning-app   # linked to example-project
secret set GOOGLE_CLOUD_PROJECT_ID          # shared: visible to every repo
secret set DATABASE_URL -S                  # scoped: learning-app only
secret get DATABASE_URL                     # scoped first, falls back to shared
eval "$(secret env)"                        # shared + this repo's scope (scoped wins)
```

The same `secret set DATABASE_URL -S` in `courses` lands in its own scope —
no collision. Reads/updates/deletes are DWIM (repo scope first, then
shared); `--shared`, `--scope X` and `-S` pin a specific layer. `ls` shows
scoped items as `scope/NAME`, and so does Keychain Access via the label.

### Master password

All custom keychains share one password, kept in a password manager. A copy
lives in the login keychain so everything unlocks silently:

```
macOS login password
  └─ login.keychain-db ── keychain-password/master (one item)
       ├─ global.keychain-db        (the "global" project)
       └─ <project>.keychain-db ... (auto-created on first write, no prompt)
```

| Command                              | Purpose                                                      |
| ------------------------------------ | ------------------------------------------------------------ |
| `secret keychain master set`         | define it and rotate every registered custom keychain to it  |
| `secret keychain master rotate`      | change it everywhere at once                                 |
| `secret keychain master status`      | unlock source (`master`/`individual`/`none`) + lock state    |
| `secret keychain master reveal [-c]` | show / copy it (for the password manager)                    |
| `secret keychain master forget`      | remove the login copy (access starts prompting)              |
| `secret keychain create NAME`        | new keychain — no password prompt once a master is set       |
| `secret keychain register NAME`      | add a copied `.keychain-db` to the search list               |
| `secret keychain remember NAME`      | per-keychain password override (takes precedence)            |
| `secret keychain ls` | inventory and lifecycle                                  |
| `secret keychain info` | inventory and lifecycle                                  |
| `secret keychain lock` | inventory and lifecycle                                  |
| `secret keychain unlock` | inventory and lifecycle                                  |
| `secret keychain rm` | inventory and lifecycle                                  |

## Launcher shims — env injection without .env files

[`bin/secret-shim`](../../bin/secret-shim) wraps commands that read
configuration from the environment. `bin/` holds one symlink per command and
comes first in `PATH` ([`config.zsh`](../config.zsh)), so every launch —
interactive shell or the tmux `prefix o` popup — goes through the shim,
which injects Keychain secrets and execs the real binary (resolved from
`PATH`, skipping itself, so e.g. the Claude Code self-updater in
`~/.local/bin` keeps working). The symlink name selects one of two modes:

| Mode    | Commands                                       | Injects                                                  |
| ------- | ---------------------------------------------- | -------------------------------------------------------- |
| tool    | `opencode`, `claude`, `codex`, `copilot` — and any name not listed below | `secret env -p global`, then `-p <command>` (tool wins) |
| project | `npm`, `pnpm`, `node`, `bun`, `bunx`, `yarn`, `npx`, `python`, `python3`, `uv` | `secret env` — the ambient project + repository scope of the CWD; nothing outside a git repository |

Effective precedence in both modes:

```
explicitly exported environment  >  .env files (project mode)  >  Keychain
```

Project mode never shadows an application's own dotenv loading: it collects
variable *names* (values are never read) from `.env`, `.env.local` and
`.env.{development,production,test}{,.local}` — in every directory from the
CWD up to the git toplevel plus the subtree below the CWD (`node_modules`
pruned, depth-limited) — and skips those names. Monorepo package files like
`apps/web/.env` are therefore respected when launching from the workspace
root; run inside `apps/api` for per-package precision. Templates
(`.env.example`, ...) are ignored. Nested launches (npm scripts calling npm)
skip re-injection via the `_SECRET_SHIM_PROJ` / `_SECRET_SHIM_TOOL`
sentinels.

```sh
secret set OPENAI_API_KEY -p global        # every AI tool
secret set CONTEXT7_API_KEY -p opencode    # one tool (overrides global)
secret set DATABASE_URL -S                 # this repo — `npm run dev` sees it
ln -s secret-shim ~/.config/bin/hermes     # wrap another tool
```

If the keychain cannot be unlocked, the shim starts the command without the
injection — it never blocks a launch. Test hooks: `SECRET_SHIM_MODE` forces
the mode, `SECRET_SHIM_BASE` replaces `global` as the tool-mode base.

## Import / export

| Format          | Metadata | Protection                                  |
| --------------- | -------- | ------------------------------------------- |
| `age` (default) | kept     | age passphrase encryption (`.json.age`)     |
| `json`          | kept     | plaintext JSON, `chmod 600`                 |
| `env`           | lost     | plaintext `export NAME='...'`, `chmod 600`  |

```sh
secret export -p global                  # -> secret-export-global-YYYYMMDD.json.age
secret export --all --format env -o dev.env
secret import dev.env -p myproj          # format auto-detected; JSON items keep
secret import backup.json.age            # their own project/scope unless -p /
                                         # -S / --scope override them
```

JSON exports record each item's scope, so layered setups restore exactly;
the env format flattens everything (scope and metadata are lost).

Keychain unlock passwords are **never** part of an export. Encrypted exports
are the recommended off-machine backup: they restore without the keychain
files or the master password.

### New machine / recovery

```sh
~/.config/install.sh --deps              # fzf, jq, age

# Option A — keychain files copied over from the old machine:
secret keychain register global          # repeat per copied keychain
secret keychain master set               # master password from the password manager

# Option B — from an encrypted export (keychains are recreated on the fly):
secret keychain master set
secret import secret-export-all-YYYYMMDD.json.age
```

## Security model

- Secret values never appear in process argv: writes are piped to
  `security -i` on stdin, interactive entry uses zsh `read -s`, reads use
  `find-generic-password -w`.
- Values are single-line; control characters are rejected.
- fzf — including preview — only ever sees names and metadata.
- Clipboard copies clear after 45 s unless something else was copied since.
- Known limitation: items created by `secret` are readable via
  `/usr/bin/security` without a GUI prompt **while their keychain is
  unlocked**. That is what makes a CLI workflow possible, and it means
  malware running as the logged-in user is outside the threat model (true
  for every keychain CLI). At-rest protection comes from the keychain
  encryption (master password) plus FileVault.

## Tests

[`zsh/tests/secret-selftest.zsh`](../tests/secret-selftest.zsh) — 142
assertions: round-trips (special characters, json/env/age), partial updates,
keychain auto-creation, `secret link` / the `git config secret.project`
mapping, scope layering (DWIM reads, env overlay, isolation between repos),
the unregistered-file write gate, master adoption/rotation, auto-unlock. It
only uses throwaway `secret-selftest*` projects/keychains, isolates the
master machinery via the `SECRET_MASTER_ACCOUNT` / `SECRET_TEST_ONLY_KC`
hooks, and cleans up after itself — safe to run on a machine with real data.

[`zsh/tests/secret-shim-selftest.zsh`](../tests/secret-shim-selftest.zsh) —
23 assertions for the launcher shims: layer injection and override order,
inherited-environment precedence, dotenv name skipping (monorepo union from
the root vs per-package precision, `.env.example` exclusion, `export NAME=`
lines), sentinels, exec passthrough (arguments, exit codes, missing
binaries). Same isolation and cleanup guarantees.

```sh
zsh -f ~/.config/zsh/tests/secret-selftest.zsh
zsh -f ~/.config/zsh/tests/secret-shim-selftest.zsh
```
