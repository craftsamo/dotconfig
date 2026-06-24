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

For read-only codebase exploration, prefer the `explore-small` (trivial),
`explore-high` (hard), or `explore-max` (hardest) subagents. Use the default
`explore` subagent only when the primary model is specifically needed for the
exploration.

</ExplorationDelegation>
</GlobalAgentInstructions>
