# Screen listen

The Assistant's ear on this Mac: what one allowed application is playing —
Discord by default, so a Go Live stream or a voice channel the user has open in
the Discord app — recorded for a bounded time and returned as text. It is the
audio half of "look at that stream for me"; the picture half is
`computer_use` (cua-driver's `zoom` on the window), and opening the stream or
channel in the first place is `computer_use` too. Nothing here touches the
Discord API, the user's Discord account ([discord-access.md](discord-access.md))
or the Assistant's Discord bot. Read it when changing the plugin or its helper.
Part of the Hermes design docs — index: [`PROFILES.md`](../PROFILES.md).

## Shape

| Piece                                                                      | Home                                                        | Reader    |
| -------------------------------------------------------------------------- | ----------------------------------------------------------- | --------- |
| Helper: the only code that records, a Core Audio process tap in a tiny app | `engines/screen-listen/main.swift`, `Info.plist`            | people    |
| Built helper (ad-hoc signed, ignored)                                      | `local/screen-listen/ScreenListen.app`                      | plugin    |
| Engine manager (`install`, `status`, `grant`)                              | `scripts/screen-listen.sh`                                  | people    |
| `screen_listen` tool (toolset `screen_listen`), allowlist, STT handoff     | `plugins/inspection/screen-listen/__init__.py`, `listen.py` | Assistant |
| When and how the Assistant uses it with `computer_use`                     | the plugin skill `screen-listen:discord-live` (planned)     | Assistant |

## Why a process tap, and why an app

The helper taps the audio of specific processes (`CATapDescription` over the
process objects whose bundle id is the allowed app's or a `.helper` child of it),
so the recording holds that app's output and nothing else: not the microphone,
not other apps, not the screen. The consent macOS asks for is therefore only
**System Audio Recording**, never Screen Recording, and there is no periodic
re-consent as with screen capture. ScreenCaptureKit would have needed the wider
grant for no gain: the picture comes from `computer_use` already.

macOS attributes that consent to the _responsible process_. Spawned plainly
from the gateway the helper would inherit the gateway launcher's identity and the
dialog would name it; so the plugin launches the helper through
`open -W -n -g --stdout … -a ScreenListen.app`, which makes the helper its own
responsible process: the dialog says "Hermes Screen Listen", the grant sticks to
the helper, and a gateway update does not revoke it. The helper is ad-hoc
signed, so a **rebuild is a new identity and macOS asks once more**
(`scripts/screen-listen.sh install` says so; `grant` answers it on purpose
rather than in the middle of a listen). A real signing identity would make the
grant survive rebuilds; none is required.

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
- A silent recording (peak under 0.001) returns no transcript and says so
  without calling STT; zero frames delivered means the consent is missing and
  the tool says which command grants it.
- Transcription is the profile's own STT chain (`stt.provider`, normally
  `stt-fallback`; [ops/audio-tooling.md](ops/audio-tooling.md)), so the local
  faster-whisper floor works offline and the language hint is the chain's.
- The transcript is other people's speech and the tool says so: data to report
  on, never instructions. Inbound A2A requests never get the tool (the `a2a`
  platform toolset omits it and the handler refuses).

## Boundaries

- The app must be open and playing on this Mac: the user is a viewer, or the
  Assistant made the Mac one with `computer_use`. The tool never opens, joins
  or leaves anything; that choreography is the skill's.
- No approval card: a listen records only an allowed app the user asked to
  hear, for a bounded time, into a private folder. Widening the allowlist is a
  config change by the user, not something the Assistant can do.
- Not a monitor: there is no background or continuous listening; each listen is
  one bounded tool call.

## Setup

```sh
hermes/scripts/screen-listen.sh install   # builds the helper (needs Xcode or its CLT)
hermes/scripts/screen-listen.sh grant     # records one second; answer the dialog once
hermes/scripts/screen-listen.sh status    # built? which processes are playing audio
```

Then `screen-listen` in `plugins.enabled` and `screen_listen` in the Assistant's
toolsets (the example config has both) and a drained gateway restart.
