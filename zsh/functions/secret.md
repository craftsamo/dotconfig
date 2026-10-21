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
secret set STRIPE_KEY -j "prod key, rotate in dashboard" -D "API KEY"
secret get STRIPE_KEY           # value on stdout   (-c: clipboard, auto-clears in 45 s)
secret get api/STRIPE_KEY@prod  # the token `ls` prints names one exact layer
secret ls --long                # grouped by layer: kind, env, modified, meta, comment (fits the terminal; --wide)
secret ls --all --long          # every project
secret ls --json                # for programs: a JSON array, no values (never parse --long)
eval "$(secret env -p global)"  # inject a whole project as environment variables
```

The wizard's item pickers show every item with a preview pane of its
metadata (`secret show`), and match what you type against the name, the
meta fields and the comment, so a dashboard URL or an account finds its
key. **List** keeps that picker open as a browser: `^y` copies the item's
value, `^f` copies one meta field or the comment (plain, no auto-clear —
metadata is not secret), `^o` opens its `url=` field in the browser, `^e`
opens the update dialogue, `^d` deletes it (after a confirmation), and
each returns to the list; `enter` prints the item's details and leaves,
`esc` leaves — a look at a secret flows straight into the next step.

Project resolution: `-p NAME` > `git config secret.project` > the git
repository name > `global`. Run `secret link NAME` once per clone of a
multi-repo product so they all share one project (`secret link` alone
shows how the current directory resolves, `--unset` removes the mapping).

## Data model

One keychain item per secret — fully visible and editable in Keychain Access:

| Attribute | Value                                                                                                                      |
| --------- | -------------------------------------------------------------------------------------------------------------------------- |
| service   | `secret.<project>[/<scope>][@<stage>]` — shared, scoped, and per-stage layers; lookup key together with account            |
| account   | the variable name (`TAVILY_API_KEY`) — **unique key, do not repurpose**                                                    |
| label     | `[<scope>/]NAME[@<stage>]` inside the project's own keychain, prefixed with `<project>/` elsewhere                         |
| kind      | short type label (`-D`), upper-cased on write; default `ENV` (`API KEY`, `TOKEN`, `SECRET`, ...)                           |
| comment   | free-form description (`-j`), shown by `show` / `ls --long` / the GUI                                                      |
| type      | four-character code holding the ENV setting: `envn` = never emitted by `secret env` (`--no-env`), `envy` / unset = emitted |
| generic   | structured metadata: `;`-separated `KEY=VALUE` fields (`--meta`, see below), sorted by key                                 |

### Keeping an item out of every environment (`--no-env`)

Every item is emitted by `secret env` — and so injected by the launcher
shims below and by any helper built on `secret env` — unless it is stored
with `--no-env`. Such an item is read only by `get` (and carried by
export/import); use it for what no process environment may hold, such as a
wallet's seed phrase. `ls --long` and `show` display the setting (`ENV`
column, `Env:` line).

```sh
secret set HERMES_MAIN -p work -D mnemonic --no-env   # new item, never injected
secret update OLD_SEED -p work --no-env               # an existing item
secret update OLD_SEED -p work --env                  # injected again
```

Rewriting the value (`set` without `--env`/`--no-env`, `update --value`)
keeps the setting, so a later write never re-enables injection by accident.
The setting is the item's type attribute (`envn` / `envy`); a type can be
rewritten but never cleared, hence the explicit `envy`. Items written before
the type code kept `env=no` in the generic attribute — still honoured when no
type is set — and `secret migrate [-p proj|--all] [--dry-run]` moves it into
the type so the generic attribute holds nothing but metadata fields.

`set --new` is create-only: an item of that name already in the layer is
refused rather than overwritten, by a check first and by `security` itself
(the write leaves out `-U`), so a program that makes a secret — Hermes'
new wallets — can never replace one that holds something.
In `secret env`, a `--no-env` item in the winning layer hides the name
entirely: the shared value is not emitted in its place.

### Structured metadata (`--meta`)

`--meta KEY=VALUE` attaches structured fields to an item — where a key was
issued, which account it belongs to, what a mnemonic is for — as many as
needed, on `set` and `update`; `update --meta KEY=` removes one. Keys are
identifiers (letters, digits, `_`, `-`; `env` is reserved), values are
single-line and may not contain `;`. They live in the generic attribute as
`KEY=VALUE;KEY=VALUE`, sorted by key, and are visible in Keychain Access.
Free-form notes stay in the comment (`-j`).

```sh
secret set STRIPE_KEY -p shop -D 'api key' --meta url=https://dashboard.stripe.com --meta account=ops@example.com
secret set WALLET_SEED -p wallet -D mnemonic --no-env --meta purpose=cold-storage --meta chain=eth
secret update STRIPE_KEY -p shop --meta url= --meta rotated=2026-10-20   # drop url, add rotated
secret show STRIPE_KEY -p shop         # Meta: lines
secret ls -p shop --long               # META column
secret ls -p shop --meta account       # items with that field
secret ls --meta chain=eth --meta purpose   # every filter must match
```

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
cd ~/Workspaces/Projects/ExampleProject/github/learning-app   # linked to example-project
secret set GOOGLE_CLOUD_PROJECT_ID          # shared: visible to every repo
secret set DATABASE_URL -S                  # scoped: learning-app only
secret get DATABASE_URL                     # scoped first, falls back to shared
eval "$(secret env)"                        # shared + this repo's scope (scoped wins)
```

