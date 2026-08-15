# CLAUDE.md (global)

<!--
  Rebuilt 2026-06-11: the previous version was lost
  (symlink target was deleted before ever being committed).
  Add global instructions for Claude Code below.
-->

## Skill authoring

When the user explicitly asks to create or update an Agent Skill, skill
directory, or `SKILL.md`, load and follow the shared `skill-authoring` Skill.
Do not load or combine any bundled or plugin-provided `skill-creator` for that
request. Do not use either Skill merely because a workflow appears repetitive.
