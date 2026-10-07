---
name: execute-assistant-creative
description: "Execute creative: commission the media hands directly with filled forms, consult Creator for open looks and vague feedback, relay proposals and approvals, and deliver candidates promptly with producer checks and caveats. Normal completions stay here, without a separate QA stage."
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    category: assistant-pipeline
    tags: ["execute", "creative"]
---

<ReadBeforeWork>

Re-evaluate the entry when the request, mode or domain changes, including within a turn.
Reuse full-body instructions only while present in the current context, not a past load or summary.
Check the kernel and common mode procedure independently. Load each whose full body is missing:

```text
skill_view(name="assistant-pipeline")
skill_view(name="assistant-pipeline", file_path="references/execute/index.md")
```

These dependencies also apply to direct entry. Loading does not restart an approved plan or expand a grant.
If a tool returns unchanged while the earlier body is unavailable, use read_file on `${HERMES_SKILL_DIR}/../SKILL.md` and `${HERMES_SKILL_DIR}/../references/execute/index.md`.
Recover this entry and its own references from ${HERMES_SKILL_DIR} likewise.
Follow next_offset until the whole required document is available; do not invent alternate paths or ranges to evade dedup.
If the required instructions remain missing, stop the affected action and report it, never infer a pass.
Read only applicable detail references below.

</ReadBeforeWork>

# Creative - commissioning the hands

You are the only client of the media hands: `image-creator`, `video-creator`
and `audio-creator`. You fill each leaf's form from the user's words and
decisions, send it, relay proposals and approvals, sequence dependent units and
deliver. The hands produce and self-check. Creator is your creative advisor: it
proposes directions and translates vague feedback, but never produces, sends a
handoff or approves anything. You produce nothing yourself, even when a leaf's
procedure is readable.

## Subject references

Read the selected subject's reference before filling or releasing its form,
and again before relaying one of its approvals. Read only the subjects this job
needs; a composite reads one per released unit.

| Hands | Subject references |
| --- | --- |
| image-creator | [card](references/card.md), [icon](references/icon.md), [emoji](references/emoji.md), [mascot](references/mascot.md), [reimagine](references/reimagine.md), [kit](references/kit.md), [diagram](references/diagram.md), [pixel-art](references/pixel-art.md) |
| video-creator | [clip](references/clip.md), [music-video](references/music-video.md), [ad](references/ad.md), [tour](references/tour.md), [explainer-video](references/explainer-video.md), [promotion](references/promotion.md), [master](references/master.md), [story](references/story.md) |
| audio-creator | [speech](references/speech.md), [sfx](references/sfx.md), [music](references/music.md), [mix](references/mix.md) |

## Choosing the leaf

Read the candidate leaf with `skill_view(name="<verb>-<subject>")`. Its
`description` says what it delivers, `metadata.hermes.hands` names the hands
and `form` says what it needs; read its form and option references, never run
its `<Procedure>`.

| The user has / wants | Verb |
| --- | --- |
| an existing file to change | `edit` |
| a look no library draws, or a subject no library has | `generate` |
| a symbol a published library already has | `source` |
| a deterministic composition or set from approved inputs | `create` |
| a judgment, not new media | `analyze` |

Use only an installed leaf for that verb and subject. A request no leaf fits is
`no skill fits` to the user, with the missing capability, and a note for the
maintainer; never improvise a leaf, fall back to an archived method or bend a
form field to carry an unsupported requirement. A composite is a sequence of
forms ordered by what feeds what: fill the first now and each dependent form
only once its input exists.

## Consulting Creator

Commission directly when the user's own words settle every required field.
Consult Creator first when a required field or the look is open, a reference or
analogy needs interpreting, or feedback on a storyboard, draft or delivery is
too vague to map onto a form. The look is open unless the user named it
concretely (a leaf style or option, a reference to match, colours, typefaces or
motifs); a mood given only as an adjective or two (「あたたかみのある感じで」,
"something modern") is open, so get directions from Creator and let the user
pick before commissioning:

- `specialist_call(target="creator", kind="inquiry")` for a bounded proposal or
  revision list; `kind="work"` when Creator must look at several media files or
  the exchange takes several turns.
- Send the settled intent (purpose, audience, destination, fixed words,
  exclusions, supplied inputs and what each is for) or the artifacts with the
  user's verbatim feedback. Never send a design of your own for it to fill in.
- Show the user Creator's directions or changes in plain language, with their
  examples. The user's pick is a human decision; record it separately from
  Creator's recommendation, then send the picked draft handoff after checking
  it against the leaf's form and this job's grants.

Creator's output is advice: it approves nothing, releases no spend and is not
a reviewer of a finished candidate.

## Filling the form

Infer before you ask: a colour named in passing, a pasted path or "transparent"
is an answer. Ask the user only what is truly open, in ordinary language; never
show them an internal form. A free-text answer goes into the field as written;
never add form keys.
Keep the original purpose, audience and must-keep conditions in every
dependent form.

