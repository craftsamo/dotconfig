---
name: opencode-env
description: >-
  Engineer's capability map of the OpenCode instance on THIS machine — where its
  configuration lives (opencode.jsonc, agent roster, the two skill trees, custom
  tools, always-on instructions), what it therefore does on its own (loads
  technique skills, delegates to subagents, runs custom git/board tools), and the
  inspection recipes that confirm all of it before you rely on it. Load it before
  the first OpenCode run of an implement task, when an advisory verdict depends on
  what OpenCode can do here, when orient must report the toolchain, or when a run
  behaves oddly (auto-rejects, quota, auth). This is the capability map — CLI
  syntax lives in the bundled `opencode` skill, and the drive loop lives in
  engineer-pipeline's implement reference.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [opencode, environment, capability, configuration, delegation, permissions, quota, inspection]
    category: software-development
    related_skills: [engineer-pipeline, opencode, machine-env]
---

<Goal>

Know your executor before you drive it. OpenCode is not a bare model — on this
machine it is a configured harness with its own agent roster, skill library,
custom tools, and permission system. Knowing that surface changes how you
prompt (state intent, not procedure), what you can promise in an advisory
verdict, and how you read an anomalous run.

This skill is a **map plus inspection recipes**, never a snapshot. The
configuration is version-controlled and changes; the layout of where to look is
what stays true.

</Goal>

<Scope>
<UseWhen>

- Before the first OpenCode run of an implement task, when the goal touches a
  capability you have not confirmed (a technique skill, a subagent, a custom
  tool, a model).
- Advisory/plan work whose verdict depends on what OpenCode can actually do in
  this environment.
- Orient tasks that must report the toolchain available for the work.
- A run behaves unexpectedly: permissions auto-reject, a quota or auth error,
  an unexplained delegation, a capability you assumed is missing.

</UseWhen>

<DoNotUseWhen>

- You need CLI syntax (flags, sessions, forking) — the bundled `opencode`
  skill.
- You need the drive loop itself (base/Wave forks, PermissionBridge,
  QuestionBridge) — `engineer-pipeline` + `references/implement.md`.
- The task is about the machine outside OpenCode (secrets injection, the
  dotconfig repo, account split) — the `machine-env` skill.

</DoNotUseWhen>
</Scope>

<ConfigMap>

Everything is under `~/.config/opencode/` unless noted. `~/.config` is a git
repo (see `machine-env`), so history explains any surprise.

| Path | What it decides |
| --- | --- |
| `opencode.jsonc` | plugins, `small_model`, per-agent overrides (including the compaction model), providers + model pricing, the `permission` tree, custom-tool permissions, MCP servers |
| `agent/*.md` | the agent roster — primary modes and subagents; each file's frontmatter carries its own model and permissions |
| `AGENTS.md` | always-on global instructions: skill routing rules and the delegation policy (which subagent for which kind of work) |
| `skills/` | OpenCode-only skills — ones that name its subagents or its custom tools, so they cannot be shared |
| `~/.config/agents/skills/` | the harness-neutral shared skill tree (also reachable as `~/.agents/skills`); OpenCode reads it too |
| `tools/*.ts` | custom tools built for this machine (git workflow, GitHub Projects, X search) |
| `instructions/*.md` | always-on policy injected into every session (e.g. the secrets policy) |
| the worktree's own `AGENTS.md` | project rules OpenCode reads on its own — you do not need to restate them |

`opencode.jsonc` is JSONC: it carries comments that explain *why* a setting
exists. Read it as text; strict JSON parsers choke on it.

</ConfigMap>

<CapabilitySurface>

What the map implies for how you drive it. Confirm anything you lean on with
<InspectionRecipes> — these are properties of the current configuration, not
laws.

- **It loads technique skills by itself.** Approach playbooks, commit/PR
  conventions, UI and prose rules are skills OpenCode routes into on its own
  per its `AGENTS.md`. So prompts carry **intent, constraints, and done
  criteria** — not the procedure. Naming a skill is a legitimate hint; pasting
  its steps is micromanagement and usually worse than the skill.