The same `secret set DATABASE_URL -S` in `courses` lands in its own scope —
no collision. Reads/updates/deletes are DWIM (repo scope first, then
shared); `--shared`, `--scope X` and `-S` pin a specific layer. `ls` shows
scoped items as `scope/NAME` — `--long` groups them under a `scope/`
heading — and so does Keychain Access via the label.

`secret ls --long` prints one block per project — the project, a column
header, then one group per layer (`shared`, `scope/`, `@stage`,
`scope/ @stage`) — with NAME, KIND, ENV, MODIFIED, META and COMMENT per
row (the last two headed only when the project has any). The rows are sized to the terminal
(`COLUMNS`, else the terminal width; unbounded when piped): META and COMMENT
share what is left and are cut with an ellipsis, so a row never wraps;
`--wide` never cuts. On a terminal without `NO_COLOR`, the project is bold,
stage groups magenta and `ENV no` yellow. `--all` spans every registered
keychain, one block per project (the short form prefixes its tokens with
the project).

The table is for people and changes with them; a program reads
`secret ls --json` instead — a JSON array with one object per item and the
fields of `export --format json` (`project`, `scope`, `stage`, `name`,
`kind`, `comment`, `env`, `meta`, `modified`), never a value. It needs
nothing but zsh, so it works under a bare `PATH=/usr/bin:/bin`; nothing to
list prints `[]`. The web3 wallet finds its seed phrases and keys this way,
and the self-test runs the wallet's parser on the real output.

### Stages — per-environment overrides

A **stage** (`prod`, `test`, `staging`, ...) is a second layer on top of
scopes, for the same name holding a different value per environment. The
stage every command works in is `--stage S`, else `$SECRET_STAGE`, else
none; `--no-stage` forces the stage-less layers whatever the shell says.

```sh
secret set DATABASE_URL -S                       # the repo's dev value (no stage)
secret set DATABASE_URL -S --stage prod          # the same name, prod only
secret set DATABASE_URL -S --stage test
secret set LOG_LEVEL                             # environment-neutral: stored once
secret env                                       # DATABASE_URL = dev, LOG_LEVEL
secret env --stage prod                          # DATABASE_URL = prod, LOG_LEVEL
SECRET_STAGE=test npm test                       # through the shim
secret ls --long                                 # @stage groups; ls prints [scope/]NAME[@stage]
secret ls --stage prod                           # that stage's layers only
```

