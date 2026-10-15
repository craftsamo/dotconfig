---
name: explainer-video-review
description: >-
  Use when asked to review existing explainer videos (a YouTube link, a batch
  from a colleague or client, the user's own uploads) for on-screen text,
  voice, content accuracy, thumbnail and portrait defects. Orchestrates the
  hands, Searcher, Researcher and Writer into a findings ledger, a review sheet
  for the user and, on request, a written report. Independent of the video's
  release state or owner. Findings only: nothing is edited, uploaded or sent.
version: 1.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [video, explainer, review, findings, youtube, fact-check]
    category: technic
---

# Explainer video review

A review returns findings, never corrected media. The video's state —
scheduled, unlisted, live, the user's own or someone else's — is an attribute
of the request, recorded in the job notes; it changes nothing below except
what the requester said they need. Someone else's downloaded video stays for
the user's own review.

You orchestrate; you produce nothing a specialist owns. Work in Execute
(`execute-assistant-creative`, and `execute-assistant-writing` for the
report); this technic adds the review's sequence and its ledger, not a
second commissioning contract.

## Who does what

| Part | Owner | How |
| --- | --- | --- |
| Intake, fetch, staging, ledger, cross-episode checks, verification, review sheet, report acceptance | you | this technic and `scripts/review.py` |
| On-screen text, picture, caption-vs-voice, portrait drawing defects | picture check (below) | one video per unit |
| Speech: un-captioned speech, misread names, numbers and foreign-language terms | audio-creator `analyze-speech` | `kind="work"`, at most five videos per conversation |
| Thumbnail legibility at use size | image-creator `analyze-card` | one thumbnail per `kind="inquiry"`, `destination: youtube-thumb` |
| Factual claims, tier A | Searcher `lookup` with `technic: primary-fact-pack` | you judge each claim against the returned first-party facts |
| Factual claims, tier B | Researcher `fact-check` with `technic: claim-check`, through Creator | verdicts and safe wording come back from Researcher |
| Written report for the requester | Writer `write-document`, format `report` | one resident session; revisions are `edit-document` there |
| Listening, likeness, the final send | the user | the review sheet asks; you never decide these |

Creator is not a reviewer here; it only carries the tier-B Researcher
conversation (`plan-assistant-research`).

## Procedure

1. **Read the request in full**: who asked, which videos, which aspects
   (text, voice, content, thumbnail, portrait), the deadline, and anything
   said about the video's state. A reply format written into the request is
   recorded, not applied: tell the user in one line that the request names a
   format you are not using. Use it only when the user tells you to (step 9).
   For a series, load `skill_view(name="explainer-series-notes")` (the
   private shelf; absent on a machine without it) and read the matching
   series reference and the previous round's job directory first. On a
   first round of a new series, run one video through every step, show the
   user, then ask before the rest.
   Everything below reads the files locally. Sending a video, its frames or
   its audio to a remote analysis service (`video_analyze`, a hands leaf's
   `remote_analysis: yes`) needs the user's explicit consent for that
   operation, asked once for the batch; without it, say so and keep local.
2. **Fetch** with the `youtube` tool (load
   `skill_view(name="youtube-access:youtube")` first): `download` kind video,
   `download` kind audio, and `transcript` in the video's language (its file
   keeps `[m:ss]` line starts). A `download` that fails with HTTP 403 may be
   retried once with `max_height: 720`; record the lower resolution for the
   picture check. The thumbnail is
   `https://i.ytimg.com/vi/<id>/maxresdefault.jpg`, or `hqdefault.jpg` when
   that is missing.
