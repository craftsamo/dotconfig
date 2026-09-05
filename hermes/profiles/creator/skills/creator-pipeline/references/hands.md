# Hands — families served by a hands profile (v3)

A **hands** profile makes one medium from a filled form and nothing else.
For a family a hands serves, Creator does not produce: it chooses the
leaf, fills the leaf's form with the client, hands the filled form over,
gates what comes back with its own eyes, and delivers. The leaves are
visible to you through `skills.external_dirs` so you can read their
forms — **never run a leaf's `<Procedure>` yourself**, even though the
tools are in your reach; that is the hands' run, on the hands' budget
tally, in the hands' context.

## Served today

| Family | Hands | Leaves (read the form with `skill_view("<name>")`) |
| --- | --- | --- |
| icon | image-creator (A2A `:9907`) | `source-icon` — a published Iconify glyph, free · `create-icon` — favicon / PWA set from a first-party SVG, free · `generate-icon` — a model draws one in a named style, metered · `edit-icon` — recolour / background / cut-out / resize, free · `analyze-icon` — findings only, free |

Every other family stays on the technics in `capabilities.md` until its
leaves land.

## The client

You have clients, not entry points. The same procedure serves both:

- **Human** (your Telegram bot, a DM, or the CLI): fill the form with the
  **`clarify` tool** — the platform renders it natively (Telegram: one
  inline button per choice; CLI: a picker). Never type a `Q<n>:` list at a
  human. ONE call carrying one entry per open field: `required: true`
  fields you cannot infer, plus at most one optional field when it changes
  the deliverable (`style` for `generate-icon`, `what_for` for
  `analyze-icon`). A field with `options` becomes a single-select whose
  choices are those options, your recommendation FIRST (the UI marks it);
  the UI appends "Other" by itself, which is the form's `other: true`. A
  field without options is open-ended (omit `choices`). Put the field's
  `label` / `example` in the question text, never the options. A free-text
  answer is used as written.
- **Assistant** (a resident session it started, or an A2A peer call):
  parse its brief (Goal / Context / Inputs / Deliverable / Constraints /
  Budget) into the form. Anything required that the brief does not settle
  is ONE `Q<n>:` **text** block back to the assistant (2-4 options + your
  recommendation) — a peer reads text, not buttons; it answers from its
  own context or asks the user with its own clarify.

Pick the leaf by verb: an existing file to change → `edit`; a look no
library has → `generate`; a symbol a library has → `source`; a set from an
SVG → `create`; a judgment, no file → `analyze`. Two leaves in sequence
(`source-icon` then `edit-icon`, `generate-icon` then `create-icon` from
its SVG-less output is NOT possible — say so) are two handoffs; the second
waits for the first's report.

## The handoff

Send exactly this text, nothing before it, nothing after it:

```
skill: <verb>-<subject>
intent: new | revise <absolute path of the previous delivery>
deliver: <absolute durable directory>
budget: <grant>                      # metered leaves only; omit = leaf default
form:
  <field>: <value>                   # one line per filled field
```

`deliver` follows the brief; absent, the owning Group's
`.agent/deliverables/<job>/`, else `~/Workspaces/.deliverables/<job>/`.
Paths in the form are absolute; a reference image is copied there first.
Japanese values are fine in the form (it travels as a message, not argv).

Transport:

- **Free leaf, one reply** (`source`, `create`, `edit`, `analyze`) →
  `a2a_call(agent="image-creator", message=<the text>)`. The reply is the
  leaf's `<Report>` or a `Q<n>:` block; answer a `Q<n>:` with a second
  `a2a_call` carrying the same form completed (same `context`).
- **Metered or long** (`generate`, anything whose estimate exceeds ~4
  minutes) → a resident session you supervise:
  `~/.hermes/profiles/assistant/scripts/resident-session.sh start
  <job>-image --profile image-creator -f <file holding the text>` with
  `background: true` + `notify_on_complete`; later turns with `send`.
  Close it on acceptance.

## The gate

The hands verified against the leaf's `<QA>`; you verify against the
client's intent. Look at the delivered files with vision — the recommended
variant at native size, and at the size the client will use — before you
answer the client. A file that fails your eye goes back as
`intent: revise` with the form field that changes, never as a local fix.
A `Q<n>:` block from the hands is relayed the same way the form was
filled: `clarify` to a human, text to the assistant — never answered
from your own taste.
Report to the client: the paths, one sentence of what it is, the spend
line from the hands' report, and the hands' own open questions if any.
A `no skill fits` reply is relayed as such and noted for the maintainer;
do not fall back to a technic for a served family.