`secret env` overlays the layers least to most specific — shared < scoped
< shared@stage < scoped@stage — so a stage layer always beats a stage-less
one (asking for prod never hands out a repository's dev value), names the
stage does not hold fall back to the stage-less layers, and other stages are
never emitted. **With no stage nothing staged is emitted**: a prod value only
leaves the keychain when asked for by name. Reads are DWIM in the same
order; the exact flags (`-S`, `--scope X`, `--shared`) combined with
`--stage S` / `--no-stage` address exactly one layer (`secret rm
DATABASE_URL -S --stage prod` deletes only that item). Stage names are
letters, digits, `_` and `-`; project and scope names may not contain `@`.
The service is `secret.<project>[/<scope>]@<stage>` and the label
`[<scope>/]NAME@<stage>`, both visible in Keychain Access.

### Master password

All custom keychains share one password, kept in a password manager. A copy
lives in the login keychain so everything unlocks silently. One `secret`
invocation looks the password up and unlocks each keychain it touches once
(`env` and `export` read every value on that one unlock), so a tool
launched through the shim waits about half a second for twenty secrets:

```
macOS login password
  └─ login.keychain-db ── keychain-password/master (one item)
       ├─ global.keychain-db        (the "global" project)
       └─ <project>.keychain-db ... (auto-created on first write, no prompt)
```

| Command                              | Purpose                                                     |
| ------------------------------------ | ----------------------------------------------------------- |
| `secret keychain master set`         | define it and rotate every registered custom keychain to it |
| `secret keychain master rotate`      | change it everywhere at once                                |
| `secret keychain master status`      | unlock source (`master`/`individual`/`none`) + lock state   |
| `secret keychain master reveal [-c]` | show / copy it (for the password manager)                   |
| `secret keychain master forget`      | remove the login copy (access starts prompting)             |
| `secret keychain create NAME`        | new keychain — no password prompt once a master is set      |
| `secret keychain register NAME`      | add a copied `.keychain-db` to the search list              |
| `secret keychain remember NAME`      | per-keychain password override (takes precedence)           |
| `secret keychain ls`                 | inventory and lifecycle                                     |
| `secret keychain info`               | inventory and lifecycle                                     |
| `secret keychain lock`               | inventory and lifecycle                                     |
| `secret keychain unlock`             | inventory and lifecycle                                     |
| `secret keychain rm`                 | inventory and lifecycle                                     |

## Launcher shims — env injection without .env files

[`bin/secret-shim`](../../bin/secret-shim) wraps commands that read
configuration from the environment. `bin/` holds one symlink per command and
comes first in `PATH` ([`config.zsh`](../config.zsh)), so every launch —
interactive shell or the tmux `prefix o` popup — goes through the shim,
which injects Keychain secrets and execs the real binary (resolved from
`PATH`, skipping itself, so e.g. the Claude Code self-updater in
`~/.local/bin` keeps working). The symlink name selects one of three modes:

| Mode    | Commands                                                                                                   | Injects                                                                                                                                                  |
| ------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| tool    | `opencode`, `claude`, `codex`, `copilot`, `grok` — and any name not listed below                           | the shared, stage-less layers of `global`, then `<command>` (tool wins); never a repository scope or a stage                                             |
| project | `npm`, `pnpm`, `node`, `bun`, `bunx`, `yarn`, `npx`, `python`, `python3`, `uv`, `docker`, `docker-compose` | `secret env` — the ambient project + repository scope of the CWD, in the stage `$SECRET_STAGE` names (none by default); nothing outside a git repository |
| plain   | `pip`, `pip3`                                                                                              | nothing — wrapped only for the mise pin below                                                                                                            |

Both injecting modes go through `secret env`, so items stored `--no-env`
never reach a wrapped command.

Every mode also pins mise's directories (`MISE_DATA_DIR`, `MISE_CONFIG_DIR`,
`MISE_STATE_DIR`, `MISE_CACHE_DIR`) to the account's home from the user
database, not `$HOME`, keeping inherited values — the same paths
[`env.zsh`](../env.zsh) exports. A caller that swaps `HOME` for a temp dir
and forwards little more than `PATH` (test harnesses that rebuild the child
environment from an allowlist) still lands on these launchers first; without
the pin, the mise shim behind them would see no installed tool and resolve,
and install, every `latest` tool from the network on each call.