3. **Stage** one job directory under the owning Group's
   `.agent/<YYYYMMDD>-<job>/` with `<NN>/src/` per video. Copy each path the
   tool returned into it, one `cp` per file with literal paths; never work in
   the download folder. Make the speech script from the captions and, for the
   picture check, the stills, before dispatching:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/review.py script <NN>/src/<id>.<lang>.txt <NN>/src/script.txt
   python3 ${HERMES_SKILL_DIR}/scripts/review.py frames <NN>/src/<id>.mp4 <NN>/visual/f
   ```

   The caption file is what should be on screen; it is itself unchecked, so a
   caption typo is a text finding, not proof the voice is right.
   Create `ledger.json` (shape in `review.py`'s header) with one `episodes`
   entry per video, its caption path included, `language` set to the
   captions' language and `sheet_language` to the user's. Add an aspect to
   the episode's `checked` list only when that check has actually returned.
4. **Dispatch in parallel**, then end the turn; results return as new
   messages, never poll.
   - Speech: the [speech](../../assistant-pipeline/execute-assistant-creative/references/speech.md)
     reference's `analyze-speech` with `source` (the audio download),
     `script`, `language` and a note asking for speech absent from the script
     and for the heard words of every name, number and foreign-language term, findings
     only. Fresh ASR on a whole batch outlives one turn, so split a batch into
     conversations of at most five videos and send them together; every video
     still gets its check. The leaf takes up to 600 seconds: a longer video's
     speech stays unchecked and is named so on the sheet. An exit code 1 with
     `script_match FAIL` still produced findings: read its output before
     calling the run failed. ASR runs over music, so its output is candidates.
   - Picture: one `delegate_task` child per video, never two, with the brief
     in a file it reads and the stills already extracted. It looks at no more
     than two images at once, writes `visual/findings.md` early and appends.
     Checks: typos and missing glyphs, caption-vs-voice mismatch, text hidden
     by an overlap, text too small for a phone (measured height), off-screen
     text, and portrait drawing defects (name, title, year, a broken figure)
     — never likeness. A label sitting on a character while every word stays
     legible is staging, not a finding; keep an overlap only when it hides
     text, a chart point or part of a figure. Re-sample a moving counter or
     highlight at 0.3 s before calling it a mismatch. A flat-coloured limb
     over same-coloured clothing is hidden, not missing. Each line is
     `m:ss | aspect | problem | evidence | certain/confirm`, and the child
     also lists every factual claim on screen or in the captions verbatim.
     Its findings enter the ledger with `source: assistant`: the child is
     yours, not a hands verdict.
   - Thumbnail: the [card](../../assistant-pipeline/execute-assistant-creative/references/card.md)
     reference's `analyze-card` with `files` (the one thumbnail),
     `input_kind: single`, `destination: youtube-thumb`, `expected_text` when
     the intended title is known, and a note asking whether the thumbnail
     alone tells which topic it is at the reduced size.
5. **Check the claims.** From the picture check's claim list, send tier A
   first: one Searcher lookup per batch, `technic: primary-fact-pack`, the
   claims with figures, dates and ranks as the item list ([search
   plan](../../assistant-pipeline/plan-assistant-search/SKILL.md)). Judge each
   claim against the returned facts yourself and cite them. Send tier B
   through Creator to Researcher with `technic: claim-check` ([research
   plan](../../assistant-pipeline/plan-assistant-research/SKILL.md)) for a
   claim that is the episode's central premise, concerns a real person's or
   company's conduct or intent, got no first-party source or conflicting ones
   in tier A, or that the user marks. Record the tier in each finding's
   `source`.
6. **Verify and enter the ledger.** Before a finding enters `ledger.json`,
   open its cited frame or timestamp yourself; drop what you cannot
   reproduce. For a numbered series, compare across episodes: a "last time"
   reference must name the right episode, and a figure shown in several
   episodes (a price, a rank, a same-month value) must read the same in each.
   Every entry starts `status: open`; `certainty: certain` only when you
   reproduced it and no taste or listening is involved.
7. **Build the review sheet** for the user and send it as a file:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/review.py listen ledger.json
   python3 ${HERMES_SKILL_DIR}/scripts/review.py sheet ledger.json review-sheet.md
   ```

   `listen` adds the names, numbers and foreign-language terms of each
   caption line at that line's own start time, found by the rules for the
   captions' `language`; a language without its own rules yields numbers and
   capitalised words only, so pass its names with `--terms`; prune obvious noise with `--terms` or by
   editing the `listen` list, never by retyping times. The sheet separates
   certain findings from those that need the user's eyes or ears. Never write
   "no problem" for anything not judged: an unchecked aspect is named as
   unchecked.
8. **Settle with the user.** Record each answer in the ledger (`source:
   user`, the listen item's `result`), set every finding `keep` or `drop`,
   rebuild the sheet, and run `review.py validate ledger.json --final`.
   Likeness is the user's call: when asked to prepare it, have Searcher
   locate the reference photos (the photographer or source credited in the
   video description), put each portrait frame beside its photo in one local
   sheet, say which pairs are weak matches, and leave the verdict to the user.
   If they waive it, use their wording.
9. **Report, only when the user asks for one.** Release a Writer
   `write-document` unit through
   [writing execution](../../assistant-pipeline/execute-assistant-writing/SKILL.md):
   format `report`; reader the requester; purpose what the requester must
   decide or fix; sources the ledger path; `must_keep` every kept finding's
   time, quotes, figures and certainty, and the counts; `avoid` adding,
   dropping, merging away or strengthening any finding; `note` that each
   episode's findings sit under a line that begins with its label (the
   check finds sections that way). Put a requester's
   format in `template` only when the user told you to use it. Accept with

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/review.py check ledger.json <report path>
   ```

   plus the writing acceptance gate. Every mismatch it lists goes back to
   Writer in the same session as feedback; never patch the report yourself.
   A finding changed after the report exists changes the ledger first, then
   goes to Writer as an `edit-document`.
10. **Deliver** the review sheet and, when made, the report as files. Nothing
    goes to the requester without the user's explicit OK, and the user often
    sends it themselves.

## Pitfalls

- The terminal guard rejects shell variables, brace expansion, loops and
  chained copies: call `review.py` and other scripts with literal absolute
  paths, `mkdir -p` as its own call, and put per-item lists in files.
- Vision refuses a fourth load of the same file, crops included: render each
  re-check as a new file instead of re-cropping one frame.
- Measure text height by pixel row projection in a script, not by asking the
  vision model for sizes.
- Put contact-sheet time labels bottom-right: top-left hides header tabs that
  are themselves checked.
