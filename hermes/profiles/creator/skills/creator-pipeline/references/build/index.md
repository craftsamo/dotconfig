# Build - hands make it; you hand off and supervise

Build turns each filled form from [Plan](../plan/index.md) into a
delivery by the hands. You produce nothing yourself for a served family -
even though the tools are in your reach and you can read the leaf's
`<Procedure>`. The run is the hands', on the hands' spend tally, in the
hands' context. Read the selected subject reference before dispatch or
resuming an approval round; its transport and release rules apply in
addition to this common procedure.

## Subject references

| Hands | Subject references |
| --- | --- |
| image-creator | [card](image-creator/card.md), [icon](image-creator/icon.md), [emoji](image-creator/emoji.md), [mascot](image-creator/mascot.md), [reimagine](image-creator/reimagine.md), [kit](image-creator/kit.md) |
| video-creator | [clip](video-creator/clip.md), [music-video](video-creator/music-video.md), [ad](video-creator/ad.md), [tour](video-creator/tour.md), [explainer-video](video-creator/explainer-video.md) |
| audio-creator | [speech](audio-creator/speech.md), [sfx](audio-creator/sfx.md), [music](audio-creator/music.md), [mix](audio-creator/mix.md) |

## The handoff text

Send exactly this, nothing before it, nothing after it:

```text
skill: <verb>-<subject>
intent: new | revise <absolute path of the previous delivery>
deliver: <absolute durable directory>
budget: <grant>                      # provider calls or local speech takes; omit = leaf default
form:
  <field>: <value>                   # one line per filled field
```

Paths are absolute. Japanese values are fine - the text travels as a
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

These are defaults, not a verb-only classifier: the selected subject
reference names free work that still requires `kind="work"` from its
first proposal, synthesis or evidence-extraction turn.

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

One session per job per hands; never carry unrelated jobs in one.

## Supervising

- The reply names the leaf, the paths, every QA check with its evidence,
  the spend line, and anything for you to decide. A reply missing paths
  or a spend line is a defect - ask for it, do not assume. Findings-only
  analyze leaves are the exception to output paths, never to evidence/spend.
- A `Q<n>:` from the hands is relayed the same way the form was filled:
  `clarify` to a human, text to the assistant - never answered from your
  own taste.
- A `no skill fits` is relayed as such and noted for the maintainer; do
  not fall back to a technic for a served family.
- A one-line "procedure note" from the hands (the leaf and the runtime
  disagreed) goes to the maintainer verbatim; the delivery still counts.
- Two independent forms may use separate `specialist_call` conversations
  (parallel when live messaging supports it). A dependent form waits for
  the report it consumes; copy the consumed path into the next form.

## Legacy - families with no hands yet

Until a family's leaves land, you are still its producer: load
[Produce](../legacy/produce.md), [direction](../legacy/direction.md)
(anchor before a batch), or [advisory](../legacy/advisory.md), with
their engines [iterate](../legacy/iterate.md), [verify](../legacy/verify.md),
[delivery](../legacy/delivery.md), [resume](../legacy/resume.md), and the
technic table in [capabilities](../capabilities.md). The MediaBrief
checklist ([brief](../legacy/brief.md)) replaces the form there.
[Cards](../legacy/card.md) exist only for legacy families. Nothing in
this branch changes for served families - do not mix the two: a job
that spans a served and a legacy family is two handoffs, the hands'
first. A legacy job that needs spoken audio (narration for
`creator-html-motion`, a mix input for `creator-media-assembly`) takes a
finished audio-creator delivery as its QA-passed input part - the
legacy family consumes it, it never synthesizes speech itself.

## Build is done when

- every form has a report with paths at `deliver:` (or findings only for
  analyze leaves) and a spend line;
- every `Q<n>:` was relayed and answered, or the job is parked waiting
  for the client and says so;
- sessions opened for the job are closed or explicitly kept for a revise
  round the client asked for.
