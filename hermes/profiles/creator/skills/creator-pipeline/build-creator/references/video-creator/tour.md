# Build — video-creator: tour

Read [common build](../../SKILL.md) first.

## Transport

| Leaf | Transport |
| --- | --- |
| video-creator's `create-tour` | `specialist_call(target="video-creator", message=<the text>, kind="work")` even though free; local snapshots/rendering and preview approval are not one-reply work |

## Supervising

For create-tour, pass approved semantics and literal custom intro/outro/style
directions, not a screenshot-per-step manifest. VideoCreator authors the UI,
state changes and camera in task-local source, never managed helper scripts.
Preserve screen_mode and the reference/source/target distinction. For explicit
modes, relay exact proposal-vN.md + approval_sha256 only after client consent.
Consent to reconnaissance is not unlimited action consent. Capture's scope
covers target/origins, start state, allowed actions, dummy data, forbidden actions
and time/attempt ceilings. VideoCreator records through capture.py, not a shared
browser or Assistant. No native capture or login/private-region fallback. Keep
raw takes, approval hashes and action evidence private. Confirm real moving media
and source-time mapping instead of screenshots; keep/mute audio must be explicit.
Ordinary narration uses finished audio-creator WAV/words.json inputs. For
`audio_workflow: mix`, first request preliminary timing from VideoCreator,
relay it to AudioCreator, then return the verified Mix bundle before formal
video approval. Its distinct captions.json preserves clean-speech evidence;
never reuse a speech-only words.json against the mixed WAV or play stems twice.
Preview returns a frozen source project and snapshots, not a finished MP4.
After client approval, continue that work conversation with `intent: revise`
and `preview: no`; the hands render the unchanged approved project into a
fresh final directory. Changed fields require a new source project/preview.
Never invoke raw A2A or resident scripts, nor edit the hands' HTML yourself.
Check that custom beats were actually rendered, not silently replaced by one
of the three examples. Explicit none is the only omission instruction.
