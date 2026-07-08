---
name: git-commit
description: >-
  Use when creating git commits — staging, splitting work into atomic
  build-passing commits, writing commit messages that match the repo's own
  convention, folding a change into an earlier local commit, and tracing which
  commit/PR/Issue a change came from to link a fix or follow-up (コミット,
  commit, git commit, atomic commit, conventional commits, ステージング, amend,
  fixup, 直前のコミットに追加, どのコミット/PR/Issue 由来, 来歴, blame, bisect,
  trace, provenance). Resolves the commit convention from history → config
  files → Conventional Commits; one concern per commit; never commits secrets.
  Do NOT use for creating/merging pull requests or pushing — only commit
  creation and the read-only history tracing that supports it.
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
  the message MUST pass it regardless of habit; `git_commit_lint` runs the
  repo's commitlint when it is present.
- No usable history (empty or brand-new repo, shallow clone): skip to 2,
  then 3.
- Message language follows the dominant language of recent subjects — infer
  it, never assume English.

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
  hunks with stable ids, then stage exactly the ones for this commit (by id,
  or with include/exclude; set `denySecrets` for risky content). It applies
  them deterministically via `git apply --cached`, avoiding fragile
  interactive `git add -p`. Verify with `git diff --cached` before committing.
- Mixed changes already staged (e.g. after `git add -A`): unstage with
  `git reset` first, then stage selectively — the tool lists only unstaged
  hunks.
- A large pre-written diff (a big branch, many files): do not stage it whole.
  `git reset` to unstage everything, then build the sequence one concern at a
  time — stage only that concern's hunks with `git_stage_hunks`, confirm with
  `git diff --cached`, commit, and repeat for the next concern. Iterating
  concern-by-concern is what keeps each commit small; staging all then
  committing once is the failure to avoid.
- Untracked and binary files cannot be hunk-split: `git add <path>` them
  whole, into the commit whose concern they serve.
- One hunk mixing two concerns: edit the file down to the first concern's
  state, commit, then restore the rest — or accept the coarser commit. Never
  commit a broken intermediate; co-dependent changes stay in one commit.
- A change that belongs to an earlier commit: run `git_amend_check` (pass the
  `sha`, default HEAD) to classify it.
  - `amend` / `fixup` (local, unpushed): fold it in with `git commit --amend`
    (for HEAD) or `git commit --fixup=<sha>` followed by
    `git rebase -i --autosquash`.
  - `linked-fix` (already pushed or on another branch): do not rewrite it. Make
    a new commit that links the origin (see <Provenance>), e.g.
    `fix(scope): add missing num arg (follow-up to abc1234)`.

</CommitGranularity>

<Provenance>

Trace a change to its origin and assemble link-ready references. Read-only.

Anchor the symptom: a code location (file + lines) or a behavior (a failing
test / reproduction).

Hop 1 — symptom → commit:

- From a location or a string, `git_provenance` locates the commit for you:
  pass `file` + `lines` (blame) or `token` / `regex` (pickaxe — when a string
  entered), and it continues straight into hops 2-3.
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

1. Confirm the user asked to commit. Inspect: `git status` (including
   untracked files), `git diff` (unstaged) and `git diff --cached` (staged);
   resolve the convention per <ConventionResolution>.
2. Plan the split along concern and build boundaries (see <CommitGranularity>);
   resolve amend-vs-link first for changes that belong to earlier work. Unless
   the diff is a single trivial concern, this is a required gate: enumerate the
   concerns, map each to a commit, and present the ordered plan
   (concern → commit → order) before staging anything. A large or multi-file
   diff must produce a multi-commit plan — one fat commit is the default to
   resist, not accept.
3. Stage intentionally: explicit paths, or specific hunks via `git_stage_hunks`.
   Never `git add -A` or `git add .` blindly. Re-check `git diff --cached`.
4. Scan the staged diff with `git_secret_scan` (built-in rules plus gitleaks
   when available; values are redacted). Judge each finding: a genuine secret
   stops the commit — report it and point at `keychain-secrets`; a clear false
   positive (lockfile integrity hash, minified bundle, fixture data) does not —
   proceed and note it.
5. Write the message per <ConventionResolution> and <MessageHygiene>, then
   validate it with `git_commit_lint`; fix errors before committing (warnings
   yield to the repo's own convention). Add provenance links when committing a
   fix or follow-up.
6. Commit with the message-bearing form: `git commit -m "subject" -m "body
   paragraph"` (one `-m` per paragraph), or `-m "$(cat <<'EOF' ... EOF)"` for
   longer bodies — never encode newlines as literal `\n`. If pre-commit hooks
   or formatters modify files, re-stage and redo steps 4-5 before committing
   again; if a hook rejects, fix the cause and re-commit — never `--no-verify`.
7. Verify the commit passes the project's relevant quick checks — with partial
   staging, a passing worktree does not prove the commit passes on its own.
   For a strict check, run the checks with the leftover changes stashed
   (`git stash push -u` after committing, `git stash pop` when done); at
   minimum
   verify the final commit of a sequence. Fix breakage immediately — `--amend`
   while still local.
8. Show the result: `git show --stat HEAD` (or `git log --oneline` for a
   multi-commit sequence).

</Steps>

<MessageHygiene>

Draft the message, then check it with `git_commit_lint` — it validates the
rules below (and the repo's commitlint when present).

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
- Do not `--amend` or force-push a commit that is already pushed or shared.
- Do not mix unrelated changes or different concerns into one commit.
- Do not use the build gate or a large diff as an excuse to lump independent
  concerns; scope means more commits, not a bigger one.
- Do not invent a convention that contradicts the repo's history.
- Do not add trailers unless asked.
- Do not fabricate provenance — leave a link out rather than guess the
  commit, PR, or Issue.

</AntiPatterns>
