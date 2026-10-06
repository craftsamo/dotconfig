# Shared agent skills

One flat skill tree — `~/.agents/skills`, the cross-agent convention defined
by the [Agent Skills](https://agentskills.io/client-implementation/adding-skills-support)
client guide — read by every AI CLI on this machine. It is backed by two
layers with distinct owners:

| Layer        | Path                           | Owner                    |
| ------------ | ------------------------------ | ------------------------ |
| Mutable root | `~/.agents/skills/` (real dir) | third-party installers   |
| Curated tree | [`agents/curated/`](./curated) | this repo, fully tracked |

`install.sh` links each curated skill into the mutable root
(`~/.agents/skills/<name> -> agents/curated/<name>`) and prunes links whose
repo target disappeared. Third-party installers (`npx skills`,
`hyperframes skills`) write real directories into the same root; they sit
alongside the curated links and never touch the repo. The `skills` CLI keeps
its update state in `~/.agents/.skill-lock.json`, which is per-machine and
stays outside the repo.

Claude Code does not read the shared root natively, so `install.sh` links
each shared skill into `~/.claude/skills`, which stays a real directory. The
links point at the mutable root, never into the repo (a repo-pointing bridge
once turned every hyperframes link circular). Linking the whole directory is
not an option: Claude Code syncs claude.ai skills into `~/.claude/skills/synced/`,
and those need the Claude app's own tools, so they would leak into every CLI
that reads the shared root. `hyperframes skills` installs with `--copy`, so it
writes a real copy into both directories; `install.sh` leaves real entries in
`~/.claude/skills` alone. A skill installed only into the shared root reaches
Claude Code at the next `install.sh` run.

OpenCode V2 still reads `~/.claude/skills` as a compatibility source and has
no way to exclude it yet (anomalyco/opencode#36990), so
`opencode/opencode.jsonc` denies the synced skills that cannot work there.

## Who reads what

| CLI            | Reads `~/.agents/skills` | Own skill dir                         |
| -------------- | ------------------------ | ------------------------------------- |
| Codex          | yes (canonical path)     | `~/.codex/skills` (machine-local)     |
| opencode       | yes                      | `~/.config/opencode/skills`           |
| GitHub Copilot | yes                      | `~/.copilot/skills` (machine-local)   |
| Grok Build     | yes (AGENTS.md compat)   | `~/.grok/skills`                      |
| Gemini CLI     | yes (alias)              | `~/.gemini/skills`                    |
| Claude Code    | **no**                   | `~/.claude/skills` — linked per skill |

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

`japanese-writing` is the shared skill for writing, rewriting, proofreading
and diagnosing Japanese deliverables. `SKILL.md` holds the routing and the
workflow (design, draft, inspect, judge, converge, final review at quick or
full depth); everything conditional lives in `references/` and is read when
`SKILL.md` routes to it:

| File                         | Content                                                              |
| ---------------------------- | -------------------------------------------------------------------- |
| `constitution.md`            | 12 drafting principles                                               |
| `readability.md`             | readability principles and the A1–J3 catalog                         |
| `expression.md`              | stock phrasing, translationese, rhythm, specificity (X1–X10)         |
| `notation.md`                | house notation (N1–N11), Microsoft style based                       |
| `revision.md`                | meaning preservation, stance, decision ledger, convergence (R1–R5)   |
| `genres.md`, `doctypes/*.md` | genre adjustments; minutes, report, guide, memo, slide               |
| `evaluation.md`              | 0-100 diagnosis and the six-axis final review (each ≥ 90, mean ≥ 92) |
| `inspection.md`              | how to run and read the inspector                                    |

Inspector findings cite these anchors in their `reason`, and
`agents/tests/test_japanese_writing.py` keeps the anchors and the citations in
sync. Scores describe reader cost, never authorship.

### Inspector

`scripts/inspect_text.py` is a read-only CLI (`--request` JSON on stdin, or
`--file` with `--original`, `--modes`, `--genre`, `--stance`,
`--experimental`). It emits report schema 2 and never writes, installs or
fetches anything. The `inspector/` package holds the Markdown-aware document
model (`document.py`), optional Sudachi morphology (`morphology.py`), report
limits (`report.py`), the mechanical score (`score.py`), one module per mode
under `rules/` and the word lists and patterns as data under `data/`:

| Mode                          | Origin                                                            |
| ----------------------------- | ----------------------------------------------------------------- |
| `naturalness`, `reading-load` | natural-japanese lint lanes (default, experimental, reading load) |
| `outline`, `terms`            | natural-japanese outline/terms                                    |
| `expression`, `revision`      | yomiyasu lint and diff                                            |
| `notation`                    | Microsoft Japanese style guide (own rule set)                     |
| `structure`                   | this repo                                                         |

Hermes Writer reaches it only through the `writing_inspect` tool; other
clients run the CLI themselves.

### Sources and reconstruction

The skill and inspector are a reconstruction, not a vendored copy, of two MIT
projects:

- [coji/natural-japanese](https://github.com/coji/natural-japanese) v1.5.0
  (`21e632661a910bf97289c501089ad11eb8b4d85f`)
- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) v1.0.4
  (`8d5abeebe2dd20c2db005deaddcc50be43c59c0a`)

Their scripts were reduced to behavior specifications (rule ids, thresholds,
severities, score formula), and the inspector was written from those specs.
Word lists and regular expressions were carried over as data so the rules keep
their calibration. No upstream code, comments, prompts, message strings or
example texts are included, and the references are newly written with
original examples. Parity was checked by running both upstream CLIs as black
boxes. natural-japanese's own fixtures give identical per-rule counts (25
default, 33 experimental, 0 natural). The remaining differences are
deliberate:

- code blocks are never counted;
- links are masked as a whole;
- all ten transitive-verb patterns can match;
- yomiyasu's half-width-space and trailing-colon rules are dropped because they
  contradict the house notation;
- its `〜に他なりません` pattern is fixed.

Notation follows the
[Microsoft Japanese Localization Style Guide](https://aka.ms/japanese-styleguide)
(PDF of 2025-07-18). UI-only rules are not generalized to prose. Where the
guide is silent or inconsistent, `notation.md` records the house choice: the
kana list, `℃`, full-width characters in its own examples. Documents that
consistently follow another convention, such as JTF's unspaced style, keep it.

Do not import upstream semantic models, corpora, calibration scripts or
subagent orchestration. When upstream changes, compare behavior through the
specs and black-box runs, then port deliberate rule changes as data or code
with tests. The retired v1.3.0-era catalogs and lint remain recoverable from
Git history only.

### Runtime provisioning

Hermes uses a dedicated Python 3.12 environment. There is no runtime
auto-install; this is a maintainer-only, one-time step, run from the repo root
after checking that `hermes/local/writing-inspection/venv/` does not exist:

```sh
uv venv hermes/local/writing-inspection/venv --python 3.12
uv pip install --python hermes/local/writing-inspection/venv/bin/python \
  -r agents/curated/japanese-writing/scripts/requirements.txt
```

Other clients may point at their own Python with the pinned packages (see
`references/inspection.md`). Without them, the morphology-dependent rules are
reported as unverified and the score is withheld.

### Maintaining the core

- Write the references in Japanese with the house notation, one sentence per
  line. Run `inspect_text.py --modes notation,expression` on them; findings
  that deliberately show violations stay.
- A new rule gets a data entry, a reason that cites an existing anchor, and
  tests under `agents/tests/japanese_writing/`.
- Tests: `uv run --with pytest python -m pytest agents/tests -q`. To cover
  the Sudachi paths, run
  `hermes/local/writing-inspection/venv/bin/python -m unittest discover -s agents/tests/japanese_writing -t agents/tests`.
- Behavioral cases live in `agents/tests/japanese-writing-cases.md`. Tests
  check structure and rule behavior, not writing quality.

### Hermes Writer adaptation

Writer maps its operations onto the shared workflow (kernel `<Selection>`):

- a write leaf writes;
- an edit leaf edits with `original`;
- an analyze leaf diagnoses only on request.

Writer's own leaf references keep form-specific craft and their natural-japanese
v1.5.0 provenance links (consulted 2026-09-10). The requester-owned acceptance
rubric uses the same six 0-100 axes and the 90/92 floor as `evaluation.md`,
with Purpose and Fidelity as hard gates. Behavioral review cases for Writer
live in `hermes/scripts/tests/writer-craft-cases.md`.

A published before/after analysis,
["生成AI以前と以後でエンジニアの文章はどう変わったのか: Qiitaの7万記事を数えてみた話"](https://nyosegawa.com/posts/qiita-writing-before-after-ai/)
(2026-09-11), was consulted for observations about vocabulary and formatting
frequency. It is not evidence of writing quality or individual authorship.

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

`media-craft-motion` owns temporal execution of a chosen effect: timing/spacing,
continuity, UI choreography, explanation/performance, generated shots and actual
motion review. It permits deliberate cuts, stillness and divergent visual styles;
it imports no seam scripts or universal camera law. Technique sources include
Adobe animation principles, Blender F-curve documentation, Material transitions
and OpenAI's Sora prompting guide, independently expressed with original cases.
Provider controls and detector-derived timing are never universal guarantees.

`media-craft-audio` owns sonic execution: delivery, sound shape, composition,
arrangement, generation briefs and listening-based revision. It distinguishes
score or meter evidence from hearing, and grants no audio-understanding service.
Hermes uses human comparison listening for this release. Its independently
written examples draw on the following sources (consulted 2026-09-12); no audio,
score, source tables or substantial licensed text is copied:

- [ElevenLabs TTS practices](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices)
  and [Google SSML](https://docs.cloud.google.com/text-to-speech/docs/ssml):
  delivery concepts only, never portable control syntax.
- [Ableton melody lessons](https://learningmusic.ableton.com/make-melodies/make-melodies.html)
  and [Open Music Theory](https://viva.pressbooks.pub/openmusictheory/):
  independently expressed musical principles and original note examples.
- [Audiokinetic dynamics](https://www.audiokinetic.com/en/blog/loudness-processing-best-practices-chapter-2-loudness-dynamics-and-how-to-process-them/),
  [iZotope masking](https://www.izotope.com/community/blog/unmasking-your-mix-with-neutron)
  and [EBU R 128](https://tech.ebu.ch/publications/r128): sound-envelope,
  priority and measurement concepts, not claims of available DSP or universal
  loudness targets. Source licensing still governs any future direct adaptation.

Behavioral cases and the independent evaluation contract live under
`agents/tests/`. Run `uv run --with pytest python -m pytest agents/tests -q` for structural
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
