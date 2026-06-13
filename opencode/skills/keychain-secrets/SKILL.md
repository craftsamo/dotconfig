---
name: keychain-secrets
description: Use when handling secrets, API keys, tokens, credentials, environment variables, .env files, or "missing"/unset env vars on this machine — secrets are injected from the macOS Keychain via ~/.config/bin PATH shims. Covers tool vs project injection modes and the command allowlist, why injected values are invisible to the parent shell, adding/listing/getting secrets with the `secret` CLI, wrapping new tools, name-collision pitfalls, and debugging missing injection.
---

# Keychain secrets on this machine

Development secrets live in the **macOS Keychain**, not in committed files. A
PATH-based shim injects them as environment variables when a command launches.
Authoritative docs: `~/.config/zsh/functions/secret.md`. Implementation:
`~/.config/bin/secret-shim` and `~/.config/zsh/functions/secret.zsh`.

## How injection works

`~/.config/zsh/env.zsh` puts `~/.config/bin` first on `PATH`. That directory holds
one symlink per wrapped command, all pointing at `secret-shim`. Every launch
therefore goes through the shim, which reads values via `secret env`
(`security find-generic-password`), exports them, then `exec`s the real binary
(resolved further down `PATH`, skipping the shim itself).

Two modes, chosen by the command name (`bin/secret-shim:44-49`):

| Mode    | Commands | Injects |
| ------- | -------- | ------- |
| tool    | `opencode`, `claude`, `codex`, `copilot`, and any unlisted name | `secret env -p global`, then `-p <command>` (tool layer overrides global) |
| project | `node npm pnpm bun bunx yarn npx python python3 uv docker docker-compose` | `secret env` for the current git repo's project + scope; **only inside a git repo** |

Precedence in both modes:
`exported env  >  .env files (project mode)  >  Keychain`.

## The critical subtlety: env vars, not shell-expandable values

Injection delivers variables **into the launched process's environment**. It does
**not** populate the parent shell. Consequences:

- ✅ `node app.js` reading `process.env.DATABASE_URL` — works.
- ✅ `python -c 'import os; print(os.environ["X"])'` — works.
- ❌ `some-cmd --token=$API_KEY` typed at the shell — the parent shell expands
  `$API_KEY` (empty here) before the command runs.
- ❌ A generated `deploy.sh` containing `curl -H "Authorization: Bearer $TOKEN"`
  run via `bash deploy.sh` — `bash` is not shimmed, and `$TOKEN` is expanded by a
  shell that does not have it.

Rule: reference secrets **by name, read at runtime inside an allowlisted program**.
Write programs that read `process.env` / `os.environ`. If you must use a shell
script, run its secret-dependent steps through an allowlisted launcher (a
`node`/`python` entry, or an `npm` script), not bare `bash`/`sh`.

## What OpenCode's own environment has

OpenCode launches via the tool-mode shim, so its process env contains the
**global + opencode** layers only (e.g. `MCP_GITHUB_TOKEN`, `TAVILY_API_KEY`) —
**never** project secrets. You cannot read a project secret's value directly; it
materializes only inside an allowlisted child process. Do not echo, log, or commit
the global-layer values you can see.

## Non-allowlisted launchers

`cargo`, `go`, `make`, `pytest`, `ruby`, `rails`, `php`, `deno`, `dotnet`,
`bundle`, `psql`, bare scripts, and compiled binaries receive **no** project
injection. Options:

- **Inject for one command** by loading the repo's secrets into a subshell, then
  running the launcher there:

  ```sh
  ( eval "$(secret env)" && pytest )
  ```

  `secret env` (no `-p`) resolves the current repo's project + scope; the subshell
  `( … )` keeps the values out of later commands. This works for any launcher
  (`bash`, `sh`, `cargo`, `make`, …) and prompts once (`secret env` is `ask`).
- Invoke the work through an allowlisted command (e.g. `npm run <script>`, whose
  child process inherits the injected env).
- Permanently wrap the tool (see below).

## Using the `secret` CLI from here

`secret` is available **directly** via the `~/.config/bin/secret` launcher (it
loads the function for non-interactive shells; it is *not* a secret-shim symlink
and injects nothing):

```sh
secret ls                 # names + metadata (no values)
secret show NAME          # one item's metadata (no value)
secret projects           # project names
```

OpenCode's permission rules mirror the safety model: `ls`/`show`/`projects`/
`help` and `keychain ls`/`keychain master status` run without approval;
`get`/`env`/`set` prompt; `rm`/`del`/`export`/`import` and `keychain
rm`/`master set|rotate|forget|reveal` are **blocked**. Need a value injected for
a command? Use the `( eval "$(secret env)" && … )` idiom above, not `secret get`.

Adding a secret writes to the Keychain. Prefer asking the **user** to run
`secret set NAME -p <project>` (or `-S` for a repo-specific scope) interactively —
that keeps the value out of argv and the transcript. `.env` files are gitignored;
project mode reads only their variable **names** (to avoid shadowing the app's own
loader), never their values.

## Wrapping a new tool

```sh
ln -s secret-shim ~/.config/bin/<command>     # route it through the shim
```

If it should receive **project** (repo) secrets rather than the tool layers, also
add its name to the `project` case in `~/.config/bin/secret-shim:46`.

## Name-collision pitfall under OpenCode

Project mode never overrides a name already exported (`secret-shim:60`, the `_had`
set). Because OpenCode already exports the global-layer names, a project secret
**with the same name as a global one** is skipped in OpenCode-launched children —
the global value wins (this differs from a human running the command in a fresh
shell). Use distinct names, or run the command outside OpenCode, when a per-repo
override must take effect.

## Debugging missing injection

1. `which -a <cmd>` — does it resolve to `~/.config/bin/<cmd>` (the shim) first?
2. Is `~/.config/bin` first on `PATH`? (`print -l -- $path | head`)
3. Project mode: are you inside a git repo, and is the command on the allowlist?
4. Keychain unlocked? `secret keychain master status`.
5. Does the value exist? `secret env -p <project>` lists it (prompts; `ask`).
6. Name already in env (collision skip) or present as a `.env` name (dotenv skip)?

## References

- `~/.config/zsh/functions/secret.md` — full CLI + mechanism reference
- `~/.config/bin/secret-shim` — the injector
- `~/.config/zsh/tests/secret-shim-selftest.zsh`, `secret-selftest.zsh` — behavior specs
