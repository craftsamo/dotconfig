# Motion and component vocabulary

A dictionary, not a rulebook. Left alone, a plan collapses every idea into
"fade in", "slide", "card" and "transition". Use these names instead: pick
the one that says exactly what the viewer should see, and write it into the
storyboard or design by name (one entry per event or component; combine
entries freely; a more precise name of your own is fine). Each entry gives
what it looks like and how it is usually built in HTML/CSS/SVG/GSAP.

## Text animations

| Name | Looks like | Built with |
| --- | --- | --- |
| split-text stagger | letters/words/lines arrive one after another as a wave | split into spans; stagger 0.02-0.08 s on y/opacity |
| mask reveal (line rise) | each line slides up out of an invisible slot, cut off below | line wrapper `overflow:hidden`; inner span y 110% -> 0 |
| blur-in / focus pull | words arrive soft and snap sharp as they land | `filter: blur()` 12-20px -> 0 with y or scale |
| scale punch | a key word lands oversized and settles to size | scale 1.3-1.6 -> 1, expo/back ease |
| tracking-in | letters spread wide then contract into the word | letter-spacing 0.5em -> normal, opacity |
| typewriter + caret | characters appear one by one with a blinking caret | per-char opacity set; caret element |
| scramble / decode | random glyphs resolve into the real word | per-char text swap from a fixed seeded glyph list |
| word swap slot | one word in a sentence rolls to the next option | vertical stack in a masked slot, y steps |
| odometer digits | each digit column rolls like a mechanical counter | per-digit column of 0-9, masked, y tween |
| count-up | a number climbs to its value | tween an object, write rounded value per frame |
| marker highlight | a colour band sweeps behind a word | pseudo-element scaleX 0 -> 1 from the left |
| underline draw | a stroke draws under the word | SVG path `stroke-dashoffset` |
| outline-to-fill | hollow outlined letters fill with colour | `-webkit-text-stroke` + fill clip or opacity layer |
| gradient sweep text | a light band travels across the letters | `background-clip:text`, animate background-position |
| echo stack | the word repeats in fading copies behind itself | duplicated layers offset in y/z, decreasing opacity |
| karaoke highlight | words brighten in reading order | colour/opacity per word on a stagger |
| kinetic lockup | words of a line fly in from different directions and lock into a block | per-word from-vectors, shared end time |
| text as window | giant type acts as a mask revealing imagery/UI inside it | `background-clip:text` or SVG mask with text |

## Transitions (between beats)

| Name | Looks like | Built with |
| --- | --- | --- |
| hard cut on hit | instant change on a beat, no dissolve | `tl.set` visibility at the cut |
| match cut | the next beat's shape appears exactly where the last one was | align geometry of both sides at the cut |
| carrier handoff | one object keeps moving across the cut and becomes part of the next beat | same element (or aligned twin) continues its tween |
| shared-element morph | a card grows into a full page / a button becomes a panel | FLIP: tween position, size, radius between two layouts |
| zoom-through | camera pushes through the outgoing beat into the next | scale up + blur on exit, incoming scales from 0.8 |
| inverse zoom / arrival | the next beat arrives oversized and settles back | incoming scale 1.25 -> 1, outgoing shrinks |
| dolly into screen | camera flies into a device screen, which becomes the frame | scale the device until its screen fills the canvas, swap |
| pull-back reveal | a close detail pulls back to reveal the whole | start scaled 3-5x on a detail, tween to 1 |
| whip pan | very fast sideways travel with streaked blur | x travel + directional blur (SVG feGaussianBlur x only) |
| clip-path wipe | a hard-edged shape sweeps the new beat in | `clip-path: inset()/polygon()` tween |
| iris / circle reveal | a circle opens from a point (often a click) | `clip-path: circle(0 -> 150%)` |
| light wipe | a band of light sweeps and leaves the new beat behind it | bright gradient bar tweened across, swap under it |
| glow wash | a bloom rises to near-white, beat swaps under it | full-frame radial white overlay opacity up/down |
| rack focus | the scene defocuses, swaps, refocuses | wrapper blur spike, swap at peak |
| card flip | a surface turns over and its back is the next beat | `rotateY(180deg)`, `backface-visibility` |
| fold / unfold | a panel folds along a crease into the next shape | two halves with `rotateX` on a shared edge |
| shutter slices | the frame splits into strips that slide away | N strips with staggered x/y |
| push stack | the new beat slides over the old like a card on a pile | incoming y from 100%, old scales to 0.94 and dims |
| split-screen expand | a divider opens, one side grows to fill the frame | width/clip tween on two panes |
| dither / pixel dissolve | the image breaks into pixels and rebuilds | canvas or SVG pattern mask, seeded |

## Camera

| Name | Looks like | Built with |
| --- | --- | --- |
| push-in / pull-out | slow move toward/away from the subject | scale on a camera wrapper |
| truck / pedestal | sideways / vertical travel over a wide layout | x/y on a camera wrapper over an oversized stage |
| orbit | camera circles an object in 3D | `rotateY` on the object inside a `perspective` parent |
| snap / crash zoom | abrupt fast zoom onto a detail | short scale tween, expo.in-out |
| parallax layers | foreground, midground, background move at different rates | same tween, different distances per layer |
| infinite canvas pan | camera travels across one huge board of UI and text | one large stage translated through keyed positions |
| tilt-shift | top and bottom blurred, middle sharp; looks miniature | gradient-masked blurred copies or backdrop-filter bands |
| dutch tilt | slightly rotated frame for energy | small rotate on the camera wrapper |
| focus follow | depth of field shifts to whatever becomes important | per-layer blur tweens |

