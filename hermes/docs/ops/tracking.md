# Tracking: what is in Git and how a profile is adopted

What the repo tracks and ignores under `hermes/`, who owns each kind of skill
directory, how a named profile is moved into the repo, and why `cron/` stays
out. Read it before adding a file, a profile or a skill to the tree, or when
`git status` shows something unexpected.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

## Tracked vs ignored

**Tracked:** root `config.example.yaml` / `mcp.json` / `.no-bundled-skills`; per profile
`config.example.yaml`, `profile.yaml`,
`.no-bundled-skills`, `skills/pipeline/` and `skills/technic/`,
`scripts/`, `cron.d/`; every `SOUL.example.md`; `skills/pipeline/`; `plugins/`
source; `launchd/`; `engines/`; `scripts/`; docs.

**Not here at all:** everything Hermes writes. `~/.hermes` and each profile
home are real machine-local directories holding links into this tree
([`README.md`](../README.md) "Symlinks"), so runtime state (`auth.json`,
`memories/`, `sessions/`, `state.db*`, `cron/`, …), the real `config.yaml` and
`SOUL.md` (the private overlay's, linked from HOME), `learned/` and the skill
bookkeeping (`.usage.json*`, `.curator_*`, `.hub/`, seeded categories), a
profile's `adhoc/` scripts, its own `cron.d/` directories and the wrappers
cron-sync generates all land beside the links, outside the repository.

**Ignored** (see [`.gitignore`](../../../.gitignore)): the runtime-state names
above, as a safety net for a `HERMES_HOME` pointed at this tree by mistake;
`**/__pycache__/`, `*.pyc` (Python writes bytecode beside the real source).
Engine runtimes are not in the tree: `~/.hermes/local/` (`HERMES_LOCAL`)
holds them, and the overlay's Irodori lexicon is linked there. A plugin's private data (the specialist-call
roster additions, the workspace registry's local integration) is read from
`~/.hermes/plugin-data/<plugin>/`, never beside the source. Never commit
secrets, state or host-rendered plists (`~/Library/LaunchAgents/…`).

**Skill ownership follows the directory type.** Shared `skills/pipeline/` and
every profile's `pipeline/` and `technic/` are maintainer-owned and
tracked normally. What must
stay private lives in the overlay repo instead: the assistant's private technic
shelf, the real `config.yaml` files (root and every profile) and the real
`SOUL.md` files; commit those there.
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
`~/.hermes/profiles/<name>/` and `link()` never replaces a real file, move the
tracked ones into the repo (clearing the real files) before linking:

1. `hermes profile create <name> --description "<role>"` — seeds state + the
   `~/.local/bin/<name>` alias. Routing quality depends on the description
   (`hermes profile describe <name> --text "…"` to change it).
2. Stop bundled-skill seeding so bundled skills stay in `external_dirs`:
   ```sh
   hermes -p <name> skills opt-out --remove --yes
   ```
3. Move the version-controllable files into the repo (skip any that don't exist):
   ```sh
   mkdir -p ~/ghq/github.com/craftsamo/dotconfig/hermes/profiles/<name>/skills
   mv ~/.hermes/profiles/<name>/{profile.yaml,mcp.json} \
      ~/ghq/github.com/craftsamo/dotconfig/hermes/profiles/<name>/
   mv ~/.hermes/profiles/<name>/skills/pipeline \
      ~/ghq/github.com/craftsamo/dotconfig/hermes/profiles/<name>/skills/
   ```
   `skills/` itself stays in HOME (`learned/` lives there); only the managed
   `pipeline/` and `technic/` move. Commit a `SOUL.example.md` persona
   template and move the real `SOUL.md` into the private overlay
   (`hermes/profiles/<name>/SOUL.md` there). Commit the config as
   `config.example.yaml` and move the real `config.yaml` into the overlay
   likewise: tests, the validator and a fresh machine read the example.
4. In that profile's `config.yaml`, point `skills.external_dirs` at the clone
   (`~/ghq/github.com/NousResearch/hermes-agent/skills`) — same as default.
5. `./install.sh` (which runs the overlay's) — the `[hermes]` loop now links
   them (no WARN).

State (`memories/`, `sessions/`, `state.db*`, `cron/`, …) stays in
`~/.hermes/profiles/<name>/` — never moved, never tracked. A new bot also needs
a `hermes-<name>` Keychain layer plus its `platforms`/`a2a`/toolset entries (the
single host gateway serves every profile directory; there is no allowlist) — see
[`../topology.md`](../topology.md) "Multiplex gateway and A2A peer graph".

### Caveats

- **Order matters / "already installed".** The link must exist _before_
  Hermes writes a real file. If real files already exist (a named profile, or a
  `~/.hermes/` set up before this repo), `install.sh` won't replace them — use
  the move-then-`install.sh` adoption above. Hermes itself runs fine either way;
  only the link tracking is affected. A profile's `scripts/` is the one
  directory of copies: edit the repo file and re-run `install.sh`; an edit made
  in HOME is overwritten by the next run.
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
  recreates it on its own — back it up before touching that directory. What
  does recreate the tracked jobs is `install.sh`: every job worth keeping is a
  `profiles/<p>/cron.d/<name>/` directory in this repository or the private
  overlay, and `scripts/cron-sync.py` derives `jobs.json` from the links
  `install.sh` places ([cron.md](cron.md)). A job's definition is never a
  `hermes cron create` command quoted in a header or a README.
- A profile's own jobs are real directories beside those links, written
  through `cron-sync add`; the wrappers cron-sync generates land in
  `profiles/*/scripts/cron/` in HOME, outside the repository. Promoting a
  local job into a repository is the same move as `learned/ → technic/`
  ([cron.md "Public, private, local"](cron.md#public-private-local)).
