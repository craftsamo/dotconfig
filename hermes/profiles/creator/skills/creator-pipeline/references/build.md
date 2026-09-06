# Build — hands make it; you hand off and supervise

Build turns each filled form from `plan.md` into a delivery by the hands.
You produce nothing yourself for a served family — even though the tools
are in your reach and you can read the leaf's `<Procedure>`. The run is
the hands', on the hands' spend tally, in the hands' context.

## The handoff text

Send exactly this, nothing before it, nothing after it:

```
skill: <verb>-<subject>
intent: new | revise <absolute path of the previous delivery>
deliver: <absolute durable directory>
budget: <grant>                      # provider calls or local speech takes; omit = leaf default
form:
  <field>: <value>                   # one line per filled field
```

Paths are absolute. Japanese values are fine — the text travels as a
message (or a file), never as an argv string.

## Transport

| Leaf | Transport |
| --- | --- |
| free, one reply (`source`, `create`, `edit`, `analyze`) | `a2a_call(agent="<hands>", message=<the text>)`; the reply is the leaf's `<Report>` or a `Q<n>:` block; answer a `Q<n>:` with a second `a2a_call` carrying the same form completed, same `context` |
| metered, or anything whose estimate exceeds ~4 minutes (`generate`) | a resident session you supervise: write the text to a file, then `~/.hermes/profiles/assistant/scripts/resident-session.sh start <job>-<medium> --profile <hands> -f <file>` with `background: true` + `notify_on_complete`; later turns with `send <key> -f <file>`; `close <key>` on acceptance |
| audio-creator's synthesis/ASR-heavy leaves (`generate-speech`; an `edit-speech`/`analyze-speech` that needs fresh ASR rather than reused sidecars) | the same resident session as the metered row, even though the leaf is `cost: free` — synthesis and ASR routinely outlive the reply window. Use the free one-reply transport only when the job is bounded and known to finish in one reply (reused, already-validated sidecars; no fresh ASR) |

Hands and their peers: `image-creator` (still images), `video-creator`
(short clips; no TTS), `audio-creator` (spoken speech only — no music,
singing or sound effects). One session per job per hands; never carry
unrelated jobs in one.

For analyze-clip, `deliver` may be omitted: its report and scratch evidence
are the result, not a new movie. A free video analysis may approach the
reply window; use a resident session when the estimate exceeds it rather
than repeating an A2A request that may still be running.

For analyze-speech, `deliver` may likewise be omitted: its report is
findings only, no new audio file, and expect no files back beyond the
reply text itself.

## Supervising

- The reply names the leaf, the paths, every QA check with its evidence,
  the spend line, and anything for you to decide. A reply missing paths
   or a spend line is a defect — ask for it, do not assume. Findings-only
   analyze leaves are the exception to output paths, never to evidence/spend.
- A `Q<n>:` from the hands is relayed the same way the form was filled:
  `clarify` to a human, text to the assistant — never answered from your
  own taste.
- A `no skill fits` is relayed as such and noted for the maintainer; do
  not fall back to a technic for a served family.
- A one-line "procedure note" from the hands (the leaf and the runtime
  disagreed) goes to the maintainer verbatim; the delivery still counts.
- Two independent forms may run in parallel — a second `a2a_call`, or a
  second session key `<job>-<medium>-<part>`. A dependent form waits for
  the report it consumes; copy the consumed path into the next form.

## Legacy — families with no hands yet

Until a family's leaves land, you are still its producer: load
`legacy/produce.md` (Produce), `legacy/direction.md` (anchor before a
batch), or `legacy/advisory.md`, with their engines `legacy/iterate.md`,
`legacy/verify.md`, `legacy/delivery.md`, `legacy/resume.md`, and the
technic table in `capabilities.md`. The MediaBrief checklist
(`legacy/brief.md`) replaces the form there. Cards (`legacy/card.md`)
exist only for legacy families. Nothing in this branch changes for
served families — do not mix the two: a job that spans a served and a
legacy family is two handoffs, the hands' first. A legacy job that needs
spoken audio (narration for `creator-html-motion`, a mix input for
`creator-media-assembly`) takes a finished audio-creator delivery as its
QA-passed input part — the legacy family consumes it, it never
synthesizes speech itself.

## Build is done when

- every form has a report with paths at `deliver:` (or findings only for
  analyze leaves) and a spend line;
- every `Q<n>:` was relayed and answered, or the job is parked waiting
  for the client and says so;
- sessions opened for the job are closed or explicitly kept for a revise
  round the client asked for.
