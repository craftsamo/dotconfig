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

<WebUiSkill>

When implementing or modifying web frontend UI — pages, components, layout,
styling, visual states — load and follow the `web-ui` skill. UI work is not
done until the real rendering has been verified with `agent-browser`
screenshots; code-only inspection is not verification.

</WebUiSkill>
</SkillRouting>

<ExplorationDelegation>

For read-only codebase exploration, prefer the built-in `task` tool with
subagent_type `explore-small` (trivial lookups) or `explore-high` (anything
harder). Use `explore-max` only for difficult, ambiguous, or high-stakes
exploration. These agents are pinned to OpenAI models. Use the default
`explore` subagent only when the primary model is specifically needed for the
exploration.

</ExplorationDelegation>

<ImplementationDelegation>

When a change is well-specified and mechanical — bulk edits, boilerplate,
rote refactors, applying an already-decided design — run it through the built-in
`task` tool with subagent_type `worker` and an exact spec instead of
doing it in the primary session. Keep design decisions, ambiguous work, and
difficult code in the primary. Before commits of non-trivial changes, consider a
read-only pass through `task` with subagent_type `reviewer`.

</ImplementationDelegation>

<DebuggingDelegation>

For bugs, regressions, failing tests, runtime errors, incidents, and root-cause
questions, prefer the built-in `task` tool with subagent_type `debugger` for
read-only diagnosis. The `debugger` subagent owns reproduction, isolation,
root-cause evidence, fix direction, and verification recommendations.

Use `verifier` only for routine tests, typechecks, lint, builds, and failure-log
summarization. Use `build` to implement fixes after diagnosis. `debug` and
`debugger` do not edit files.

</DebuggingDelegation>

<UiReviewDelegation>

For unbiased visual critique of substantial web UI work — new pages,
restyles, or "the design looks bad" complaints — prefer the built-in `task`
tool with subagent_type `ui-review` after your own render check passes. It
captures multi-viewport screenshots with `agent-browser` (absorbing the image
tokens) and returns a severity-ranked critique with measurements and
screenshot paths. Apply fixes in the primary, then re-invoke with the same
`task_id` to confirm. Keep quick single-screenshot checks inline; `ui-review`
does not edit files.

</UiReviewDelegation>

<VerificationDelegation>

For routine verification chores — tests, typechecks, lint, format checks,
builds, and summarizing failure logs — prefer the built-in `task` tool with
subagent_type `verifier`. Give it exact commands when known. Keep root-cause
analysis and design decisions in the primary session when failures are
non-obvious or require code changes.

</VerificationDelegation>

</GlobalAgentInstructions>
