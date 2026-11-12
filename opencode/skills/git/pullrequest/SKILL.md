---
name: pullrequest
description: >-
  Use when opening, pushing, or updating a GitHub pull request — the
  convention layer over the git and GitHub tools: rebasing onto the latest
  base, pushing, writing a title and body in the repository's convention for a
  reader who has only the repository, marking it ready, stacking PRs when the
  work splits into reviewable layers, judging labels, assignees, reviewers and
  milestones (ラベル, アサイン, レビュアー, マイルストーン), attaching
  screenshots (スクショ添付), linking related Issues and PRs, and following CI
  checks and review feedback (PR, pull request, プルリク, プルリクエスト, push,
  gh pr, open a PR, レビュー依頼, 関連Issue, stacked PR, gh stack, スタック,
  rebase onto main, 最新の main を取り込む, CI, checks, チェックが落ちた,
  レビューコメント, review comments). How each tool is called is the package
  skills' job (`git-push`, `git-rebase`, and github-tools'
  `github-pull-requests`). Do NOT use to create commits (use `commit`) or to
  merge — merging stays gated and explicit.
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
- The publish timing recorded in an aligned plan, agreed with the user, is
  reached: a layer it publishes as it completes, or the last layer when it
  publishes all at the end.
- The user asks to mark a PR ready, or to refresh its title, body, links, or
  its labels, assignees, reviewers or milestone (<Metadata>).
- The user asks to attach screenshots or recordings to a PR (<Media>).
- The user asks how a PR's checks or reviews stand, or to follow CI after a
  push (Step 10 alone).

</UseWhen>

<DoNotUseWhen>

- Creating commits or staging — use `commit`. This skill assumes the commits
  already exist and starts at push.
- Merging, closing, or approving a PR. Merging stays gated (`ask`) and happens
  only on explicit request.

</DoNotUseWhen>
</Scope>

<Mechanics>

This skill decides what to publish and what to write; the packages' skills say
how each tool is called. Load the package skills for the call itself and do
not restate them here: `git-push` (`git_push_read` `preview`, `git_push_send`:
kinds of push, refusals, findings, leases), `git-rebase` (`git_rebase_*`:
stack reading, rebasing, resuming, cutting and adding layers), `git-worktree`
(`git_worktree_*`) and github-tools' `github-pull-requests` (`github_pr_*`,
`github_stack_*`: opening and editing, closing issues, attachments, partial
failures, merging). The package's `git-commit` skill is about the commit tools;
this repo's `commit` skill is the convention for using them.

</Mechanics>

<ConventionResolution>

Resolve the title and body format. Detect, do not assume.

1. Existing habit — read recent merged PR titles with `github_pr_read`
   (`method: "list"`, `state: "merged"`) and the branch's commit subjects with
   `git_repo_read` `conventions` (it reads commit subjects only, not PR
   titles); infer the title style (casing, whether a `type:` prefix is used,
   parentheticals) and the body structure.
2. Template — the same `conventions` call reports the PR template in the
   tree; if there is one, fill its sections instead of inventing structure.
3. Fallback — derive from the branch's commits (`git log <base>..HEAD`): a
   capitalized summary title and the body of <BodyStructure>.

- Treat PR titles as durable descriptions, but do not promise they become the
  landed commit subject. Squash-message defaults depend on repository settings
  and commit count; a one-commit PR may use its commit subject instead. Read the
  actual settings when explaining the expected result, never change them here.
- Title and body language follow the repo's merged-PR habit — infer it, never
  assume English.
- Habit sets style, structure and language, never content or length: what
  <Audience> keeps out stays out even when merged PRs carry it, and long
  merged PRs do not license a long one (<BodyStructure>).

</ConventionResolution>

<Audience>

A PR's title and body are read by someone who has the repository and GitHub
and nothing else: not this conversation, not the plan, not the caller's brief,
not the machine the work ran on. Write for that reader. Everything the branch
was planned and built with is working context, and working context stays out
of the published text unless a tracked file or an Issue of the repository
defines it: a step of the repository's own migration guide may be named; a
step of the plan may not.

Keep out of titles, bodies and branch names:

