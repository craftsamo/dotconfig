---
name: propose-creator
description: >-
  Propose creative directions: turn the Assistant's settled intent into 2-3
  named directions, each with an existing example and a draft hands handoff.
  No storyboard, design, production or spend.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [creator, propose, direction]
    category: creator-pipeline
---

<ReadBeforeWork>

Re-evaluate this entry on each inbound turn or completion and before a change
of entry, subject or scope. Reuse full-body instructions only while present in
current context. Before work, including direct entry, load the kernel if its
full body is missing:

```text
skill_view(name="creator-pipeline")
```

This entry is the complete procedure. Read only the selected subject
references and knowledge. If `skill_view` returns unchanged while a body is
unavailable, use `read_file` on `${HERMES_SKILL_DIR}/../SKILL.md` for the kernel,
`${HERMES_SKILL_DIR}/SKILL.md` for this entry or the selected reference under
`${HERMES_SKILL_DIR}/../references/`, following `next_offset`; if a required body
stays missing, stop and report it.

</ReadBeforeWork>

# Propose - intent into directions

## What arrives

The Assistant sends settled intent: purpose, audience, destination, fixed
words, exclusions, supplied inputs and what each is for, and sometimes
references or an analogy. Keep observed evidence, the user's decisions, your
suggestions and open questions apart. A research example is inspiration, never
a production input. If something required is missing and cannot be inferred,
return one `Q<n>:` block instead of guessing.

## Work

1. Pick the candidate subjects and read their capability references and leaf
   forms. A request that spans several units is a sequence; direct only the
   units whose look is open.
2. When a reference or analogy is involved, read `media-craft-direction`'s
   `references/reference-interpretation.md` (and
   `references/direction-constraints.md` for must-keep scope) and interpret it
   before proposing. Look at supplied media with `media_inspect` and vision.
3. Build 2-3 directions that genuinely differ in what the viewer sees, hears or
   feels — not three intensities of one idea. Each must be makeable by a served
   leaf within the stated constraints.
4. For each direction, find an example that already exists: a leaf's sample
   asset, an option reference, an earlier delivery the Assistant named, or a
   supplied reference. With none, name the leaf's representative sample unit
   (an anchor round, a single card, a short storyboard-approved draft) as the
   way to see it before full production.
5. Write the draft handoff for each: the leaf, real form fields only, the
   direction in existing fields (`style`, `theme`, `direction`, `what_for`) and
   `note`, with named techniques from the vocabulary rather than generic "fade"
   or "clean". For authored video, the direction names techniques and pacing in
   words; the producer writes the storyboard.

Do not propose research or several concepts for a request whose look is
already settled; say so and return the single handoff instead.

## Reply

For each direction: a short name, what the viewer sees in plain words, the
named techniques and where they come from, the example (path or sample unit),
and the draft handoff. Then the recommendation with one reason tied to the
purpose or audience, and what the user still has to decide. A direction is a
suggestion; nothing is approved or released until the Assistant relays the
user's choice.
