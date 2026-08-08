---
name: default-pipeline
description: >-
  CLI front-door adapter for the default profile. The workflow itself —
  modes Chat / Plan / Execute / Quality Assurance, the three execution
  tiers, and the closed kanban card catalog — is owned by the assistant's
  `assistant-pipeline` skill; this skill points at that reference tree and
  records only the deltas of running it from an interactive terminal
  instead of the Telegram gateway.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [orchestration, cli, front-door, modes, resident-session, kanban]
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
~/.hermes/profiles/assistant/skills/assistant-pipeline/references/
  chat/  plan/  execute/  quality-assurance/
```

Load `SKILL.md` beside it for the pipeline, tier litmus, and the closed
card-catalog rule, then the mode/capability files exactly as it routes
them. Everything there applies here unless a delta below overrides it.

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
- **Kanban completions notify the gateway, not this terminal.** The
  board is shared, so registering a catalog card from here is legal, but
  its terminal events wake the *messaging* assistant's subscribed chat —
  not you. Register a card from the CLI only when the user understands
  results land there (or will ask later); otherwise keep the work in a
  resident session you supervise synchronously.
- **Scheduled parking works from here** (`execute/scheduled.md`) — the
  sweeper cron runs on the assistant profile regardless of who parked
  the card.
- **Same closed catalog.** The CLI has no special dispensation: no
  `card_units` match → no card, however detailed the body you could
  write.

</CliDeltas>

<AntiPatterns>

- Duplicating or paraphrasing assistant-pipeline content here — this
  skill is an adapter; the tree is the authority.
- Long background work in a one-shot run that nothing will ever collect.
- Registering feedback-likely work as cards because the CLI makes
  sessions feel heavyweight — supervision cost is the point, not
  overhead.

</AntiPatterns>
