import importlib.util
from pathlib import Path
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("whatsapp_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
READ_TOOLS = {"whatsapp_account_read", "whatsapp_chat_read", "whatsapp_contact_read", "whatsapp_grant_read"}
WRITES = (
    "whatsapp_message_send", "whatsapp_file_send", "whatsapp_file_save", "whatsapp_history_backfill",
    "whatsapp_chat_archive", "whatsapp_chat_mark", "whatsapp_chat_mute", "whatsapp_chat_pin",
    "whatsapp_message_delete", "whatsapp_message_edit", "whatsapp_message_react", "whatsapp_grant_create",
    "whatsapp_grant_revoke", "whatsapp_future_write", "whatsapp_future_read", "whatsapp_chat_read_all",
    "whatsapp_chat_unread",
)
CHAT_READS = {"method": "search", "query": "private words"}
ENV_NAMES = ("WHATSAPP_TOOLS_STATE_DIR", "WHATSAPP_TOOLS_GRANTS_DIR", "XDG_STATE_HOME", "HERMES_HOME",
             "HERMES_WHATSAPP_STATE")


class Ctx:
    def __init__(self):
        self.tools = {}
        self.hooks = []

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


# tmp_path is named after the test, so a test name holding an env-name text pattern (`wacli_`) would be blocked.
@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
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


def test_the_reads_are_exactly_the_four_named_ones():
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


def test_a_tool_added_later_fails_closed(monkeypatch):
    no_human(monkeypatch)
    assert blocked(gate("whatsapp_future_write", chat="1"))
    assert blocked(gate("whatsapp_future_read", chat="1"))
    assert blocked(gate("whatsapp_chat_read_all", chat="1"))      # a name that starts like a read is no read


def test_inbound_a2a_blocks_reads_and_writes(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in (*sorted(plugin.READS), *WRITES):
        assert gate(tool) == {"action": "block", "message": f"{tool} is not available to inbound A2A requests"}


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="whatsapp-tools-cli") is None
    assert gate("browser_click", ref="whatsapp_message_send") is None
    assert gate("signal_message_send", text="hi") is None
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "whatsapp-tools-cli service status",
    "whatsapp-tools login",
    "/opt/homebrew/bin/whatsapp-tools sync",
    "bash -c 'whatsapp-tools-cli service status'",
    "wacli chats list",
    "/opt/homebrew/bin/wacli chats list",
    "bash -c 'wacli auth'",
    "env WACLI_STORE_DIR=/tmp/x wacli sync",
    "npx @craftsamo/whatsapp-tools",
    "npx -y @craftsamo/whatsapp-tools@0.3.0 login",
    "npm exec @craftsamo/whatsapp-tools",
    "pnpm dlx @craftsamo/whatsapp-tools",
    "bunx @craftsamo/whatsapp-tools",
    "npm install -g @craftsamo/whatsapp-tools",
    "node ~/.hermes/plugins/whatsapp-tools/dist/cli.js",
    "node ~/.hermes/plugins/whatsapp-tools/dist/mcp.js",
    "node node_modules/@craftsamo/whatsapp-tools/dist/cli.js",
    "cat ~/.local/state/whatsapp-tools/default/wacli/session.db",
    "sqlite3 ~/.local/state/whatsapp-tools/default/wacli/wacli.db",
    "ls ~/.local/state/whatsapp-tools/default/outbox ~/.local/state/whatsapp-tools/grants",
    "ls ~/.local/state/whatsapp-tools/default/service.sock",
    "tail ~/Library/Logs/io.github.craft-agent.whatsapp-tools/default.log",
    "launchctl print gui/501/io.github.craft-agent.whatsapp-tools.default",
    "cat ~/Library/LaunchAgents/io.github.craft-agent.whatsapp-tools.default.plist",
    "~/Library/Application\\ Support/io.github.craft-agent.whatsapp-tools/whatsapp-tools-sync-default node x.js",
    "echo $WHATSAPP_TOOLS_STATE_DIR",
    "echo $WHATSAPP_TOOLS_GRANTS_DIR",
    "echo $WHATSAPP_TOOLS_GRANT_KEY",
    "ls ~/.wacli",
    "sqlite3 ~/.wacli/wacli.db .dump",
    "echo $WACLI_MEDIA_ROOTS",
    "ls ~/Library/Group\\ Containers/group.net.whatsapp.WhatsApp.shared",
    "ls ~/Library/Group\\ Containers/AB12CD34EF.net.whatsapp.WhatsApp.private",
    "ls ~/Library/Containers/net.whatsapp.WhatsApp/Data",
    "ls ~/Library/Application\\ Support/WhatsApp",
    'cat "~/Library/Application Support/WhatsApp/ChatStorage.sqlite"',
    "ls ~/.local/state/hermes-whatsapp",
    "sqlite3 $HERMES_WHATSAPP_STATE/outbox/x .dump",
    "ls $TMPDIR/hermes-wacli",
    "ls ~/.hermes/whatsapp-access",
    "cat ~/.hermes/profiles/assistant/whatsapp-access/head.json",
    "cat $HERMES_HOME/whatsapp-access/mandates/a.json",
    "cat ${HERMES_HOME}/whatsapp-access/uses.jsonl",
    "secret show WHATSAPP_MANDATE_KEY_work",
    "~/.config/hermes/launchd/whatsapp-access-launchctl.sh status",
    "bash hermes/launchd/whatsapp-access-launchctl.sh pair work +15551234567",
    "tail ~/Library/Logs/whatsapp-access-sync-work.log",
    "launchctl print gui/501/local.hermes.whatsapp-access.sync.work",
    "~/Library/Application\\ Support/hermes-whatsapp-access-sync node x.js",
])
def test_terminal_blocks_ways_around_the_tools(command):
    assert gate("terminal", command=command) == {"action": "block", "message": plugin.BYPASS_MESSAGE}


