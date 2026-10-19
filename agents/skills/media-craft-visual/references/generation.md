# Generation: prompting as a design medium

Read this when the work happens through a text-to-image prompt or an
image-editing/inpainting instruction, especially when an existing image's
identity has to survive an edit, or when exact copy (a specific word or
number) has to appear in the output.

Treat a generation prompt as a design brief, not a keyword bag. State the
subject, the composition (what is in the frame and where), the light
(direction, quality, source), and the priority order between them, the same
way you would brief a human illustrator. A prompt that lists many
disconnected adjectives without a stated priority tends to produce a
generically "busy" or averaged result, because the model has no signal for
which quality matters most when they conflict.

When editing an existing, identifiable image (a specific mascot, a specific
person's likeness, a specific product shape), protect identity explicitly:
name the features that must not change (proportions, color palette, a
signature prop or marking) separately from the change being requested.
Treat this the same as any other "retain" decision: the fact that a tool
can regenerate an entire image does not mean every pixel should be
considered open to change.

Do not rely on a generative model to render exact copy (a specific headline,
a price, a data label) reliably; if the request needs specific words to be
correct and legible, plan to typeset that copy separately after generation
and compose it onto the image, rather than prompting for it directly. Avoid
model-specific prompt syntax (a particular tool's weighting brackets or
parameter flags) in guidance meant to be portable; describe the desired
result in plain language instead, since that syntax does not transfer
between tools and goes stale as tools change.

## Case 1: reimagining a mascot lost its identity

Request: "reimagine" the "Riverbend Community" mascot (a rounded, orange fox
character with a signature blue scarf) in a more dynamic, action-oriented
pose for a sports-league sponsorship image.

Weak result (observed): the regenerated mascot was recognizably a fox in a
dynamic pose, but the color had shifted to a more reddish-brown, the scarf
was gone, and the head shape was more angular than the original rounded
design; stakeholders said it "isn't our mascot" despite being an orange fox.

Diagnosis: the prompt described the desired pose and energy in detail but did
not separately state the identity features that had to be preserved, so the
model treated color, scarf, and head shape as open along with everything
else, since nothing signaled they were fixed rather than stylistic defaults.

Revision (specific choice): re-ran the edit with an explicit identity block
in the brief separate from the pose request: exact color values for the fur
and scarf, "rounded" head shape named directly, and the scarf described as a
required element, not an optional accessory, then used an image-to-image or
reference-conditioned edit (feeding the original mascot art as a reference)
rather than a text-only regeneration, since text-only regeneration had
already shown it would drift on identity details.

Retain: the new dynamic pose and increased motion energy from the first
attempt were kept, since that part of the result matched the request; only
the identity-losing details were corrected.

When NOT to use this fix: if the request is explicitly to redesign the
mascot's core look (a deliberate rebrand), do not lock the old identity
features; in that case, the "identity" that must be preserved is whatever
the rebrand brief defines as staying constant (e.g., the species and general
personality), not the old color and scarf.

Evidence method: placed the revised mascot side by side with the original
reference art at the same scale and checked each named identity feature
(fur color, scarf, head shape) individually, rather than judging "does it
still look like the mascot" as one holistic impression.

## Case 2: baking exact copy into a generated image

Request: a generated poster background for the "Harborview Art Fair," with
the specific text "SEPT 14" needed prominently on the poster.

Weak result (observed): the generated image included text-like shapes in
the requested area, but the characters were malformed (extra strokes,
inconsistent letterforms), unreadable as "SEPT 14" even though the general
composition and placement were correct.

Diagnosis: the copy was treated as part of the visual generation, which does
not reliably produce specific, correct legible text; the placement and
composition intent was sound, but exact wordmark accuracy was not something
that step of the process could guarantee.

Revision (specific choice): regenerated the background with the text area
left as clean negative space (describing the desired composition and
reserved area, not the words themselves) and then typeset "SEPT 14"
separately in the project's actual typeface and composited it into the
reserved area, matching the perspective and lighting of that area by hand.

Retain: the generated background's composition, color palette, and overall
mood stayed exactly as approved; only the text layer changed from
"generated" to "typeset and composited."

When NOT to use this fix: if the platform or workflow explicitly does not
allow separate typesetting or compositing after generation (a one-shot
generation pipeline with no post-processing step), do not promise exact copy
accuracy; instead, flag the limitation and negotiate either a looser copy
requirement or a different pipeline, rather than silently accepting
malformed text.

Evidence method: read the generated text character by character against the
required string at the poster's actual print or display size, rather than
confirming only that "there is text in the right place."

## Sources

No tool-specific prompt syntax is documented here by design, since bracket
weighting, parameter flags, and similar syntax are specific to one generation
tool and go stale as tools change (reviewed 2026-09-12); the subject,
composition, and light-priority framing above is original, portable prompt
craft, not a specific vendor's guaranteed output behavior.
