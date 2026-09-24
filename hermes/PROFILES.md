# Profiles — multi-agent plan

How this machine runs several Hermes agents that cooperate: two **front
doors** a human talks to, plus named **worker** profiles they delegate to in
the background. This is the design doc; [`README.md`](./README.md) covers the
single-profile mechanics (symlinks, skills, cron, secrets).

A profile is just a separate `HERMES_HOME` (`~/.hermes/profiles/<name>/`) with
its own `config.yaml` / `SOUL.md` / `skills/` / `cron/` / state, and a
`~/.local/bin/<name>` alias that runs `hermes -p <name>`. The default profile is
`~/.hermes` itself (it can't be deleted or renamed).

The design docs live under [`docs/`](./docs/). Section names are kept, so a
pointer such as `PROFILES.md "Broker shape"` resolves through this table.

| Doc | Sections |
|---|---|
| [Topology and operating layers](./docs/topology.md) | Topology (Multiplex gateway and A2A peer graph); Three delegation layers; Profile roster (Toolsets, Planning ownership, Default is the assistant's CLI counterpart (and stays a clean baseline), Two working directories per worker); Operating layers (per profile); Entry loading contract; Candidate rollout and cutover |
| [Specialist calls and work continuity](./docs/profiles/specialist-calls.md) | Specialist calls (Completion and deadlines, Ownership); Shared work continuity; Failure and reconciliation |
| [Assistant](./docs/profiles/assistant.md) | Assistant quality gate; Visual design and timeline; Creative early delivery candidate; Assistant entry routing (Routing and tiers, Kanban catalog, Pinned Telegram topics) |
| [Engineer](./docs/profiles/engineer.md) | Engineer dialogue loop (Mode entries, OpenCode runtime, Resident turns and reconcile, UI evaluators, Hands-reference maintenance, Specialist dialogue discipline) |
| [Researcher and Searcher](./docs/profiles/research.md) | Research and search dialogue (Researcher, Searcher, Entries and status) |
| [Writer](./docs/profiles/writer.md) | Writer leaves; Writer post family; Writer article family; Writer document family; Writer message family; Writer copy family; Writer script family; Writer craft and independent editorial QA; Japanese inspector |
| [Marketer](./docs/profiles/marketer.md) | Marketer strategy and browser drafts (Browser lease, Draft-only saving, Validation status) |
| [Creator broker shape](./docs/broker.md) | Broker shape (Assistant Client guides and retirement gates) |
| [Creator hands — overview](./docs/hands/overview.md) | Creator hands (v3, 2026-09) (Client model, Skill tree, The form (front matter is the only representation), Handoff message (Creator → hands, A2A or resident session alike), Media craft knowledge, Migration) |
| [Image hands (image-creator)](./docs/hands/image.md) | Image generation capabilities; Icon, emoji and mascot families; Reimagine family; Card family; Kit family |
| [Video hands (video-creator)](./docs/hands/video.md) | Ad family; Music-video family; Video authoring references; Tour family (Footage And Capture v3); Explainer-video family; Promotion family; Clip family |
| [Audio hands (audio-creator)](./docs/hands/audio.md) | Speech family (Character voices and performance direction); SFX family (Local Stable Audio 3 Medium runtime); Music family; Mix family |
| [Models, authentication and secrets](./docs/models-auth.md) | Models and fallback chains (Fable and the Max weekly pool, `agent.*` does not inherit from the root profile); Authentication inheritance; Secrets layering |
| [Gateway, tracking and status](./docs/operations.md) | Gateway as a persistent service; Tracking; Current state |
