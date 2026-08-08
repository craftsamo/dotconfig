# Shared agent skills

One flat skill tree — `~/.agents/skills`, the cross-agent convention defined
by the [Agent Skills](https://agentskills.io/client-implementation/adding-skills-support)
client guide — read by every AI CLI on this machine. It is backed by two
layers with distinct owners:

| Layer        | Path                            | Owner                  |
| ------------ | ------------------------------- | ---------------------- |
| Mutable root | `~/.agents/skills/` (real dir)  | third-party installers |
| Curated tree | [`agents/curated/`](./curated)  | this repo, fully tracked |

`install.sh` links each curated skill into the mutable root
(`~/.agents/skills/<name> -> agents/curated/<name>`) and prunes links whose
repo target disappeared. Third-party installers (`npx skills`,
`hyperframes skills`) write real directories into the same root; they sit
alongside the curated links and never touch the repo. The `skills` CLI keeps
its update state in `~/.agents/.skill-lock.json`, which is per-machine and
stays outside the repo.

`~/.claude/skills` is symlinked to `~/.agents/skills` — Claude Code does not
read the shared root natively, and `hyperframes skills` uses that path as its
store, so the bridge must point at the mutable root, never into the repo
(a repo-pointing bridge once turned every hyperframes link circular).

## Who reads what

| CLI            | Reads `~/.agents/skills` | Own skill dir                          |
| -------------- | ------------------------ | -------------------------------------- |
| Codex          | yes (canonical path)     | `~/.codex/skills` (machine-local)      |
| opencode       | yes                      | `~/.config/opencode/skills`            |
| GitHub Copilot | yes                      | `~/.copilot/skills` (machine-local)    |
| Grok Build     | yes (AGENTS.md compat)   | `~/.grok/skills`                       |
| Gemini CLI     | yes (alias)              | `~/.gemini/skills`                     |
| Claude Code    | **no**                   | `~/.claude/skills` — bridged           |

Skill directories must be **flat** — `agents/curated/<name>/SKILL.md`. Codex
and Claude Code do not descend into nested groups, so a shared skill cannot
be filed under a category subdirectory the way opencode allows.

## Why the curated tree is not `agents/skills/`

`~/.config/agents/skills` is itself a registered install target of
`hyperframes skills` (the amp/"universal" agent-dir convention), so any
content kept there gets mixed with tool droppings. That path is surrendered:
git-ignored wholesale, owned by the installers. The curated tree lives at
`agents/curated/`, where no installer writes, and is tracked like any other
repo content — no `git add -f` opt-in dance.

`hyperframes skills` also mirrors its store into every agent dir it
recognizes. For dirs that live inside this repo that is handled per dir:
`opencode/skills/` uses an ignore-allowlist (see `.gitignore`); codex and
copilot have machine-local skill dirs, so their droppings never reach the
repo.

## What lives here

Only skills that any agent can actually follow. A skill that names opencode
subagents (`explore-medium`, `reviewer`, ...) or opencode-only tools
(`git_commit_lint`, `github_project_*`) stays in
[`opencode/skills/`](../opencode/skills) — sharing it would tell other agents
to call tools they do not have.

## Provenance of the Japanese writing stack

The curated `japanese-writing` skill bundles the whole Japanese writing
stack (notation SKILL.md + tech-prose / prose-rhythm / business / inspection
layers under references/). Several layers re-author ideas from external
sources. Their prose is original to this repo (meaning preserved, wording
fully re-expressed), so no upstream license text is carried in the files:

- `references/business/` and `references/inspection/` — adapted from
  [coji/natural-japanese](https://github.com/coji/natural-japanese) v1.3.0
  (`b54954f`, MIT): doctype patterns, the 12-article constitution, the
  detection scripts and judgment catalogs. The Python scripts under
  `japanese-writing/scripts/` are carried nearly verbatim and each keeps a
  one-line SPDX/MIT attribution header (that header must stay). Dropped from
  upstream: essay/blog authoring scope, style profiles, the no-uv manual
  checklist, examples.md, `semantic.py`, `calibrate.py`.
- `references/tech-prose.md` — adapted from k16shikano's japanese-tech-writing
  gist (Unlicense); the LLM-phrase catalog now lives in
  `references/inspection/`.
- `references/prose-rhythm.md` — adapted from k16shikano's
  cognitive-rhythm-writing gist (Unlicense).

To pull upstream improvements: diff the upstream repo against the recorded
ref, then re-express the delta in the affected skill (never paste prose
verbatim) and update the ref here.

### House style of the `japanese-writing` skill body

The Japanese bodies (SKILL.md and everything under references/) are
themselves deliverable Japanese text and must dogfood the skill's own
notation layer. On top of that:

- Prose (framing/explanation) is 敬体 (です・ます) in full sentences; rule
  bullets are 常体 dictionary-form directives ending with 。 when they are
  full sentences. No 「〜すること」 endings.
- No `対象: <noun phrase>` label-style prose — write it out
  (「〜が対象です」). Example labels (悪い例：/良い例：) and
  reference-list labels stay, delimited by full-width 「：」 (never ` — `).
- Inline enumerations of 3+ items break out into a bulleted list received
  by 「〜といった」; near-synonym pairings use parentheses (書く（直す）),
  not 中黒. 中黒 is allowed only in heading/label/table noun runs.
- Self-reference: 「本スキル」 in SKILL.md, 「この層」 in layer files;
  never address the agent in second person.
- Prohibition strength ladder: 「〜しない」 (default rule), 「〜に限る」
  (conditional), 「〜てはならない」 (absolute gate).
- Numerals set solid with Japanese (「3個」「12条」); frontmatter
  `description` stays English and is out of scope.

## Third-party skills

Third-party skills are never committed; they are restored from their source.
The HyperFrames set is reinstalled with the HyperFrames CLI
(`npm i -g hyperframes`):

```sh
hyperframes skills          # install the full set into every supported CLI
hyperframes skills update   # update installed skills, drop unpublished ones
```

Note that the global `~/.agents/.skill-lock.json` written by the `skills` CLI
records installs but has no restore command — it cannot be used to rebuild
the mutable root on a fresh machine.