@pytest.mark.parametrize("command", [
    'grep -r "whatsapp tools" notes.md',
    "grep -n wacli notes.md",
    "ls ~/Workspaces/.inbox/whatsapp",
    "cat ~/Workspaces/.inbox/whatsapp/work/123/a.pdf",
    "cat whatsapp.md",
    "cat ~/Workspaces/whatsapp.md",
    "open whatsapp://send?phone=15551234567",
    'open "whatsapp://send?phone=15551234567&text=hi"',
    "open -b net.whatsapp.WhatsApp",
    "open -a WhatsApp",
    "cat ~/.wacli-notes.md",
    "git log -- hermes/plugins/guards/whatsapp-tools-guard",
    "ls /work/feat-hermes-whatsapp-tools",
    "ls /work/feat-whatsapp-tools-hermes/hermes",
    "cat /Users/x/Worktrees/dotconfig/feat-hermes-whatsapp-tools/hermes/docs/whatsapp-tools.md",
    "cat docs/whatsapp-tools.md",
    "cat docs/whatsapp-access.md",
    "ls hermes/plugins/messaging/whatsapp-access",
    "cat hermes/plugins/messaging/whatsapp-access/wa.py",
    "cat ~/.hermes/plugins/messaging/whatsapp-access/wa.py",
    "cat hermes/docs/whatsapp-access.md",
    "ls ~/.hermes/profiles/assistant/skills",
    "ls ~/.local/state",
    "ls ~/.local/state/*",
    "ls ~/.local/state*",
    "ls ~/.local/st*",
    "ls ~/.local/state/whatsapp-b*",
    "ls ~/Library/Application\\ Support/Other",
    "cd ~/.local/state && ls",
])
def test_terminal_allows_plain_work(command):
    assert gate("terminal", command=command) is None


