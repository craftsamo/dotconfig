---
name: message-reply
description: >-
  Help interpret and reply to a received message (Telegram/DM/email/chat). First routes the
  message to its scope — a ~/Workspaces/Projects/<group>, ~/Workspaces/Personal, or unrelated —
  then resolves the sender against the People registry (preferred language, tone, roles,
  permissions) plus the relevant project/personal context, explains what the message likely
  means, and offers a few on-voice reply variants for the user to pick — never sends
  automatically. Use when the user shares an incoming message and asks "what does this mean?"
  or wants help responding. 返信, メッセージ返信, 返事, 解釈, どういう意味, 意味, reply, respond,
  draft a reply, answer a message, what does this mean, interpret, DM.
version: 0.2.0
author: Hermes agent
license: MIT
metadata:
  hermes:
    tags: [message-reply, communication, people, projects, personal, drafting]
    category: workspaces
---

<Goal>

Interpret and draft a reply to a message the user received. Bias toward **the user's voice, the
sender's context, the topic's scope, and the user's approval** — explain what it means, propose
replies, never send.

</Goal>

<Scope>
<UseWhen>

- The user pastes/forwards an incoming message and wants help understanding or replying.
- The user asks "what does X mean?" / "どういう意味？" about a message from a specific sender.

</UseWhen>

<DoNotUseWhen>

- Composing a brand-new outbound message to nobody in particular (no sender/topic context).
- Anything that requires actually sending — this skill only interprets and drafts; the user sends.

</DoNotUseWhen>
</Scope>

<Engine>

Reuse the sibling CLIs; never open their DBs/files. Siblings share the cluster dir, so from
this skill:
- People: `${HERMES_SKILL_DIR}/../people/scripts/pp` (or `pp` on PATH) — resolve the sender.
- Projects: `${HERMES_SKILL_DIR}/../projects/scripts/pj` (or `pj` on PATH) — project identity/members.
People & Personal data are **sensitive** (see People/AGENTS.md, Personal/AGENTS.md) and project
member calibration is **semi-private** — read locally, summarize, never paste raw records/PII.

</Engine>

<Steps>

**0. Parse the request.** Separate three things from what the user sent:
- **Sender** (`xxx`) — a handle or name.
- **Content** (`…`) — the actual message to interpret/answer.
- **The user's ask** — interpret ("what does this mean?"), draft a reply, or both.

**1. Resolve the sender** (People registry; join key = person_id):
```
pp whois "<handle or name>"      # a Telegram handle, GitHub login, or display name
```
Returns JSON `{query, matches:[…]}`; each match has `display_name`, `aliases`, `contacts`,
`preferred_language` + `languages`, `timezone`, `tags`, `relationships`, and per-project
`memberships` (`project_id`, `working_relationship`, `roles`, `responsibilities`, `areas`,
`permissions`, `notes`). The **memberships are the bridge from "who" to "which work"** — they
drive the scope step below. A person may belong to several projects.
- No match → proceed with what's known; offer to add them
  (`pp upsert-person --id <slug> --name "..." [--contact ...]`). Don't invent facts.

**2. Classify the scope** (Projects / Personal / unrelated). Decide what the **content** is
about — person-first, then reconcile with the text:
- **Primary signal** ← the sender's `memberships`. If `xxx` works on project `P` and the content
  fits `P`'s `areas`/`responsibilities`, scope = `Projects/<P>`.
- **Reconcile with content** — match product/repo/keyword hints in `…` against the registry:
  `pj list`, `pj show --id <P>` (names, aliases, tags). If the content points elsewhere than the
  membership, prefer the project the content actually supports.
- **Personal** — sender is a personal contact (no project membership, or a personal
  `relationship`) and the content is personal.
- **Unrelated** — nothing in the message maps to a project or a personal area.
- **Ambiguous** (several plausible projects, or person↔content mismatch) → ask the user which.

**3. Gather context for that scope.** Pull just enough to interpret and reply well — summarize,
never dump:
- **Projects/<P>** — `pj show --id <P>` (repos, links, members, tags) + prose knowledge in
  `~/Workspaces/Projects/<P>/docs/about/`; for code-specific messages also the repo's
  `github/<repo>/AGENTS.md`. Use the sender's membership `areas`/`responsibilities` to see what
  they own. Stay within `P` — don't pull other projects' context.
- **Personal** — the sender's People `relationship`, `notes`, and comms `tags` (summarized).
  Default to **People only**; touch other Personal groups (e.g. the budget) only with an explicit,
  specific OK, and never paste raw values.
- **Unrelated** — rely on the message text + general knowledge; no workspace lookups.

**4. Interpret the message.** Answer "what does this mean?": in the gathered context, explain
what the sender is saying and what (if anything) they're asking for or expect back. Flag
uncertainty rather than guessing.

**5. Use the comms context:**
- **Language** ← `preferred_language` (fallback: the person's `languages`). Reply in their
  language unless the user says otherwise. If `preferred_language` is null and they list several,
  ask the user which to use.
- **Register / tone** ← membership `working_relationship` + `relationships` + any `comms` tag
  (e.g. "conclusion-first").
- **Framing** ← membership `notes` (comms prefs) + `roles`/`responsibilities` (address what they own).
- **Scope of asks** ← membership `permissions` (don't ask beyond what they can
  approve/review/merge/deploy).

**6. Clarify the user's intent:**
- Outcome: accept / decline / negotiate / ask for info / defer / acknowledge.
- Tone and length; anything to explicitly include or avoid.

**7. Draft & offer choices:**
- Write in the **user's** voice; concise; reflect the interpretation and context above.
- Offer **1–3 variants** (e.g. concise / warm / firm); the user picks and edits.
- Don't fabricate facts or commit on the user's behalf beyond what they approved.

</Steps>

<SafetyGates>

People/Personal data is sensitive; project calibration is semi-private.

- [ ] Read people / project / personal data **locally only**; summarize — never paste raw
      records/PII or member calibration (`working_relationship`/`notes`) to chat/logs.
- [ ] Scope stays put — don't leak one project's (or a personal) context into another.
- [ ] Personal scope defaults to **People only**; other Personal groups need an explicit OK.
- [ ] Reply language & tone match the sender's record.
- [ ] **Never send automatically** — the user approves the final text and the send action.
- [ ] No invented facts or unauthorized commitments.
- [ ] If registry data is missing/stale, say so; don't infer personal facts. Offer to update
      People (`pp upsert-person` / `pp contact-set`) so next time resolves cleanly.

</SafetyGates>
