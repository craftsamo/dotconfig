# Resident sessions — the default for heavy work

A resident session is a persistent `hermes -p <profile> chat` conversation
owned by the assistant, driven through the wrapper:

```
~/.hermes/profiles/assistant/scripts/resident-session.sh \
    start <key> --profile <name> [--topic "<t>"] (-q "<brief>" | -f <file>)
resident-session.sh send  <key> (-q "<msg>" | -f <file>) [--image <path>]
resident-session.sh status [<key>] | list | close <key> [--note "<n>"]
```

## Mechanics

- **Always run turns via `terminal` with `background=true` +
  `notify_on_complete`** — a specialist turn routinely exceeds the
  foreground timeout. The completion notification carries the reply
  (script stdout). Never poll; never block your own turn waiting.
- **Key = `<topic>-<profile>[-<purpose>]`** (e.g. `12116-creator-pv`).
  One live session per key; turns are serialized per key by the wrapper
  (busy → exit 75: wait for the in-flight notification instead of
  retrying). The wrapper re-captures the session id every turn, so
  compaction never strands a key.
- **The session cannot see this chat.** The first turn carries a
  self-contained SessionBrief:

  ```text
  Goal: <outcome and beneficiary — one short paragraph>
  Context: <the settled decisions and taste signals from the chat that
            the specialist needs; paste, don't reference>
  Inputs: <paths, URLs, pasted data, reference images via --image>
  Deliverable: <format, language, length; where to write files — always the
               owning Group's durable path, e.g.
               ~/Workspaces/Projects/<Group>/.agent/deliverables/<job>/;
               use ~/Workspaces/.deliverables/<job>/ only when no single
               Group owns the work>
  Constraints: <scope limits, deadlines, things NOT to do>
  <grant lines when relevant — see below>
  ```

  After the first turn the session accumulates its own context;
  follow-up turns are ordinary conversation ("C2の本を開いた状態に",
  "最後2秒は開眼で").
- **Grants live in the conversation.** State them in the brief and expand
  them in later turns; the session log is the record:
  - `Budget:` (creator) — generation-spend caps; omitted = creator
    defaults.
  - `Authority:` (engineer) — `A1` commit-only (default) / `A2` + push +
    PR / `A3` + dependency changes, plus `scope:` / `do not touch:`
    boundaries. Grant only what the user sanctioned in the plan.
  - `Publish:` (marketer) — absent = draft-only; posting needs the exact
    text approved verbatim by the user, or an explicit in-cap `P1` grant.
    Publishing is irreversible; never approve a post autonomously.
- **Deliverables are files at durable paths + a reply that names them.**
  Sessions must never leave results only in scratch dirs or tool caches.
- **Lifecycle: close on acceptance.** A resident session is per-
  deliverable, not immortal — `close` it once the user accepts, so
  context rot never accumulates. A follow-up request after close starts a
  fresh session, seeded with the canonical keeper or the user's accepted
  chat attachment rather than cleaned staging.
- **Clean on acceptance, not promotion.** Producer-verification promotion
  removes only reproducible caches; variants and useful intermediates
  survive until acceptance. Once accepted, move any canonical keepers to
  the Group's typed surfaces, clear the job's scratch and delivery staging,
  then close the session. Durable notes remain.
- **Failure handling** — a nonzero turn or timeout: read the tail of
  `~/.hermes/profiles/assistant/resident-sessions/<key>.log`, retry once
  if transient, otherwise report plainly and decide with the user. If a
  session has gone incoherent (context rot), close it and start a fresh
  one seeded with the surviving artifacts — never fight a rotten session.

## Revision escalation from cards

When a card deliverable fails your QA and the fix is not a mechanical
re-render, do NOT cycle cards: open (or reuse) the capability's resident
session seeded with the artifact paths + itemized defects, and iterate
there. Cards produce; sessions converge.
