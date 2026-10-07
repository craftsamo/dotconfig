"""Checkout paths for the Assistant pipeline tests.

The pipeline and these tests live in the public checkout, so the public tree
under test is always this checkout. The Assistant's config.yaml carries private
channel IDs and stays in the private overlay: name that checkout explicitly
with HERMES_PRIVATE_ROOT. An absent variable skips the config checks; an
invalid one fails. Nothing falls back to ~/.config/private or a live profile.
"""

import os
import unittest
from pathlib import Path


PUBLIC_ROOT = Path(__file__).resolve().parents[6]
_CONFIG = "hermes/profiles/assistant/config.yaml"


def private_config() -> Path:
    root = os.environ.get("HERMES_PRIVATE_ROOT")
    if root is None:
        raise unittest.SkipTest("Set HERMES_PRIVATE_ROOT to the paired private checkout")
    config = Path(root).expanduser() / _CONFIG
    if not config.is_file():
        raise FileNotFoundError(f"HERMES_PRIVATE_ROOT has no Assistant config: {config}")
    return config