- **Plan labels** — `Phase 1`, `段 B`, `3 層目`, `Step 2.4`, roadmap or
  milestone names that live only in the plan. A layer's place in a stack is
  shown by its base and the stack's PR links, not by a label. The next layer is
  "the layer that uses this" or a `Refs #N`, never "next is Phase 11".
- **Working records** — numbers and names of a decision log, brief, job,
  session or task directory (`決定 #66`, `decisions.md`, `progress.md`). A
  decision the reader must know is restated in its own words; one that lives
  in a GitHub Issue is linked as `#N`.
- **Tooling** — the names of agents, tools, skills, subagents or the harness
  (`reviewer`, `git_commit_verify`, `OpenCode`, `Hermes`). Say what was
  checked, not what checked it: "each commit passes lint and typecheck",
  never "`git_commit_verify` ran".
- **The build machine** — local paths, the user's home, what is or is not
  installed there ("no Java here"), which model or account did the work.
- **The organisation's state** — billing, plan or account status, who is on
  leave, internal deadlines. A CI run that did not happen is "CI did not run
  on this branch", with no reason that lives outside the repository.
- **The caller's words** — a brief or a request pasted or paraphrased as the
  PR's purpose. Give the purpose as the repository's reader would state it.

Commit subjects feed the fallback title and show in the PR, so the same
exclusions hold there (`commit` <MessageHygiene>). When a convention
resolved in <ConventionResolution> appears to invite one of these — merged
PRs that carry a plan label, say — it is a habit to break, not to follow:
write the clean form, and tell the user in your reply (never in the PR) that
the habit was not followed.

No tool checks these words. Read the branch name, the commit subjects and the
PR's title and body yourself, as the <Audience> reader, before
`git_push_send`, `github_pr_create` or `github_pr_edit`.

</Audience>

<RelatedScan>

Find the Issues and PRs to link. There is no single scan tool; do it by
reading, all read-only:

- **Existing PR** — `github_pr_read` `list` with `head` = this branch (state
  open, then all if none). Update the open one; do not duplicate it.
- **Explicit references** — issue numbers (`#N`, `Closes #N`, `Refs #N`) in the
  branch's commit messages (`git log <base>..HEAD`) and in its name. Link
  these directly.
- **Candidates** — search by the change's keywords: `github_issue_read`
  `list` with `query` for Issues and `github_pr_read` `list` with `query` for
  PRs. Propose and confirm; never auto-`Closes` a guessed issue.
- **Stack membership** — `git_rebase_read` `stack` shows the layers of the
  checked-out branch, and `github_pr_read` `view` or `github_stack_read`
  `view` the PR-side stack, including the PR of the layer below.

For a prior PR that a commit builds on, `commit` <Provenance> (commit → PR)
gives a `Follow-up to #M` / `Supersedes #M` link.

Judgment stays here: explicit refs link directly, search hits are confirmed not
assumed, and a link is never fabricated. Use `Closes #N` for full resolution;
`Refs #N` / `Follow-up to #M` / `Supersedes #M` for relations.

Limits: search filters by keyword, not reliably by file path, so area overlap
is approximate; links exist only when the work genuinely maps; cross-repo or
private refs may not resolve; solo repos surface few Issues.

</RelatedScan>

<StackDecision>

Prefer a native GitHub stack whenever the work splits into reviewable layers;
one plain PR is the fallback, not the default. Decide before Step 4.
When the work was planned in Phases, each Phase is one layer, in stack order,
and its Phase{N}.{m} steps are that layer's commits: a cut the plan already
agreed needs no second proposal. The Phase is the plan's name for the layer,
not the layer's name: it decides where the cut falls and never reaches a
branch name, title or body (<Audience>).

- **Always stack** when the branch builds on an unmerged PR of the same
  repository: add a layer on top of that PR's branch (<StackedPRs>), never
  hand-manage a base branch.
- **Propose a split** when the branch's own commits fall into two or more
  layers that each review and build on their own — an extraction before its
  use, a schema or API before its callers, a refactor before a behavior
  change. Cuts run between existing commits: never reorder or rewrite commits
  to make a cut fit. Propose the cut once (each layer's commits, its branch
  name, why it stands alone, and that the quick check passes at each cut,
  `git_commit_verify`), and split only after the user agrees.
