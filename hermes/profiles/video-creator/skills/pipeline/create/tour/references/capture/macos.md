# macOS: Unavailable

Installed cua-driver 0.23.2 was inspected read-only on 2026-09-07.
`describe start_recording` exposes only output_dir and record_video. Its
continuous video records the **main display**, not an approved target window.
Per-action window screenshots are trajectory evidence, not moving footage.
Screen Recording and Accessibility were already granted to the driver daemon;
`permissions status --json` reported both true, with direct capture not checked.
No grant, direct-capture probe, native action or recording was performed.

Refuse native capture. Do not infer a safe recording API from a TCC grant, use
full-desktop recording and crop later, enable broad computer_use, automate
Finder as a substitute, or delegate desktop recording to Assistant.

Enabling this path requires BOTH a proven window-scoped continuous recorder
and a target-enforcing cross-profile desktop action guard. The guard must cover
Assistant's existing computer_use as well as VideoCreator, with shared lease,
start/action/stop validation, interruption recovery and exact state restoration.
A video-only lock would not stop Assistant moving the same desktop concurrently.
Any permission change, toolset/plugin activation or gateway restart is a
separate user-approved operation. Until then offer sanitized supplied footage,
or propose an explicit mode change to recreate; never change it silently.
