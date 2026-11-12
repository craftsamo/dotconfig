import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("signal_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
WRITES = (
    "signal_message_send", "signal_file_send", "signal_file_save", "signal_message_edit",
    "signal_message_delete", "signal_message_react", "signal_foo",
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
    monkeypatch.delenv("SIGNAL_TOOLS_STATE_DIR", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
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


def test_reads_pass_with_no_human(monkeypatch):
    no_human(monkeypatch)
    for tool in sorted(plugin.READS):
        assert gate(tool, method="list") is None


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_with_no_human(monkeypatch, tool):
    no_human(monkeypatch)
    directive = gate(tool, chat="x", text="hi")
    assert directive == {"action": "block", "message": plugin.human_gate.refusal(tool, "yolo mode is on")}


@pytest.mark.parametrize("tool", WRITES)
def test_writes_pass_with_a_human(tool):
    assert gate(tool, chat="x", text="hi") is None


def test_inbound_a2a_blocks_reads_and_writes(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in (*sorted(plugin.READS), *WRITES):
        assert gate(tool) == {"action": "block", "message": f"{tool} is not available to inbound A2A requests"}


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="signal-cli") is None
    assert gate("browser_click", ref="signal_message_send") is None
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "signal-cli -a x send -m hi +10000000000",
    "/opt/homebrew/bin/signal-cli -a x send -m hi +10000000000",
    "bash -c 'signal-tools-cli run signal_message_send'",
    "npx @craftsamo/signal-tools",
    "node ~/.hermes/plugins/signal-tools/dist/cli.js",
    "cat ~/.local/state/signal-tools/default/mirror.sqlite",
    "tail ~/Library/Logs/io.github.craft-agent.signal-tools/default.log",
    "launchctl print gui/501/io.github.craft-agent.signal-tools.default",
    "~/Library/Application\\ Support/io.github.craft-agent.signal-tools/signal-tools-sync-default node x.js",
    "echo $SIGNAL_TOOLS_STATE_DIR",
    "ls ~/.local/state/hermes-signal",
    "ls ~/.local/share/signal-cli",
    "ls ~/Library/Application\\ Support/Signal",
])
def test_terminal_blocks_ways_around_the_tools(command):
    assert gate("terminal", command=command) == {"action": "block", "message": plugin.BYPASS_MESSAGE}


@pytest.mark.parametrize("command", [
    'grep -r "signal tools" notes.md',
    "ls ~/Workspaces/.inbox/signal",
    "cat ~/Workspaces/.inbox/signal/123/a.txt",
    "git log -- hermes/plugins/guards/signal-tools-guard",
    "ls /work/feat-hermes-signal-tools",
    "cat /Users/x/Worktrees/dotconfig/feat-hermes-signal-tools/hermes/docs/signal-tools.md",
    "cat docs/signal-tools.md",
    "ls ~/.local/state",
    "ls ~/.local/state/*",
    "ls ~/.local/state*",
    "ls ~/.local/st*",
    "ls ~/.local/state/signal-a*",
    "cd ~/.local/state && ls",
])
def test_terminal_allows_plain_work(command):
    assert gate("terminal", command=command) is None


@pytest.mark.parametrize("command", [
    "cd ~/.local/state && sqlite3 signal-tools/default/mirror.sqlite",
    "sqlite3 ~/.local/state//signal-tools/default/mirror.sqlite",
    "sqlite3 ~/.local/state/./signal-tools/default/mirror.sqlite",
    'sqlite3 ~/.local/state/"signal-tools"/default/mirror.sqlite',
    "sqlite3 ~/.local/state/sig''nal-tools/default/mirror.sqlite",
    "cd ~/.local/state && sqlite3 signal-'tools'/default/mirror.sqlite",
    "sqlite3 $HOME/.local/state/signal-tools/default/mirror.sqlite",
    "sqlite3 ${HOME}/.local/state/signal-tools/default/mirror.sqlite",
    "sqlite3 --db=~/.local/state//signal-tools/default/mirror.sqlite",
    "ls ~/.local/state/signal-tool?",
    "cat ~/.local/state/signal-tool*/default/mirror.sqlite",
    "cat ~/.local/state/signal-t?ols/default/mirror.sqlite",
    "cat ~/.local/state/*tools/default/mirror.sqlite",
    "cd ~/.local/state && ls signal-tool?",
    "cat ~/Library/Logs/io.github.craft-agent.signal-*/default.log",
    "cat ~/.hermes/profiles/assistant/plugins/signal-t*ls/dist/cli.js",
    "(cd ~/.hermes/plugins && cat signal-tools/package.json)",
    "bash -c 'cd ~/.hermes/profiles/assistant/plugins; cat signal-tools/package.json'",
])
def test_terminal_blocks_single_line_forms(command):
    assert blocked(gate("terminal", command=command)), command


def test_a_link_in_a_word_is_followed(monkeypatch, isolated):
    state = isolated / "state-dir"
    state.mkdir()
    (isolated / "elsewhere").symlink_to(state)
    assert gate("terminal", command=f"cat {isolated}/elsewhere/default") is None
    monkeypatch.setenv("SIGNAL_TOOLS_STATE_DIR", str(state))
    assert blocked(gate("terminal", command=f"cat {isolated}/elsewhere/default"))


def tracked(monkeypatch, cwd):
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": str(cwd))


def test_the_terminal_directory_kept_between_calls_is_judged(monkeypatch, isolated):
    home = isolated / "home"
    assert gate("terminal", command="cd ~/.local/state") is None            # call 1: nothing named yet
    tracked(monkeypatch, home / ".local" / "state")
    assert blocked(gate("terminal", command="cd signal-tools"))             # call 2
    assert blocked(gate("terminal", command="sqlite3 signal-tools/default/mirror.sqlite"))
    assert gate("terminal", command="ls") is None


def test_a_terminal_inside_a_protected_directory_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "signal-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    directive = gate("terminal", command="node dist/cli.js run signal_message_send")
    assert directive == {"action": "block", "message": plugin.CWD_MESSAGE}
    assert blocked(gate("terminal", command="ls"))
    tracked(monkeypatch, install / "dist")
    assert blocked(gate("terminal", command="ls"))
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert blocked(gate("terminal", command="ls"))


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "signal-tools"
    tracked(monkeypatch, install)
    assert gate("terminal", command="node dist/cli.js", workdir=str(isolated)) is None
    assert gate("terminal", command="ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command="ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".local" / "state")
    assert blocked(gate("terminal", command="ls", workdir="signal-tools"))      # relative: the recorded one


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    state = isolated / "state-dir"
    (state / "default").mkdir(parents=True)
    monkeypatch.setenv("SIGNAL_TOOLS_STATE_DIR", str(state))
    command = "cat state-dir/default/mirror.sqlite"
    assert gate("terminal", command=command) is None            # no record of the directory: text checks only
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command=command))
    assert blocked(gate("terminal", command="cat default/mirror.sqlite", workdir=str(state)))
    tracked(monkeypatch, isolated / "elsewhere")
    assert gate("terminal", command=command) is None
    assert gate("terminal", command='grep -r "signal tools" notes.md') is None


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
    assert blocked(gate("terminal", command="ls", workdir="~/.local/state/signal-tools"))