- **Stay plain** when one reviewable change remains: a single layer gains
  nothing, since GitHub forms a stack from two PRs. Also when the PR comes
  from a fork (stacks cannot span a fork and its upstream; `github_pr_create`
  does not open from forks yet), the remote is not github.com, or stacks are
  unavailable for the repository. A plain PR still publishes through
  <Publishing>, and can join a stack later.
- A unit in `approach-github-delivery` follows its own `<Branches>`, which
  already decides the stack.

</StackDecision>

<Publishing>

Every PR this skill opens or updates leaves in three steps, plain or stacked
alike: push, then PR, then (for a stack) link.

1. **Preview, then send the push.** `git_push_read` `preview` describes the
   push per branch (kind, the commits the remote lacks, what a force drops),
   with refusals, warnings, the secret scan and the published-text findings;
   its `send` is what `git_push_send` (asks) pushes, atomically and each
   branch leased on the remote commit the preview saw. Show the user the
   preview before sending. `stale` means a branch moved: preview again. A
   refusal is fixed, never worked around: rebase (Step 3), commit or stash,
   remove a secret, or ask. A finding is fixed in the words or the code, and
   a false positive is let through only by its fingerprint after reading it
   (`git-push`). A force push after a rebase is the mechanism here, not a
   violation of the no-force-push rule: the leased push in `send` is that
   push.
2. **Open or update the PRs.** `github_pr_create` per missing layer: `head`,
   `head_sha` = the sha the push returned, `base` (the layer below's branch;
   the default branch for a plain PR or the bottom layer, unless the user chose
   another), `title`, `body`, `draft`, the <Metadata> judged and the <Media>
   agreed, and `closes` for the issues the layer finishes. An existing PR is
   changed with `github_pr_edit` (title, body, base, metadata), never
   duplicated; `github_pr_ready` marks a draft ready. Read the title and body
   as the <Audience> reader first.
3. **Link a stack.** `github_stack_link` with the PR numbers bottom to top
   (<StackedPRs>).

Read the results rather than assuming success: `pushed` and `sha` per branch,
the PR's `errors` (a step after the PR exists that failed — fix it on what
exists and never run `github_pr_create` again to retry; see the package's
`github-pull-requests` "Partial failures"), `closing_issues` and notes.

Fall back to the gated shell (`git push`, `gh pr create`, `gh pr edit`) only
where the tools refuse by design: a PR from a fork, a remote that is not
github.com. A metadata-only update of title or body with nothing to push needs
no push at all: go straight to `github_pr_edit`.

</Publishing>

<Metadata>

Labels, assignees, review requests and a milestone can start workflows,
merge bots and notifications, so they are judged before they are set. No tool
infers them: decide each yourself, from the repository, and pass them to
`github_pr_create` / `github_pr_edit`.

- **Labels.** Read the repository's labels (`github_label_read`) and what its
  recent merged PRs carry (`github_pr_read` `list`, `state: "merged"`); use
  the labels the habit supports, plus what the user asked for. Never create a
  label to make a change valid.
- **Assignees.** The habit of recent merged PRs (usually the author); add
  whom the user names.
- **Milestone.** Only when the user asks, or the repository's habit is clear
  and the user agrees; never create one.
- **Reviewers only on request.** A review request notifies people (and
  `@copilot` uses AI credits); never infer or add one the user did not ask
  for, and consult CODEOWNERS only to suggest a name. The PR's author cannot
  review it.
- **On an existing PR**, `github_pr_edit` overwrites and asks the person once
  per call; propose only what the repository's habit or the user's request
  supports, and call it only after they agree.
- Report what was set or skipped from the tool's result, not from the request.

</Metadata>

<Media>

Screenshots and recordings show a reviewer what the diff cannot.
`attachments` on `github_pr_create`, `github_pr_edit` and `github_pr_comment`
upload them (`{ path, alt? }` per file; gh 2.99.0 or later; limits in
`github-pull-requests` "Attachments"). An upload cannot be deleted, so
nothing is attached that the user has not agreed to.

- **When.** If the PR changes what a page or screen renders and `web_ui_check`
  ran, propose its screenshots (the `Screenshots:` directory; the comparison
  images under `Comparison images:` when it compared a baseline): name each
  file and what it shows, and attach only those the user picks. Otherwise
  attach only what the user asks for.
- **Files.** Images and videos. Keep them outside the worktree or gitignored,
  so they are never committed (`web_ui_check` already writes outside it).
  Do not touch a file between agreeing and sending.
