---
name: commit
description: >-
  Use when creating git commits — the convention layer over the git tools:
  resolving the repo's own commit convention, splitting work into atomic
  build-passing commits, writing commit messages that match it, choosing
  between amend, fixup + autosquash and a linked follow-up commit when a change
  belongs to earlier work, and tracing which commit/PR/Issue a change came
  from to link a fix or follow-up (コミット, commit, git commit, atomic commit,
  conventional commits, ステージング, amend, fixup, autosquash, 直前のコミットに
  追加, 前のコミットに混ぜる, どのコミット/PR/Issue 由来, 来歴, blame, bisect,
  trace, provenance). Resolves the commit convention from history → config
  files → Conventional Commits; one concern per commit; never commits secrets.
  How each tool is called is the package skills' job (`git-commit`,
  `git-repo`, `git-rebase`). Do NOT use for creating/merging pull requests or
  pushing — only commit creation and the read-only history tracing that
  supports it.
author: CraftSamo
license: MIT
---

<Goal>

Create the commits the user explicitly asked for, or that an aligned plan's
steps end in: atomic, build-passing, secret-free, and worded to the
repository's own convention. When a change belongs to earlier work, trace its
origin (commit → PR → Issue) and link it precisely instead of guessing.

</Goal>

<Scope>
<UseWhen>

- The user asks to commit, stage, or split changes into commits.
- A step of an aligned plan has verified and ends in its checkpoint commit.
- The user asks which commit / PR / Issue introduced a change, or to link a
  fix or follow-up to its origin.

</UseWhen>

<DoNotUseWhen>

- Creating, merging, or reviewing pull requests, or pushing branches. Reading
  PR/Issue metadata for provenance is in scope; creating them is not.
- Routine or security dependency bumps — use `resolve-dependabot-alerts`.

</DoNotUseWhen>
</Scope>

<Mechanics>

This skill decides what to commit and how to word it; the git-tools package
skills say how each tool is called. Load the package's `git-commit` skill
(`git_commit_read` / `_stage` / `_create` / `_amend` / `_verify`: hunk
listings and their digest, lint and secret checks, `check_failed` details,
rewrite refusals), `git-repo` (`git_repo_read`: status, conflicts,
conventions, origin) and `git-rebase` (`git_rebase_*`: folding fixups,
resuming a stopped rebase) for the call itself, and do not restate them here.

</Mechanics>

<ConventionResolution>

Resolve the message format in this priority order. Detect, do not assume.

1. Existing habit — call `git_repo_read` with `method: "conventions"` for
   recent commit subjects with their type/scope frequencies; infer the type
   set, scope vocabulary, casing, language, body structure, and trailer usage.
   Habit never sets length: <MessageHygiene> owns it. Ignore squash-merge PR
   titles (`... (#NN)`) as machine-generated noise.
2. Convention files — the same call lists any commitlint, `.gitmessage`,
   commitizen, or `CONTRIBUTING` config present; read and honor them. A rule a
   config file states outranks what the history suggests.
3. Fallback — Conventional Commits: `type(scope): subject`.

- Hard gate: when a convention is enforced (a `commit-msg` hook or commitlint),
  the message MUST pass it regardless of habit; `git_commit_create` (and
  `git_commit_read` `lint`) run the repo's commitlint when it is installed.
  When it is not and a `commit-msg` hook needs it, that is an error (install
  the dependencies first, or the hook rejects the commit); a config alone
  makes it a warning (only the built-in rules ran).
- No usable history (empty or brand-new repo, shallow clone): skip to 2,
  then 3.
- Message language follows the dominant language of recent subjects — infer
  it, never assume English.
- If the resolved language is Japanese, also load and apply the
  `japanese-writing` skill for language and notation. Resolve subject/body
  register from the repository's commit convention, not a universal Japanese
  rule; the repo's own convention still outranks the skill on any conflict.

</ConventionResolution>

<CommitGranularity>

A large diff is a signal to split more, not less. When the working diff spans
several files or concerns, decompose further — it is never a reason to lump.
Even one large feature breaks into foundation → core → wiring → tests → docs.
Scope grows the number of commits, not the size of a single commit.

Two invariants, in priority order:

1. Build gate — every commit must build and pass the project's relevant
   checks on its own; never leave an intermediate commit broken. This gate
   constrains ordering and boundaries; it is NOT a license to merge independent
   concerns into one commit. If two parts each build once correctly ordered,
   they are two commits. Merging is justified only by a genuine dangling
   reference (below) — never by diff size or convenience. Within that
   constraint the gate wins every conflict with the rules below.