def test_file_tools_block_paths_by_text(isolated):
    for tool, args in (("read_file", {"path": "~/.local/state/signal-tools/default/mirror.sqlite"}),
                       ("write_file", {"path": "~/.hermes/plugins/signal-tools/dist/cli.js", "content": "x"}),
                       ("search_files", {"pattern": "x", "path": "~/Library/Logs/io.github.craft-agent.signal-tools"}),
                       ("patch", {"path": "/tmp/x", "patch": "*** Update File: ~/.local/state/hermes-signal/a"})):
        assert gate(tool, **args) == {"action": "block", "message": plugin.BYPASS_MESSAGE}


def test_file_tools_block_the_state_root_by_real_path(monkeypatch, isolated):
    state = isolated / "state-dir"      # no pattern names it: only its real path does
    (state / "default").mkdir(parents=True)
    (state / "default" / "mirror.sqlite").write_text("x")
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("SIGNAL_TOOLS_STATE_DIR", str(state))
    for path in (state / "default" / "mirror.sqlite", state, link / "default" / "mirror.sqlite", link,
                 isolated / "other" / ".." / "state-dir" / "default"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "state-dir-notes.txt")) is None


def test_file_tools_block_the_service_launcher_by_real_path(isolated):
    launchers = isolated / "Library" / "Application Support" / "io.github.craft-agent.signal-tools"
    launchers.mkdir(parents=True)
    (launchers / "signal-tools-sync-default").write_text("#!/bin/sh\nexec \"$@\"\n")
    link = isolated / "launchers"       # no pattern names it: only its real path does
    link.symlink_to(launchers)
    assert blocked(gate("write_file", path=str(link / "signal-tools-sync-default"), content="x"))
    assert blocked(gate("read_file", path=str(link)))
    assert gate("read_file", path=str(isolated)) is None


