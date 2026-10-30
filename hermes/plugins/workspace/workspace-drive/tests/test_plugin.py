"""The workspace_drive tool: every profile reads status (Personal/ only for the Assistant), only the
Assistant moves and restores, each move or restore passes an approval card that names the folder and
its size and is refused where no person can answer, the approved call queues exactly what the card
showed, and terminal and file calls around the tool are blocked."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    """An isolated HOME with a stub `mount` reporting the Drive mount, and a Group to move from."""
    h = tmp_path / "home"
    stubs = h / "bin"
    stubs.mkdir(parents=True)
    (stubs / "mount").write_text('#!/bin/sh\necho "localhost:/ on $HOME/Workspaces/.drive (nfs, nobrowse)"\n')
    (stubs / "mount").chmod(0o755)
    data = h / "Workspaces" / "Projects" / "Alpha" / "data"
    data.mkdir(parents=True)
    (data / "a.csv").write_text("aa")
    (data / "b.csv").write_text("bbb")
    (h / "Workspaces" / "Personal").mkdir()
    (h / "Workspaces" / ".drive").mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("PATH", f"{stubs}:/usr/bin:/bin")
    monkeypatch.delenv("HERMES_LOCAL", raising=False)
    return h


@pytest.fixture
def plugin(home: Path, monkeypatch):
    """The plugin loaded fresh under the isolated HOME, with a person present to answer cards."""
    for name in ("hermes_workspace_drive", "workspace_drive_plugin"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("workspace_drive_plugin", PLUGIN / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.human_gate, "no_human", lambda: None)
    monkeypatch.setattr(module, "_inbound_peer", lambda: False)
    monkeypatch.setattr(module, "_watch", lambda job, task_id: {"watching": True})
    yield module
    sys.modules.pop("hermes_workspace_drive", None)


def gate(module, profile: str, tool: str, args: dict, call_id: str = "call-1"):
    return module.make_gate(profile)(tool_name=tool, args=args, tool_call_id=call_id)


def handle(module, profile: str, args: dict, call_id: str = "call-1", monkeypatch=None) -> dict:
    if monkeypatch is not None:
        monkeypatch.setattr(module, "_call_id", lambda: call_id)
    return json.loads(module.make_handler(profile)(args))


def test_only_the_assistant_is_offered_move_and_restore(plugin):
    assistant = plugin.schema_for("assistant")["parameters"]["properties"]
    other = plugin.schema_for("researcher")["parameters"]["properties"]
    assert assistant["action"]["enum"] == ["status", "move", "restore"] and "path" in assistant
    assert other["action"]["enum"] == ["status"] and "path" not in other


def test_a_move_asks_on_a_card_naming_the_folder_and_queues_what_it_showed(plugin, home, monkeypatch):
    args = {"action": "move", "path": "Projects/Alpha/data"}
    decision = gate(plugin, "assistant", "workspace_drive", args)
    assert decision["action"] == "approve" and decision["rule_key"].startswith("workspace-drive:move:")
    card = decision["message"]
    assert "Move to Drive" in card and "Projects/Alpha/data" in card and "2 files, 5 B" in card
    assert "readable in Drive's apps" in card
    done = handle(plugin, "assistant", args, monkeypatch=monkeypatch)
    assert done["ok"] is True and done["queued"]["path"] == "Projects/Alpha/data" and done["watching"] is True
    queue = list((home / ".hermes" / "local" / "workspaces-drive" / "queue").glob("*.json"))
    assert [json.loads(q.read_text())["kind"] for q in queue] == ["move"]
    # The job carries what the card showed, so the agent refuses it if the folder changes meanwhile.
    assert json.loads(queue[0].read_text())["expect"] == plugin.drive.plan_digest(
        plugin.drive.plan("move", "Projects/Alpha/data"))
    # The approval is consumed: the same call cannot queue twice.
    again = handle(plugin, "assistant", args, monkeypatch=monkeypatch)
    assert again["ok"] is False and "approval card" in again["error"]


def test_a_personal_folder_is_shown_as_encrypted(plugin, home):
    notes = home / "Workspaces" / "Personal" / "Notes" / "data"
    notes.mkdir(parents=True)
    (notes / "n.txt").write_text("n")
    decision = gate(plugin, "assistant", "workspace_drive", {"action": "move", "path": "Personal/Notes/data"})
    assert "On Drive: encrypted" in decision["message"]


def test_nothing_is_queued_without_the_card_or_after_the_folder_changed(plugin, home, monkeypatch):
    args = {"action": "move", "path": "Projects/Alpha/data"}
    assert "approval card" in handle(plugin, "assistant", args, monkeypatch=monkeypatch)["error"]
    gate(plugin, "assistant", "workspace_drive", args)
    (home / "Workspaces" / "Projects" / "Alpha" / "data" / "c.csv").write_text("new")
    changed = handle(plugin, "assistant", args, monkeypatch=monkeypatch)
    assert changed["ok"] is False and "changed after the card" in changed["error"]
    assert not (home / ".hermes" / "local" / "workspaces-drive" / "queue").exists()


@pytest.mark.parametrize("path, message", [
    ("Projects/Alpha/github", "repositories"),
    ("Projects/Alpha/.agent", "starts with '.'"),
    ("Projects/Alpha", "inside a Group"),
    ("Projects/Alpha/missing", "not a folder"),
])
def test_a_move_that_would_fail_is_blocked_without_asking(plugin, path, message):
    decision = gate(plugin, "assistant", "workspace_drive", {"action": "move", "path": path})
    assert decision["action"] == "block" and message in decision["message"]


def test_a_move_is_refused_where_no_person_can_answer(plugin, monkeypatch):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    decision = gate(plugin, "assistant", "workspace_drive", {"action": "move", "path": "Projects/Alpha/data"})
    assert decision["action"] == "block" and "cron job" in decision["message"]
    done = handle(plugin, "assistant", {"action": "move", "path": "Projects/Alpha/data"}, monkeypatch=monkeypatch)
    assert done["ok"] is False and "cron job" in done["error"]


def test_another_profile_cannot_move(plugin, monkeypatch):
    decision = gate(plugin, "researcher", "workspace_drive", {"action": "move", "path": "Projects/Alpha/data"})
    assert decision["action"] == "block" and "Assistant's" in decision["message"]
    done = handle(plugin, "researcher", {"action": "move", "path": "Projects/Alpha/data"}, monkeypatch=monkeypatch)
    assert done["ok"] is False


def test_status_shows_personal_folders_to_the_assistant_only(plugin, monkeypatch):
    sample = {"on_drive": ["Personal/Notes/assets", "Projects/Alpha/assets"], "local_assets": ["Personal/X/assets"],
              "foreign_links": [], "leftovers": [], "would_link": [],
              "interrupted": [{"path": "Personal/Notes/data", "kind": "move"}],
              "jobs": {"queued": [{"path": "Personal/Notes/data"}], "running": [], "recent": []}}
    monkeypatch.setattr(plugin.drive, "status_data", lambda: sample)
    mine = handle(plugin, "assistant", {"action": "status"})
    theirs = handle(plugin, "researcher", {"action": "status"})
    assert mine["on_drive"] == sample["on_drive"]
    assert theirs["on_drive"] == ["Projects/Alpha/assets"] and theirs["local_assets"] == []
    assert theirs["interrupted"] == [] and theirs["jobs"]["queued"] == []


def test_inbound_a2a_gets_nothing(plugin, monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate(plugin, "assistant", "workspace_drive", {"action": "status"})["action"] == "block"
    assert "A2A" in handle(plugin, "assistant", {"action": "status"})["error"]


@pytest.mark.parametrize("tool, args", [
    ("terminal", {"command": "ws-drive move Projects/Alpha/data"}),
    ("terminal", {"command": "~/.config/bin/ws-drive restore Projects/Alpha/data"}),
    ("terminal", {"command": "ws-drive restart"}),
    ("terminal", {"command": '"$HOME/.config/bin/ws-drive" move Projects/Alpha/data'}),
    ("terminal", {"command": "ws-drive 'move' Projects/Alpha/data"}),
    ("terminal", {"command": "ws-drive \\move Projects/Alpha/data"}),
    ("terminal", {"command": 'python -I "/x/workspace-drive/drive.py" restore Projects/Alpha/data'}),
    ("terminal", {"command": "cp request.json queue/job.json", "workdir": "~/.hermes/local/workspaces-drive"}),
    ("terminal", {"command": "tail ~/Library/Logs/workspaces-drive-mount.log"}),
    ("terminal", {"command": "python3 ~/.config/hermes/plugins/workspace/workspace-drive/drive.py move x"}),
    ("terminal", {"command": "rclone lsf wsdrive-crypt:Personal"}),
    ("terminal", {"command": "cp a.json ~/.hermes/local/workspaces-drive/queue/x.json"}),
    ("terminal", {"command": "ls ~/Workspaces/.drive/Projects"}),
    ("terminal", {"command": "cd ~/Workspaces && rm -rf .drive/Projects/Alpha"}),
    ("terminal", {"command": "launchctl unload ~/Library/LaunchAgents/local.hermes.workspaces-drive.mount.plist"}),
    ("terminal", {"command": "secret get WORKSPACES_DRIVE_CRYPT_PASSWORD -p hermes"}),
    ("execute_code", {"code": "open('/Users/x/.hermes/local/workspaces-drive/rclone.conf').read()"}),
    ("write_file", {"path": "~/.hermes/local/workspaces-drive/queue/x.json", "content": "{}"}),
    ("read_file", {"path": "/Users/x/Workspaces/.drive/Projects/Alpha/assets/a.png"}),
])
def test_ways_around_the_tool_are_blocked(plugin, tool, args):
    decision = gate(plugin, "assistant", tool, args)
    assert decision and decision["action"] == "block" and "workspace_drive" in decision["message"]


@pytest.mark.parametrize("tool, args", [
    ("terminal", {"command": "ws-drive status"}),
    ("terminal", {"command": "ws-drive status --json | jq .on_drive"}),
    ("terminal", {"command": "ls ~/Workspaces/Projects/Alpha/assets"}),
    ("terminal", {"command": "ffmpeg -i ~/Workspaces/Projects/Alpha/assets/clip.mov out.mp4"}),
    ("terminal", {"command": "cat docs/google.drive.md"}),
    ("read_file", {"path": "~/Workspaces/Projects/Alpha/assets/a.png"}),
    ("write_file", {"path": "~/Workspaces/Projects/Alpha/assets/out.png", "content": "x"}),
])
def test_ordinary_work_on_drive_folders_is_not_blocked(plugin, tool, args):
    assert gate(plugin, "assistant", tool, args) is None


def test_register_offers_the_skill_and_the_preview_to_the_assistant_only(plugin):
    class Ctx:
        def __init__(self, profile):
            self.profile_name = profile
            self.tools, self.hooks, self.skills = {}, [], []

        def register_tool(self, name, toolset, handler, description, schema, emoji):
            assert emoji and toolset == "workspace_drive"
            self.tools[name] = schema

        def register_hook(self, name, fn):
            self.hooks.append(name)

        def register_skill(self, name, path, description="", frontmatter=None):
            assert path.is_file() and frontmatter["name"] == name and len(description) <= 260
            self.skills.append(name)

    assistant, other = Ctx("assistant"), Ctx("writer")
    plugin.register(assistant)
    plugin.register(other)
    assert set(assistant.tools) == set(other.tools) == {"workspace_drive"}
    assert assistant.hooks == other.hooks == ["pre_tool_call"]
    assert assistant.skills == ["manage"] and other.skills == []
