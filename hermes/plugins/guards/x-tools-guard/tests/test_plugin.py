import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("x_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
READ_TOOLS = {
    "x_account_read", "x_post_read", "x_user_read", "x_list_read", "x_community_read", "x_trend_read",
    "x_grant_read",
}
KNOWN_WRITES = ("x_media_download", "x_grant_create", "x_grant_revoke")
WRITES = (*KNOWN_WRITES, "x_future_write", "x_future_read", "x_post_read_all", "x_unread")
ENV_NAMES = ("X_TOOLS_STATE_DIR", "X_TOOLS_GRANTS_DIR", "XDG_STATE_HOME", "TERMINAL_CWD")


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
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": None)   # no terminal record
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)     # a person is there to answer cards
    return tmp_path


def gate(tool, **args):
    return plugin.gate(tool_name=tool, args=args)


def blocked(directive):
    return isinstance(directive, dict) and directive["action"] == "block" and bool(directive["message"])


def block_with(message):
    return {"action": "block", "message": message}


def no_human(monkeypatch, reason="yolo mode is on"):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)


def tracked(monkeypatch, cwd):
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": str(cwd))


def test_the_reads_are_exactly_the_seven_named_ones():
    assert plugin.READS == READ_TOOLS
    assert len(READ_TOOLS) == 7


def test_every_read_passes_with_no_human_and_for_a_peer(monkeypatch):
    no_human(monkeypatch)
    for tool in sorted(plugin.READS):
        assert gate(tool, method="view") is None
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in sorted(plugin.READS):
        assert gate(tool, method="view") is None


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_with_no_human(monkeypatch, tool):
    no_human(monkeypatch)
    assert gate(tool, url="https://x.com/example/status/1") == block_with(
        plugin.human_gate.refusal(tool, "yolo mode is on"))


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_for_an_inbound_peer(monkeypatch, tool):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate(tool, url="https://x.com/example/status/1") == block_with(
        f"{tool} is not available to inbound A2A requests")


@pytest.mark.parametrize("tool", WRITES)
def test_writes_pass_with_a_human(tool):
    assert gate(tool, url="https://x.com/example/status/1") is None


def test_a_tool_added_later_fails_closed(monkeypatch):
    no_human(monkeypatch)
    assert blocked(gate("x_future_write"))
    assert blocked(gate("x_media_download", url="https://x.com/example/status/1"))
    assert blocked(gate("x_"))


def test_the_writes_listed_are_exactly_the_labelled_ones():
    assert set(plugin.LABELS) - {"x_account_read"} == set(KNOWN_WRITES)
    assert not set(KNOWN_WRITES) & plugin.READS


def test_hermes_x_search_is_left_alone_entirely(monkeypatch):
    assert plugin.OTHER_TOOLS == {"x_search"}
    assert not plugin._is_write("x_search")
    assert gate("x_search", query="private words") is None
    no_human(monkeypatch)
    assert gate("x_search", query="private words") is None
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("x_search", query="private words") is None


