import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("discord_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
READ_TOOLS = {
    "discord_account_read", "discord_sync_read", "discord_chat_read", "discord_search_read",
    "discord_inbox_read", "discord_people_read", "discord_server_read", "discord_history_read",
    "discord_role_read", "discord_grant_read",
}
WRITES = (
    "discord_message_send", "discord_file_send", "discord_file_save", "discord_message_edit",
    "discord_message_delete", "discord_reaction_add", "discord_pin_add", "discord_sync_add",
    "discord_sync_remove", "discord_read_mark", "discord_role_assign", "discord_foo",
    "discord_future_write", "discord_future_read", "discord_chat_read_all", "discord_chat_unread",
)
CHAT_READS = {"method": "messages", "query": "private words"}


class Ctx:
    def __init__(self):
        self.tools = {}
        self.hooks = []

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for name in ("DISCORD_TOOLS_STATE_DIR", "XDG_STATE_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": None)   # no terminal record
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)     # a person is there to answer cards
    return tmp_path


def gate(tool, **args):
    return plugin.gate(tool_name=tool, args=args)


def blocked(directive):
    return isinstance(directive, dict) and directive["action"] == "block" and bool(directive["message"])


def no_human(monkeypatch, reason="yolo mode is on"):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)


def test_the_reads_are_exactly_the_ten_named_ones():
    assert plugin.READS == READ_TOOLS


def test_reads_pass_with_no_human(monkeypatch):
    no_human(monkeypatch)
    for tool in sorted(plugin.READS):
        assert gate(tool, method="list") is None


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_with_no_human(monkeypatch, tool):
    no_human(monkeypatch)
    directive = gate(tool, chat="1", text="hi")
    assert directive == {"action": "block", "message": plugin.human_gate.refusal(tool, "yolo mode is on")}


@pytest.mark.parametrize("tool", WRITES)
def test_writes_pass_with_a_human(tool):
    assert gate(tool, chat="1", text="hi") is None


def test_mark_read_is_a_write_though_its_name_contains_read(monkeypatch):
    no_human(monkeypatch)
    assert blocked(gate("discord_read_mark", chat="1"))
    assert [gate(tool, method="list") for tool in sorted(plugin.READS)] == [None] * len(READ_TOOLS)


def test_a_tool_added_later_fails_closed(monkeypatch):
    no_human(monkeypatch)
    assert blocked(gate("discord_future_write", chat="1"))
    assert blocked(gate("discord_future_read", chat="1"))


def test_inbound_a2a_blocks_reads_and_writes(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in (*sorted(plugin.READS), *WRITES):
        assert gate(tool) == {"action": "block", "message": f"{tool} is not available to inbound A2A requests"}


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="discord-tools-cli") is None
    assert gate("browser_click", ref="discord_message_send") is None
    assert gate("signal_message_send", text="hi") is None
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "discord-tools-cli run discord_message_send",
    "discord-tools login",
    "/opt/homebrew/bin/discord-tools sync",
    "bash -c 'discord-tools-cli run discord_message_send'",
    "npx @craftsamo/discord-tools",
    "npx -y @craftsamo/discord-tools@0.3.0 login",
    "npm exec @craftsamo/discord-tools",
    "pnpm dlx @craftsamo/discord-tools",
    "bunx @craftsamo/discord-tools",
    "npm install -g @craftsamo/discord-tools",
    "node ~/.hermes/plugins/discord-tools/dist/cli.js",
    "node ~/.hermes/plugins/discord-tools/dist/mcp.js",
    "node node_modules/@craftsamo/discord-tools/dist/cli.js",
    "cat ~/.local/state/discord-tools/default/token",
    "cat ~/.local/state/discord-tools/app.json",
    "sqlite3 ~/.local/state/discord-tools/default/mirror.sqlite",
    "ls ~/.local/state/discord-tools/default/incoming ~/.local/state/discord-tools/default/kept",
    "ls ~/.local/state/discord-tools/default/sync.sock",
    "tail ~/Library/Logs/io.github.craft-agent.discord-tools/default.log",
    "launchctl print gui/501/io.github.craft-agent.discord-tools.default",
    "cat ~/Library/LaunchAgents/io.github.craft-agent.discord-tools.default.plist",
    "~/Library/Application\\ Support/io.github.craft-agent.discord-tools/discord-tools-sync-default node x.js",
    "echo $DISCORD_TOOLS_STATE_DIR",
    "secret show DISCORD_USER_TOKEN -p hermes --scope discord-user",
    "ls ~/Library/Application\\ Support/discord",
    "ls ~/Library/Application\\ Support/discordcanary",
    "ls ~/Library/Application\\ Support/discordptb/Local\\ Storage",
    'cat "~/Library/Application Support/discord/Local Storage/leveldb/x.ldb"',
])
def test_terminal_blocks_ways_around_the_tools(command):
    assert gate("terminal", command=command) == {"action": "block", "message": plugin.BYPASS_MESSAGE}