2. One concern per commit — a vertical slice, not a horizontal layer: the
   change plus the wiring it is incomplete without (implementation, call
   sites, registration or permission, the tests that verify it), even when
   that spans code, config, and prose. Example: a new tool, the permission
   that lets it run, and the skill section that calls it land in one commit —
   split apart, the tool is dead code and the skill references something
   absent.

Split-or-merge test — classify each part once:

- Dangling reference — a call site, import, or registration of something not
  yet present: it breaks the build alone, so it stays with its target.
- Not-yet-used foundation — self-contained, genuinely reusable, builds on its
  own, and only lacks a consumer until a later commit: it may stand as its own
  earlier commit. Reusability is the bar — inert-but-building is never an
  excuse to commit a broken fragment.

Subject test — if the honest subject needs "and", a comma, or a bullet list to
say what the commit does, it is more than one commit. A commit that touches many
files serving distinct concerns is probably several commits — the exception is a
single vertical slice whose parts are co-dependent.

Kind boundaries — separate commits when each side stands alone:

- Refactoring and behavior change never mix; land the refactor first.
- Formatting/whitespace-only churn stays out of logic commits.
- Pure renames or moves get their own commit so content diffs stay readable.
- A dependency bump and its lockfile delta are one commit — never split them.
- Unrelated fixes, chores, and descriptive docs each stand alone.
- Tests ride with the change they verify; only unrelated test work stands
  alone.

Order and size: foundations first (a reusable component, a shared capability),
then the feature that consumes them, then the wiring that exposes it (entry
points, routes, navigation, sitemap). Prefer the finest decomposition in which
every commit still builds; the sequence should read as the construction steps
toward the branch's stated goal, keeping review diffs small and `git bisect`
precise.