def test_x_search_passes_when_the_check_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("x_search", query="x") is None


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="x-tools-cli") is None
    assert gate("browser_click", ref="x_media_download") is None
    assert gate("x") is None
    assert gate("xa_post", text="hi") is None           # no underscore after the x: not this plugin's
    assert gate("signal_message_send", text="hi") is None
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "x-tools-cli engine install", "x-tools-cli login", "x-tools-cli remove work", "/opt/homebrew/bin/x-tools-cli login",
    "bash -c 'x-tools-cli login'", "sudo x-tools-cli engine install", "env CI=1 x-tools-cli login",
    "twscrape accounts", "twscrape search 'x' --limit 5", "./venv/bin/twscrape user_by_login example",
    "sudo twscrape accounts", "bash -c 'twscrape accounts'", "cd app && twscrape accounts",
    "python3 -c 'import twscrape'", "python3 -c 'from twscrape import API'", "python3 -m twscrape accounts",
    "python3 - <<'PY'\nimport twscrape\nPY",
    "curl https://api.fxtwitter.com/example/status/1", "curl https://fixupx.com/example/status/1",
    "open https://vxtwitter.com/example/status/1", "wget https://fixvx.com/example/status/1", "echo FxTwitter",
    "grep -rn fxtwitter docs",      # the names are matched as text, mentions included
    "curl -H 'Cookie: auth_token=abcdef; ct0=123456' https://x.com", "echo auth_token=abc", "echo ct0=abc",
    "echo 'ct0 = abc'",
    "echo $X_READER_COOKIES", "secret get X_READER_COOKIES", "secret ls --scope x-reader", "echo x-reader",
    "secret get X_READER_COOKIES -p hermes --scope x-reader", "secret get X --project=hermes",
    "secret set X_READER_COOKIES -p hermes --scope x-reader", "secret export -p hermes",
    "security find-generic-password -s secret.hermes", "security dump-keychain",
    "node ~/.hermes/plugins/x-tools/dist/cli.js", "node ~/.hermes/plugins/x-tools/dist/mcp.js",
    "node node_modules/@craftsamo/x-tools/dist/cli.js", "npx @craftsamo/x-tools", "npx -y @craftsamo/x-tools@0.2.0",
    "pnpm dlx @craftsamo/x-tools", "npm install -g @craftsamo/x-tools",
    "cat ~/.local/state/x-tools/accounts/default/cookies", "ls ~/.local/state/x-tools",
    "ls ~/.local/state/x-tools/engine/venv/bin", "cat $HOME/.local/state/x-tools/grants/grants.json",
    "ls ~/.hermes/plugins/x-tools", "cat ~/.hermes/plugins/x-tools/package.json",
])
def test_the_guard_blocks_ways_around_the_tools(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE), command


@pytest.mark.parametrize("command", [
    "echo $X_TOOLS_COOKIES_WORK", "echo ${X_TOOLS_COOKIES_DEFAULT:-}", "echo $X_TOOLS_GRANT_KEY",
    "echo $X_TOOLS_STATE_DIR", "echo $X_TOOLS_GRANTS_DIR", "export X_TOOLS_COOKIES_WORK=x",
    "X_TOOLS_READ_ONLY=true make", "X_TOOLS_UNATTENDED=true node server.js",
])
def test_the_guard_blocks_the_x_tools_variables_with_any_label(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE), command


@pytest.mark.parametrize("command", [
    "grep twscrape notes.md", "echo \"run twscrape later\"", "pip show twscrape-notes",
    "grep -n x-tools-cli notes.md", "echo \"run x-tools-cli login\"", "git log --grep x-tools-cli",
    "curl https://x.com/example/status/1", "open https://twitter.com/example/status/1",
    "echo https://x.com/i/lists/123", "curl https://www.x.com/example", "echo $X_COOKIES", "echo $X_TOOLS",
    "secret ls -p hermes", "secret show CLOUDFLARE_WORK -p hermes", "echo \"author_token\"", "echo fact0=1",
    "echo dict0=1", "echo $HOME", "git log --from twscrape-ish", "git log -- hermes/plugins/guards/x-tools-guard",
    "cat docs/x-tools.md", "ls ~/.hermes/plugins/guards/x-tools-guard", "ls /work/hermes-x-tools/hermes",
    "ls /work/feat-x-tools-opencode", "cat /x/Worktrees/dotconfig/feat-x-tools-opencode/README.md",
    "git log -- hermes/plugins/x_tools_guard",
    "ls ~/.local/state", "ls ~/.local/state/*", "ls ~/.local/state*", "ls ~/.local/st*",
    "ls ~/.local/state/x-b*", "cd ~/.local/state && ls",
    "ls ~/.hermes/profiles/assistant/skills", "ls ~/Downloads",
])
def test_the_guard_leaves_ordinary_commands_alone(command):
    assert gate("terminal", command=command) is None, command


