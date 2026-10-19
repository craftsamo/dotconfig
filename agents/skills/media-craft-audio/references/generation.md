# Generation

Craft feedback for turning a mood or scene into a text prompt for an audio
generation tool, and for judging what actually comes back.

## Turn mood into timbre and plausible time evolution

A generation prompt is stronger when it names concrete, plausible timbral
choices ("warm analog pad," "bright plucked string," "breathy solo flute")
rather than an unbounded stack of mood adjectives. It should also describe
how the piece is meant to develop across its actual requested duration — for
example, "starts sparse with a single sustained tone, adds a soft rhythmic
layer at the midpoint, resolves to a held chord in the final few seconds" —
so the requested arc is something the requested length can actually contain.

## Forbid unstable, contradictory prompts

Do not stack descriptors that pull in opposite directions in the same prompt
("aggressive but calm," "fast but slow," "dark but bright") — a generative
model has no way to reconcile contradictory instructions, and the result is
typically incoherent or unpredictable rather than a blend of both qualities.
Pick the one dominant mood axis the request actually needs and describe it
clearly instead of hedging with a long list of adjectives.

Also check that the described time evolution fits the requested duration: a
prompt asking for a multi-movement arc ("dramatic build, a midpoint twist,
then a triumphant finale") inside an 8-second sting has no room to actually
realize that structure, and the result will typically sound cramped or
truncated rather than achieving all three described stages.

## A prompt is a request, not a guarantee

A text prompt for a generation model does not guarantee a specific
instrument, exact pitch content, or a specific existing reference track will
be reproduced, and its output is not "native" audio captured from a real
performance — it's a generated result from a model. Judge and critique the
actual returned audio by listening to it, not by re-reading the prompt and
assuming it was realized as written.

## Worked case: unstable ambience loop

**Request**: "Generate a mysterious forest ambience for a clean 30-second
loop."

**Observed** (from listening to the returned audio, not from the prompt):
the generated clip has an unexpected loud percussive hit around the 10-second
mark that breaks the intended seamless loop.

**Cause**: the original prompt asked for "mysterious but energetic, sparse
but busy" — a contradictory pair of descriptors that likely led the model to
insert an unpredictable dynamic event rather than sustaining a stable,
loopable texture.

**Revision**: rewrite the prompt to remove the contradictory pair and commit
to one clear mood axis (mysterious, sparse), with an explicit gentle time
evolution suited to a clean loop — "starts near-silent, slowly introduces a
distant wind texture by the midpoint, stays sparse and non-percussive
throughout" — regenerate through the host's actual tool, and listen to the
new result again rather than assuming the rewritten prompt fixed it.

## Worked case: cramped short sting

**Request**: "An energetic 8-second sting for a level-up moment."

**Observed**: the returned clip attempts a full arc — a build, a midpoint
twist, and a triumphant finale — compressed into 8 seconds, and each stage
sounds rushed and unresolved rather than clearly landing.

**Cause**: the prompt described a three-stage structure that needs
significantly more than 8 seconds to read clearly; asking for that much
structure in that little time produces a cramped result regardless of how
well-chosen the individual timbres are.

**Revision**: simplify the prompt to a single clear gesture that actually
fits 8 seconds — "a quick rising synth stab that lands on one bright,
sustained chord" — regenerate, and confirm by listening that the shorter,
simpler arc reads cleanly at that length.

## When no revision applies (unsupported request)

**Request**: "Generate the exact three-chord piano riff from [a specific
existing reference track], just re-rendered."

**Observation**: text-to-audio generation has no mechanism to guarantee
reproducing a specific existing piece's exact notes, voicing, and
instrumentation from a text description alone.

**Response**: state plainly that this isn't achievable through prompt
craft — it would require the actual reference material and a different kind
of tool (e.g., sample-accurate transcription or licensed reproduction, which
are outside this skill and the host's generation tool) — rather than
iterating through an open-ended series of new adjectives hoping one prompt
happens to match the reference by chance.