Staging the split (hunk listing and staging: the package's `git-commit`):

- One file, several concerns: split it by hunk (`git_commit_read` `hunks`,
  then `git_commit_stage`), not by interactive `git add -p`.
- Mixed changes already staged (e.g. after `git add -A`): unstage with
  `git reset` first, then stage selectively — the hunk listing covers only
  unstaged changes.
- A large pre-written diff (a big branch, many files): do not stage it whole.
  `git reset` to unstage everything, then build the sequence one concern at a
  time — stage only that concern's hunks, confirm with `git diff --cached`,
  commit, and repeat with a fresh listing for the next concern. Iterating
  concern-by-concern is what keeps each commit small; staging all then
  committing once is the failure to avoid.
- Untracked and binary files cannot be hunk-split: `git add <path>` them
  whole, into the commit whose concern they serve.
- One hunk mixing two concerns: edit the file down to the first concern's
  state, commit, then restore the rest — or accept the coarser commit. Never
  commit a broken intermediate; co-dependent changes stay in one commit.

A change that belongs to an earlier commit — decide amend, fixup or a linked
follow-up before committing. `git_commit_read` with `method: "amend"` (pass
the `sha`, default HEAD) classifies it from the package's rewrite rule: a task
branch's own commits may be rewritten even once pushed; never the default
branch, a commit already on it, or one another remote branch holds (the
layers of the branch's own stack excepted), nor a branch GitHub protects
against force pushes.

- `amend` (HEAD): stage the change and call `git_commit_amend` (omit
  `message` to keep HEAD's, or pass the new one to reword).
- `fixup` (an earlier commit of the branch): stage the change, commit it with
  `git_commit_create` and `fixup: <sha>`, then fold it in with
  `git_rebase_start` and `keep_base: true`. A stop on conflicts or an empty
  commit is resolved with `git_rebase_resume` (`git-rebase`).
- When the result says `needs_force_push`, the branch was already pushed: the
  next push is a leased one through the push preview (`pullrequest`
  <Publishing>). On a native stack layer, make the fixup on the top branch
  and fold it with `keep_base: true`; the rebase moves the layers above, and
  `pullrequest` publishes them.
- `new_commit` (refused, or not on this branch): do not rewrite it. Make a
  new commit that links the origin (see <Provenance>), e.g.
  `fix(scope): add missing num arg (follow-up to abc1234)`.

</CommitGranularity>

<Provenance>

Trace a change to its origin and assemble link-ready references. Read-only.

Anchor the symptom: a code location (file + lines) or a behavior (a failing
test / reproduction).

Hop 1 — symptom → commit:

- From a location or a string, `git_repo_read` with `method: "origin"`
  locates the commit: pass `file` + `lines` (blame) or `token` / `regex`
  (pickaxe — when a string entered), or the `sha` itself. It reads the local
  clone only; a commit this clone does not have is read on GitHub.
- From a behavior (most reliable, manual): `git bisect start <bad> <good>` →
  `git bisect run <test-cmd>` → culprit, then `git bisect reset`.
- Caveat: blame reports the last modifier, not necessarily the introducer.
  Pickaxe anchors on the oldest hit (the introducer) and reports the newest
  alongside. Confirm with bisect when it matters.

Hops 2-3 — commit → PR → Issue: `origin` returns the commit's full message,
so read a `(#NN)` in a squash-merge subject, a `Fixes #NN` or a trailer from
it. It does not look up PRs or Issues: find the PR that introduced the commit
with `github_pr_read` (`method: "list"`, `state: "all"`, the short sha or the
`#NN` in `query`), then its `view` for the Issues it closes, and
`github_issue_read` for the Issue itself. For merge-commit repos, confirming
the merge that brought a commit in still helps:
`git log --oneline --merges --ancestry-path <sha>..<branch> | tail -1` (the
oldest listed merge is the one that brought it in).

Reverse (Issue-first fan-out): `github_issue_read` for the Issue, then
`github_pr_read` `list` with the Issue number in `query` → each PR → its
commits.

Output — link-ready references for the message: a commit as a bare short SHA
(`abc1234`, which auto-links on GitHub); a PR/Issue as `#N` / `#M`; footers
`Closes #M` or `Refs: abc1234` when apt.

Limits: blame ≠ introducer; squash/rebase loses intra-PR commit granularity;
Issue links exist only if someone recorded them — never fabricate; bisect needs
a deterministic reproduction; local/unpushed commits have no PR or Issue.

</Provenance>

<Steps>

1. Confirm the user asked to commit, or that this is a verified step of a
   plan the user aligned on (its checkpoint commit is authorized by the plan,
   per the global `<PlanHandoff>`). A narrower restriction from the user or
   the session's instructions wins over the plan. Get the overview with
   `git_repo_read` `status` (branch, staged / unstaged / untracked /
   conflicted files, an operation in progress, the branch's commits since its
   base), then read the content with `git diff` (unstaged) and
   `git diff --cached` (staged); resolve the convention per
   <ConventionResolution>. If an operation is in progress, finish it first:
   map its conflicts with `git_repo_read` `conflicts`, and continue a rebase
   with `git_rebase_resume` (`action: "continue"`).
2. Plan the split along concern and build boundaries (see <CommitGranularity>);
   resolve amend-vs-fixup-vs-link first for changes that belong to earlier
   work. Unless the diff is a single trivial concern, this is a required
   gate: enumerate the concerns, map each to a commit, and present the ordered
   plan (concern → commit → order) before staging anything. A large or
   multi-file diff must produce a multi-commit plan — one fat commit is the
   default to resist, not accept.
3. Stage intentionally: explicit paths, or specific hunks via
   `git_commit_stage`. Never `git add -A` or `git add .` blindly. Re-check
   `git diff --cached`.
4. Write the message per <ConventionResolution> and <MessageHygiene>, wrapped
   exactly as it should land. Add provenance links when committing a fix or
   follow-up.
5. Commit with `git_commit_create` (`message` = the whole message; `fixup`
   per <CommitGranularity>); it lints the text, scans the staged diff for
   secrets and only then commits the same text. Act on a `check_failed`:
   - `lint` — fix the errors (warnings yield to the repo's own convention);
     for `commitlint-not-installed`, install the repo's dependencies first.
   - `secrets` — judge each finding: a genuine secret stops the commit; report
     it and point at `keychain-secrets`. Only when every finding is a clear
     false positive (lockfile integrity hash, minified bundle, fixture data)
     pass its fingerprint in `accept_findings` and note it.
   - `hook` — fix what the hook reports, stage the result and commit again;
     never `--no-verify`.
   A `rewrite_refused` means the amend or fixup is refused (see
   <CommitGranularity>): make a linked follow-up instead. On success, read
   `message_matches` (false means the landed message differs from the linted
   one: read it with `git log -1`), `changed_by_hook` / `left_modified` (stage
   the leftovers into this or the next commit deliberately), `hook_findings`
   (a genuine secret there means the commit must be undone before anything is
   pushed) and `remaining` (whether the planned sequence is done). Commit only
   through `git_commit_create` / `git_commit_amend`: a shell `git commit`
   asks for approval and skips the lint and the secret scan, and retyping a
   linted message into `git commit -m` is how a passing lint still fails the
   hook.
6. Verify the commit passes the project's relevant quick checks — with partial
   staging, a passing worktree does not prove the commit passes on its own.
   For a sequence, `git_commit_verify` (`command` = the quick check, `setup` =
   the dependency install, `dir` = the package directory in a monorepo) runs
   it at every commit in a scratch worktree and names the first failing one;
   it asks for approval each call. On a stacked layer pass `base` = the layer
   below. Without it, run the checks with the leftover changes stashed
   (`git stash push -u` after committing, `git stash pop` when done); at
   minimum verify the final commit of a sequence. Fix breakage immediately —
   with an amend or a fixup while the rewrite rule allows it.
7. Show the result: `git_commit_create` returns the sha and the changed files
   (use `git log --oneline` for a multi-commit sequence).

</Steps>

<MessageHygiene>

Draft the message; `git_commit_create` lints it (and runs the repo's
commitlint when present) before committing. `git_commit_read` `lint` runs the
same checks alone, for a draft you are not committing yet.

- Roles: the subject says what the commit does; the body says why. Describe
  how it works only where the code cannot show it: a rejected alternative, a
  constraint, a side effect, an ordering that matters. A rejected alternative
  belongs to the why. Never walk through the diff step by step: the reader has
  it one command away.
- Subject: imperative, concise. Lengths are display columns (a wide character
  counts two). The target is the repository's own 90th percentile of recent
  subjects, clamped to 50–60, and 50 when fewer than 20 commits are usable;
  squash-merge titles, merges, reverts, fixups, bots and trailer-carrying
  commits do not count. `lint` reports the target it used
  (`subject_target`). The clamp is deliberate: a history of long subjects,
  generated ones included, cannot loosen it. Hard ceiling 72. If commitlint
  enforces a length, that wins.
- Body: wrap near 72 columns. Aim for at most about 12 lines and 800 columns.
  A longer body is acceptable when the why genuinely needs it; past the limit,
  first cut what restates the diff. The history's body lengths set no norm.
- Breaking changes: state them in the form the convention uses — a
  `BREAKING CHANGE:` footer (or `!` after the type) under Conventional
  Commits — and say what a user must change.
- Plain text only: GitHub does not render Markdown in commit messages, so no
  headings, tables, `<details>`, alerts or fenced blocks for prose. Use the
  forms that still auto-link: `#N`, `owner/repo#N`, a bare short SHA.
- Paths and filenames: use sparingly. Never enumerate them; avoid multi-segment
  paths like `src/foo/bar.ts`. A bare filename or a symbol name is fine only
  when it sharpens the explanation.
- Keep out: line numbers; tool, agent, or generator mentions; boilerplate or
  self-evident lines ("update code"); pasted logs or large code blocks; emoji;
  trailers (no `Co-authored-by`, no generated-by) unless the user asks.
- Write for a reader who has only the repository: no plan labels (`Phase 1`,
  `段 B`, `step 2.4`), no numbers from a decision log or task record that are
  not GitHub Issues, no local paths or machine state. A Phase names where the
  work was planned, not what the commit does; the subject lands in PR titles
  and history, so it carries the same exclusions as a PR (`pullrequest`
  <Audience>). The push preview checks subjects against the same rules file
  as branch names, but wording them right starts here.
- References: link a commit by bare short SHA, an Issue or PR by `#number`, and
  use `Closes #M` / `Refs: abc1234` footers when appropriate.
- Lint warnings are advisory: the convention resolved in <ConventionResolution>
  outranks stylistic warnings (e.g. `conventional` in a repo that does not use
  Conventional Commits). Length warnings are not stylistic: shorten unless the
  why needs the room. Errors must be fixed.

</MessageHygiene>

<AntiPatterns>

- Do not commit unless explicitly asked or a verified step of an aligned plan
  calls for it; never commit a plan step whose check failed or did not run.
  Do not work around a gated command by reshuffling flags (e.g. sneaking
  `--amend` or `--no-verify` after `-m`).
- Do not `git add -A` or `git add .` blindly; stage intentionally.
- Do not stage or commit secret values or `.env` files.
- Do not `--no-verify` to skip hooks; fix what the hook flags.
- Do not rewrite a commit that `git_commit_read` `amend` refuses (`new_commit`)
  — on the default branch, already on it, held by another remote branch, or
  on a protected branch — and do not work around a `rewrite_refused` with
  shell git.
- Do not mix unrelated changes or different concerns into one commit.
- Do not use the build gate or a large diff as an excuse to lump independent
  concerns; scope means more commits, not a bigger one.
- Do not invent a convention that contradicts the repo's history.
- Do not add trailers unless asked.
- Do not fabricate provenance — leave a link out rather than guess the
  commit, PR, or Issue.

</AntiPatterns>