@pytest.mark.parametrize("command", [
    "cd ~/.local/state && cat x-tools/accounts/default/cookies",
    "cat ~/.local/state//x-tools/accounts/default/cookies",
    "cat ~/.local/state/./x-tools/accounts/default/cookies",
    'cat ~/.local/state/"x-tools"/accounts/default/cookies',
    "cat ~/.local/state/x''-tools/accounts/default/cookies",
    "cd ~/.local/state && cat x-'tools'/accounts/default/cookies",
    "cat ${HOME}/.local/state/x-tools/grants/grants.json",
    "cat --file=~/.local/state//x-tools/grants/grants.json",
    "ls ~/.local/state/x-tool?",
    "cat ~/.local/state/x-tool*/accounts/default/cookies",
    "cat ~/.local/state/*tools/grants/grants.json",
    "cd ~/.local/state && ls x-tool?",
    "cat ~/.hermes/profiles/assistant/plugins/x-t*ls/dist/cli.js",
    "(cd ~/.hermes/plugins && cat x-tools/package.json)",
    "bash -c 'cd ~/.hermes/plugins; cat x-tools/package.json'",
    "bash -c 'cat ~/.local/state/x-tools/accounts/default/cookies'",
    "cd ~/.local/state && cd x-tools",
    "pushd ~/.local/state && ls x-tools",
])
def test_terminal_blocks_single_line_forms(command):
    assert blocked(gate("terminal", command=command)), command


@pytest.mark.parametrize("command", [
    "git push origin hermes/x-tools",
    "git checkout hermes/x-tools",
    "git log origin/main..hermes/x-tools",
    "git branch -d x-tools",
    "git checkout -b feat/x-tools",
    "git checkout -b feat/x-tools-opencode",
    "git merge origin/x-tools",
    "git rebase hermes/x-tools",
    "cd ~/ghq/github.com/me/shop && git push origin hermes/x-tools",
    "bash -c 'git push origin hermes/x-tools'",
    "ls ~/.hermes/profiles/assistant/plugins/x-tools",      # no copy of the package there
    "ls /elsewhere/x-tools/dist-not",
    "git commit -m 'remove x-access'",
])
def test_a_git_ref_or_a_name_that_resolves_to_nothing_passes(command, isolated, monkeypatch):
    tracked(monkeypatch, isolated)
    assert gate("terminal", command=command) is None, command
    assert gate("terminal", command=command, workdir=str(isolated)) is None, command


def test_a_directory_named_like_the_package_is_caught_when_it_exists(monkeypatch, isolated):
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent" / "x-tools"
    profile_copy = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "x-tools"
    workspace = isolated / "work"
    for directory in (checkout, profile_copy, workspace / "x-tools" / "sub"):
        directory.mkdir(parents=True)
    tracked(monkeypatch, workspace)
    for command in ("cd ~/ghq/github.com/craft-agent/x-tools", f"cd {checkout}", f"ls {checkout}/src",
                    f"ls {profile_copy}", "ls ~/.hermes/profiles/assistant/plugins/x-tools",
                    "bash -c 'cd ~/.hermes/profiles/assistant/plugins; cat x-tools/package.json'",
                    "cat x-tools/sub/x", "git branch -d x-tools"):
        assert blocked(gate("terminal", command=command)), command
    assert gate("terminal", command="git push origin hermes/x-tools") is None   # workspace/hermes/… is absent
    assert blocked(gate("read_file", path=str(checkout / "README.md")))
    assert blocked(gate("read_file", path=str(profile_copy / "package.json")))
    assert blocked(gate("read_file", path=str(workspace / "x-tools" / "sub" / "x")))
    assert gate("read_file", path=str(workspace / "x-tools-notes" / "x")) is None
    assert gate("read_file", path=str(workspace / "x-tools.md")) is None


