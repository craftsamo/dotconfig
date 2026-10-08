# Assistant

Front-door Client: quality gate, visual design, creative early delivery, entry routing, tiers and pinned topics. Part of the Hermes design docs — index: [`PROFILES.md`](../../PROFILES.md).

## Assistant quality gate

For non-creative work, the assistant is the quality gate. Every specialist deliverable — a resident
session reply — is a candidate until the assistant
verified the actual artifact per the contracts under
`profiles/assistant/skills/assistant-pipeline/qa-assistant-*/` and common QA
(`references/quality-assurance/index.md`; Writing QA uses Writer's public
acceptance contract — see [writer.md](./writer.md) "Writer craft and independent
editorial QA"): vision on images/frames, ffprobe on av
media, read the prose, spot-check sources; `delegate_task` fans out
per-artifact checks on large sets. Defects go back to the same resident
session as itemized feedback — a minutes-scale loop.
Delivery happens only after verification; the session is closed on
acceptance. External factual claims still ride researcher evidence supplied
in the flow.

## Visual design

Assistant is the hands' only client and commissions them itself
([broker.md](../broker.md)); it adds no aesthetic gate. For
newly authored video it passes intent and acceptance — purpose, audience,
destination, fixed words, brand rules, exclusions, inputs, references and what
each is for — and the producer designs the storyboard, which Assistant relays
for the user's approval. When the look is open, Creator proposes named
directions that travel in the form's fields and `note`, never a design
([creator.md](./creator.md)). Static UI images use the Plan entry's
`plan-assistant-creative/references/ui-design.md` component design without an
invented video duration. The hands keep their own proposal and preview
approvals.

## Creative early delivery candidate

Normal creative production is Plan -> Execute -> delivery. The
Assistant does not run a routine perceptual acceptance stage, repeat measurements,
invoke learned verification for a second gate or autonomously polish a candidate
before showing it; do not restore routine broker inspection through learned
skills or delivery references, and does not consult Creator as a reviewer of
a finished candidate. The producer keeps its self-checks; the Assistant reads report
completeness, obvious settled-constraint conflicts and spend, then forward
artifacts and limitations. Required failures still block final readiness and
dependent use, but a viewable preview can be shown with those failures
disclosed. Delivery is not acceptance, and an early preview establishes neither
final readiness nor approval.

`qa-assistant-creative` remains the explicit user-requested inspection
entry, not an automatic completion step. It returns one scoped findings pass,
not an automatic repair grant or a chain of reviews. Existing entry
topology, hands forms, producer scripts, failed/unknown disclosure,
proposal/preview hashes and approvals, upload and remote-analysis consent,
budgets and non-creative QA remain unchanged.

Use an early supported representative sample for unresolved direction. With a
moving reference, demonstrate composition and progression, not just an ending
or static frame. Rejection of the idea returns to interpretation rather than
minor polish. Samples retain their existing approval and spending rules.

Status: paired public/private candidate, not a live cutover; paired candidate
verification does not authorize it. Timing and creative quality require fresh
real work after explicit rollout approval (see [topology](../topology.md)
"Candidate rollout and cutover").

## Assistant entry routing

The `assistant-pipeline` root is tracked in this repository like every other
pipeline. Names of private accounts, businesses and people stay on the private
technic shelf, which the entries reach by skill name only. The root owns
invariant lifecycle, grants and delivery policy. Its
19 independent child skills are `chat-assistant` plus
`{plan,execute,qa}-assistant-<domain>` for engineering, creative, writing,
research, search and marketing. Each child root `SKILL.md` owns its former
mode/domain index; each child's `references/` holds details and creative legacy.
No entry lives below the parent's `references/`. The shared parent files are
only `references/plan/index.md`, `references/execute/{index,resident-sessions}.md`
and `references/quality-assurance/index.md`; Chat's common procedure is its
entry body. No aliases, generated index, new overlay/symlink install mapping or
default `skills.external_dirs` expansion. Writer's acceptance rubric remains in
its own pipeline, not copied into the Assistant's QA entries.

Loading follows the shared [entry loading contract](../topology.md#entry-loading-contract):
each entry requires the invariant kernel and its mode-common procedure before
applying relevant details. An approval-only reply follows existing job state
and scope; it never restarts planning or widens a grant. Default's CLI adapter
reads the same tree through the filesystem (see [topology](../topology.md)
"Default is the assistant's CLI counterpart").

Status: deployed; existing messaging histories are not proven refreshed.

### Routing and tiers

Telegram auto-loads the root skill through its chat-wide
`channel_skill_bindings` entry (root DM plus fixed and user-created topics).
Discord binds the allowlisted guild channel explicitly; auto-created threads
inherit that parent binding and channel prompt. Discord DM bindings require the
literal DM channel ID and cannot use a user-ID wildcard: the first authorized DM
is bootstrap-only, then its channel ID is added to both `channel_skill_bindings`
and `channel_prompts`, the gateway is restarted, and `/new` starts the first
working session. The gateway injects the skill body into the session's first
turn; `compression.protect_first_n` protects initial context but does not prove
all required bodies remain present. After an approved restart, `/new` starts a
session on the refreshed index.

Every working request flows Classify → Locate → Mode (Chat / Plan / Execute /
Quality Assurance) → Deliver. Questions are risk/ambiguity driven: a settled
request does not pay an interview tax. Tier selection is by context dependence,
not size: `inline` for conversation/quick local work, a **resident session** for
anything the user will give feedback on (the default for heavy work, started
through `specialist_call(kind="work")`). Fire-and-forget or time-deferred
work is a cron job. Plan mode
ends in one conversational approval that sanctions the grants; Execute
supervises the sessions turn by turn, sizing each resident turn to one
verifiable increment and continuing in the same conversation; QA verifies actual
artifacts before delivery.

The org stays **flat by design**: profiles are global, resident sessions are
owned by their originating Client, and
specialists never register work of their own; follow-up work they propose returns in their
reply or completion summary, and the assistant decides. Grants never propagate
between specialists. `delegate_task` covers medium parallel
lookups the user is actively waiting on, and absorbs per-artifact QA checks on
large sets. Keep routing in sync with each `profile.yaml` description.

The user's own Google Sheets, Gmail and Drive and the `gcloud` CLI are inline
tools of the assistant alone (`google_access` toolset); every change waits for
the user's `/approve`, and the terminal path around them is blocked. Contract:
[google-access.md](../google-access.md).

The user's own WhatsApp accounts are likewise the assistant's alone
(`whatsapp_access` toolset, never on A2A): reads come from a local mirror,
and every send waits for approval on a card naming the account, the chat and
the text. The plugin skill `whatsapp-access:whatsapp` holds the mechanics. Contract:
[whatsapp-access.md](../whatsapp-access.md).

The user's own Signal account is the assistant's alone in the same way
(`signal_access` toolset, never on A2A): reads come from a local mirror
that keeps disappearing messages (marked expired) and drops messages
deleted for everyone, and every send — text and `~/Workspaces` files —
waits for approval on a card naming the chat, every file and the text. The
plugin skill `signal-access:signal` holds the mechanics. Contract:
[signal-access.md](../signal-access.md).

The user's own Discord account (not the Assistant's Discord bot) is the
assistant's alone too (`discord_access` toolset, never on A2A): DMs and the
servers on its sync list come from a local mirror, other channels are read
live through an engine that alone holds the token, the sync list is edited by
request within code-enforced limits, and every write — sends of text and
`~/Workspaces` files, reactions, edits and deletions of the user's own
messages, role management checked against the user's permissions — waits for
approval on a card naming exactly what it does. Contract:
[discord-access.md](../discord-access.md).

The user's own Telegram account (not the Assistant's Telegram bot, whose
chats it never shows) is the assistant's alone too (`telegram_access`
toolset, never on A2A): private chats, bots, basic groups and the supergroups
and channels on its sync list come from a local mirror that keeps
disappearing messages (marked expired, files included) and drops messages
deleted for everyone, other chats are read live through a sync agent that
alone holds the session, and every send — text and `~/Workspaces` files —
waits for approval on a card naming the chat, every file and the text. The
plugin skill `telegram-access:telegram-account` holds the mechanics. Contract:
[telegram-access.md](../telegram-access.md).