Effective precedence in both modes:

```
explicitly exported environment  >  .env files (project mode)  >  Keychain
```

Project mode never shadows an application's own dotenv loading: it collects
variable _names_ (values are never read) from `.env`, `.env.local` and
`.env.{development,production,test}{,.local}` — in every directory from the
CWD up to the git toplevel plus the subtree below the CWD (`node_modules`
pruned, depth-limited) — and skips those names. Monorepo package files like
`apps/web/.env` are therefore respected when launching from the workspace
root; run inside `apps/api` for per-package precision. Templates
(`.env.example`, ...) are ignored. Nested launches (npm scripts calling npm)
skip re-injection via the `_SECRET_SHIM_PROJ` (`project@stage`) /
`_SECRET_SHIM_TOOL` sentinels. A nested project launch in another stage (or
project) first retracts what the outer shim injected — the names travel in
`_SECRET_SHIM_NAMES` — then injects the new layers, so the environment holds
one stage's values and never a mix (a prod-only name disappears when the
stage is dropped, a dev value is replaced when prod is entered); it says so
on stderr (`secret-shim: stage <project>@ -> <project>@prod (N injected)`;
`0 injected` means the keychain gave nothing, so the child has no secrets
of either stage).
Values the user exported by hand are not in that list and keep winning, as
the inherited-environment rule above says. A project launch under
`SECRET_STAGE=prod` (or `production`) announces itself on stderr
(`secret-shim: stage=prod (<project>)`), so a shell left in prod is noticed.

OpenCode clients run in tool mode. OpenCode 2's shared background service is
spawned by the first client and inherits its environment, so it sees the same
Keychain secrets; restart it (`opencode service restart`) after changing one.
The service keeps its own generated password.

```sh
secret set OPENAI_API_KEY -p global        # every AI tool
secret set CONTEXT7_API_KEY -p opencode    # one tool (overrides global)
secret set DATABASE_URL -S                 # this repo — `npm run dev` sees it
secret set DATABASE_URL -S --stage prod    # `SECRET_STAGE=prod npm run migrate` sees this one
ln -s secret-shim ~/.config/bin/hermes     # wrap another tool
```

Containers: `docker` / `docker compose` run through the shim too. Declare
names **without values** under `environment:` and make `env_file` optional —
Compose then prefers the `env_file` entry when the variable is absent from
the shell, and falls back to the injected (Keychain) value otherwise
(verified against Compose v5):

```yaml
env_file:
  - path: ./apps/api/.env
    required: false # works with or without the file
environment:
  - STRIPE_SECRET_KEY # value-less: shell (= injected) when set
```

If the keychain cannot be unlocked, the shim normally starts the command
without injection. `opencode serve` is the fail-closed exception: it exits
unless `OPENCODE_PASSWORD` or `OPENCODE_SERVER_PASSWORD` was inherited or
injected. Test hooks:
`SECRET_SHIM_MODE` forces the mode, `SECRET_SHIM_BASE` replaces `global` as
the tool-mode base, `SECRET_SHIM_LIB` points at the `secret.zsh` to source
(a candidate checkout).

[`bin/secret`](../../bin/secret) is a launcher too, but **not** a shim: it is a
small wrapper that `source`s `secret.zsh` and dispatches, so the `secret` CLI is
also callable from non-interactive shells (scripts, `zsh -c`, opencode) where
`config.zsh` hasn't loaded the function. Interactive shells keep using the
function directly (a defined function outranks the `bin/secret` command on
`PATH`), so nothing changes there; the wrapper injects nothing.

