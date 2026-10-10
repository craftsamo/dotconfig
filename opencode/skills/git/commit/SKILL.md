---
name: git-commit
description: >-
  Use when creating git commits — staging, splitting work into atomic
  build-passing commits, writing commit messages that match the repo's own
  convention, folding a change into an earlier commit of the branch (amend,
  fixup + autosquash), and tracing which commit/PR/Issue a change came from to
  link a fix or follow-up (コミット, commit, git commit, atomic commit,
  conventional commits, ステージング, amend, fixup, autosquash, 直前のコミットに
  追加, 前のコミットに混ぜる, どのコミット/PR/Issue 由来, 来歴, blame, bisect,
  trace, provenance). Resolves the commit convention from history → config
  files → Conventional Commits; one concern per commit; never commits secrets.
  Do NOT use for creating/merging pull requests or pushing — only commit
  creation and the read-only history tracing that supports it.
author: CraftSamo
license: MIT
---

<Goal>

Create the commits the user explicitly asked for: atomic, build-passing,
secret-free, and worded to the repository's own convention. When a change
belongs to earlier work, trace its origin (commit → PR → Issue) and link it
precisely instead of guessing.

</Goal>

<Scope>
<UseWhen>

- The user asks to commit, stage, or split changes into commits.
- The user asks which commit / PR / Issue introduced a change, or to link a
  fix or follow-up to its origin.

</UseWhen>

<DoNotUseWhen>

- Creating, merging, or reviewing pull requests, or pushing branches. Reading
  PR/Issue metadata for provenance is in scope; creating them is not.
- Routine or security dependency bumps — use `resolve-dependabot-alerts`.

</DoNotUseWhen>
</Scope>

<ConventionResolution>

Resolve the message format in this priority order. Detect, do not assume.

1. Existing habit — call `git_history_digest` for recent commit subjects with
   their type/scope frequencies; infer the type set, scope vocabulary, casing,
   language, body norms, and trailer usage. Ignore squash-merge PR titles
   (`... (#NN)`) as machine-generated noise.
2. Convention files — `git_history_digest` also reports any commitlint,
   `.gitmessage`, commitizen, or `CONTRIBUTING` config present; honor them.
3. Fallback — Conventional Commits: `type(scope): subject`.

- Hard gate: when a convention is enforced (a `commit-msg` hook or commitlint),
  the message MUST pass it regardless of habit; `git_commit` (and
  `git_commit_lint`) run the repo's commitlint when it is installed. When it
  is not, a `commit-msg` hook that runs it makes `commitlint-not-installed` an
  error (install the dependencies first, or the hook rejects the commit); a
  config alone makes it a warning (only the built-in rules ran).
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

Mechanics:

- One file, several concerns: split by hunk with `git_stage_hunks` — list the
  hunks, then stage exactly the ones for this commit (by id, or with
  include/exclude; set `denySecrets` for risky content), passing the
  listing's `token`. It applies them deterministically via
  `git apply --cached`, avoiding fragile interactive `git add -p`. Ids are
  positions in one listing: after any staging they shift, so list again
  before the next selection; the `token` makes a stale selection fail instead
  of staging other hunks. Verify with `git diff --cached` before committing.
- Mixed changes already staged (e.g. after `git add -A`): unstage with
  `git reset` first, then stage selectively — the tool lists only unstaged
  hunks.
- A large pre-written diff (a big branch, many files): do not stage it whole.
  `git reset` to unstage everything, then build the sequence one concern at a
  time — list and stage only that concern's hunks with `git_stage_hunks`,
  confirm with `git diff --cached`, commit, and repeat (with a fresh listing)
  for the next concern. Iterating concern-by-concern is what keeps each
  commit small; staging all then committing once is the failure to avoid.
- Untracked and binary files cannot be hunk-split: `git add <path>` them
  whole, into the commit whose concern they serve.
- One hunk mixing two concerns: edit the file down to the first concern's
  state, commit, then restore the rest — or accept the coarser commit. Never
  commit a broken intermediate; co-dependent changes stay in one commit.
