"""Offline mechanical text contracts, not model selection or policy enforcement.

Public candidate only. Configs are parsed with safe YAML, never Hermes' mutating
config loader; assertions/serialization use only the approved safe projection.
Existing role, engine, transport and approval suites own their broader contracts.
"""

from pathlib import Path
import re

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
HANDS = ("image-creator", "video-creator", "audio-creator")


def pipeline(profile):
    return ROOT / f"profiles/{profile}/skills/{profile}-pipeline"


def text(path):
    return path.read_text(encoding="utf-8")


def compact(value):
    return " ".join(value.split())


def block(value, tag):
    matches = re.findall(rf"<{tag}>\s*(.*?)\s*</{tag}>", value, re.DOTALL)
    assert len(matches) == 1, f"Expected one {tag} contract"
    return compact(matches[0])


@pytest.fixture(params=HANDS)
def hands_config(request):
    # Do not retain or expose model, plugin, secret helper or transport settings.
    config = yaml.safe_load(text(ROOT / f"profiles/{request.param}/config.yaml"))
    safe = {
        "system_prompt": config["agent"]["system_prompt"],
        "skills": {key: config["skills"][key]
                   for key in ("external_dirs", "template_vars", "inline_shell")},
    }
    return request.param, safe


def test_hands_config_safe_yaml_offline_mechanical(hands_config):
    profile, safe = hands_config
    assert set(safe) == {"system_prompt", "skills"}
    assert yaml.safe_load(yaml.safe_dump(safe)) == safe
    assert safe["skills"]["template_vars"] is True
    assert safe["skills"]["inline_shell"] is False
    expected = [f"~/.agents/skills/{name}" for name in (
        "hyperframes-core", "hyperframes-animation", "cut-the-curve", "oversized-cursor",
    )] if profile == "video-creator" else []
    assert safe["skills"]["external_dirs"] == expected


def test_hands_turn_and_option_contract_offline_mechanical(hands_config):
    profile, safe = hands_config
    prompt = compact(safe["system_prompt"])
    for required in (
        "On every inbound turn or completion",
        "before an action changes operation, subject or form/reference selections",
        "current request and retained approved job",
        f"Require the full `{profile}-pipeline` kernel, leaf and required selected references in current context",
        "reuse full bodies, never a past load, summary or preload marker",
        "Load missing bodies with skill_view",
        "If unchanged hides an unavailable body",
        "recover the canonical file with read_file",
        "if recovery fails, stop the affected action and report the missing instructions",
        "Reselection does not release a different leaf, scope or grant, restart production or reset spent attempts",
        "Return unreleased changes to Creator",
    ):
        assert required in prompt, required


@pytest.mark.parametrize("profile", HANDS)
def test_hands_owner_context_offline_mechanical(profile):
    context = block(text(pipeline(profile) / "SKILL.md"), "InstructionContext")
    for required in (
        f"For execution as {profile}",
        "on every inbound turn or completion",
        "before an action changes operation, subject or form options",
        "current request and retained approved job together",
        "new selection is not permission to expand the released work",
        "Return an unreleased change to Creator rather than substituting a leaf or grant",
        "does not turn Creator's inspection of a form into a hands run",
        "Clients read forms; only the owning hands executes the procedure",
        "Require the full kernel, selected leaf and required reference bodies in current context",
        "not a past load, summary or preload marker",
        "using the named leaf's file_path for its selected references",
        "Read only applicable options, not the whole reference tree",
        "Optional advisory references retain their existing fallback",
        "If skill_view returns unchanged but the earlier body is unavailable",
        "read_file on the canonical document",
        "`${HERMES_SKILL_DIR}/SKILL.md`",
        "`${HERMES_SKILL_DIR}/<verb>/<subject>/SKILL.md`",
        "references resolve from that leaf's directory",
        "document's owning skill root, not the last loaded skill",
        "Follow next_offset for a genuinely truncated read",
        "never use alternate paths or artificial ranges to evade deduplication",
        "If required instructions remain unavailable, stop the affected action",
        "Loading instructions never restarts production, restores spent attempts or changes approval, engine, inputs or budget",
        "Reuse surviving outputs and preserve the existing proposal/preview and revision gates",
    ):
        assert required in context, required


@pytest.mark.parametrize("leaf", ("tour", "ad", "explainer-video"))
def test_optional_hyperframes_fallback_offline_mechanical(leaf):
    root = pipeline("video-creator")
    policy = compact(text(root / "references/hyperframes.md"))
    document = text(root / f"create/{leaf}/SKILL.md")
    assert "hyperframes.md" in document
    assert "Optional advisory references retain their existing fallback" in block(
        text(root / "SKILL.md"), "InstructionContext",
    )
    for required in (
        "optional advisory background",
        "never a substitute for the leaf's own form, approvals or helper scripts",
        "If it is unavailable, unreadable, or its name resolves ambiguously",
        "continue with the local authoring reference for that topic",
        "This is not a blocker",
        "do not stop work solely because a reference is absent",
        "A real missing CLI/runtime dependency, or a failed approval/validation check, still blocks",
        "not a failure",
    ):
        assert required in policy, required
    # No fabricated availability response and no read of the external live store.