def test_a_worktree_a_guard_directory_and_a_doc_named_with_the_package_pass(isolated):
    worktree = isolated / "Worktrees" / "dotconfig" / "feat-x-tools-opencode"
    guard = worktree / "hermes" / "plugins" / "guards" / "x-tools-guard"
    docs = worktree / "hermes" / "docs"
    for directory in (guard / "tests", docs):
        directory.mkdir(parents=True)
    (docs / "x-tools.md").write_text("x")
    for path in (worktree / "README.md", guard / "__init__.py", guard / "tests" / "test_plugin.py",
                 docs / "x-tools.md"):
        assert gate("read_file", path=str(path)) is None, path
        assert gate("terminal", command=f"cat {path}") is None, path
        assert gate("terminal", command=f"cat {path}", workdir=str(worktree)) is None, path
    assert gate("search_files", pattern="x", path=str(guard)) is None
    assert gate("terminal", command="ls", workdir=str(guard)) is None
    assert gate("write_file", path=str(docs / "x-tools.md"), content="x") is None


def test_a_link_to_an_existing_package_directory_is_followed(isolated):
    package = isolated / "elsewhere" / "x-tools"
    package.mkdir(parents=True)
    (isolated / "shortcut").symlink_to(package)
    assert blocked(gate("read_file", path=str(isolated / "shortcut" / "package.json")))
    assert blocked(gate("terminal", command=f"cat {isolated}/shortcut/package.json"))


def test_the_terminal_directory_kept_between_calls_is_judged(monkeypatch, isolated):
    home = isolated / "home"
    assert gate("terminal", command="cd ~/.local/state") is None            # call 1: nothing named yet
    tracked(monkeypatch, home / ".local" / "state")
    assert blocked(gate("terminal", command="cd x-tools"))                  # call 2
    assert blocked(gate("terminal", command="cat x-tools/accounts/default/cookies"))
    assert gate("terminal", command="ls") is None


def test_a_terminal_inside_a_protected_directory_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "x-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    tracked(monkeypatch, install / "dist")
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)


def test_a_terminal_inside_the_state_root_is_blocked(monkeypatch, isolated):
    state = isolated / "home" / ".local" / "state" / "x-tools" / "accounts" / "default"
    state.mkdir(parents=True)
    tracked(monkeypatch, state)
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    tracked(monkeypatch, isolated)
    (isolated / "shortcut").symlink_to(state)
    assert gate("terminal", command="ls", workdir=str(isolated / "shortcut")) == block_with(plugin.CWD_MESSAGE)
    assert blocked(gate("terminal", command="ls", workdir=str(state)))
    assert gate("terminal", command="ls", workdir=str(isolated)) is None


def test_a_terminal_inside_a_configured_state_directory_is_blocked(monkeypatch, isolated):
    state = isolated / "state-dir"
    (state / "engine" / "venv").mkdir(parents=True)
    monkeypatch.setenv("X_TOOLS_STATE_DIR", str(state))
    tracked(monkeypatch, state / "engine" / "venv")
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    tracked(monkeypatch, isolated)
    assert gate("terminal", command="ls") is None


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "x-tools"
    install.mkdir(parents=True)
    tracked(monkeypatch, install)
    assert gate("terminal", command="node dist/cli.js", workdir=str(isolated)) is None
    assert gate("terminal", command="ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command="ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".local" / "state")
    assert blocked(gate("terminal", command="ls", workdir="x-tools"))      # relative: the recorded one


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    grants = isolated / "grants-dir"
    grants.mkdir()
    monkeypatch.setenv("X_TOOLS_GRANTS_DIR", str(grants))
    command = "cat grants-dir/grants.json"
    assert gate("terminal", command=command) is None            # no record of the directory: text checks only
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command=command))
    assert blocked(gate("terminal", command="cat grants.json", workdir=str(grants)))
    tracked(monkeypatch, isolated / "elsewhere")
    assert gate("terminal", command=command) is None


def test_a_link_in_a_word_is_followed(monkeypatch, isolated):
    state = isolated / "state-dir"
    state.mkdir()
    (isolated / "elsewhere").symlink_to(state)
    assert gate("terminal", command=f"cat {isolated}/elsewhere/accounts/default/cookies") is None
    monkeypatch.setenv("X_TOOLS_STATE_DIR", str(state))
    assert blocked(gate("terminal", command=f"cat {isolated}/elsewhere/accounts/default/cookies"))


