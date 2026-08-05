---
name: git-pullrequest
description: >-
  Use when opening, pushing, or updating a GitHub pull request — pushing a
  branch, creating a PR whose title and body match the repository's own
  convention, marking it ready, adding a layer to a native GitHub stack, and
  scanning the branch for related Issues and PRs to link (PR, pull request,
  プルリク, プルリクエスト, push, gh pr, open a PR, レビュー依頼, 関連Issue,
  related issues, link PR, stacked PR, gh stack, スタック). Resolves the PR
  title/body convention from merged PRs and a template, derives links from
  commits, the branch name and targeted gh queries, and defaults to
  ready-for-review. Do NOT use to create commits (use git-commit) or to merge —
  merging stays gated and explicit.
author: CraftSamo
license: MIT
---

<Goal>

Open or update the pull request the user asked for: push the branch, write a
title and body that match the repository's convention, and link the related
Issues and PRs the branch's work actually touches. Never merge.

</Goal>

<Scope>
<UseWhen>

- The user asks to open, push, or update a pull request for the current branch.
- The user asks to mark a PR ready, or to refresh its title, body, or links.

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

- Squash-merge repos: the PR title becomes the squash commit subject on the
  base branch — make it a good permanent subject.
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

<StackedPRs>

A purpose executes as a chain of PRs (`approach-github-projects`
`<BranchTopology>`). When the branch belongs to one, `gh stack` owns the base
and the push; this skill still owns the title, body and links.

`gh stack` is the `github/gh-stack` extension, declared in `GH_EXTENSIONS` in
`install.sh`. If the command is missing, install it
(`gh extension install github/gh-stack`) rather than falling back to
hand-managed base branches.

- **Detect first.** `git_related_scan` returns `stack` — trunk, position, size,
  the layers below and above, and `needsRebase` — for a layer that has no PR
  yet as well as one that has. If the branch is in a stack, do not compute a
  base yourself: the layer below is the base and `gh stack` maintains it,
  including retargeting survivors after a partial merge.
- **Adding a layer.** `gh stack top` then `gh stack add <branch>` (append only
  — the CLI refuses to insert mid-stack, and `gh stack modify` is TUI-only).
  Publish with `gh stack submit --open`: `--auto` alone creates **drafts**,
  which contradicts this skill's ready-by-default rule.
- **Pushing.** Use `gh stack push`, not `git push`. Rewriting a lower layer
  requires `gh stack rebase` first; the stack cannot merge unless every layer
  is a linear descendant of the one below.
- **Force-push is expected here.** `gh stack push` force-pushes rewritten
  layers with `--force-with-lease`. That is the mechanism, not a violation of
  the no-force-push rule — but it is not atomic across branches, so re-read the
  result instead of assuming all layers moved.
- **Never `gh stack link` without `--base`.** It defaults the trunk to the
  repository default branch and silently rewrites an existing PR's base to
  match. Pass `--base` explicitly whenever the intended trunk is anything else,
  and re-read the resulting bases afterwards.
- **Closing keywords work from any layer** of a stack rooted at the default
  branch — a mid-stack `Closes #N` does fire on merge. This is NOT true when
  the stack is rooted elsewhere, which is one reason the topology fixes the
  trunk to the default branch. So write `Closes` only on the layer that
  actually finishes the issue; earlier layers use `Refs`.
- **A branch created from an issue closes it regardless.** A PR opened from a
  `gh issue develop` branch lands in the issue's `closingIssuesReferences`
  with no keyword written anywhere. Check `gh pr view --json
  closingIssuesReferences` before merging a lower layer, or the issue closes
  while the rest of the stack is still open.
- Merging (`gh stack merge`) stays out of scope here, like every other merge.

</StackedPRs>

<Steps>

1. Confirm the user asked to open or update a PR. Inspect: the current branch is
   not the default branch, `git status`, and `git log --oneline <base>..HEAD`
   has commits. Warn that uncommitted changes will not be in the PR.
2. Determine the base: the repo default branch
   (`gh repo view --json defaultBranchRef`), unless the user names one or the
   branch is a stack layer (then the layer below is the base — see
   <StackedPRs>).
3. Push: `git push -u origin HEAD` (gated `ask`), or `gh stack push` for a
   stack layer; when `origin` is not writable (fork workflow), push to the
   writable fork remote instead. Never force-push outside the stack mechanism
   unless explicitly asked.
4. Run <RelatedScan>: `git_related_scan` returns the existing open PR for this
   head — update it, do not duplicate — along with the links to include.
5. Build the title and body per <ConventionResolution>, folding in the links.
6. Create or update: `gh pr create --base <base> --title "..." --body-file -`
   fed by a heredoc (multi-line bodies survive quoting; never literal `\n`);
   ready by default, add `--draft` only if asked. For a stack layer, publish
   with `gh stack submit --open` and then set the title/body via `gh pr edit`.
   Update with `gh pr edit`. Set reviewers, labels, assignees, or a milestone
   only if the user asked.
7. Report the PR URL and its ready/draft state. Do not merge.

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
- Do not force-push unless explicitly asked, or as part of `gh stack push`
  after a `gh stack rebase`.
- Do not run `gh stack link` without an explicit `--base` — it silently
  retargets existing PRs to the default branch.
- Do not leave a stack layer as a draft when the repo convention is
  ready-for-review — `gh stack submit --auto` defaults to draft.
- Do not open a PR from the default branch, and do not duplicate an existing
  open PR — update it.
- Do not silently exclude uncommitted work; warn that only pushed commits ship.
- Do not set reviewers, labels, assignees, or a milestone unless asked.
- Do not fabricate an Issue or PR link — leave it out or ask when unsure.
- Do not invent a title or body convention that contradicts the repo's merged
  PRs.

</AntiPatterns>
