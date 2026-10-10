# Tracking: what is in Git and how a profile is adopted

What the repo tracks and ignores under `hermes/`, who owns each kind of skill
directory, how a named profile is moved into the repo, and why `cron/` stays
out. Read it before adding a file, a profile or a skill to the tree, or when
`git status` shows something unexpected.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Tracked vs ignored

**Tracked:** root `config.yaml` / `mcp.json` / `.no-bundled-skills`; per profile
`config.yaml` (assistant: `config.example.yaml`), `profile.yaml`,
`.no-bundled-skills`, `skills/<profile>-pipeline/` and `skills/technic/`,
`scripts/`; every `SOUL.example.md`; `skills/default-pipeline/`; `plugins/`
source; `launchd/`; `engines/`; `scripts/`; docs.

**Ignored** (see [`.gitignore`](../../../.gitignore)): every `SOUL.md` and
`profiles/assistant/config.yaml` (private overlay); `auth.json`, `.env*`,
`memories/`, `sessions/`, `state.db*`, `logs/`, `workspace/`, `plans/`,
`*_cache/`, `local/`, `browser-profile/` (copied cookies — must never ship);
`specialist-sessions/`, `resident-sessions/`, `opencode-sessions/`; skill
bookkeeping (`.bundled_manifest`, `.usage.json*`, `.curator_*`, `.archive/`,
`.hub/`, `index-cache/`, `.restore-backups/`); every other directory under
`skills/` (`learned/`, seeded categories); `profiles/*/scripts/local-*.sh`;
Marketer lease files; `**/__pycache__/`, `*.pyc`; the
`plugins/hermes-achievements/` runtime data. `cron/` is absent entirely — it is
not linked, so nothing it writes reaches the repo. Never commit secrets, state
or host-rendered plists (`~/Library/LaunchAgents/…`).

**Skill ownership follows the directory type.** Shared `default-pipeline/` and
every worker's `<profile>-pipeline/` and `technic/` are maintainer-owned and
tracked normally, and so is the assistant's `assistant-pipeline/`. What must
stay private lives in the overlay repo instead: the assistant's private technic
shelf, its `config.yaml` and the real `SOUL.md` files; commit those there.
Never use `skip-worktree` for managed skills: their changes must remain visible
in `git status`.

**Promoting a learned skill** is an explicit review step: review it, move the
complete package from `learned/` into `technic/`, set
`metadata.hermes.category: technic` and normalize its routing, add it to the
pipeline's capability registry when applicable, pin an agent-created source
against curator writes with `hermes -p <profile> curator pin <name>`, then
commit it normally. An assistant skill that must stay private moves to the
private technic shelf instead and is committed in the overlay repo; no pin is
needed there, because the curator never touches `external_dirs` skills. Move,
never copy: the same name in `learned/` and the shelf makes `skill_view`
refuse it as ambiguous.

## Profiles

Named profiles live under `~/.hermes/profiles/<name>/` — each its own
`HERMES_HOME` with its own `config.yaml` / `SOUL.md` / `skills/` / `cron/` /
state. The alias `~/.local/bin/<name>` is a wrapper that runs
`exec hermes -p <name> "$@"` — **bare `hermes`**, so it still resolves through
the `bin/hermes` shim and the shared `global` + `hermes` Keychain layers are
injected for every profile. The default profile is `~/.hermes` itself. Roster
and roles: [`../topology.md`](../topology.md) "Profile roster".

### Tracking a profile

Because `hermes profile create` writes **real** files into
`~/.hermes/profiles/<name>/` and `link()` never replaces a real file, move them
into the repo (clearing the real files) before linking:

1. `hermes profile create <name> --description "<role>"` — seeds state + the
   `~/.local/bin/<name>` alias. Routing quality depends on the description
   (`hermes profile describe <name> --text "…"` to change it).
2. Stop bundled-skill seeding so bundled skills stay in `external_dirs`:
   ```sh
   hermes -p <name> skills opt-out --remove --yes
   ```
3. Move the version-controllable files into the repo (skip any that don't exist):
   ```sh
   mkdir -p ~/.config/hermes/profiles/<name>
   mv ~/.hermes/profiles/<name>/{config.yaml,profile.yaml,SOUL.md,mcp.json,skills} \
      ~/.config/hermes/profiles/<name>/
   ```
   Commit a `SOUL.example.md` persona template; `SOUL.md` itself stays
   untracked (put the real one in the private overlay). A config holding private
   identifiers follows the assistant pattern: track `config.example.yaml`, keep
   the real `config.yaml` in the overlay.
4. In that profile's `config.yaml`, point `skills.external_dirs` at the clone
   (`~/ghq/github.com/NousResearch/hermes-agent/skills`) — same as default.
5. `./install.sh` — the `[hermes]` loop now symlinks them (no WARN).

State (`memories/`, `sessions/`, `state.db*`, `cron/`, …) stays in
`~/.hermes/profiles/<name>/` — never moved, never tracked. A new bot also needs
a `hermes-<name>` Keychain layer plus its `platforms`/`a2a`/toolset entries (the
single host gateway serves every profile directory; there is no allowlist) — see
[`../topology.md`](../topology.md) "Multiplex gateway and A2A peer graph".

### Caveats

- **Order matters / "already installed".** The symlink must exist _before_
  Hermes writes a real file. If real files already exist (a named profile, or a
  `~/.hermes/` set up before this repo), `install.sh` won't replace them — use
  the move-then-`install.sh` adoption above. Hermes itself runs fine either way;
  only the symlink tracking is affected.
- **Background / launchd processes** may start with a restricted `PATH`. The
  multiplex gateway launcher sets `PATH` explicitly and injects the approved
  Keychain layers before `exec`; other services must follow the same pattern.

## Cron

`~/.hermes/cron` (and each profile's) is a real machine-local directory this
repo neither links nor tracks; Hermes creates it and owns every file in it
(`jobs.json`, run output, locks, the execution database). Definition and
run-state share one file, so tracking `jobs.json` meant constant churn. The
rule never to re-link it or re-add it with `skip-worktree`, and why, is in
[`../../AGENTS.md`](../../AGENTS.md) "Repository and install".

- A missing `jobs.json` is read as **zero jobs, silently**, and nothing
  recreates it — back it up before touching that directory.
- The private `local-*` schedules are re-creatable from the `hermes cron create`
  commands in the private overlay's README. Hermes' scheduler only runs a script
  resolving inside `<HERMES_HOME>/scripts`, so the overlay's `install.sh`
  generates the ignored `profiles/*/scripts/local-*.sh` wrappers.
- Throwaway scripts a profile writes for its own jobs go in the ignored
  `profiles/*/scripts/adhoc/` and are referenced as `adhoc/<name>`; only
  scripts meant to be maintained sit directly in `scripts/` and get tracked.
  Deleting a job does not delete its `adhoc/` script — prune by hand.
