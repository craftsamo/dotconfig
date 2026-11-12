import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("telegram_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
WRITES = (
    "telegram_message_send", "telegram_file_send", "telegram_file_save", "telegram_message_edit",
    "telegram_message_delete", "telegram_message_react", "telegram_message_pin", "telegram_sync_add",
    "telegram_sync_remove", "telegram_chat_mark_read", "telegram_foo", "telegram_chat_read_all",
    "telegram_chat_unread",
)
CHAT_READS = {"method": "search", "query": "private words"}


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
    for name in ("TELEGRAM_TOOLS_STATE_DIR", "XDG_STATE_HOME", "HERMES_HOME", "HERMES_TELEGRAM_STATE"):
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


def test_the_reads_are_exactly_the_three_named_ones():
    assert plugin.READS == {"telegram_account_read", "telegram_chat_read", "telegram_sync_read"}


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


def test_mark_read_is_a_write_though_its_name_ends_in_read(monkeypatch):
    no_human(monkeypatch)
    assert blocked(gate("telegram_chat_mark_read", chat="1"))
    assert [gate(tool, method="list") for tool in sorted(plugin.READS)] == [None] * 3


def test_inbound_a2a_blocks_reads_and_writes(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in (*sorted(plugin.READS), *WRITES):
        assert gate(tool) == {"action": "block", "message": f"{tool} is not available to inbound A2A requests"}


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="telegram-tools-cli") is None
    assert gate("browser_click", ref="telegram_message_send") is None
    assert gate("signal_message_send", text="hi") is None
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "telegram-tools-cli run telegram_message_send",
    "telegram-tools login",
    "/opt/homebrew/bin/telegram-tools sync",
    "bash -c 'telegram-tools-cli run telegram_message_send'",
    "npx @craftsamo/telegram-tools",
    "npx -y @craftsamo/telegram-tools@0.3.0 login",
    "npm exec @craftsamo/telegram-tools",
    "pnpm dlx @craftsamo/telegram-tools",
    "bunx @craftsamo/telegram-tools",
    "npm install -g @craftsamo/telegram-tools",
    "node ~/.hermes/plugins/telegram-tools/dist/cli.js",
    "node ~/.hermes/plugins/telegram-tools/dist/mcp.js",
    "node node_modules/@craftsamo/telegram-tools/dist/cli.js",
    "cat ~/.local/state/telegram-tools/default/session.sqlite",
    "cat ~/.local/state/telegram-tools/app.json",
    "sqlite3 ~/.local/state/telegram-tools/default/mirror.sqlite",
    "ls ~/.local/state/telegram-tools/default/incoming ~/.local/state/telegram-tools/default/kept",
    "ls ~/.local/state/telegram-tools/default/sync.sock",
    "tail ~/Library/Logs/io.github.craft-agent.telegram-tools/default.log",
    "launchctl print gui/501/io.github.craft-agent.telegram-tools.default",
    "cat ~/Library/LaunchAgents/io.github.craft-agent.telegram-tools.default.plist",
    "~/Library/Application\\ Support/io.github.craft-agent.telegram-tools/telegram-tools-sync-default node x.js",
    "echo $TELEGRAM_TOOLS_STATE_DIR",
    "ls ~/.local/state/hermes-telegram",
    "sqlite3 $HERMES_TELEGRAM_STATE/mirror.db .dump",
    "ls ~/.hermes/telegram-access",
    "cat ~/.hermes/profiles/assistant/telegram-access/head.json",
    "cat $HERMES_HOME/telegram-access/mandates/a.json",
    "cat ${HERMES_HOME}/telegram-access/uses.jsonl",
    "~/.config/hermes/launchd/telegram-access-launchctl.sh status",
    "bash hermes/launchd/telegram-access-launchctl.sh login",
    "tail ~/Library/Logs/telegram-access-sync.log",
    "ls ~/Library/Application\\ Support/Telegram\\ Desktop",
    "ls ~/Library/Group\\ Containers/AB12CD34EF.ru.keepcoder.Telegram",
])
def test_terminal_blocks_ways_around_the_tools(command):
    assert gate("terminal", command=command) == {"action": "block", "message": plugin.BYPASS_MESSAGE}