def test_the_xdg_state_root_is_protected(monkeypatch, isolated):
    state = isolated / "xdg" / "signal-tools"
    state.mkdir(parents=True)
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(link / "default")))
    assert gate("read_file", path=str(isolated / "xdg" / "signal-tools-notes.txt")) is None
    assert gate("read_file", path=str(isolated / "xdg")) is None


def test_the_state_dir_variable_wins_over_xdg(monkeypatch, isolated):
    custom = isolated / "custom"
    custom.mkdir()
    monkeypatch.setenv("SIGNAL_TOOLS_STATE_DIR", str(custom))
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(custom / "default" / "mirror.sqlite")))
    assert gate("read_file", path=str(isolated / "xdg" / "other.txt")) is None


def test_the_installed_plugin_is_protected_through_a_link(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "signal-tools"
    install.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(install)
    assert blocked(gate("read_file", path=str(link / "package.json")))


def test_file_tools_read_the_download_dir(isolated):
    inbox = isolated / "home" / "Workspaces" / ".inbox" / "signal" / "1"
    inbox.mkdir(parents=True)
    (inbox / "a.txt").write_text("x")
    assert gate("read_file", path="~/Workspaces/.inbox/signal/1/a.txt") is None
    assert gate("read_file", path=str(inbox / "a.txt")) is None
    assert gate("search_files", pattern="x", path="~/Workspaces/.inbox/signal") is None


def test_unpacked_files_are_not_run():
    run = gate("terminal", command="bash ~/Workspaces/.inbox/signal/1/a.zip.unpacked/run.sh")
    assert run == {"action": "block", "message": plugin.archives.RUN_MESSAGE}
    assert gate("terminal", command="cat ~/Workspaces/.inbox/signal/1/a.zip.unpacked/data.json") is None


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "bypass", boom)
    assert gate("terminal", command="ls") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("read_file", path="a.txt") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("signal_message_send", chat="x", text="hi") == {
        "action": "block",
        "message": plugin.UNCHECKED_MESSAGE,
    }
    assert gate("signal_chat_read", **CHAT_READS) is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("signal_file_send", files=["a"]) == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("signal_account_read") is None
    assert gate("web_search", query="x") is None


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    assert line("signal_message_send", chat="someone's name", text="the private message") == "send"
    assert line("signal_file_send", files=["/secret.txt"], text="the private message") == "send files"
    assert line("signal_file_save", chat="c", id="1", unpack=True) == "save files"
    assert line("signal_message_edit", text="the private message") == "edit"
    assert line("signal_message_delete", chat="c") == "delete"
    assert line("signal_message_react", chat="c", text="👍") == "react"
    assert line("signal_account_read", account="a private label") == "account"
    assert line("signal_chat_read", **CHAT_READS) == "search"
    assert line("signal_chat_read", method="around", query="private words") == "around"
    assert line("signal_chat_read", method="private words", query="private words") is None
    assert line("signal_contact_read", method="check", numbers=["+10000000000"]) == "check"
    assert line("signal_contact_read", query="private name") is None


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