def test_the_hook_hands_its_ids_to_the_terminal_record(monkeypatch):
    asked = []
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": asked.append((task_id, session_id)))
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}, task_id="t1", session_id="s1") is None
    assert asked == [("t1", "s1")]
    assert plugin.gate(tool_name="read_file", args={"path": "a.txt"}, task_id="t1", session_id="s1") is None
    assert asked == [("t1", "s1")] * 2      # the file tools anchor relative paths there too


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
    assert blocked(gate("terminal", command="ls", workdir="~/.local/state/x-tools"))


def test_file_tools_may_read_the_plugin_source_but_not_the_state():
    (Path.home() / ".hermes" / "profiles" / "assistant" / "plugins" / "x-tools").mkdir(parents=True)
    guard_source = ROOT / "__init__.py"
    assert gate("read_file", path=str(guard_source)) is None
    assert gate("search_files", pattern="x", path=str(ROOT)) is None
    assert gate("read_file", path="/repo/notes.md") is None
    assert gate("read_file", path="https://x.com/example/status/1") is None
    assert gate("write_file", path="/repo/notes.md",
                content="twscrape reads via fxtwitter; X_TOOLS_COOKIES_WORK, X_READER_COOKIES, auth_token=") is None
    for tool, args in (("read_file", {"path": "~/.local/state/x-tools/accounts/default/cookies"}),
                       ("search_files", {"pattern": "x", "path": "~/.local/state/x-tools/engine"}),
                       ("read_file", {"path": "~/.local/state/x-tools/grants/grants.json"}),
                       ("write_file", {"path": "~/.hermes/plugins/x-tools/dist/cli.js", "content": "x"}),
                       ("patch", {"path": "~/.hermes/plugins/x-tools/package.json", "old": "a", "new": "b"}),
                       ("read_file", {"path": "~/.hermes/profiles/assistant/plugins/x-tools/x"})):
        assert gate(tool, **args) == block_with(plugin.BYPASS_MESSAGE), args


FILE_CALLS = (
    ("read_file", lambda path: {"path": path}),
    ("write_file", lambda path: {"path": path, "content": "x"}),
    ("patch", lambda path: {"path": path, "old_string": "a", "new_string": "b"}),
    ("search_files", lambda path: {"pattern": "x", "path": path}),
)


@pytest.fixture
def state_with_elsewhere(monkeypatch, isolated):
    """The default state root with a cookies file, and a process directory that is not inside it."""
    state_home = isolated / "home" / ".local" / "state"
    (state_home / "x-tools" / "accounts" / "default").mkdir(parents=True)
    (state_home / "x-tools" / "accounts" / "default" / "cookies").write_text("x")
    elsewhere = isolated / "elsewhere"
    (elsewhere / "docs").mkdir(parents=True)
    monkeypatch.chdir(elsewhere)
    return state_home


@pytest.mark.parametrize(("tool", "build"), FILE_CALLS)
def test_file_tools_resolve_relative_paths_against_the_session_directory(
        monkeypatch, state_with_elsewhere, tool, build):
    # the terminal did `cd ~/.local/state`; the file tool anchors there, not in the process directory
    tracked(monkeypatch, state_with_elsewhere)
    for path in ("x-tools/accounts/default/cookies", "x-tools", "./x-tools/grants", "docs/../x-tools/engine",
                 "x-tool?/accounts", "x-tool*"):
        assert gate(tool, **build(path)) == block_with(plugin.BYPASS_MESSAGE), path
    for path in ("docs/notes.md", "notes.txt", "x-tools-notes.txt", "x-b*"):
        assert gate(tool, **build(path)) is None, path


