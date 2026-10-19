# Explainer video

Read [the procedure](../SKILL.md) first. This reference adds what an
explainer video — a topic explained to an audience by a narrator, with
captions, diagrams, figures and sometimes a mascot or portraits of real
people — asks you to look for, and which leaf looks.

## Items

An inspection names its items before anyone looks; a finding is one item
failed at one moment. The catalog is `explainer.json` beside this file —
read it with `inspection.py aspects explainer`, never by hand — and it
holds five aspects:

| Aspect | Kinds | Who looks | What the items cover |
| --- | --- | --- | --- |
| text (on-screen text and captions) | mismatch, overlap, typo | video-creator | caption against voice and picture, timing; hidden, cut-off and phone-size text; misspellings, 誤変換, 表記ゆれ |
| voice | delivery, reading | audio-creator | jumps, uncaptioned speech, buried or rushed lines; numbers, names, foreign terms and kanji read wrongly |
| content | fact, figure, clarity | video-creator; `fact` goes to Searcher and Researcher | figures and counters against the captions, drawn hands, limbs, merged objects, pseudo-text, glitches; unsupported claims; skipped steps, undefined terms, wrong "last time" references |
| thumbnail | — | image-creator | topic, legibility and title at the reduced size |
| portrait | — | video-creator; `likeness` is the user's | drawing defects of a real person's portrait; likeness itself is the user's call (procedure step 8) |

Pick the aspects the request asks for at `init`; within an aspect, every
item is in scope unless the request or the series overlay removes it from
the ledger's copy. The catalog marks the items that need the user's ears
or eyes `confirm`; the script keeps such findings from ever being certain.

A mascot's deliberately wrong line — a running gag the series writes on
purpose — is not a content defect; the series reference lists them, and the
thumbnail note says so.

## The picture leaf

The picture goes to video-creator's `analyze-explainer-video`
([commissioning reference](../../../assistant-pipeline/execute-assistant-creative/references/explainer-video.md)),
one `specialist_call(kind="work")` conversation per video, `deliver` the
video's `<NN>/visual/`. It sees the picture and the caption file only:

- `source`: the local video, at most 600 seconds — a longer one is refused,
  its picture stays unchecked and the sheet says so unless the user decides
  otherwise (a cut is the user's decision, never yours)
- `captions`: the `[m:ss] text` file from the fetch
- `remote_analysis`: `no` unless the user consented for this batch
- `focus`: the `inspection.py focus … --route video-creator` lines (the
  text, figure and portrait items in the ledger), plus the series'
  recurring defects
- `note`: the series' deliberate gags, so they are listed, not flagged, and
  the ask that each finding name its item

It returns `findings.md` (`m:ss | text|content|portrait | item: problem |
evidence path | certain|confirm`) and `claims.md` (`m:ss | caption|screen |
verbatim claim`) under `<deliver>/review-<n>/`; `inspection.py import`
reads the first as it is, and step 5 of the procedure takes the claims. The leaf
measures text heights and lists portrait defects; it never says whether a
portrait looks like a real person, and it never reviews the thumbnail.

## Speech

Nothing beyond the procedure, except the `--ignore` file for
`triage-speech`: an explainer series reads its brand names, product names
and recurring foreign terms its own way every episode, so list them once in
the series reference and pass the file every round. Without it the triage
keeps every episode's "ChatGPT" as a reading finding.

## Series

A recurring series gets a series technic on the private shelf:
`skill_view(name="explainer-series-notes")` (absent on a machine without
it). Load it at step 1 when the request belongs to a listed series, read
only the matching series reference, and open the previous round's job
directory for the readings and gags it recorded. The series reference owns:
where the series' jobs live, the defects that keep recurring (they go into
`focus`), the `--ignore` terms, the deliberate gags, and the requester's
reply format (recorded, applied only on the user's instruction).

Across the episodes of one round, and against earlier rounds: a figure
shown in several episodes (a price, a rank, a same-month value) must read
the same in each, and a "last time" reference must name the right episode.
Those are `content` findings with `episode: all` when they span episodes.

A new series' first round runs one video through every step, shows the
user, and asks before the rest; what that round taught is proposed to the
user for the maintainer as a new series reference, never written into a
learned skill.

## Pitfalls

- A remote video analysis (`remote_analysis: yes`) has returned wrong
  counts, missing times and truncated drafts on short explainer videos; when
  a series' notes say it adds nothing, do not ask for consent and do not
  send one, and never let its reading override the frames.
- Captions are the explainer's spine: the leaf compares picture against
  captions and the triage compares voice against captions, so a video whose
  captions were not fetched loses both comparisons. Fetch the transcript
  before anything else, and say on the sheet when it was auto-generated.
