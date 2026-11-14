# Cloudflare tools

Cloudflare for the Assistant, Researcher and Marketer: the zones, DNS records,
zone settings, rules, analytics, Workers and Pages, R2, KV and D1, tunnels,
Email Routing, Queues, Hyperdrive, Vectorize, Turnstile, Zero Trust Access
applications and registered domains of the user's own Cloudflare accounts,
through API tokens the user creates. Every profile with the tools reads; the
Assistant alone also changes things, each change after the user answers the
approval card. It runs on the third-party package
[craft-agent/cloudflare-tools](https://github.com/craft-agent/cloudflare-tools),
the same release the person's OpenCode loads, and a dotconfig guard adds what
this setup requires of every access plugin. Why the package and not a plugin
of our own, and what was given up for it:
[decision](decisions/cloudflare-tools-plugin.md). Common rules:
[access-common.md](access-common.md). Part of the Hermes design docs — index:
[`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                       | Home                                                                                                   | Reader                          |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------- |
| Tools, approval card, skills                                                | the package, installed at `~/.hermes/plugins/cloudflare-tools`                                         | Assistant, Researcher, Marketer |
| The pinned release                                                          | `scripts/external-plugins.json`, installed by `scripts/external-plugins.py`                            | people                          |
| Refusal where no person can answer or for A2A, bypass guard, progress lines | `plugins/guards/cloudflare-tools-guard`                                                                | Assistant, Researcher, Marketer |
| The tokens in the gateway's environment                                     | `launchd/bin/hermes-gateway-multiplex`, from the Keychain                                              | the gateway                     |
| Settings (toolsets, read-only, card language)                               | `plugins.entries.cloudflare-tools.settings` in each profile's config                                   | the three profiles              |
| How the tools are used                                                      | the package's skills, `cloudflare-tools:<toolset>`                                                     | the three profiles              |
| OpenCode                                                                    | `opencode/opencode.jsonc` (the npm package), denied in Hermes-driven runs ([opencode.md](opencode.md)) | OpenCode                        |

One implementation serves both harnesses: the Hermes plugin spawns Node on the
package's built `dist/cli.js`, which calls Cloudflare's API itself, through a
route allowlist, never following a redirect and masking anything shaped like a
credential. Building and deploying code stays with each project's own tooling
(Wrangler, Git); the tools read Workers and Pages and roll them back.

## Profiles and toolsets

| Profile    | Settings          | Inbound A2A |
| ---------- | ----------------- | ----------- |
| Assistant  | reads and writes  | none        |
| Researcher | `read_only: true` | reads       |
| Marketer   | `read_only: true` | reads       |

Every profile has every toolset but `grants`: `account`, `zones`, `dns`,
`rules`, `analytics`, `workers`, `pages`, `storage`, `tunnels`, `email`,
`queues`, `hyperdrive`, `vectorize`, `turnstile`, `access` and `registrar`.
`read_only` registers no write tool and no write procedure, so Researcher and
Marketer never see one. The Assistant's toolsets are in its `cli`, `telegram`
and `discord` lists, never `a2a`; Researcher's and Marketer's are in `cli` and
`a2a`. OpenCode loads the same toolsets; the plan, design, review and debug
agents keep the reads only.

`require_plugins` names `cloudflare-tools-guard`: while Hermes has not loaded
the guard, the package refuses every write before it is approved, so a guard
that fails to load stops the writes rather than leaving them unguarded. The
profile validator refuses a config that enables the package without the guard
or without naming it there.

Keep every `CLOUDFLARE_TOOLS_*` environment variable unset: the Hermes adapter
emits no flag for a `false` or empty setting, so a variable would override the
config rather than being cancelled by it.

## Tokens

The package reads its tokens from the environment only, and its Hermes plugin
hands its command line a copy of the gateway's process environment, never the
calling profile's secret scope. So the tokens sit in the gateway's process
environment: `launchd/bin/hermes-gateway-multiplex` adds the
`CLOUDFLARE_API_TOKEN[_<LABEL>]` and `CLOUDFLARE_ACCOUNT_ID[_<LABEL>]` items of
the `hermes` project's `cloudflare-tools` scope, and nothing else that call
emits. It first drops a `CLOUDFLARE_API_TOKEN` the `global` layer brings
without its account id, which would make every call that names no account
fail; a project's own Wrangler signs in with its own login.

A label (`work`, `personal`) names one account; its pair is
`CLOUDFLARE_API_TOKEN_<LABEL>` and `CLOUDFLARE_ACCOUNT_ID_<LABEL>`, the label in
capitals. A call picks the label with `account`; left out, it takes the
unlabeled pair, or the only label. The labels and accounts behind them are
private: they stay in the Keychain.

What that exposes, accepted in the [decision](decisions/cloudflare-tools-plugin.md):

- **Every profile the gateway serves holds the tokens**, and the terminal tool
  passes them to its commands, since Hermes strips only the variables it knows.
  The guard stops the obvious ways to read them in the three profiles that use
  the tools (below); other profiles have no guard for them. `execute_code` and
  MCP servers do not receive them.
- **A CLI session has none.** `hermes -p <profile>` from a shell gets the
  `global` and `hermes` layers, not this scope, so the tools there answer that
  no token is set.
- **Changing a token needs a gateway restart.**

## Approval

Every write is held by the package's own `pre_tool_call` card, drawn from
what the call will do and fitted to the surface the turn runs on. What the
card showed is pinned into the call. An "always" or "session" answer covers
the tool and the targets the card named (a zone, a record, a Worker), not the
exact request, and the package does so for every write, the administrative
ones included (deletes, a weakened setting, a purge of a whole zone, DNSSEC
off, rollbacks, tunnel routes): answer those "once". Only a call whose
targets the package cannot tell gets a key no later call repeats. There are
no zone mandates and no grants: a write needs a person who can answer the
card.

The guard (`cloudflare-tools-guard`) adds, for every `cloudflare_*` tool:

- **No card where no person can answer.** Every tool not explicitly named as
  a read is refused under YOLO, `approvals.mode: off`, cron, a single query
  and the unattended platforms (`plugins/_shared/human_gate.py`). A tool the
  package adds later is held too. A block from any plugin beats an approve,
  so the package's card is never drawn there.
- **Reads only for inbound A2A.** Every write is refused for an inbound A2A
  request; the reads stay open, since Researcher and Marketer answer peers.
- **No way around the tools.** Terminal and file-tool calls are blocked when
  they run `wrangler`, `cloudflared`, `flarectl` or the package's CLI, call the
  API by hand or import a Cloudflare SDK, name a token's shape or variable,
  read or change a Keychain item of the `hermes` project, or name the
  package's install, its state or the CLIs' logins (`~/.wrangler/config`,
  `~/.cloudflared`); paths are also matched by their real path, and a terminal
  call by the directory it runs in. In a project, its own wrangler still runs
  through its package manager ([project
  tooling](access-common.md#bypass-guard-ways-around-the-tool)).
- **No printing the environment.** `env`, `printenv`, `export -p`, a bare
  `set`, `declare -p`, `compgen -e`, `${!…}`, `ps` with the environment,
  `os.environ`, `process.env`, Perl's `%ENV`, Ruby's `ENV` taken whole,
  `jq env`, `/proc/*/environ` and `launchctl getenv` are refused where a
  command runs them; `env FOO=1 cmd` and mentions that run nothing pass. A
  best-effort list and a pattern match, not a sandbox: a script file's
  contents are never seen.
- **Progress lines** that name the operation only, never a zone, a record or
  a path.

## Install and update

`scripts/external-plugins.py install` (from the live checkout) runs
`hermes plugins install craft-agent/cloudflare-tools --ref <commit> --force
--no-deps --no-enable` for the commit `external-plugins.json` pins; `status`
compares the installed commit with the pin. `--force` accepts the security
scan's caution (the tunnel tools name a permission the scan rates as a
tunneling service). Never install it by hand at another commit or link it
from a checkout.

A new release: change `version` and `commit` in `external-plugins.json` and
the npm version in `opencode.jsonc` together, run
`scripts/external-plugins.py install`, restart the gateway and
`opencode service restart`.

## Setup

1. In the Cloudflare dashboard, create an API token (My Profile → API Tokens,
   or Manage Account → API Tokens for an account-owned one) limited to the
   account and zones the profiles should see, with the Read permission of
   each toolset (the package's README lists them) and, for the Assistant's
   changes, the Edit permission of each change it should make. A Global API
   Key is refused. The dashboard shows a token once: store it straight away.
2. Store the pair per label in the `hermes` project, scope `cloudflare-tools`,
   without a stage and without `--no-env` (the launcher reads it through
   `secret env`):
   `secret set CLOUDFLARE_API_TOKEN_<LABEL> -p hermes --scope cloudflare-tools --no-stage -D TOKEN`
   (paste the token at the hidden prompt) and
   `secret set CLOUDFLARE_ACCOUNT_ID_<LABEL> -p hermes --scope cloudflare-tools --no-stage`
   with the 32-character account id from the account's home page.
3. Install the plugin (above) and its Node runtime.
4. Enable `cloudflare-tools` and `cloudflare-tools-guard` in the private
   `plugins.enabled` of the three profiles, with the `cloudflare-tools-*`
   toolsets in `toolsets` and the platform lists above.
5. Restart the gateway (`launchd/gateway-launchctl.sh restart`);
   `cloudflare_account_read` with `method: list` shows each label, and `view`
   confirms Cloudflare takes its token.

OpenCode reads the same variables from its own environment, which its shim
fills from the `global` and `opencode` projects: store the pairs in the
`opencode` project the same way (no scope), then `opencode service restart`.
An unlabeled `CLOUDFLARE_API_TOKEN` in `global` without its account id makes
every call there that names no `account` fail; name the label, or store
`CLOUDFLARE_ACCOUNT_ID` beside it.
