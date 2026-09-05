# Plan — from a client's words to filled forms

Plan ends with one or more **filled forms** (each a hands leaf + its
fields), sequenced when there are several, each with a budget line where
metered — or with the finding that no leaf fits. Nothing is produced in
Plan; nothing is spent.

## The client

You have clients, not entry points; the same procedure serves both.
**Tell them apart by the shape of the message, not by the surface**: the
assistant always writes in the brief shape (`Goal:` / `Context:` /
`Inputs:` / `Deliverable:` / `Constraints:` / `Budget:` lines) — on the
CLI of a resident session or over A2A alike. A message in that shape is
the assistant; anything conversational is a human, even on the CLI.
(`clarify` in a non-interactive `-q` run cannot be answered and returns
at once — a brief-shaped message never gets one.)

- **Human** (your Telegram bot, a DM, the CLI). Fill the form with the
  **`clarify` tool** — the platform renders it natively (Telegram: one
  inline button per choice; CLI: a picker). Never type a `Q<n>:` list at a
  human. ONE call carrying one entry per open field: the `required: true`
  fields you cannot infer from what they said, plus at most one optional
  field when it changes the deliverable (`style` for `generate-icon`,
  `what_for` for `analyze-icon`). A field with `options` is a
  single-select whose choices are those options, your recommendation
  FIRST (the UI marks it); the UI appends "Other" itself, which is the
  form's `other: true`. A field without options is open-ended (omit
  `choices`). Put the field's `label` / `example` in the question text,
  never the options. A free-text answer is used as written.
- **Assistant** (a resident session it started, or an A2A peer call).
  Parse its brief — `Goal:` / `Context:` / `Inputs:` / `Deliverable:` /
  `Constraints:` / `Budget:` — into the form. Anything required the brief
  does not settle is ONE `Q<n>:` **text** block back (2-4 options + your
  recommendation) — a peer reads text, not buttons; it answers from its
  own context or asks the user with its own clarify.

Infer before you ask: a colour named in the message, a path pasted, a
"transparent" said in passing are answers. Ask only what is truly open.

## Choosing the leaf

`capabilities.md` lists the served families first. Read the candidate
leaf's front matter with `skill_view("<verb>-<subject>")` — the
`description` says what it delivers, the `form` says what it needs. Pick
by **verb**:

| The client has / wants | Verb |
| --- | --- |
| an existing file to change | `edit` |
| a look no library draws, or a subject no library has | `generate` |
| a symbol a published library already has | `source` |
| a set derived from something first-party (an SVG, a master) | `create` |
| a judgment, no file | `analyze` |

A family with no leaf yet is **legacy**: it is still yours to produce,
through `capabilities.md`'s technic table — see `build.md` "Legacy".

## Composite requests — a sequence of forms

"An icon set for the new bot" is two forms: `generate-icon` (the mark),
then `create-icon` from an SVG — which `generate-icon` does not produce,
so say so and offer `edit-icon` sizes instead. Decompose into leaves,
order them by what feeds what, and note the dependency ("form 2's
`source` = form 1's recommended variant"). Fill form 1 completely now;
fill a dependent form only when its input exists. Two independent forms
(a light and a dark icon) can run in parallel — `build.md`. Do not invent
structure beyond the leaves: no menus, presets, or Styles above the
form; a request that needs a leaf that does not exist is `no skill fits`
to the client, noted for the maintainer.

## Budget lines

A metered leaf takes a `budget:` line; absent, the leaf's default (icon:
4 variants + 1 corrective). The assistant's `Budget:` line is copied
through; a human is told the default and asked only when they want more.
Never hand a metered form off without knowing who pays for a corrective.

## Advisory — a conversation that may not end in a form

"Would a glass icon work on a dark sidebar?" is answered from what you
know and from a leaf's style notes (`references/styles/<style>.md` via
`skill_view(..., file_path=)`), at zero spend, with a proposal: "if yes,
this form". A cheap `analyze-*` leaf may back the opinion with
measurements — that is a handoff like any other.

## Plan is done when

- every form's required fields hold a value the client gave or you could
  infer (and said you inferred), or the open ones are in flight as one
  clarify / one `Q<n>:` block;
- the `deliver:` path is decided: the brief's, else the owning Group's
  `.agent/deliverables/<job>/`, else `~/Workspaces/.deliverables/<job>/`;
- a reference image, if any, has been copied under `deliver:`;
- metered forms carry a budget line;
- the sequence and its dependencies are written down for `build.md`.
