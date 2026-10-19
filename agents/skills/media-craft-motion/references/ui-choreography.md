# UI Choreography

Interface motion should read as a direct response to what the pointer or
input just did, in the same coordinate space as that input. When a control
changes state, the motion that communicates the change should originate
from where the interaction happened — a ripple, expansion, or reveal that
begins at the point of contact ties the effect to its cause. Motion that
appears somewhere unrelated to the trigger (a menu that always fades in at
screen center regardless of which button opened it) breaks that link and
forces the viewer to relocate the connection themselves.

## Modal foreground versus backdrop

When a modal, sheet, or overlay appears above existing content, its motion
should distinguish it from what is behind it: the backdrop recedes (dims,
blurs, or otherwise visually steps back) while the modal itself asserts
foreground presence (scales up, slides in, or otherwise arrives). Treat
these as two coordinated but separate motions, not one combined fade — a
modal that appears with exactly the same treatment as its backdrop gives the
viewer no depth cue that one element now has priority over the other. When
the interaction has a clear originating point (a clicked button, a tapped
row), let the modal's entrance motion begin from that point when the
interaction model supports it; when there is no such point, see the retain
case below.

## Camera attention is not a blanket response

Zooming, pushing in, or otherwise moving the camera toward a UI element is a
strong attention cue that should be reserved for state changes the user
actually needs to notice and register — a completed purchase, a critical
error, an irreversible action. Applying that same treatment to every minor
interaction (every button press, every hover, every toggle) exhausts its
own signal: if everything gets a camera push, nothing stands out, and minor
interactions end up feeling heavier and slower than they should. Reserve
camera-level emphasis for genuine state transitions and use lighter,
in-place feedback (a color shift, an elevation change, a brief highlight)
for the routine interactions that make up most of an interface.

## Cases

**Revision — unlinked modal origin.** Request: a settings modal in a
product tour always fades in centered on screen, regardless of which of
several icons the user tapped to open it. Weak observation: when several
different icons are shown opening "the same" modal across a tour, the
identical centered fade makes it unclear which action actually triggered
it. Cause: the modal's entrance treatment has no positional relationship to
its trigger — it is one fixed animation reused for every entry point.
Revision: animate the modal expanding from the tapped icon's on-screen
position (or from its nearest edge) so each opening visibly traces back to
its own trigger.

**Revision — blanket zoom on every click.** Request: an ad's UI walkthrough
zooms the camera in on the button for every single click shown, including
minor toggles. Weak observation: by the third or fourth click the zoom no
longer reads as emphasis — it slows the pacing and the viewer stops
reacting to it. Cause: camera-level attention was applied uniformly to every
interaction instead of reserved for the interactions that actually matter.
Revision: keep the camera push only for the interaction that completes the
featured action (for example, confirming a purchase), and replace the
zoom on minor toggles with an in-place color/elevation change on the control
itself.

**Retain — keyboard-triggered modal with no visible origin.** Request/
observation: a modal opens with a fixed center-anchored fade+scale after a
keyboard shortcut, and a reviewer flags it for "not linking to a trigger
position" the way pointer-triggered modals in the same product do. Evidence
for retaining the center-anchored treatment: the triggering action (a
keyboard shortcut) has no on-screen contact point to originate from —
there is no clicked element whose position the modal could plausibly expand
from. Inventing an arbitrary origin point would misrepresent an input that
never touched the screen. The center-anchored appearance is retained as the
correct treatment for this specific trigger type.

## Sources

Backdrop/foreground layering and reserving strong transition emphasis for
meaningful state changes reflect the general shape of Material Design 3's
motion guidance for transitions — read there as one platform's
recommendation, not a universal law that applies outside it:
https://m3.material.io/styles/motion/transitions/applying-transitions
(consulted 2026-09-12).
