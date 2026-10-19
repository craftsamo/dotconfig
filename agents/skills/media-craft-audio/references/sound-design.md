# Sound design

Craft feedback on foley, sound effects, and ambience: one-shot hits, looping
textures, and layered environmental beds.

## The vocabulary: attack, body, tail

Every sound effect has three phases worth judging separately:

- **Attack**: the onset — how sharply or softly the sound starts. A sharp
  attack (a crack, a snap) reads as sudden or dangerous; a soft attack (a
  swell, a rustle) reads as gentle or distant.
- **Body**: the sustained middle — its texture, pitch content, and implied
  physical material.
- **Tail**: how it dies away — an abrupt cutoff reads as small or clipped; an
  extended, decreasing tail reads as large, resonant, or consequential.

A weak sound effect is often weak in exactly one of these three phases even
when the other two are fine — diagnose which phase is missing rather than
asking for "more impact" in general.

## Material, distance, density

- **Material**: what the sound implies it's made of or interacting with
  (wood, metal, cloth, gravel, water). A mismatch between implied material and
  visual/narrative context reads as fake even if the sound is otherwise
  well-built.
- **Distance**: perceived proximity, usually signaled by relative level, loss
  of high-frequency detail, and the ratio of direct sound to any reflected/
  reverberant tail. A close sound has more high-frequency detail and less
  reflected tail relative to its direct level; a distant one has the reverse.
- **Density/repetition**: how often an effect repeats and whether repeated
  instances are identical. A sound repeated with zero variation (same attack,
  same tail, same length every time) reads as mechanical or looped even if
  each instance is well-built in isolation.

## Synthesis and balance: only what's supported

Reference a specific synthesis mechanism (subtractive, FM, granular, etc.)
only when the host has already demonstrated it exposes that engine and its
named parameters. Otherwise, describe the target sound by its audible
qualities (bright, damped, metallic, breathy) rather than inventing a plugin
name or DSP parameter that may not exist in the host's toolchain. The same
applies to balance against dialogue or music: describe the target relative
level and role, and only reference a specific gain/EQ/compression control if
the host has confirmed it's available.

## Worked case: mechanical-sounding footsteps

**Request**: "These footsteps sound robotic, like the same sample looped."

**Observed**: every step has an identical attack transient and identical tail
length, regardless of the character's changing walking pace across the shot.

**Cause**: no per-step variation in attack sharpness or tail length, and
density (steps per second) increases as the pace quickens in the scene while
each individual step's tail length stays fixed — so tails start to overlap
and smear as the character speeds up.

**Revision**: vary attack sharpness slightly step to step (alternate a
slightly harder heel-strike with a slightly softer one), and shorten each
step's tail as the pace increases so faster steps don't smear into each
other; keep the implied material (e.g., gravel) consistent throughout so the
footstep's identity doesn't drift even as its character varies.

## Worked case: toothless explosion

**Request**: "This explosion doesn't feel dangerous, it just sounds like a
low boom."

**Observed**: a single low-frequency rumble layer with a soft onset and an
abrupt cutoff — no sharp attack transient and no extended settling tail.

**Cause**: an explosion's sense of danger and scale comes from a fast, bright
attack (the initial crack) layered ahead of the low body, plus a tail that
decreases in density over several seconds (debris and settling) rather than
cutting off; this version has only the low body.

**Revision**: add a fast, bright attack layer ahead of the existing rumble,
and extend the tail with gradually decreasing density (rather than an abrupt
stop) to imply debris settling after the initial blast.

## When no revision applies

**Request**: "Add more bass to this UI click so it feels weightier."

**Observation**: the click is a short, high-frequency-dominant one-shot with
no sustained body to carry low-frequency content, and the host's available
source/synthesis for this element has no bass-capable material to draw on.

**Response**: state that "more bass" isn't achievable for a sound this short
and this source-limited without changing its fundamental character (which
would stop reading as a click at all), and don't invent an EQ boost command
the host hasn't confirmed exists for this asset. If more weight is genuinely
wanted, that's a different sound to source, not a processing fix to this one.