@pytest.mark.parametrize("command", [
    'grep -r "telegram tools" notes.md',
    "ls ~/Workspaces/.inbox/telegram",
    "cat ~/Workspaces/.inbox/telegram/123/456/a.txt",
    "git log -- hermes/plugins/guards/telegram-tools-guard",
    "ls /work/feat-hermes-telegram-tools",
    "ls /work/feat-telegram-tools-hermes/hermes",
    "cat /Users/x/Worktrees/dotconfig/feat-hermes-telegram-tools/hermes/docs/telegram-tools.md",
    "cat docs/telegram-tools.md",
    "cat docs/telegram-access.md",
    "ls hermes/plugins/messaging/telegram-access",
    "cat hermes/plugins/messaging/telegram-access/tg.py",
    "cat ~/.hermes/plugins/messaging/telegram-access/tg.py",
    "ls ~/.hermes/profiles/assistant/skills",
    "ls ~/.local/state",
    "ls ~/.local/state/*",
    "ls ~/.local/state*",
    "ls ~/.local/st*",
    "ls ~/.local/state/telegram-b*",
    "cd ~/.local/state && ls",
])
def test_terminal_allows_plain_work(command):
    assert gate("terminal", command=command) is None


@pytest.mark.parametrize("command", [
    "cd ~/.local/state && sqlite3 telegram-tools/default/mirror.sqlite",
    "sqlite3 ~/.local/state//telegram-tools/default/mirror.sqlite",
    "sqlite3 ~/.local/state/./telegram-tools/default/mirror.sqlite",
    'sqlite3 ~/.local/state/"telegram-tools"/default/mirror.sqlite',
    "sqlite3 ~/.local/state/tele''gram-tools/default/mirror.sqlite",
    "cd ~/.local/state && sqlite3 telegram-'tools'/default/mirror.sqlite",
    "sqlite3 $HOME/.local/state/telegram-tools/default/mirror.sqlite",
    "sqlite3 ${HOME}/.local/state/telegram-tools/default/mirror.sqlite",
    "sqlite3 --db=~/.local/state//telegram-tools/default/mirror.sqlite",
    "ls ~/.local/state/telegram-tool?",
    "cat ~/.local/state/telegram-tool*/default/session.sqlite",
    "cat ~/.local/state/telegram-t?ols/default/session.sqlite",
    "cat ~/.local/state/*tools/default/session.sqlite",
    "cd ~/.local/state && ls telegram-tool?",
    "cat ~/Library/Logs/io.github.craft-agent.telegram-*/default.log",
    "cat ~/Library/LaunchAgents/io.github.craft-agent.telegram-*.plist",
    "cat ~/.hermes/profiles/assistant/plugins/telegram-t*ls/dist/cli.js",
    "(cd ~/.hermes/plugins && cat telegram-tools/package.json)",
    "bash -c 'cd ~/.hermes/profiles/assistant/plugins; cat telegram-tools/package.json'",
    "cd ~/.hermes/profiles && cat assistant/telegram-access/head.json",
    "cat ~/.hermes/profiles/*/telegram-acce*/head.json",
])
def test_terminal_blocks_single_line_forms(command):
    assert blocked(gate("terminal", command=command)), command


def test_a_link_in_a_word_is_followed(monkeypatch, isolated):
    state = isolated / "state-dir"
    state.mkdir()
    (isolated / "elsewhere").symlink_to(state)
    assert gate("terminal", command=f"cat {isolated}/elsewhere/default") is None
    monkeypatch.setenv("TELEGRAM_TOOLS_STATE_DIR", str(state))
    assert blocked(gate("terminal", command=f"cat {isolated}/elsewhere/default"))


def tracked(monkeypatch, cwd):
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": str(cwd))


