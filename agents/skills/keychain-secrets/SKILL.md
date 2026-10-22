---
name: keychain-secrets
description: Use when handling secrets, API keys, tokens, credentials, environment variables, .env files, or "missing"/unset env vars on this machine — secrets are injected from the macOS Keychain via ~/.config/bin PATH shims. Covers tool vs project injection modes and the command allowlist, why injected values are invisible to the parent shell, adding/listing/getting secrets with the `secret` CLI, wrapping new tools, name-collision pitfalls, and debugging missing injection.
author: CraftSamo
license: MIT
---

<Goal>

Handle local development secrets safely. Secrets live in the macOS Keychain,
not in committed files, and are injected as environment variables by PATH-based
command shims when a process launches.

</Goal>

<Implementation>

Authoritative docs: `~/.config/zsh/functions/secret.md`.
Implementation: `~/.config/bin/secret-shim` and
`~/.config/zsh/functions/secret.zsh`.

`~/.config/zsh/env.zsh` puts `~/.config/bin` first on `PATH`. That directory
holds one symlink per wrapped command, all pointing at `secret-shim`. Every
launch goes through the shim, which reads values via `secret env`
(`security find-generic-password`), exports them, then `exec`s the real binary
resolved further down `PATH`, skipping the shim itself.

</Implementation>

<InjectionModes>

The mode is chosen by the command name in `bin/secret-shim:53-58`.

| Mode | Commands | Injects |
| --- | --- | --- |
| tool | `opencode`, `claude`, `codex`, `copilot`, `grok`, and any unlisted name | shared layers only: `global`, then `<command>`; tool layer overrides global; never a repository scope |
| project | `node npm pnpm bun bunx yarn npx python python3 uv docker docker-compose` | `secret env` for the current git repo's project + scope, in the stage `SECRET_STAGE` names (none by default); only inside a git repo |
| plain | `pip pip3` | nothing; wrapped only for the mise pin |

Precedence in the injecting modes:
`exported env > .env files (project mode) > Keychain`.

Stages: an item may exist once per environment (`secret set DATABASE_URL -S
--stage prod`). Project mode injects the stage named by `SECRET_STAGE` on top
of the stage-less layers (`SECRET_STAGE=test npm test`); with no stage,
nothing staged is injected, so a prod value never leaves the keychain unless
asked for by name. Tool mode never receives a stage: your own environment
holds stage-less values only. A nested launch in another stage swaps the
values the outer shim injected for the new stage's (never a mix of two
stages) and prints `secret-shim: stage <project>@ -> <project>@prod
(N injected)`; values you exported by hand are left alone. A launch with
`SECRET_STAGE=prod` prints `secret-shim: stage=prod (...)` on stderr; both
lines are expected, not errors. `production` and `development` are
spellings of `prod` and `dev` (one layer each); other stage names are stored
as typed, and `secret set --stage X` into a stage the project does not hold
yet prints `note: 'X' is a new stage ... (in use: ...)` — read it as a typo
check, not an error.

Every mode also exports `MISE_DATA_DIR`, `MISE_CONFIG_DIR`, `MISE_STATE_DIR`
and `MISE_CACHE_DIR`, pinned to the account's real home (inherited values
win), so a wrapped command launched under a swapped `HOME` still uses the
real mise installs. Seeing these in a child's environment is expected.

</InjectionModes>

<ShellExpansionRule>

Injection delivers variables into the launched process's environment. It does
not populate the parent shell.

- Works: `node app.js` reading `process.env.DATABASE_URL`.
- Works: `python -c 'import os; print(os.environ["X"])'`.
- Fails: `some-cmd --token=$API_KEY` typed at the shell, because the parent
  shell expands `$API_KEY` before the command runs.
- Fails: a generated `deploy.sh` containing `curl -H "Authorization: Bearer
  $TOKEN"` run via `bash deploy.sh`, because `bash` is not shimmed and `$TOKEN`
  is expanded by a shell without that variable.

Rule: reference secrets by name and read them at runtime inside an allowlisted
program. Write programs that read `process.env` or `os.environ`. If a shell
script is unavoidable, run its secret-dependent steps through an allowlisted
launcher such as a `node` or `python` entry, or an `npm` script, not bare
`bash`/`sh`.

</ShellExpansionRule>

<AgentProcessEnvironment>

Every AI CLI here (opencode, claude, codex, copilot, grok) launches through
the tool-mode shim, so your own process environment contains the global layer
plus your own tool layer only, for example `MCP_GITHUB_TOKEN` or
`TAVILY_API_KEY`. It never contains project secrets. Project secret values
materialize only inside an allowlisted child process. Do not echo, log, or
commit any global-layer value visible to you.

</AgentProcessEnvironment>

<NonAllowlistedLaunchers>

`cargo`, `go`, `make`, `pytest`, `ruby`, `rails`, `php`, `deno`, `dotnet`,
`bundle`, `psql`, bare scripts, and compiled binaries receive no project
injection.

Options:

1. Inject for one command by loading the repo's secrets into a subshell, then
   running the launcher there:

   ```sh
   ( eval "$(secret env)" && pytest )
   ```

   `secret env` with no `-p` resolves the current repo's project + scope. The
   subshell keeps the values out of later commands and out of the transcript.
   This works for any launcher. opencode denies a bare `secret env` (it would
   print values); confirm the subshell form with the user before running it.