@pytest.mark.parametrize("command", [
    "cd ~/.local/state && sqlite3 whatsapp-tools/default/wacli/wacli.db",
    "sqlite3 ~/.local/state//whatsapp-tools/default/wacli/wacli.db",
    "sqlite3 ~/.local/state/./whatsapp-tools/default/wacli/wacli.db",
    'sqlite3 ~/.local/state/"whatsapp-tools"/default/wacli/wacli.db',
    "sqlite3 ~/.local/state/whats''app-tools/default/wacli/wacli.db",
    "cd ~/.local/state && sqlite3 whatsapp-'tools'/default/wacli/wacli.db",
    "sqlite3 $HOME/.local/state/whatsapp-tools/default/wacli/wacli.db",
    "sqlite3 ${HOME}/.local/state/whatsapp-tools/default/wacli/wacli.db",
    "sqlite3 --db=~/.local/state//whatsapp-tools/default/wacli/wacli.db",
    "ls ~/.local/state/whatsapp-tool?",
    "cat ~/.local/state/whatsapp-tool*/default/wacli/session.db",
    "cat ~/.local/state/whatsapp-t?ols/default/wacli/session.db",
    "cat ~/.local/state/*tools/default/wacli/session.db",
    "cd ~/.local/state && ls whatsapp-tool?",
    "cat ~/Library/Logs/io.github.craft-agent.whatsapp-*/default.log",
    "cat ~/Library/LaunchAgents/io.github.craft-agent.whatsapp-*.plist",
    "cat ~/.hermes/profiles/assistant/plugins/whatsapp-t*ls/dist/cli.js",
    "(cd ~/.hermes/plugins && cat whatsapp-tools/package.json)",
    "bash -c 'cd ~/.hermes/profiles/assistant/plugins; cat whatsapp-tools/package.json'",
    "cd ~/.hermes/profiles && cat assistant/whatsapp-access/head.json",
    "cat ~/.hermes/profiles/*/whatsapp-acce*/head.json",
    "tail ~/Library/Logs/whatsapp-access-sy*",
    "cat ~/.config/hermes/launchd/whatsapp-access-launch*",
    "ls ~/.local/state/hermes-whats*",
])
def test_terminal_blocks_single_line_forms(command):
    assert blocked(gate("terminal", command=command)), command


def test_a_link_in_a_word_is_followed(monkeypatch, isolated):
    state = isolated / "state-dir"
    state.mkdir()
    (isolated / "elsewhere").symlink_to(state)
    assert gate("terminal", command=f"cat {isolated}/elsewhere/default") is None
    monkeypatch.setenv("WHATSAPP_TOOLS_STATE_DIR", str(state))
    assert blocked(gate("terminal", command=f"cat {isolated}/elsewhere/default"))


def tracked(monkeypatch, cwd):
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": str(cwd))


def test_the_terminal_directory_kept_between_calls_is_judged(monkeypatch, isolated):
    home = isolated / "home"
    assert gate("terminal", command="cd ~/.local/state") is None            # call 1: nothing named yet
    tracked(monkeypatch, home / ".local" / "state")
    assert blocked(gate("terminal", command="cd whatsapp-tools"))           # call 2
    assert blocked(gate("terminal", command="sqlite3 whatsapp-tools/default/wacli/wacli.db"))
    assert blocked(gate("terminal", command="ls hermes-whatsapp"))
    assert gate("terminal", command="ls") is None


def test_a_terminal_inside_a_protected_directory_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "whatsapp-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    directive = gate("terminal", command="node dist/cli.js run whatsapp_message_send")
    assert directive == {"action": "block", "message": plugin.CWD_MESSAGE}
    assert blocked(gate("terminal", command="ls"))
    tracked(monkeypatch, install / "dist")
    assert blocked(gate("terminal", command="ls"))
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert blocked(gate("terminal", command="ls"))


