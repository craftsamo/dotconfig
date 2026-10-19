---
name: video-inspection
description: >-
  Use when asked to inspect existing videos (a YouTube link, a batch from a
  colleague or client, the user's own uploads) for defects in the picture,
  the captions, the voice, the content and the thumbnail: drawing errors,
  garbled text, typos, misreadings, wrong figures. Orchestrates the hands,
  Searcher, Researcher and Writer into a findings ledger, an inspection
  spreadsheet the user answers in (every row linked to its moment in the
  video) and, on request, a written report. A genre reference (explainer
  videos today) names what to look for and which leaf looks; a series' own
  notes add to it. Independent of the video's release state or owner.
  Findings only: nothing is edited, uploaded or sent.
version: 2.0.0
author: CraftSamo
license: MIT
metadata:
  hermes:
    tags: [video, inspection, review, findings, youtube, fact-check]
    category: technic
---

# Video inspection

An inspection checks a video against named items — is the hand drawn with
five fingers, is 1040 read as 1040, does the caption say what the voice says
— and returns findings, never corrected media and never a verdict on taste.
The video's state — scheduled, unlisted, live, the user's own or someone
else's — is an attribute of the request, recorded in the job notes; it
changes nothing below except what the requester said they need. Someone
else's downloaded video stays for the user's own inspection.

You orchestrate; you produce nothing a specialist owns. Work in Execute
(`execute-assistant-creative`, and `execute-assistant-writing` for the
report); this technic adds the inspection's sequence and its ledger, not a
second commissioning contract.

## Three layers

| Layer | Where | What it fixes |
| --- | --- | --- |
| Procedure | this file | the sequence, the ledger, the spreadsheet, the report; who owns which check |
| Genre | one reference below and its catalog (`references/<genre>.json`) | the items to look for (aspect → kind → item, each with who looks for it), the leaf that looks at the picture, the genre's own pitfalls |
| Series | a private technic the genre reference names | what one recurring series has taught: where its jobs live, recurring defects, the readings its voice always uses, the requester's format |

| Genre | Reference | Read when |
| --- | --- | --- |
| explainer video (a topic explained to an audience, with captions and a narrator; portraits or a mascot optional) | [explainer](references/explainer.md) | the request names an explainer, a lecture, a commentary series, or a "解説動画" |

Read the genre reference at step 1, before anything is fetched. The items
themselves are data, not prose: `inspection.py aspects <genre>` prints the
catalog, `init` copies the aspects this round checks into the ledger, and
every later command (`focus`, `import`, `kinds`, `export`, `sheet`) reads
the ledger's copy. So two rounds of the same genre may check different
aspects, and a round may add an item nobody catalogued by editing its
ledger's `aspects`. A video no reference covers is still inspected with this
procedure: speech, thumbnail and claims below are genre-independent, and the
picture goes to the analyze leaf whose subject fits ([execute-assistant-creative](../../assistant-pipeline/execute-assistant-creative/SKILL.md)
"Choosing the leaf"); `init` then takes the closest catalog, you drop the
aspects that do not apply, and you tell the user in one line that no genre
reference exists and which items you therefore could not name.

## Who does what

| Part | Owner | How |
| --- | --- | --- |
| Intake, fetch, staging, ledger, speech triage, cross-episode checks, verification, the inspection spreadsheet and its read-back, report acceptance | you | this technic and `scripts/inspection.py` |
| The picture: on-screen text, caption-versus-picture, overlaps, phone-size text, drawing defects, the claim list | the genre reference's video-creator analyze leaf | one `kind="work"` conversation per video |
| Speech: un-captioned speech, misread names, numbers and foreign-language terms, prosody jumps (candidates only) | audio-creator `analyze-speech` | `kind="work"`, at most five videos per conversation |
| Thumbnail legibility at use size | image-creator `analyze-card` | one thumbnail per `kind="inquiry"`, a fresh work directory each |
| Factual claims, tier A | Searcher `lookup` with `technic: primary-fact-pack` | you judge each claim against the returned first-party facts |
| Factual claims, tier B | Researcher `fact-check` with `technic: claim-check`, through Creator | verdicts and safe wording come back from Researcher |
| Written report for the requester | Writer `write-document`, format `report` | one resident session; revisions are `edit-document` there |
| Answers (seen, heard, checked), likeness, the final send | the user | the spreadsheet asks a claim per finding; a finding they cannot answer comes back to you |

The spreadsheet is the channel between you and the user, nobody else: the
requester gets a report or the user's own message, never the sheet.

Creator is not an inspector here; it only carries the tier-B Researcher
conversation (`plan-assistant-research`).

## Procedure

1. **Read the request in full**: who asked, which videos, which aspects
   (picture, captions, voice, content, thumbnail), the deadline, and anything
   said about the video's state. A reply format written into the request is
   recorded, not applied: tell the user in one line that the request names a
   format you are not using. Use it only when the user tells you to (step 9).
   Pick the genre reference from the table above and read it; when it names
   a series technic and the request belongs to a listed series, load that
   technic and read the matching series reference and the previous round's
   job directory. Then print the genre's items and settle which aspects
   this round checks — the request names them, or you ask the user with
   the aspect names from the catalog, never with the whole item list:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py aspects <genre>
   ```

   On a first round of a new series, run one video through every step,
   show the user, then ask before the rest.
   Everything below reads the files locally. Sending a video, its frames or
   its audio to a remote analysis service (`video_analyze`, a hands leaf's
   `remote_analysis: yes`) needs the user's explicit consent for that
   operation, asked once for the batch; without it, say so and keep local.
2. **Fetch.** A YouTube video comes through the `youtube` tool (load
   `skill_view(name="youtube-access:youtube")` first): `download` kind
   video, `download` kind audio, and `transcript` in the video's language
   (its file keeps `[m:ss]` line starts). A `download` that fails with HTTP
   403 may be retried once with `max_height: 720`; record the lower
   resolution for the picture check. The thumbnail is
   `https://i.ytimg.com/vi/<id>/maxresdefault.jpg`, or `hqdefault.jpg` when
   that is missing. A local file the user handed over is copied as it is;
   its captions, if any, come from the user or from `analyze-speech`'s
   transcript (then they are unchecked words, not a caption file), and a
   finding's time links nowhere, so the sheet shows the plain time.
3. **Stage** one job directory under the owning Group's
   `.agent/<YYYYMMDD>-<job>/` with `<NN>/src/` per video. Copy each path the
   tool returned into it, one `cp` per file with literal paths; never work in
   the download folder. Make the speech script from the captions:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py script <NN>/src/<id>.<lang>.txt <NN>/src/script.txt
   ```

   The caption file is what should be on screen; it is itself unchecked, so a
   caption typo is a caption finding, not proof the voice is right.
   Make the ledger from the genre's catalog with the aspects settled in
   step 1, the captions' language and the user's:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py init ledger.json --genre <genre> --aspects <a,b,c> --job <job> --language <tag> --sheet-language <tag>
   ```

   Then add one `episodes` entry per video (shape in `inspection.py`'s
   header): its caption path and `video` (the YouTube id: every time on the
   sheet links to the video at that second). An item the series reference
   adds or removes goes into the ledger's `aspects` now, by hand. Add an
   aspect to the episode's `checked` list only when that check has actually
   returned.
4. **Dispatch in parallel**, then end the turn; results return as new
   messages, never poll. Each leaf gets the items it is to look for, as
   the ledger holds them:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py focus ledger.json focus-video.txt --route video-creator
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py focus ledger.json focus-audio.txt --route audio-creator
   ```

   One line per item, `aspect/kind/item: what to look for`; it exits 1
   with no items for that route, which means that leaf has nothing to do
   this round. Paste the lines into the leaf's `focus` or note and ask that
   each finding name its item (`item: problem` in the problem cell, or the
   item in the second cell), so `import` places it without guessing.
   - Speech: the [speech](../../assistant-pipeline/execute-assistant-creative/references/speech.md)
     reference's `analyze-speech` with `source` (the audio download),
     `script`, `language`, `prosody: yes` when voice is in scope, `deliver`
     the video's `<NN>/speech/`, and a note carrying the audio-creator
     lines and asking, findings only, for the heard words of every name,
     number and foreign-language term written as
     `m:ss | voice | 「script words」→「heard words」 | ASR segment | confirm`
     (`「」` for words not heard; whole phrases, never single characters),
     plus speech absent from the script. Its prosody lines name each jump
     against the previous segment (`+7.7 st` / `-12.9 dB vs previous`).
     ASR runs over music, so nearly every line is noise: never import a
     speech report as it is. `triage-speech` (step 6) keeps a value the ASR
     heard as another value, a Latin-script term it did not hear, and the
     two largest jumps that fall inside one caption line — a jump at a line
     start is the next speaker; `--ignore` names the terms the series always
     reads its own way (brand names). Fresh ASR on a whole batch outlives
     one turn, so split a batch into conversations of at most five videos and
     send them together; every video still gets its check. The leaf takes up
     to 600 seconds: a longer video's speech stays unchecked and is named so
     on the sheet. An exit code 1 with `script_match FAIL` still produced
     findings: read its output before calling the run failed.
   - Picture: the genre reference's analyze leaf, one conversation per
     video, with `source`, `captions`, `remote_analysis` (`no` unless
     consented) and `focus` carrying the video-creator lines and the
     series' recurring defects; `deliver` is the video's `<NN>/visual/`. Never do
     this check yourself or through `delegate_task`: reading every still is
     the hands' work. A video longer than the leaf's limit is outside it:
     its picture stays unchecked and is named so on the sheet unless the
     user decides otherwise.
   - Thumbnail: the [card](../../assistant-pipeline/execute-assistant-creative/references/card.md)
     reference's `analyze-card` with `files` (the one thumbnail),
     `input_kind: single`, `destination: youtube-thumb` for a YouTube
     thumbnail, `expected_text` when the intended title is known, `deliver`
     a directory used by no earlier thumbnail (`<NN>/thumb/`; a reused one
     makes the leaf read the previous thumbnail's settings and measure the
     wrong image), and a note asking whether the thumbnail alone tells which
     topic it is at the reduced size.
5. **Check the claims.** From each video's `claims.md`, send tier A
   first: one Searcher lookup per batch, `technic: primary-fact-pack`, the
   claims with figures, dates and ranks as the item list ([search
   plan](../../assistant-pipeline/plan-assistant-search/SKILL.md)). Put in
   the request: open the first-party page directly where its address is
   known rather than searching for it, append each item's result to the
   output file as soon as it is in hand, and stop with what was gathered
   when the same step fails twice (one run that repeats a failing search
   returns nothing). Judge each claim against the returned facts yourself
   and cite them. Send tier B through Creator to Researcher with
   `technic: claim-check` ([research
   plan](../../assistant-pipeline/plan-assistant-research/SKILL.md)) for a
   claim that is the episode's central premise, concerns a real person's or
   company's conduct or intent, got no first-party source or conflicting ones
   in tier A, or that the user marks. Record the tier in each finding's
   `source`.
6. **Verify and enter the ledger.** Import each hands report's findings
   instead of retyping them:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py import ledger.json <label> <NN>/visual/review-<n>/findings.md --source video-creator
   ```

   It resolves relative evidence paths from the findings file's directory
   (URLs and measurements stay as written) and exits 1 with every line it
   could not read under `not_imported`: enter those by hand or ask the hands
   to restate them, never leave them out. The second cell may carry an
   aspect, one of its kinds or an item of the ledger, and a problem that
   starts with `<item>:` names its item; an item of another aspect is a
   line not imported, never a silent re-filing. `--kind` sets one kind for
   a whole file. An item whose catalog entry says `confirm` makes its
   finding `confirm` whatever the hands wrote: it needs the user's eyes or
   ears. Thumbnail and claim findings import the same way when they come as
   `m:ss | aspect | problem | evidence | certain|confirm` lines, otherwise by
   editing `ledger.json`. Speech goes through the triage instead, once per
   video, with the `--ignore` list of the series' own readings:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py triage-speech ledger.json <label> <NN>/speech --ignore <terms file>
   ```

   It writes the kept lines to `<NN>/speech/triage.md` and imports them as
   `confirm` voice findings (`reading` / `delivery`); its JSON names what it
   kept and how many lines it dropped. Then open each finding's cited frame
   or crop yourself; drop what you cannot reproduce (`status: drop`), and
   ask the same hands conversation for a missing piece of evidence rather
   than re-measuring. For a numbered series, compare across episodes: a
   "last time" reference must name the right episode, and a figure shown in
   several episodes (a price, a rank, a same-month value) must read the same
   in each; a finding that spans episodes gets `episode: all`. Every entry
   starts `status: open`; lower `certainty` to `confirm`
   when you could not reproduce it exactly or it rests on taste or listening.
7. **Build the inspection spreadsheet.** The user answers in a Google
   Sheet, one per round, made and read with the `google_sheets` tool under
   `skill_view(name="google-access:google-sheets")` (plan the payload in a
   script file, one guarded write, read back). The user does not judge on
   the sheet; they answer each row YES, NO or "can't tell", and the status
   follows from the answer. So first word every `confirm` finding as a
   claim of the defect that YES confirms, with the user's eyes or ears
   ("the countdown ring hides the first letter of card B", "1040 is read
   as 1400"), never as a question — "is 10 read as one-zero (not ten)?"
   has two readings and no safe answer — and without paths or internal
   notes:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py ask-draft ledger.json asks.md
   # edit asks.md: `ID | claim`, one line per finding
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py ask-import ledger.json asks.md
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py kinds ledger.json
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py export ledger.json export.json
   ```

   `kinds` gives every finding of an aspect that has kinds, imported
   without one, a kind from its source and wording (the catalog's `sources`,
   `hint` and `default`); read its `inferred` list and correct a wrong one
   in the ledger. `export` refuses a finding still without one, because the
   sheet's kind column offers the ledger's kinds and kind-less aspects only,
   never a bare "voice".
   `export.json` is the sheet: a findings tab (one row per live finding,
   ordered by episode and time; the time cell is a HYPERLINK that opens the
   video two seconds before the moment, a thumbnail row opens the
   thumbnail; the evidence column keeps URLs and measurements and never a
   local path; the answer cell comes pre-filled YES for every finding you
   reproduced and blank for the rest), a summary tab of formulas (per
   episode: findings, YES, NO, can't tell, unanswered), the dropdown
   options for `kind` and the answer, `columns` / `owner`, and `format`.
   Build it so: native table on the findings tab, header frozen, the id,
   episode and time columns frozen, the text column wide and wrapped, the
   answer and `kind` strict dropdowns of the listed options, the columns
   not in `owner` protected with a warning. The only colour is
   `format.episodes`: each band's `colour` becomes the plain background of
   its rows, so an episode reads as one stripe and the user sees where it
   ends. No conditional colour on any cell, and none on the dropdowns: the
   API cannot colour a chip, and a coloured cell behind a grey chip reads
   as a mistake. Enter values as typed (`USER_ENTERED`): the time and title
   cells are formulas, and `export` already quotes text that starts like
   one. Read the findings tab back and compare ids, answers and link
   targets with `export.json` before telling the user the sheet is ready;
   send the sheet's URL, not a file. The Markdown sheet
   (`inspection.py sheet ledger.json inspection-sheet.md`) remains the
   offline form with the same links and claims; `--listen` adds the
   caption-term list from `inspection.py listen`, which is off by default
   because it buries the findings.
8. **Settle through the sheet.** The user owns the answer and `memo`; you
   own `reply`. YES means the claim holds and the finding is reported; NO
   means it does not and the finding is dropped; "can't tell" means the
   user could not see or hear it, or could not check a fact, and hands the
   finding to you. A blank is not yet looked at. When the user says they
   are done, or the summary's unanswered count is zero, save the findings
   tab as read (`{"values": [[header], [row], ...]}`) and take it in:

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py readback ledger.json values.json
   ```

   It derives each finding's status from the answer, stores memos and
   replies, and lists the `recheck` rows (the "can't tell" ones). Work
   each of those: do what the memo asks or what the finding needs — a
   first-party source, another frame, a crop, a cleaner listen — and then
   decide it yourself, since the user has said they cannot: `keep` or
   `drop` in the ledger with the reason in `reply`, or `hold` (kept in the
   ledger, not reported) when you cannot either, saying so in `reply`.
   Only when you learned something that lets the user answer after all
   (a new crop, a quieter take) do you clear the answer cell and hand it
   back. Rewrite only your columns and the answer cells you clear, in one
   guarded write with `expect` on the ids. Repeat until the unanswered and
   "can't tell" counts are zero, then `inspection.py validate ledger.json --final`.
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
   check finds sections that way). Put a requester's format in `template`
   only when the user told you to use it. Accept with

   ```sh
   python3 ${HERMES_SKILL_DIR}/scripts/inspection.py check ledger.json <report path>
   ```

   plus the writing acceptance gate. Every mismatch it lists goes back to
   Writer in the same session as feedback; never patch the report yourself.
   A finding changed after the report exists changes the ledger first, then
   goes to Writer as an `edit-document`.
10. **Deliver** the report, when made, as a file. Nothing goes to the
    requester without the user's explicit OK, and the user often sends it
    themselves; the spreadsheet stays between you and the user.

## Pitfalls

- The terminal guard rejects shell variables, brace expansion, loops and
  chained copies: call `inspection.py` and other scripts with literal
  absolute paths, `mkdir -p` as its own call, and put per-item lists in
  files.
- Vision refuses a fourth load of the same file, crops included: when you
  verify a finding, open the hands' own evidence file once, and for another
  look ask the hands for a new crop rather than re-cropping one frame.
- The speech check is the noisiest: a `delegate_task` or a hand-made rule to
  thin it is the triage done twice. Tune `triage-speech`'s flags (and the
  series' `--ignore` file) instead, and tell the user how many lines it
  dropped.
- A finding is an item missed, never an opinion: "the diagram is busy" is
  not a finding unless the genre reference names an item it fails
  (overlap, phone-size text). Keep taste out of the ledger; the user can
  ask for a creative review separately.