X is read-only (`x_access` toolset, never on the assistant's A2A): it reads
as a separate sub-account through twscrape, paced and capped, downloads a
post's media, records the main account's public counts and checks public
posts in bulk through FxTwitter outside those caps (`verify`); nothing posts
or sends. Marketer shares the tool and its caps for analysis. The browser
stays off x.com, which carries the user's main login, with two exceptions,
both at the user's request and both stopping at a saved draft, never
publishing or scheduling: the Assistant saves an approved ordinary post
draft, and completes an X Article draft in the editor. The plugin skills
`x-access:x-twitter` (reading) and `x-access:x-twitter-drafts` (the two browser
tasks) hold the mechanics. Contract:
[x-access.md](../x-access.md).

note.com is the assistant's to write too (`note_access` toolset, never on
the assistant's A2A; Marketer has its reads and `check`, Writer only the
offline format `check`): public articles, creators, comments and
hashtags plus the user's own drafts and stats are read as the user's main
account, and unpublished drafts are created or wholly replaced from Markdown
with local images, each save waiting for approval on a card naming the
draft, the title, every new image and the start of the text; nothing
publishes. The plugin skills `note-access:note-com`, `note-com-format` and
`note-com-drafts` hold the mechanics; the browser
stays off note.
Contract: [note-access.md](../note-access.md).