def test_a_terminal_inside_the_client_store_or_the_app_data_is_blocked(monkeypatch, isolated):
    home = isolated / "home"
    for directory in (home / ".wacli", home / "Library" / "Application Support" / "WhatsApp",
                      home / "Library" / "Containers" / "net.whatsapp.WhatsApp" / "Data",
                      home / "Library" / "Group Containers" / "group.net.whatsapp.WhatsApp.shared"):
        directory.mkdir(parents=True)
        tracked(monkeypatch, directory)
        assert gate("terminal", command="ls") == {"action": "block", "message": plugin.CWD_MESSAGE}, directory


def test_a_terminal_inside_the_old_state_or_mandates_is_blocked(monkeypatch, isolated):
    old = isolated / "home" / ".local" / "state" / "hermes-whatsapp"
    mandates = isolated / "home" / ".hermes" / "profiles" / "assistant" / "whatsapp-access"
    scratch = isolated / "tmp" / "hermes-wacli"
    for cwd in (old, mandates, scratch):
        cwd.mkdir(parents=True)
        tracked(monkeypatch, cwd)
        assert gate("terminal", command="ls") == {"action": "block", "message": plugin.CWD_MESSAGE}, cwd


def test_a_terminal_in_the_inbox_or_the_old_source_is_not_blocked(monkeypatch, isolated):
    for cwd in (isolated / "home" / "Workspaces" / ".inbox" / "whatsapp",
                isolated / "home" / ".hermes" / "plugins" / "messaging" / "whatsapp-access"):
        cwd.mkdir(parents=True)
        tracked(monkeypatch, cwd)
        assert gate("terminal", command="ls") is None, cwd


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "whatsapp-tools"
    tracked(monkeypatch, install)
    assert gate("terminal", command="node dist/cli.js", workdir=str(isolated)) is None
    assert gate("terminal", command="ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command="ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".local" / "state")
    assert blocked(gate("terminal", command="ls", workdir="whatsapp-tools"))      # relative: the recorded one


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    state = isolated / "state-dir"
    (state / "default").mkdir(parents=True)
    monkeypatch.setenv("WHATSAPP_TOOLS_STATE_DIR", str(state))
    command = "cat state-dir/default/wacli/session.db"
    assert gate("terminal", command=command) is None            # no record of the directory: text checks only
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command=command))
    assert blocked(gate("terminal", command="cat default/wacli/session.db", workdir=str(state)))
    tracked(monkeypatch, isolated / "elsewhere")
    assert gate("terminal", command=command) is None
    assert gate("terminal", command='grep -r "whatsapp tools" notes.md') is None


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
    assert blocked(gate("terminal", command="ls", workdir="~/.local/state/whatsapp-tools"))


def test_file_tools_block_paths_by_text():
    for tool, args in (("read_file", {"path": "~/.local/state/whatsapp-tools/default/wacli/session.db"}),
                       ("write_file", {"path": "~/.hermes/plugins/whatsapp-tools/dist/cli.js", "content": "x"}),
                       ("search_files", {"pattern": "x", "path": "~/Library/Logs/io.github.craft-agent.whatsapp-tools"}),
                       ("read_file", {"path": "~/.local/state/whatsapp-tools/grants/work.json"}),
                       ("read_file", {"path": "~/.wacli/wacli.db"}),
                       ("read_file", {"path": "~/Library/Application Support/WhatsApp/ChatStorage.sqlite"}),
                       ("read_file", {"path": "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/x"}),
                       ("read_file", {"path": "~/Library/Containers/net.whatsapp.WhatsApp/Data/x"}),
                       ("read_file", {"path": "~/Library/Application Support/io.github.craft-agent.whatsapp-tools/x"}),
                       ("read_file", {"path": "~/Library/Logs/whatsapp-access-sync-work.log"}),
                       ("read_file", {"path": "~/.config/hermes/launchd/whatsapp-access-launchctl.sh"}),
                       ("read_file", {"path": "~/.hermes/whatsapp-access/mandates/a.json"}),
                       ("patch", {"path": "/tmp/x", "patch": "*** Update File: ~/.local/state/hermes-whatsapp/a"})):
        assert gate(tool, **args) == {"action": "block", "message": plugin.BYPASS_MESSAGE}, args


