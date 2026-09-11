# Quality assurance - against the client's intent

The hands verified against the leaf's `<QA>` (dimensions, alpha, cut-out,
style cues) and said so with evidence. You verify the one thing they
cannot: **is this what the client meant.** Nothing is re-measured here;
nothing is re-done here. Read the selected subject reference before
judging the report; a proposal, findings-only analysis and final media
are different outputs, not interchangeable completion states.

## Subject references

| Hands | Subject references |
| --- | --- |
| image-creator | [card](image-creator/card.md), [icon](image-creator/icon.md), [emoji](image-creator/emoji.md), [mascot](image-creator/mascot.md), [reimagine](image-creator/reimagine.md), [kit](image-creator/kit.md) |
| video-creator | [clip](video-creator/clip.md), [music-video](video-creator/music-video.md), [ad](video-creator/ad.md), [tour](video-creator/tour.md), [explainer-video](video-creator/explainer-video.md) |
| audio-creator | [speech](audio-creator/speech.md), [sfx](audio-creator/sfx.md), [music](audio-creator/music.md), [mix](audio-creator/mix.md) |

## Look before you answer (visual deliveries)

The numbered steps below are for a **visual** file. Speech, SFX, Music
and Mix are reviewed from the hands' evidence under their subject
references above, never opened with vision, relistened to or given a
fresh ASR pass. For video, use the subject's sampled/native-frame
procedure, never pass an MP4 to image vision or claim that a poster
proves motion or sound.

1. Open the recommended file (or every delivered file when there is no
   recommendation) with vision at native size.
2. Open it again at the size the client will use - a Slack sidebar icon
   at 64 px, a favicon at 16 px - by resizing to a scratch copy under
   `deliver:` or `/tmp`. Write the verdict down before the next look;
   vision holds about three images.
3. Read the hands' QA lines: a `FAIL` or `WARN` they delivered anyway is
   yours to weigh against the intent, not to ignore.
4. With a reference image in the form, look at reference and delivery
   side by side once: carried over, not copied.

## The verdict

Compare with the retained purpose and audience, not just the producer's chosen
metaphor. For an explanatory visual, state what a reader can infer from the
actual image without the author's explanation. Geometry/stability and factual
accuracy do not prove comprehension or appeal. Keep subjective uncertainty
explicit; no universal font minimum or extra evaluator for every medium.

For a composite, reconcile the exact accepted versions of its parts with the
assembled output. Changed words can invalidate narration, captions and diagrams;
unchanged parts keep their evidence. Record local acceptance, user approval and
service-side save as separate facts in the existing job notes. A previously
saved draft does not prove the current version was saved. Unknown or failed
checks remain visible, even when some parts are ready.

- **Accept** - it is what was asked, at the size it will be used.
- **Revise** - one `intent: revise <deliver dir>` handoff with the form
  field that changes and nothing else changed ([Build](../build/index.md)).
  Name the defect the way you saw it ("the tail reads as a chip at 64 px"),
  not as an instruction to the model. A revise on a metered leaf costs
  the leaf's corrective; a second revise round is the client's call,
  with the cost stated. Preserve the subject's proposal-approval gates
  when the revision changes approved creative choices.
- **Back to Plan** - the form was wrong, not the render (the wrong verb,
  a field the client meant differently): re-fill with the client, then a
  fresh `intent: new`.

Never "fix it yourself": a local edit on the hands' file is a different
deliverable wearing its filename. An `edit-icon` handoff is the way to
change an icon file; use the actual supported leaf for other subjects.

## Delivery to the client

Reply in the client's language, short:

- the paths (absolute), one sentence of what each is;
- the recommended one, when there are variants, and why in one line;
- the hands' spend line verbatim (`spend: img 2/2 ...` / `spend: free`);
- the hands' open questions, if any, relayed (`clarify` / `Q<n>:`);
- for the assistant: the hands' QA evidence lines too - it gates by
  intent on its side and needs them.

On a human's bot the file itself is sent when the platform can carry it
(an image inline), the path always.

## QA is done when

- every delivered visual file was looked at, at native size and at the
  size of use, and the verdict is written (a speech, SFX, music or mix
  delivery's evidence was read per its subject reference, not looked
  at or listened to);
- the reply carries paths, spend, and relayed questions;
- sessions for the job are closed
  (`specialist_session(action="close", conversation_id=<id>)`) unless a
  revise round is pending. A blocked/unknown session instead leaves a documented
  unresolved report; do not claim the job passed merely to satisfy closure.
  Reconciled `interrupted` transport may be closed as bookkeeping while its
  unknown effects and unaccepted work remain explicitly unresolved.
