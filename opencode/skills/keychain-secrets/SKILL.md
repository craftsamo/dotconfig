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

The mode is chosen by the command name in `bin/secret-shim:44-49`.

| Mode | Commands | Injects |
| --- | --- | --- |
| tool | `opencode`, `claude`, `codex`, `copilot`, and any unlisted name | `secret env -p global`, then `-p <command>`; tool layer overrides global |
| project | `node npm pnpm bun bunx yarn npx python python3 uv docker docker-compose` | `secret env` for the current git repo's project + scope; only inside a git repo |

Precedence in both modes:
`exported env > .env files (project mode) > Keychain`.

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

<OpenCodeEnvironment>

OpenCode launches via the tool-mode shim, so its process environment contains
the global + opencode layers only, for example `MCP_GITHUB_TOKEN` or
`TAVILY_API_KEY`. It never contains project secrets. Project secret values
materialize only inside an allowlisted child process. Do not echo, log, or
commit any global-layer values visible to OpenCode.

</OpenCodeEnvironment>

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
   subshell keeps the values out of later commands. This works for any launcher
   and prompts once because `secret env` is `ask`.
2. Invoke the work through an allowlisted command, for example `npm run <script>`.
3. Permanently wrap the tool.

</NonAllowlistedLaunchers>

<SecretCli>

`secret` is available directly via the `~/.config/bin/secret` launcher. It loads
the function for non-interactive shells; it is not a `secret-shim` symlink and
injects nothing.

```sh
secret ls                 # names + metadata, no values
secret show NAME          # one item's metadata, no value
secret projects           # project names
```

OpenCode permission rules mirror the safety model: `ls`, `show`, `projects`,
`help`, `keychain ls`, and `keychain master status` run without approval;
`get`, `env`, and `set` prompt; `rm`, `del`, `export`, `import`, and `keychain
rm` / `master set|rotate|forget|reveal` are blocked.

Need a value injected for a command? Use `( eval "$(secret env)" && ... )`, not
`secret get`.

Adding a secret writes to the Keychain. Prefer asking the user to run
`secret set NAME -p <project>` or `secret set NAME -S <scope>` interactively;
that keeps the value out of argv and the transcript. `.env` files are
gitignored. Project mode reads only their variable names to avoid shadowing the
app's own loader, never their values.

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
`_had` set). Because OpenCode already exports global-layer names, a project
secret with the same name as a global one is skipped in OpenCode-launched
children, and the global value wins. This differs from a human running the
command in a fresh shell. Use distinct names, or run the command outside
OpenCode when a per-repo override must take effect.

</NameCollisionPitfall>

<Debugging>

1. `which -a <cmd>`: does it resolve to `~/.config/bin/<cmd>` first?
2. Is `~/.config/bin` first on `PATH`? Use `print -l -- $path | head` in an
   interactive zsh.
3. Project mode: are you inside a git repo, and is the command allowlisted?
4. Is the Keychain unlocked? `secret keychain master status`.
5. Does the value exist? `secret env -p <project>` lists it and prompts.
6. Is the name already in env, causing a collision skip, or present as a `.env`
   name, causing dotenv skip?

</Debugging>

<References>

- `~/.config/zsh/functions/secret.md`: full CLI and mechanism reference
- `~/.config/bin/secret-shim`: injector implementation
- `~/.config/zsh/tests/secret-shim-selftest.zsh` and `secret-selftest.zsh`:
  behavior specs

</References>
