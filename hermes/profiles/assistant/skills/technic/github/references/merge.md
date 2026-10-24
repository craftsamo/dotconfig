# Merging pull requests

How to merge is the `pr_merge` mechanics in
`skill_view(name="github-access:github-pr")`. This adds what this user
expects of a merge: which method, which message, in which order, and how to
read what went wrong. It applies only after the user said to merge that pull
request; green CI never implies it.

## Before the card

1. `github_pr` `view`: `mergeable`, the merge state, the base, the commit
   count (`size.commits`), the checks, the review decision, and `stack`.
2. Wait for CI as [ci](ci.md) says: no pending check is not green.
3. Count the commits of every pull request in a batch, the top one included,
   before presenting the plan: a miscount changes the method.

## Method and message (this user's convention)

For a pull request that lands alone. Two or more stacked layers landing in
one merge follow "Stacks and chains" below.

- **One commit: squash.** `subject` = the commit's own subject + ` (#n)`,
  `body` = the commit's own body (read it with `git log -1 --format=%B <sha>`
  in a clone). Always pass both: repository squash settings and other
  merge screens then cannot change what lands.
- **Several commits: a merge commit, not squash.** `subject` = the PR title +
  ` (#n)`, `body` = `""`. The history keeps its commits and the PR title is the
  one summary line. "Squash everything with the PR title" is the wrong
  reading.
- **When the repository does not allow that method** (`github_repo` `view`
  shows the merge settings; `pr_merge` refuses it), stop and tell the user.
  Never fall back to another method on your own.
- **Every message that lands is scanned first** for repo-external words, as
  [text-hygiene](text-hygiene.md) says:
  - one commit: pass the cleaned body to `pr_merge` (main stays clean, the
    branch does not need a rewrite);
  - several commits: the branch's messages must be rewritten first, which
    is history surgery ([history-repair](history-repair.md)).

## Stacks and chains

- **Native stack or chain?** A chain is pull requests whose bases point at
  each other; a native stack is what `github_pr` `view` shows as `stack`
  (null otherwise; merged members stay listed). Say "native stack" only after
  that check; never call a chain stacked.
- **A stack whose layers serve one goal lands once, on one card, when it is
  done.** Wait until every layer is green, then `pr_merge` on the top pull
  request: it lands every open layer below it too, and its card lists them.
  Landing layer by layer would leave a half-built goal on main for as long as
  the rest takes. The number of layers does not change this.
- **Its message names the goal and every layer.** A merge-commit merge of
  several layers makes ONE commit on main, and every one of their pull
  requests records it; without a `subject` it carries the top pull request's
  title alone, and the lower layers vanish from main's first-parent line.
  So: a merge commit, `subject` = the goal in the style of a pull request
  title + ` (#<top>)`, `body` = one line per layer, bottom-up,
  `- #<n> <title>`. Every layer's commits stay in the history under it,
  whatever their counts. Its commits land as they are, so the text scan
  covers each layer's messages as for several commits above.
- **Squash on a stack** makes one commit per layer, each with that layer's
  default message; a `subject` renames only the top layer's commit. Only when
  the user asks for it; a repository that allows no merge commit is stopped
  and told, as above.
- **When the user lands it by hand** on GitHub's page, give the title and
  body to paste: the page's title field starts as the top title with
  ` (#<top>)` and lands exactly as edited, so keep the number at its end.
- **A lower part first** only when the user asks (another job needs that
  base now): `pr_merge` on the highest layer to land, with the one-PR rules
  above for one layer and the stack message for several. GitHub rebases the
  layers above onto main itself: read the next one with `github_pr` `view`
  (its base is now the trunk, its commits are only its own, its additions
  match the original) and wait for its CI before its card.
- **After each merge-commit merge, check where it forked**, in a fetched
  clone: for the new main commit C, `git rev-parse C^1` must equal
  `git merge-base C^1 C^2`, and C^2 is the top layer's head. After a stack's
  last landing, run the same check over
  `git rev-list --merges <stack base>..origin/main`, look at `git log --graph`
  (each side branch hangs off the previous merge, not an older branch tip),
  and `git diff --stat <old top sha> origin/main` must be empty. Never report
  "all merged, matches" from equal trees alone: the tree is the same even when
  the history has the wrong shape.
- **A layer that still carries merged commits, or a `Merge branch 'main'
  into …` commit, is broken, not normal.** Its fix is a rebase onto main with
  a lease (the user's go, a build run, or the stack's own rebase in GitHub's
  page); never explain it away, and never say who made the merge commit (the
  record cannot tell). For future updates recommend "Update with rebase" (the
  arrow beside Update branch). A clean diff after such an update does not mean
  a clean commit list: read the commit count too.
- **Blocked by rules:** when GitHub says `blocked`, read `github_repo`
  `rules` to name what blocks it (a required check that cannot run, a
  review). Bypassing it is the user's own act in GitHub's page: say plainly
  that no CI would run on the merged commit.
- **Building layered work:** the build run creates the stack from the start,
  or links an existing chain without touching branches (brief it with
  [history-repair](history-repair.md) "Linking a chain"). Check `stack` on
  the newest PR after each layer is reported, not only at the end.

## BEHIND is not a conflict

- GitHub never rewrites a chained (non-native) PR's commits: it only
  retargets the base when the lower PR merges. After lower PRs were
  squash-merged, the next one shows `behind` with `mergeable`: its branch
  still carries the originals while main has their squashed copies.
  Confirm in a clone with `git merge-tree --write-tree origin/main
  origin/<branch>` (a bare tree hash, no conflict lines) and report "behind,
  no conflict". The fix is a rebase of the chain, not conflict resolution.
- When handing over a chain for the user to merge by hand, say the rule in
  the same message: bottom-up with "Create a merge commit", or merge one and
  ask for a rebase of the rest before the next.
- When the user reports a conflict after merging by hand, read the real state
  first (`github_pr` `list` with state `all`, `git log origin/main`): it
  may already be resolved and merged.
- Two kinds of merge commit exist; do not conflate them. The one a PR merge
  makes follows the repository's merge-commit settings (the PR title for a
  plain merge). The one "Update branch" or a stack sync makes always reads
  `Merge branch 'main' into <branch>`; no setting touches it. A squash
  leaves neither. Show a real pair from `git log --graph --format='%h %p | %s'`
  rather than explaining in the abstract, and only when asked.
- If the user doubts a squash happened, show evidence: the merge commit has
  one parent (`git rev-list --parents -n1 <sha>`), the original is not an
  ancestor of main (`git merge-base --is-ancestor`), and their content diff
  is empty.

## A wrong squash message: find the surface first

Some merge screens (the mobile app's stack merge among them) build their own
title and body and ignore the repository's settings. Ask or look at which
surface made the message before changing any setting, and do not say a
setting fixed it until the user confirms on that surface. The fix that works
everywhere: merge with `pr_merge` and an explicit `subject` and `body`.

## After the merges

When the user asks to tidy up branches, do it in one pass in the local clone,
listing before deleting: `git fetch --prune origin`, then `git branch -r`
(expect only `origin/main`), `git branch`, `git worktree list`; check
`git status --porcelain` and the stash; then reset the clone to
`origin/main`, remove the worktrees of merged branches, `git worktree prune`,
and delete the rest with `git branch -D` (squash history leaves
`--merged` empty; the remote holding only main is the evidence nothing is
lost). Finish by showing the branches and worktrees left. Worktrees an
OpenCode workspace made are removed through that workspace, not by hand.
