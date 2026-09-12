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

## Japanese writing core

The curated `japanese-writing` SKILL.md now contains language knowledge and
five notation defaults: mixed-script typography, kana spelling, okurigana,
no Japanese prose dashes, and contextual use of `〜化` / `〜的`.
It does not select document types, orchestrate review, run tools or score
naturalness. Fixed terminology tables, genre-wide registers and source-line
wrapping rules are no longer part of the shared core.

The package contains only `SKILL.md`. Document construction and checking belong
to the host workflow; Hermes Writer uses its operation/subject leaves and a
bounded pre-draft consultation. The old catalogs, inspection loop, naturalness
scores, Python tools and their detector fixtures have been retired after their
Writer and caller dependencies were removed. Do not reinstall that workflow by
copying old resources back into a discovered skill directory.

### Historical sources

The former stack is recoverable from Git history. Locate the deletion of its
resource paths with `git log --all --diff-filter=D -- agents/curated/japanese-writing/`,
then inspect the removal commit's parent rather than relying on a hash that
changes during a rebase. This record preserves the origin of ideas also
re-expressed in Writer references; it is not an active dependency or a
skill-resource index.

- Business-document and inspection material was adapted from
  [coji/natural-japanese](https://github.com/coji/natural-japanese) v1.3.0
  (`b54954f`, MIT). The retired Python scripts were carried nearly verbatim
  with SPDX/MIT attribution headers. Preserve those headers and applicable
  license notices if restoring or reusing that code from history.
- Argumentation guidance was adapted from k16shikano's japanese-tech-writing
  gist (Unlicense), and pacing guidance from the cognitive-rhythm-writing gist
  (Unlicense). The local prose re-expressed those ideas rather than copying it.

Consider future source improvements only for an identified language or writing
task. Preserve attribution for reused material; do not restore obsolete
detectors, templates or review procedures as a bulk upstream update.

### Maintaining the language core

Write the Japanese core in readable prose with the selected notation.
Separate actual ambiguity or meaning loss from an optional change of style.
Examples must preserve facts, modality and register; natural counterexamples
are as important as corrections. Do not reintroduce fixed repetition counts,
genre templates, a mandatory review loop or a reference router.
Behavioral cases live outside the runtime skill under `agents/tests/`.

### Current Hermes Writer adaptation

Hermes Writer's existing operation-specific references now draw on
[coji/natural-japanese v1.5.0](https://github.com/coji/natural-japanese/tree/v1.5.0)
(`21e632661a910bf97289c501089ad11eb8b4d85f`, MIT, consulted 2026-09-10).
This is separate from the retired v1.3.0 material above and does not expand
the shared Japanese language core. The 91 leaf references contain locally
authored examples, conditional craft guidance and operation-specific checks;
their source links identify the particular upstream ideas used. Message,
copy, script and post guidance also cites relevant primary Microsoft, GOV.UK,
BBC, W3C and ONS material where upstream has no specialized treatment.

The requester-owned editorial rubric adapts v1.5.0's evaluation questions,
not its self-scoring workflow: six evidence-anchored 0-4 axes, no averaging
away failures, and a bounded correction loop. The scale and acceptance floor
are local policy, not validated statistical measurements. No upstream scripts,
detectors or substantial verbatim reference text are imported. Retain source
attribution, and preserve the upstream MIT notice if subsequently copying
substantial text or code rather than independently expressing its ideas.

Behavioral review cases live in `hermes/scripts/tests/writer-craft-cases.md`,
outside skill discovery. Structural tests do not prove writing quality or
live-profile adherence.

## Media craft knowledge

`media-craft-direction` supplies portable reference interpretation, direction,
production translation and critique knowledge. It owns no host tools, budgets,
approval workflow or style menu. Its fictional worked examples are original;
the client's actual constraints and producer capabilities remain authoritative.
Detailed material is read at the relevant decision, not loaded wholesale for
mechanical edits. Installation uses the same curated links as other shared
skills; it does not add an always-on rule to every CLI.

`media-craft-visual` owns execution of the chosen visual effect: composition,
typography, material/light, symbols/characters, asset systems and image-prompt
craft. Direction selects the intended effect; this skill diagnoses how pixels
realize it. The shared boundary is complementary, not two approval workflows.
Its original examples independently express ideas from Apple HIG typography and
symbol guidance, IBM Carbon's grid guidance, and Adobe's animation principles
(source links and consultation dates are in the relevant references). No vendor
artwork, symbols, screenshots or substantial source prose are redistributed.

Behavioral cases and the independent evaluation contract live under
`agents/tests/`. Run `python3 -m unittest discover -s agents/tests` for structural
checks; fresh-context use and actual-media quality need separate evidence.

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
