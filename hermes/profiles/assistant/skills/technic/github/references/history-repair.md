# History repair: what to commission, with the user's go

Everything here rewrites history or force-pushes, so none of it is the
Assistant's to run. Each needs the user's explicit go for that repair, named
in plain words (which branches or main, what changes, what the PR pages keep
showing), then an OpenCode build run commissioned as `opencode:brief` says:
the repair as an outcome, the conditions it must meet afterwards, what to
hand back, and that nothing else changes (no merge, no retarget, no other
branch). How it gets there, which commands and in what order, is the run's.
Read the result back yourself with `github_pr_read` `view` and a fetch of the
clone before reporting it done.

Two limits shape every brief. A build pushes only the task branch its
worktree is on (with a lease) and a native stack's layers (through its
publishing request), never main or any other branch. So commission a
branch's repair from the session that built it, a chain's after it is linked
into a native stack (below); main, or a branch no build session holds, ends
with a verified result the user pushes, never a push of the run's. And every
push is against the tip the run read, so a change made meanwhile refuses it:
when several branches move, ask that every condition holds locally before
anything is pushed, and that a refused push stops the run with each branch's
state reported.

## Commit messages on a multi-commit branch

For a pull request whose commits keep their messages on main (a merge
commit), the repo-external words leave the branch itself before the merge.
Commission the rewritten messages, from the session that built the branch,
with these conditions: the branch's tree is identical before and after;
commits outside the scan keep their message and author; the pull request's
base, commit count and additions are unchanged after the push. Ask back the old and new tip and the evidence for each
condition.

## Wording that already landed on main

- **Commit messages on main:** the run rewrites them on a fresh, separate
  clone, never the person's checkout, and hands back a main whose tree equals
  the old one and whose messages hold none of the scanned words. The user
  pushes it to main against the old tip (main's ruleset needs the admin
  bypass), so nothing that landed meanwhile is lost; afterwards the local clones are reset and the worktrees of merged
  branches dropped.
- **File contents** (docs, comments, error strings and the tests that match
  them) are never rewritten with a blind regex across files: a string
  constant and the test that matches it change together. Hand the scan's
  findings (each file and the term found in it) to a build run as one
  ordinary pull request, never as part of a history rewrite: what must be
  gone, not where to edit.
- After that pull request merges, run the same scan again over PR titles and
  bodies and the new main: a rewrite leaves residue shapes the first pattern
  missed (orphan punctuation where an id was removed, near-variants of an
  environment phrase). Phase names in a public roadmap or a tool's own config
  are legitimate: list them as kept on purpose.
- A remediation for an incident (a script, a note) belongs outside the
  repository: no commit, doc or PR text mentions it.

## Re-seating a chain onto main

For a chain or stack whose next branch still carries a merged pull request's
original commits, or a `Merge branch 'main'` commit. Whether a branch needs
it is decided by its fork point (it should fork from the current main), never
by its commit count: after a merge commit the count still matches.

Commission each affected branch re-seated onto main, from the session that
built the stack (a plain chain is linked first, below), with these
conditions, checked before anything is pushed and again after: the top
branch's tree is unchanged; each branch holds one commit per pull request and
no merge commit; each pull request keeps its original additions and
deletions. Ask back each branch's old and new tip and, per pull request, its base,
commit count and line counts after the push. Any scratch branches or
worktrees the run made for it are gone at the end.

After a bypass merge the user made in GitHub's page, the next layer is often
not re-seated the way a normal merge does: check its base, commit count and
additions after a minute, and if the merged commit is still inside it, this
re-seat is the fix.

## Repairing a main whose merge commits forked from the wrong place

The run rebuilds main from the last good merge in a separate clone, each bad
merge replaced by one that forks from the merge before it. Conditions: each
replayed commit keeps its tree, author and committer date; each new merge's
tree equals the original's and keeps its subject, author and date; each
merge's first parent is its fork point; the final tree equals the
old main's; what is handed back is exactly what was verified. The run stops
there and reports the new tip: the push replaces main against the old tip and
needs the ruleset's admin bypass, so it is the user's, and you re-run the
per-merge check on the fetched main afterwards. Tell the user what changes:
the pull request pages keep the old merge shas, and merge commits made
locally carry no "Verified" mark.

## Linking a chain into a native stack

Existing pull requests become one native stack, bottom to top on the trunk,
without any branch moving or being pushed: commission that outcome, and ask
back each branch's tip before and after (identical) and the stack's size and order. Then
check `stack` on the top pull request with `github_pr_read` `view` (size, the
trunk as base, the entry order). For layered work, ask for this from the first
layer, each new pull request linked as it opens. A chain can also be linked
from GitHub's page, where an eligible pull request shows a banner; prefer
that, or a link of existing pull requests, over starting a new stack on
existing branches, which can rebase and force-push them.
