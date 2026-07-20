# Creative approach — reference

Loaded after Step 3 picks **Approach=Creative**. Dispatches to creator for
any media production; you produce no media yourself.

## When to pick Creative

- **Any media production** — image, video, GIF, voice, single or batch.
  Always goes to creator, no matter how small. The front door only collects
  the brief and dispatches.
- If the request mixes media with implementation/research, Plan likely
  applies instead (Plan can fan out a creator sub-task mid-stream) — see
  `references/plan.md`.

## What to collect before dispatching (MediaBrief)

Gather (from the chat, the user, and memory) before dispatching, so creator
never has to block on style questions or burn credits guessing:

- **Purpose & audience** — what the asset is for, where it will be seen.
- **Destination & specs** — platform/placement and its constraints
  (dimensions, aspect ratio, duration, format, file-size cap) when known.
- **Style direction** — tone, palette, brand assets, reference images/links;
  paste or link references into the task body.
- **Quantity & variants** — how many, which sizes/crops.
- **Deadline / priority.**

Ask the user at most one compact round of questions for missing essentials
(a `clarify` if options exist); fill sensible defaults yourself and say so.

## Dispatching

Put all of the MediaBrief in the task body (`Inputs` / `Constraints`) —
creator cannot see this chat. Use the standard `<TaskSpec>` shape from the
main skill, with:

- `assignee: creator`
- `workspace_kind: scratch` (or `dir` if assets must land somewhere specific)
- The MediaBrief fields in the body
- Output spec: file format(s), delivery via `kanban_attach` or to
  `~/Workspaces/.deliverables/`

Ack with the task id and deliver on the completion notification. Small
single assets go to creator too — never improvise media inline.

## After dispatch

Hand off to Step 7's standard mechanics: `<AfterCreate>` ack, `<Failures>`
recovery, `<BlockedTriage>` for any creator block (rare — the MediaBrief
should have eliminated style ambiguity up front).