- `deliver:` is the job's existing directory: the owning Group's
  `.agent/<YYYYMMDD>-<job>/` (or a job-owned subdirectory), else
  `~/Workspaces/.agent/<YYYYMMDD>-<job>/`. Never create a Group, relocate a valid
  Group-local job or overwrite an existing output.
- A metered leaf takes a `budget:` line from the user's actual grant or the
  leaf's documented default; the subject reference names any leaf that needs
  explicit current-work approval before spending. `cost: free` is not an
  unlimited attempt allowance; failed attempts count and resumes never restore
  them.
- An upload of a real person's photo or any asset to a model or remote analysis
  needs the user's explicit consent for that asset and operation, asked in the
  same round as the related choice. A path, a public URL, a direction choice or
  "use this" is not consent, and an omitted permission is unknown, not yes.
  Missing permission blocks the affected operation, not harmless local
  planning. Research examples are inspiration, never production inputs.
- Authored video gets intent only; the producer writes the storyboard. Never
  accept a silently flattened substitute for a required effect (a flat zoom for
  parallax, a fade for a material change, a generic control for designed UI);
  for an uncertain method, consult Creator with the requirement marked
  discussion-only.

## The handoff text

Use exactly this shape as the `message`; paths are absolute, Japanese values
are fine:

```text
skill: <verb>-<subject>
intent: new | revise <absolute path of the previous delivery>
deliver: <absolute durable directory>
budget: <grant>                      # provider calls or local speech takes; omit = leaf default
form:
  <field>: <value>                   # one line per filled field
```

## Transport

| Leaf | Transport |
| --- | --- |
| free, bounded, one reply (`source`, `create`, `edit`, `analyze`) | `specialist_call(target="<hands>", message=<the text>, kind="inquiry")` |
| metered, multi-turn, or longer than ~4 minutes | `specialist_call(target="<hands>", message=<the text>, kind="work")` |

These are defaults; the subject reference names free work that still needs
`kind="work"`. Transport grants nothing. Continue with the same `target` and
returned `conversation_id`; if an inquiry reveals metered or multi-turn work,
open a new `kind="work"` conversation instead of upgrading it. One conversation
per job per hands. Stop a turn that went wrong with `specialist_session(action=
"cancel")`; continue a confirmed `cancelled` conversation with the corrected form
(spend already made stays spent). Abandoned work follows
[resident-session supervision](../references/execute/resident-sessions.md);
never retry an unknown result or switch backends.

Independent units may run in parallel conversations; a dependent unit waits
for the report it consumes, and its form names the consumed path. Record each
consumed version in the job notes; a changed input invalidates only its
dependents' evidence.

## Supervising

- A report names the leaf, the paths, every QA check with its evidence and the
  spend line. A missing path or spend line is a defect to ask for, not assume.
- A hands `Q<n>:` the user can answer literally: ask the user in plain
  language, or answer from settled context. One that needs interpretation
  ("brighter" — which field?): get options from Creator first, then let the
  user choose. Never invent an approval or ask twice.
- A proposal, storyboard or preview is an approval stop. Show the actual
  returned material with a short explanation, then relay the user's decision in
  the same conversation, quoting the user's own words and the exact path and
  SHA-256 the hands returned. Never compute, refresh or invent a hash. A Budget
  line is not proposal approval, and proposal approval is not more spend. An
  approved study is not an approved final.
- Approvals and choices are the user's alone. When the user cannot be reached
  (a question tool fails, no reply arrives), stop and say in your reply what is
  waiting for them; never approve, pick a direction or answer a hands question
  on their behalf, and never read the original brief, a Budget line or
  "make it good" as approval.
- A one-line procedure note from the hands goes to the maintainer verbatim.

## Direct delivery

Stay in Execute on normal completion; do not load `qa-assistant-creative` or
ask Creator to review. Read the report for output kind, paths, required check
status, obvious conflicts with settled constraints and spend; request a missing
receipt or a scoped fix from the same producer, or report the blocker. Never
re-probe, repeat visual looks or spend the corrective allowance on your own
taste before showing work.

Deliver through [media-ops.md](references/media-ops.md): attach the actual
file when supported, or give an accessible viewing route. Show usable previews
promptly with failed and unknown checks disclosed, including unverified motion,
listening or taste. A required failure still blocks final readiness and
dependent use; never rename it PASS. Delivery is not the user's acceptance or
permission to continue. Close a conversation only after the user accepts its
result, not merely a proposal.

If the user rejects the overall direction, consult Creator on a different
reading of the reference and show a supported representative sample before full
production. For a time-based reference, the sample must show composition and
progression, not only a frame or an ending. An explicit request to inspect
routes to [requested inspection](../qa-assistant-creative/SKILL.md).
