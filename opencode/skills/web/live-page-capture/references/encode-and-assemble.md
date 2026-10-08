# Encoding a stream-copyable body and proving frame identity

The goal: the body appears in the final video as the *same bytes* that were
captured, so the delivered video is provably the recording rather than a
re-render of it.

## Encode the frame sequence

Encode all-intra with pinned parameters. All-intra costs size but makes every
frame an independent cut point, so the body can be stream-copied into a
longer timeline and sliced anywhere without re-encoding.

```bash
ffmpeg -v error -y -framerate 30 -i frames/%04d.png \
  -frames:v <N> \
  -vf 'scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p' \
  -c:v libx264 -preset medium -qp 18 -profile:v high -level:v 5.0 \
  -bf 0 -g 1 -keyint_min 1 -sc_threshold 0 \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 \
  -video_track_timescale 15360 -an body.mp4
```

Why the unusual flags:

- `-bf 0` — no B-frames, so the final segment needs no future pictures and a
  cut at the end stays decodable.
- `-g 1 -keyint_min 1 -sc_threshold 0` — every frame an IDR; concat and
  stream-copy can start at any offset.
- `-video_track_timescale` fixed — concat demands matching timebases;
  mismatches show up as drift or a rejected join.
- `-an` — no audio stream at all, which is stronger than a silent one.

Segments composed around the body (title cards, curtains, holds) must use the
same parameters, or the concat will refuse to stream-copy and fall back to
re-encoding, destroying frame identity.

## Join without re-encoding

```bash
ffmpeg -v error -y -f concat -safe 0 -i concat.txt -c:v copy -an out.mp4
```

If this step needs `-c:v libx264` to succeed, the segments are not actually
compatible — fix the encode parameters rather than re-encoding the join.

## Prove frame identity

Compare decoded frame hashes, not file hashes, over **every** frame of the
body against the region of the output where the body is uncovered:

```bash
ffmpeg -v error -i body.mp4 -map 0:v:0 -pix_fmt yuv420p -f framehash -hash sha256 -
ffmpeg -v error -i out.mp4  -map 0:v:0 -pix_fmt yuv420p -f framehash -hash sha256 -
```

Align the body's hash list with the output's at the known offset and require
zero mismatches. Sampled comparison proves nothing about the frames between
samples; write the full per-frame comparison to a CSV as evidence.

## Conformance and content checks

- `ffprobe -v error -show_streams -show_format -of json <file>` — codec,
  pixel format, exact dimensions, frame rate, duration, and the absence of an
  audio stream.
- Full decode (`-f null -`) to catch truncated or corrupt frames.
- Blank/black frame detection across the whole output — a dropped capture
  frame or an unloaded image shows up as a flat or partially empty frame.
- Held stills: assert the intended frames hash identically to each other,
  which is what makes a "static" claim measurable.
