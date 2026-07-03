<GlobalAgentInstructions>
<LanguagePolicy>

Always reply in the language the user used in their latest message, or the
language they explicitly request. This applies to explanations and user-facing
communication; code and identifiers stay as-is.

</LanguagePolicy>

<SkillRouting>
<ApproachSkill>

Use the `approach` skill for non-trivial or ambiguous work: planning something
new, adding a capability, deciding where to start, restructuring, migrating, or
any "how should I approach this?" style task. Skip it for small,
well-specified, single-step tasks.

</ApproachSkill>

<DependabotSkill>

When asked to triage, resolve, or fix GitHub Dependabot security alerts
(GHSA/CVE, "security alert", "dependabot"), load and follow the
`resolve-dependabot-alerts` skill rather than hand-fixing.

</DependabotSkill>

<CommitSkill>

When asked to create git commits — staging, splitting changes into atomic
build-passing commits, writing commit messages, or tracing which
commit/PR/Issue a change came from — load and follow the `git-commit` skill
rather than committing ad hoc.

</CommitSkill>

<PullRequestSkill>

When asked to open, push, or update a GitHub pull request — pushing a branch,
creating a PR whose title and body match the repo, scanning the branch for
related Issues/PRs to link, or marking it ready — load and follow the
`git-pullrequest` skill. It does not create commits (use `git-commit`) and does
not merge.

</PullRequestSkill>
</SkillRouting>

<ExplorationDelegation>

For read-only codebase exploration, prefer the `explore-small` (trivial
lookups) or `explore-high` (anything harder) subagents. Use the default
`explore` subagent only when the primary model is specifically needed for the
exploration.

</ExplorationDelegation>

<ImplementationDelegation>

When a change is well-specified and mechanical — bulk edits, boilerplate,
rote refactors, applying an already-decided design — delegate it to the
`worker` subagent with an exact spec instead of doing it in the primary
session. Keep design decisions, ambiguous work, and difficult code in the
primary. Before commits of non-trivial changes, consider a read-only pass by
the `reviewer` subagent.

</ImplementationDelegation>

<QuotaAwareRouting>

Model pools: the primary session runs on the Claude Max pool (scarcest);
default subagents (`explore-*`, `worker`, `reviewer`) run on the z.ai Coding
Plan pool; OpenRouter is pay-per-use and a last resort.

Check quota BEFORE delegating, so subagents are not launched into an
exhausted pool:

    npx -y @slkiser/opencode-quota show

Run this check before the FIRST subagent delegation of the session, and
remember the result. Re-run it only when the last check is stale (roughly an
hour old), before kicking off a large batch of subagent work, or after any
subagent fails with a rate-limit/quota error despite the check.

Routing by the result (a pool is exhausted when ANY of its active windows —
e.g. the 5h or weekly window — is at 0% left):

- z.ai has quota (default): use `explore-small` / `explore-high` / `worker` /
  `reviewer`.
- z.ai exhausted or down: use the Claude-pool mirrors `explore-small-claude`
  (Haiku), `explore-high-claude` (Sonnet), `worker-claude`,
  `reviewer-claude` (Sonnet).
- Anthropic quota unknown ("Unavailable / not detected") counts as available;
  fall back to it freely when z.ai is exhausted.
- Both pools exhausted: stop delegating; do the work directly in the primary
  session and tell the user, who may switch the primary model to an
  `openrouter/...` model manually via `/model`.

Never route subagents to OpenRouter models on your own initiative.

</QuotaAwareRouting>
</GlobalAgentInstructions>
