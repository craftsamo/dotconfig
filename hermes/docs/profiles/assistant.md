# Assistant

Front-door Client: quality gate, visual design, creative early delivery, entry
routing, tiers and pinned topics. Read it before changing the Assistant's
entries, gate or topics. Part of the Hermes design docs — index:
[`PROFILES.md`](../../PROFILES.md).

## Assistant quality gate

For non-creative work, the assistant is the quality gate. Every specialist
deliverable (a resident session reply) is a candidate until the assistant has
verified the actual artifact per the `qa-<domain>` entries under
`profiles/assistant/skills/pipeline/` and common QA
(`references/quality-assurance/index.md`). Writing QA uses Writer's public
acceptance contract ([writer.md](./writer.md) "Writer craft and independent
editorial QA"), which is not copied into the Assistant's entries.

- Defects go back to the same resident session as itemized feedback; the
  session is closed on acceptance.
- Delivery happens only after verification.
- External factual claims still ride researcher evidence supplied in the flow.

## Visual design

Assistant is the hands' only client and commissions them itself
([broker.md](../broker.md)); it adds no aesthetic gate. For newly authored video
it passes intent and acceptance (purpose, audience, destination, fixed words,
brand rules, exclusions, inputs, references and what each is for); the producer
designs the storyboard, which Assistant relays for the user's approval. When the
look is open, Creator proposes named directions that travel in the form's fields
and `note`, never a design ([creator.md](./creator.md)). Static UI images use the
Plan entry's `plan-creative`'s `references/ui-design.md`. The hands keep
their own proposal and preview approvals.

## Creative early delivery candidate

Creative production is Plan -> Execute -> delivery, with no routine perceptual
acceptance stage:

- The Assistant does not repeat measurements, run learned verification as a
  second gate, polish a candidate before showing it, or consult Creator as a
  reviewer of a finished candidate. Do not restore routine broker inspection
  through learned skills or delivery references.
- It reads report completeness, obvious settled-constraint conflicts and spend,
  then forwards artifacts and limitations.
- Required failures still block final readiness and dependent use, but a
  viewable preview may be shown with them disclosed. Delivery is not acceptance;
  an early preview establishes neither final readiness nor approval.
- `qa-creative` is the explicit user-requested inspection entry, never
  an automatic completion step: one scoped findings pass, not a repair grant or a
  chain of reviews.
- Unresolved direction gets an early representative sample (for a moving
  reference, composition and progression, not a static frame); rejecting the
  idea returns to interpretation, not polish. Samples keep their approval and
  spending rules.

## Assistant entry routing

The `assistant-pipeline` root is tracked in this repository like every other
pipeline. Names of private accounts, businesses and people stay on the private
technic shelf, which the entries reach by skill name only. The root owns
lifecycle, grants and delivery policy; its 19 independent child skills are
`chat-assistant` (at `pipeline/chat/`) plus `{plan,execute,qa}-<domain>`
(at `pipeline/<domain>/{plan,execute,qa}/`) for engineering, creative,
writing, research, search and marketing. A domain directory only groups its
three entries; each child's `SKILL.md` owns its mode/domain index. No entry lives below the parent's `references/`, which
holds only `plan/index.md`, `execute/{index,resident-sessions}.md` and
`quality-assurance/index.md`. No aliases, generated index, new overlay/symlink
install mapping or default `skills.external_dirs` expansion.

Loading follows the shared [entry loading contract](../topology.md#entry-loading-contract);
an approval-only reply follows existing job state and scope and never restarts
planning or widens a grant. Default's CLI adapter reads the same tree (see
[topology](../topology.md) "Default is the assistant's CLI counterpart").

### Routing and tiers

- **Telegram** auto-loads the root skill through the chat-wide
  `channel_skill_bindings` entry (DM plus fixed and user-created topics).
  **Discord** binds the allowlisted guild channel; auto-created threads inherit
  it. A Discord DM binding needs the literal DM channel ID (no user-ID
  wildcard): the first authorized DM is bootstrap-only, then its channel ID goes
  into `channel_skill_bindings` and `channel_prompts`, the gateway restarts, and
  `/new` starts the first working session.
- The gateway injects the skill body into a session's first turn;
  `compression.protect_first_n` does not prove the bodies stay present.
- **A session's skill index is built once and kept** (the session row stores
  its system prompt, so a gateway restart restores it unchanged). After an
  approved restart, a running session learns renamed or added skills through
  `/reload-skills`: the next turn carries what was added and removed, and
  `skill_view` resolves by name, so the new names work while the index still
  lists the old ones. `/new` is for a conversation that should start over; it
  starts a session on the refreshed index but carries nothing of the previous
  session over.
- The flow (Classify → Locate → Mode → Deliver), the question policy and tier
  choice (`inline` / resident session / cron) are owned by the root `SKILL.md`
  and `references/execute/index.md`. The contract here: tier follows context
  dependence, not size; anything the user will give feedback on is a resident
  session started through `specialist_call(kind="work")`.
- The org is **flat by design**: profiles are global, resident sessions belong
  to their originating Client, and specialists never register work of their
  own: follow-up they propose returns in their reply and the assistant decides.
  Grants never propagate between specialists. Keep routing in sync with each
  `profile.yaml` description.

### Account and service tools

