<GlobalAgentInstructions>
<LanguagePolicy>

Always reply in the language the user used in their latest message, or the
language they explicitly request. This applies to explanations and user-facing
communication; code and identifiers stay as-is.

</LanguagePolicy>

<QuestionQuality>

Questions to the user must be answerable in ~30 seconds without opening code.
Never make a bare file/line reference the subject of a question — summarize
what that code does in plain language. Phrase options as behavior/outcomes
with a recommended default; for non-blocking details, proceed on the default
and report it.

</QuestionQuality>

<PlanHandoff>

When a plan is aligned in Plan mode, register it as todos shaped
`Phase{N}.{m} - <task> (executor)` — Phase = dependency wave, {m} = reference
id within the phase (no ordering implied), executor = Build | worker |
reviewer | verifier | debugger | ui-review (default Build; worker only for
mechanical work) — then switch to Build. Build executes phases in order,
delegates per the executor tag, and updates todo statuses as it goes.

</PlanHandoff>

<SkillRouting>
<ApproachSkills>

For non-trivial or ambiguous work, load the matching approach-* scenario skill
before designing:

- Add a feature or capability to an existing system → `approach-new-feature`
- Rebuild, restructure, or schema/data migration → `approach-rebuild-migration`
- Improve structure without changing behavior → `approach-refactor`
- Resolve a performance problem → `approach-performance`
- Persist a durable, cross-session plan on GitHub Projects (layers on any of
  the above) → `approach-github-projects`

Refactor vs rebuild: behavior stays identical and the change is incremental →
`approach-refactor`; the system or its data is replaced or moved wholesale →
`approach-rebuild-migration`. Bugs, regressions, failing tests, and root-cause
work belong to `debug` / `debugger`, not these skills. Generic planning that
matches no scenario stays with the Plan agent's default behavior. Skip these
skills for small, well-specified, single-step tasks.

</ApproachSkills>

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

<UxPersonaTestingSkill>

When asked to test UI/UX as users would experience it — persona testing,
usability testing, hostile/reluctant/involuntary/novice user simulations, or
separating "computer hate" noise from real UX defects — load and follow the
`ux-persona-testing` skill. Personas run in the `ux-persona` subagent (never
in the primary session); triage stays in the primary per the skill's rubric.

</UxPersonaTestingSkill>

<JapaneseWritingSkill>

When writing Japanese-language deliverable text — documentation, README, code
comments, commit messages, PR bodies, UI copy, release notes — load and follow
the `japanese-writing` skill for typography, terminology, and style
consistency. It does not apply to conversational replies (LanguagePolicy
governs those) or to i18n/translation-file workflows.

</JapaneseWritingSkill>
</SkillRouting>

<ExplorationDelegation>

For read-only codebase exploration, prefer the built-in `task` tool with the
matching explore-* tier:

- `explore-spark` — ONLY when the scope is pre-identified and narrow (specific
  files/dirs or a single symbol). Small context: never send it open-ended
  queries.
- `explore-small` — trivial lookups: find files, symbols, config keys, simple
  keyword search.
- `explore-medium` — standard exploration: multi-file traces, "how does X
  work?" questions.
- `explore-high` — hard or ambiguous questions where explore-medium falls
  short.
- `explore-max` — only for difficult, high-stakes, or previously failed
  exploration.

These agents are pinned to OpenAI models. Use the default `explore` subagent
only when the primary model is specifically needed for the exploration.

</ExplorationDelegation>

<ResearchDelegation>

For web research — external docs, library/API behavior, versions, changelogs,
advisories, best practices, current events — prefer the built-in `task` tool
with subagent_type `searcher` (fast sweeps, fact checks) or `searcher-deep`
(settling one topic: conflicting sources, primary-source verification). These
agents run on the Grok subscription tier and absorb bulky web-page tokens;
avoid running `websearch`/`webfetch` in the primary session except for a
single user-provided URL. Codebase questions stay with the explore-* agents;
never put secrets, private code, or internal identifiers into delegated
queries. For multi-question research sessions, the `deepsearch` primary mode
orchestrates both.

</ResearchDelegation>

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
