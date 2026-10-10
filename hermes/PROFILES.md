# Profiles and design docs — index

How this machine runs several Hermes agents that cooperate: two **front doors** a
human talks to (the Assistant on Telegram/Discord, the Marketer bot), plus named
**worker** profiles they delegate to in the background (Creator, Writer,
Researcher, Searcher and the three media hands image-creator, video-creator and
audio-creator). A profile is a separate `HERMES_HOME`
(`~/.hermes/profiles/<name>/`) with its own `config.yaml`, `SOUL.md`, skills and
state; the default profile is `~/.hermes` itself.

This is the one index of the documentation. Start with
[`README.md`](./README.md) (entry point and commands) and
[`AGENTS.md`](./AGENTS.md) (rules for editing). Section names in the docs are
stable, so a pointer such as `docs/topology.md "Toolsets"` keeps resolving.

## Design docs (`docs/`) — what each one decides

| Doc                                                                                          | Covers                                                                                                        |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| [Topology](./docs/topology.md)                                                               | gateway and A2A graph, the profile roster, toolsets, how entry skills load, candidate rollout and cutover     |
| [Specialist calls](./docs/profiles/specialist-calls.md)                                      | `specialist_call` / `specialist_session`: completion, deadlines, ownership, work continuity, failure handling |
| [OpenCode runtime](./docs/opencode.md)                                                       | who runs code work, the plugin, roles and models, rendered-UI checks                                          |
| [Assistant](./docs/profiles/assistant.md)                                                    | quality gate, visual design, creative early delivery, entry routing, pinned Telegram topics                   |
| [Researcher and Searcher](./docs/profiles/research.md)                                       | research and search dialogue, entries and status                                                              |
| [Writer](./docs/profiles/writer.md)                                                          | the writing leaf families, craft and independent editorial QA, the Japanese inspector                         |
| [Creator](./docs/profiles/creator.md)                                                        | Creator as creative advisor: entries, boundaries, model                                                       |
| [Marketer](./docs/profiles/marketer.md)                                                      | Marketer as strategy advisor: read-only toward services, browser lease, what outlasts a conversation          |
| [Hands commissioning](./docs/broker.md)                                                      | who does what between Assistant, Creator and hands; references each side owns; approvals, budget, consent     |
| [Hands overview](./docs/hands/overview.md)                                                   | skill tree, the form, handoff message, media craft knowledge, vision window                                   |
| [Image hands](./docs/hands/image.md)                                                         | image-creator families: generation, icon/emoji/mascot, reimagine, card, kit, diagram, pixel art, illustration |
| [Video hands](./docs/hands/video.md)                                                         | video-creator families: ad, music video, tour, explainer, promotion, story, master, clip, pixel animation     |
| [Audio hands](./docs/hands/audio.md)                                                         | audio-creator families: speech and character voices, SFX, music, mix                                          |
| [Models, authentication and secrets](./docs/models-auth.md)                                  | model and fallback chains, Console credit lanes, authentication inheritance, secrets layering                 |
| [Gateway and tracking](./docs/operations.md)                                                 | the gateway LaunchAgent mechanics and what is tracked                                                         |
| [Session history](./docs/session-history.md)                                                 | reading past OpenCode and Hermes sessions                                                                     |
| [Workspace drafts](./docs/workspace-drafts.md), [Workspace repos](./docs/workspace-repos.md) | the read-only workspace reports                                                                               |

## Access plugins (`docs/`)

Shared contract first: [Access plugins — common contract](./docs/access-common.md)
(risk acceptance, secret scoping, approval gate, bypass guard, shared setup).
Each doc then holds only its own deltas.

[Google](./docs/google-access.md) · [WhatsApp](./docs/whatsapp-access.md) ·
[Signal](./docs/signal-access.md) · [Discord](./docs/discord-access.md) ·
[Telegram](./docs/telegram-access.md) · [X](./docs/x-access.md) ·
[note](./docs/note-access.md) · [Substack](./docs/substack-access.md) ·
[YouTube](./docs/youtube-access.md) · [Web3](./docs/web3.md)

## Mechanics (`docs/ops/`)

| Doc                                            | Covers                                                                                         |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| [Install](./docs/ops/install.md)               | installing the binary, secrets mechanics, the tailnet dashboard, capabilities and dependencies |
| [Tracking](./docs/ops/tracking.md)             | what is tracked vs ignored, profiles and adopting one, cron                                    |
| [Skills](./docs/ops/skills.md)                 | skill placement, skills, worker terminal approvals                                             |
| [Plugins](./docs/ops/plugins.md)               | enabling plugins, groups, media-stack configuration                                            |
| [Services](./docs/ops/services.md)             | LaunchAgents, launchers, engine scripts, work continuity                                       |
| [Local TTS engines](./docs/ops/tts-engines.md) | Qwen3-TTS and Irodori-TTS runtimes and voice registration                                      |
| [Audio tooling](./docs/ops/audio-tooling.md)   | speech-to-text chain, audio hands tooling, Stable Audio runtime                                |
| [Web search](./docs/ops/web-search.md)         | backends and tier pinning                                                                      |
| [Browser](./docs/ops/browser.md)               | the per-profile Brave clone and attach                                                         |

## Decisions (`docs/decisions/`)

Short records of why a design was fixed, for rules whose reason would otherwise
look arbitrary:
[Creator family model split](./docs/decisions/creator-family-model-split.md) ·
[Explainer structure approval](./docs/decisions/explainer-structure-approval.md) ·
[Storyboard vocabulary stays rule-free](./docs/decisions/storyboard-vocabulary-rule-free.md).
