# Assistant

Front-door Client: quality gate, visual design, creative early delivery, entry
routing, tiers and pinned topics. Read it before changing the Assistant's
entries, gate or topics. Part of the Hermes design docs — index:
[`PROFILES.md`](../../PROFILES.md).

## Assistant quality gate

For non-creative work, the assistant is the quality gate. Every specialist
deliverable (a resident session reply) is a candidate until the assistant has
verified the actual artifact per the `qa-assistant-*` entries under
`profiles/assistant/skills/assistant-pipeline/` and common QA
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
Plan entry's `plan-assistant-creative/references/ui-design.md`. The hands keep
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
- `qa-assistant-creative` is the explicit user-requested inspection entry, never
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
`chat-assistant` plus `{plan,execute,qa}-assistant-<domain>` for engineering,
creative, writing, research, search and marketing. Each child's `SKILL.md` owns
its mode/domain index. No entry lives below the parent's `references/`, which
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
  `compression.protect_first_n` does not prove the bodies stay present. After an
  approved restart, `/new` starts a session on the refreshed index.
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

| Service                               | Toolset                       | Notes                                                                                                                   | Contract                                    |
| ------------------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Google Sheets, Gmail, Drive, `gcloud` | `google_access`               | terminal path around it is blocked                                                                                      | [google-access.md](../google-access.md)     |
| WhatsApp                              | `whatsapp_access`             | local mirror                                                                                                            | [whatsapp-access.md](../whatsapp-access.md) |
| Signal                                | `signal_access`               | mirror keeps expired messages, drops deleted-for-everyone                                                               | [signal-access.md](../signal-access.md)     |
| Discord (user account, not the bot)   | `discord_access`              | one engine holds the token                                                                                              | [discord-access.md](../discord-access.md)   |
| Telegram (user account, not the bot)  | `telegram_access`             | a sync agent alone holds the session                                                                                    | [telegram-access.md](../telegram-access.md) |
| X                                     | `x_access`                    | read-only; browser stays off x.com except two saved-draft tasks (`x-access:x-twitter-drafts`); Marketer shares the tool | [x-access.md](../x-access.md)               |
| note.com                              | `note_access`                 | drafts only, never publishes; browser stays off note                                                                    | [note-access.md](../note-access.md)         |
| Substack                              | `substack_access`             | Marketer reads only                                                                                                     | [substack-access.md](../substack-access.md) |
| YouTube                               | `youtube_access`              | Marketer reads only; non-API settings via Studio after a `clarify`                                                      | [youtube-access.md](../youtube-access.md)   |
| EVM / Solana                          | `evm_access`, `solana_access` | reads shared with Researcher, Searcher, Marketer; wallet actions the Assistant's alone                                  | [web3.md](../web3.md)                       |

Marketing work is the Assistant's to execute, with Marketer as its strategy
advisor ([marketer.md](./marketer.md)): the marketing entries consult Marketer on
direction, reviews and results, release Writer and hands units, accept them with
the shared writing contract and save the approved service-side draft themselves
after exact remote-save consent. Nothing publishes, schedules or sends; the user
publishes. Marketer's browser is never a fallback.

### Pinned Telegram topics

The assistant's `platforms.telegram.extra.dm_topics` (private `config.yaml`)
declares exactly two pinned topics, both skill-less Assistant surfaces rather
than worker threads: the chat-wide `assistant-pipeline` binding is the only skill
surface. Each topic's contract lives entirely in its
`channel_prompts['<thread_id>']` entry (template in `config.example.yaml`). The
validator (`validate_assistant_dm_topics`) rejects any topic carrying a `skill:`
key and any `dm_topics` list without a topic literally named `Inbox`.

- **Inbox** receives system cron output and starts no work. Jobs keep bare
  `deliver: telegram`; `scripts/profile-secrets.sh` derives
  `TELEGRAM_CRON_THREAD_ID` from the topic literally named `Inbox`, so renaming
  it makes every such job fail closed.
- **Admin** is the inline surface for small administrative work: workspace
  bookkeeping, edits to the `~/.config` dotconfig repo and its Hermes profiles,
  and Hermes upkeep (browser relaunch, cron / validator checks, skill
  housekeeping). No resident session or delegation. It is not the only OpenCode
  topic: code work happens in any topic per the engineering entries (see
  [opencode.md](../opencode.md)).

Both fix the tier to `inline`; work that needs a specialist hands off to a new
ad-hoc topic, which inherits the chat-wide binding and owns the sessions. A new
pinned topic is a `dm_topics` entry WITHOUT `thread_id`: the next gateway start
creates the forum topic and writes the id back through the symlink into the
private `config.yaml`; only then can its `channel_prompts` entry be keyed,
followed by `/restart`. Hermes never deletes a Telegram topic: close retired ones
by hand in the client.