## Import / export

| Format          | Metadata                             | Protection                                                                                                                                                                                                                                    |
| --------------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `age` (default) | kept                                 | age passphrase encryption (`.json.age`)                                                                                                                                                                                                       |
| `json`          | kept                                 | plaintext JSON, `chmod 600`                                                                                                                                                                                                                   |
| `env`           | kind/comment lost; ENV and meta kept | plaintext `export NAME='...'`, `chmod 600`; a `--no-env` item is written as `#no-env# export ...`, so sourcing the file never exports it, and an item's fields ride on a `#meta:K=V;...` comment line right above it — `import` restores both |

```sh
secret export -p global                  # -> secret-export-global-YYYYMMDD.json.age
secret export --all --format env -o dev.env
secret import dev.env -p myproj          # format auto-detected; JSON items keep
secret import backup.json.age            # their own project/scope unless -p /
                                         # -S / --scope override them
```

JSON exports record each item's scope, stage, `env` setting and `meta`
object, so layered setups restore exactly; the env format flattens
everything (scope, stage, kind and comment are lost — the stage is only
named in the section headers) except the `--no-env` and `#meta:` markers.
Importing an older export that has no `env` field / `meta` object leaves an
existing item's setting / fields as they are; a present `meta` replaces them.
`import --stage S` / `--no-stage` force every item into one stage; otherwise
JSON items keep their recorded stage and env files land in `$SECRET_STAGE`,
like any other write.

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

[`zsh/tests/secret-selftest.zsh`](../tests/secret-selftest.zsh) — 289
assertions: round-trips (special characters, json/env/age), partial updates,
`--no-env` (kept out of `env`, kept across rewrites and export/import, stored
as the `envn`/`envy` type code), `--meta` fields (validation, sorting,
`ls --meta` filters, export/import round-trips), `secret migrate` of the
legacy `env=no` marker, `set --new`, non-ASCII metadata read back as text,
keychain auto-creation, `secret link` / the `git config secret.project`
mapping, scope layering (DWIM reads, env overlay, isolation between repos),
stages (`--stage` / `$SECRET_STAGE` / `--no-stage`, the four-layer env
overlay, exact-layer rm, export/import round-trips, `ls` tokens), the
`ls` token accepted as NAME, the fzf picker's lines, preview and expect
mode (fzf stubbed), the grouped `ls --long` layout (groups, ordering,
fitting `COLUMNS`, `--wide`, `--all`), `ls --json` under a bare `PATH`
and the web3 wallet's parser on its real output,
the unregistered-file write gate, master adoption/rotation, auto-unlock
(one unlock per keychain per invocation, counted through a shadowed
`security`). It
only uses throwaway `secret-selftest*` projects/keychains, isolates the
master machinery via the `SECRET_MASTER_ACCOUNT` / `SECRET_TEST_ONLY_KC`
hooks, and cleans up after itself — safe to run on a machine with real data.

[`zsh/tests/secret-shim-selftest.zsh`](../tests/secret-shim-selftest.zsh) —
53 assertions for the launcher shims: layer injection and override order,
inherited-environment precedence, dotenv name skipping (monorepo union from
the root vs per-package precision, `.env.example` exclusion, `export NAME=`
lines), sentinels, stages (`SECRET_STAGE` in project mode, the stage-carrying
sentinel, the prod announcement, no stage in tool mode, the swap of a nested
launch in another stage: replaced, dropped and hand-exported values, the
recorded names, the stderr line), the mise pin under a
swapped `HOME` and plain mode, exec passthrough (arguments, exit codes,
missing binaries). Same isolation and cleanup guarantees. It tests the
`secret.zsh` beside the shim under test (`SECRET_SHIM_UNDER_TEST`).

```sh
zsh -f ~/.config/zsh/tests/secret-selftest.zsh
zsh -f ~/.config/zsh/tests/secret-shim-selftest.zsh
```
