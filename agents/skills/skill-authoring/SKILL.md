---
name: skill-authoring
description: >-
  Use ONLY when the user explicitly asks to create or update an Agent Skill,
  skill folder, or SKILL.md (create a skill, add a skill, update this skill,
  improve this SKILL.md, Skill を作る, Skill 化して, スキルを追加, スキルを更新).
  Investigates the target repository and comparable skills, grounds the design
  in concrete trigger and non-trigger examples, resolves ownership and
  placement, writes only the necessary files, and validates the finished
  skill. Do NOT use merely because a workflow appears repetitive, to
  proactively suggest skill creation, or for general prompt, agent, command,
  plugin, or documentation authoring.
license: MIT
---

<Goal>

Create or update the specific Agent Skill the user requested. Ground it in the
real workflow, repository, and client environment so another agent can follow
it without reconstructing missing intent. Produce a complete skill, not a
generic template or a folder of unresolved placeholders.

</Goal>

<Scope>
<UseWhen>

- The user explicitly asks to create, add, write, capture, or implement an
  Agent Skill or `SKILL.md`.
- The user explicitly asks to update, correct, narrow, or improve an existing
  Agent Skill.
- The user explicitly asks to turn a named workflow from the current
  conversation into a Skill.

</UseWhen>
<DoNotUseWhen>

- A repeated workflow is merely observed. Repetition is useful evidence after
  an explicit request; it is never permission to create a Skill.
- The user asks for a general prompt, always-on instruction, command, agent,
  plugin, MCP server, or ordinary documentation without asking for a Skill.
- The user asks only to use, explain, list, or review a Skill and does not ask
  to change it.

</DoNotUseWhen>
</Scope>

<ProjectFirst>

Resolve local rules before designing. Do not assume a client, discovery root,
folder layout, metadata extension, language, or validation command.

1. Read the applicable repository instructions (`AGENTS.md`, `CLAUDE.md`,
   `CONTRIBUTING.md`, and local equivalents) from the target directory upward.
2. Inspect the target client's configuration and Skill discovery paths when
   placement is not already documented.
3. Inspect nearby Skills, their resource layout, validation commands, and Git
   history. Prefer the repository's established pattern over a generic
   template.
4. Search all relevant discovery roots for the proposed name. Do not rely on a
   client's duplicate-name precedence.
5. Apply the portable Agent Skills contract only where local rules are silent:
   a skill directory containing exactly one root `SKILL.md`, with `name` and
   `description` frontmatter and Markdown instructions.

</ProjectFirst>

<IntentContract>

Before editing, establish these facts from the conversation, existing
artifacts, implementation, and history:

1. Job: the concrete task the Skill enables.
2. Triggers: realistic requests or contexts that should load it.
3. Near misses: similar requests that should not load it, including adjacent
   Skills or artifacts that should win instead.
4. Inputs and outputs: what the agent receives and what it must produce or
   change.
5. Operating constraints: required tools, dependencies, permissions, side
   effects, approval gates, and failure handling.
6. Completion evidence: the observable checks that prove the task was done.

Investigate before asking. If an unresolved fact materially changes behavior,
ask one short outcome-level question. If the request remains vague, do not
write a generic Skill to fill the gap. When all facts are recoverable from the
request and repository, proceed without requiring ceremonial approval.

</IntentContract>

<ArtifactBoundary>

Confirm that a Skill is the right artifact even when the user used the word
"skill":

- Skill: reusable procedural or domain knowledge that should load for a class
  of tasks.
- Always-on instructions: policy that must apply to every relevant session.
- Command: an explicitly invoked prompt with arguments and no discovery need.
- Agent: a distinct role, model, tool surface, or permission boundary.
- Script: deterministic execution that does not need model judgment.
- Reference documentation: information for people or occasional lookup, with
  no agent workflow.

If another artifact is clearly required, explain the behavioral mismatch and
ask before substituting it. Never silently turn a Skill request into another
artifact, and never create both as a hedge.

</ArtifactBoundary>

<Placement>

Choose the narrowest correct owner:

- Put project-specific behavior in the project's Skill tree.
- Put a user-level Skill in the user's shared tree only when its instructions
  are portable across the clients that discover it.
- Keep client-specific tools, subagents, permission models, and handoffs in
  that client's Skill tree.
- Keep runtime-learned or generated Skills in the environment's documented
  mutable area until its explicit promotion process is complete.

Use lowercase ASCII letters, digits, and single hyphens for `name`; keep it at
64 characters or fewer. Make it match the parent directory unless the target
client documents a different logical naming scheme for nested Skills. Prefer a
short action-oriented name. Namespace by product or tool when that prevents an
ambiguous trigger or collision.

</Placement>

<Design>

Match instruction freedom to task risk:

- Use heuristics and prose when several approaches are valid.
- Use pseudocode or parameterized scripts when one pattern is preferred but
  context still varies.
- Use a tested deterministic script and explicit gates when the operation is
  fragile, repetitive, or safety-critical.