@pytest.mark.parametrize("command", [
    'grep -r "discord tools" notes.md',
    "ls ~/Workspaces/.inbox/discord",
    "cat ~/Workspaces/.inbox/discord/123/456/a.txt",
    'open -g -b com.hnc.Discord "discord://-/channels/1/2"',
    "cat /x/Worktrees/dotconfig/feat-discord-tools-opencode/README.md",
    "git log -- hermes/plugins/guards/discord-tools-guard",
    "ls /work/feat-hermes-discord-tools",
    "ls /work/feat-discord-tools-hermes/hermes",
    "cat /Users/x/Worktrees/dotconfig/feat-hermes-discord-tools/hermes/docs/discord-tools.md",
    "cat docs/discord-tools.md",
    "ls ~/.hermes/profiles/assistant/skills",
    "ls ~/.local/state",
    "ls ~/.local/state/*",
    "ls ~/.local/state*",
    "ls ~/.local/st*",
    "ls ~/.local/state/discord-b*",
    "cd ~/.local/state && ls",
])
def test_terminal_allows_plain_work(command):
    assert gate("terminal", command=command) is None


@pytest.mark.parametrize("command", [
    "cd ~/.local/state && sqlite3 discord-tools/default/mirror.sqlite",
    "sqlite3 ~/.local/state//discord-tools/default/mirror.sqlite",
    "sqlite3 ~/.local/state/./discord-tools/default/mirror.sqlite",
    'sqlite3 ~/.local/state/"discord-tools"/default/mirror.sqlite',
    "sqlite3 ~/.local/state/disc''ord-tools/default/mirror.sqlite",
    "cd ~/.local/state && sqlite3 discord-'tools'/default/mirror.sqlite",
    "sqlite3 $HOME/.local/state/discord-tools/default/mirror.sqlite",
    "sqlite3 ${HOME}/.local/state/discord-tools/default/mirror.sqlite",
    "sqlite3 --db=~/.local/state//discord-tools/default/mirror.sqlite",
    "ls ~/.local/state/discord-tool?",
    "cat ~/.local/state/discord-tool*/default/token",
    "cat ~/.local/state/discord-t?ols/default/token",
    "cat ~/.local/state/*tools/default/token",
    "cd ~/.local/state && ls discord-tool?",
    "cat ~/Library/Logs/io.github.craft-agent.discord-*/default.log",
    "cat ~/Library/LaunchAgents/io.github.craft-agent.discord-*.plist",
    "cat ~/.hermes/profiles/assistant/plugins/discord-t*ls/dist/cli.js",
    "(cd ~/.hermes/plugins && cat discord-tools/package.json)",
    "bash -c 'cd ~/.hermes/profiles/assistant/plugins; cat discord-tools/package.json'",
])
def test_terminal_blocks_single_line_forms(command):
    assert blocked(gate("terminal", command=command)), command


def test_a_link_in_a_word_is_followed(monkeypatch, isolated):
    state = isolated / "state-dir"
    state.mkdir()
    (isolated / "elsewhere").symlink_to(state)
    assert gate("terminal", command=f"cat {isolated}/elsewhere/default") is None
    monkeypatch.setenv("DISCORD_TOOLS_STATE_DIR", str(state))
    assert blocked(gate("terminal", command=f"cat {isolated}/elsewhere/default"))


def tracked(monkeypatch, cwd):
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": str(cwd))


