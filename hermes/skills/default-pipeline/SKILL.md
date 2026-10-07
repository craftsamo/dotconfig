---
name: default-pipeline
description: >-
  CLI front-door adapter for the default profile. The workflow itself —
  modes Chat / Plan / Execute / Quality Assurance and the two execution
  tiers — is owned by the assistant's
  `assistant-pipeline` kernel and child entries; this skill reads that tree and
  records only the deltas of running it from an interactive terminal
  instead of the Telegram gateway.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [orchestration, cli, front-door, modes, resident-session]
    category: orchestration
    related_skills: []
---

<Goal>

Give the CLI front door the same workflow as the messaging assistant —
plan with the user, supervise specialists, verify deliverables — while
respecting what a terminal session can and cannot do.

</Goal>

<ReferenceTree>

The single source of truth is the assistant's tree:

```
~/.hermes/profiles/assistant/skills/assistant-pipeline/
  SKILL.md
  chat-assistant/SKILL.md
  {plan,execute,qa}-assistant-<domain>/SKILL.md
  <entry>/references/                 # entry-owned details, creative legacy
  references/plan/index.md
  references/execute/{index,resident-sessions}.md
  references/quality-assurance/index.md
```

Use `read_file` on the known root's `SKILL.md` for the common contract
and tier litmus. Discover available mode/domain entries
with a bounded filesystem listing of that root's immediate child directories
and their `SKILL.md` files, using the same names as the root map:
`chat-assistant` and `plan-assistant-*` / `execute-assistant-*` /
`qa-assistant-*` for engineering, creative, writing, research, search and
marketing. Do not generate another index or add these 19 skills to default's
`skills.external_dirs`; clones must not inherit an expanded skill menu.

On each user turn and completion, and BEFORE an action changing mode, domain
or scope midturn, select the applicable entry from that filesystem index.
Read its `<entry>/SKILL.md`, the kernel and required mode-common procedure,
then relevant details. Reuse full instruction bodies currently in context,
not a past load or summary; root preload does not prove dependencies present.
An approval-only reply follows existing job state and scope, never restarts
planning or expands a grant. Everything in the tree applies here unless a
delta below overrides it.

Use `read_file` for Assistant files even when their names are hidden from
CLI `skill_view`. Translate dependency calls to canonical paths under the
known root: `assistant-pipeline` means its root `SKILL.md`, its `file_path`
is root-relative, and an entry name means `<entry>/SKILL.md` with entry-relative
details. Never follow a literal skill-name call that cannot resolve here.
In raw child content, `${HERMES_SKILL_DIR}` resolves to THAT owning child's
directory, not default-pipeline or the Assistant root; references retain their
owning skill's base. Follow `next_offset` to finish a truncated document.
If a read reports unchanged while its body is missing, use the entry-local
canonical `read_file` fallback; if still unavailable, stop the affected action.
Do not evade dedup with alternate paths or artificial ranges.

Writing QA still belongs to the public Writer pipeline. If `writer-pipeline`
is unavailable by name in this profile, translate its acceptance dependency
to `read_file` at
`~/.hermes/profiles/writer/skills/writer-pipeline/references/acceptance/index.md`
and the selected `prose.md` or `script.md` alongside it. This is requester
inspection, not production or permission to expose Writer's authoring leaves.
Missing required acceptance bodies block acceptance, never a generic-review
fallback.

</ReferenceTree>

<CliDeltas>

- **The user is present.** `clarify` renders as arrow-key selection;
  plan approvals happen live. There is no gateway persona ceremony —
  answer plainly in the terminal.
- **Resident sessions work normally** via `resident-session.sh` (the
  wrapper is profile-agnostic). Short turns may run foreground; long
  turns run `background=true` + `notify_on_complete` and surface in this
  interactive session. In a non-interactive run (`-q` one-shot) there is
  no wake — don't start long background work you cannot hand back;
  either wait foreground within the timeout or tell the user to continue
  from the messaging assistant.

</CliDeltas>

<AntiPatterns>

- Duplicating or paraphrasing assistant-pipeline content here — this
  skill is an adapter; the tree is the authority.
- Long background work in a one-shot run that nothing will ever collect.
- Skipping a resident session because the CLI makes it feel
  heavyweight — supervision cost is the point, not overhead.

</AntiPatterns>
