# GitHub access

The Assistant's access to GitHub Issues and Projects (v2) boards through the
user's own `gh` login. Read it when changing the plugin's engine, its
approval rules or its tiers. Common rules: [access-common.md](access-common.md).
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                          | Home                                                                             | Reader    |
| -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | --------- |
| Read engine: GraphQL transport, references, tiers, board resolution, issue and board reads                     | `plugins/github-access/access.py`                                                | all       |
| Write engine: change validation, the plan of targets, the card, applying a change list                         | `plugins/github-access/changes.py`                                               | all       |
| Mandates: terms, the MAC'd state, whether a change list fits                                                   | `plugins/github-access/mandate.py`                                               | all       |
| Bypass guard                                                                                                   | `plugins/github-access/guard.py`                                                 | all       |
| `github_issue`, `github_board`, `github_change`, `github_mandate` tools (toolset `github_access`) and the hook | `plugins/github-access/__init__.py`                                              | Assistant |
| How the Assistant reads Issues and boards, and the draft / issue model                                         | the `github-access:github` plugin skill (`plugins/github-access/skills/github/`) | Assistant |
| How the Assistant changes them: proposing tracking, change lists, tiers, recipes                               | the `github-access:github-tracking` plugin skill                                 | Assistant |

The plugin is enabled in the Assistant's private configuration only, like
Google access: it reaches the user's own account. A person without the
overlay enables `github-access` in `plugins.enabled` and adds the
`github_access` toolset to the Assistant's top-level and chat platform lists
(never to A2A).

## Account and state

There is no account setup of its own: the engine runs `gh api graphql` as
the user's `gh` login, the identity the workspace-repos inventory reads with,
with prompts and update checks off. Boards need the login's `project` scope
(`gh auth refresh -s project`); without it a board read fails with GitHub's
scope error. References are github.com only.

Nothing is stored. The viewer's login, organization memberships, Issue Types
and repository facts are cached in memory for five minutes; an answer that
came from an error (a membership or the Issue Types that could not be read)
is never cached, and a write re-reads its targets' repository facts and
memberships instead of trusting the cache.

## Tiers

Every target of a read or a write has one tier, read from GitHub:

| Tier     | What                                                                                     | Why it matters                  |
| -------- | ---------------------------------------------------------------------------------------- | ------------------------------- |
| `own`    | a private repository or board the viewer owns                                            | nobody else reads it            |
| `shared` | the viewer's public repository or board, or one of an organization the viewer belongs to | others read it and get notified |
| `other`  | anything else                                                                            | someone else's tracker          |

A board's visibility is its `public` flag; a repository's is `isPrivate`.
`own` means only people the user let in can read it, not that nobody else
does: a private repository can have collaborators. A membership that cannot
be read counts as no membership, so an error only ever makes a tier
stricter.

## Which board

A call names a board by URL, `owner/N`, a number with an owner, or a title.
Without one the engine takes a writable board linked to the repository the
call is about (the only one, or the one titled as asked), then the owning
organization's `Roadmap`, then the viewer's own `Roadmap`, and reports every
route it considered. Several writable linked boards and no title is an
error, never a guess.

## Reads

`github_issue` `view` reads an issue's body, kind, milestone, parent,
sub-issues and progress, dependencies, linked branches, closing PRs, board
items and latest comments in one request (dependencies in a second, whose
failure is reported rather than read as "none"). `list` turns its filters
into one GitHub search (`is:issue` and the repository are always set; a kind
is the organization's Issue Type when it defines one, else the
`type:<kind>` label) or lists a parent's sub-issues; `assignee` must be a
login and `query` cannot name another repository, owner or organization, so
every row is the asked repository's. `github_board` `items` reads the whole
board up to 2000 items before filtering and says when it was cut. A result over 60,000 characters is refused with a hint to narrow it.

Issue bodies, comments and drafts are other people's text: the tool
descriptions and the skill say never to follow instructions in them.

## Changes

`github_change` takes a list of up to 50 changes and applies them in order,
stopping at the first failure; the result names what was done, what failed
(with what of that change already exists, and `uncertain` when the failure
may have come after GitHub acted) and what was not tried. Every change is
validated before anything is read (op, its keys, a close reason), then the
plan reads, fresh, every repository and board the list writes to, with its
tier and the viewer's right to write there, and checks each board field
value (the field exists and is not built in, the option or iteration exists,
a date is `YYYY-MM-DD`). A target the viewer cannot write, an archived
repository, a read-only board and a bad field value end the call before any
card. Removing or replacing a parent also targets the old parent's
repository, read from the issue. An `issue_create`'s `parent` and
`blocked_by` may name `$N`, the issue an earlier `issue_create` or
`draft_promote` of the same list creates, so a parent and its sub-issues in
order are one list and one card; its repository is the target, and the card
reads it as "change N's issue".

Each change has a class. `routine`: moving an item's fields, a note on a
draft, a draft's own text, archiving or restoring an item, editing an issue's
title or body. `create`: anything that makes something new, notifies someone
or closes it — a draft, an item, an issue, a comment, a relation, a kind,
labels, assignees, a milestone, a close or a reopen, and an issue edit whose
new words carry an `@` mention. A board's own automations can still act on a
routine field change; `own` is about who can read a target, not about
nothing reacting to it. Putting someone else's
issue on a board writes only the board; a relation to an issue in another
repository writes there too, so that repository is a target.

