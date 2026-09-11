---
name: opencode-env
description: Inspect this machine's OpenCode configuration, agent/skill capabilities and authentication boundary when Engineer's proposal depends on them or a run behaves unexpectedly. An environment map, not an alternative CLI execution workflow.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: technic
    tags: [opencode, environment, inspection]
---

<Goal>

Know the configured executor, not a memorized roster. OpenCode owns its coding
methods, internal agents and repository conventions. Engineer's pipeline owns
Client decisions and the opencode_call transport; this skill is only a map.

</Goal>

<ConfigMap>

| Source | Meaning |
| --- | --- |
| `~/.config/opencode/opencode.jsonc` | Provider/agent defaults, plugins, permissions, MCP and custom-tool grants |
| `~/.config/opencode/agent/*.md` | Installed primary/subagent definitions and model/permission overrides |
| `~/.config/opencode/AGENTS.md` | Global skill routing and delegation rules |
| `~/.config/opencode/skills/` | OpenCode-specific skills, including nested approach/Git groups |
| `~/.agents/skills/` | Shared/external skill discovery; ownership varies, not all are repo-managed |
| Target repository instructions | Local structure, test commands, conventions and constraints |
| Engineer config `opencode_cli` | Wrapper enablement/deadline and optional per-agent model override |

Read needed configuration with file tools, never dump credential stores, process
environment or resolved provider configurations containing secrets. JSONC is not
plain JSON. A missing catalog entry is not evidence of a broken provider.

</ConfigMap>

<IntentCatalog>

Verify these installed names before relying on them; pass intent, not copied
Skill procedures, to OpenCode.

| Work | Existing OpenCode capability |
| --- | --- |
| Feature | approach-new-feature |
| Behavior-preserving cleanup | approach-refactor |
| Replacement/migration | approach-rebuild-migration |
| Performance | approach-performance |
| Security alerts | resolve-dependabot-alerts (within the released authority) |
| Diagnosis/review | debug/review primary through the wrapper |
| Commits/PRs | git-commit / git-pullrequest |

The migrated UI design/visual-review/persona workflows belong to Engineer and
its Hermes evaluators. They are not OpenCode global skills/subagents anymore.
OpenCode still implements UI and runs project/browser tests. Do not reintroduce
the removed workflows as aliases, fallback agents or copied prompts.

</IntentCatalog>

<Inspection>

Use opencode --version or run --help only for harmless capability inspection;
actual execution uses the wrapper. Read the specific agent/skill/instruction
file for its contract. Git history can explain a changed configuration.
Models follow configured defaults, not a fixed ladder duplicated in this Skill.
OpenCode-specific model aliases may not be valid Hermes provider model names.

Authentication is separate from Hermes' own account; see machine-env. Do not
re-login, change providers or retry a failed/uncertain build as an auth workaround.
Inspect the scoped result first, preserve partial effects and ask on changes to
account/cost/authority. Never infer capacity from an unavailable quota display.

</Inspection>
