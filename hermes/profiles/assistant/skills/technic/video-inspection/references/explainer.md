# Explainer video

Read [the procedure](../SKILL.md) first. This reference adds what an
explainer video — a topic explained to an audience by a narrator, with
captions, diagrams, figures and sometimes a mascot or portraits of real
people — asks you to look for, and which leaf looks.

## Items

An inspection names its items before anyone looks; a finding is one item
failed at one moment. The aspects and kinds below are the ones the ledger,
`inspection.py kinds` and the sheet know; the items under each are what the
`focus` of the picture leaf, the note to the speech leaf and your own
verification name. Pick the aspects the request asks for; within an aspect,
every item is in scope unless the request or the series reference removes
it.

| Aspect | Kind | Items (what a finding says) |
| --- | --- | --- |
| text (on-screen text and captions) | typo | a misspelt or mis-converted word on screen; a caption word that differs from the script's meaning (誤変換); notation that differs between episodes for the same term |
| text | overlap | an element that hides information: a caption over a figure's label, a countdown ring over a card's first letter, a lower third over a chart axis; text cut off at the frame edge; text too small to read at phone width (the leaf measures pixel rows) |
| voice | reading | a name, number, unit or foreign-language term read as another value or word (1040 as 1400, a kanji numeral read on-yomi where the script is kun-yomi); an accent that changes the word |
| voice | delivery | a pitch or level jump inside one caption line; speech the captions do not carry; a passage buried under music |
| content | figure | a diagram, counter or animated number whose value, direction or order does not match the caption or the voice; a frame of a drawn figure with the wrong limb count, merged objects, pseudo-text (letter-like marks that spell nothing) or a logo with the wrong letters |
| content | fact | a claim with a figure, date, rank or attribution that first-party sources (tier A) or Researcher (tier B) do not support |
| content | clarity | a step the explanation skips so the next one cannot be followed; a term used before it is defined; a "last time" reference that names the wrong episode |
| thumbnail | — | at the reduced size (168 px) the thumbnail does not tell which topic it is; its text is not legible; its text differs from the intended title |
| portrait | — | a drawn portrait of a real person with a drawing defect (as under figure); likeness itself is the user's call (procedure step 8) |

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
- `focus`: the text, overlap, figure and portrait items in scope from the
  table above, in the leaf's own words, plus the series' recurring defects
  and a portrait drawing check when portraits are in scope
- `note`: the series' deliberate gags, so they are listed, not flagged

It returns `findings.md` (`m:ss | text|content|portrait | problem | evidence
path | certain|confirm`) and `claims.md` (`m:ss | caption|screen | verbatim
claim`) under `<deliver>/review-<n>/`; `inspection.py import` reads the
first as it is, and step 5 of the procedure takes the claims. The leaf
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
