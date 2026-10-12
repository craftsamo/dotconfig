---
name: git-pullrequest
description: >-
  Use when opening, pushing, or updating a GitHub pull request — rebasing the
  branch onto the latest base, pushing it, creating a PR whose title and body
  match the repository's own convention, marking it ready, preferring a native
  GitHub stack of PRs whenever the work splits into reviewable layers, setting
  labels, assignees, reviewers and milestones after judging what they trigger
  (ラベル, アサイン, レビュアー, マイルストーン), scanning the branch for related Issues and PRs to link,
  and following the PR's CI checks and review feedback (PR, pull request,
  プルリク, プルリクエスト, push, gh pr, open a PR, レビュー依頼, 関連Issue,
  related issues, link PR, stacked PR, gh stack, スタック, rebase onto main,
  最新の main を取り込む, CI, checks, CI の結果, チェックが落ちた, レビュー
  コメント, review comments). Resolves the PR title/body convention from merged
  PRs and a template, derives links from commits, the branch name and targeted
  gh queries, and defaults to ready-for-review. Do NOT use to create commits
  (use git-commit) or to merge — merging stays gated and explicit.
author: CraftSamo
license: MIT
---

<Goal>

Open or update the pull request the user asked for: rebase the branch onto its
base's latest state, push it, write a title and body that match the
repository's convention, link the related Issues and PRs the branch's work
actually touches, and follow its checks and reviews when asked. Never merge.

</Goal>

<Scope>
<UseWhen>

- The user asks to open, push, or update a pull request for the current branch.
- The user asks to mark a PR ready, or to refresh its title, body, links, or
  its labels, assignees, reviewers or milestone (<Metadata>).
- The user asks how a PR's checks or reviews stand, or to follow CI after a
  push (Step 10 alone).

</UseWhen>

<DoNotUseWhen>

- Creating commits or staging — use `git-commit`. This skill assumes the
  commits already exist and starts at push.
- Merging, closing, or approving a PR. Merging stays gated (`ask`) and happens
  only on explicit request.

</DoNotUseWhen>
</Scope>

<ConventionResolution>

Resolve the title and body format. Detect, do not assume.

1. Existing habit — call `git_history_digest` for recent merged PR titles and
   the branch's commit subjects; infer the title style (casing, whether a
   `type:` prefix is used, parentheticals) and the body structure.
2. Template — `git_history_digest` reports whether a PR template exists; if so,
   fill its sections instead of inventing structure.
3. Fallback — derive from the branch's commits (`git log <base>..HEAD`): a
   capitalized summary title and a Summary / Changes / Notes body.

- Treat PR titles as durable descriptions, but do not promise they become the
  landed commit subject. Squash-message defaults depend on repository settings
  and commit count; a one-commit PR may use its commit subject instead. Read the
  actual settings when explaining the expected result, never change them here.
- Title and body language follow the repo's merged-PR habit — infer it, never
  assume English.

</ConventionResolution>

<RelatedScan>