The write side of each account below is the Assistant's alone (never on A2A);
some tools are shared read-only with other profiles (the contract doc lists who
gets which action). Reads come from a local mirror or a live read, and a write
asks the user as its contract says (a card naming exactly what it does, with a
few contract-defined exceptions such as a transfer to the user's own address).
Nothing publishes, schedules or sends where nobody can approve. Mechanics live
in the plugin skills; the contract in the linked doc.

| Service                               | Toolset                       | Notes                                                                                                                     | Contract                                        |
| ------------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Google Sheets, Gmail, Drive, `gcloud` | `google_access`               | terminal path around it is blocked                                                                                        | [google-access.md](../google-access.md)         |
| WhatsApp                              | `whatsapp_access`             | local mirror                                                                                                              | [whatsapp-access.md](../whatsapp-access.md)     |
| Signal                                | `signal_access`               | mirror keeps expired messages, drops deleted-for-everyone                                                                 | [signal-access.md](../signal-access.md)         |
| Discord (user account, not the bot)   | `discord_access`              | one engine holds the token                                                                                                | [discord-access.md](../discord-access.md)       |
| Telegram (user account, not the bot)  | `telegram_access`             | a sync agent alone holds the session                                                                                      | [telegram-access.md](../telegram-access.md)     |
| X                                     | `x_access`                    | read-only; browser stays off x.com except two saved-draft tasks (`x-access:draft-post`, `x-access:draft-article`); Marketer shares the tool   | [x-access.md](../x-access.md)                   |
| note.com                              | `note_access`                 | drafts only, never publishes; browser stays off note                                                                      | [note-access.md](../note-access.md)             |
| Substack                              | `substack_access`             | Marketer reads only                                                                                                       | [substack-access.md](../substack-access.md)     |
| YouTube                               | `youtube_access`              | Marketer reads only; non-API settings via Studio after a `clarify`                                                        | [youtube-access.md](../youtube-access.md)       |
| EVM / Solana                          | `evm_access`, `solana_access` | reads shared with Researcher, Searcher, Marketer; wallet actions the Assistant's alone                                    | [web3.md](../web3.md)                           |
| Hyperliquid                           | `hyperliquid_access`          | reads shared with Researcher, Searcher, Marketer; trading the Assistant's alone, increases on a card                      | [hyperliquid.md](../hyperliquid.md)             |
| Stripe                                | `stripe_access`               | live or test per call; reads shared with Researcher, Marketer; every change on a card, refunds and invoices ask each time | [stripe-access.md](../stripe-access.md)         |
| Cloudflare                            | `cloudflare_access`           | reads shared with Researcher, Marketer; changes on a card; deletes, publishing and weakening ask each time                | [cloudflare-access.md](../cloudflare-access.md) |
| This Mac's audio (Discord app)        | `screen_listen`               | one allowed app's output: minutes transcribed, or a session kept as a file; no account, no API, no card                   | [screen-listen.md](../screen-listen.md)         |

Marketing work is the Assistant's to execute, with Marketer as its strategy
advisor ([marketer.md](./marketer.md)): the marketing entries consult Marketer on
direction, reviews and results, release Writer and hands units, accept them with
the shared writing contract and save the approved service-side draft themselves
after exact remote-save consent. Nothing publishes, schedules or sends; the user
publishes. Marketer's browser is never a fallback.

### Pinned Telegram topics

The assistant's `platforms.telegram.extra.dm_topics` (private `config.yaml`)
declares one pinned topic, Inbox, a skill-less Assistant surface rather than a
worker thread: the chat-wide `assistant-pipeline` binding is the only skill
surface. A pinned topic's contract lives entirely in its
`channel_prompts['<thread_id>']` entry (template in `config.example.yaml`). The
entry replaces the chat-wide prompt rather than adding to it, so it carries any
chat-wide rule the topic still needs. The validator
(`validate_assistant_dm_topics`) rejects any topic carrying a `skill:` key and
any `dm_topics` list without a topic literally named `Inbox`.

- **Inbox** receives system cron output and starts no work: its contract fixes
  the tier to `inline`, and work that needs action hands off to a new ad-hoc
  topic, which inherits the chat-wide binding and owns the sessions. Jobs keep
  bare `deliver: telegram`; `scripts/profile-secrets.sh` derives
  `TELEGRAM_CRON_THREAD_ID` from the topic literally named `Inbox`, so renaming
  it makes every such job fail closed.

Pin a topic only when Hermes must find it by name or it needs a contract of its
own. The bot creates every pinned topic, so the user cannot rename it in the
client, and Hermes never renames one either. Everyday topics (a General one,
reset often with `/new`) are created and pinned in the client instead: they run
on the chat-wide prompt with the same routing and tiers, and stay renamable
there. Hermes renames such a topic to its session's title only once `/topic`
has turned topic mode on for the chat. `/new` in any topic ends the old
session's hold on the resident sessions it started (`status`, `wait`, `cancel`
and `close` answer only the originating session, see
[specialist-calls.md](./specialist-calls.md)), so long specialist work belongs
in a topic of its own; OpenCode runs stay bound to the topic and survive it
([opencode.md](../opencode.md)).

A new pinned topic is a `dm_topics` entry WITHOUT `thread_id`: the next gateway
start creates the forum topic and writes the id back through the symlink into
the private `config.yaml`; only then can its `channel_prompts` entry be keyed,
followed by `/restart`. Since nobody can rename a pinned topic, a new name is a
new entry. Hermes never deletes a Telegram topic: once an entry is gone, the
topic it created stays as an ordinary topic; close it by hand in the client.
