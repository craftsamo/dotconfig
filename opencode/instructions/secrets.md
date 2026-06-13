## Secrets & macOS Keychain

Secrets on this machine are injected from the macOS Keychain by PATH shims
(`~/.config/bin/*` -> `secret-shim`), never from committed files. Follow these rules:

- **Never reveal secret values.** Your own environment already holds global/tool
  secrets (e.g. `*_API_KEY`, `MCP_*`, `TAVILY_*`, `OPENCODE_SERVER_PASSWORD`). Do
  not run `env`/`printenv`/`echo $SECRET`, and never write a value into a file,
  log, or commit.
- **Secrets arrive as environment variables inside the launched program**, not as
  values your shell can expand. Reference them by name at runtime —
  `process.env.X`, `os.environ["X"]`, or `$X` *inside the program*. Passing
  `cmd --key=$X` from the shell, or baking `$X` into a script you run with
  `bash`/`sh`, yields empty or leaked values.
- **Project secrets auto-inject only into these commands, inside a git repo:**
  `node npm pnpm bun bunx yarn npx python python3 uv docker docker-compose`.
  Other launchers (`cargo`, `go`, `make`, `pytest`, `ruby`, `php`, `deno`,
  `./script.sh`) get **no** project secrets — route the work through an
  allowlisted command, or wrap the tool (see the skill).
- **Use the `secret` CLI directly** (e.g. `secret ls`, `secret show NAME`) — a
  launcher in `~/.config/bin` makes it callable here. Reads are auto-approved;
  `get`/`rm`/`export`/`import` are blocked. Prefer storing new secrets in the
  Keychain (`secret set NAME -p <project>`, or `-S` for repo scope) over writing
  plaintext `.env` files.

For injection modes, debugging missing env vars, and wrapping new tools, load the
**`keychain-secrets`** skill.
