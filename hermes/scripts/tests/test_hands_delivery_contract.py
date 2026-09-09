"""Static handoff-policy consistency, not filesystem security enforcement."""

from pathlib import Path

import pytest
import yaml


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
                  ".agent/deliverables/<job>/", "video-plan", "music-plan",
                  "~/Workspaces/.deliverables/<job>/"):
        assert value in text
    assert "never reject or relocate" in text
    assert "beneath an existing parent" in text


@pytest.mark.parametrize("profile", HANDS)
def test_delivery_policy_does_not_expand_authority(profile):
    text = delivery(profile)
    assert "never a new Group" in text
    assert "exclusive-output and parent-exists checks still apply" in text
    assert "no upload consent, overwrite permission or managed-skill edits" in text


def test_creator_handoff_uses_the_same_nested_shape():
    text = (ROOT / "profiles/creator/skills/creator-pipeline/references/build/index.md").read_text()
    assert "<G>/.agent/deliverables/<job>/video-plan" in text
    assert "All three hands accept" in text
    assert "Do not relocate a valid Group-local request" in text
