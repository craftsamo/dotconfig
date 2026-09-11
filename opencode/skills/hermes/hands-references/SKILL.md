---
name: hermes-hands-references
description: >-
  Use when assessing, adding or improving option-backed references in Hermes
  image-creator, video-creator or audio-creator hands leaves: styles, themes,
  destination, packs, contents and similar local catalogs. Includes reference
  audits and incorporating observed evidence. Not producing media, creating
  new leaves/families, retiring options, Writer references, Creator broker
  references or Assistant guides.
license: MIT
compatibility: OpenCode maintaining this dotconfig repository; Python with PyYAML and the Hermes test environment.
---

<Goal>

Maintain the selected hands leaf's reference knowledge and its actual consumers,
not a second catalog of all profiles. Assess without edits; add or improve only
the released scope. Engineer's mode guides own Client dialogue and independent
acceptance; this Skill owns the maintenance procedure, including direct OpenCode
requests. This repository uses grouped Skill paths, like git/commit: the logical
name here is hermes-hands-references at hermes/hands-references.

</Goal>

<Scope>

- Positive: add a paper-cut style to generate-icon; incorporate supplied
  four-image X observations in create-card's x-carousel reference; assess missing
  option backing across the three hands before deciding what to improve.
- Negative: create an OG card using paper; change Creator's Plan card guidance;
  improve Writer article references; add a new media family; retire a style.
  Those use their own production, broker, authoring or migration workflows.
- An audit request is not permission to repair. A single task-local custom look
  is not permission to promote it into the managed style catalog.
- If the target is unspecified, ask which capability or outcome needs improving.
  Offer a bounded read-only inventory, not a speculative rewrite of every profile.

</Scope>

<Locate>

1. Resolve the selected dotconfig checkout or task worktree. Read its AGENTS.md,
   hermes/AGENTS.md, and the relevant Creator hands sections of hermes/PROFILES.md.
   Inspect Git status and the real paths before any edit. Paths below are relative
   to that checkout, never hardcoded to the live ~/.config or ~/.hermes tree.
2. Locate hermes/profiles/<hands>/skills/<hands>-pipeline/<verb>/<subject>/SKILL.md
   for image-creator, video-creator or audio-creator. Read its form, Procedure, QA,
   chosen references and representative siblings. Trace script consumers and
   callers; do not assume every Markdown file is prose.
3. For option backing follow validate_hands_form in
   hermes/scripts/validate-profile-skills.py: style maps to styles, theme to
   themes, other fields to their field name. Style always requires backing;
   other option fields require it when their conventional directory exists or
   the field declares references. That declaration is currently a presence
   marker in the validator, not an arbitrary glob resolver. Do not invent a
   different mapping or duplicate another leaf's canonical reference locally.
4. Inspect related options, body links, scripts, tests and current history.
   Establish the intended change, evidence and checks before editing. Shared
   vocabulary is a dependency to inspect, not a rule that all verbs must have
   identical catalogs. Do not create a registry, generated menu or shared Styles
   layer. Read machine-env when platform ownership or live configuration matters.

</Locate>

<Assess>

Run the repository-owned audit from the candidate root using a Python environment
with PyYAML already installed (normally the Hermes venv):

```sh
python3 hermes/scripts/audit-hands-references.py --root . --json
```

For a bounded leaf, add --leaf with its repo-relative directory, for example:

```sh
python3 hermes/scripts/audit-hands-references.py --root . --leaf hermes/profiles/image-creator/skills/image-creator-pipeline/create/card --json
```

Exit 0 means no structural errors, not no findings or verified quality. Exit 1
means errors; exit 2 means invalid invocation. Missing dependencies are a blocker,
not permission to install them. The audit reads the candidate's trusted card.py
adapter through importlib, without rendering or bytecode writes; it is NOT a
sandbox for untrusted Python. Inspect unfamiliar adapter code before executing it.

Classify missing/empty backing and invalid structures separately from orphan
candidates or missing loading links. A supporting file can be legitimate even if
it is not an option. Do not delete it to clear a warning. Review prose for actual
contradictions, selection guidance and missing evidence; matching headings alone
prove nothing. An UNVERIFIED label is useful uncertainty, not inherently a defect.
Return evidence-backed findings and proposed scope, with no automatic repairs.

</Assess>

<Classify>

