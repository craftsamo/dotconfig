# AGENTS

<!-- Global instructions for opencode. Add rules below. -->

## Rules

1. **Respond in the user's language.** Always reply in the language the user
   used in their latest message, or the language they explicitly request. This
   applies to all explanations and communication (code and identifiers stay as-is).

2. **Use the `approach` skill for non-trivial work.** When a task is non-trivial
   or ambiguous — planning something new, adding a capability, deciding where to
   start, restructuring, migrating, or any "how should I approach this?" — load
   and follow `@opencode/skills/approach/SKILL.md`. Skip it for small,
   well-specified, single-step tasks.

3. **Resolve Dependabot alerts via its skill.** When asked to triage or fix
   GitHub Dependabot security alerts (GHSA/CVE), load and follow
   `@opencode/skills/resolve-dependabot-alerts/SKILL.md` rather than hand-fixing.

4. **Offload codebase exploration to GLM.** For read-only codebase exploration,
   prefer the `explore-small` (trivial), `explore-high` (hard), or `explore-max`
   (hardest) subagents — they run on GLM to conserve Claude quota. Use the
   default `explore` (which inherits the primary model) only when you
   specifically need the primary model for exploration.
