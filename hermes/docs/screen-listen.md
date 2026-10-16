# Screen listen

The Assistant's ear on this Mac: what one allowed application is playing —
Discord by default, so a Go Live stream or a voice channel the user has open in
the Discord app — either listened to for a few minutes and returned as text, or
recorded as a session for hours and kept as a file the user can play back,
transcribe and share. It is the audio half of "look at that stream for me"; the picture half is
`computer_use` (a `capture` of the window), and joining the stream or channel
in the first place is `computer_use` too, after a deep link opens it. Nothing here touches the
Discord API, the user's Discord account ([discord-access.md](discord-access.md))
or the Assistant's Discord bot. Read it when changing the plugin or its helper.
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                      | Home                                                                  | Reader    |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------- | --------- |
| Helper: the only code that records — a Core Audio process tap, and ScreenCaptureKit for one window — in a tiny app | `engines/screen-listen/main.swift`, `Info.plist` | people |
| Built helper (ad-hoc signed, ignored)                                      | `local/screen-listen/ScreenListen.app`                                | plugin    |
| Engine manager (`install`, `status`, `grant`, `grant-screen`)              | `scripts/screen-listen.sh`                                            | people    |
| `screen_listen` tool (toolset `screen_listen`), allowlist, STT handoff     | `plugins/inspection/screen-listen/__init__.py`, `listen.py`           | Assistant |
| Recording sessions (start, status, stop, the kept files)                   | `plugins/inspection/screen-listen/record.py`                          | Assistant |
| Transcripts of kept recordings (a detached local-whisper job)              | `plugins/inspection/screen-listen/transcript.py`, `transcribe_job.py` | Assistant |
| When and how the Assistant uses it with `computer_use`                     | the plugin skill `screen-listen:discord-live`                         | Assistant |

## Why a process tap, and why an app

