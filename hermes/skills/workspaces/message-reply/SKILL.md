---
name: message-reply
description: >-
  Help draft a reply to a received message (Telegram/DM/email/chat). Resolves the sender
  against the People registry for context (preferred language, tone, roles, permissions),
  clarifies intent, and offers a few on-voice variants for the user to pick — never sends
  automatically. Use when the user shares an incoming message and wants help responding.
  返信, メッセージ返信, 返事, reply, respond, draft a reply, answer a message, DM.
version: 0.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [message-reply, communication, people, personal, drafting]
    category: workspaces
---

# Message reply

Draft a reply to a message the user received. Bias toward **the user's voice, the sender's
context, and the user's approval** — propose, never send.

## When to use
- The user pastes/forwards an incoming message and wants help replying.
- The user asks "how should I respond to X?" about a specific message/sender.

## When NOT to use
- Composing a brand-new outbound message to nobody in particular (no sender context needed).
- Anything that requires actually sending — this skill only drafts; the user sends.

## 1. Resolve the sender (People registry; join key = person_id)
Use the `people` skill's CLI (`${HERMES_SKILL_DIR}/../people/scripts/pp`, or just `pp` if
on PATH). People data is **sensitive** — read locally, summarize, never paste raw records.
```
pp whois "<handle or name>"      # e.g. a Telegram handle, GitHub login, or display name
```
`whois` returns the matched person(s) with: `display_name`, `aliases`, `contacts`,
`preferred_language` + `languages`, `timezone`, `tags`, `relationships`, and per-project
`memberships` (`working_relationship`, `roles`, `responsibilities`, `areas`, `permissions`,
project `notes`). A person may belong to several projects.
- No match → proceed with what's known; offer to add them
  (`pp upsert-person --id <slug> --name "..." [--contact ...]`). Don't invent facts.

## 2. Use the context
- **Language** ← `preferred_language` (fallback: the person's `languages`). Reply in their
  language unless the user says otherwise. If `preferred_language` is null and they list
  several, ask the user which to use.
- **Register / tone** ← membership `working_relationship` + `relationships` + any `comms`
  tag (e.g. "conclusion-first").
- **Framing** ← membership `notes` (comms prefs) + `roles`/`responsibilities` (address what
  they own).
- **Scope of asks** ← membership `permissions` (don't ask beyond what they can
  approve/review/merge/deploy).

## 3. Clarify the user's intent
- Outcome: accept / decline / negotiate / ask for info / defer / acknowledge.
- Tone and length; anything to explicitly include or avoid.

## 4. Draft & offer choices
- Write in the **user's** voice; concise; reflect the context above.
- Offer **1–3 variants** (e.g. concise / warm / firm); the user picks and edits.
- Don't fabricate facts or commit on the user's behalf beyond what they approved.

## Safety gates (People data is sensitive — see People/AGENTS.md)
- [ ] Read people/team data **locally only**; summarize — never paste raw records/PII to chat/logs.
- [ ] Reply language & tone match the sender's record.
- [ ] **Never send automatically** — the user approves the final text and the send action.
- [ ] No invented facts or unauthorized commitments.
- [ ] If registry data is missing/stale, say so; don't infer personal facts. Offer to update
      People (`pp upsert-person` / `pp contact-set`) so next time resolves cleanly.
