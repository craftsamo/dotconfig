---
name: git-commit
description: >-
  Use when creating git commits — staging, splitting work into atomic
  build-passing commits, writing commit messages that match the repo's own
  convention, and tracing which commit/PR/Issue a change came from to link a
  fix or follow-up (コミット, commit, git commit, atomic commit, conventional
  commits, ステージング, どのコミット/PR/Issue 由来, 来歴, blame, bisect, trace,
  provenance). Resolves the commit convention from history → config files →
  Conventional Commits; one concern per commit; never commits secrets. Do NOT
  use for creating/merging pull requests or pushing — only commit creation and
  the read-only history tracing that supports it.
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

1. Existing habit — read recent history and infer the type set, scope
   vocabulary, casing, language, body norms, and trailer usage:
   `git log --no-merges -30 --pretty='%s%n%b%n--'`. Ignore squash-merge PR
   titles (`... (#NN)`) as machine-generated noise.
2. Convention files — `commitlint.config.*`, `.commitlintrc*`, `.gitmessage`,
   `CONTRIBUTING.md`, commitizen config.
3. Fallback — Conventional Commits: `type(scope): subject`.

- Hard gate: when a convention is enforced (a `commit-msg` hook or commitlint
  in CI), the message MUST pass it regardless of habit.
- Subject language follows the repo's habit (English in this repo).

</ConventionResolution>

<CommitGranularity>

- Build gate (highest priority): every commit must build and pass the
  project's relevant checks on its own. Never split in a way that leaves an
  intermediate commit broken.
- One concern per commit — a vertical slice, not a horizontal layer. A concern
  is a coherent change together with the wiring it is incomplete without: the
  implementation, its call sites, its registration or permission, and the
  integration that makes it actually run. Keep these together even when they
  span code, config, and skill prose. Example: a new tool, the permission that
  lets it run, and the skill section that calls it land in one commit — split
  apart, the tool is dead code and the skill references something absent.
- Separate by kind only when the parts stand alone. Independently meaningful
  changes — descriptive docs about a feature, a standalone refactor, an
  unrelated test or chore — stay in their own commits. Test: if splitting leaves
  a part inert (dead code) or dangling (a reference to something not yet
  present), it is one concern; if each part is meaningful and the build is
  coherent in either order, separate them.
- Smallest atomic unit within a concern: when one file holds unrelated
  changes, split by hunk. `git add -p` is interactive and awkward for an
  agent — prefer a patch: `git diff -- <file> > /tmp/p.diff`, trim it to the
  wanted hunks, then `git apply --cached /tmp/p.diff`. Verify with
  `git diff --cached` before committing.
- Never split co-dependent hunks: changes that must land together to keep the
  build or semantics intact stay in one commit. The build gate wins over
  granularity.
- A change that belongs to an earlier commit:
  - Earlier commit is local and unpushed (verify: `git branch -r --contains
    <sha>` is empty, i.e. not in `@{upstream}`): fold it in with
    `git commit --amend` (for HEAD) or `git commit --fixup=<sha>` followed by
    `git rebase -i --autosquash`.
  - Earlier commit is already pushed or on another branch: do not rewrite it.
    Make a new commit that links the origin (see <Provenance>), e.g.
    `fix(scope): add missing num arg (follow-up to abc1234)`.

</CommitGranularity>

<Provenance>

Trace a change to its origin and assemble link-ready references. Read-only.

Anchor the symptom: a code location (file + lines) or a behavior (a failing
test / reproduction).

Hop 1 — symptom → commit:

- From a location: `git blame -w -C -L <a>,<b> -- <file>` (last touch);
  `git log -L <a>,<b>:<file>` (line history); pickaxe
  `git log -S'<token>' -- <file>` or `-G'<regex>'` (when a string entered).
- From a behavior (most reliable): `git bisect start <bad> <good>` →
  `git bisect run <test-cmd>` → culprit, then `git bisect reset`.
- Caveat: blame reports the last modifier, not necessarily the introducer.
  Confirm with pickaxe or bisect.

Hop 2 — commit → PR:

- `gh api repos/{owner}/{repo}/commits/<sha>/pulls --jq '.[].number'`.
- Detect merge style from history: squash repos → the commit subject ends with
  `(#N)`; merge repos → `git log --merges --ancestry-path <sha>..<branch>` →
  first merge → parse `#N`.

Hop 3 — PR → Issue:

- `gh pr view <N> --json closingIssuesReferences,title,body` →
  `closingIssuesReferences[].number`; also parse the body for
  `Closes/Fixes/Resolves #\d+`.

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

1. Confirm the user asked to commit. Inspect: `git status`, `git diff`
   (unstaged) and `git diff --cached` (staged), and recent `git log` for style.
2. Plan the split along concern and build boundaries (see <CommitGranularity>).
   If a change belongs to earlier work, resolve amend-vs-link first.
3. Stage intentionally: explicit paths, or hunks via `git apply --cached`.
   Never `git add -A` or `git add .` blindly. Re-check `git diff --cached`.
4. Scan the staged diff for secrets — `.env`, keys, tokens, credentials. Never
   stage or commit secret values (see `keychain-secrets`). Stop and report if
   any appear.
5. Write the message per <ConventionResolution> and <MessageHygiene>. Add
   provenance links when committing a fix or follow-up.
6. Run hooks and formatters. If they modify files, re-stage and re-verify. If a
   hook rejects the commit, fix the cause and re-commit — never `--no-verify`.
7. Commit, then show the result: `git show --stat HEAD` (or `git log -1`).

</Steps>

<MessageHygiene>

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

</MessageHygiene>

<AntiPatterns>

- Do not commit unless explicitly asked; do not bypass the `git commit`
  approval gate.
- Do not `git add -A` or `git add .` blindly; stage intentionally.
- Do not stage or commit secret values or `.env` files.
- Do not `--no-verify` to skip hooks; fix what the hook flags.
- Do not `--amend` or force-push a commit that is already pushed or shared.
- Do not mix unrelated changes or different concerns into one commit.
- Do not invent a convention that contradicts the repo's history.
- Do not add trailers unless asked.
- Do not fabricate provenance — leave a link out rather than guess the
  commit, PR, or Issue.

</AntiPatterns>
