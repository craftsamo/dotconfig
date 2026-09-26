# Motion and component vocabulary

A dictionary, not a rulebook. Left alone, a plan collapses every idea into
"fade in", "slide", "card" and "transition", and every abstract idea into a
label or an icon. Use these names instead: pick
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

## Visual metaphors

An idea shown as a physical thing the viewer already understands, instead
of a word on a card. Name the idea and the image together ("bottleneck as
funnel"); the image can be drawn in any style and combined with any entry
above.

| Idea | Image | Looks like | Built with |
| --- | --- | --- | --- |
| bottleneck | funnel / hourglass neck | many items crowd the wide mouth and trickle through one at a time | dots on paths converging to one point, staggered release |
| filtering / selection | sieve | a stream of items falls, only the right ones pass, the rest bounce away | two particle groups, one passes a mesh line, one deflects |
| growth | sprout | a stem rises, leaves unfold, the plant reaches the number | SVG stem path draw, leaf scale from the node, count-up at the tip |
| compounding | snowball | a small ball rolls downhill and swells with each turn | scale tied to x, rotation, trail |
| scale / replication | tile cloning | one unit copies itself outward until it fills a grid | one element, staggered clones from its position |
| sync / integration | meshing gears | separate gears slide together, teeth catch, all turn as one | SVG gears, rotation ratios by tooth count, start on contact |
| connection / network | nodes and threads | points appear, lines draw between them, a pulse travels the links | node pop, path draw, dot along path |
| handoff / trust | baton pass | an object passes from one hand or lane to the next without stopping | carrier handoff between two tracks |
| pipeline / flow | conveyor or pipe | items ride through stations and change at each one | items on a path, state swap at station x |
| transformation | machine or box | a rough shape goes in one side, a finished one comes out | occluder box, swap the shape while hidden |
| automation | repeating arm | a mechanism does the same task again and again without a hand | looped sub-timeline repeated on the master clock |
| chaos to order | snap to grid | scattered, rotated pieces fly into a clean aligned layout | seeded start positions and angles, shared end layout |
| simplification | untangling | a knotted line pulls straight | SVG path morph from a tangled path to a straight one |
| complexity / clutter | pile or tangle | items overlap and keep arriving until the frame is crowded | growing stack with jitter-free seeded offsets |
| overload | overflow | a container fills past its rim and spills | fill level tween, spill particles past the edge |
| accumulation / saving | filling jar or stack | coins or blocks drop in and the level climbs | stacked drops with settle, level line |
| waiting / delay | queue | a line of items shuffles forward one step at a time | row x steps with holds between |
| speed | streak | the subject leaves speed lines and a blurred trail | lines behind the motion vector, directional blur |
| breakthrough | wall cracking | a barrier fractures and the subject bursts through | crack path draw, pre-cut shards pushed outward |
| protection / security | shield or lock | a shell closes around the subject; attacks glance off | shield scale-in, deflected dots, lock shackle drop |
| isolation / sandbox | glass bubble | the subject sits inside a clear sphere; outside things bounce off | circle with sheen, collisions reflect at its radius |
| unlock / access | key and door | a key turns, a door or lid opens onto what was inside | key rotate, door `rotateY` on its hinge |
| dependency / chain reaction | dominoes | one tile tips and knocks the rest down in sequence | per-tile rotate with stagger from the pivot edge |
| layers / abstraction | stacked plates | thin layers separate vertically, each labelled | exploded view of flat panels in `translateZ` or y |
| decision / branching | forked path | a road splits; one branch lights up and the traveller takes it | path draw, highlight one branch, dot along it |
| journey / progress | road with milestones | a traveller moves past markers toward a goal | camera truck along a path, markers pop as passed |
| feedback loop | circular track | a pulse runs round a loop and changes something each lap | dot on a closed path, state change per lap |
| balance / trade-off | scale | two pans tip as weight moves from one side to the other | beam rotation from summed weights, pans hang level |
| memory / cache | shelf or drawer | a thing is put away, later pulled out instantly instead of fetched far | drawer x slide, second retrieval much shorter |
| fit / solution | puzzle piece | the missing piece turns and clicks into the gap | rotate + translate into the slot, small settle |
| signal from noise | tuning wave | a jagged waveform smooths into a clean wave | SVG path morph between noisy and clean |
| clarity / focus | lens | a blurry scene sharpens where a lens passes | masked sharp layer under a moving circle |
| spark / idea | ignition | a small point flashes and lights up the shapes around it | pulse ring, bloom, radial stagger of lit elements |