@pytest.mark.parametrize(("tool", "build"), FILE_CALLS)
def test_file_tools_check_the_process_directory_too(monkeypatch, isolated, state_with_elsewhere, tool, build):
    # the session is elsewhere, the process directory is the state home: the path is blocked under either
    tracked(monkeypatch, isolated / "elsewhere")
    monkeypatch.chdir(state_with_elsewhere)
    assert gate(tool, **build("x-tools/accounts/default/cookies")) == block_with(plugin.BYPASS_MESSAGE)
    assert gate(tool, **build("docs/notes.md")) is None


@pytest.mark.parametrize(("tool", "build"), FILE_CALLS)
def test_file_tools_without_a_recorded_directory_still_check_the_process_directory(
        monkeypatch, state_with_elsewhere, tool, build):
    assert plugin._tracked_cwd() is None
    assert gate(tool, **build("x-tools/accounts/default/cookies")) is None      # process directory: elsewhere
    monkeypatch.chdir(state_with_elsewhere)
    assert gate(tool, **build("x-tools/accounts/default/cookies")) == block_with(plugin.BYPASS_MESSAGE)
    assert gate(tool, **build("docs/notes.md")) is None


@pytest.mark.parametrize(("tool", "build"), FILE_CALLS)
def test_file_tools_check_the_configured_terminal_directory_too(
        monkeypatch, state_with_elsewhere, tool, build):
    monkeypatch.setenv("TERMINAL_CWD", str(state_with_elsewhere))
    assert gate(tool, **build("x-tools/accounts/default/cookies")) == block_with(plugin.BYPASS_MESSAGE)
    monkeypatch.setenv("TERMINAL_CWD", "relative/dir")      # the runtime ignores a relative anchor, so do we
    assert gate(tool, **build("x-tools/accounts/default/cookies")) is None


def test_the_recorded_directory_is_reached_through_the_hook_for_file_tools(monkeypatch, state_with_elsewhere):
    monkeypatch.setattr(plugin, "_tracked_cwd",
                        lambda task_id="", session_id="": str(state_with_elsewhere) if task_id == "t1" else None)
    args = {"path": "x-tools/accounts/default/cookies"}
    assert plugin.gate(tool_name="read_file", args=args, task_id="t1", session_id="s1") == \
        block_with(plugin.BYPASS_MESSAGE)
    assert plugin.gate(tool_name="read_file", args=args, task_id="t2", session_id="s2") is None


def test_a_file_tool_in_a_protected_recorded_directory_gets_the_bypass_message_not_the_cwd_one(
        monkeypatch, isolated):
    # the cwd message is about where the terminal runs: a file call that names nothing protected is not judged by it
    state = isolated / "home" / ".local" / "state" / "x-tools" / "grants"
    state.mkdir(parents=True)
    tracked(monkeypatch, state)
    assert gate("read_file", path="/repo/notes.md") is None
    assert gate("read_file", path="grants.json") == block_with(plugin.BYPASS_MESSAGE)


def test_file_tools_block_the_state_root_by_real_path(monkeypatch, isolated):
    state = isolated / "state-dir"      # no pattern names it: only its real path does
    (state / "accounts" / "default").mkdir(parents=True)
    (state / "accounts" / "default" / "cookies").write_text("x")
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("X_TOOLS_STATE_DIR", str(state))
    for path in (state / "accounts" / "default" / "cookies", state, link / "accounts" / "default" / "cookies", link,
                 isolated / "other" / ".." / "state-dir" / "engine"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "state-dir-notes.txt")) is None


def test_a_configured_state_directory_does_not_free_the_default_root_of_the_grants(monkeypatch, isolated):
    state = isolated / "state-dir"
    state.mkdir()
    monkeypatch.setenv("X_TOOLS_STATE_DIR", str(state))
    default = isolated / "home" / ".local" / "state" / "x-tools"
    assert blocked(gate("read_file", path=str(default / "grants" / "grants.json")))      # exists or not
    assert blocked(gate("read_file", path=str(state / "accounts")))


def test_the_xdg_state_root_is_protected(monkeypatch, isolated):
    state = isolated / "xdg" / "x-tools"
    state.mkdir(parents=True)
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(link / "grants")))
    assert gate("read_file", path=str(isolated / "xdg" / "x-tools-notes.txt")) is None
    assert gate("read_file", path=str(isolated / "xdg")) is None


