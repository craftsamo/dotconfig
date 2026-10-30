"""Group folders under ~/Workspaces kept in Google Drive behind links into an rclone mount.

The engine is the stdlib module ``drive.py`` beside this file: the ``ws-drive`` launcher and
the LaunchAgent ``local.hermes.workspaces-drive.mount`` run it. This file registers nothing
yet. Design: docs/ops/workspaces-drive.md.
"""

from __future__ import annotations


def register(ctx):
    return None