- **Placement.** Reference a file where it belongs in the body,
  `![After, 375px](<absolute path>)` or a path relative to the worktree root,
  and it is replaced with the uploaded URL, keeping that reference's alt text.
  Files the body does not reference are appended at the end, with `alt` (else
  the file name) as alt text. Videos render as a player and take no alt text.
- **Before sending.** Show the user each file and what it shows. On a public
  repository anyone can open the uploads and no scan reads images: check that
  no screenshot shows a token, a private page or personal data before asking.
- **Existing PRs.** A `body` replaces the current one; without it the files are
  appended. Either way, attaching again uploads and appends them again: attach
  each file once.
- **Result.** A failed upload is in `errors.attachments`, and the PR still
  stands: never re-run `github_pr_create` to retry. Tell the user which files
  are missing and, once they agree, add them with `github_pr_edit` or
  `github_pr_comment`.
- **Shell fallback.** For a fork or a non-GitHub remote, `gh pr create` and
  `gh pr edit` take `--attach '<absolute path>#<alt>'` (repeatable, `#<alt>`
  optional, no `#` inside the alt); check `gh --version` first. GitHub
  Enterprise Server cannot attach files.

</Media>

<StackedPRs>

When the branch belongs to a stack, the stack owns the base and the push; this
skill still owns the title, body and links.

- **Layer descriptions.** Derive the title and change summary from the diff
  against the layer immediately below (the trunk for the bottom layer), not
  from the whole stack's diff against the trunk. Describe only changes this
  PR introduces; the broader purpose is one sentence in the reader's terms,
  and the layer's place in the stack is its base and the linked PRs
  (`Refs #N` for the layer below or the one that uses this), never a plan
  label such as "layer 2 of Phase 3" (<Audience>). Never broaden the top
  PR's title to serve as a whole-stack merge title.

A stack is local branches read from ancestry (`git_rebase_read` `stack`) and
GitHub PRs each based on the one below, joined by `github_stack_link`.
`git_rebase_*` shapes the branches, <Publishing> publishes them. Shell
`gh stack` stays available (asking) for what the tools do not cover, such as
`gh stack sync` or `gh stack checkout`.

- **Detect first.** `git_rebase_read` `stack` shows the layers, how each
  branch stands to its remote, and whether the stack may be rewritten; for the
  PR side, `github_pr_read` `view` or `github_stack_read` `view`. If the branch
  is in a stack, do not compute a base yourself: the layer below is the base.
- **Creating.** `git_rebase_split` with `at` (the last commit of each lower
  layer, bottom-up) and `names` cuts the current branch into lower layers,
  the current branch staying the top. A single branch is already a stack of one
  layer, so work that builds on an unmerged PR follows as a new layer on top.
- **Adding a layer.** `git_rebase_split` `add` starts a new empty layer on the
  top (from the top only) and checks it out, so the next commit lands there.
  Layers cannot be inserted mid-stack.
- **Rebasing.** `git_rebase_start` brings the trunk's latest state into every
  layer and keeps each on the one below. When a lower layer was merged by
  squash, pass `after` (that layer) so only the layers above are replayed.
  A fix to a lower layer is a fixup committed on the top and folded with
  `keep_base` (`commit` <CommitGranularity>). On a stop, see Step 3; keep the
  result's before-shas for the report.
- **Publishing.** Per <Publishing>: push the layers in one preview/send, open
  each missing PR on the layer below (`github_pr_create` with that `base`),
  then link them.
- **Linking existing PRs.** `github_stack_link` with PR numbers bottom-up. It
  never opens a PR or changes a base: it refuses bases that do not chain and
  names the base to set with `github_pr_edit`. Never run a bare
  `gh stack link`: it silently retargets existing PRs.
- **Closing keywords work from any layer** of a stack rooted at the default
  branch — a mid-stack `Closes #N` does fire on merge (the tool may note that
  GitHub shows it in the Development panel only for a PR into the default
  branch). This is NOT true when the stack is rooted elsewhere, which is one
  reason the topology fixes the trunk to the default branch. So write
  `Closes` only on the layer that actually finishes the issue; earlier layers
  use `Refs`.