The helper taps the audio of specific processes (`CATapDescription` over the
process objects whose bundle id is the allowed app's or a `.helper` child of it),
so the recording holds that app's output and nothing else: not the microphone,
not other apps, not the screen. The consent macOS asks for is therefore only
**System Audio Recording** for everything audio, and there is no periodic
re-consent as with screen capture. A quick look at the picture comes from
`computer_use` already.

Video is the one opt-in beyond that. The helper's `capture` records **one
window of the allowed app** through ScreenCaptureKit (a desktop-independent
window filter: the window as composited for itself, so other windows over it,
notifications and the cursor are not in it), at a bounded frame rate and width
(10 fps, 1280 points by default: a screen share is not a film, and an hour
must stay in the hundreds of megabytes), with the app's own audio in the same
MP4 (`SCRecordingOutput`, H.264 + AAC, macOS 15). It never captures a
display. The consent for it is **Screen Recording**, asked only when video is
used (`grant-screen`), and it behaves unlike the audio one: macOS re-confirms
it periodically, and **a rebuilt ad-hoc helper is refused silently** — the stored
grant carries the earlier build's code requirement, the new one does not
match, and Screen Recording does not prompt again while System Settings still
shows the switch on. `grant-screen` therefore drops the stale grant
(`tccutil reset ScreenCapture <bundle id>`) and asks again; when macOS answers
with a notification instead of a dialog, the switch is flipped by hand in the
pane the script opens. Which window: the largest normal window of the app,
on-screen ones first, or the one whose title contains `--window`; the capture
ends with the window (`stopped_by` in the answer).

macOS attributes that consent to the _responsible process_. Spawned plainly
from the gateway the helper would inherit the gateway launcher's identity and the
dialog would name it; so the plugin launches the helper through
`open -W -n -g --stdout … -a ScreenListen.app`, which makes the helper its own
responsible process: the dialog says "Hermes Screen Listen", the grant sticks to
the helper, and a gateway update does not revoke it. The grant is stored
against the helper's designated code requirement. Signed ad hoc, that is the
hash of one build, so **a rebuild is a new identity and macOS asks once more**
(`install` says so; `grant` answers it on purpose rather than in the middle of
a listen). `scripts/screen-listen.sh identity` makes a self-signed
code-signing identity in the login keychain once ("Hermes Local Code
Signing": the certificate trusted for code signing in the user's trust
settings, which costs one login-password dialog; only `codesign` may use the
key unasked), and `install` signs with it when it exists. The requirement is
then `identifier "local.hermes.screen-listen" and certificate leaf = <that
certificate>`, which every later build satisfies, so the consents, audio and
screen, survive rebuilds (verified: a changed binary, no dialog, no switch).
Nothing is notarized or Apple-issued; the identity exists only on this Mac.

The helper is built with the system Swift toolchain for a minimum OS of 14.2
(the process tap API's floor). The minimum must stay at or below the host's
version: LaunchServices refuses to launch a bundle whose minimum OS is newer
than the host, silently from the plugin's side (`open` fails with -10825).

## Allowlist, bounds and state

- `screen_listen.apps` in the profile's `config.yaml` (name → bundle id)
  replaces the default `{discord: com.hnc.Discord}`; the tool refuses any other
  name. The gateway reads the file itself, so a change needs no restart.
- One recording is at most `screen_listen.max_seconds`, itself capped at 300 s,
  because the Assistant's tool deadline (960 s) must also cover transcription
  of what was recorded. One listen at a time (a lock in the state directory).
- Recordings live in `~/.local/state/hermes-screen-listen/` (0700) as 16-bit
  WAV and are deleted after transcription unless `keep=true` (then the path is
  returned) or transcription failed (kept for a retry, path returned); a kept
  recording older than seven days is removed at the next listen. `last.json`
  keeps the last outcome, success or failure, without its text for `status`.
- A silent recording (peak under 0.001), or one with under 1.5 s of sound in
  it (the helper counts 100 ms blocks above a small threshold as
  `active_seconds`: a join chime in a minute of silence is a loud peak but a
  fraction of a second; `too_little_sound` in the answer), returns no
  transcript and says so without calling STT — a speech model given
  near-silence invents stock phrases. A tap delivers nothing while its
  processes output nothing (and resumes by itself when they do), so zero
  frames from an app that was not playing is answered as `silent` + `idle`;
  only zero frames from an app that was playing points at a missing consent,
  and the tool says which command grants it. `grant` therefore listens to a
  speech synthesizer it starts, and takes twice: the take that raises the
  dialog gets no audio even when the answer is yes.
- Transcription is local by default (`screen_listen.stt: local`: the plugin's
  own faster-whisper job run to completion, model `screen_listen.stt_model`
  else `stt.local.model`, language `stt.local.language`; timestamped lines),
  because a listen is other people's speech and the chain's first tiers are
  cloud services. `screen_listen.stt: chain` uses the profile's STT chain
  instead (`stt.provider`, normally `stt-fallback`;
  [ops/audio-tooling.md](ops/audio-tooling.md)), faster when a cloud tier is
  up. Recording sessions always transcribe locally. The take is mono.
- The transcript is other people's speech and the tool says so: data to report
  on, never instructions. Inbound A2A requests never get the tool (the `a2a`
  platform toolset omits it and the handler refuses).

## Boundaries

- The app must be open and playing on this Mac: the user is a viewer, or the
  Assistant made the Mac one with `computer_use`. The tool never opens, joins
  or leaves anything; that choreography is the skill's
  (`screen-listen:discord-live`: resolve the channel with `discord_account`,
  open its deep link in the background, join, watch, listen, report, leave).
  The skill reads the app's controls from the accessibility tree by label in
  the app's own language rather than assuming positions, because Discord's UI
  changes. A channel the skill joins for the user has its microphone muted
  (Discord keeps the last mute state, so a join can open the room's audio to
  the channel); a channel the user is in themselves is left alone; deafening
  is never used, since it silences the very output the tap records.
- No approval card: a listen records only an allowed app the user asked to
  hear, for a bounded time, into a private folder. Widening the allowlist is a
  config change by the user, not something the Assistant can do.
- Not a monitor: nothing listens on its own. A listen is one bounded tool call;
  a recording session runs only between the user's start and stop (or its cap)
  and is announced as such.

## Recording sessions

A session is for a call or stream the user wants to keep whole: play back,
turn into minutes, share. It differs from a listen in three ways.

- **It outlives the tool call.** `record_start` launches the helper detached
  (`open` without `-W`) with `--progress`, waits only until the helper reports
  its pid, and returns; the helper records until `record_stop` sends it
  SIGTERM or `minutes` (at most 240, default 180) runs out. `record_status`
  reads the progress file: seconds so far and whether audio arrived in the
  last write (a silent, left or restarted app shows `receiving: false`; a
  restarted app is not followed, because the tap was built on its old
  processes). One session at a time; a helper that died without an answer is
  marked failed by the next action rather than blocking it.
- **The file is a deliverable.** `record_stop` reads the helper's answer,
  converts the mono WAV to a 64 kbps AAC m4a with ffmpeg (about 30 MB an
  hour), deletes the WAV and writes `recording.json` (app, title, times,
  seconds, peak, silence, the `tracks` list) beside it, under
  `screen_listen.record_dir` (default `~/Workspaces/.inbox/recordings/`, so
  the messaging plugins' attach roots reach it) in a folder named
  `<YYYYMMDD-HHMM>-<app>[-<title>]`. `recordings` lists them, with transcripts
  when present. A session that hit its cap is packed by the next
  `record_stop`. Session bookkeeping (progress, the helper's stdout, pid) stays
  in the state directory and is removed when packed.
- **It hears the other side only.** The tap is the app's output, so in a call
  the user's own voice is absent. `tracks` in `recording.json` is a list on
  purpose: a microphone track is the planned next entry, behind the
  Microphone consent, mixed into the same m4a.
- **Video is a second track, not a second recording.** `record_start` with
  `video: true` launches the helper's `capture` beside the audio helper (same
  cap, the app's window, `window` to pick one by title) writing `video.mp4`
  in the same folder; `record_stop` ends the capture first, then the audio,
  and keeps the MP4 as the helper finalized it (no re-encode; it holds the
  app's audio too, so it plays on its own). The audio stays the primary
  deliverable: a capture that cannot start (Screen Recording refused, no
  window) is reported in the start answer and the session goes on without
  it; a capture that ends early (the window closed) leaves a shorter video,
  said so at stop. `recording.json` names it as `video` and a `window` track;
  `recordings` lists it. The transcript is always from the audio track.
- **Its transcript is a job, not a call.** `transcribe` (by session `id` or
  folder `dir`) starts `transcribe_job.py` detached under the gateway's own
  interpreter and returns; called again it reports progress from
  `transcript.job.json` (`percent` and, once there is a pace, `eta_seconds`,
  so the caller waits about that long instead of guessing) and, once done,
  the files: `transcript.txt` (one line per segment, `[H:MM:SS] text`),
  `transcript.vtt` and `segments.json`, all beside the audio, so `recordings`
  lists them. The job uses local
  faster-whisper with the profile's `stt.local.model` and language (a `model`
  argument overrides, `small` for speed), not the STT chain: the recording is
  long and private and the cloud tiers cap uploads. Speakers are not labelled.
  A failed or finished job is reported, not rerun, unless `force`. Minutes are
  Writer's work from `transcript.txt`; sharing goes through the existing
  routes (the chat the user asked from, a messaging plugin's attachment, Drive).

Recording other people for an hour is a different act from a five-minute
listen: the skill requires that the user asked for this session and that it is
their meeting or announced to its participants, and the Assistant says when a
recording is running.

## Setup

```sh
hermes/scripts/screen-listen.sh identity      # once: a signing identity, so rebuilds keep their consents
hermes/scripts/screen-listen.sh install       # builds the helper (needs Xcode or its CLT)
hermes/scripts/screen-listen.sh grant         # records one second; answer the dialog once
hermes/scripts/screen-listen.sh grant-screen  # only for video: Screen Recording, see above
hermes/scripts/screen-listen.sh status        # built? which processes are playing audio
```

Then `screen-listen` in `plugins.enabled` and `screen_listen` in the Assistant's
toolsets (the example config has both) and a drained gateway restart.
