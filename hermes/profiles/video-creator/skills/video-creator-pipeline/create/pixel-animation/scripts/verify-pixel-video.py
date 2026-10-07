#!/usr/bin/env python3
"""Verify pixel-video grid, palette, cadence, source identity, and loop seam."""

from __future__ import annotations

import argparse
import glob
import json
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image


def probe(path: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,codec_name,pix_fmt,color_range,color_space",
            "-show_entries", "format=duration", "-of", "json", path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def parse_grid(value: str) -> tuple[int, int]:
    try:
        width, height = (int(part) for part in value.lower().split("x", 1))
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("grid must be WxH") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("grid dimensions must be positive")
    return width, height


def load_source_frames(pattern: str, grid: tuple[int, int]) -> list[np.ndarray]:
    files = [Path(path) for path in sorted(glob.glob(pattern))]
    if not files:
        raise ValueError(f"source pattern matched no frames: {pattern}")
    frames: list[np.ndarray] = []
    for path in files:
        image = Image.open(path).convert("RGB")
        if image.size != grid:
            raise ValueError(f"source frame is {image.size}, expected {grid}: {path}")
        frames.append(np.asarray(image, dtype=np.uint8))
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--grid", type=parse_grid, required=True)
    parser.add_argument("--scale", type=int, required=True)
    parser.add_argument("--palette-max", type=int, required=True)
    parser.add_argument("--effective-fps", type=float, required=True)
    parser.add_argument("--container-fps", type=float, required=True)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--master", action="store_true")
    mode_group.add_argument("--compat", action="store_true")
    loop_group = parser.add_mutually_exclusive_group(required=True)
    loop_group.add_argument("--loop", action="store_true")
    loop_group.add_argument("--no-loop", action="store_true")
    parser.add_argument(
        "--source-pattern",
        help="native RGB frame glob; required to prove RGB-lossless master identity",
    )
    args = parser.parse_args()

    if args.scale <= 0 or args.palette_max <= 0:
        parser.error("--scale and --palette-max must be positive")
    if args.effective_fps <= 0 or args.container_fps <= 0:
        parser.error("fps values must be positive")
    if args.master and not args.source_pattern:
        parser.error("--master requires --source-pattern to prove RGB identity")
    if args.compat and args.source_pattern:
        parser.error("--source-pattern is reserved for --master verification")

    info = probe(args.video)
    stream = info["streams"][0]
    duration = float(info["format"]["duration"])
    width, height = int(stream["width"]), int(stream["height"])
    grid_w, grid_h = args.grid
    failures: list[str] = []

    scale_x, scale_y = width / grid_w, height / grid_h
    if scale_x != args.scale or scale_y != args.scale:
        failures.append(
            f"scale mismatch: output={scale_x:g}x{scale_y:g}, expected={args.scale}x"
        )

    actual_container_fps = float(Fraction(stream["r_frame_rate"]))
    if abs(actual_container_fps - args.container_fps) > 0.001:
        failures.append(
            f"container fps mismatch: {actual_container_fps:g} != {args.container_fps:g}"
        )
    if args.master:
        if stream.get("codec_name") != "h264":
            failures.append(f"master codec must be h264/libx264rgb, got {stream.get('codec_name')}")
        if stream.get("pix_fmt") not in {"gbrp", "gbrp10le", "gbrp12le"}:
            failures.append(f"master pixel format must be planar RGB, got {stream.get('pix_fmt')}")
        if stream.get("color_range") != "pc" or stream.get("color_space") != "gbr":
            failures.append(
                f"master must be full-range GBR, got range={stream.get('color_range')} "
                f"space={stream.get('color_space')}"
            )
    elif stream.get("pix_fmt") != "yuv420p":
        failures.append(f"compatibility pixel format must be yuv420p, got {stream.get('pix_fmt')}")

    print(
        f"container: {width}x{height} {stream['pix_fmt']} "
        f"{actual_container_fps:g}fps {duration:.3f}s"
    )
    print(f"grid: {grid_w}x{grid_h}; scale={scale_x:g}x{scale_y:g}")

    decoded_grid_frames: list[np.ndarray] = []
    palette_union: set[tuple[int, int, int]] = set()
    nonuniform_frames = 0
    with tempfile.TemporaryDirectory(prefix="verify-pixel-video-") as tmp:
        pattern = str(Path(tmp) / "frame-%06d.png")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", args.video, "-vsync", "0", pattern],
            check=True,
        )
        files = sorted(Path(tmp).glob("frame-*.png"))
        if not files:
            print("FAIL: no decoded frames")
            return 1

        valid_shape = (
            scale_x.is_integer()
            and scale_y.is_integer()
            and int(scale_x) > 0
            and int(scale_y) > 0
        )
        for file in files:
            pixels = np.asarray(Image.open(file).convert("RGB"), dtype=np.uint8)
            colors = np.unique(pixels.reshape(-1, 3), axis=0)
            palette_union.update(tuple(int(channel) for channel in color) for color in colors)

            if not valid_shape:
                decoded_grid_frames.append(
                    np.asarray(
                        Image.fromarray(pixels).resize(args.grid, Image.Resampling.NEAREST),
                        dtype=np.uint8,
                    )
                )
                continue

            sx, sy = int(scale_x), int(scale_y)
            blocks = pixels.reshape(grid_h, sy, grid_w, sx, 3).transpose(0, 2, 1, 3, 4)
            cells = blocks[:, :, 0, 0, :]
            if not np.all(blocks == cells[:, :, None, None, :]):
                nonuniform_frames += 1
            decoded_grid_frames.append(cells)

    print(f"palette: {len(palette_union)} colors across all frames")
    print(f"blocks: {nonuniform_frames} frames contain nonuniform scale blocks")
    if len(palette_union) > args.palette_max:
        failures.append(
            f"palette max exceeded: union {len(palette_union)} > {args.palette_max}"
        )
    if nonuniform_frames:
        failures.append(f"nearest-neighbor block invariant failed in {nonuniform_frames} frames")

    change_indices = [0]
    changed_frames = [decoded_grid_frames[0]]
    for index, frame in enumerate(decoded_grid_frames[1:], start=1):
        if not np.array_equal(frame, decoded_grid_frames[index - 1]):
            change_indices.append(index)
            changed_frames.append(frame)

    holds = np.diff(change_indices + [len(decoded_grid_frames)])
    expected_hold = args.container_fps / args.effective_fps
    if not expected_hold.is_integer():
        failures.append(
            f"container/effective fps ratio is non-integer: {expected_hold:g}"
        )
    elif np.any(holds != int(expected_hold)):
        failures.append(
            f"uneven frame holds: {sorted(set(int(value) for value in holds))}, "
            f"expected {int(expected_hold)}"
        )

    actual_effective_fps = len(changed_frames) / duration
    print(
        f"cadence: {len(changed_frames)} native changes; "
        f"effective={actual_effective_fps:.3f}fps; holds={sorted(set(holds.tolist()))}"
    )
    if abs(actual_effective_fps - args.effective_fps) > 0.01:
        failures.append(
            f"effective fps mismatch: {actual_effective_fps:.3f} != {args.effective_fps:g}"
        )

    if len(changed_frames) < 2:
        failures.append("video has no visible native-grid motion")
    elif args.loop:
        step_diffs = np.array(
            [
                float(np.abs(b.astype(np.int16) - a.astype(np.int16)).mean())
                for a, b in zip(changed_frames, changed_frames[1:])
            ]
        )
        wrap_diff = float(
            np.abs(changed_frames[0].astype(np.int16) - changed_frames[-1].astype(np.int16)).mean()
        )
        seam_limit = max(float(np.percentile(step_diffs, 75)) * 1.5, 1e-9)
        print(
            f"loop: step median={np.median(step_diffs):.3f}; "
            f"p75={np.percentile(step_diffs, 75):.3f}; wrap={wrap_diff:.3f}; "
            f"limit={seam_limit:.3f}"
        )
        if wrap_diff > seam_limit:
            failures.append("loop seam exceeds robust frame-step range")

    if args.source_pattern:
        try:
            source_frames = load_source_frames(args.source_pattern, args.grid)
        except ValueError as error:
            failures.append(str(error))
        else:
            if len(source_frames) != len(changed_frames):
                failures.append(
                    f"source/output native frame count differs: "
                    f"{len(source_frames)} != {len(changed_frames)}"
                )
            else:
                mismatches = sum(
                    not np.array_equal(source, decoded)
                    for source, decoded in zip(source_frames, changed_frames)
                )
                print(f"source identity: {len(source_frames) - mismatches}/{len(source_frames)} exact")
                if mismatches:
                    failures.append(f"RGB master differs from source in {mismatches} native frames")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: pixel-video mechanical checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
