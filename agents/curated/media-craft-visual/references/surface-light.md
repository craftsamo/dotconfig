# Surface and light: value, mass, edges, material

Read this when a surface in an image looks flat, plasticky, muddy, or
overworked, or when a fix like "add grain" or "add a gradient" was tried and
did not solve the actual problem.

Surface quality is mostly a value (light-to-dark) and edge problem before it
is a texture problem. An object reads as having mass when its core shadow,
midtones, and highlight are placed consistently with one light direction and
with the material's actual light behavior (matte scatters light broadly and
softly; glossy holds a tight, bright highlight with sharp falloff; metal
picks up its environment's colors in its reflections). Texture (grain, noise,
paper weave) is a surface finish applied on top of correct value and edges;
adding it to a shape that has no value structure just adds noise to a flat
shape, it does not create the missing form.

Match the rendering approach to what the material is and to how the asset
will be used. A UI icon usually wants simplified, controlled value steps
(2 to 4 tonal levels) rather than photographic gradients, because it has to
stay legible at small size; a hero illustration can carry much more tonal
range because it is viewed larger and longer.

## Case 1: adding grain instead of fixing missing form

Request: a set of weather condition icons ("sunny," "cloudy," "rain") for
a neighborhood app looked "cheap" compared to a reference icon set; the
first attempt to fix it added a subtle grain texture over each icon.

Weak result (observed): the icons still looked flat after the grain was
added; the grain sat visibly on top of the flat shapes like a filter, and at
the app's actual small size (24px) the grain mostly disappeared into noise
and made the icons look slightly dirty instead of more refined.

Diagnosis: the "cheap" perception was coming from flat, single-tone shapes
with no light-direction logic (the cloud shape had no distinction between its
lit top and shadowed underside), not from a missing surface finish. Grain
cannot substitute for value structure, especially at a size where fine
texture cannot even resolve.

Revision (specific choice): added a simple two-tone shading pass to each icon
(a slightly darker tone on the underside of rounded forms, consistent across
all icons as if lit from the same upper-left direction), and removed the
grain entirely since it added noise without solving the reported problem.

Retain: the icons' flat color fills for the "unlit" faces stayed exactly as
they were; only the shadow tone was added, keeping the icon set's simplified
look appropriate for its small display size.

When NOT to use this fix: do not add multi-step photographic shading to an
icon meant to sit in a dense toolbar or list at very small size; over
rendering an icon that needs to read instantly as a silhouette can hurt
recognizability more than a flat fill would.

Evidence method: rendered the icons at their actual 24px display size next to
each other (not enlarged in an editor) to confirm the shading was visible and
the light direction read consistently across the set.

## Case 2: material mismatch between edge treatment and claimed material

Request: a metallic badge icon for an "Art Fair Sponsor" tier, meant to read
as brushed metal.

Weak result (observed): the badge had a smooth, glassy highlight with a
sharp specular dot and vivid color-shifted reflections, similar to polished
chrome; several reviewers described it as "plastic" or "toy-like" rather than
metal.

Diagnosis: brushed metal and polished chrome behave differently. Brushed
metal scatters reflections along the direction of the brushing, producing
elongated, softer highlights and a narrower reflected color range; a sharp
round specular dot with saturated color shifts is the signature of a
smooth, glossy plastic or polished surface, not a brushed one, so the edge
and highlight treatment contradicted the stated material.

Revision (specific choice): replaced the round specular highlight with a
horizontal streak-shaped highlight aligned to an implied brushing direction,
and reduced the reflected color's saturation so the badge stayed within a
narrow warm-neutral range instead of a rainbow-tinted one.

Retain: the badge's overall gold-toned color and its embossed rim stayed;
only the highlight shape and reflection saturation changed, since the
complaint was specifically about material believability, not the color.

When NOT to use this fix: do not apply a soft brushed-metal highlight to an
object that is meant to look new, polished, or premium in a glossy sense
(e.g., a "1st place" trophy icon); in that case the sharp specular highlight
this case removed is the correct choice.

Evidence method: compared the badge at native resolution against two or three
real reference photos of brushed vs. polished metal side by side, rather than
judging "does this look like metal" from memory alone.

## Sources

No single external source is cited for value/material rendering here; the
principles above are original engineering and design reasoning about light
behavior and material perception (reviewed 2026-09-12), not a vendor
guarantee or a rendering-engine specification. Verify a material claim
("this reads as brushed metal") against real reference photos rather than
against this text alone.