| Reference | Contract and verification |
| --- | --- |
| create/card/references/destination/*.md | Runtime scalar metadata read by card.py, not general YAML. width, height, status are required; display_width_css_px and display_gap_css_px form a pair. Tile variants and geometry follow destination(). |
| create/card/references/styles/*.md | Exactly one fenced css block, with the three #rrggbb palette roles --surface, --ink, --accent. css_style() owns the selector/property restrictions; read references/spec.md rather than copying the allowlist here. |
| generate/card/references/styles/*.md | Backdrop prompt prose, never a duplicate of composition CSS. Inspect the paired create/generate style options and update both when extending their shared named vocabulary. |
| Other hands catalogs | Model-facing guidance unless tracing proves a runtime reader. Follow useful sibling conventions: Look/Prompt/Avoid/QA cues, reimagine's explicit Medium, pack/content tables or subject-specific technical notes. Their prose can still describe implemented limits; check that implementation. |

Card geometry has named branches for x-pair/x-carousel. A new tiled destination
needs implementation work, not just metadata. Likewise, a style outside the
renderer contract needs an explicit capability change. Return that scope for
approval instead of changing the helper or documenting unsupported behavior.
Do not infer any platform upload limit or crop guarantee from an authoring canvas.

</Classify>

<Add>

1. Confirm the new option's distinct purpose and supported behavior. Preserve
   free-text/custom routes; do not silently replace a described look with a named
   approximation. Author only the requested references, using concrete cues and
   applicable constraints rather than generic aesthetic adjectives.
2. Add the backing file and its form option together, plus a real loading pointer
   in the leaf Procedure. Preserve existing names/semantics and metadata parsing
   limits. Inspect consumers of the same vocabulary, not just the edited leaf.
3. For card destinations, inspect create-card's options and body links,
   generate-card's destination label and test_card.py's expected dimensions.
   For card styles, inspect both leaves' options/body links, the CSS/prose pair,
   and the style test cases. Do not assume current lists are dynamically derived.
4. Change broker guidance, PROFILES.md or AGENTS.md only when their actual contract
   or statement changes. Mere addition of an option needs no per-option broker
   file, new Skill, profile, toolset or secret.

</Add>

<Improve>

Start from the reported limitation, supplied evidence or an observed failure.
Preserve already-effective prose; do not normalize an entire family for symmetry.
Separate authoring defaults, user observations, official documentation and unknowns.
For factual updates record source, observation date, relevant environment and
limits of inference. Do not broaden a single post/device observation into a
universal rule or remove qualifications merely to sound confident.

For a status change, read the current status vocabulary and actual consumers;
retain unverified portions explicitly. Research public primary sources only as
needed. No test posts, authenticated browsing, uploads or paid generation without
their own authorization. Supplied examples are evidence, not licensed production
assets or consent. Do not edit frozen job files or reinterpret saved specifications.

If a discovered defect belongs to scripts, approval gates or platform policy,
report the dependency and obtain scope for that change; reference prose cannot
repair runtime behavior. Retirement and renaming are outside this workflow.

</Improve>

<Verify>

1. Re-run the scoped audit, then the whole-hands audit to expose cross-leaf drift.
   Report pre-existing warnings separately. Neither warnings nor UNVERIFIED
   labels authorize unrelated fixes.
2. From hermes/, run python3 scripts/validate-profile-skills.py --all using the
   documented environment. Run the relevant tests with the Hermes venv and
   --import-mode=importlib per hermes/AGENTS.md. At minimum check
   scripts/tests/test_audit_hands_references.py and
   scripts/tests/test_validate_profile_skills.py; card changes additionally use
   scripts/tests/test_card.py. Inspect configured skip gates: a skipped renderer
   test is not a rendered pass.
3. For card CSS/geometry changes, exercise a minimal approved-text spec through
   the candidate's card.py create into a NEW scratch output bundle and inspect
   the actual image for style, text readback and bounds. Use installed local
   rendering tools and safe fixtures only. Missing tools mean visual validation
   is UNVERIFIED, not permission to install, spend or claim full validation.
   For prose catalogs, forward-test the changed instructions in fresh context;
   separate instruction-following evidence from actual generated-media quality.
4. Keep the complete changed hands frontmatter within Hermes' first 4,000-character
   discovery window, with margin. Use actual discovery to check leaf names if
   metadata changed. Plain reference files do not appear as separate skills:
   verify their routes and fresh-session loading, not skills-list entries.
5. Inspect diff and Git ownership in the actual candidate. Do not run install.sh,
   restart a gateway, merge or redirect live symlinks as validation. A branch in
   the live symlink-backed checkout is NOT runtime isolation: edits can already
   be visible to new reads. Use a task worktree for isolation; live cutover needs
   its own explicit release and the documented linking procedure.

</Verify>

<Report>

Return the selected leaf/field, added or changed options, consumers updated,
factual sources, checks with results/skips, remaining warnings and next decision.
Assessment ends with findings, not changes. Implementation reports what was
actually verified, never cosmetic confidence scores. Commit or PR only when the
current caller authorized it, using git-commit / git-pullrequest; Engineer's
approved task-branch delivery contract does not grant merge or live cutover.

</Report>