def test_file_tools_read_the_inbox():
    assert gate("search_files", pattern="x", path="~/Workspaces/.inbox/whatsapp") is None
    assert gate("read_file", path="~/Workspaces/.inbox/whatsapp/work/1/a.pdf") is None
    assert gate("read_file", path="~/Workspaces/whatsapp.md") is None


def test_file_tools_read_the_old_plugin_source_and_docs():
    assert gate("read_file", path="~/.hermes/plugins/messaging/whatsapp-access/wa.py") is None
    assert gate("read_file", path="hermes/plugins/messaging/whatsapp-access/wa.py") is None
    assert gate("read_file", path="hermes/docs/whatsapp-access.md") is None
    assert gate("search_files", pattern="x", path="hermes/plugins/messaging/whatsapp-access") is None


def test_file_tools_read_this_guard_and_a_worktree_with_the_package_name_in_it():
    assert gate("read_file", path="hermes/plugins/guards/whatsapp-tools-guard/__init__.py") is None
    path = "/x/Worktrees/dotconfig/feat-hermes-whatsapp-tools/hermes/docs/whatsapp-tools.md"
    assert gate("read_file", path=path) is None
    assert gate("terminal", command=f"cat {path}") is None


def test_file_tools_block_the_state_root_by_real_path(monkeypatch, isolated):
    state = isolated / "state-dir"      # no pattern names it: only its real path does
    (state / "default").mkdir(parents=True)
    (state / "default" / "service.json").write_text("x")
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("WHATSAPP_TOOLS_STATE_DIR", str(state))
    for path in (state / "default" / "service.json", state, link / "default" / "service.json", link,
                 isolated / "other" / ".." / "state-dir" / "default"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "state-dir-notes.txt")) is None


def test_file_tools_block_the_service_launcher_by_real_path(isolated):
    launchers = isolated / "home" / "Library" / "Application Support" / "io.github.craft-agent.whatsapp-tools"
    launchers.mkdir(parents=True)
    (launchers / "whatsapp-tools-sync-default").write_text("#!/bin/sh\nexec \"$@\"\n")
    link = isolated / "launchers"       # no pattern names it: only its real path does
    link.symlink_to(launchers)
    assert blocked(gate("write_file", path=str(link / "whatsapp-tools-sync-default"), content="x"))
    assert blocked(gate("read_file", path=str(link)))
    assert gate("read_file", path=str(isolated)) is None


def test_file_tools_block_a_launch_agent_by_real_path(isolated):
    agents = isolated / "home" / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / "io.github.craft-agent.whatsapp-tools.default.plist"
    plist.write_text("<plist/>")
    link = isolated / "agent.plist"     # no pattern names it: only its real path does
    link.symlink_to(plist)
    assert blocked(gate("write_file", path=str(link), content="x"))
    (agents / "com.example.other.plist").write_text("<plist/>")
    assert gate("read_file", path=str(agents / "com.example.other.plist")) is None


def test_the_xdg_state_root_is_protected(monkeypatch, isolated):
    state = isolated / "xdg" / "whatsapp-tools"
    state.mkdir(parents=True)
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(link / "default")))
    assert gate("read_file", path=str(isolated / "xdg" / "whatsapp-tools-notes.txt")) is None
    assert gate("read_file", path=str(isolated / "xdg")) is None


def test_a_relative_xdg_state_home_is_ignored_as_the_package_does(monkeypatch, isolated):
    default = str(isolated / "home" / ".local" / "state" / "whatsapp-tools")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", "relative/state")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", "~/state")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert plugin._state_root() == str(isolated / "xdg" / "whatsapp-tools")