def test_the_terminal_directory_kept_between_calls_is_judged(monkeypatch, isolated):
    home = isolated / "home"
    assert gate("terminal", command="cd ~/.local/state") is None            # call 1: nothing named yet
    tracked(monkeypatch, home / ".local" / "state")
    assert blocked(gate("terminal", command="cd discord-tools"))            # call 2
    assert blocked(gate("terminal", command="sqlite3 discord-tools/default/mirror.sqlite"))
    assert gate("terminal", command="ls") is None


def test_a_terminal_inside_a_protected_directory_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "discord-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    directive = gate("terminal", command="node dist/cli.js run discord_message_send")
    assert directive == {"action": "block", "message": plugin.CWD_MESSAGE}
    assert blocked(gate("terminal", command="ls"))
    tracked(monkeypatch, install / "dist")
    assert blocked(gate("terminal", command="ls"))
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert blocked(gate("terminal", command="ls"))


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "discord-tools"
    tracked(monkeypatch, install)
    assert gate("terminal", command="node dist/cli.js", workdir=str(isolated)) is None
    assert gate("terminal", command="ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command="ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".local" / "state")
    assert blocked(gate("terminal", command="ls", workdir="discord-tools"))      # relative: the recorded one


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    state = isolated / "state-dir"
    (state / "default").mkdir(parents=True)
    monkeypatch.setenv("DISCORD_TOOLS_STATE_DIR", str(state))
    command = "cat state-dir/default/token"
    assert gate("terminal", command=command) is None            # no record of the directory: text checks only
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command=command))
    assert blocked(gate("terminal", command="cat default/token", workdir=str(state)))
    tracked(monkeypatch, isolated / "elsewhere")
    assert gate("terminal", command=command) is None
    assert gate("terminal", command='grep -r "discord tools" notes.md') is None


def test_the_hook_hands_its_ids_to_the_terminal_record(monkeypatch):
    asked = []
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": asked.append((task_id, session_id)))
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}, task_id="t1", session_id="s1") is None
    assert plugin.gate(tool_name="read_file", args={"path": "a.txt"}, task_id="t1", session_id="s1") is None
    assert asked == [("t1", "s1")]


def fake_runtime(monkeypatch, records, session_key="", broken=False):
    import sys
    import types

    def get_session_cwd(key):
        if broken:
            raise RuntimeError("no record")
        return records.get(key)

    modules = {"tools": types.ModuleType("tools"), "tools.approval": types.ModuleType("tools.approval"),
               "tools.terminal_tool": types.ModuleType("tools.terminal_tool")}
    modules["tools.approval"].get_current_session_key = lambda default="": session_key or default
    modules["tools.terminal_tool"].get_session_cwd = get_session_cwd
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def test_the_recorded_directory_is_read_as_the_terminal_tool_keys_it(monkeypatch):
    records = {"task-1": "/a", "sess-1": "/b", "key-1": "/c"}
    fake_runtime(monkeypatch, records)
    assert REAL_TRACKED_CWD("task-1", "sess-1") == "/a"
    assert REAL_TRACKED_CWD("", "sess-1") == "/b"
    assert REAL_TRACKED_CWD("other", "other") is None
    assert REAL_TRACKED_CWD() is None
    fake_runtime(monkeypatch, records, session_key="key-1")
    assert REAL_TRACKED_CWD("task-1", "sess-1") == "/c"
    fake_runtime(monkeypatch, records, broken=True)
    assert REAL_TRACKED_CWD("task-1", "sess-1") is None


def test_a_path_argument_of_the_terminal_is_judged_too():
    assert blocked(gate("terminal", command="ls", workdir="~/.local/state/discord-tools"))


def test_file_tools_block_paths_by_text():
    for tool, args in (("read_file", {"path": "~/.local/state/discord-tools/default/token"}),
                       ("write_file", {"path": "~/.hermes/plugins/discord-tools/dist/cli.js", "content": "x"}),
                       ("search_files", {"pattern": "x", "path": "~/Library/Logs/io.github.craft-agent.discord-tools"}),
                       ("read_file", {"path": "~/.local/state/discord-tools/app.json"}),
                       ("read_file", {"path": "~/Library/Application Support/discord/Local Storage/leveldb/x.ldb"}),
                       ("read_file", {"path": "~/Library/Application Support/discordcanary/Cookies"}),
                       ("read_file", {"path": "~/Library/Application Support/discordptb/Cookies"}),
                       ("read_file", {"path": "~/Library/Application Support/io.github.craft-agent.discord-tools/x"})):
        assert gate(tool, **args) == {"action": "block", "message": plugin.BYPASS_MESSAGE}, args