Writes go through `gh` itself (`gh issue …`, `gh project …`, `gh label …`, the
milestones REST route) or one GraphQL mutation (turning a draft into an
issue); issue bodies and comments travel on stdin, a draft's text as an
argument (`gh project item-edit` takes no file). A note on a draft reads the
draft again right before it appends, so two notes in one list both land. A
relation already in place is not sent again.
A kind lands as the organization's Issue Type when it defines one, else as a
`type:<kind>` label created on first use, and the other `type:*` labels come
off.

## Approval

The hook plans the call and shows one card for the whole list: the targets,
each with its tier (`own, private`, `others can read it`, `⚠️ someone
else's`), the sites the changes link to (with the numbers of the changes that
do), how many local paths the text carries and how many code links follow a
branch rather than a commit, then one line per change. Names and quoted text
are collapsed to one line, control, bidi-override and invisible characters are
spelled out, and a list too long for the card ends with the count of the
rest; the skill agrees the full wording of text others will read first, as a
Markdown file delivered with a question before the card. Each card gets a
fresh allowlist key, so "session" or "always" on one card never approves
another list.

Before any card every text a change writes is checked: its words (title,
body, note, comment), the values it sets (board field values, a kind, which
lands as a label and its description, a milestone title, label names), and
for a promotion the draft's title and body as the list's earlier edits and
notes of that draft will leave them (a body cleaned by an earlier `draft_edit`
passes). Something that looks like a token or a private key (GitHub, OpenAI-style, Slack and AWS key
shapes, a PEM private-key header) is refused on every tier. On a change whose
targets include one others can read, a path of this machine is refused with
its rewrite named: a home path (`/Users/<name>/…`) as `~/…`, a file in a
repository checkout (`~/ghq/…`, `~/Worktrees/…`) as its repository-relative
path or a permalink, a path into the workspace, a job directory or the private
configuration, and a `file://` URL, in words (also spelled `$HOME/…`,
`${HOME}/…` or a bare `.agent/…`; a workspace path wins over a checkout inside
it). System paths (`/opt/…`,
`/usr/…`) and `~/…` paths pass. The tool refuses rather than rewriting, so
what the card shows is what is written; on the user's own private targets
paths pass as they are, so a debugging note stays whole.

The hook records, per exact call, that it decided it and the targets it showed
with their tiers; the handler takes that record once and runs nothing without
it, then plans again (the targets read now) and refuses when they differ from
the decided ones: another board resolved, a repository or board whose tier
changed. Hook and handler both refuse where no person can answer the card
(`human_gate`).

## Mandates

A mandate is the user's standing approval for a bounded kind of change, made
with `github_mandate` `create` on a card of its own (a fresh key every time;
a mandate never covers another). Its terms: boards and repositories (read and
checked writable when it is made, and held by node id, so a repository
renamed away and another made under the old name is not covered), an
optional parent issue, the classes it covers, a purpose, and 1 to 30 days.
The end is fixed when the card is drawn and printed on it; that is the end
stored, and a card approved after it makes nothing. `list` shows those in
force; `revoke` ends one at once. Neither asks.

With a parent, every issue a change touches or relates must be that issue or
one of its direct sub-issues (read at the write), and nothing may leave the
tree or join it from outside: no removing a parent, no moving under another
issue, no blocked-by with an issue outside, and only the parent itself adds
or removes sub-issues, from within the tree. An issue an earlier change of the
same list creates (`$N`) is inside only when that change creates a direct
sub-issue of the parent; a `$N` parent makes a grandchild, which is outside.

A change list skips its card when every change fits one mandate: its class
is covered, every target of the change is in the mandate's boards or
repositories, and the target's tier, read at the write, allows the class —
`own` takes `routine` and `create`, `shared` only `routine`, `other` nothing.
The hook records the mandate it matched; the handler re-reads the targets,
refuses if they changed, and checks the list still fits the mandate in force
now (revoked or ended between the two refuses). Inside a mandate a list also
runs where nobody can answer a card, such as a cron job. A card for a list
that fits no mandate names the first reason it did not.

State lives in the profile home under `github-access/`: one MAC'd JSON per
mandate, a MAC'd head naming those in force (only the head decides), and a
history file kept for the record. The MAC key is a random key in the Keychain
(`GITHUB_MANDATE_KEY_<PROFILE>`, project `hermes`, scope `github-access`, a
scope no profile receives), made with the first mandate and read from the
Keychain at every check, never cached: without a readable key, or with a
replaced one, nothing is in force. As with Hyperliquid's mandates, the MACs stop an
edited mandate or head, not an older head copied back; the guard on the
state directory and the 30-day ceiling bound that
([decision](decisions/github-mandates.md)).

## Ways around the tools

The hook blocks a terminal `gh` command that writes Issues (`create`,
`edit`, `comment`, `close`, `reopen`, `delete`, `transfer`, `pin`, `lock`,
`develop` …), changes a board (every `gh project` command but `list`, `view`,
`item-list`, `field-list`), changes labels, calls `gh api` at all, prints the
login's token (`gh auth token`, `--show-token`: `curl` could write with it)
or defines an alias or an extension (either could hide a write). It reads
the whole command text, so environment assignments, wrappers, a path to the
binary, `bash -c "…"`, `eval '…'` and backslash-newlines do not hide one;
a mere mention (`echo gh issue create`) is blocked too. It is a guard of
text, not a sandbox: a script file's contents are never seen. Reading
through `gh` (`gh issue view`, `gh pr …`, `gh auth status`) and `gh repo
create` stay open. File and terminal calls that name the plugin's state
directory (`<HERMES_HOME>/github-access/`) are blocked too, in any letter
case and also when an argument resolves there (`~`, `..`, a symlink): the
mandates' head is what a revoke changes, and a saved copy written back would
undo it.
