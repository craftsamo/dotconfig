# Generated Shots

A shot brief for a generative video model should specify camera, subject,
action, and framing as concrete directives — the same discipline as
briefing a human camera operator. But treat exact reproduction of an
appearance or identity (a specific character's face across multiple
generations, an exact brand mark, a precise recurring prop) as a
probabilistic outcome of the generative process, not a guaranteed one.
Writing "the same character as before" into a prompt does not make the
output the same character; it makes the output a new sample from the
model's distribution that may or may not resemble the prior one closely.

## Do not assume cross-model capability

Camera-motion tags, negative prompts, reference-image conditioning,
consistent-seed reuse, and built-in audio generation are all provider- and
model-specific features. A prompting pattern documented for one text-to-video
model — for example, the shot-description structure OpenAI's cookbook
documents for Sora 2 — is evidence for what that specific model supports,
not a general standard every generative video backend implements. Before
reusing a brief format, a camera tag, or an assumption that the model can
also generate synchronized audio, confirm the actual target model and
version's current documentation lists that capability. Do not carry a
feature assumption from one provider's guide into a brief for a different
backend.

## Music-video timing: pin cuts to evidence, not intent

When cutting generated shots to an existing track, pin the cut points
(where one clip ends and the next begins) to checked event markers when beat
sync is intended, not an assumed tempo. Detector peaks are candidates: verify
which events they represent through listening or qualified supplied annotations.
An intentional off-beat cut is not a defect. Separately, do not assume internal
generated motion has frame-exact timing unless the actual model documents that
control and output evidence confirms it. Without it, treat clip boundaries as
authorable timing and in-clip motion as approximate, checked after generation.

## Cases

**Revision — reused camera tag across models.** Request: a shot brief for a
new generative video tool reuses a hypothetical camera parameter (`camera=dolly`)
that worked in a brief written for a different model, without checking
whether the new model's documentation defines that tag at all. Weak
observation: the delivered clip shows a static or unrelated camera behavior,
not a dolly-in. Possible cause: camera-control syntax was carried over from one
provider's documented feature set into a brief for a model that may not
implement it the same way, or at all. Revision: check the target model's
current documentation for its actual supported camera-control vocabulary; if
none exists, describe the desired framing in plain compositional language
and treat the resulting camera behavior as best-effort rather than a
controllable parameter.

**Revision — assumed identity match across clips.** Request: a brief asks
for the same mascot character to appear consistently across five separately
generated clips, based only on repeating a text description of the
character in each prompt. Weak observation: the five clips show visibly
different interpretations of the mascot — different proportions, colors, or
features. Cause: the brief treated generative output as a deterministic
reproduction of a described character rather than a probabilistic sample,
with no reference image or consistent seed/conditioning mechanism supplied.
Revision: if the model supports image-conditioned or seed-based consistency,
supply the same reference image or seed scaffold across all five
generations, and still plan a manual continuity check afterward, since even
conditioned consistency is not guaranteed.

**Retain — approximate in-clip motion timing.** Request/observation: a
music-video brief pins every clip boundary to the track's annotated beat
timestamps from a verified beat-detection pass, but does not attempt to
force the motion inside each generated clip to land on a specific beat
frame-for-frame; a reviewer flags this as "not tightly synced enough."
Evidence for retaining the approach: the precise, verifiable element (the
cut points) is correctly pinned to checked events. In this hypothetical case,
the target model's documentation has been checked and supplies no frame-level
internal timing control. Demanding it would assert an unsupported capability.
The cut-level precision is retained as-is; no attempt is
made to fabricate frame-exact internal timing.

## Sources

The shot-brief discipline of specifying camera, subject, action, and framing
as explicit prompt elements reflects the general shape of OpenAI's Sora 2
prompting guide, which documents that structure for one specific model and
should not be assumed to transfer to other providers' models or their
prompting syntax: https://developers.openai.com/cookbook/examples/sora/sora2_prompting_guide
(consulted 2026-09-12).
