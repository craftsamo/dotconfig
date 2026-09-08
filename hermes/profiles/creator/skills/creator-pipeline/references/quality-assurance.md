# Quality assurance — your eyes, against the client's intent

The hands verified against the leaf's `<QA>` (dimensions, alpha, cut-out,
style cues) and said so with evidence. You verify the one thing they
cannot: **is this what the client meant.** Nothing is re-measured here;
nothing is re-done here.

## Speech deliveries — read the evidence, do not relisten

A speech delivery is never opened with vision; there is no frame to look
at. Read the hands' report against the approved script and the client's
goal: does the readback text match the script, does the take count and
any WARN line still fit what was asked. Never re-run ASR yourself just
to re-score something the hands already measured — that is spending a
fresh take against their tally, not a review. A reproduced seed is
decoded-PCM-hash evidence, not container-byte equality; take the hands'
comparison as given rather than redoing it. Retain every WARN in your
reply exactly as the hands reported it — a WARN is not a defect to
silently drop. The gap between "measured and read back" and "heard"
stays explicit in the verdict: whether that perceptual gap is acceptable
is the client's decision, not yours to resolve by claiming to have
listened.

## Look before you answer (visual deliveries)

The numbered steps below are for a **visual** file; a speech delivery is
reviewed under "Speech deliveries" above.

For clips, use the hands' sampled sheet and a native frame instead of
passing an MP4 to image vision. Read its timecoded video-analysis findings
against the requested motion and client intent. A poster cannot establish
motion, continuity, audio or loop quality. If remote analysis was declined
or failed, carry the temporal QA gap through; acceptance as an unverified
candidate is the client's decision, not an implicit pass. Do not upload
again just to repeat the hands' check. An analyze-clip report is findings,
not a new deliverable: review the evidence and return it without requiring
an output video or opening a new generation job.
For a deterministic clip edit, helper dimensions/duration/decode results
and the bounded framing looks are the checks. Do not expand sampled QA
into pixel-exact source alignment/padding calculations or ask the hands
to run extra approval-gated scripts. Carry unverified checks explicitly.

For generate-music-video, an awaiting-approval proposal is text to review, not missing
video. After generation use the clip review path above, comparing the hands'
timecoded findings to the APPROVED progression, identity and expanded theme.
Cuts are allowed, not mandatory: performance may be continuous, while montage
expects shot changes. Judge the approved direction, not a minimum cut count.
Read the approved pace/transition together: snappy means crisp motion/shorter
holds, not necessarily cuts; continuous forbids shot breaks. Check the hands'
timecoded evidence for long idle/final holds, dissolve ghosts where cut was
asked for, unreadably fast transitions or overlapping successive words when
forbidden. Samples cannot certify speed or cut cadence. A requested tempo
change goes back to proposal approval, never an unapproved corrective or a
global speedup. Do not apply new defaults to an old approved proposal.
Check that defaults did
not override client colors/materials and that the subject actually performs.
Native generated audio must exist in generated mode; model analysis is not
human listening evidence or exact beat/lyric/lip-sync proof. A silent supplied-
music master or a text-free base with deferred lettering is needs finishing,
not a completed MV. Offer acceptance, an in-grant corrective for a specific
defect, a separately released supported edit, or re-planning. A new creative
choice needs renewed proposal approval; no silent fixes or new generation
merely because remote analysis failed.
The client may explicitly accept disclosed temporal/audio QA gaps and close
the job; preserve UNVERIFIED in the report instead of relabeling it PASS.
This does not waive a mandatory finishing requirement without a new decision.

For reference-led spatial actions, read each critical event's START / CROSS /
AFTER evidence and opening/subject shape verdict separately. "The keyhole is
visible" is not "the camera passed through it"; a fade to an interior does not
meet an approved continuous crossing. A correct actor, world and words do not
outweigh a failed critical passage. Do not reuse an isolated-shot success as
evidence for its integrated version. Carry sampled/unknown status honestly;
propose a separately released isolation or revised scope, never automatic
extra shot generation, unapproved montage assembly or unsupported completion %.

1. Open the recommended file (or every delivered file when there is no
   recommendation) with vision at native size.
2. Open it again at the size the client will use — a Slack sidebar icon
   at 64 px, a favicon at 16 px — by resizing to a scratch copy under
   `deliver:` or `/tmp`. Write the verdict down before the next look;
   vision holds about three images.
3. Read the hands' QA lines: a `FAIL` or `WARN` they delivered anyway is
   yours to weigh against the intent, not to ignore.
4. With a reference image in the form, look at reference and delivery
   side by side once: carried over, not copied.

## The verdict

- **Accept** — it is what was asked, at the size it will be used.
- **Revise** — one `intent: revise <deliver dir>` handoff with the form
  field that changes and nothing else changed (`build.md`). Name the
  defect the way you saw it ("the tail reads as a chip at 64 px"), not as
  an instruction to the model. A revise on a metered leaf costs the
  leaf's corrective; a second revise round is the client's call, with
  the cost stated.
- **Back to Plan** — the form was wrong, not the render (the wrong verb,
  a field the client meant differently): re-fill with the client, then a
  fresh `intent: new`.

Never "fix it yourself": a local edit on the hands' file is a different
deliverable wearing its filename. An `edit-icon` handoff is the way to
change a file.

## Delivery to the client

Reply in the client's language, short:

- the paths (absolute), one sentence of what each is;
- the recommended one, when there are variants, and why in one line;
- the hands' spend line verbatim (`spend: img 2/2 …` / `spend: free`);
- the hands' open questions, if any, relayed (`clarify` / `Q<n>:`);
- for the assistant: the hands' QA evidence lines too — it gates by
  intent on its side and needs them.

On a human's bot the file itself is sent when the platform can carry it
(an image inline), the path always.

## QA is done when

- every delivered visual file was looked at, at native size and at the
  size of use, and the verdict is written (a speech delivery's evidence
  was read per "Speech deliveries" above, not looked at or listened to);
- the reply carries paths, spend, and relayed questions;
- sessions for the job are closed (`specialist_session(action="close", conversation_id=<id>)`) unless a
  revise round is pending.