def test_the_state_root_follows_the_package_s_resolution(monkeypatch, isolated):
    default = str(isolated / "home" / ".local" / "state" / "x-tools")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", "relative/state")      # a relative one is ignored, as the package does
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", "~/state")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert plugin._state_root() == str(isolated / "xdg" / "x-tools")
    monkeypatch.setenv("X_TOOLS_STATE_DIR", str(isolated / "mine"))      # its own variable wins
    assert plugin._state_root() == str(isolated / "mine")
    assert plugin._default_state_root() == str(isolated / "xdg" / "x-tools")
    monkeypatch.setenv("X_TOOLS_STATE_DIR", "~/mine")
    assert plugin._state_root() == str(isolated / "home" / "mine")
    monkeypatch.setenv("X_TOOLS_STATE_DIR", "  ")       # blank counts as unset
    assert plugin._state_root() == str(isolated / "xdg" / "x-tools")


def test_a_configured_grants_directory_is_protected_through_a_link(monkeypatch, isolated):
    custom = isolated / "custom"
    custom.mkdir()
    (isolated / "shortcut").symlink_to(custom)
    assert gate("read_file", path=str(isolated / "shortcut" / "grants.json")) is None
    monkeypatch.setenv("X_TOOLS_GRANTS_DIR", str(custom))
    assert blocked(gate("read_file", path=str(custom / "grants.json")))
    assert blocked(gate("read_file", path=str(isolated / "shortcut" / "grants.json")))


def test_the_installed_plugin_is_protected_through_a_link(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "x-tools"
    install.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(install)
    assert blocked(gate("read_file", path=str(link / "package.json")))


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "bypass", boom)
    assert gate("terminal", command="ls") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("read_file", path="a.txt") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("x_media_download", url="https://x.com/example/status/1") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("x_grant_create", reason="a reason") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("x_future_write") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("x_post_read", method="view") is None
    assert gate("x_search", query="x") is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("x_grant_revoke") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("x_user_read", method="view") is None
    assert gate("web_search", query="x") is None


def test_a_failing_command_reader_blocks_the_terminal(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin.shell_commands, "runs", boom)
    assert gate("terminal", command="ls") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("read_file", path="a.txt") is None      # the file tools never reach the command reader


def test_the_command_reader_falls_back_to_the_pattern_on_a_line_it_cannot_read():
    # an unclosed quote cannot be read: the pattern alone decides
    assert gate("terminal", command="x-tools-cli login 'x") == block_with(plugin.BYPASS_MESSAGE)
    assert gate("terminal", command="twscrape accounts \"x") == block_with(plugin.BYPASS_MESSAGE)
    assert gate("terminal", command="grep notes 'x") is None


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    assert line("x_media_download", url="https://x.com/private/status/1", path="/private/dir") == "save media"
    assert line("x_grant_create", target="x_media_download", reason="a private reason") == "grant"
    assert line("x_grant_revoke", id="grant_0123456789ab") == "revoke grant"
    assert line("x_account_read", label="private") == "account"
    assert line("x_post_read", method="search", query="a private query") == "search"
    assert line("x_post_read", method="thread", post="https://x.com/private/status/1") == "thread"
    assert line("x_post_read", method="a private value", query="a private query") is None
    assert line("x_user_read", method="followers", user="private") == "followers"
    assert line("x_list_read", method="members", list="123") == "members"
    assert line("x_community_read", method="posts", community="123") == "posts"
    assert line("x_trend_read", method="explore", category="news") == "explore"
    assert line("x_grant_read", method="log", limit=5) == "log"


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
    assert not (set(plugin.LABELS) | set(plugin.METHODS)) & plugin.OTHER_TOOLS
    assert set(plugin.METHODS) | {"x_account_read"} == plugin.READS      # every read but the account one has a method
    assert set(plugin.LABELS) == {"x_account_read", *KNOWN_WRITES}


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