def test_the_terminal_directory_kept_between_calls_is_judged(monkeypatch, isolated):
    home = isolated / "home"
    assert gate("terminal", command="cd ~/.local/state") is None            # call 1: nothing named yet
    tracked(monkeypatch, home / ".local" / "state")
    assert blocked(gate("terminal", command="cd telegram-tools"))           # call 2
    assert blocked(gate("terminal", command="sqlite3 telegram-tools/default/mirror.sqlite"))
    assert blocked(gate("terminal", command="ls hermes-telegram"))
    assert gate("terminal", command="ls") is None


def test_a_terminal_inside_a_protected_directory_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "telegram-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    directive = gate("terminal", command="node dist/cli.js run telegram_message_send")
    assert directive == {"action": "block", "message": plugin.CWD_MESSAGE}
    assert blocked(gate("terminal", command="ls"))
    tracked(monkeypatch, install / "dist")
    assert blocked(gate("terminal", command="ls"))
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert blocked(gate("terminal", command="ls"))


def test_a_terminal_inside_the_old_state_or_mandates_is_blocked(monkeypatch, isolated):
    old = isolated / "home" / ".local" / "state" / "hermes-telegram"
    mandates = isolated / "home" / ".hermes" / "profiles" / "assistant" / "telegram-access"
    old.mkdir(parents=True)
    mandates.mkdir(parents=True)
    for cwd in (old, mandates):
        tracked(monkeypatch, cwd)
        assert gate("terminal", command="ls") == {"action": "block", "message": plugin.CWD_MESSAGE}


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "telegram-tools"
    tracked(monkeypatch, install)
    assert gate("terminal", command="node dist/cli.js", workdir=str(isolated)) is None
    assert gate("terminal", command="ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command="ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".local" / "state")
    assert blocked(gate("terminal", command="ls", workdir="telegram-tools"))      # relative: the recorded one


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    state = isolated / "state-dir"
    (state / "default").mkdir(parents=True)
    monkeypatch.setenv("TELEGRAM_TOOLS_STATE_DIR", str(state))
    command = "cat state-dir/default/session.sqlite"
    assert gate("terminal", command=command) is None            # no record of the directory: text checks only
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command=command))
    assert blocked(gate("terminal", command="cat default/session.sqlite", workdir=str(state)))
    tracked(monkeypatch, isolated / "elsewhere")
    assert gate("terminal", command=command) is None
    assert gate("terminal", command='grep -r "telegram tools" notes.md') is None


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
    assert blocked(gate("terminal", command="ls", workdir="~/.local/state/telegram-tools"))


def test_file_tools_block_paths_by_text():
    for tool, args in (("read_file", {"path": "~/.local/state/telegram-tools/default/session.sqlite"}),
                       ("write_file", {"path": "~/.hermes/plugins/telegram-tools/dist/cli.js", "content": "x"}),
                       ("search_files", {"pattern": "x", "path": "~/Library/Logs/io.github.craft-agent.telegram-tools"}),
                       ("read_file", {"path": "~/.local/state/telegram-tools/app.json"}),
                       ("read_file", {"path": "~/Library/Application Support/Telegram Desktop/tdata/key_datas"}),
                       ("read_file", {"path": "~/Library/Group Containers/AB12CD34EF.ru.keepcoder.Telegram/x"}),
                       ("read_file", {"path": "~/Library/Logs/telegram-access-sync.log"}),
                       ("read_file", {"path": "~/.config/hermes/launchd/telegram-access-launchctl.sh"}),
                       ("read_file", {"path": "~/.hermes/telegram-access/mandates/a.json"}),
                       ("patch", {"path": "/tmp/x", "patch": "*** Update File: ~/.local/state/hermes-telegram/a"})):
        assert gate(tool, **args) == {"action": "block", "message": plugin.BYPASS_MESSAGE}, args


def test_file_tools_read_the_old_plugin_source_and_docs():
    assert gate("read_file", path="~/.hermes/plugins/messaging/telegram-access/tg.py") is None
    assert gate("read_file", path="hermes/docs/telegram-access.md") is None
    assert gate("search_files", pattern="x", path="~/Workspaces/.inbox/telegram") is None


