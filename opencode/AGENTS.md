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

For read-only codebase exploration, prefer the `delegate` tool with role
`explore-small` (trivial lookups) or `explore-high` (anything harder). Use the
built-in `task` tool only if `delegate` is unavailable or explicitly requested.
Use the default `explore` subagent only when the primary model is specifically
needed for the exploration.

</ExplorationDelegation>

<ImplementationDelegation>

When a change is well-specified and mechanical — bulk edits, boilerplate,
rote refactors, applying an already-decided design — delegate it through the
`delegate` tool with role `worker` and an exact spec instead of doing it in the
primary session. Keep design decisions, ambiguous work, and difficult code in
the primary. Before commits of non-trivial changes, consider a read-only pass
through `delegate` with role `reviewer`.

</ImplementationDelegation>

<QuotaAwareRouting>

Model pools: the primary session usually runs on the Claude Max pool
(scarcest). Delegated subagents should run through the `delegate` custom tool,
which chooses OpenAI Pro or Claude by budget tier and quota. OpenRouter is
pay-per-use and a last resort.

When using `delegate`, do NOT run a separate quota check first; the tool checks
quota and retries quota/rate-limit failures on the fallback provider. Check
quota manually only when using the built-in `task` tool directly:

    npx -y @slkiser/opencode-quota show

Run this check before the FIRST subagent delegation of the session, and
remember the result. Re-run it only when the last check is stale (roughly an
hour old), before kicking off a large batch of subagent work, or after any
subagent fails with a rate-limit/quota error despite the check.

`delegate` budget tiers:

- `auto`: default; the tool chooses from the role.
- `small`: fast/cheap lookup profile.
- `medium`: normal implementation or search profile.
- `high`: stronger model + deeper reasoning for review/debug/design-adjacent work.
- `max`: last resort for failed retries or critical review.

Direct `task` fallback rules, if `delegate` is unavailable: when OpenAI Pro has
quota, use `explore-small` / `explore-high` / `worker` / `reviewer`; when it is
exhausted, stop delegating and do the work in the primary session or ask the
user to switch model/provider. The old `*-claude` mirror agents are not present;
provider fallback is centralized in `delegate`.

Never route subagents to OpenRouter models on your own initiative.

</QuotaAwareRouting>
</GlobalAgentInstructions>
