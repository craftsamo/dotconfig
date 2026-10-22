# History repair: what a build run does, with the user's go

Everything here rewrites history or force-pushes, so none of it is the
Assistant's to run. Each needs the user's explicit go for that repair, named
in plain words (which branches or main, what changes, what the PR pages keep
showing), then an OpenCode build run whose brief carries the steps below and
forbids anything else (no merge, no retarget, no other branch). Read the
result back yourself with `github_pr` `view` and a fetch of the clone before
reporting it done.

Brief each stage as its own simple command (make the worktree, rebase,
verify, push, re-check, clean up): one compound command with loops, `$(…)`
and destructive cleanup trips the command-approval scan, and keeping the
read-only checks apart from deletions means a timeout never strands a check.

## Commit messages on a multi-commit branch

For a pull request whose commits keep their messages on main (a merge
commit), the repo-external words are removed from the branch itself: rewrite
the messages (`git filter-repo --message-callback`, or a rebase with an
`--exec` amend), then verify the tree is identical (`git diff --stat <old
tip> <new tip>` empty), that commits outside the scan kept their message and
author, and that the pull request's base, commit count and additions are
unchanged after a `--force-with-lease` push.

## Wording that already landed on main

- **Commit messages on main:** `git filter-repo --message-callback` on a
  fresh `--no-local` clone; `git diff --stat <old tip> HEAD` must be empty and
  the grep over `git log --format=%B` zero. Force-push to main with a fixed
  lease; afterwards the local clones are reset and the worktrees of merged
  branches dropped.
- **File contents** (docs, comments, error strings and the tests that match
  them) are never rewritten with a blind regex across files: a string
  constant and the test that matches it change together. Hand the list (file,
  line, term) to a build run as one ordinary pull request, never as part of a
  history rewrite.
- After that pull request merges, run the same scan again over PR titles and
  bodies and the new main: a rewrite leaves residue shapes the first pattern
  missed (orphan punctuation where an id was removed, near-variants of an
  environment phrase). Phase names in a public roadmap or a tool's own config
  are legitimate: list them as kept on purpose.
- A remediation for an incident (a script, a note) belongs outside the
  repository: no commit, doc or PR text mentions it.

## Re-seating a chain onto main

For a chain or stack whose next branch still carries a merged pull request's
original commits, or a `Merge branch 'main'` commit.

1. Fetch and read the real shape: `git log --graph --format='%h %s'
   origin/main~1..origin/<top branch>` and each branch's parent. Note each
   branch's current sha: these are the lease values.
2. In a throwaway worktree (`git worktree add --detach <tmp> origin/<top>`),
   make a local branch at each member's tip; if the bottom member's tip is
   the merge commit, point it at the last good commit before it.
3. `git rebase --update-refs --onto origin/main <merged original sha> <top
   local branch>` moves every intermediate branch with it.
4. Verify before pushing: `git diff --stat origin/<top> <top local>` empty,
   `git log origin/main..<top local>` shows one conventional commit per pull
   request and no merge commit, and each branch's `git diff --shortstat
   <b>~1 <b>` matches its pull request's original additions and deletions.
   Whether a branch needs re-seating is decided by its fork point
   (`git merge-base origin/main origin/<branch>` equals `origin/main`), never
   by its commit count: after a merge commit the count still matches.
5. Push all members in one `git push --atomic origin
   --force-with-lease=<branch>:<old sha> … <local>:<branch> …`, so a
   concurrent change aborts everything.
6. Re-check each pull request (base, commit count, original line counts),
   then clean up: `git checkout --detach` in the worktree first (git refuses
   to delete a branch a worktree has checked out), `branch -D` the temporary
   branches, `worktree remove`. A failure there leaves only cleanup to redo.

After a bypass merge the user made in GitHub's page, the next layer is often
not re-seated the way a normal merge does: check its base, commit count and
additions after a minute, and if the merged commit is still inside it, this
re-seat is the fix.

## Repairing a main whose merge commits forked from the wrong place

In a throwaway worktree at the last good merge, for each bad merge M in
order: cherry-pick its branch commits (`git rev-list --reverse M^1..M^2`) with
the original committer dates, checking each tree equals the original's; then
from the pre-pick head `git merge --no-ff` the new tip with M's subject,
author and date. Each merge's tree must equal M's and `HEAD^1` must equal
`merge-base(HEAD^1, HEAD^2)`; the final tree must equal the old main's. Push
with `git push --force-with-lease=main:<old main sha> origin
<new sha>:refs/heads/main` (main's ruleset needs the admin bypass), then
re-run the per-merge check on the fetched main. Build it as one script with a
build mode and a push mode, so the verified result is exactly what is pushed.
Tell the user what changes: the pull request pages keep the old merge shas,
and merge commits made locally carry no "Verified" mark.

## Linking a chain into a native stack

Without touching branches: `gh stack link --base <trunk> <PR numbers bottom
to top>` (the `github/gh-stack` extension; numbers, not branch names, take the
no-push path). Record `git ls-remote --heads origin '<prefix>*'` before and
compare after (shas identical), then check `stack` on the top pull request
with `github_pr` `view` (size, the trunk as base, the entry order). For
layered work, put this duty in the build brief from the first layer, linking
after each new pull request. A chain can also be linked from GitHub's page,
where an eligible pull request shows a banner; prefer that, or `link`, over
`gh stack init` on existing branches, which can rebase and force-push.