def test_file_tools_block_the_state_root_by_real_path(monkeypatch, isolated):
    state = isolated / "state-dir"      # no pattern names it: only its real path does
    (state / "default").mkdir(parents=True)
    (state / "default" / "session.sqlite").write_text("x")
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("TELEGRAM_TOOLS_STATE_DIR", str(state))
    for path in (state / "default" / "session.sqlite", state, link / "default" / "session.sqlite", link,
                 isolated / "other" / ".." / "state-dir" / "default"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "state-dir-notes.txt")) is None


def test_file_tools_block_the_service_launcher_by_real_path(isolated):
    launchers = isolated / "Library" / "Application Support" / "io.github.craft-agent.telegram-tools"
    launchers.mkdir(parents=True)
    (launchers / "telegram-tools-sync-default").write_text("#!/bin/sh\nexec \"$@\"\n")
    link = isolated / "launchers"       # no pattern names it: only its real path does
    link.symlink_to(launchers)
    assert blocked(gate("write_file", path=str(link / "telegram-tools-sync-default"), content="x"))
    assert blocked(gate("read_file", path=str(link)))
    assert gate("read_file", path=str(isolated)) is None


def test_file_tools_block_a_launch_agent_by_real_path(isolated):
    agents = isolated / "home" / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / "io.github.craft-agent.telegram-tools.default.plist"
    plist.write_text("<plist/>")
    link = isolated / "agent.plist"     # no pattern names it: only its real path does
    link.symlink_to(plist)
    assert blocked(gate("write_file", path=str(link), content="x"))
    (agents / "com.example.other.plist").write_text("<plist/>")
    assert gate("read_file", path=str(agents / "com.example.other.plist")) is None


def test_the_xdg_state_root_is_protected(monkeypatch, isolated):
    state = isolated / "xdg" / "telegram-tools"
    state.mkdir(parents=True)
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(link / "default")))
    assert gate("read_file", path=str(isolated / "xdg" / "telegram-tools-notes.txt")) is None
    assert gate("read_file", path=str(isolated / "xdg")) is None


def test_a_relative_xdg_state_home_is_ignored_as_the_package_does(monkeypatch, isolated):
    assert plugin._state_root() == str(isolated / "home" / ".local" / "state" / "telegram-tools")
    monkeypatch.setenv("XDG_STATE_HOME", "relative/state")
    assert plugin._state_root() == str(isolated / "home" / ".local" / "state" / "telegram-tools")
    monkeypatch.setenv("XDG_STATE_HOME", "~/state")
    assert plugin._state_root() == str(isolated / "home" / ".local" / "state" / "telegram-tools")
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert plugin._state_root() == str(isolated / "xdg" / "telegram-tools")


def test_the_state_dir_variable_wins_over_xdg(monkeypatch, isolated):
    custom = isolated / "custom"
    custom.mkdir()
    monkeypatch.setenv("TELEGRAM_TOOLS_STATE_DIR", str(custom))
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(custom / "default" / "session.sqlite")))
    assert gate("read_file", path=str(isolated / "xdg" / "other.txt")) is None


def test_the_old_state_variable_moves_the_old_state_root(monkeypatch, isolated):
    old = isolated / "old-state"
    old.mkdir()
    link = isolated / "elsewhere"
    link.symlink_to(old)
    assert gate("read_file", path=str(link / "mirror.db")) is None
    monkeypatch.setenv("HERMES_TELEGRAM_STATE", str(old))
    assert blocked(gate("read_file", path=str(link / "mirror.db")))
    assert gate("read_file", path=str(isolated / "old-state-notes.txt")) is None


