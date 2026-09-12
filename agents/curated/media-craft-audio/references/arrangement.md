# Arrangement

Craft feedback on how multiple audio layers — music, dialogue, sound effects,
ambience — share a scene or a mix over time. This is distinct from
composition (the content of one part) and sound design (the character of one
effect): arrangement is about relative roles, space, and density across
everything sounding at once.

## Roles: foreground, midground, background

Assign every layer a role for each moment rather than letting everything
compete for the listener's attention at once:

- **Foreground**: the thing that should command primary attention right now —
  a lead vocal, a key line of dialogue, a critical sound effect.
- **Midground**: supportive harmonic or rhythmic content that reinforces the
  foreground without competing with it.
- **Background**: ambient texture or a pad that sets context but isn't meant
  to be consciously tracked.

A layer's role can and should change over time (music can be foreground
during an instrumental passage and background during dialogue) — the problem
isn't having a busy arrangement, it's having no differentiation of roles at
all, so several layers fight for foreground simultaneously.

## Space and density

Leave space — genuine gaps or thinner texture — at the moments the
foreground needs clarity. A mix with every layer sustaining continuously in
overlapping registers gives the ear nowhere to rest and makes the intended
foreground hard to track. Reducing density (fewer simultaneous active
layers, or a simpler version of a layer) at the right moment is usually a
more effective fix than trying to carve every layer with narrow processing.

## Dynamic beds, not static ones

A background ambience or pad should have its own dynamic shape over time —
swelling and receding with the narrative moment — rather than sitting at one
constant level and density for the whole scene. A static bed under a scene
with rising tension reads as unengaged with the scene, independent of how
well-designed the bed's individual sound is.

## Only use supported gain/envelope controls; preserve timing

Recommend specific gain automation, ducking, or envelope shaping only when
the host's tool has already confirmed it exposes such a control; otherwise,
describe the target balance and role (which stems should be thinner or
silent at a given moment) and let the host determine how to realize it, or
suggest reduced-density re-renders of the offending layer. Never force a
generic EQ, compression, or spatial (panning/reverb) instruction the host
hasn't confirmed is available. Arrangement fixes must also preserve the
actual timing and content of underlying recordings — don't recommend
retiming dialogue or shifting an existing effect's cue point to solve a
balance problem a role or density change can solve instead.

## Worked case: music masking narration

**Request**: "This corporate video's arrangement feels busy — the narrator is
hard to follow."

**Observed**: the background music plays a full arrangement (drums, bass,
pad, and a melodic hook) at a consistent level throughout the entire
narration, not just during music-only sections.

**Cause**: the music never yields a foreground role to the narration — it
stays in a foreground-competing role the whole time, and the melodic hook in
particular sits in a register that overlaps the narrator's voice, so the two
compete directly rather than one supporting the other.

**Revision**: during narration passages, drop the music to a midground or
background role — specifically remove or reduce the competing melodic hook
(the busiest, most register-overlapping element) — and restore the full
arrangement during music-only sections. If the host's tool exposes an actual
ducking or gain-automation control, direct that; otherwise, recommend which
stems to omit or re-render at reduced density during narration rather than
inventing a sidechain-compressor instruction the host hasn't confirmed.

## Worked case: wall-of-noise ambience

**Request**: "The layered ambience (rain, crowd, traffic) for this scene just
sounds like a wall of noise."

**Observed**: all three beds sit at a similar, constant level throughout the
scene, with similar frequency content and rhythmic density, regardless of
what the scene is narratively focused on at a given moment.

**Cause**: none of the three beds has an assigned priority for the scene's
current narrative moment — an establishing wide shot and a quiet dialogue
moment both get the identical three-way mix, so nothing is foreground and
nothing recedes.

**Revision**: designate one bed as foreground for the establishing shot
(traffic, since that's the shot's visual focus), demote the other two to
background at reduced density, then swap the priority to crowd or rain as the
scene's focus shifts — keeping each bed's own recorded content and timing
untouched; only their relative prominence over time changes.

## When no revision applies

**Request**: "Make the mix bigger" on a scene where the actual underlying
complaint (on further listening) is that the master sounds quiet compared to
a reference, not that any layer is misbalanced against another.

**Observation**: every layer's role, density, and relative balance are
already well-differentiated; the complaint is really about overall loudness,
which is a mastering/listening-review question, not an arrangement one.

**Response**: state that arrangement techniques (roles, space, density)
don't address this complaint, and redirect to a loudness/listening-review
comparison instead of forcing unrelated panning or reverb changes that
wouldn't fix the actual issue.