The user's own Substack account is shared with Marketer, which only reads
(`substack_access` toolset; the Assistant's never on A2A): any publication's
posts, the inbox and the user's drafts, published posts and stats, and on the
Assistant's side drafts with `~/Workspaces` images, publishing, scheduling and
Notes, each waiting for approval on a card naming the publication, the draft,
whether email goes out and the text; nothing is written where nobody can
approve. Contract: [substack-access.md](../substack-access.md).

The user's YouTube channels are shared with Marketer, which only reads
(`youtube_access` toolset; the Assistant's never on A2A): search, videos,
channels, playlists and comments, each authorized channel's own uploads and
analytics, and transcripts and downloads of public videos into
`~/Workspaces/.inbox/youtube`; on the Assistant's side video edits and
settings, thumbnails, comment replies and moderation, uploads (kept private
by YouTube), captions, playlists and the channel's settings and watermark,
each waiting for approval on a card naming the channel and the change.
Settings outside the API (name, handle, picture, banner, links, upload
defaults) go through YouTube Studio in its browser after a `clarify`
confirmation. Contract: [youtube-access.md](../youtube-access.md).

EVM chains and Solana are read through `evm` and `solana` (`evm_access` and
`solana_access` toolsets), shared with Researcher, Searcher and Marketer:
transactions, blocks, addresses, tokens, approvals, balances, gas and prices,
contracts and programs (who controls them, what they can do, test calls),
decoded, with on-chain text marked untrusted. The Assistant's tools alone
carry the wallet actions (never on A2A): the seed phrases and private keys in
the user's Keychain, sending only from those named with `HERMES`; a transfer
to one of them runs, any other waits for approval on a card naming both
sides, and none goes out where nobody can approve. A new Hermes wallet is
made the same way: its seed phrase generated and stored, never shown, after
a card of all its Keychain metadata. Contract:
[web3.md](../web3.md).

Marketing work is the Assistant's to execute, with Marketer as its strategy
advisor ([marketer.md](./marketer.md)): the marketing entries consult Marketer
on direction, reviews and results, release Writer and hands units, accept
them with the shared writing contract and save the approved service-side
draft themselves after exact remote-save consent — X posts and Articles in
the Assistant's browser (`x-access:x-twitter-drafts`), Substack and note through their tools
and cards, Zenn personal Articles in the browser (public technic `zenn-dev`).
Nothing publishes, schedules or sends; the user publishes. Marketer's browser
is never a fallback.

### Pinned Telegram topics

The assistant's `platforms.telegram.extra.dm_topics` (private `config.yaml`)
declares exactly two pinned topics, both skill-less Assistant surfaces rather
than worker threads — the chat-wide `assistant-pipeline` binding is the only
skill surface, and a per-topic skill layer only duplicated that routing. Each
topic's contract lives entirely in its `channel_prompts['<thread_id>']` entry
(template in `config.example.yaml`). The validator
(`validate_assistant_dm_topics`) rejects any topic carrying a `skill:` key and
any `dm_topics` list without a topic literally named `Inbox`, so the retired
desk layer (Personal / Projects / Brainstorm and their skills and `desks/`
overlay link) cannot creep back.

- **Inbox** receives system cron output and starts no work. Jobs keep bare
  `deliver: telegram`; `scripts/profile-secrets.sh` derives
  `TELEGRAM_CRON_THREAD_ID` from the topic literally named `Inbox`, so renaming
  it makes every such job fail closed. Maintenance and report cron output
  targets Inbox.
- **Admin** is the inline surface for small administrative work: workspace
  bookkeeping (`workspace_registry` records and new Groups, `hb` records,
  docs/data touch-ups), edits to the `~/.config` dotconfig repo and its Hermes profiles,
  and Hermes upkeep (browser relaunch, cron / validator checks, skill
  housekeeping). No resident session or delegation. It is not the only
  OpenCode topic: code work happens in any topic per the engineering entries
  (see [opencode.md](../opencode.md)).

Both fix the tier to `inline`; work that needs a specialist hands off to a new
ad-hoc topic, which inherits chat-wide `assistant-pipeline` and owns the
sessions. A new pinned topic is a `dm_topics` entry WITHOUT `thread_id`: the next
gateway start creates the forum topic and writes the id back through the symlink
into the private `config.yaml`; only then can its `channel_prompts` entry be
keyed, followed by `/restart`. Hermes never deletes a Telegram topic: close retired ones by hand in the
client.