def test_the_old_mandates_are_protected_through_a_link(monkeypatch, isolated):
    profile = isolated / "profile-home"
    (profile / "telegram-access").mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(profile / "telegram-access")
    assert gate("read_file", path=str(link / "head.json")) is None      # a home that is not the running one
    monkeypatch.setenv("HERMES_HOME", str(profile))
    assert blocked(gate("read_file", path=str(link / "head.json")))
    assert gate("read_file", path=str(profile / "config.yaml")) is None
    named = isolated / "home" / ".hermes" / "profiles" / "work" / "telegram-access"
    named.mkdir(parents=True)
    assert blocked(gate("read_file", path=str(named / "head.json")))    # any profile home, without the variable


def test_the_installed_plugin_is_protected_through_a_link(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "telegram-tools"
    install.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(install)
    assert blocked(gate("read_file", path=str(link / "package.json")))


def test_telegram_desktop_data_is_protected_through_a_link(isolated):
    desktop = isolated / "home" / "Library" / "Application Support" / "Telegram Desktop"
    container = isolated / "home" / "Library" / "Group Containers" / "AB12CD34EF.ru.keepcoder.Telegram"
    for directory in (desktop, container):
        directory.mkdir(parents=True)
    desktop_link = isolated / "desktop"
    container_link = isolated / "container"
    desktop_link.symlink_to(desktop)
    container_link.symlink_to(container)
    assert blocked(gate("read_file", path=str(desktop_link / "tdata")))
    assert blocked(gate("read_file", path=str(container_link / "account-1")))
    assert gate("read_file", path=str(isolated / "home" / "Library" / "Application Support" / "Other")) is None


def test_file_tools_read_the_download_dir(isolated):
    inbox = isolated / "home" / "Workspaces" / ".inbox" / "telegram" / "default" / "1" / "2"
    inbox.mkdir(parents=True)
    (inbox / "a.txt").write_text("x")
    assert gate("read_file", path="~/Workspaces/.inbox/telegram/default/1/2/a.txt") is None
    assert gate("read_file", path=str(inbox / "a.txt")) is None
    assert gate("search_files", pattern="x", path="~/Workspaces/.inbox/telegram") is None


def test_unpacked_files_are_not_run():
    run = gate("terminal", command="bash ~/Workspaces/.inbox/telegram/default/1/2/a.zip.unpacked/run.sh")
    assert run == {"action": "block", "message": plugin.archives.RUN_MESSAGE}
    assert gate("terminal", command="cat ~/Workspaces/.inbox/telegram/default/1/2/a.zip.unpacked/data.json") is None


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "bypass", boom)
    assert gate("terminal", command="ls") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("read_file", path="a.txt") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("telegram_message_send", chat="1", text="hi") == {
        "action": "block",
        "message": plugin.UNCHECKED_MESSAGE,
    }
    assert gate("telegram_chat_mark_read", chat="1") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("telegram_chat_read", **CHAT_READS) is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("telegram_file_send", files=["a"]) == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("telegram_account_read") is None
    assert gate("web_search", query="x") is None


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    assert line("telegram_message_send", chat="1", text="the private message") == "send"
    assert line("telegram_file_send", chat="1", files=["/secret.txt"], caption="the private message") == "send files"
    assert line("telegram_file_save", chat="1", id=2, unpack=True) == "save files"
    assert line("telegram_message_edit", text="the private message") == "edit"
    assert line("telegram_message_delete", chat="1") == "delete"
    assert line("telegram_message_react", chat="1", reaction="👍") == "react"
    assert line("telegram_message_pin", chat="1", id=2) == "pin"
    assert line("telegram_chat_mark_read", chat="1") == "mark read"
    assert line("telegram_sync_add", chat="-1000000000001") == "add to sync list"
    assert line("telegram_sync_remove", chat="-1000000000001") == "remove from sync list"
    assert line("telegram_account_read", account="a private label") == "account"
    assert line("telegram_chat_read", **CHAT_READS) == "search"
    assert line("telegram_chat_read", method="around", query="private words") == "around"
    assert line("telegram_chat_read", method="fetch", chat="1") == "fetch"
    assert line("telegram_chat_read", method="private words", query="private words") is None
    assert line("telegram_sync_read", method="list", account="a private label") == "list"
    assert line("telegram_sync_read", query="private name") is None


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