def test_the_state_dir_variable_wins_over_xdg(monkeypatch, isolated):
    custom = isolated / "custom"
    custom.mkdir()
    monkeypatch.setenv("WHATSAPP_TOOLS_STATE_DIR", str(custom))
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(custom / "default" / "service.json")))
    assert gate("read_file", path=str(isolated / "xdg" / "other.txt")) is None


def test_the_grants_dir_variable_is_protected_through_a_link(monkeypatch, isolated):
    grants = isolated / "grants-dir"
    grants.mkdir()
    link = isolated / "elsewhere"
    link.symlink_to(grants)
    assert gate("read_file", path=str(link / "work.json")) is None      # not configured: an ordinary folder
    monkeypatch.setenv("WHATSAPP_TOOLS_GRANTS_DIR", str(grants))
    assert blocked(gate("read_file", path=str(link / "work.json")))
    assert blocked(gate("write_file", path=str(grants / "work.json"), content="x"))
    assert gate("read_file", path=str(isolated / "grants-dir-notes.txt")) is None


def test_the_default_grants_dir_is_inside_the_state_root(isolated):
    grants = isolated / "home" / ".local" / "state" / "whatsapp-tools" / "grants"
    grants.mkdir(parents=True)
    link = isolated / "elsewhere"
    link.symlink_to(grants)
    assert blocked(gate("read_file", path=str(link / "work.json")))