## Effects

| Name | Looks like | Built with |
| --- | --- | --- |
| bloom / glow | light bleeding around bright elements | blurred duplicate behind, `mix-blend-mode: screen` |
| light leak | warm/cool soft light spills across a corner | large blurred gradient blobs drifting |
| light field | soft coloured glows living in the background | 2-4 radial gradients, slow drift |
| lens streak | a thin horizontal flare line across a highlight | thin blurred bar, screen blend |
| sheen / shimmer | a diagonal gloss passes over a surface | angled gradient masked to the element, x tween |
| glassmorphism | frosted translucent panels over colour | `backdrop-filter: blur()`, 1px light border |
| shadow stack | contact + ambient + tinted shadows under objects | multiple `box-shadow` layers |
| reflection floor | objects mirrored faintly on a glossy floor | flipped copy with gradient mask |
| motion blur | streak along fast movement | directional blur only while moving |
| depth of field | far things soft, near things sharp | per-layer blur |
| film grain | fine moving noise over everything | SVG `feTurbulence` or seeded noise overlay, low opacity |
| chromatic aberration | colour fringe on fast moves | RGB-split copies offset a few px |
| pulse ring | a ring expands from a tap or node | circle scale 1 -> 3, opacity 1 -> 0 |
| particle burst | small shapes spray out from an impact | pre-placed seeded particles, radial tweens |
| sparkle | brief star glints on a success moment | small scale/rotate pops |
| spotlight | a soft pool of light follows the focus | radial gradient positioned on the subject |
| halftone / dither | printed dot or pixel texture | pattern fill or SVG filter |
| vignette | edges darkened to hold the eye in the centre | radial gradient overlay |
| noise gradient / mesh gradient | rich multi-colour soft background | several blurred blobs, optional grain |

## Components (drawn UI and graphics)

| Name | Looks like | Built with |
| --- | --- | --- |
| phone frame | realistic device with bezel, notch, screen content | rounded rects, inner screen, gloss |
| browser window | chrome with traffic lights, tabs, URL bar | flex header + content area |
| URL / domain bar | a pill showing a web address with a lock | pill, icon, text |
| one-page site mock | hero, sections, menu, hours, map, footer with real-looking content | stacked sections, real words and numbers |
| bento grid | tiles of different sizes each showing a feature | CSS grid, varied spans |
| floating UI cards | pieces of UI detached and floating in depth | absolutely positioned cards with z/shadow |
| exploded view | an interface separated into layers in 3D | same layers offset in `translateZ` |
| wall of screens | many screens tiled, camera travels across | grid of mini mocks |
| notification toast stack | notifications dropping in and stacking | stacked cards, y/scale offsets |
| chat bubbles | a conversation building up | alternating bubbles, typing dots |
| form with caret | fields filling themselves, focus ring moving | inputs as divs, per-char reveal |
| button press | a button squashes, changes state, ripples | scale 0.96 -> 1, colour change, ring |
| oversized cursor | a big pointer that travels and clicks | SVG pointer, eased path, click squash |
| toggle / switch | a switch flips on | knob x tween, track colour |
| checklist with ticks | items tick off one by one | SVG check path draw per item |
| progress bar / ring | fills to a value | scaleX or `stroke-dashoffset` |
| stepper / timeline | numbered steps connected by a line that fills | nodes + line fill |
| calendar strip | days in a row, a range highlighting | row of day cells, fill sweep |
| price tag | a hanging tag with an amount | shape + string, pendulum rotation |
| pricing card | plan card with price, period, inclusions | card with large numeral |
| receipt / invoice | a slip printing line by line | clip reveal downward |
| stat card | a big number with a label | count-up numeral |
| badge / chip / pill | small labelled capsules | rounded spans |
| avatar stack | overlapping round portraits | negative margins, stagger in |
| map + pin + route | a map with a dropping pin and a path drawing | SVG shapes, pin drop, path draw |
| search bar with typed query | a query types, results drop in | caret typing, list stagger |
| tooltip / callout | a label with a leader line pointing at a detail | line draw + label pop |
| hand-drawn annotation | circles and arrows scribbled on the UI | SVG path draw, rough stroke |
| marquee / ticker | a line of text or logos scrolling endlessly | duplicated row, linear x |
| carousel | cards sliding past a focus position | row x steps, scale on centre |
| sticky note | a paper note slapped on | rotate + scale pop with shadow |
| QR / scan frame | a scan frame locking onto a code | corner brackets tighten |
| logo lockup reveal | the mark resolves with the wordmark | the supplied file, opacity/position only when the brand forbids effects |

## Compositions

| Name | Looks like |
| --- | --- |
| full-bleed hero | one object or word fills the whole frame, edges cropped |
| oversized type crop | letters bigger than the frame, only part visible |
| centre stack | headline, object, sub-line stacked on the centre axis |
| split layout | frame divided into two zones (text / object), often diagonal |
| over-the-shoulder device | device held close to camera, content readable, background soft |
| macro close-up | extreme close view of one UI detail |
| top-down flat lay | objects arranged on a surface seen from above |
| isometric | 3D-looking layout without perspective convergence |
| tunnel / corridor | cards lining the walls of a corridor the camera travels through |
| orbit around headline | objects circling a central line of text |
| collage | many cut-out elements overlapping at different scales |
| screen within screen | a device whose screen shows another device or the film itself |
| before / after split | two states side by side with a moving divider |
