---
name: machine-env
description: >-
  Engineer's map of the machine itself — `~/.config` as the dotconfig git repo
  whose files are symlinked into every tool home (including `~/.hermes`), the
  Keychain-plus-PATH-shim secrets model that explains "missing" env vars, the
  split Anthropic accounts behind Hermes and OpenCode, and where the
  authoritative rules live (root and nested `AGENTS.md`). Load it when a task
  touches configuration or dotfiles, when a build behaves oddly around
  environment variables or credentials, or when orient must report the
  environment. Carries the self-modification guard: changes to Hermes' own
  runtime need a block round-trip regardless of Authority. Pointers to the real
  rules, never copies of them.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [environment, dotfiles, configuration, secrets, keychain, symlinks, accounts, self-modification]
    category: technic
    related_skills: [engineer-pipeline, opencode-env]
---

<Goal>

Understand the machine your work runs on: how configuration is stored and
linked, why environment variables appear and disappear, which credentials
belong to whom, and which edits can break the runtime that is executing you.

This skill is a **map with pointers**. The authoritative rules live in the
repo's own `AGENTS.md` files; copying them here would create two truths. Read
the pointer when you need the detail.

</Goal>

<Scope>
<UseWhen>

- The task touches `~/.config` or any dotfile/tool configuration.
- A build, test, or script behaves oddly around environment variables,
  credentials, or "missing" API keys.
- Orient tasks that must report the environment the work will run in.
- You are about to change anything that Hermes or OpenCode themselves read.

</UseWhen>

<DoNotUseWhen>

- You need OpenCode's capability surface specifically — the `opencode-env`
  skill.
- Ordinary work inside a project worktree with no configuration or credential
  dimension.

</DoNotUseWhen>
</Scope>

<Layout>

`~/.config` is a **git repository**, not a scratch directory. Real files live
there; tool homes hold only symlinks into it, created by `~/.config/install.sh`
(idempotent, and a drift detector — it refuses to overwrite a real file and
warns instead).

| Path | Role |
| --- | --- |
| `~/.config/AGENTS.md` | repo-wide rules, and the index of which subtrees have their own |
| `~/.config/<subtree>/AGENTS.md` | authoritative rules for that subtree — read before touching it |
| `~/.config/install.sh` | creates every symlink; run it after adding new files |
| `~/.config/bin/` | PATH shims that inject secrets into wrapped commands |
| `~/.config/agents/curated/` | repo-curated shared skills, linked per skill into the harness-neutral `~/.agents/skills` root (a machine-local real dir that installers also write into; `~/.claude/skills` bridges there) |
| `~/.hermes/`, `~/.claude/`, other tool homes | **symlinks back into this repo** — edit the repo, never these |

Consequence: editing `~/.hermes/config.yaml` and editing
`~/.config/hermes/config.yaml` are the same file, and a *new* file under the
repo is invisible to the tool until `install.sh` links it.

</Layout>

<Secrets>

Secrets are stored in the macOS Keychain and injected by the `~/.config/bin`
shims at launch. Nothing is in committed files, and nothing is in your shell.

Operationally that means:

- **Injected values never exist in the parent shell.** A variable can be
  present inside the program and absent to `echo`. Reference secrets by name
  *inside* the program (`process.env.X`, `os.environ["X"]`), never by
  interpolating them into a command line.
- **Injection is allowlisted per launcher.** Common package/runtime commands
  are wrapped; many others are not. A tool that "loses" its API key is usually
  an unwrapped launcher, not a missing secret — route the work through a
  wrapped command or wrap the tool.
- **Never print, log, commit, or pass secret values.** Do not run `env` /
  `printenv` to inspect them.
- Depth (injection modes, wrapping a new tool, debugging a missing variable)
  lives in the shared skill — read
  `~/.config/agents/curated/keychain-secrets/SKILL.md` when you need it.

</Secrets>

<Accounts>

Anthropic access is **split between two accounts on purpose**: Hermes (you)
authenticates one way, OpenCode authenticates as a separate sub account via a
plugin, with its own quota. `~/.config/hermes/AGENTS.md` holds the exact
mapping.

The trap: a plain `claude` re-login changes **Hermes'** credentials, not
OpenCode's. So a quota or auth failure inside an OpenCode run is never fixed by
logging in — it is diagnosed against OpenCode's own account (`opencode-env`),
and anything beyond diagnosis is a question for the orchestrator, not a
credential change you make.

</Accounts>

<SelfModificationGuard>

Some paths in this repo define the runtime that is executing you. Changing them
is not an ordinary edit: the effect appears only after a restart you do not
control, and a mistake can disable the worker, the dispatcher, or the messaging
gateway.

**Block for approval before changing any of these, whatever the Authority
grant says** (`Authority` covers repository work, not the agent platform):

- `hermes/profiles/engineer/**` — your own profile, pipeline, and skills.
- the assistant profile, dispatcher, gateway, or cron wiring.
- `install.sh`, or anything that changes how symlinks are created.
- OpenCode's own configuration when the task did not explicitly ask for it.

Additional standing rules when such work *is* granted:

- Never start, restart, or reload the gateway — it is single-instance and
  supervised; a second poller breaks messaging.
- `hermes/config.yaml` files are rewritten by Hermes at runtime: keep diffs
  minimal and match the existing serialization instead of reformatting.
- Skills under `hermes/**` are git-ignored by default; a new one must be
  opted in explicitly, and the subtree's `AGENTS.md` documents how tracked
  files are frozen.
- Read the subtree's `AGENTS.md` first, every time — it is the authority, and
  it changes.

</SelfModificationGuard>

<InspectionRecipes>

Single commands, no inline interpreters — safe under the worker approval guard.

| Question | Command |
| --- | --- |
| What subtrees exist? | `ls ~/.config` |
| What are the repo-wide rules? | `cat ~/.config/AGENTS.md` |
| Which subtrees carry their own rules? | `find ~/.config -maxdepth 2 -name AGENTS.md` |
| Is the config repo clean? | `git -C ~/.config status --short` |
| What changed recently? | `git -C ~/.config log --oneline -10` |
| Which secrets exist (names only)? | `secret ls` |
| Which commands get secret injection? | `ls ~/.config/bin` |
| Where does a tool home point? | `ls -la ~/.hermes` |

</InspectionRecipes>

<Pitfalls>

- Editing a tool home (`~/.hermes/...`) believing it is separate from the repo,
  or adding a file to the repo and expecting the tool to see it without
  `install.sh`.
- Diagnosing a missing environment variable as a broken Keychain when the real
  cause is an unwrapped launcher — or trying to inspect the value to find out.
- Re-authenticating to fix an OpenCode quota problem, and silently swapping
  Hermes' account instead.
- Treating a change to your own profile, the dispatcher, or the gateway as
  ordinary in-scope work covered by the Authority grant.
- Reformatting a Hermes-managed `config.yaml`, producing a diff that is all
  churn.
- Quoting rules from this file instead of reading the subtree's `AGENTS.md` —
  this map goes stale, that file does not.

</Pitfalls>

<Verification>

- Configuration edits were made in the repo (not a tool home), and new files
  were linked with `install.sh`.
- No secret value was printed, logged, written, or committed.
- Any change touching Hermes' own runtime (your profile, dispatcher, gateway,
  `install.sh`) went through a block round-trip, and the subtree's `AGENTS.md`
  was read first.
- Environment claims in the report come from the inspection recipes, not from
  this file's prose.

</Verification>
