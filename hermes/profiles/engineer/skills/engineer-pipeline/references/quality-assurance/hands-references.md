# Hands option-backed references

Judge a hands option-backed reference change against the agreed scope in
[Plan](../plan/hands-references.md), not a generic diff review. Reference the
candidate Skill's Verify section
(`opencode/skills/hermes/hands-references/SKILL.md`, hermes-hands-references)
for the actual checks. Read it directly if not in Hermes discovery; it does not
need to become a second Hermes Skill. Engineer independently inspects the diff,
audit and supporting evidence rather than accepting OpenCode's summary alone.

1. Confirm the diff stays inside the agreed scope and required consumers: no drive-by rewrite of
   sibling catalogs, no new registry/menu/preset layer, no PROFILES.md/
   AGENTS.md edit beyond an actually changed contract.
2. Re-run the scoped audit, then the whole-hands audit for cross-leaf drift;
   report pre-existing warnings separately from new ones. From the candidate's
   hermes/ directory, run `python3 scripts/validate-profile-skills.py --all`
   using the documented Hermes environment. Inspect trusted adapter code before
   an audit import; this is not a sandbox. Do not install missing dependencies.
3. Inspect the named test results, skips and their candidate revision. Re-run
   only bounded checks whose side effects were inspected and authorized, with
   the documented Hermes venv and --import-mode=importlib. Do not blindly run
   the whole plugin suite, restart services or regenerate media for acceptance.
4. For card CSS/geometry changes inspect the actual approved-scope scratch
   render and readback, not just metadata. Missing render evidence is UNVERIFIED;
   obtain scope for any additional execution. Prose forward tests prove only
   instruction following, not generated-media quality or platform correctness.
5. Check changed frontmatter fits the discovery prefix and references remain
   reachable from their owning leaf. References are not separate skills-list
   entries. Structural success does not prove fresh-session loading or factual
   accuracy; report those checks separately, without live-link cutover.
6. Verdict under the normal [Quality assurance](index.md) contract: accept,
   request corrections through [Build](../build/hands-references.md), or
   return a scope decision to the Client.
