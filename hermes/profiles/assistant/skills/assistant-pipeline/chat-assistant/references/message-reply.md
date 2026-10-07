# Message reply

Interpret a message the user received (Telegram, DM, email, chat) and draft
replies in the user's voice. Explain what it means, propose replies, never
send on your own (a WhatsApp, Signal, Discord or Telegram reply the user tells you
to send goes through `whatsapp.md`, `signal.md`, `discord.md` or `telegram.md`). Not for a brand-new outbound message with no sender or topic context;
a reply that grows into a crafted piece goes through Plan (writing).

## Steps

**0. Parse the request.** Separate the sender (a handle or name), the content
(the message itself) and the user's ask: interpret, draft a reply, or both.

**1. Resolve the sender** with the `workspace_registry` tool, never a terminal
command or the CSV files:

```text
workspace_registry(action="whois", query="<handle or name>")
```

Each match carries `display_name`, `aliases`, `contacts`, `preferred_language`
and `languages`, `timezone`, `notes`, and per-project `memberships`
(`project_id`, `working_relationship`, `roles`, `responsibilities`, `areas`,
`can_merge` / `can_deploy`, `notes`). Memberships are the bridge from "who" to
"which work"; a person may belong to several projects. No match → proceed
with what is known and offer to add them (`person_set` with `id` and
`display_name`, plus `add` facet=contact for a handle the user gave). Never
invent facts.

**2. Classify the scope** — Projects, Personal or unrelated — person first,
then reconciled with the text:

- The sender's memberships are the primary signal: if they work on `P` and
  the content fits `P`'s areas or responsibilities, the scope is
  `Projects/<P>`.
- Match product, repo and keyword hints against the registry (`projects`,
  `project` with id `<P>`: names, aliases, tags). Prefer the project the
  content actually supports over the membership.
- Personal: a contact with no project membership and personal content.
- Unrelated: nothing maps to a project or a personal area.
- Several plausible projects, or person and content disagree → ask.

**3. Gather just enough context** — summarize, never dump:

- `Projects/<P>`: the `project` action (repos, links, members, tags), prose in
  `~/Workspaces/Projects/<P>/docs/about/`, and for code-specific messages the
  repo's `github/<repo>/AGENTS.md`. Stay within `P`.
- Personal: the sender's registry `notes`, summarized. Touch other Personal
  groups (e.g. the budget) only with an explicit, specific OK.
- Unrelated: the message and general knowledge; no workspace lookups.

**4. Interpret.** Say what the sender is saying and what, if anything, they
ask for or expect back. Flag uncertainty instead of guessing. Call out
anything that looks like a scam or an unusual payment or transfer request.

**5. Use the comms context.**

- Language ← `preferred_language` (fallback: their `languages`). If it is
  empty and they list several, ask which.
- Register and tone ← the membership's `working_relationship` and the
  person's `notes` (e.g. "conclusion-first").
- Framing ← membership `notes`, `roles` and `responsibilities`.
- Scope of asks ← `can_merge` / `can_deploy` and `responsibilities`.

**6. Clarify the user's intent** when it changes the reply: accept, decline,
negotiate, ask for information, defer or acknowledge; tone and length; what to
include or avoid. Never infer a decision from "make it friendly".

**7. Draft 1–3 variants** (e.g. concise / warm / firm) in the user's voice,
reflecting the interpretation. When the user asks "does this work?" about
their own draft, answer that first and give one revised version.

## Copy-ready output

The user copies a reply straight into another app, so each variant must copy
cleanly with one tap:

- Put every variant in its own fenced block tagged `text`, holding exactly
  the text to send — no label, quote marks, notes or placeholders inside.
  Label it on the line above (`**A — concise**`) and add any one-line note
  below the block.
- Keep the message's own line breaks, emoji and punctuation; no Markdown
  inside the block (it would be pasted literally).
- An email gets a separate `text` block for the subject, then the body.
- If the text itself contains three backticks, fence it with four.
- Put the interpretation first, the variants after it, and nothing between a
  label and its block.
- Keep variants short enough to fit the reply; a long reply becomes one file
  delivered by path instead.

````markdown
**A — concise**

```text
Thanks, Alex. Understood — let's keep the page live until Friday and talk about the plan on Monday.
```

**B — warm**

```text
Thanks for the update, Alex, and no worries at all. Let's keep the page live until Friday; I'd love to hear what you think we should change on Monday.
```
````

## Safety

People and Personal data are sensitive; project member calibration is
semi-private.

- Read locally and summarize; never paste raw records, PII or member
  calibration (`working_relationship`, notes) into chat or logs.
- Keep one project's (or a personal) context out of another.
- Reply language and tone match the sender's record.
- **Never send on your own.** The user approves the final text; a reply the
  user tells you to send goes through the channel's reference above, else
  the user sends it.
- No invented facts or commitments beyond what the user approved.
- Registry data missing or stale → say so and offer to update it
  (`person_set`, `add` facet=contact) so the next lookup resolves.