2. Invoke the work through an allowlisted command, for example `npm run <script>`.
3. Permanently wrap the tool.

</NonAllowlistedLaunchers>

<SecretCli>

`secret` is available directly via the `~/.config/bin/secret` launcher. It loads
the function for non-interactive shells; it is not a `secret-shim` symlink and
injects nothing.

```sh
secret ls                 # one "[scope/]NAME[@stage]" token per item, no values
secret ls --long          # grouped by layer, with kind, env, meta and comment
secret ls --long --wide   # nothing cut to the terminal width (piped output never is)
secret ls --all           # every project, tokens prefixed with the project
secret ls --json          # for scripts: a JSON array of fields, no values (never parse --long)
secret show NAME          # one item's metadata, no value
secret show api/DB@prod   # a token from `ls` names that exact layer
secret projects           # project names
```

`ls` prints every layer of a project as a token, `[scope/]NAME[@stage]`, and
`show`, `get`, `update` and `rm` accept that token in place of a NAME: pass it
through as printed instead of translating it into `--scope` / `--stage` flags.
A bare NAME reads DWIM (the most specific layer that holds it). Running
`secret` with no arguments opens an fzf wizard that needs a terminal: never
start it from an agent; use the subcommands.

The safety model has three tiers: `ls`, `show`, `projects`, `help`, `keychain
ls`, and `keychain master status` are read-only and safe to run; `get`, `env`,
and `set` touch values and should be confirmed with the user first; `rm`,
`del`, `export`, `import`, and `keychain rm` / `master set|rotate|forget|
reveal` are destructive or exfiltrating — never run them unprompted. opencode
enforces these tiers as permission rules; other CLIs rely on you to honor
them.

Need a value injected for a command? Use `( eval "$(secret env)" && ... )`, not
`secret get`.

Adding a secret writes to the Keychain. Prefer asking the user to run
`secret set NAME -p <project>` (add `-S` for this repository's scope, or
`--scope NAME` for a named one) interactively;
that keeps the value out of argv and the transcript. `.env` files are
gitignored. Project mode reads only their variable names to avoid shadowing the
app's own loader, never their values.

An item stored with `--no-env` (`no` in the ENV column of `secret ls --long`, type code
`envn` in Keychain Access) is never emitted by `secret env`, so no shim or
helper injects it; only `get` reads it. That is deliberate — a wallet seed
phrase, say — so a "missing" variable that shows `ENV no` is not a bug to fix:
never lift it with `update --env` unless the user asks. `secret migrate` only
moves a pre-type `env=no` marker into the type code; it is a one-off the user
runs, not something to run unprompted.

Items may carry structured fields (`--meta KEY=VALUE`: `url=`, `account=`,
`purpose=`, `from=` and `index=` for a key derived from a mnemonic, `path=` for
a derivation path). `secret show NAME` lists them and `secret ls --meta
KEY[=VALUE]` filters by them — both read-only — so check there before asking
the user what a key is for or where it was issued. `update --meta KEY=VALUE`
sets one field and `--meta KEY=` removes one, leaving the others; it rewrites
the item, so confirm with the user like any `set`.

</SecretCli>

<WrappingTools>

```sh
ln -s secret-shim ~/.config/bin/<command>     # route it through the shim
```

If the tool should receive project/repo secrets instead of tool-layer secrets,
also add its name to the `project` case in `~/.config/bin/secret-shim:46`.

</WrappingTools>

<NameCollisionPitfall>

Project mode never overrides a name already exported (`secret-shim:60`, the
`_had` set). Because your own process already exports global-layer names, a
project secret with the same name as a global one is skipped in the children
you launch, and the global value wins. This differs from a human running the
command in a fresh shell. Use distinct names, or have the command run outside
the agent when a per-repo override must take effect.

</NameCollisionPitfall>

<Debugging>

1. `which -a <cmd>`: does it resolve to `~/.config/bin/<cmd>` first?
2. Is `~/.config/bin` first on `PATH`? Use `print -l -- $path | head` in an
   interactive zsh.
3. Project mode: are you inside a git repo, and is the command allowlisted?
4. Is the Keychain unlocked? `secret keychain master status`.
5. Does the value exist? `secret env -p <project>` lists it and prompts.
6. Is the name already in env, causing a collision skip, or present as a `.env`
   name, causing dotenv skip? Under `SECRET_STAGE=S` only `.env`, `.env.local`
   and `.env.S{,.local}` cause that skip (`prod` reads `.env.production`,
   `dev` `.env.development`);
   with no stage, every `.env.{development,production,test}{,.local}` does.
7. Is the value stored under a stage (an `@stage` group in `secret ls --long`, or
   `NAME@stage` in `secret ls`) while `SECRET_STAGE` is unset or names another
   stage? Staged values are injected only for their own stage.

</Debugging>

<References>

- `~/.config/zsh/functions/secret.md`: full CLI and mechanism reference
- `~/.config/bin/secret-shim`: injector implementation
- `~/.config/zsh/tests/secret-shim-selftest.zsh` and `secret-selftest.zsh`:
  behavior specs

</References>
