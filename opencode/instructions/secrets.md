<SecretsPolicy>
<StorageModel>

Secrets on this machine are injected from the macOS Keychain by PATH shims
(`~/.config/bin/*` -> `secret-shim`), never from committed files.

</StorageModel>

<Rules>

- Never reveal secret values. The OpenCode process environment may already hold
  global/tool secrets such as `*_API_KEY`, `MCP_*`, `TAVILY_*`, or
  `OPENCODE_SERVER_PASSWORD`. Do not run `env`, `printenv`, or `echo $SECRET`,
  and never write a value into a file, log, or commit.
- Secrets arrive as environment variables inside the launched program, not as
  values the parent shell can expand. Reference them by name at runtime:
  `process.env.X`, `os.environ["X"]`, or `$X` inside the program. Passing
  `cmd --key=$X` from the shell, or baking `$X` into a script run with
  `bash`/`sh`, yields empty or leaked values.
- Project secrets auto-inject only into these commands, inside a git repo:
  `node npm pnpm bun bunx yarn npx python python3 uv docker docker-compose`.
  Other launchers (`cargo`, `go`, `make`, `pytest`, `ruby`, `php`, `deno`,
  `./script.sh`) get no project secrets. Route the work through an allowlisted
  command, or wrap the tool.
- Use the `secret` CLI directly for metadata, for example `secret ls` or
  `secret show NAME`. A launcher in `~/.config/bin` makes it callable here.
  Reads are auto-approved; `get`, `rm`, `export`, and `import` are blocked.
  Prefer storing new secrets in the Keychain (`secret set NAME -p <project>`, or
  `-S` for repo scope) over writing plaintext `.env` files.

</Rules>

<SkillEscalation>

For injection modes, debugging missing environment variables, and wrapping new
tools, load the `keychain-secrets` skill.

</SkillEscalation>
</SecretsPolicy>
