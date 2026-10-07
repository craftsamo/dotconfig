---
name: revise-creator
description: >-
  Translate feedback: turn the user's own words about a storyboard, draft,
  preview or delivery into located, named changes, each with a draft revision
  handoff. No score, verdict or unrequested critique.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [creator, revise, feedback]
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

# Revise - feedback into changes

## What arrives

The Assistant sends the artifacts (storyboard, draft, preview, delivery and the
hands' review sheets), the original intent and the user's feedback verbatim.
The feedback is the brief: do not add complaints of your own, and do not
reopen decisions the user did not question.

## Work

1. Read the subject's capability reference and the leaf's form, then the
   storyboard or proposal if one exists, so positions can be named by beat.
2. Look at the material: the hands' sheets first; `media_inspect` for a contact
   sheet or the frames at the times the feedback points to. At most three
   images per step; note what each look showed before the next.
3. Read `media-craft-direction`'s `references/critique-revision.md`, plus
   `media-craft-visual`, `media-craft-motion` or `media-craft-audio` for the
   medium involved, to connect the user's words to what is on screen or in the
   sound.
4. Turn the feedback into a few changes, each at a position: a storyboard beat,
   or a time and frame. For each, say what is seen there now and the named
   change, using vocabulary names, not adjectives. When the feedback can mean
   two different things, offer both as alternatives for the user to pick.
5. Mark any change that alters what a storyboard approval covered (beats,
   timing, copy, audio plan) as needing a new approval; a look-only change does
   not.
6. Write the draft revision handoff: `intent: revise <path>`, the changed
   fields and a `note` listing the changes by position.

## Reply

The changes in order of position, each with its alternatives where the
feedback was ambiguous, then the draft handoff and what the user must choose.
No score, verdict, ranking or comparison with other work; whether the result is
good enough is the user's call. Audio changes are expressed through form
fields and named techniques, never as something you heard.
