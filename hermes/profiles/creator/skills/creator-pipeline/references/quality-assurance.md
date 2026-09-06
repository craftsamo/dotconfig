# Quality assurance — your eyes, against the client's intent

The hands verified against the leaf's `<QA>` (dimensions, alpha, cut-out,
style cues) and said so with evidence. You verify the one thing they
cannot: **is this what the client meant.** Nothing is re-measured here;
nothing is re-done here.

## Look before you answer

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

- every delivered file was looked at, at native size and at the size of
  use, and the verdict is written;
- the reply carries paths, spend, and relayed questions;
- sessions for the job are closed (`resident-session.sh close`) unless a
  revise round is pending.
