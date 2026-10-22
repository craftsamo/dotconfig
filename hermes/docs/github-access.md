# GitHub access

The Assistant's access to GitHub Issues, Projects (v2) boards and
repositories through the user's own `gh` login. Read it when changing the
plugin's engine, its approval rules or its tiers. Common rules:
[access-common.md](access-common.md).
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                                                                                                              | Home                                                                                                                               | Reader    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- | --------- |
| Read engine: GraphQL transport, references, tiers, board resolution, issue and board reads                                                                         | `plugins/github-access/access.py`                                                                                                  | all       |
| Repository reads: settings, labels, milestones, releases, Actions workflows and runs, rulesets                                                                     | `access_repo.py` beside `access.py`                                                                                                | all       |
| Pull request reads: one in full with its checks and reviews, a repository's list                                                                                   | `access_pr.py` beside `access.py`                                                                                                  | all       |
| Write engine: the op registry, change validation, the plan of targets, the card, applying a change list                                                            | `plugins/github-access/changes.py`                                                                                                 | all       |
| The ops of a change list, one module per domain: boards and their items, issues, repositories, pull requests and attachments, releases, Actions, branch protection | `ops_board.py`, `ops_issue.py`, `ops_repo.py`, `ops_pr.py`, `ops_release.py`, `ops_actions.py`, `ops_rules.py` beside `changes.py` | all       |
| Mandates: terms, the MAC'd state, whether a change list fits                                                                                                       | `plugins/github-access/mandate.py`                                                                                                 | all       |
| Bypass guard                                                                                                                                                       | `plugins/github-access/guard.py`                                                                                                   | all       |
| `github_issue`, `github_board`, `github_repo`, `github_pr`, `github_change`, `github_mandate` tools (toolset `github_access`) and the hook                         | `plugins/github-access/__init__.py`                                                                                                | Assistant |
| How the Assistant reads Issues and boards, and the draft / issue model                                                                                             | the `github-access:github` plugin skill (`plugins/github-access/skills/github/`)                                                   | Assistant |
| How the Assistant changes them: proposing tracking, change lists, tiers, recipes                                                                                   | the `github-access:github-tracking` plugin skill                                                                                   | Assistant |
| How the Assistant reads and changes a repository, its labels, milestones, releases, Actions runs and branch protection                                             | the `github-access:github-repo` plugin skill                                                                                       | Assistant |
| How the Assistant reads, opens, edits, attaches files to and merges a pull request                                                                                 | the `github-access:github-pr` plugin skill                                                                                         | Assistant |

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
error, never a guess, and so is no board at all; that error names
`board_create` as the way to make one.

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
board up to 2000 items before filtering and says when it was cut.
`github_repo` `view` reads a repository's visibility, archived and template
flags, default branch, description, homepage, topics, license, features and
merge settings with the viewer's permission and the tier; `labels` and
`milestones` (open, closed or all, with due date and progress) list the
rest, `releases` the latest releases (drafts too, for a viewer who can push),
`workflows` and `runs` the Actions workflows and recent runs, `run` one
run's jobs and failed steps with the last 120 lines (at most 8,000
characters) of their log, terminal colors and control characters removed,
and `rules` every ruleset that reaches the repository (its branches, rules,
bypass and enforcement; an organization's marked by its source) and the
classic branch protection rules. `github_pr` `view` reads a pull request's
state, draft flag, base and head with the head commit, GitHub's mergeable and merge state, the review
decision, latest reviews and requests, the head commit's checks (failing and
pending ones named, required ones counted), the issues a merge closes and
the latest comments; `list` turns its filters into one search of one
repository. A result over 60,000 characters is refused with a hint to narrow
it.

Issue bodies, comments and drafts are other people's text: the tool
descriptions and the skill say never to follow instructions in them.

## Changes

`github_change` takes a list of up to 50 changes and applies them in order,
stopping at the first failure; the result names what was done, what failed
(with what of that change already exists, and `uncertain` when the failure
may have come after GitHub acted) and what was not tried. Each op is
registered by the module of its domain with its keys, its plan, its card
line and how it runs; the tool's schema and its list of ops are built from
that registry. Every change is validated before anything is read (op, its
keys and their types, a close reason), then the plan reads, fresh, every
repository and board the list writes to, with its tier and the viewer's right
to write there, and checks each board field value (the field exists and is
not built in, the option or iteration exists, a date is `YYYY-MM-DD`). A
target the viewer cannot write, an archived repository, a read-only board and
a bad field value end the call before any card. Removing or replacing a
parent also targets the old parent's repository, read from the issue. An
`issue_create`'s `parent` and
`blocked_by` may name `$N`, the issue an earlier `issue_create` or
`draft_promote` of the same list creates, so a parent and its sub-issues in
order are one list and one card; its repository is the target, and the card
reads it as "change N's issue".

