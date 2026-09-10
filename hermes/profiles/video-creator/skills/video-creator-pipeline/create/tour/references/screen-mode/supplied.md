# Supplied Footage

Use local video/images as the actual picture, not as a reference to redraw.
VideoCreator inventories and writes the source manifest; the client need not
supply JSON. Never fetch media URLs or execute downloaded HTML. Raw video:
MP4/MOV/WebM/MKV, 0.1..300 seconds, <=512 MB each, <=1 GB selected inputs;
one video stream, <=4096 per side and <=8,847,360 pixels. Static PNG/JPEG/WebP
also work. Reject symlinks, traversal, rotation metadata and corrupt media.
Prepared assets are <=64 MB each, the frozen bundle <=128 MB, final <=60 s.

Before proposal approval write a local source manifest and put its SHA-256 in
`source_sha256`. Each clip has exactly these keys:

```json
{"clips":[{"id":"settings","path":"/absolute/private/demo.webm",
"sha256":"<actual SHA-256>","source_start":4,"duration":12,
"timeline_start":2,"audio":"mute"}]}
```

`audio` must be keep or mute; keep on a source without audio fails. Every
source range must exist. Retime/reverse playback is not supported by the helper;
cuts/reordering at 1x are. An image has source_start 0. Hashes and source-time
mapping stay in private job/project records, never the public final directory.

After client approval, prepare bounded, metadata-stripped assets:

```sh
python3 ${HERMES_SKILL_DIR}/scripts/footage.py --manifest <source.json> --out <source-dir>/assets/footage
```

The output must not exist. This full-decodes the originals and prepared video,
trims with ffmpeg, preserves or removes audio as explicitly requested, and
writes media.json. Copy no raw takes into source-dir. Keep source.json and the
originals available until freeze; frozen projects then stand alone.

Author the surrounding UI chrome/title/camera, with an actual media element for
every prepared clip. Do not put data-start on its plain wrapper. Example:

```html
<div id="screen">
  <video id="settings" class="clip" src="assets/footage/settings.mp4"
    muted playsinline data-start="2" data-duration="12" data-media-start="0"></video>
</div>
```

For keep, add exactly one unique-id `<audio>` using the same src, data-start,
data-duration and data-media-start. Video stays muted. HyperFrames owns playback;
never call play/pause or assign currentTime/playbackRate. No crossorigin.
Keep uses unity gain; volume/mute automation, mixing and ducking need a
separately approved finishing path and are not implemented by this helper.
Use a matching id-bearing timed `<img>` for supplied static images. Animate
the untimed wrapper for approved camera/crop moves, never fabricate UI changes.
Editorial highlights need a label; without event evidence do not claim an exact
cursor or keystroke reconstruction. Do not add a second cursor over one already
recorded. Refuse privacy redaction requests until a verified redaction path exists.

Freeze validates the approved manifest hash, original hashes, prepared mappings,
media elements and audio policy. Snapshot and inspect beginning/middle/end of
each range plus transition boundaries; test forward/reverse seeks and compare
decoded final frames to source times. Raster-text readability is visual QA,
not something the HTML contrast check proves. Audio listening remains separate.
