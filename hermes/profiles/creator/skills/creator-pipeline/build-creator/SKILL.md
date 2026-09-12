---
name: build-creator
description: >-
  Dispatch approved media forms and supervise the hands.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [creator, build, dispatch, hands, delivery]
    category: creator-pipeline
---

<ReadBeforeWork>

Select the applicable entry from the available skills on every inbound turn or
completion, and before an action changes mode, subject or scope. A short approval
resumes the retained job; selection never restarts a plan or expands a grant.
Reuse full-body instructions only while present in current context, not a past
load, summary or preload marker. Direct entry requires the full kernel as well:

```text
skill_view(name="creator-pipeline")
```

Load that dependency if its body is missing. This entry is the mode procedure;
there is no separate common-mode file to load. Read only the selected subjects
below. Before applying another entry's detail, load its owning entry and kernel.
A missing required guide blocks the affected action, not the whole capability.
Creator reads hands forms and relevant options as a Client, never their producer
procedure as permission to execute a served leaf locally.

If skill_view returns unchanged while the earlier body is unavailable, use
read_file on the canonical document: `${HERMES_SKILL_DIR}/../SKILL.md` for the
kernel, `${HERMES_SKILL_DIR}/SKILL.md` for this entry, or its selected reference
under `${HERMES_SKILL_DIR}/references/`. Follow next_offset only when that read is
truncated. If the full required body still cannot be recovered, stop the affected
action and report the missing instructions. Never evade dedup with alternate
paths or artificial ranges. In raw text, `${HERMES_SKILL_DIR}` is the directory
of the document's owning SKILL.md, not whichever skill was loaded last.

</ReadBeforeWork>

# Build - hands make it; you hand off and supervise

Build turns each filled form from [Plan](../plan-creator/SKILL.md) into a
delivery by the hands. You produce nothing yourself for a served family -
even though the tools are in your reach and you can read the leaf's
`<Procedure>`. The run is the hands', on the hands' spend tally, in the
hands' context. Read the selected subject reference before dispatch or
resuming an approval round; its transport and release rules apply in
addition to this common procedure.

## Subject references

| Hands | Subject references |
| --- | --- |
| image-creator | [card](references/image-creator/card.md), [icon](references/image-creator/icon.md), [emoji](references/image-creator/emoji.md), [mascot](references/image-creator/mascot.md), [reimagine](references/image-creator/reimagine.md), [kit](references/image-creator/kit.md) |
| video-creator | [clip](references/video-creator/clip.md), [music-video](references/video-creator/music-video.md), [ad](references/video-creator/ad.md), [tour](references/video-creator/tour.md), [explainer-video](references/video-creator/explainer-video.md) |
| audio-creator | [speech](references/audio-creator/speech.md), [sfx](references/audio-creator/sfx.md), [music](references/audio-creator/music.md), [mix](references/audio-creator/mix.md) |

## The handoff text

Use exactly this shape for the tool's `message`. The transport's runtime
attribution and retained initial request surround it; they are not form fields
and never substitute for a human approval:

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

For an abandoned resident turn, inspect outputs, nested jobs and external effects
before `specialist_session(action="reconcile", conversation_id=<id>, evidence=...)`.
The tool only records a confirmed-stopped owned process group with no live,
foreign or unverifiable shell lock as `interrupted`. A lock naming that same
dead group is retained as evidence, never stolen or removed. Effects remain unknown; the conversation cannot be
resumed. Closing it is bookkeeping, never task acceptance or safe-retry evidence.
Missing handles, remaining locks and A2A uncertainty stay blocked; do not steal
locks, invent process evidence or repeat the request under a new ID.

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
- Answer a hands `Q<n>:` from settled context or granted discretion. Relay an
  unresolved consequential choice the same way the form was filled: `clarify`
  to a human, text to an agent Client. Do not invent approval or ask twice.
- A `no skill fits` is relayed as such and noted for the maintainer; do
  not fall back to a technic for a served family.
- A one-line "procedure note" from the hands (the leaf and the runtime
  disagreed) goes to the maintainer verbatim; the delivery still counts.
- Two independent forms may use separate `specialist_call` conversations
  (parallel when live messaging supports it). A dependent form waits for
  the report it consumes; copy the consumed path into the next form.
  Record the consumed version/hash in the existing job notes. When that input
  changes, invalidate only its dependent production/QA evidence. A completed
  transport is not acceptance of a part, an assembled deliverable or a saved draft.

## Legacy - families with no hands yet

Until a family's leaves land, you are still its producer: load
[Produce](../references/legacy/produce.md), [direction](../references/legacy/direction.md)
(anchor before a batch), or [advisory](../references/legacy/advisory.md), with
their engines [iterate](../references/legacy/iterate.md), [verify](../references/legacy/verify.md),
[delivery](../references/legacy/delivery.md), [resume](../references/legacy/resume.md), and the
technic table in [capabilities](../references/capabilities.md). The MediaBrief
checklist ([brief](../references/legacy/brief.md)) replaces the form there.
[Cards](../references/legacy/card.md) exist only for legacy families. Nothing in
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