Find the Issues and PRs to link. Call `git_related_scan` (base defaults to the
repo's default branch; pass `keywords` to widen the search). It returns,
read-only:

- `existingPR` — the open PR for this branch, if any. Update it; do not duplicate.
- `closes` / `refs` — issue numbers from the branch's commit messages and name
  (explicit references — link directly).
- `issueCandidates` / `relatedPRs` — keyword-search hits. Propose and confirm;
  never auto-`Closes` a guessed issue.
- `stack` — the branch's native stack membership (trunk, position, size) and
  the PR of the layer below, when this branch is part of a stack.

For a prior PR that a commit builds on, `git_provenance` (commit → PR) gives a
`Follow-up to #M` / `Supersedes #M` link.

Judgment stays here: explicit refs link directly, search hits are confirmed not
assumed, and a link is never fabricated. Use `Closes #N` for full resolution;
`Refs #N` / `Follow-up to #M` / `Supersedes #M` for relations.

Limits: `gh` search filters by keyword, not reliably by file path, so area
overlap is approximate; links exist only when the work genuinely maps;
cross-repo or private refs may not resolve; solo repos surface few Issues.

</RelatedScan>

<StackDecision>

Prefer a native GitHub stack whenever the work splits into reviewable layers;
one plain PR is the fallback, not the default. Decide before Step 4.
When the work was planned in Phases, each Phase is one layer, in stack order,
and its Phase{N}.{m} steps are that layer's commits: a cut the plan already
agreed needs no second proposal.

- **Always stack** when the branch builds on an unmerged PR of the same
  repository: adopt that PR's branch and add a layer (<StackedPRs>), never
  hand-manage a base branch.
- **Propose a split** when the branch's own commits fall into two or more
  layers that each review and build on their own — an extraction before its
  use, a schema or API before its callers, a refactor before a behavior
  change. Cuts run between existing commits: never reorder or rewrite commits
  to make a cut fit. Propose the cut once (each layer's commits, its branch
  name, why it stands alone, and that the quick check passes at each cut,
  `git_verify_commits`), and split only after the user agrees.
- **Stay plain** when one reviewable change remains: a single layer gains
  nothing, since GitHub forms a stack from two PRs. Also when the PR comes
  from a fork (stacks cannot span a fork and its upstream), the remote is not
  github.com, or `git_publish` returns `stacksUnavailable`. A plain PR still
  publishes through <Publishing>, and can join a stack later.
- A purpose in `approach-github-projects` follows its own `<BranchTopology>`,
  which already decides the stack.

</StackDecision>

<Publishing>

Every PR this skill opens or updates leaves through two tools, plain or
stacked alike:

- `git_publish_preview` (read-only, runs without asking) describes the
  publication and pins it in a `token`: the `mode` (`plain` for a branch
  outside a stack, `stack` for a stack's layers), the `base`, each layer's
  commits and push kind (create / fast-forward / force), its PR, a `retarget`
  of an existing plain PR's base, refusals, warnings, and a secret scan of
  every commit. For a plain branch pass `base` only for a base the user chose
  (Step 2); otherwise the open PR's base, else the default branch, is kept.
- `git_publish` (asks) publishes exactly that, given the `token` and the same
  `base` (and `meta`): `push` sends the commits and sets the previewed
  metadata on PRs that already exist; `submit` also opens each missing PR
  (ready unless asked for drafts), applies `prs` titles and bodies to new and
  existing PRs, moves a plain PR's base when the preview showed `retarget`,
  and links a stack's PRs. Existing PRs keep their draft state.

Show the user the preview's layers, refusals and warnings before publishing.
A refusal is fixed, never worked around: rebase (Step 3), commit or stash,
remove a secret, or ask. A force push after a rebase is the mechanism here,
not a violation of the no-force-push rule: the pinned commits leave in one
atomic push, each branch leased on the remote commit the preview saw. Read
`pushed`, `pr`, `baseMismatch`, `errors` and `autoMergeDisabled` in the result
rather than assuming success.

Fall back to the gated shell (`git push`, `gh pr create`, `gh pr edit`) only
where the tools refuse by design: a PR from a fork, a remote that is not
github.com, or a metadata-only update of title or body with nothing to push.

</Publishing>

<Metadata>

Labels, assignees, review requests and a milestone can start workflows,
merge bots and notifications, so they are judged before they are set.

- **At publication.** Pass `meta` to `git_publish_preview` and `git_publish`
  alike (and `layerMeta` for one layer of a stack). By default that is
  `infer: true`: the repository's habit, read from your merged PRs, adds
  yourself as assignee and the labels most of them carry; a habitual milestone
  is only suggested. Add what the user asked for on top. The preview judges
  each change — `harmless`, `approval` (with reasons), `invalid` (a label,
  milestone or person that does not exist; nothing is created) or
  `unchanged` — and publishing sets the harmless and approval ones, so show
  them with the rest of the preview.
- **On an existing PR.** `gh_pr_meta` applies what nothing reacts to at once
  and returns the rest as `pending` with its reasons; show those to the user
  and apply them with `gh_pr_meta_apply` (asks) only after they agree.
- **Reviewers only on request.** A review request notifies people (and
  `@copilot` uses AI credits); never infer or add one the user did not ask
  for. The PR's author cannot review it.
- Report what was set, inferred (with its counts) or skipped, from the tool's
  re-read rather than from the request.

</Metadata>

<StackedPRs>

When the branch belongs to a stack, the stack owns the base and the push; this
skill still owns the title, body and links.

- **Layer descriptions.** Derive the title and change summary from the diff
  against the layer immediately below (the trunk for the bottom layer), not
  from the whole stack's diff against the trunk. Describe only changes this
  PR introduces; put the broader purpose and dependencies in body context or
  links. Never broaden the top PR's title to serve as a whole-stack merge title.

`git_stack` (local only, runs without asking: `split`, `add`, `rebase`)
shapes the stack over the `github/gh-stack` extension (`gh stack`, declared in
`GH_EXTENSIONS` in `install.sh`; if it is missing, install it rather than
falling back to hand-managed base branches), and <Publishing> publishes it.
Prefer them to shell `gh stack`, which stays available (asking) for what they
do not cover, such as `gh stack sync` or `gh stack checkout`.

- **Detect first.** `git_related_scan` returns `stack` — trunk, position, size,
  the layers below and above, and `needsRebase` — for a layer that has no PR
  yet as well as one that has. If the branch is in a stack, do not compute a
  base yourself: the layer below is the base and the stack maintains it,
  including retargeting survivors after a partial merge.
- **Creating.** `git_stack` `split` with `at` (the last commit of each lower
  layer, bottom-up) and `names` turns the current branch into the top layer
  on the default branch. With no cuts it adopts the branch, and its open PR,
  as a one-layer stack, so work that builds on an unmerged PR can follow as a
  new layer.
- **Adding a layer.** `git_stack` `add` with the new branch name appends on
  top (it switches to the top first). The CLI cannot insert mid-stack, and
  `gh stack modify` is TUI-only.
- **Rebasing.** `git_stack` `rebase` brings the trunk's latest state into
  every layer and moves the layers above a changed one; publishing refuses a
  stack that is behind the trunk or out of order. On conflicts it returns the
  layer, the worktree and the conflict map (`ours` is the layer below,
  `theirs` the commit being replayed; lockfiles are regenerated, not merged):
  resolve, `git add`, then `step: continue`, or `step: abort` to restore every
  layer. Keep its `before` commits for the report.
- **Publishing.** Per <Publishing>: `submit` for new layers (each missing PR
  opens on the layer below, and the stack's PRs are linked), `push` for
  updates. Report `stacksUnavailable` when present.
- **Linking existing PRs.** `git_publish` `link` with PR numbers
  bottom-up; it always passes the default branch as `--base`. Never run a bare
  `gh stack link`: it silently retargets existing PRs.
- **Closing keywords work from any layer** of a stack rooted at the default
  branch — a mid-stack `Closes #N` does fire on merge. This is NOT true when
  the stack is rooted elsewhere, which is one reason the topology fixes the
  trunk to the default branch. So write `Closes` only on the layer that
  actually finishes the issue; earlier layers use `Refs`.
- **A branch created from an issue closes it regardless.** A PR opened from a
  `gh issue develop` branch lands in the issue's `closingIssuesReferences`
  with no keyword written anywhere. Check the layer's `closingIssues` with
  `gh_pr_status` before merging a lower layer, or the issue closes while the
  rest of the stack is still open.
- Merging (`gh stack merge`) stays out of scope here, like every other merge.

</StackedPRs>

<MergeMessageHandoff>

PR descriptions and merge messages have different scopes. A native stack has
no independent title/body that can stand in for its members. Do not assume a
particular member supplies the default title of a stack merge commit.

At handoff, distinguish the documented native-stack merge methods:

| Method | Result and description scope |
| --- | --- |
| Merge commit | One merge commit for the selected group; its title and body should describe all PRs being landed. |
| Squash | One squash commit per merged PR; each layer's description remains relevant, subject to repository message defaults. |
| Rebase | Individual commits are replayed; their subjects remain the descriptions, not one aggregate PR title. |

A later, separately authorized merge must re-read the current stack and the
selected prefix: merging through a middle layer excludes the layers above it.
Prepare the merge description from that actual range and chosen method, not
from a stale whole-stack summary or a mechanically copied top-layer title.
PR creation does not settle the merge scope, method or message in advance.

This is a handoff rule, not merge execution. Do not add merge commands, API
fallbacks or repository-setting mutations to this workflow. If the installed
CLI cannot customize a merge message, disclose that limit; do not claim a PR
rename guarantees the desired merge subject or use an API to bypass a gate.

Sources: [native stack merge methods](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests#merge-methods)
and [squash-message settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/configuring-commit-squashing-for-pull-requests).

</MergeMessageHandoff>

<Steps>

1. Confirm the user asked to open or update a PR. Inspect the branch with
   `git_state` (branch, upstream ahead/behind, uncommitted files, the
   branch's PR). Its `base` is the merge-base with the remote default branch,
   not the PR's base (Step 2 resolves that), and it reads local refs only:
   ahead/behind are as of `lastFetch`. Do not open a PR from the default
   branch; move the work to a task branch (`git_worktree`, `action: create`)
   first. Warn that uncommitted changes will not be in the PR.
2. Run <RelatedScan> before comparing changes, writing descriptions or pushing.
   Resolve the existing PR and stack membership, then determine the base: the
   stack's immediate lower layer wins. For a non-stack PR, honor an explicit
   base request (it becomes `git_publish_preview`'s `base`); otherwise the
   existing PR's base is kept, and a new PR without a selected base goes to the
   repository default — the preview resolves both and reports the `base`. If
   adding/rebasing layers changes the topology, rescan and resolve the base
   again before continuing.
3. Bring in the base's latest state before every push, for a new PR and for an
   update alike (skip it for a metadata-only update). For a stack,
   `git_stack` `rebase` (see <StackedPRs>). Otherwise `git_rebase` with
   `action: start` and `onto: <base>`: it fetches the base, replays the
   branch's commits on it without an editor, and folds pending fixups.
   - `upToDate` — nothing to do.
   - `conflicts` — resolve each file from its conflict map (in a rebase `ours`
     is the base, `theirs` the commit being replayed; lockfiles are
     regenerated, not merged), `git add` it, then `git_rebase` with
     `action: continue`; `abort` restores the branch.
   - `empty` — the replayed commit's change is already in the base:
     `action: skip` drops it.
   - `rebase` with `inProgress` — git stopped for another reason (an
     untracked file in the way, signing): fix what `output` names, then
     `action: continue`. Never `skip` it: that drops a real commit.
   - `rewrite` — the rewrite rule refuses (the default branch, commits
     already on it or held by another remote branch, or a branch GitHub
     protects; see `git_amend_check`): stop and report; do not merge the base
     in or rebase with shell git instead.
   Keep the result's `before` sha for the report: `undo` restores it. Then,
   before every push, run the project's quick check once on the final commit;
   a failure is fixed with a commit (`git-commit`) before pushing.
   For a new PR not yet in a stack, apply <StackDecision> now, on the rebased
   commits: an agreed split or an adoption goes through `git_stack`, and
   Step 2's scan runs again, since every layer now has its own base.
4. Inspect `git log --oneline <base>..HEAD` and `git diff <base>...HEAD` using
   that resolved base. Confirm the PR introduces changes and review every
   included commit, not only the latest. For a stack, separate lower-layer
   context from the changes this layer actually introduces. For metadata-only
   updates, inspect the published PR with `gh pr diff` and
   `gh pr view --json commits` instead of unpublished local HEAD.
5. Build the title and body per <ConventionResolution> and <StackedPRs>, folding
   in verified links. Update an existing PR instead of creating a duplicate.
6. Publish only a new PR or an authorized branch update, through
   <Publishing>: `git_publish_preview` (with `base` from Step 2 when one was
   chosen, and `meta` per <Metadata>), show it, then `git_publish` with its
   `token` and the same arguments — `push` when every
   PR already exists, `submit` when one is missing or its title, body or base
   changes. A rebase (Step 3, or a fixup's fold) that reported
   `needsForcePush` is published the same way: the leased push is the force
   push. A request to edit a title or body alone does not authorize
   publishing local commits.
   Only for a PR from a fork or a non-GitHub remote, push with the gated shell:
   `git push -u <writable remote> HEAD`, or after a rebase exactly
   `git push --force-with-lease <remote> HEAD:refs/heads/<branch>` (the full
   destination cannot be remapped by push config, and some rulesets open no
   other force spelling). Never a bare `--force`.
7. Create or update the PR: `git_publish` `submit` opens a missing PR on its
   base (ready unless asked for a draft) and sets the title and body from
   `prs`, multi-line bodies included. If it returns `stacksUnavailable`, the
   layer PRs already exist, each on the layer below, just unlinked: report them
   and ask the user whether to keep them so or close them for one plain PR; do
   not open another PR on your own.
   On the shell fallback (a fork, or a metadata-only update with nothing to
   push), write the body to a scratch file with the write tool, then
   `gh pr create --base <base> --title "..." --body-file <file>` or
   `gh pr edit` (never literal `\n`; a heredoc fed to `--body-file -` breaks
   when anything follows its terminator line). Preserve unspecified fields and
   draft state. Metadata goes through `gh_pr_meta` there too (<Metadata>),
   never through `gh pr` flags.
8. Re-read the published PR's base, title, body and draft state, and the stack
   order when applicable (`git_publish` returns them per layer, with any
   `baseMismatch`, `pushed: false` or `errors`). Confirm the description
   matches the layer diff; do not assume submission or base retargeting
   preserved that match.
9. Report the PR URL and its ready/draft state, including the immediate base
   for a stack, and whether Step 3 rebased (with its `before` sha). Keep any
   later merge-message handoff separate. Do not merge.
10. When CI or review feedback should be followed, read it with
    `gh_pr_status` (`wait: true` to wait for the checks) instead of `sleep` +
    `gh pr checks` loops or `--watch`. It returns the checks' verdict, the
    failed jobs' errors, mergeability, closing issues and unresolved review
    threads. Act on `waited.endedBy`:
    - `complete` — read `checks.overall`; report unresolved threads.
    - `failed` — read `failedLogs` (the `##[error]` lines first); a fix is a
      new commit or a fixup (`git-commit`), then Steps 3 and 6 again.
    - `timeout` — checks are still pending: call it again, do not sleep.
    - `no_checks` — read `hints`: CI will not start (a conflict with the
      base, no workflow, runs awaiting approval); it has not passed.

</Steps>

<BodyStructure>

- Follow the template when present. Otherwise: `## Summary` (what changed and
  why), a changes section with `**Label**:` bullets describing changes
  conceptually (not a file-by-file dump), and `## Notes` for caveats,
  follow-ups, or "requires restart".
- Place the <RelatedScan> links in the body or a footer: `Closes #N` to close
  issues; `Refs #N` / `Follow-up to #M` / `Supersedes #M` for relations.
- Keep out: secrets; emoji (unless the repo's PRs use them); pasted logs or
  large code blocks; mechanical file listings.

</BodyStructure>

<AntiPatterns>

- Do not open or update a PR unless explicitly asked.
- Do not create commits here — that is `git-commit`'s job.
- Do not merge, and do not bypass the `git push` or `gh pr merge` gates.
- Do not force-push unless explicitly asked, except the leased push of a
  `git_publish` (or its shell fallback) after a `git_rebase`, `git_stack`
  rebase or `git_commit` amend that reported `needsForcePush`. Never a bare
  `--force`.
- Do not push a branch without first bringing in its base (Step 3), and do
  not merge the base in or rebase with shell git when `git_rebase` refuses.
- Do not open one large PR when its commits split into reviewable layers, and
  do not split without the user's agreement or by reordering commits.
- Do not hand-manage a base branch for work on top of an unmerged PR — stack it.
- Do not publish without showing the user its `git_publish_preview`, and do
  not retry `git_publish` with a fresh token to get past a refusal or a
  changed branch without showing the new preview.
- Do not push with the shell what `git_publish` can publish; the shell push is
  for forks and non-GitHub remotes only.
- Do not run a bare `gh stack link` or `gh stack submit --open`: link without
  `--base` retargets existing PRs, and `--open` marks existing drafts ready.
  Preserve existing draft state during metadata-only updates.
- Do not open a PR from the default branch, and do not duplicate an existing
  open PR — update it.
- Do not silently exclude uncommitted work; warn that only pushed commits ship.
- Do not request a review, change a milestone, or set metadata beyond the
  repository's habit unless asked; do not apply `pending` metadata without the
  user's agreement, or create labels or milestones to make a change valid.
- Do not fabricate an Issue or PR link — leave it out or ask when unsure.
- Do not invent a title or body convention that contradicts the repo's merged
  PRs.
- Do not describe lower-layer changes as new work in the current PR, or rename
  a layer to disguise a whole-stack merge-message mismatch.
- Do not treat a PR title as a guaranteed merge subject or a PR-creation
  request as authorization to choose or execute a later stack merge.

</AntiPatterns>