- **A branch created from an issue closes it regardless.** A PR opened from a
  `gh issue develop` branch lands in the issue's `closingIssuesReferences`
  with no keyword written anywhere. Check the layer's `closing_issues` with
  `github_pr_read` `view` before merging a lower layer, or the issue closes
  while the rest of the stack is still open.
- Merging stays out of scope here, like every other merge; how a finished
  stack should land is the handoff in <MergeMessageHandoff>.

</StackedPRs>

<MergeMessageHandoff>

PR descriptions and merge messages have different scopes, and a stack shows
the gap: each layer's PR describes its own diff, while one stack merge lands
every open layer up to the PR it names, by one method. This skill never
merges. When the user asks how to land a stack or says it is ready to merge,
or the layer that completes its goal is published, it hands over a landing
plan.

What a stack merge leaves on the trunk:

| Method | Commits on the trunk | Default message |
| --- | --- | --- |
| Merge commit | ONE merge commit for all the layers merged together; each of their PRs records that same commit | the named PR's merge message (under the default settings its title + ` (#n)`): the top layer only |
| Squash | one squash commit per PR | each PR's own, from the repository's squash settings |
| Rebase | every commit replayed | each commit's own subject |

GitHub's stack reference promises one merge commit per PR; the merges make
one for the group. When they disagree, trust the trunk
(`git log --first-parent`), not the reference.

Landing plan for a stack whose layers serve one goal:

- **Once, when done.** Land the whole stack in one merge after every layer
  is reviewed and its checks pass. Landing layer by layer leaves a half-built
  goal on the trunk for as long as the rest takes. The number of layers does
  not change this.
- **A merge commit with an explicit message.** Title: the goal in the
  repository's PR-title style, ending in ` (#<top PR>)`, written for the
  <Audience> reader like any PR title (no plan labels) and within the same
  65 columns before the number (<BodyStructure>). Body: one line per
  layer it lands, bottom-up, `- #<n> <PR title>`. Every layer's commits stay
  in the history under that merge, and the body names each PR the default
  message drops. Always write the message: repositories differ in their
  defaults (`Merge pull request #n from …`, a PR body, a blank body), so
  leaving it to them lands a different message per repository.
- **Where the message can be given.** GitHub's stack merge page: its title
  field starts as the top PR's title and ` (#n)` and lands exactly as edited,
  so keep the ` (#n)`. Or `PUT /repos/{owner}/{repo}/pulls/{top}/merge-async`
  with `merge_method: merge`, the top PR's head as `sha`, `commit_title` and
  `commit_message`; nothing appends the number there. `github_pr_merge` takes
  `subject` and `body` (and `with_lower_layers`), but the package's skill
  says they apply to the named layer only, so for one merge commit of several
  layers give the message on the page or through the API above.
  `gh stack merge` takes no message: with `--merge` it always lands the top
  PR's title, so never hand it a stack of two or more layers for a merge
  commit.
- **No merge commits allowed, or the user asks for squash:** squash lands one
  commit per layer with that layer's own default message, so there is nothing
  to write; a `commit_title` sent with it renames only the top layer's commit.
  Rebase replays every commit and leaves no line for the goal.
- **A lower part first** is an exception the user names, for example when
  other work needs that base now. That merge lands the layers up to the PR it
  names: one layer follows the repository's single-PR habit, several follow
  the merge-commit rule above. GitHub then rebases the layers left above onto
  the trunk itself.
- **A stack that carries several goals** (work stacked on an unrelated
  unmerged PR) lands each goal's layers as a landing of their own, bottom-up.
- **`gh stack merge` itself:** with no argument and `--yes` it merges the
  whole current stack; a bare number is read as a stack number before a PR
  number; without a method flag it reuses the last method. Spell out the PR
  and the method when handing it over.

The plan names the layers it lands, the surface, the method, and the title
and body. Write the title and body out in full, ready to paste, in the
language of the repository's merged PR titles: the title in one fenced block
and the body in another, never only the rule they follow. Re-read the stack
right before handing it over: a layer added since changes the range. A later,
separately authorized merge re-reads it again and takes the message from the
range it actually lands, never from a stale summary or a copied top-layer
title. PR creation settles none of this in advance.

This is a handoff rule, not merge execution. The surfaces above are named for
whoever lands the stack; this skill runs none of them. Do not add merge
commands, API fallbacks or repository-setting mutations to this workflow, and
do not claim a PR rename sets the merge subject.