Keep only resources that directly support the Skill:

- `SKILL.md`: trigger-independent core workflow, decisions, invariants, and
  completion gates.
- `references/`: detailed material read only for named conditions. Link every
  reference directly from `SKILL.md` and state when to read it.
- `scripts/`: deterministic work that would otherwise be rewritten. Test every
  included script with representative inputs.
- `assets/`: files copied or used in outputs but not intended as context.

Do not add a `README.md`, installation guide, quick reference, changelog, or
empty resource directory inside a Skill. Do not duplicate the same rule in the
body and a reference. Keep `SKILL.md` under 500 lines when practical; split
conditional detail before the core workflow becomes hard to scan.

</Design>

<DescriptionContract>

The `description` is the primary discovery surface. Put all information needed
to decide whether to load the Skill there, because the body is unavailable
until after selection.

- State what the Skill does and when it should be used.
- Front-load literal user phrases, filenames, formats, task names, and symptoms
  that distinguish it.
- Include adjacent exclusions when a keyword would otherwise over-trigger it.
- Use `Use ONLY when` when explicit invocation or a narrow safety boundary is
  part of the contract.
- Keep it between 1 and 1024 characters and useful if a client truncates the
  end.

Draft realistic positive and negative requests before finalizing the
description. Negative requests must be plausible near misses, not unrelated
easy cases.

</DescriptionContract>

<WritingContract>

Write for a fresh capable agent that knows general software engineering but
does not know this workflow.

- Use imperative instructions and concrete nouns.
- Specify inputs, outputs, decision points, side effects, error handling, and
  verification where they matter.
- Explain non-obvious reasons that help the agent generalize; do not restate
  common knowledge to make the Skill look complete.
- Replace vague instructions such as "follow best practices", "handle edge
  cases", or "verify carefully" with the relevant decision or check.
- Name the exact resource or command at the step where it is needed.
- Keep examples realistic but do not overfit the rules to one example.
- Leave no scaffold prose, placeholder files, `[TODO]`, or unresolved design
  alternatives in the finished Skill.
- Preserve the target repository's language and style conventions.

</WritingContract>

<Workflow>

1. Confirm that the user explicitly requested Skill creation or modification.
2. Locate the target repository, applicable instructions, discovery paths, and
   existing Skill if this is an update.
3. Reconstruct the real workflow from the conversation, implementation,
   documentation, tests, and history. Inspect comparable Skills and adjacent
   responsibilities.
4. Establish the <IntentContract>. Ask one focused question only when
   investigation cannot settle a behavior-changing gap.
5. Confirm the <ArtifactBoundary>, owner, placement, name, and trigger boundary.
6. Choose the minimum `SKILL.md`, references, scripts, and assets needed by the
   <Design> rules.
7. Create or edit the files directly. Do not generate a generic scaffold and
   fill it by guesswork.
8. Run the repository's own Skill validator when one exists. Also run this
   Skill's read-only validator from the `skill-authoring` directory:

   ```sh
   uv run scripts/validate.py <target-skill-directory>
   ```

9. Fix every error and judge every portability warning against documented
   local rules. Record any intentional client-specific exception in the result.
10. Test bundled scripts and run the target repository's relevant checks.
11. Forward-test the Skill on representative requests when feasible. Use fresh
    context, pass source artifacts rather than intended answers, and include a
    near miss that must not trigger.
12. Verify discovery and ownership: inspect Git ignore/tracking state, install
    or link the Skill through the documented mechanism, and report any client
    reload required.

</Workflow>

<UpdatingExistingSkills>

Preserve the existing name and directory unless the user explicitly requested
a rename. Start from the observed failure, requested behavior, or usage trace;
do not rewrite an effective Skill merely to impose this Skill's preferred
structure. Check every resource link and routing instruction affected by the
change, then rerun static validation and the smallest forward test that covers
the change.

</UpdatingExistingSkills>

<Verification>

A finished Skill satisfies all of these conditions:

- The request was explicit, and the result addresses that exact request.
- The job, inputs, outputs, triggers, near misses, constraints, and completion
  evidence are concrete.
- The name, directory, frontmatter, body, and local resource links validate.
- No placeholder or unnecessary auxiliary file remains.
- Bundled scripts were executed against representative inputs.
- A realistic positive request can follow the workflow without hidden context.
- A realistic near miss stays outside the Skill's responsibility.
- The Skill is visible in the intended discovery root and visible to Git when
  it belongs in version control.

</Verification>

<AntiPatterns>

- Creating or suggesting a Skill merely because a workflow repeated.
- Writing files before a vague purpose has concrete behavior and boundaries.
- Defaulting to a familiar client path without inspecting the target.
- Copying an installed creator Skill or external template instead of fitting
  the target repository.
- Hiding client-specific tools in a supposedly portable shared Skill.
- Treating a long checklist as evidence that a Skill is precise.
- Adding deterministic code without testing it.
- Declaring success after frontmatter validation without testing the workflow
  or its trigger boundary.

</AntiPatterns>
