"""The shared frame-rate list of the authored HyperFrames video leaves."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

HERMES_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = HERMES_ROOT / "profiles/video-creator/skills/video-creator-pipeline"

spec = importlib.util.spec_from_file_location("frame_rate", PIPELINE / "scripts/frame_rate.py")
frame_rate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frame_rate)


def test_allowed_rates_and_default():
    assert frame_rate.ALLOWED == (24, 25, 30, 50, 60)
    assert frame_rate.DEFAULT == 30 and frame_rate.describe() == "24/25/30/50/60"


@pytest.mark.parametrize("value, ok", [(24, True), (60, True), (30, True), (True, False), (60.0, False),
                                       ("60", False), (120, False), (240, False), (29, False), (None, False)])
def test_valid_accepts_only_allowed_integers(value, ok):
    assert frame_rate.valid(value) is ok


@pytest.mark.parametrize("value, expected", [("60", 60), (" 60 ", 60), ("'60'", 60), ('"25"', 25), (50, 50),
                                             ("29.97", None), ("120", None), ("240", None), ("", None),
                                             ("abc", None), (120, None), (None, None)])
def test_parse_text(value, expected):
    assert frame_rate.parse_text(value) == expected


@pytest.mark.parametrize("measured, expected", [(59.94, 60), (23.976, 24), (25.0, 25), (29.97, 30),
                                                (47.952, 50), (120.0, 60), (240.0, 60), (1.0, 24)])
def test_nearest_allowed_rate(measured, expected):
    assert frame_rate.nearest(measured) == expected


@pytest.mark.parametrize("rate, expected", [(60, 30), (50, 30), (30, 30), (25, 25), (24, 24)])
def test_drafts_are_capped_at_30(rate, expected):
    assert frame_rate.draft(rate) == expected