Sources: [native stack merge methods](https://docs.github.com/en/pull-requests/reference/stacked-pull-requests#merge-methods),
[asynchronous merge](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request-asynchronously)
and [squash-message settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/configuring-commit-squashing-for-pull-requests).

</MergeMessageHandoff>

<Steps>

1. Confirm the user asked to open or update a PR, or that an aligned plan's
   publish timing has been reached (global `<PlanHandoff>`); when the plan
   does not say, ask at the layer boundary. A narrower restriction from the
   user or the session's instructions (no push) wins. Inspect the branch with
   `git_repo_read` `status` (branch, upstream ahead/behind, uncommitted files,
   the branch's commits). Its `base` is the merge-base with the remote default
   branch, not the PR's base (Step 2 resolves that), and it reads local refs
   only: ahead/behind are as of `last_fetch`. Do not open a PR from the
   default branch; move the work to a task branch (`git_worktree_add`) first.
   Warn that uncommitted changes will not be in the PR.
2. Run <RelatedScan> before comparing changes, writing descriptions or pushing.
   Resolve the existing PR and stack membership, then determine the base: the
   stack's immediate lower layer wins. For a non-stack PR, honor an explicit
   base request; otherwise the existing PR's base is kept, and a new PR
   without a selected base goes to the repository default. If adding or
   rebasing layers changes the topology, rescan and resolve the base again
   before continuing.
3. Bring in the base's latest state before every push, for a new PR and for an
   update alike (skip it for a metadata-only update). `git_rebase_start`
   fetches the default branch and replays every layer of the stack on it
   without an editor (`onto` names another base), folding pending fixups; for
   a lone branch it is a stack of one.
   - `up_to_date` — nothing to do.
   - `paused` for `conflicts` — resolve each file from the result's conflict
     map (in a rebase `ours` is the base, `theirs` the commit being replayed;
     lockfiles are regenerated, not merged), then `git_rebase_resume` with
     `action: "continue"`; `abort` restores every layer.
   - `paused` for `empty` — the replayed commit's change is already in the
     base: `action: "skip"` drops it.
   - `paused` as `stopped` (a failing hook, an `exec`) — fix what `output`
     names, then `continue`. Never `skip` it: that drops a real commit.
   - `rewrite_refused` — the rewrite rule refuses (the default branch,
     commits already on it or held by another remote branch, or a branch
     GitHub protects; see `git_commit_read` `amend`): stop and report; do not
     merge the base in or rebase with shell git instead.
   Keep the result's before-shas for the report. Then, before every push, run
   the project's quick check once on the final commit; a failure is fixed
   with a commit (`commit`) before pushing. For a new PR not yet in a stack,
   apply <StackDecision> now, on the rebased commits: an agreed split goes
   through `git_rebase_split`, and Step 2's scan runs again, since every layer
   now has its own base.
4. Inspect `git log --oneline <base>..HEAD` and `git diff <base>...HEAD` using
   that resolved base. Confirm the PR introduces changes and review every
   included commit, not only the latest. For a stack, separate lower-layer
   context from the changes this layer actually introduces. For metadata-only
   updates, inspect the published PR with `github_pr_read` `diff` and `view`
   instead of unpublished local HEAD.
5. Build the title and body per <ConventionResolution>, <Audience> and
   <StackedPRs>, folding in verified links; then read them once as the
   <Audience> reader and strip what only this conversation can explain.
   Update an existing PR instead of creating a duplicate. Judge the metadata
   (<Metadata>). When the change is visible on screen, settle its attachments
   per <Media> and reference them in the body.
6. Push only for a new PR or an authorized branch update, through
   <Publishing>: `git_push_read` `preview`, show it, then `git_push_send` with
   its `send`. A rebase (Step 3, or a fixup's fold) that reported
   `needs_force_push` is published the same way: the leased push is the force
   push. A request to edit a title or body alone does not authorize pushing
   local commits.
   Only for a PR from a fork or a non-GitHub remote, push with the gated shell:
   `git push -u <writable remote> HEAD`, or after a rebase exactly
   `git push --force-with-lease <remote> HEAD:refs/heads/<branch>` (the full
   destination cannot be remapped by push config, and some rulesets open no
   other force spelling). Never a bare `--force`.
7. Create or update the PR: `github_pr_create` (once per missing layer, bottom
   to top, each on the layer below) with the Step 5 title, body and metadata
   and `head_sha` from the push; `github_pr_edit` for an existing PR whose
   title, body, base or metadata changes; then `github_stack_link` for a
   stack. If the stack cannot be linked, the layer PRs already exist, each on
   the layer below, just unlinked: report them and ask the user whether to
   keep them so or close them for one plain PR; do not open another PR on your
   own. On the shell fallback (a fork), write the body to a scratch file with
   the write tool, then `gh pr create --base <base> --title "..." --body-file
   <file>` or `gh pr edit` (never literal `\n`; a heredoc fed to
   `--body-file -` breaks when anything follows its terminator line).
   Preserve unspecified fields and draft state.
8. Re-read the published PR's base, title, body and draft state with
   `github_pr_read` `view`, and the stack order when applicable
   (`github_stack_read` `view`). Confirm the description matches the layer
   diff and holds nothing <Audience> keeps out; do not assume creation or base
   retargeting preserved that match. An attached file's local path in the body
   now reads as its uploaded URL, and unreferenced files sit at the end: that
   is the expected difference from the body you wrote.
9. Report the PR URL and its ready/draft state, including the immediate base
   for a stack, and whether Step 3 rebased (with its before-shas). When this
   publication completes a stack's goal, add its landing plan
   (<MergeMessageHandoff>) after the report, never in the PR text. Do not
   merge.
10. When CI or review feedback should be followed, read it with
    `github_pr_read` `method: "checks"` (it waits for them) instead of
    `sleep` + `gh pr checks` loops or `--watch`; `method: "view"` adds
    mergeability, closing issues and unresolved review threads
    (`github-pull-requests` "Waiting for checks"). Act on `waited.ended_by`:
    - `settled` — read `checks.overall`; report unresolved threads.
    - `failed` (with `fail_fast`), or `settled` with failures — read
      `failed_logs` (the error lines first); a fix is a new commit or a
      fixup (`commit`), then Steps 3 and 6 again.
    - `timeout` with `checks.overall` pending — call it again, do not sleep.
    - `timeout` with `checks.overall` `none` — read `hints`: CI will not
      start (a conflict with the base, no workflow, runs awaiting approval);
      it has not passed.

</Steps>

<BodyStructure>

The body is a review document, not the commit log. The commits carry the
lasting what and why; the body adds what a reader needs to judge, ship and
later trace the change. Never paste the commit bodies in.

Its readers go beyond today's reviewer: a maintainer who reaches the PR from
the history months later, whoever applies or operates the change, and the
users it affects. Each optional section below answers one of them; write it
whenever that reader would otherwise have to ask.

Follow the template when present, fitting these sections into it. Otherwise,
with section names in the repository's language:

- `## Summary` (required) — why the change is made and what it achieves, in
  2–4 sentences.
- `## Changes` (required) — the changes as concepts, `**Label**:` bullets one
  level deep, one or two sentences each; never a file-by-file dump. A stack
  layer describes only its own diff (<StackedPRs>).
- `## Verification` (required) — a task list in the reader's terms: `- [x]`
  for what passed ("unit tests: 239 pass"), `- [ ]` with a short reason for
  what did not run ("the emulator suite did not run on this branch"), and the
  manual checks a reviewer should repeat. Never the tool that ran a check, or
  a reason that lives off the repository.
- `## Impact and migration` (when it applies) — breaking changes; changed
  settings, environment variables or defaults; what applying it takes (a
  restart, an install step, a data migration). Lead with one `> [!WARNING]`
  when a user must act.
- `## Review focus` (when it applies) — where to look hardest, the decisions
  the code cannot show, and the alternatives rejected, each with why.
- `## Risk and rollback` (when it applies) — what could break and how it would
  show, and how to undo it when a revert alone does not (a migration, external
  state, a published artifact).
- `## Out of scope` (when it applies) — what this PR deliberately leaves, and
  the follow-up as `#N` when an Issue tracks it.
- Links — the <RelatedScan> links in a footer: `Closes #N` to close issues;
  `Refs #N` / `Follow-up to #M` / `Supersedes #M` for relations.

Omit a section that does not apply, heading and all; never fill one with
"None" or "N/A".

Length, in display columns (a wide character counts two): the title fits
within 65, so the ` (#NNN)` GitHub appends on a squash merge still lands
within 72. Summary 2–4 sentences, Changes one level deep. Neither merged PRs
nor the branch's commit bodies set the length; anything long that is only
supporting material goes into `<details>`.

GitHub renders PR bodies, so use its forms:

| To show | Write |
| --- | --- |
| An issue, PR or commit | `#N`, `owner/repo#N`, a short SHA; several related ones as a list, one per line (GitHub shows each one's title and state) |
| Code outside the diff (a caller, the constraint a change relies on) | a permalink pinned to a commit with its line range, alone on its line so GitHub shows the code inline (same repository); never a branch link or `file:line` |
| A long log, output or measurement | `<details><summary>what it is</summary>` around a fenced block; supporting material only, never what a reviewer must read |
| Before and after (numbers, behavior) | a table |
| A setting a user must change by hand | a `diff` fence |
| What must not be missed (a breaking change, a required step) | one `> [!WARNING]` (or `[!NOTE]`); used twice, neither stands out |
| Checks | a task list |
| Screens | attachments per <Media> |
| Any other source | `[what it is](URL)`, never a bare URL |

Keep out: secrets; emoji (unless the repo's PRs use them); logs or large code
blocks outside `<details>`; mechanical file listings; and everything
<Audience> names — plan labels, working records, tooling, the build machine,
the organisation's state, the caller's words.

</BodyStructure>

<AntiPatterns>

- Do not open or update a PR unless explicitly asked or an aligned plan's
  publish timing calls for it; when the plan is silent, ask at the layer
  boundary.
- Do not create commits here — that is `commit`'s job.
- Do not merge, and do not bypass the `git push` or `gh pr merge` gates.
- Do not force-push unless explicitly asked, except the leased push of a
  `git_push_send` (or its shell fallback) after a `git_rebase_start` or
  `git_commit_amend` that reported `needs_force_push`. Never a bare
  `--force`.
- Do not push a branch without first bringing in its base (Step 3), and do
  not merge the base in or rebase with shell git when `git_rebase_start`
  refuses.
- Do not open one large PR when its commits split into reviewable layers, and
  do not split without the user's agreement or by reordering commits.
- Do not hand-manage a base branch for work on top of an unmerged PR — stack it.
- Do not push without showing the user the `git_push_read` preview, and do
  not retry `git_push_send` with a rebuilt `send` to get past a refusal or a
  changed branch without showing the new preview.
- Do not push with the shell what `git_push_send` can push; the shell push is
  for forks and non-GitHub remotes only.
- Do not run a bare `gh stack link`: it retargets existing PRs. Use
  `github_stack_link`. Preserve existing draft state during metadata-only
  updates.
- Do not open a PR from the default branch, and do not duplicate an existing
  open PR — update it.
- Do not silently exclude uncommitted work; warn that only pushed commits ship.
- Do not request a review, change a milestone, or set metadata beyond the
  repository's habit unless asked; do not edit an existing PR's metadata with
  `github_pr_edit` without the user's agreement, or create labels or milestones
  to make a change valid.
- Do not attach a file the user has not agreed to, and do not re-run
  `github_pr_create` to retry a failed upload or any other partial failure.
- Do not fabricate an Issue or PR link — leave it out or ask when unsure.
- Do not invent a title or body convention that contradicts the repo's merged
  PRs.
- Do not write for this conversation: no plan label, decision-log number,
  agent or tool name, local path, or account state in a title, body or
  branch name (<Audience>) — a merged PR that carries one is not a licence.
  The push preview checks only branch names and commit subjects; titles and
  bodies are on you.
- Do not describe lower-layer changes as new work in the current PR, or rename
  a layer to disguise a whole-stack merge-message mismatch.
- Do not treat a PR title as a guaranteed merge subject or a PR-creation
  request as authorization to choose or execute a later stack merge.
- Do not plan a goal's stack to land layer by layer unless the user names that
  exception, and do not hand two or more layers to a merge-commit landing
  without an explicit title and body (`gh stack merge --merge` cannot take
  one): the one commit it makes describes the top layer only.

</AntiPatterns>
