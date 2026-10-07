"""Static handoff-policy consistency, not filesystem security enforcement."""

from pathlib import Path

import pytest
import hermes_yaml as yaml


ROOT = Path(__file__).resolve().parents[2]
HANDS = ("image-creator", "video-creator", "audio-creator")


def delivery(profile):
    config = yaml.safe_load((ROOT / "profiles" / profile / "config.yaml").read_text())
    prompt = config["agent"]["system_prompt"]
    return " ".join(prompt.split("Deliver: accept", 1)[1].split("\n\n", 1)[0].split())


def test_all_hands_share_one_delivery_contract():
    assert len({delivery(profile) for profile in HANDS}) == 1


@pytest.mark.parametrize("profile", HANDS)
def test_existing_group_and_nested_job_paths_are_explicit(profile):
    text = delivery(profile)
    for value in ("~/Workspaces/Projects/<G>", "~/Workspaces/Personal/<G>",
                  ".agent/<YYYYMMDD>-<job>/", "video-plan", "music-plan",
                  "~/Workspaces/.agent/<YYYYMMDD>-<job>/"):
        assert value in text
    # The earlier layout was emptied on 2026-09-28; no hand may point back to it.
    for value in (".agent/deliverables/", ".deliverables/", ".scratch/", ".notes/"):
        assert value not in text
    assert "never reject or relocate" in text
    assert "beneath an existing parent" in text


@pytest.mark.parametrize("profile", HANDS)
def test_delivery_policy_does_not_expand_authority(profile):
    text = delivery(profile)
    assert "never a new Group" in text
    assert "exclusive-output and parent-exists checks still apply" in text
    assert "no upload consent, overwrite permission or managed-skill edits" in text


def test_assistant_handoff_uses_the_same_nested_shape():
    text = " ".join((
        ROOT / "profiles/assistant/skills/assistant-pipeline/execute-assistant-creative/SKILL.md"
    ).read_text().split())
    assert "`.agent/<YYYYMMDD>-<job>/` (or a job-owned subdirectory)" in text
    assert "`~/Workspaces/.agent/<YYYYMMDD>-<job>/`" in text
    assert "Never create a Group, relocate a valid Group-local job or overwrite an existing output" in text
    for value in (".agent/deliverables/", ".deliverables/", ".scratch/", ".notes/"):
        assert value not in text


def test_creator_does_not_dictate_delivery_paths():
    text = " ".join((
        ROOT / "profiles/creator/skills/creator-pipeline/SKILL.md"
    ).read_text().split())
    assert "leaves `deliver:` and `budget:` for the Assistant to fill when unknown" in text
    assert "Never write into a deliverable or a `deliver:` directory" in text