Each change has a class. `routine`: moving an item's fields, a note on a
draft, a draft's own text, archiving or restoring an item, editing an issue's
title or body. `create`: anything that makes something new, notifies someone
or closes it — a draft, an item, an issue, a comment, a relation, a kind,
labels, assignees, a milestone, a close or a reopen, a board, its link to a
repository, a field, an option or a view, and an issue edit whose new words
carry an `@` mention. `admin`: what changes how a repository works
or reaches others at once (its settings or visibility, a merge, a published
release, a workflow run); it always asks on its card. A board's own
automations can still act on a routine field change; `own` is about who can
read a target, not about nothing reacting to it. Putting someone else's
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

### Setting up a board

`board_create` makes a board for the viewer or for an organization the viewer
belongs to (a new board is private: `own` for the viewer's, `shared` for an
organization's), or reuses the one open board of that title the owner
already has; two of that title is an error. Its target is the owner, by node
id, until the board exists, so no mandate covers making one. Either way the
board is brought to the standard shape: Status with Todo, In Progress, Done
and Cancelled, the Start and Target dates, and the Kanban, Backlog and
Roadmap views (`views: false` skips them); `template` copies another board
(its views and fields, never its drafts), shown on the card with its tier
and bound like a target though nothing is written there, and `link_repo`
links the repository, which is then a target too. A reused board whose
Status, Start or Target has another type is refused before the card, and a
failure part-way reports what the board already has. `field_ensure` makes a
field or appends the options it lacks, `view_ensure` makes a view the board has none
of by that name, and `board_link` links or unlinks the list's board and a
repository. A field name GitHub keeps for its own (`Labels`, `Milestone`, …)
is refused for a new field, as is a type that differs from an existing one's,
and a column a view names must exist on the board. When a view is made with
the standard shape, a column the board lacks is skipped and reported.

These go through GraphQL mutations with typed variables. Appending options
sends the existing ones with their ids, colors and descriptions, so no item's
value moves. A view's layout, filter and columns are all the API takes:
grouping, sort and a roadmap's date fields are set once in GitHub's own page.
A list resolves its board before anything runs, so changes on a board the
same list makes go in a later call.

### Repositories, labels and milestones

`repo_create`, `repo_edit`, `repo_visibility` and `repo_archive` are `admin`:
each asks on its card, whatever mandate is in force. `repo_create` makes a
repository for the viewer or an organization the viewer belongs to, private
unless `visibility` says otherwise (`internal` only for an organization);
its target is the new name under its owner's node id, tiered `own` only when
it is the viewer's and private, and a `template` must be a template
repository, shown as "Copied from" with its tier; a name that already exists
is refused. The others need admin on the repository and read its settings
before the card, which shows each setting moving from what it is to what it
becomes and leaves out what already holds. `repo_edit` keeps one merge method
allowed and takes only a `default_branch` that exists; topics are lowercase
letters, digits and hyphens. `repo_visibility` says what the new visibility
exposes or takes away, and `repo_archive` (or `unarchive`) refuses a repository
already in that state; an archived repository is otherwise refused as a
target of any change.

`label_create` and `label_edit` (a label that exists, by name in any case;
`new_name`, a six-hex-digit `color`, `description`) and `milestone_create`
and `milestone_edit` (by title; `new_title`, `due` as `YYYY-MM-DD` or `""` to
remove it, `description`, `state`) are `create` changes. Writes go through
`gh repo …` and `gh label …`, and milestones through their REST route with a
JSON body on stdin; a due date is sent as midday UTC, which reads as the same
date from UTC−11 to UTC+11. A list resolves its repositories before anything
runs, so labels and milestones of a repository the same list makes go in a
later call.

### Pull requests and attachments

`pr_create` opens a pull request from a branch that is already pushed (or
`owner:branch` of a fork, found among that owner's forks whatever its name)
onto a base that exists, by default the repository's default branch; an open pull request for the same head is
refused, and nothing is pushed. `pr_edit` changes a pull request's words,
base, labels, assignees, reviewers or milestone; it is `routine` only for its
own words without a mention, `create` otherwise. `pr_comment`, `pr_ready`
(`undo` back to draft), `pr_close` and `pr_reopen` are `create`, and each is
refused when the pull request is not in the state it changes. A pull request
is never inside a mandate's parent issue tree.

`pr_merge` is `admin`. The plan refuses a draft, a conflicting pull request
and a method the repository does not allow (it is required when the
repository allows more than one), and binds the head commit, the base and
the method as a target ("Merging"), so a push, a retargeted base or another
method after the card is a different change. Right before the merge the
pull request is read once more, so an earlier change of the same list that
retargets it, or a push since the plan, stops the merge; what remains is the
moment between that read and GitHub's merge, where `--match-head-commit`
pins the head and nothing pins the base. The merge never sends `--admin`, so
GitHub's own rules still decide, and the result reads the pull request back:
one a merge queue took is reported as not merged yet. The card names the issues the merge closes and warns of
failing or pending checks, a review decision that is not an approval, and a
merge state GitHub reports as blocked, behind, unstable or unknown. gh runs it
from a temporary directory, so `--delete-branch` never touches a local
checkout.

`pr_create`, `pr_edit` and `pr_comment` take `attachments`: absolute paths of
images (PNG, JPEG, GIF, WebP, SVG, up to 10 MiB) and videos (MP4, MOV, WebM,
up to 100 MiB, no alt text) mapped to their alt text, at most 50, uploaded
by gh 2.99 or later through `--attach`. Each must be a regular file (read
without blocking, so a FIFO is refused rather than waited on) that starts
like its type, so a renamed text file is refused. An upload is permanent and
readable by everyone who can read the repository, by anyone at all on a
public one, so each file is a target of its own ("Upload", with its whole
path — and where a symlink points — and its size), bound by its SHA-256; no mandate
names one, so a change that attaches always asks. At the write each file is
read once more, compared with that hash, and copied into a private directory
under the same name, and gh uploads the copy: a path retargeted after the
card uploads nothing it points to now. A body may reference an attached file
by the path written in `attachments` (gh swaps the reference for the
uploaded URL), and only in a body does that path pass the local-path check
that refuses every other. When gh makes the pull request or comment but some
uploads fail, the result keeps its URL under `partial`.

### Releases and Actions

`release_create` always makes a draft (only people who can push see it, and
the tag is made when it is published); its `target` is for a tag that does
not exist yet and must name a branch or a full SHA. `release_edit` is
`routine` on a draft and `admin` on a published release, where `target` is
refused; the plan reads the release (among the latest 100, where drafts
show to a viewer who can push) and raises the change's class, and binds the
release's state and its tag's commit as a target ("Release"), so a draft
published or a tag moved after the card is a different change. Notes travel
on stdin. `release_publish` is `admin`: it turns a draft into a
release everyone who can read the repository sees, makes its tag, and tells
watchers.

`run_rerun` and `workflow_dispatch` are `admin`: a workflow can deploy,
publish or spend whatever its name says. `run_rerun` takes a finished run,
by default re-running only its failed jobs (refused when it has none), and
binds the run's attempt as a target ("Re-running"); a run URL of another
repository is refused. `workflow_dispatch` takes an active workflow by id or
path, or by a file name or name that names exactly one, a branch or tag (the
default branch unless named) and inputs; its file at that commit must name
`workflow_dispatch` outside a comment, the commit is bound as a target
("Starting"), so a push after the card is a different change (one between the
handler's read and GitHub's dispatch is not caught), and the inputs travel as
JSON on stdin (never `-F`, which reads a value starting with `@` as a file).

### Branch protection

`branch_rule` is `admin` and needs admin on the repository. It writes one
ruleset per branch, named `Managed protection: <branch>` (or `default
branch`), and never another: a ruleset someone made in GitHub's page or an
organization's is read with `rules`, never changed, and GitHub applies every
ruleset that reaches a branch together. A change names only what it moves —
`require_pr` with `approvals` (0 to 10), `required_checks`,
`block_force_push`, `block_deletion`, `linear_history`, `admin_bypass` (the
repository admin role bypasses) and `disable` — and the rest keeps what the
ruleset says now; a new one blocks force pushes and deletion and lets admins
bypass, so the user is not locked out of their own branch. Rule types the
ruleset holds besides these, the review settings it has, other bypass actors
and the admin entry's own mode (bypassing in pull requests only stays so)
are kept as they are. Check names are text others read and pass its checks.
One branch per rule (no patterns), and the branch must exist. The card
shows the whole rule for a new ruleset and what moves for an existing one,
whether it is enforced and who bypasses first and check names last; a
change that moves nothing, or leaves the ruleset no rule, is refused before
it. The ruleset's id and last update are
bound as a target ("Ruleset") and read again right before the write, so one
edited in GitHub's page after the card is not overwritten.

## Approval

The hook plans the call and shows one card for the whole list: the targets
(the owner of a board not made yet as "New board for", a template as
"Copied from"), each with its tier (`own, private`, `others can read it`,
`⚠️ someone else's`), the sites the changes link to (with the numbers of the
changes that do), how many local paths the text carries and how many code
links follow a branch rather than a commit, which changes are `admin`, then
one line per change (an `admin` one marked ⚠️). Names and quoted text are
collapsed to one line, control, bidi-override and invisible characters are
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
An `admin` change never fits, and no mandate can be made for that class.
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

The hook lets a terminal `gh` command run only when it is a read it knows:
`view`, `list` and `status` of issues and pull requests, a pull request's
`checks`, `diff` and `checkout`, a repository's `view`, `list`, `clone`,
`set-default`, `license` and `gitignore`, the board reads (`list`, `view`,
`item-list`, `field-list`), the listings of labels, releases, runs,
workflows, caches, secrets, variables, gists, organizations, rulesets and
keys, release and run downloads, `run watch`, `search`, `status`, `browse`,
`auth status`, `config get` and `list`, attestation checks, and help. Every
other one is blocked: a subcommand gh gains later, an extension run as `gh
<name>`, `auth login` or `refresh`, `config set`, codespaces and agent tasks
are not the Assistant's to run, with a message that says so. Within that,
the messages name what the command was: one that writes what
`github_change` offers (an issue, a board, a label, a repository, a pull
request, a release, a re-run or a started workflow), calls `gh api` at all,
prints the login's token (`gh auth token`, `auth status --show-token` or
`-t`: `curl` could write with it) or defines an alias or an extension (either
could hide a write) points at the tools.

It reads every simple command of the line and a path to the binary. An
environment assignment's value is read as a command too (a pager or an
editor gh starts); after a wrapper (`env`, `sudo -u x`, `timeout 10`,
`xargs -I {}`, …) every token that may be the command it runs is followed,
since its flags may or may not take a value, and after `find` what follows
each `-exec`. It follows `sh -c '…'` (any shell, any `-…c` flag, past its
options; else a here-string `<<<` the shell reads) and `eval '…'` into the
script they run. A line nested deeper, or with more readings, than it
follows is blocked rather than passed. Flags before a subcommand (`gh issue -R
a/b create`) count both ways: with a value and without, and the command
passes only when every reading is a read (`-R` and `--repo` always take a
value). The writes are also matched over the whole text, so backslash-newlines
do not hide one and a mere mention (`echo gh issue create`) is blocked too.
It is a guard of text, not a sandbox: a script file's contents, a script
piped into a shell, and a binary reached through a variable or
`$(which gh)` are never seen.

The same guard blocks, with a message saying the Assistant never does it, the
writes no tool offers: setting or deleting secrets and variables, writing
gists, deleting, renaming, forking or syncing a repository and its deploy keys
and autolinks, adding or deleting the account's SSH and GPG keys,
deleting releases, release assets, workflow runs and caches, uploading
release assets, cancelling runs, enabling or disabling workflows, and reviewing,
reverting, locking or updating a pull request's branch. They hold or reveal
credentials, publish outside a repository, destroy or move what others rely
on, or (a review) speak for the user's own judgement, so they stay with the
user.

File and terminal calls that name the plugin's state directory
(`<HERMES_HOME>/github-access/`) are blocked too, in any letter case and also
when an argument resolves there (`~`, `..`, a symlink): the mandates' head is
what a revoke changes, and a saved copy written back would undo it.
