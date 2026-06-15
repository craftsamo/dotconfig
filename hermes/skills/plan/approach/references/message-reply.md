# Scenario: message reply

Apply on top of the general spine when the user wants help replying to a received message.

## Resolve the sender (local people registry; join key = person_id)
1. Find the sender's `person_id` — match handle/name to `contacts.telegram`/`aliases` in
   `~/Workspaces/Personal/People/data/<id>.json`, or ask the user.
2. Canonical record `~/Workspaces/Personal/People/data/<person_id>.json` →
   `display_name`, `languages`, `aliases`, `status`, `notes`.
3. Membership(s) `~/Workspaces/Projects/*/teams/members/<person_id>.json` →
   `roles`, `responsibilities`, `areas`, `working_relationship`, `notes` (comms prefs),
   `permissions`. (A person may belong to several projects.)
4. If the sender isn't in the registry, proceed with what's known; optionally offer to add them.

## Use the context
- **Language** ← `People.languages` (reply in their language unless told otherwise)
- **Register / tone** ← `membership.working_relationship` (+ relationship notes)
- **Framing** ← `membership.notes` comms prefs + `roles`/`responsibilities` (address what they own)
- **Scope of asks** ← `permissions` (don't ask beyond what they can approve/merge/deploy)

## Clarify the user's intent
- Outcome: accept / decline / negotiate / ask for info / defer / acknowledge; tone; length;
  anything to include or avoid.

## Draft & offer choices
- Write in the user's voice; concise; reflect the context above.
- Don't fabricate facts or commit on the user's behalf beyond what they approved.
- Offer 1–3 variants (e.g., concise / warm / firm); the user picks and edits.

## Safety gates (People data is sensitive — see People/AGENTS.md)
- [ ] Read people/team data **locally only**; summarize — never paste raw records/PII to chat/logs
- [ ] Reply language & tone match the sender's record
- [ ] **Never send automatically** — the user approves the final text and the send action
- [ ] No invented facts or unauthorized commitments
- [ ] If registry data is missing/stale, say so; don't infer personal facts