def test_the_installed_plugin_is_protected_through_a_link(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "whatsapp-tools"
    install.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(install)
    assert blocked(gate("read_file", path=str(link / "package.json")))


def test_the_client_store_is_protected_through_a_link(isolated):
    store = isolated / "home" / ".wacli"
    store.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(store)
    assert blocked(gate("read_file", path=str(link / "wacli.db")))
    assert gate("read_file", path=str(isolated / "home" / ".wacli-notes")) is None


def test_whatsapp_desktop_data_is_protected_through_a_link(isolated):
    library = isolated / "home" / "Library"
    directories = {
        "support": library / "Application Support" / "WhatsApp",
        "container": library / "Containers" / "net.whatsapp.WhatsApp",
        "group": library / "Group Containers" / "group.net.whatsapp.WhatsApp.shared",
        "team": library / "Group Containers" / "AB12CD34EF.net.whatsapp.WhatsApp.private",
    }
    for name, directory in directories.items():
        directory.mkdir(parents=True)
        link = isolated / f"{name}-link"
        link.symlink_to(directory)
        assert blocked(gate("read_file", path=str(link / "account-1"))), name
    assert gate("read_file", path=str(library / "Application Support" / "Other")) is None
    assert gate("read_file", path=str(library / "Group Containers" / "group.com.example.shared")) is None


def test_the_old_state_variable_moves_the_old_state_root(monkeypatch, isolated):
    old = isolated / "old-state"
    old.mkdir()
    link = isolated / "elsewhere"
    link.symlink_to(old)
    assert gate("read_file", path=str(link / "outbox")) is None
    monkeypatch.setenv("HERMES_WHATSAPP_STATE", str(old))
    assert blocked(gate("read_file", path=str(link / "outbox")))
    assert gate("read_file", path=str(isolated / "old-state-notes.txt")) is None


def test_the_old_scratch_dir_is_protected_through_a_link(isolated):
    scratch = isolated / "tmp" / "hermes-wacli"
    scratch.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(scratch)
    assert blocked(gate("read_file", path=str(link / "work.lock")))
    assert gate("read_file", path=str(isolated / "tmp" / "other.lock")) is None


def test_the_old_mandates_are_protected_through_a_link(monkeypatch, isolated):
    profile = isolated / "profile-home"
    (profile / "whatsapp-access").mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(profile / "whatsapp-access")
    assert gate("read_file", path=str(link / "head.json")) is None      # a home that is not the running one
    monkeypatch.setenv("HERMES_HOME", str(profile))
    assert blocked(gate("read_file", path=str(link / "head.json")))
    assert gate("read_file", path=str(profile / "config.yaml")) is None
    named = isolated / "home" / ".hermes" / "profiles" / "work" / "whatsapp-access"
    named.mkdir(parents=True)
    assert blocked(gate("read_file", path=str(named / "head.json")))    # any profile home, without the variable


def test_file_tools_read_the_download_dir(isolated):
    inbox = isolated / "home" / "Workspaces" / ".inbox" / "whatsapp" / "work" / "1" / "2"
    inbox.mkdir(parents=True)
    (inbox / "a.pdf").write_text("x")
    assert gate("read_file", path="~/Workspaces/.inbox/whatsapp/work/1/2/a.pdf") is None
    assert gate("read_file", path=str(inbox / "a.pdf")) is None
    assert gate("search_files", pattern="x", path="~/Workspaces/.inbox/whatsapp") is None


def test_unpacked_files_are_not_run():
    run = gate("terminal", command="bash ~/Workspaces/.inbox/whatsapp/work/1/2/a.zip.unpacked/run.sh")
    assert run == {"action": "block", "message": plugin.archives.RUN_MESSAGE}
    assert gate("terminal", command="cat ~/Workspaces/.inbox/whatsapp/work/1/2/a.zip.unpacked/data.json") is None


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "bypass", boom)
    assert gate("terminal", command="ls") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("read_file", path="a.txt") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("whatsapp_message_send", chat="1", text="hi") == {
        "action": "block",
        "message": plugin.UNCHECKED_MESSAGE,
    }
    assert gate("whatsapp_chat_mark", chat="1") == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("whatsapp_chat_read", **CHAT_READS) is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("whatsapp_file_send", files=["a"]) == {"action": "block", "message": plugin.UNCHECKED_MESSAGE}
    assert gate("whatsapp_account_read") is None
    assert gate("web_search", query="x") is None


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    assert line("whatsapp_message_send", chat="1", text="the private message") == "send"
    assert line("whatsapp_file_send", chat="1", files=["/secret.txt"], caption="the private message") == "send files"
    assert line("whatsapp_file_save", chat="1", id="a", unpack=True) == "save file"
    assert line("whatsapp_history_backfill", chat="1", count=50) == "fetch older messages"
    assert line("whatsapp_chat_archive", chat="1") == "archive"
    assert line("whatsapp_chat_mark", chat="1", read=True) == "mark"
    assert line("whatsapp_chat_mute", chat="1", hours=8) == "mute"
    assert line("whatsapp_chat_pin", chat="1") == "pin"
    assert line("whatsapp_message_delete", chat="1") == "delete"
    assert line("whatsapp_message_edit", text="the private message") == "edit"
    assert line("whatsapp_message_react", chat="1", reaction="👍") == "react"
    assert line("whatsapp_grant_create", chat="1", name="a private label") == "grant"
    assert line("whatsapp_grant_revoke", name="a private label") == "revoke grant"
    assert line("whatsapp_account_read", account="a private label") == "account"
    assert line("whatsapp_chat_read", **CHAT_READS) == "search"
    assert line("whatsapp_chat_read", method="around", query="private words") == "around"
    assert line("whatsapp_chat_read", method="private words", query="private words") is None
    assert line("whatsapp_contact_read", method="check", query="+15551234567") == "check"
    assert line("whatsapp_contact_read", query="private name") is None
    assert line("whatsapp_grant_read", method="log", account="a private label") == "log"


def test_every_tool_the_guard_names_gets_a_progress_line(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())
    assert set(display._PREVIEW_BUILDERS) == set(plugin.METHODS) | set(plugin.LABELS)
    assert set(plugin.METHODS) | {"whatsapp_account_read"} == plugin.READS
    assert not set(plugin.LABELS) & (plugin.READS - {"whatsapp_account_read"})


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
