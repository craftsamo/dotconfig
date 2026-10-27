# GitHub changes without a card only inside a mandate

Status: in force
Owner doc: docs/github-access.md "Mandates"

## Decision

A `github_change` list runs without its approval card only when every change
fits one mandate the user approved on a card of its own: named boards and
repositories (optionally one parent issue whose direct sub-issues alone it
covers), the classes of change it covers (`routine`, `create`), a purpose,
and an end at most 30 days out. Whatever a mandate says, each target's tier is
read at the write: a target someone else owns is never covered, and one others
can read (`shared`) takes routine changes only. An `admin` change (a
repository's settings or visibility, a merge, a published release, a workflow
run) is never covered, on any tier. A mandate is never made by another
mandate, and revoking one ends it at once.

The same mandate covers an OpenCode build's writes to its own issue (its
body, its board Status; `docs/opencode.md` "A build's own writes"): the
run's permission request is turned into the `github_change` it amounts to
and checked against the mandate at the write, exactly as the Assistant's own
list would be. A build never writes another issue, closes, comments or
creates under it, and the Assistant cannot approve a run's GitHub write in
the mandate's place.

## Why

- A tracked engineering job ticks a step or moves a Status many times a day;
  a card for each trains the user to approve without reading.
- A card's "session" or "always" covers only an identical request, so it
  cannot express "routine updates on this board"; a mandate states that bound
  on its own card.
- Tiers bound the harm an injected instruction could do under a mandate to the
  user's own private tracker (and to field moves and notes where others read),
  and they are read from GitHub at each write, so a repository made public or
  a membership lost tightens at once.
- An admin change acts on others at once and cannot be taken back by the next
  change (a merge lands on the default branch, a public repository is seen, a
  run deploys), so each one is read on its own card, however often it recurs.

## Do not

- Let a mandate cover a target someone else owns, `create` changes on a
  shared one, an `admin` change anywhere, or an upload (a file a change
  attaches is permanent and public on a public repository), whatever its
  terms.
- Decide what is in force from the history file: only the MAC'd head does.
- Keep the MAC key anywhere a profile receives (it lives under the Keychain
  scope `github-access`), or open the state directory to file or terminal
  calls.
- Remove the 30-day ceiling: a forgotten mandate should lapse on its own.
