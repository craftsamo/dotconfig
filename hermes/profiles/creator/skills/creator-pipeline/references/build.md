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

Use the client's existing Group-local job directory, for example
`~/Workspaces/Personal/<G>/.agent/deliverables/<job>/video-plan` (expanded
to an absolute path). All three hands accept these job-owned subdirectories,
not only a Group root. The existing Group-root and
`~/Workspaces/.deliverables/<job>/` forms remain valid. Create missing
job-owned descendants only beneath existing parents; never create a Group,
overwrite an existing output, or infer upload consent from a local path.
Do not relocate a valid Group-local request to the global deliverables area.

## Transport

| Leaf | Transport |
| --- | --- |
| free, bounded one reply (`source`, `create`, `edit`, `analyze`) | `specialist_call(target="<hands>", message=<the text>, kind="inquiry")`; the reply is the leaf's `<Report>` or a `Q<n>:` block |
| metered, multi-turn, or anything whose estimate exceeds ~4 minutes (`generate`) | `specialist_call(target="<hands>", message=<the text>, kind="work")`; the tool starts the resident session you supervise |
| audio-creator's synthesis/ASR-heavy leaves (`generate-speech`; an `edit-speech`/`analyze-speech` that needs fresh ASR rather than reused sidecars) | `kind="work"` as in the metered row, even though the leaf is `cost: free` — synthesis and ASR routinely outlive the reply window. Use `kind="inquiry"` only when bounded and known to finish in one reply (reused, already-validated sidecars; no fresh ASR) |
| video-creator's `create-tour` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; local snapshots/rendering and preview approval are not one-reply work |

Pass the exact handoff text as `message`, with the released inputs, permissions
and budget unchanged. Transport is not a release or an additional grant.
Use only configured, policy-allowed target names, never an arbitrary profile,
URL, raw `a2a_call`, or direct resident script for new work.

Continue with `specialist_call(target="<hands>", conversation_id=<returned id>,
message=<the completed form>)`: both target and conversation_id are required;
the backend stays pinned. A short answer to an inquiry's `Q<n>:` can use that
conversation, but if it reveals metered or multi-turn work, obtain its release
and open a new `kind="work"` conversation; never upgrade the inquiry in place.
Inspect with `specialist_session(action="status", conversation_id=<id>)` and
close accepted work with `specialist_session(action="close", conversation_id=<id>)`.
Close is bookkeeping, not cancellation; never retry an unknown result or
silently switch backends.

Verified live messaging receives background completion from the tool. CLI,
including Creator nested in a resident session, waits synchronously for a
finite turn (at most 5400 seconds, shortened by the outer deadline); it has no
later wakeup promise. A2A inbound cannot launch work: ask the caller to reissue
the released unit to Creator with `specialist_call(kind="work")`.

Hands and their peers: `image-creator` (still images), `video-creator`
(short clips and task-local authored UI tours; no TTS), `audio-creator` (spoken speech only — no music,
singing or sound effects). One session per job per hands; never carry
unrelated jobs in one.

For analyze-clip, `deliver` may be omitted: its report and scratch evidence
are the result, not a new movie. A free video analysis may approach the
reply window; use `kind="work"` when the estimate exceeds it rather
than repeating an A2A request that may still be running.

For analyze-speech, `deliver` may likewise be omitted: its report is
findings only, no new audio file, and expect no files back beyond the
reply text itself.

## Supervising

For create-tour, pass approved semantics and literal custom intro/outro/style
directions, not a screenshot-per-step manifest. VideoCreator authors the UI,
state changes and camera in task-local source, never managed helper scripts.
Preserve screen_mode and the reference/source/target distinction. For explicit
modes, relay exact proposal-vN.md + approval_sha256 only after client consent.
Consent to reconnaissance is not unlimited action consent. Capture's scope
covers target/origins, start state, allowed actions, dummy data, forbidden actions
and time/attempt ceilings. VideoCreator records through capture.py, not a shared
browser or Assistant. No native capture or login/private-region fallback. Keep
raw takes, approval hashes and action evidence private. Confirm real moving media
and source-time mapping instead of screenshots; keep/mute audio must be explicit.
If narration is needed, pass finished audio-creator WAV/words.json inputs only.
Preview returns a frozen source project and snapshots, not a finished MP4.
After client approval, continue that work conversation with `intent: revise`
and `preview: no`; the hands render the unchanged approved project into a
fresh final directory. Changed fields require a new source project/preview.
Never invoke raw A2A or resident scripts, nor edit the hands' HTML yourself.
Check that custom beats were actually rendered, not silently replaced by one
of the three examples. Explicit none is the only omission instruction.

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
- Two independent forms may use separate `specialist_call` conversations
  (parallel when live messaging supports it). A dependent form waits for
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
