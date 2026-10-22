# Text that outsiders read

Commit messages on main, PR titles and bodies (open and merged) are what
someone with only the repository reads first. This applies whenever such text
is written or lands: a merge's `subject` and `body`, a `pr_edit`, a
`pr_create`, a build run's brief for its own commits.

## What must not be in it

A subject or body must read on its own to someone who never saw the plan: no
decision or ticket numbers, plan or phase codes, design-doc section marks,
"the reviewer said", names of the user, the Assistant or reviewers, local
paths, facts about this machine.

- **Before a merge,** scan every message that will land
  (`git log --format=%B <base>..<head>`); how a dirty one is fixed depends on
  the method ([merge](merge.md)). After a run, grep every message that landed
  on main since the base: zero.
- **PR text:** fix titles and bodies with `pr_edit` (merged ones are
  editable), keeping the original text in the job directory so the rewrite
  can be diffed.
- **Before saying "clean",** scan all four places (commit messages on main,
  PR titles and bodies, file contents, branch messages) with one shared
  pattern file that includes reviewer tags such as P1 to P3. Vendored tooling
  directories and licence attributions are not noise: list them as out of
  scope up front.

## Rewriting prose has two failure modes

- Removing an id leaves a hole (`until )`, an empty `()`, a double space):
  replace it with words.
- A rule for stray brackets also strips real code mentions such as `fn()`:
  count each protected token before and after, per document, and start again
  from the saved original when they differ.

Wording already on main, and file contents, are repaired by a build run:
[history-repair](history-repair.md) "Wording that already landed on main".