- **It delegates internally.** The roster includes read-only exploration
  tiers, an implementation worker, review, debug, verification, research, and
  UI/UX subagents. One prompt can fan out. Do not decompose to that level —
  that is the L4 you are told not to micromanage; judge the result instead.
- **It has custom tools** beyond the standard file/shell set — a git workflow
  set (history/convention digest, hunk staging, secret scan, commit lint,
  provenance) and GitHub Projects operations. Ask for the outcome; it will
  reach for them.
- **Agent frontmatter beats your invocation.** Read-only agents keep their own
  permissions no matter what environment you pass — that is why review/debug
  runs need no permission bridge.
- **Models are configured, not implicit.** Providers, per-model pricing, the
  compaction model, and the light title model are all pinned in
  `opencode.jsonc`. The model *choice* for a run stays with
  `references/model-routing.md`; this skill only tells you where the truth is.
- **Its Anthropic quota is not Hermes'.** OpenCode authenticates as a separate
  account through a plugin (see `machine-env`); read quota and auth errors
  against that account, never against Hermes' own.

</CapabilitySurface>

<InspectionRecipes>

Run these instead of trusting memory. Every one is a single command with no
inline interpreter, so the worker approval guard passes them.

| Question | Command |
| --- | --- |
| Which CLI version is installed? | `opencode --version` |
| What agents/subagents exist? | `ls ~/.config/opencode/agent` |
| What does one agent do (model, permissions)? | `head -20 ~/.config/opencode/agent/<name>.md` |
| Which skills can it load? | `ls ~/.config/opencode/skills` and `ls ~/.config/agents/skills` |
| What does a skill actually cover? | `head -30 ~/.config/opencode/skills/<name>/SKILL.md` |
| What are the delegation/skill routing rules? | `rg -n "subagent_type|skill" ~/.config/opencode/AGENTS.md` |
| Which custom tools exist? | `ls ~/.config/opencode/tools` |
| What is permitted by default? | `rg -n "permission" ~/.config/opencode/opencode.jsonc` |
| Which plugins/MCP servers are active? | `rg -n "plugin|mcp" ~/.config/opencode/opencode.jsonc` |
| Anthropic quota (the gate) | `npx -y @slkiser/opencode-quota show` |
| Did the config change recently? | `git -C ~/.config log --oneline -10 -- opencode` |

Nested skill directories are normal in OpenCode's own tree (`skills/<group>/<name>/`);
the shared tree is flat by contract. A one-level `ls` can therefore look empty
of the thing you want — descend before concluding it is missing.

</InspectionRecipes>

<DriftDiscipline>

The configuration is actively maintained: skills get added, moved between the
OpenCode-only and shared trees, and agents get retuned. Two rules keep you
honest:

- **Never assert a capability from memory in a report, verdict, or plan.** Run
  the matching recipe first; cite what you saw.
- **When a run contradicts your expectation, re-inspect before working
  around it.** A missing skill, a changed permission, or a moved tree explains
  more failures than model behavior does.

</DriftDiscipline>

<Pitfalls>

- Prompting OpenCode with the steps of a technique it already owns as a skill
  — you overwrite better instructions with worse ones.
- Decomposing to subagent level in a prompt; the roster is its business, the
  Wave is yours.
- Claiming in an advisory verdict that OpenCode "can/cannot do X here" without
  running an inspection recipe.
- Reading an Anthropic quota or auth error as Hermes' own — different account.
- Parsing `opencode.jsonc` with a strict JSON tool and concluding the config is
  broken.
- Concluding a skill is missing after a single-level `ls` of a tree that groups
  skills in subdirectories.
- Widening the permission bridge because a run auto-rejected, instead of
  checking whether the permission tree or the agent's own frontmatter is what
  denied it.

</Pitfalls>

<Verification>

- Any capability claim made to the orchestrator (report, verdict, plan) is
  backed by a recipe you actually ran in this task, not by this file's prose.
- Prompts sent to OpenCode carry intent, constraints, and done criteria — no
  pasted technique procedure, no subagent-level decomposition.
- Quota/auth observations are attributed to OpenCode's account, not Hermes'.

</Verification>
