# Skills: placement, creation and worker approvals

Where each kind of skill lives in the tree, how runtime-created skills are kept
out of the maintained set, how upstream skills are attached, and what a worker
terminal approval lets through. Read it before adding or moving a skill, after
`hermes update`, or when writing a worker playbook.

Part of the Hermes mechanics docs — entry: [`README.md`](../../README.md).

`~/.hermes/skills` and each profile's `skills/` are symlinks into this repo.
`scripts/validate-profile-skills.py` enforces the placement rules below. How an
entry skill is loaded at runtime is in [`../topology.md`](../topology.md)
"Entry loading contract"; the maintainer rules for plugin-shipped skills are in
[`../../AGENTS.md`](../../AGENTS.md) "Skills".

## Skill placement

Shared `skills/` holds only `default-pipeline/` and `learned/`; every other
skill lives under its profile's `skills/`.

- **One root pipeline skill per worker**, `<profile>-pipeline` (lifecycle +
  capability router, auto-loaded by its operating contract). Entry and leaf
  shapes per profile are in the per-profile docs ([`../profiles/`](../profiles/)).
  Researcher and Searcher share `references/{plan,build}.md` stages across
  their entries; their technics are purpose recipes layered on one mode,
  routed by each kernel's `references/capabilities.md`
  ([`../profiles/research.md`](../profiles/research.md) "Technics").
- **Directly selectable leaf technics** sit exactly one directory below
  `skills/technic/` (flat canonical leaves) and are pinned by name. A technic's
  references are modes only when tools, spend class and QA stay the same;
  styles, presets and formats remain references. Creator has no technics: new
  creative capability is a hands leaf ([`../broker.md`](../broker.md)).
- **A plugin ships the skill for its own tool** under
  `plugins/<group>/<name>/skills/<skill>/` (`SKILL.md` and `references/`),
  registered as `<plugin>:<skill>` for the profiles in its `SKILLS` table (for
  example `x-access:x-twitter` for every profile with the `x` tool and
  `x-access:x-twitter-drafts` for the Assistant alone). These are not part of
  any profile's `skills/`, so the validator checks them separately (`plugin
skills=` in its summary) and `skills list` does not show them;
  `skill_view(name="<plugin>:<skill>")` does. Tool mechanics for the Assistant's
  accounts and wallets live there; `technic/` keeps what has no plugin.
- **The Assistant's `assistant-pipeline`** (kernel, entries, shared mode
  references) is tracked here like every other pipeline (only the
  private technic shelf, `config.yaml` and `SOUL.md` live in the overlay; see
  [`tracking.md`](./tracking.md) "Tracked vs ignored"). Its pinned Telegram
  topics bind no skill; their contracts are `channel_prompts` entries. Its tests
  (`assistant-pipeline/tests/`) read the private `config.yaml` only through an
  explicit `HERMES_PRIVATE_ROOT`.
- **The Assistant's private technic shelf** holds knowledge that must not be
  public — account names, businesses and people the pipeline routes to by name
  only: the overlay's `hermes/profiles/assistant/skills/technic/` (same flat
  leaf shape as `technic/`), read through one `skills.external_dirs` entry in
  its private `config.yaml`. Never link it into the public `technic/` (its
  names would show in `git status`) and never use an ancestor that also
  contains `assistant-pipeline` (that indexes it twice). The runtime index
  groups such a leaf under its own name rather than `technic`; loading by name
  is unchanged. The validator checks its shape, its `external_dirs` entry and
  that each name is unique across every source the Assistant reads.
- **`learned/` is never a dispatch or Git ownership surface.**

## Skills

- **Runtime creates land in `learned/`.** Every `config.yaml` sets
  `skills.create_dir: skills/learned` (`HERMES_HOME`-relative,
  validator-enforced), which `skill_manage` consults on every create —
  background review, curator, `/learn`, the `/skills approve` replay, flat or
  `operations[]` call shape — so new skills land at
  `HERMES_HOME/skills/learned/[<category>/]<name>`. The `skill-topology` plugin
  does not do this placement; it only drops a redundant `category: learned`,
  which would otherwise nest `learned/learned/<name>`. The validator accepts one
  category level on every profile, hands included.
- **Bundled skills stay out of the repo.** Seeding is disabled:
  `hermes skills opt-out --remove` writes a `.no-bundled-skills` marker, tracked
  here and linked by `install.sh` so the opt-out reproduces on a fresh machine.
  `skills.external_dirs` points at the agent clone
  (`~/ghq/github.com/NousResearch/hermes-agent/skills`), so bundled skills are
  read in place (read-only, refreshed by `hermes update`).
- **Upstream wiring is `external_dirs`-only.** Official `skills/` libraries
  attach per category directory, `optional-skills/` per individual skill
  directory, pruned via `skills.disabled` (see each profile's `config.yaml`).
  Never run `hermes skills install` — it copies into `~/.hermes/skills`, i.e.
  this repo. The setup-gated candidate backlog is the "Upstream wiring pattern"
  paragraph in [`../topology.md`](../topology.md).
- **Upstream still seeds past the opt-out.** Each gateway launch writes
  `autonomous-ai-agents/DESCRIPTION.md` into the running profile's skill root,
  and an upgrade that changes a bundled skill copies the whole skill in. A lone
  `DESCRIPTION.md` is harmless (ignored, no `SKILL.md`; deleting it only invites
  it back). A seeded `SKILL.md` fails `validate-profile-skills.py` with
  `unexpected skill root`. So **after every `hermes update`**, run the validator
  and delete any category directory under `profiles/*/skills/` that is not
  `<profile>-pipeline`, `technic` or `learned`; the skills stay readable via
  `skills.external_dirs`.
- **Private and shared stores.** The data-skill cluster of the private working
  area lives in the private overlay and is read through `skills.external_dirs`
  as `~/.config/private/hermes/skills`. HyperFrames / `media-use` playbooks and
  the curated `media-craft-*` skills are read from `~/.agents/skills` via
  `external_dirs`, never copied or linked into a profile
  ([`../../AGENTS.md`](../../AGENTS.md) "Skills"). A fresh machine needs
  `hyperframes skills update` before Creator can load them.

## Worker terminal approvals

Worker sessions cannot answer an approval prompt — a flagged command just
fails: `approvals.mode: manual` reaches EOF, denies, and the tool returns
`status: "blocked"`.

- **The guard reads only the outer command**, never inside a script. These pass:
  `./scripts/x.sh`, `bash x.sh`, `python3 script.py`, `opencode run`,
  `npx hyperframes …`, `ffmpeg`, `git commit`, non-force `git push`,
  `gh pr create`, `xurl`.
- **What trips it:** inline interpreters (`bash -c`, `python3 -c`, `node -e`),
  `find -delete`, `chmod +x … && ./…`, recursive `rm -rf`, `git reset --hard`,
  `git clean -f`, force push. Write worker playbooks around scripts and wrapper
  CLIs, never inline one-liners.
- **`command_allowlist` stays empty on purpose.** It is the escape hatch (exact
  match or fnmatch glob against the whole command; skipped when the command
  contains `&&` `|` `>` `;`), and allowing e.g. `bash -c *` would reopen exactly
  what the guard exists to catch.
- The hardline floor (`rm -rf /`, `$HOME`, system dirs) blocks regardless.
