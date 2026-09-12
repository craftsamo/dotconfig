# Speech performance

Craft feedback on narration, dialogue, or voiceover delivery. This covers how
a line is performed — pace, pause, emphasis, breath, emotional shape — not
what the line says.

## Objective vs. emotional change

Separate two kinds of note before giving one:

- **Semantic (objective) change**: the meaning, facts, or wording is wrong.
  That's a script problem, owned by whoever approved the script.
- **Emotional/delivery (performance) change**: the words are right but the
  read doesn't land — wrong emphasis, rushed pacing, flat affect, unsupported
  breath. That's what this reference covers.

If a note about "it doesn't land" is actually a disguised request to change
words (adding urgency by adding an exclamation point, softening a claim by
rewording it), flag that distinction rather than silently rewriting approved
copy. Only alter delivery parameters the host's voice pipeline actually
exposes — never the approved words themselves.

## Emphasis

Every sentence has a word (or a few) carrying the point — usually new
information or a contrast with what preceded it, not automatically the first
or the loudest-sounding word. Identify that word specifically before
recommending a change: "stress *small*, because the sentence's point is that
even a small amount is dangerous," not "add more emphasis."

## Pause and breath

Pauses mark where a listener needs a beat to process a shift: before a
consequence clause, before a name being introduced, after a question. A
missing pause before a consequence makes a warning read like one continuous,
flattened list. A missing breath before a long or emotionally weighted clause
makes the delivery sound rushed or insincere, since real breath support is
what lets a voice land the following words with any control.

## What is and isn't a supported lever

Emphasis, pacing, and pause placement are usually real levers a host's voice
pipeline exposes (a provider's style/emphasis parameter, a phrasing/breath
hint, or simply adjusted punctuation that a given voice engine is known to
respond to). SSML tags, emoji, or a "voice style" name are not universal —
they only work if the specific host and voice route already support them.
Never invent an SSML tag, break tag, or emoji insertion on the assumption it
will be honored; ask what the host's actual supported route is, or state that
none is available for the requested effect.

A waveform image is not a substitute for listening: it shows amplitude over
time, not intelligibility, tone, or whether the emotional read actually lands.
Ground every note in an actual listen to the delivered audio.

## Worked case: flat warning line

**Request**: "The safety line doesn't feel urgent enough, without changing
the wording."

**Observed** (from listening): "Even a small amount of this chemical can
cause serious harm" is read at even pace and even stress, with barely any
gap before "can cause serious harm" — it sounds like one clause in a list,
not a warning.

**Cause**: no contrastive stress on the word carrying the actual claim
("small" — the point is that a *small* amount is enough), and no anticipatory
pause before the consequence clause to let it land separately.

**Revision**: keep the wording unchanged; direct the host's emphasis control
to stress "small" and "cause," and request a longer pause immediately before
"can cause serious harm" so the consequence reads as its own beat rather than
a continuation.

## Worked case: insincere apology line

**Request**: "This apology line reads insincere."

**Observed**: the final clause rises in pitch at the end, like a question,
and is delivered at the same brisk pace as the rest of the line — no breath
taken before it.

**Cause**: sentence-final rising intonation (often triggered by ambiguous
punctuation or a rushed read) makes a statement sound tentative or
performative rather than sincere; no breath before the final clause removes
the one pause that would let it read as considered rather than recited.

**Revision**: request a breath/pause before the final clause and a falling
terminal contour through whatever phrasing lever the host's voice pipeline
actually exposes (a punctuation hint, a pacing parameter, an explicit
phrase-break control) — do not add an SSML `<break>` tag or an exclamation
mark on spec if the host hasn't confirmed that route is honored.

## When no revision applies

**Request**: "Make the apology sound more emotional" on a take that already
carries a slow pace, a falling final contour, and audible breath before the
last clause.

**Observation**: the existing take already achieves the requested emotional
objective; adding more emphasis or a slower pace on top would tip it into
over-acting and undercut the sincerity that's already there.

**Response**: state that the take already meets the stated goal, point to the
specific evidence (pace, contour, breath) that supports leaving it alone, and
do not manufacture a change.