- A change that belongs to an earlier commit: run `git_amend_check` (pass the
  `sha`, default HEAD) to classify it. A task branch's own commits may be
  rewritten even once pushed; it refuses (and recommends `linked-fix`) on the
  default branch, for a commit already on it or held by another remote branch
  (layers above it in the same native stack excepted), and when GitHub
  protects the pushed branch against force pushes. `git_commit` and
  `git_rebase` apply the same rule themselves (`stoppedAt: rewrite`).
  - `amend` (HEAD): stage the change and `git_commit` with `amend: true`
    (omit `message` to keep HEAD's, or pass the new one to reword).
  - `fixup` (an earlier commit of the branch): stage the change, `git_commit`
    with `fixup: <sha>` (the `fixup! <subject>` message is generated), then
    fold it in with `git_rebase` (`action: start`, `keepBase: true`). If it
    stops at `conflicts`, resolve the files from its conflict map, `git add`
    them and `git_rebase` with `action: continue` (or `abort` to restore);
    `empty` means the commit has nothing left (`action: skip`), while
    `rebase` with `inProgress` means fix what `output` names and continue.
  - When the result says `needsForcePush`, the branch was already pushed: the
    next push is `git push --force-with-lease origin HEAD:refs/heads/<branch>`
    (gated `ask`). On a native
    stack layer, fold with `keepBase: true` as well, then `gh stack rebase`
    moves the layers above and `gh stack push` publishes them.
  - `linked-fix` (refused): do not rewrite it. Make a new commit that links
    the origin (see <Provenance>), e.g.
    `fix(scope): add missing num arg (follow-up to abc1234)`.

</CommitGranularity>

<Provenance>

Trace a change to its origin and assemble link-ready references. Read-only.

Anchor the symptom: a code location (file + lines) or a behavior (a failing
test / reproduction).

Hop 1 — symptom → commit:

- From a location or a string, `git_provenance` locates the commit for you:
  pass `file` + `lines` (blame) or `token` / `regex` (pickaxe — when a string
  entered), and it continues straight into hops 2-3. Blame and pickaxe need
  the local clone; for a commit of another repository pass its `sha` with
  `repo` (`owner/name`), which reads it from GitHub.
- From a behavior (most reliable, manual): `git bisect start <bad> <good>` →
  `git bisect run <test-cmd>` → culprit, then `git bisect reset`.
- Caveat: blame reports the last modifier, not necessarily the introducer.
  Pickaxe anchors on the oldest hit (the introducer) and reports the newest
  alongside. Confirm with bisect when it matters.

Hops 2-3 — commit → PR → Issue: call `git_provenance` with the `sha` (or
`file` + `lines`, or `token` / `regex`, to locate it first). It returns the
commit, the PRs that introduced it, and the Issues those PRs close, with
link-ready refs
(bare short SHA, `#PR`, `#Issue`). For merge-commit repos, confirming the merge
that brought a commit in still helps:
`git log --oneline --merges --ancestry-path <sha>..<branch> | tail -1` (the
oldest listed merge is the one that brought it in).

Reverse (Issue-first fan-out): `gh issue view <M> --json title,body` and
`gh pr list --search "<M>"` → each PR → its commits.

Output — link-ready references for the message: a commit as a bare short SHA
(`abc1234`, which auto-links on GitHub); a PR/Issue as `#N` / `#M`; footers
`Closes #M` or `Refs: abc1234` when apt.

Limits: blame ≠ introducer; squash/rebase loses intra-PR commit granularity;
Issue links exist only if someone recorded them — never fabricate; bisect needs
a deterministic reproduction; local/unpushed commits have no PR or Issue.

</Provenance>

<Steps>

1. Confirm the user asked to commit. Get the overview with `git_state` (branch,
   staged / unstaged / untracked / conflicted files, an operation in progress,
   the branch's commits since its base), then read the content with `git diff`
   (unstaged) and `git diff --cached` (staged); resolve the convention per
   <ConventionResolution>. If an operation is in progress, finish it first:
   map its conflicts with `git_conflicts`, and continue a rebase with
   `git_rebase` (`action: continue`).
2. Plan the split along concern and build boundaries (see <CommitGranularity>);
   resolve amend-vs-link first for changes that belong to earlier work. Unless
   the diff is a single trivial concern, this is a required gate: enumerate the
   concerns, map each to a commit, and present the ordered plan
   (concern → commit → order) before staging anything. A large or multi-file
   diff must produce a multi-commit plan — one fat commit is the default to
   resist, not accept.
3. Stage intentionally: explicit paths, or specific hunks via `git_stage_hunks`.
   Never `git add -A` or `git add .` blindly. Re-check `git diff --cached`.
4. Write the message per <ConventionResolution> and <MessageHygiene>, wrapped
   exactly as it should land. Add provenance links when committing a fix or
   follow-up.
5. Commit with `git_commit` (`message` = the whole message; `amend` / `fixup`
   per <CommitGranularity>). It lints that text (built-in rules plus the
   repo's commitlint), scans the staged diff for secrets (built-in rules plus
   gitleaks; values redacted), and only then runs `git commit -F` on the same
   file, so the hook sees what was linted. Pass `allowTrailers: true` only
   when the user asked for a trailer. Act on `stoppedAt`:
   - `rewrite` — the amend or fixup is refused (see <CommitGranularity>):
     make a linked-fix commit instead.
   - `lint` — fix the errors (warnings yield to the repo's own convention);
     for `commitlint-not-installed`, install the repo's dependencies first.
   - `secrets` — judge each finding: a genuine secret stops the commit; report
     it and point at `keychain-secrets`. Only when every finding is a clear
     false positive (lockfile integrity hash, minified bundle, fixture data)
     retry with `acceptSecretFindings: true` and note it.
   - `hook` — a commit failed while hooks are installed: read `output`. Fix
     what a hook reports and commit again; never `--no-verify`. The same
     output can also be git's own refusal (identity, signing, unmerged
     paths), which `commit` names when no hook is installed.
   - `stopped` — the session stopped the call; nothing was committed.
   On success, check `messageMatches` (false means the landed message differs
   from the linted one: read it with `git log -1`). `changedByHook` /
   `leftModified` name files a hook rewrote or left modified: re-check them,
   and stage the leftovers into this or the next commit deliberately.
   `hookFindings` are secrets in what a hook staged; a genuine one means the
   commit must be undone before anything is pushed. `remaining` counts what is
   still uncommitted, which tells whether the planned sequence is done.
   Commit only through `git_commit`: a shell `git commit` asks for approval
   and skips the lint and the secret scan, and retyping a linted message into
   `git commit -m` is how a passing lint still fails the hook.
6. Verify the commit passes the project's relevant quick checks — with partial
   staging, a passing worktree does not prove the commit passes on its own.
   For a sequence, `git_verify_commits` (`command` = the quick check, `setup`
   = the dependency install, `cwd` = the package directory in a monorepo)
   runs it at every commit in a scratch worktree and names the first failing
   one; it asks for approval each call. It checks the commits after the
   merge-base with the default branch, at most 30: on a stacked layer pass
   `base` = the layer below. Without it, run the checks with the leftover
   changes stashed (`git stash push -u` after committing, `git stash pop` when
   done); at minimum verify the final commit of a sequence. Fix breakage
   immediately — with an amend or a fixup while the rewrite rule allows it.
7. Show the result: `git_commit` returns the sha, subject and stat (use
   `git log --oneline` for a multi-commit sequence).

</Steps>

<MessageHygiene>

Draft the message; `git_commit` validates the rules below (and the repo's
commitlint when present) before committing. `git_commit_lint` runs the same
checks alone, for a draft you are not committing yet.

- Subject: imperative, concise. Target ≤ 50 characters, hard ceiling 72. If
  commitlint enforces a length, that wins.
- Body: wrap near 72 columns. Explain what changed and why; do not mechanically
  restate the diff.
- Paths and filenames: use sparingly. Never enumerate them; avoid multi-segment
  paths like `src/foo/bar.ts`. A bare filename or a symbol name is fine only
  when it sharpens the explanation.
- Keep out: line numbers; tool, agent, or generator mentions; boilerplate or
  self-evident lines ("update code"); pasted logs or large code blocks; emoji;
  trailers (no `Co-authored-by`, no generated-by) unless the user asks.
- References: link a commit by bare short SHA, an Issue or PR by `#number`, and
  use `Closes #M` / `Refs: abc1234` footers when appropriate.
- Lint warnings are advisory: the convention resolved in <ConventionResolution>
  outranks stylistic warnings (e.g. `conventional` in a repo that does not use
  Conventional Commits). Errors must be fixed.

</MessageHygiene>

<AntiPatterns>

- Do not commit unless explicitly asked; do not work around a gated command by
  reshuffling flags (e.g. sneaking `--amend` or `--no-verify` after `-m`).
- Do not `git add -A` or `git add .` blindly; stage intentionally.
- Do not stage or commit secret values or `.env` files.
- Do not `--no-verify` to skip hooks; fix what the hook flags.
- Do not rewrite a commit that `git_amend_check` refuses — on the default
  branch, already on it, held by another remote branch, or on a protected
  branch — and do not work around a `stoppedAt: rewrite` with shell git.
- Do not mix unrelated changes or different concerns into one commit.
- Do not use the build gate or a large diff as an excuse to lump independent
  concerns; scope means more commits, not a bigger one.
- Do not invent a convention that contradicts the repo's history.
- Do not add trailers unless asked.
- Do not fabricate provenance — leave a link out rather than guess the
  commit, PR, or Issue.

</AntiPatterns>
