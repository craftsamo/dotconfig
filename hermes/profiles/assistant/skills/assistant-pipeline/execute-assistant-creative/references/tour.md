# Commission — video-creator: tour

Read [commissioning](../SKILL.md) first.

## Leaves

| Deliverable | Leaf | Notes |
| --- | --- | --- |
| a UI task walkthrough: recreate from reference/design/text, edit supplied local footage, or record an approved sanitized Web demo | `create-tour` | free, <=60 seconds; task-local source/preview/MP4, always kind="work"; free-text intro/outro default ON; explicit mode/proposal/scope gates, isolated Web wrapper only; native capture/login/privacy redaction unavailable; optional finished audio-creator WAV/words.json |

create-tour, create-ad and HyperFrames create-explainer-video
support opt-in graphics: three-webgl2 through their local Three graphics
contract, not a separate subject. you select it for actual depth or GLSL
surface requirements and verifies provisioning; no silent flat substitute.
It uses one procedural WebGL2 layer with pinned local Three/CLI/browser and
GSAP time. Addons, async asset loading, WebGPU and Motion Canvas combinations
remain outside that scope. Existing exact proposals and previews still apply.

## Choosing and filling

UI task walkthroughs use `create-tour`: fill what_for/audience and screen_mode
recreate/supplied/capture (omitted = recreate). Reference is inspiration/context,
source is provided actual local footage, target is a URL/app to operate.
Never demand per-step screenshots, the user's pixels/keystrokes or steps JSON.
Propose semantic steps from goal, audience and start_state; optional flow helps.
You own semantic flow and fidelity approval (faithful or explanatory simplified,
never invented real-product functions); VideoCreator owns task-local UI/motion
authoring. Frame/background style belongs to presentation, not blind UI reskinning.
Intro/outro default ON (title-reveal/result-hold). Offer the three reference
examples with `other: true`, not an exhaustive menu. Preserve custom directions
verbatim; unresolved ones need ONE question or concrete proposed beat.
Only explicit none omits, never absence/blank. The whole tour is <=60 seconds.
Pass `fps` (24/25/30/50/60) only when the user names a rate; omitted stays
30 and keeps earlier approvals matching.
URLs are context, not capture permission; sufficient text needs no image.
Explicit modes first propose proposal-vN.md + SHA-256. A target URL alone is
not consent: approve target/scope reconnaissance before access, then the
stateful actions/demo data/forbidden regions/budget before recording. VideoCreator
owns isolated sanitized Web capture through its wrapper, not your fallback.
Native capture, login recording and privacy redaction are unavailable; retain
the explicit mode and report its blocker. Supplied/captured video stays footage
with source-time mapping and explicit keep/mute. Old v1/v2 artifacts and approvals
remain unchanged. Narration is a prior
audio-creator delivery, not TTS in video-creator. Send tour work via
`specialist_call(kind="work")` even though free. Authored launch/promo/brand
motion is [create-promotion](promotion.md).

For a depth/shader requirement, the leaf's optional graphics: three-webgl2 is
an implementation choice to propose, not a new default. Read its local Three
contract and confirm installed support. It requires explicit screen_mode/v3
and approved preview even if preview=no was requested. Preserve faithful UI
and all design states; do not use a shader to reskin protected product pixels.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-tour` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; local snapshots/rendering and preview approval are not one-reply work |

## Round-trip and approvals

For create-tour, pass approved semantics and literal custom intro/outro/style
directions, not a screenshot-per-step manifest. VideoCreator authors the UI,
state changes and camera in task-local source, never managed helper scripts.
Preserve screen_mode and the reference/source/target distinction. For explicit
modes, relay exact proposal-vN.md + approval_sha256 only after the user's consent.
Consent to reconnaissance is not unlimited action consent. Capture's scope
covers target/origins, start state, allowed actions, dummy data, forbidden actions
and time/attempt ceilings. VideoCreator records through capture.py, not a shared
browser or you. No native capture or login/private-region fallback. Keep
raw takes, approval hashes and action evidence private. Confirm real moving media
and source-time mapping instead of screenshots; keep/mute audio must be explicit.
Ordinary narration uses finished audio-creator WAV/words.json inputs. For
`audio_workflow: mix`, first request preliminary timing from VideoCreator,
relay it to AudioCreator, then return the verified Mix bundle before formal
video approval. Its distinct captions.json preserves clean-speech evidence;
never reuse a speech-only words.json against the mixed WAV or play stems twice.
Preview returns a frozen source project and snapshots, not a finished MP4.
After the user's approval, continue that work conversation with `intent: revise`
and `preview: no`; the hands render the unchanged approved project into a
fresh final directory. Changed fields require a new source project/preview.
Never invoke raw A2A or resident scripts, nor edit the hands' HTML yourself.
Check that custom beats were actually rendered, not silently replaced by one
of the three examples. Explicit none is the only omission instruction.