def test_file_tools_read_the_inbox():
    assert gate("search_files", pattern="x", path="~/Workspaces/.inbox/discord") is None
    assert gate("read_file", path="~/Workspaces/.inbox/discord/a.png") is None


def test_a_worktree_path_with_the_package_name_in_it_passes():
    path = "/x/Worktrees/dotconfig/feat-discord-tools-opencode/README.md"
    assert gate("read_file", path=path) is None
    assert gate("terminal", command=f"cat {path}") is None


def test_file_tools_block_the_state_root_by_real_path(monkeypatch, isolated):
    state = isolated / "state-dir"      # no pattern names it: only its real path does
    (state / "default").mkdir(parents=True)
    (state / "default" / "token").write_text("x")
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("DISCORD_TOOLS_STATE_DIR", str(state))
    for path in (state / "default" / "token", state, link / "default" / "token", link,
                 isolated / "other" / ".." / "state-dir" / "default"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "state-dir-notes.txt")) is None


def test_file_tools_block_the_service_launcher_by_real_path(isolated):
    launchers = isolated / "Library" / "Application Support" / "io.github.craft-agent.discord-tools"
    launchers.mkdir(parents=True)
    (launchers / "discord-tools-sync-default").write_text("#!/bin/sh\nexec \"$@\"\n")
    link = isolated / "launchers"       # no pattern names it: only its real path does
    link.symlink_to(launchers)
    assert blocked(gate("write_file", path=str(link / "discord-tools-sync-default"), content="x"))
    assert blocked(gate("read_file", path=str(link)))
    assert gate("read_file", path=str(isolated)) is None


def test_file_tools_block_a_launch_agent_by_real_path(isolated):
    agents = isolated / "home" / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / "io.github.craft-agent.discord-tools.default.plist"
    plist.write_text("<plist/>")
    link = isolated / "agent.plist"     # no pattern names it: only its real path does
    link.symlink_to(plist)
    assert blocked(gate("write_file", path=str(link), content="x"))
    (agents / "com.example.other.plist").write_text("<plist/>")
    assert gate("read_file", path=str(agents / "com.example.other.plist")) is None


def test_the_xdg_state_root_is_protected(monkeypatch, isolated):
    state = isolated / "xdg" / "discord-tools"
    state.mkdir(parents=True)
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(link / "default")))
    assert gate("read_file", path=str(isolated / "xdg" / "discord-tools-notes.txt")) is None
    assert gate("read_file", path=str(isolated / "xdg")) is None


def test_a_relative_xdg_state_home_is_ignored_as_the_package_does(monkeypatch, isolated):
    assert plugin._state_root() == str(isolated / "home" / ".local" / "state" / "discord-tools")
    monkeypatch.setenv("XDG_STATE_HOME", "relative/state")
    assert plugin._state_root() == str(isolated / "home" / ".local" / "state" / "discord-tools")
    monkeypatch.setenv("XDG_STATE_HOME", "~/state")
    assert plugin._state_root() == str(isolated / "home" / ".local" / "state" / "discord-tools")
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert plugin._state_root() == str(isolated / "xdg" / "discord-tools")


def test_the_state_dir_variable_wins_over_xdg(monkeypatch, isolated):
    custom = isolated / "custom"
    custom.mkdir()
    monkeypatch.setenv("DISCORD_TOOLS_STATE_DIR", str(custom))
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(custom / "default" / "token")))
    assert gate("read_file", path=str(isolated / "xdg" / "other.txt")) is None


