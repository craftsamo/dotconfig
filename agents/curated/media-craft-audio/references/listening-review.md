# Listening review

Craft feedback for comparing candidate takes, judging whether a mix or master
actually sounds right, and telling that apart from a bare technical
measurement.

## Meters tell you a number, not whether it sounds right

A loudness reading (LUFS, peak, RMS), a spectrum analysis, or a file hash
confirms that a number matches a target or a previous file — it does not
confirm the audio actually sounds good, sounds the same, or is free of an
audible problem. Two files can share an identical loudness measurement and
still sound clearly different in balance, clarity, or performance; a matched
hash proves only that the bytes match, not that a performance was done well.
Keep "what does the meter say" and "does this actually sound right" as
separate questions, and answer only the one that was actually asked.

## Measurement-only requests stay measurement-only

If a request only asks for a number (loudness, duration, sample rate), report
that number and stop. Don't volunteer unsolicited craft critique of the mix
alongside a measurement nobody asked to have judged — that's out of scope for
a pure measurement request and can read as scope creep.

## Finite variants, host-authorized

When a workflow authorizes producing a batch of candidate revisions or
generation variants, stay within whatever number the host's workflow actually
granted. A grant to review or revise once is not standing permission for
unlimited further attempts — if more variants seem warranted, say so and ask,
rather than generating them unprompted.

## Human-supplied A/B listening; the skill does not have ears

When the host has no authorized audio-understanding path, judgment belongs to
the human doing the listening (the user or a designated reviewer), not to this
skill inventing a preference from measurements. The skill grants no external
analysis calls. Any other host's actual listening tools remain under its policy.
This skill's role is to prepare a fair, clearly described comparison (what
differs between the takes, in concrete terms) and to respect whatever
preference the human states once they've listened. If the user reports "I
picked the first one, it felt warmer," accept that as the outcome — do not
push for a third variant or second-guess the stated choice unless asked.

Loudness-matching two candidates purely so a comparison is fair (removing the
"louder always sounds better" bias) is reasonable when the host provides an
approved mechanism for it — but only as a temporary review copy, never as an
unapproved permanent gain change applied to the original file.

## Transcription errors are not audio defects

If an automatic transcript of a recording contains a misheard word, that's
evidence of a possible transcription or spoken-word difference, not proof of
either cause. Don't conflate the two — verify a suspected
performance issue by listening to the actual audio at that timestamp, not by
trusting a transcript's word choice.

## Worked case: choosing between two voiceover takes

**Request**: "Which of these two voiceover takes is better?" (two files
supplied).

**Handling**: if the host offers a loudness-matching mechanism for fair
comparison, use it only with the host's release for review copies (never altering
the originals). Describe requested control differences before listening; describe
actual pacing, emphasis or breath differences only from attributed listening
evidence. Present the pair and let the human do the listening and make
the final call — don't declare a winner from a transcript or a meter, and
don't invoke unapproved external analysis. If the user reports
"I picked take one, it felt warmer," accept that outcome and don't propose a
third variant unless asked.

## Worked case: measurement-only request

**Request**: "Just tell me the LUFS of this track."

**Weak handling**: reporting the number, then also adding "by the way, I
think your kick drum is too loud in this mix" — an unrequested craft opinion
attached to a pure measurement request.

**Correct handling**: report the requested LUFS value and stop there. If
craft feedback is wanted afterward, that's a separate request the user can
make explicitly.

## When no certification applies

**Request**: "The file claimed as a new take has the same hash as the previous
delivery. Does that prove the revised performance is correct?"

**Observation**: a matching file hash establishes the same delivered bytes,
not a new performance. A matching transcript separately supports recognized-word
agreement, not pacing, emphasis or emotional delivery.

**Response**: state plainly that word-matching evidence can't certify
performance quality; that requires someone (the requester, or the host's
authorized listening workflow) to actually listen to the new take and judge
its delivery — don't rubber-stamp the take as "performed correctly" based on
the hash alone.

## Sources

Original evidence distinctions; consulted 2026-09-12:
[EBU R 128](https://tech.ebu.ch/publications/r128) for measurement scope.
Broadcast loudness guidance is not a universal aesthetic or platform target.
