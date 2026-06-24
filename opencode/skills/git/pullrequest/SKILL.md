---
name: git-pullrequest
description: >-
  Use when opening, pushing, or updating a GitHub pull request — pushing a
  branch, creating a PR whose title and body match the repository's own
  convention, marking it ready, and scanning the branch for related Issues and
  PRs to link (PR, pull request, プルリク, プルリクエスト, push, gh pr, open a PR,
  レビュー依頼, 関連Issue, related issues, link PR). Resolves the PR title/body
  convention from merged PRs and a template, derives links from commits, the
  branch name and targeted gh queries, and defaults to ready-for-review. Do NOT
  use to create commits (use git-commit) or to merge — merging stays gated and
  explicit.
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

1. Existing habit — read recent merged PRs:
   `gh pr list --state merged --limit 20 --json title,body,headRefName`. Infer
   the title style (casing, whether a `type:` prefix is used, parentheticals)
   and the body structure.
2. Template — if `.github/PULL_REQUEST_TEMPLATE.md` (or a root / `docs/`
   variant) exists, fill its sections instead of inventing structure.
3. Fallback — derive from the branch's commits (`git log <base>..HEAD`): a
   capitalized summary title and a Summary / Changes / Notes body.

- Squash-merge repos: the PR title becomes the squash commit subject on the
  base branch — make it a good permanent subject.
- Title language follows the repo's habit (English in this repo).

</ConventionResolution>

<RelatedScan>

Scan the branch to find Issues and PRs to link. Read-only. Local refs first,
then targeted gh queries (no file-overlap deep scan).

Inputs: the branch name, `git log <base>..HEAD`, and the changed files
(`git diff --name-only <base>..HEAD`).

Scan A — Issues this PR resolves or relates to:

- Commits: grep `git log <base>..HEAD --pretty='%s%n%b'` for `#\d+` and
  `Closes|Fixes|Resolves #\d+`.
- Branch name: parse an embedded issue number (`feat/123-...`, `fix/issue-123`).
- Keyword: `gh issue list --state open --search "<keywords>"` for candidates.
- Classify: full resolution → `Closes #N`; related only → `Refs #N`.

Scan B — Related or prior PRs:

- Existing PR for this head: `gh pr list --head <branch> --state open` — update
  it instead of opening a duplicate.
- Code provenance: for the commits this branch builds on,
  `gh api repos/{owner}/{repo}/commits/<sha>/pulls` → `Follow-up to #M` /
  `Supersedes #M`.
- Area overlap: `gh pr list --state open --search "<keyword>"`.
- Stacked base: when `base` is not the default branch, link the base branch's
  PR as the parent.

Output — vetted links for the body or footer: `Closes #N`, `Refs #N`,
`Follow-up to #M`, `Supersedes #M`. Explicit refs from commits or the branch
name link directly; search-derived candidates are proposed for confirmation,
never auto-`Closes`. Never fabricate a link.

Limits: `gh` search filters by keyword, not reliably by file path, so area
overlap is approximate; links exist only when the work genuinely maps;
cross-repo or private refs may not resolve; solo repos surface few Issues.

</RelatedScan>

<Steps>

1. Confirm the user asked to open or update a PR. Inspect: the current branch is
   not the default branch, `git status`, and `git log --oneline <base>..HEAD`
   has commits. Warn that uncommitted changes will not be in the PR.
2. Determine the base: the repo default branch
   (`gh repo view --json defaultBranchRef`), unless the user names one.
3. Push: `git push -u origin HEAD` (gated `ask`). Never force-push unless
   explicitly asked.
4. Detect an existing open PR for the head
   (`gh pr list --head <branch> --state open`). If one exists, update it;
   otherwise create.
5. Build the title and body per <ConventionResolution>, and gather links per
   <RelatedScan>.
6. Create or update: `gh pr create --base <base> --title "..." --body "..."`
   (ready by default; add `--draft` only if asked), or `gh pr edit`. Set
   reviewers, labels, assignees, or a milestone only if the user asked.
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
- Do not force-push unless explicitly asked.
- Do not open a PR from the default branch, and do not duplicate an existing
  open PR — update it.
- Do not silently exclude uncommitted work; warn that only pushed commits ship.
- Do not set reviewers, labels, assignees, or a milestone unless asked.
- Do not fabricate an Issue or PR link — leave it out or ask when unsure.
- Do not invent a title or body convention that contradicts the repo's merged
  PRs.

</AntiPatterns>