def test_the_installed_plugin_is_protected_through_a_link(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "discord-tools"
    install.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(install)
    assert blocked(gate("read_file", path=str(link / "package.json")))


def test_discord_app_data_is_protected_through_a_link(isolated):
    support = isolated / "home" / "Library" / "Application Support"
    for name in ("discord", "discordcanary", "discordptb"):
        (support / name).mkdir(parents=True)
        link = isolated / f"{name}-link"
        link.symlink_to(support / name)
        assert blocked(gate("read_file", path=str(link / "Cookies"))), name
    assert gate("read_file", path=str(support / "Other")) is None


def test_file_tools_read_the_download_dir(isolated):
    inbox = isolated / "home" / "Workspaces" / ".inbox" / "discord" / "1" / "2"
    inbox.mkdir(parents=True)
    (inbox / "a.txt").write_text("x")
    assert gate("read_file", path="~/Workspaces/.inbox/discord/1/2/a.txt") is None
    assert gate("read_file", path=str(inbox / "a.txt")) is None
    assert gate("search_files", pattern="x", path="~/Workspaces/.inbox/discord") is None


def test_unpacked_files_are_not_run():
    run = gate("terminal", command="bash ~/Workspaces/.inbox/discord/1/2/a.zip.unpacked/run.sh")
    assert run == {"action": "block", "message": plugin.archives.RUN_MESSAGE}
    assert gate("terminal", command="cat ~/Workspaces/.inbox/discord/1/2/a.zip.unpacked/data.json") is None


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "bypass", boom)
    assert gate("terminal", command="ls") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("read_file", path="a.txt") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("discord_message_send", chat="1", text="hi") == {
        "action": "block",
        "message": plugin.UNCHECKED_MESSAGE,
    }
    assert gate("discord_read_mark", chat="1") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("discord_role_assign", user="1", role="2") == {
        "action": "block",
        "message": plugin.UNCHECKED_MESSAGE,
    }
    assert gate("discord_future_write", chat="1") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("discord_chat_read", **CHAT_READS) is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("discord_file_send", files=["a"]) == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("discord_account_read") is None
    assert gate("web_search", query="x") is None


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    assert line("discord_message_send", chat="1", text="the private message") == "send"
    assert line("discord_file_send", chat="1", files=["/secret.txt"], caption="the private message") == "send files"
    assert line("discord_file_save", chat="1", id=2, unpack=True) == "save files"
    assert line("discord_message_edit", text="the private message") == "edit"
    assert line("discord_message_delete", chat="1") == "delete"
    assert line("discord_reaction_add", chat="1", reaction="👍") == "react"
    assert line("discord_pin_add", chat="1", id=2) == "pin"
    assert line("discord_read_mark", chat="1") == "mark read"
    assert line("discord_sync_add", chat="1") == "add to sync list"
    assert line("discord_sync_remove", chat="1") == "remove from sync list"
    assert line("discord_role_assign", user="1", role="a private role") == "assign role"
    assert line("discord_grant_revoke", grant="a private grant") == "revoke grant"
    assert line("discord_account_read", account="a private label") == "account"
    assert line("discord_chat_read", **CHAT_READS) == "messages"
    assert line("discord_chat_read", method="around", query="private words") == "around"
    assert line("discord_chat_read", method="backfill", chat="1") == "backfill"
    assert line("discord_chat_read", method="private words", query="private words") is None
    assert line("discord_search_read", method="mirror", query="private words") == "mirror"
    assert line("discord_inbox_read", method="mentions") == "mentions"
    assert line("discord_people_read", method="members", server="1") == "members"
    assert line("discord_server_read", method="invites", server="1") == "invites"
    assert line("discord_history_read", method="counts") == "counts"
    assert line("discord_role_read", method="role", role="a private role") == "role"
    assert line("discord_sync_read", method="list", account="a private label") == "list"
    assert line("discord_sync_read", query="private name") is None


def test_every_declared_label_and_method_has_a_progress_line(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())
    for tool, label in plugin.LABELS.items():
        assert display.build_tool_preview(tool, {"text": "private"}, max_len=0) == label, tool
    for tool, methods in plugin.METHODS.items():
        for method in methods:
            assert display.build_tool_preview(tool, {"method": method}, max_len=0) == method, (tool, method)


def test_the_labels_and_methods_cover_known_tools_only():
    assert all(tool.startswith(plugin.PREFIX) for tool in (*plugin.LABELS, *plugin.METHODS))
    assert not set(plugin.LABELS) & set(plugin.METHODS)
    assert set(plugin.METHODS) <= plugin.READS


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
