import importlib.util
import json
from pathlib import Path
import unicodedata

import hermes_yaml as yaml
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("google_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
READ_TOOLS = {
    "google_account_read", "google_sheets_read", "google_gmail_read", "google_drive_read", "google_comments_read",
    "google_run_read", "google_grant_read",
}
KNOWN_WRITES = (
    "google_sheets_edit", "google_sheets_append", "google_sheets_clear", "google_sheets_create",
    "google_sheets_tab_add", "google_sheets_format", "google_sheets_add", "google_sheets_restructure",
    "google_sheets_transform", "google_sheets_protect",
    "google_gmail_send", "google_gmail_draft_create", "google_gmail_draft_edit", "google_gmail_draft_delete",
    "google_gmail_label", "google_gmail_label_create", "google_gmail_trash",
    "google_drive_upload", "google_drive_folder_create", "google_drive_copy", "google_drive_rename",
    "google_drive_move", "google_drive_trash", "google_drive_restore",
    "google_comments_add", "google_comments_status", "google_comments_edit", "google_comments_delete",
    "google_run_service_deploy", "google_run_job_deploy", "google_run_job_run", "google_run_execution_cancel",
    "google_run_job_delete", "google_run_revision_delete", "google_run_service_delete", "google_run_traffic_set",
    "google_grant_create", "google_grant_revoke",
)
WRITES = (*KNOWN_WRITES, "google_future_write", "google_future_read", "google_sheets_read_all", "google_unread",
          "google_")
MAIL_TOOLS = ("google_gmail_send", "google_gmail_draft_create", "google_gmail_draft_edit")
ENV_NAMES = ("GOOGLE_TOOLS_STATE_DIR", "GOOGLE_TOOLS_GRANTS_DIR", "XDG_STATE_HOME", "XDG_CONFIG_HOME",
             "TERMINAL_CWD", "WORKSPACES_LAYOUT", "WORKSPACES_ROOT")


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
    monkeypatch.setattr(plugin, "_hermes_home", lambda: tmp_path / "home" / ".hermes")
    monkeypatch.setattr(plugin, "_SNAPSHOTS", {})                        # no profile has registered yet
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


def write_config(isolated, **settings):
    """Write the running profile's config.yaml with the plugin's settings; the guard has not seen them."""
    home = isolated / "home" / ".hermes"
    home.mkdir(parents=True, exist_ok=True)
    config = {"plugins": {"entries": {"google-tools": {"settings": settings}}}}
    (home / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")


def configure(isolated, **settings):
    """Write the settings and let the guard take its snapshot, as if the profile had registered with them."""
    write_config(isolated, **settings)
    plugin._take_snapshot()


def test_the_reads_are_exactly_the_seven_named_ones():
    assert plugin.READS == READ_TOOLS
    assert len(READ_TOOLS) == 7


def test_every_read_passes_with_no_human_and_for_a_peer(monkeypatch):
    no_human(monkeypatch)
    for tool in sorted(plugin.READS):
        assert gate(tool, method="list") is None
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in sorted(plugin.READS):
        assert gate(tool, method="list") is None


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_with_no_human(monkeypatch, tool):
    no_human(monkeypatch)
    assert gate(tool, spreadsheet="abc") == block_with(plugin.human_gate.refusal(tool, "yolo mode is on"))


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_for_an_inbound_peer(monkeypatch, tool):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate(tool, spreadsheet="abc") == block_with(f"{tool} is not available to inbound A2A requests")


@pytest.mark.parametrize("tool", WRITES)
def test_writes_pass_with_a_human(tool):
    assert gate(tool, spreadsheet="abc") is None


def test_a_tool_added_later_fails_closed(monkeypatch):
    no_human(monkeypatch)
    assert blocked(gate("google_future_write"))
    assert blocked(gate("google_sheets_edit", spreadsheet="abc"))
    assert blocked(gate("google_"))


@pytest.mark.parametrize("tool", ("google_sheets", "google_gmail", "google_drive"))
def test_a_bare_google_tool_name_counts_as_a_write(monkeypatch, tool):
    assert plugin._is_write(tool)
    assert gate(tool, action="send", to=["a@example.com"]) is None          # with a person there
    no_human(monkeypatch)
    assert gate(tool, action="send", to=["a@example.com"]) == block_with(
        plugin.human_gate.refusal(tool, "yolo mode is on"))
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate(tool, action="send") == block_with(f"{tool} is not available to inbound A2A requests")


def test_the_writes_listed_are_exactly_the_labelled_ones():
    assert set(plugin.LABELS) - {"google_comments_read"} == set(KNOWN_WRITES)
    assert not set(KNOWN_WRITES) & plugin.READS


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="google-tools-cli") is None
    assert gate("browser_click", ref="google_sheets_edit") is None
    assert gate("google") is None
    assert gate("googlex_sheets_edit") is None          # no underscore after google: not this plugin's
    assert gate("signal_message_send", text="hi") is None
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "google-tools-cli login", "google-tools-cli remove work", "/opt/homebrew/bin/google-tools-cli login",
    "bash -c 'google-tools-cli login'", "sudo google-tools-cli login", "env CI=1 google-tools-cli login",
    "cd app && google-tools-cli login", "./node_modules/.bin/google-tools-cli login",
    "gcloud projects list", "/opt/homebrew/bin/gcloud run deploy", "cd x && gsutil ls gs://b",
    "bq query 'select 1'", "(gcloud auth print-access-token)", "bash -c 'gcloud auth list'",
    "echo \"$(gcloud auth print-access-token)\"", "xargs -I{} gcloud {}", "sudo gsutil cp a gs://b",
    "cat <<EOF | sh\ngcloud auth list\nEOF", "python3 -c 'import os; os.system(\"gcloud auth list\")'",
    "node ~/.hermes/plugins/google-tools/dist/cli.js", "node ~/.hermes/plugins/google-tools/dist/mcp.js",
    "node node_modules/@craftsamo/google-tools/dist/cli.js", "npx @craftsamo/google-tools",
    "npx -y @craftsamo/google-tools@0.1.1", "pnpm dlx @craftsamo/google-tools",
    "npm install -g @craftsamo/google-tools",
    "cat ~/.local/state/google-tools/accounts/default/credentials.json", "ls ~/.local/state/google-tools",
    "cat $HOME/.local/state/google-tools/grants/grants.json", "ls ~/.hermes/plugins/google-tools",
    "cat ~/.hermes/plugins/google-tools/package.json",
    "curl -H 'Authorization: Bearer ya29.a0AfH6SMBx' https://www.googleapis.com/drive/v3/files",
    "echo ya29.abc", "echo GOCSPX-abcdefgh", "echo gocspx-abcdefgh",
    "secret get GOOGLE_CLIENT -p hermes", "secret get GOOGLE_CLIENT --project=hermes --scope google-tools",
    "secret set X -p hermes --scope google-tools", "secret export -p hermes",
    "security find-generic-password -s secret.hermes", "security dump-keychain",
])
def test_the_guard_blocks_ways_around_the_tools(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE), command


@pytest.mark.parametrize("command", [
    "echo $GOOGLE_TOOLS_CREDENTIALS_DEFAULT", "echo ${GOOGLE_TOOLS_CREDENTIALS_WORK:-}", "echo $GOOGLE_TOOLS_GRANT_KEY",
    "echo $GOOGLE_TOOLS_STATE_DIR", "echo $GOOGLE_TOOLS_GRANTS_DIR", "export GOOGLE_TOOLS_CREDENTIALS_WORK=x",
    "GOOGLE_TOOLS_READ_ONLY=true make", "GOOGLE_TOOLS_UNATTENDED=true node server.js",
])
def test_the_guard_blocks_the_google_tools_variables_with_any_label(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE), command


@pytest.mark.parametrize("command", [
    "cat ~/.config/gcloud/credentials.db", "ls ~/.config/gcloud", "CLOUDSDK_CONFIG=/tmp/x foo",
    "echo $GOOGLE_ACCESS_AGE_IDENTITY", "age -d -i <(echo AGE-SECRET-KEY-1QQQ) f.age",
    "cat google_token.json", "cat ~/google_client_secret.json",
])
def test_the_machines_other_google_credentials_stay_guarded(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE), command


@pytest.mark.parametrize("command", [
    "grep gcloud notes.md", "echo \"run gcloud auth login\"", "which gcloud", "command -v gcloud",
    "git log --grep gcloud", "git commit -m 'note: gcloud auth'", "grep -n 'gsutil cp' docs/deploy.md",
    "sed -n 1,60p scripts/deploy-manual.sh | grep -nE 'usage|gcloud auth|PROJECT'", "echo mybq",
    "grep -n google-tools-cli notes.md", "echo \"run google-tools-cli login\"", "git log --grep google-tools-cli",
    "pip show gcloud-notes", "echo $GOOGLE_TOOLS", "echo $GOOGLE_API_KEY", "echo $GOOGLE_CLOUD_PROJECT",
    "echo ya29", "echo GOCSPX", "secret ls -p hermes", "secret show GOOGLE_WORK -p hermes",
    "git log -- hermes/plugins/guards/google-tools-guard", "cat docs/google-tools.md",
    "ls ~/.hermes/plugins/guards/google-tools-guard", "ls /work/hermes-google-tools/hermes",
    "ls /work/feat-google-tools-opencode", "cat /x/Worktrees/dotconfig/feat-google-tools-opencode/README.md",
    "git log -- hermes/plugins/google_tools_guard", "ls ~/.config", "ls ~/.config/gh",
    "ls ~/.local/state", "ls ~/.local/state/*", "ls ~/.local/state*", "ls ~/.local/st*",
    "ls ~/.local/state/google-b*", "cd ~/.local/state && ls",
    "ls ~/.hermes/profiles/assistant/skills", "ls ~/Downloads",
])
def test_the_guard_leaves_ordinary_commands_alone(command):
    assert gate("terminal", command=command) is None, command


@pytest.mark.parametrize("command", [
    "cd ~/.local/state && cat google-tools/accounts/default/credentials.json",
    "cat ~/.local/state//google-tools/accounts/default/credentials.json",
    "cat ~/.local/state/./google-tools/accounts/default/credentials.json",
    'cat ~/.local/state/"google-tools"/accounts/default/credentials.json',
    "cat ~/.local/state/google''-tools/accounts/default/credentials.json",
    "cd ~/.local/state && cat google-'tools'/accounts/default/credentials.json",
    "cat ${HOME}/.local/state/google-tools/grants/grants.json",
    "cat --file=~/.local/state//google-tools/grants/grants.json",
    "ls ~/.local/state/google-tool?",
    "cat ~/.local/state/google-tool*/accounts/default/credentials.json",
    "cat ~/.local/state/*tools/grants/grants.json",
    "cd ~/.local/state && ls google-tool?",
    "cat ~/.hermes/profiles/assistant/plugins/google-t*ls/dist/cli.js",
    "(cd ~/.hermes/plugins && cat google-tools/package.json)",
    "bash -c 'cd ~/.hermes/plugins; cat google-tools/package.json'",
    "bash -c 'cat ~/.local/state/google-tools/accounts/default/credentials.json'",
    "cd ~/.local/state && cd google-tools",
    "pushd ~/.local/state && ls google-tools",
])
def test_terminal_blocks_single_line_forms(command):
    assert blocked(gate("terminal", command=command)), command


@pytest.mark.parametrize("command", [
    "git push origin hermes/google-tools",
    "git checkout hermes/google-tools",
    "git log origin/main..hermes/google-tools",
    "git branch -d google-tools",
    "git checkout -b feat/google-tools",
    "git checkout -b feat/google-tools-opencode",
    "git merge origin/google-tools",
    "git rebase hermes/google-tools",
    "cd ~/ghq/github.com/me/shop && git push origin hermes/google-tools",
    "bash -c 'git push origin hermes/google-tools'",
    "ls ~/.hermes/profiles/assistant/plugins/google-tools",      # no copy of the package there
    "ls /elsewhere/google-tools/dist-not",
    "git commit -m 'remove google-tools'",
])
def test_a_git_ref_or_a_name_that_resolves_to_nothing_passes(command, isolated, monkeypatch):
    tracked(monkeypatch, isolated)
    assert gate("terminal", command=command) is None, command
    assert gate("terminal", command=command, workdir=str(isolated)) is None, command


def test_a_directory_named_like_the_package_is_caught_when_it_exists(monkeypatch, isolated):
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent" / "google-tools"
    profile_copy = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "google-tools"
    workspace = isolated / "work"
    for directory in (checkout, profile_copy, workspace / "google-tools" / "sub"):
        directory.mkdir(parents=True)
    tracked(monkeypatch, workspace)
    for command in ("cd ~/ghq/github.com/craft-agent/google-tools", f"cd {checkout}", f"ls {checkout}/src",
                    f"ls {profile_copy}", "ls ~/.hermes/profiles/assistant/plugins/google-tools",
                    "bash -c 'cd ~/.hermes/profiles/assistant/plugins; cat google-tools/package.json'",
                    "cat google-tools/sub/x", "git branch -d google-tools"):
        assert blocked(gate("terminal", command=command)), command
    assert gate("terminal", command="git push origin hermes/google-tools") is None   # workspace/hermes/… is absent
    assert blocked(gate("read_file", path=str(checkout / "README.md")))
    assert blocked(gate("read_file", path=str(profile_copy / "package.json")))
    assert blocked(gate("read_file", path=str(workspace / "google-tools" / "sub" / "x")))
    assert gate("read_file", path=str(workspace / "google-tools-notes" / "x")) is None
    assert gate("read_file", path=str(workspace / "google-tools.md")) is None


def test_a_worktree_a_guard_directory_and_a_doc_named_with_the_package_pass(isolated):
    worktree = isolated / "Worktrees" / "dotconfig" / "feat-google-tools-opencode"
    guard = worktree / "hermes" / "plugins" / "guards" / "google-tools-guard"
    docs = worktree / "hermes" / "docs"
    for directory in (guard / "tests", docs):
        directory.mkdir(parents=True)
    (docs / "google-tools.md").write_text("x")
    for path in (worktree / "README.md", guard / "__init__.py", guard / "tests" / "test_plugin.py",
                 docs / "google-tools.md"):
        assert gate("read_file", path=str(path)) is None, path
        assert gate("terminal", command=f"cat {path}") is None, path
        assert gate("terminal", command=f"cat {path}", workdir=str(worktree)) is None, path
    assert gate("search_files", pattern="x", path=str(guard)) is None
    assert gate("terminal", command="ls", workdir=str(guard)) is None
    assert gate("write_file", path=str(docs / "google-tools.md"), content="x") is None


def test_a_link_to_an_existing_package_directory_is_followed(isolated):
    package = isolated / "elsewhere" / "google-tools"
    package.mkdir(parents=True)
    (isolated / "shortcut").symlink_to(package)
    assert blocked(gate("read_file", path=str(isolated / "shortcut" / "package.json")))
    assert blocked(gate("terminal", command=f"cat {isolated}/shortcut/package.json"))


def test_file_tools_cannot_read_the_machines_other_google_credentials():
    assert blocked(gate("read_file", path="~/.config/gcloud/credentials.db"))
    assert blocked(gate("search_files", pattern="x", path="/Users/me/.config/gcloud"))
    assert blocked(gate("read_file", path="~/google_token.json"))


def test_the_terminal_directory_kept_between_calls_is_judged(monkeypatch, isolated):
    home = isolated / "home"
    assert gate("terminal", command="cd ~/.local/state") is None            # call 1: nothing named yet
    tracked(monkeypatch, home / ".local" / "state")
    assert blocked(gate("terminal", command="cd google-tools"))             # call 2
    assert blocked(gate("terminal", command="cat google-tools/accounts/default/credentials.json"))
    assert gate("terminal", command="ls") is None


def test_a_terminal_inside_a_protected_directory_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "google-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    tracked(monkeypatch, install / "dist")
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)


def test_a_terminal_inside_the_state_root_is_blocked(monkeypatch, isolated):
    state = isolated / "home" / ".local" / "state" / "google-tools" / "accounts" / "default"
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
    (state / "accounts" / "default").mkdir(parents=True)
    monkeypatch.setenv("GOOGLE_TOOLS_STATE_DIR", str(state))
    tracked(monkeypatch, state / "accounts" / "default")
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    tracked(monkeypatch, isolated)
    assert gate("terminal", command="ls") is None


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "google-tools"
    install.mkdir(parents=True)
    tracked(monkeypatch, install)
    assert gate("terminal", command="node dist/cli.js", workdir=str(isolated)) is None
    assert gate("terminal", command="ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command="ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".local" / "state")
    assert blocked(gate("terminal", command="ls", workdir="google-tools"))      # relative: the recorded one


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    grants = isolated / "grants-dir"
    grants.mkdir()
    monkeypatch.setenv("GOOGLE_TOOLS_GRANTS_DIR", str(grants))
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
    assert gate("terminal", command=f"cat {isolated}/elsewhere/accounts/default/credentials.json") is None
    monkeypatch.setenv("GOOGLE_TOOLS_STATE_DIR", str(state))
    assert blocked(gate("terminal", command=f"cat {isolated}/elsewhere/accounts/default/credentials.json"))


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
    assert blocked(gate("terminal", command="ls", workdir="~/.local/state/google-tools"))


def make_project(isolated, monkeypatch):
    project = isolated / "ghq" / "shop"
    (project / ".git").mkdir(parents=True)
    (project / ".git" / "config").write_text('[remote "origin"]\n\turl = git@github.com:me/shop.git\n')
    monkeypatch.setattr(plugin.project_place, "_roots", lambda: [(isolated / "ghq").resolve()])
    monkeypatch.setattr(plugin.project_place, "_own_common", lambda: None)
    return project


def test_a_project_runs_its_own_entry_points_but_not_the_cli_itself(isolated, monkeypatch):
    project = make_project(isolated, monkeypatch)
    assert plugin.project_place.project_dir({"command": "x", "workdir": str(project)}) == project.resolve()
    for command in ("pnpm run deploy", "make deploy", "./scripts/deploy.sh", "GOOGLE_CLOUD_PROJECT=x ./scripts/deploy.sh",
                    "pnpm exec nps setup.google", "node scripts/setup.mjs"):
        assert gate("terminal", command=command, workdir=str(project)) is None, command
    assert gate("terminal", command=f"cd {project} && pnpm run deploy") is None
    for command in ("gcloud projects list", "gsutil ls gs://b", "bq ls", "pnpm dlx gcloud x", "npx -y gcloud x",
                    "google-tools-cli login", "pnpm exec google-tools-cli login", "./scripts/deploy.sh gcloud"):
        assert blocked(gate("terminal", command=command, workdir=str(project))), command
        assert blocked(gate("terminal", command=command, workdir=str(isolated))), command


def test_a_project_is_never_hermes_own_configuration(isolated, monkeypatch):
    own = make_project(isolated, monkeypatch) / ".git"
    monkeypatch.setattr(plugin.project_place, "_own_common", lambda: own.resolve())
    assert plugin.project_place.project_dir({"command": "x", "workdir": str(own.parent)}) is None
    assert blocked(gate("terminal", command="gcloud projects list", workdir=str(own.parent)))


@pytest.mark.parametrize("command", [
    "python ~/.hermes/hermes-agent/skills/google-workspace/scripts/google_api.py gmail send",
    "python3 skills/productivity/google-workspace/scripts/setup.py", "cat google_api.py",
])
def test_the_runtime_s_google_workspace_scripts_are_blocked(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE), command


def test_file_tools_cannot_reach_the_runtime_s_google_workspace_scripts():
    for path in ("~/.hermes/hermes-agent/skills/google-workspace/scripts/google_api.py", "scripts/google_api.py"):
        assert gate("read_file", path=path) == block_with(plugin.BYPASS_MESSAGE), path
    assert gate("write_file", path="/repo/notes.md", content="google_api.py") == block_with(plugin.BYPASS_MESSAGE)


def test_the_secret_names_are_case_sensitive_the_file_names_are_not(isolated, monkeypatch):
    project = make_project(isolated, monkeypatch)
    for command in ("python scripts/cloudsdk_setup.py", "echo age-secret-key", "echo google_access_age"):
        assert gate("terminal", command=command, workdir=str(project)) is None, command
    for command in ("CLOUDSDK_CONFIG=/tmp/x make", "echo $GOOGLE_ACCESS_AGE_IDENTITY", "echo AGE-SECRET-KEY-1QQQ",
                    "cat GOOGLE_API.PY", "cat ~/.Config/gCloud/x"):
        assert blocked(gate("terminal", command=command, workdir=str(project))), command
    assert blocked(gate("write_file", path="/repo/x.py", content="AGE-SECRET-KEY-1QQQ"))
    assert gate("write_file", path="/repo/cloudsdk_setup.py", content="x") is None


def test_file_tools_may_read_the_plugin_source_but_not_the_state():
    (Path.home() / ".hermes" / "profiles" / "assistant" / "plugins" / "google-tools").mkdir(parents=True)
    guard_source = ROOT / "__init__.py"
    assert gate("read_file", path=str(guard_source)) is None
    assert gate("search_files", pattern="x", path=str(ROOT)) is None
    assert gate("read_file", path="/repo/notes.md") is None
    assert gate("read_file", path="https://docs.google.com/spreadsheets/d/abc") is None
    assert gate("write_file", path="/repo/notes.md",
                content="gcloud projects list; google-tools-cli login; GOOGLE_TOOLS_CREDENTIALS_WORK; ya29.") is None
    for tool, args in (("read_file", {"path": "~/.local/state/google-tools/accounts/default/credentials.json"}),
                       ("search_files", {"pattern": "x", "path": "~/.local/state/google-tools/grants"}),
                       ("read_file", {"path": "~/.local/state/google-tools/grants/grants.json"}),
                       ("write_file", {"path": "~/.hermes/plugins/google-tools/dist/cli.js", "content": "x"}),
                       ("patch", {"path": "~/.hermes/plugins/google-tools/package.json", "old": "a", "new": "b"}),
                       ("read_file", {"path": "~/.hermes/profiles/assistant/plugins/google-tools/x"})):
        assert gate(tool, **args) == block_with(plugin.BYPASS_MESSAGE), args


FILE_CALLS = (
    ("read_file", lambda path: {"path": path}),
    ("write_file", lambda path: {"path": path, "content": "x"}),
    ("patch", lambda path: {"path": path, "old_string": "a", "new_string": "b"}),
    ("search_files", lambda path: {"pattern": "x", "path": path}),
)


@pytest.fixture
def state_with_elsewhere(monkeypatch, isolated):
    """The default state root with a credentials file, and a process directory that is not inside it."""
    state_home = isolated / "home" / ".local" / "state"
    (state_home / "google-tools" / "accounts" / "default").mkdir(parents=True)
    (state_home / "google-tools" / "accounts" / "default" / "credentials.json").write_text("x")
    elsewhere = isolated / "elsewhere"
    (elsewhere / "docs").mkdir(parents=True)
    monkeypatch.chdir(elsewhere)
    return state_home


@pytest.mark.parametrize(("tool", "build"), FILE_CALLS)
def test_file_tools_resolve_relative_paths_against_the_session_directory(
        monkeypatch, state_with_elsewhere, tool, build):
    # the terminal did `cd ~/.local/state`; the file tool anchors there, not in the process directory
    tracked(monkeypatch, state_with_elsewhere)
    for path in ("google-tools/accounts/default/credentials.json", "google-tools", "./google-tools/grants",
                 "docs/../google-tools/engine", "google-tool?/accounts", "google-tool*"):
        assert gate(tool, **build(path)) == block_with(plugin.BYPASS_MESSAGE), path
    for path in ("docs/notes.md", "notes.txt", "google-tools-notes.txt", "google-b*"):
        assert gate(tool, **build(path)) is None, path


@pytest.mark.parametrize(("tool", "build"), FILE_CALLS)
def test_file_tools_check_the_process_directory_too(monkeypatch, isolated, state_with_elsewhere, tool, build):
    # the session is elsewhere, the process directory is the state home: the path is blocked under either
    tracked(monkeypatch, isolated / "elsewhere")
    monkeypatch.chdir(state_with_elsewhere)
    assert gate(tool, **build("google-tools/accounts/default/credentials.json")) == block_with(plugin.BYPASS_MESSAGE)
    assert gate(tool, **build("docs/notes.md")) is None


@pytest.mark.parametrize(("tool", "build"), FILE_CALLS)
def test_file_tools_without_a_recorded_directory_still_check_the_process_directory(
        monkeypatch, state_with_elsewhere, tool, build):
    assert plugin._tracked_cwd() is None
    assert gate(tool, **build("google-tools/accounts/default/credentials.json")) is None   # process dir: elsewhere
    monkeypatch.chdir(state_with_elsewhere)
    assert gate(tool, **build("google-tools/accounts/default/credentials.json")) == block_with(plugin.BYPASS_MESSAGE)
    assert gate(tool, **build("docs/notes.md")) is None


@pytest.mark.parametrize(("tool", "build"), FILE_CALLS)
def test_file_tools_check_the_configured_terminal_directory_too(
        monkeypatch, state_with_elsewhere, tool, build):
    monkeypatch.setenv("TERMINAL_CWD", str(state_with_elsewhere))
    assert gate(tool, **build("google-tools/accounts/default/credentials.json")) == block_with(plugin.BYPASS_MESSAGE)
    monkeypatch.setenv("TERMINAL_CWD", "relative/dir")      # the runtime ignores a relative anchor, so do we
    assert gate(tool, **build("google-tools/accounts/default/credentials.json")) is None


def test_the_recorded_directory_is_reached_through_the_hook_for_file_tools(monkeypatch, state_with_elsewhere):
    monkeypatch.setattr(plugin, "_tracked_cwd",
                        lambda task_id="", session_id="": str(state_with_elsewhere) if task_id == "t1" else None)
    args = {"path": "google-tools/accounts/default/credentials.json"}
    assert plugin.gate(tool_name="read_file", args=args, task_id="t1", session_id="s1") == \
        block_with(plugin.BYPASS_MESSAGE)
    assert plugin.gate(tool_name="read_file", args=args, task_id="t2", session_id="s2") is None


def test_a_file_tool_in_a_protected_recorded_directory_gets_the_bypass_message_not_the_cwd_one(
        monkeypatch, isolated):
    # the cwd message is about where the terminal runs: a file call that names nothing protected is not judged by it
    state = isolated / "home" / ".local" / "state" / "google-tools" / "grants"
    state.mkdir(parents=True)
    tracked(monkeypatch, state)
    assert gate("read_file", path="/repo/notes.md") is None
    assert gate("read_file", path="grants.json") == block_with(plugin.BYPASS_MESSAGE)


def test_file_tools_block_the_state_root_by_real_path(monkeypatch, isolated):
    state = isolated / "state-dir"      # no pattern names it: only its real path does
    (state / "accounts" / "default").mkdir(parents=True)
    (state / "accounts" / "default" / "credentials.json").write_text("x")
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("GOOGLE_TOOLS_STATE_DIR", str(state))
    for path in (state / "accounts" / "default" / "credentials.json", state,
                 link / "accounts" / "default" / "credentials.json", link,
                 isolated / "other" / ".." / "state-dir" / "accounts"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "state-dir-notes.txt")) is None


def test_a_configured_state_directory_does_not_free_the_default_root_of_the_grants(monkeypatch, isolated):
    state = isolated / "state-dir"
    state.mkdir()
    monkeypatch.setenv("GOOGLE_TOOLS_STATE_DIR", str(state))
    default = isolated / "home" / ".local" / "state" / "google-tools"
    assert blocked(gate("read_file", path=str(default / "grants" / "grants.json")))      # exists or not
    assert blocked(gate("read_file", path=str(state / "accounts")))


def test_the_xdg_state_root_is_protected(monkeypatch, isolated):
    state = isolated / "xdg" / "google-tools"
    state.mkdir(parents=True)
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(link / "grants")))
    assert gate("read_file", path=str(isolated / "xdg" / "google-tools-notes.txt")) is None
    assert gate("read_file", path=str(isolated / "xdg")) is None


def test_the_state_root_follows_the_package_s_resolution(monkeypatch, isolated):
    default = str(isolated / "home" / ".local" / "state" / "google-tools")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", "relative/state")      # a relative one is ignored, as the package does
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", "~/state")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert plugin._state_root() == str(isolated / "xdg" / "google-tools")
    monkeypatch.setenv("GOOGLE_TOOLS_STATE_DIR", str(isolated / "mine"))      # its own variable wins
    assert plugin._state_root() == str(isolated / "mine")
    assert plugin._default_state_root() == str(isolated / "xdg" / "google-tools")
    monkeypatch.setenv("GOOGLE_TOOLS_STATE_DIR", "~/mine")
    assert plugin._state_root() == str(isolated / "home" / "mine")
    monkeypatch.setenv("GOOGLE_TOOLS_STATE_DIR", "  ")       # blank counts as unset
    assert plugin._state_root() == str(isolated / "xdg" / "google-tools")


def test_a_configured_grants_directory_is_protected_through_a_link(monkeypatch, isolated):
    custom = isolated / "custom"
    custom.mkdir()
    (isolated / "shortcut").symlink_to(custom)
    assert gate("read_file", path=str(isolated / "shortcut" / "grants.json")) is None
    monkeypatch.setenv("GOOGLE_TOOLS_GRANTS_DIR", str(custom))
    assert blocked(gate("read_file", path=str(custom / "grants.json")))
    assert blocked(gate("read_file", path=str(isolated / "shortcut" / "grants.json")))


def test_the_state_and_grants_directories_of_the_profile_settings_are_protected(isolated):
    state, grants = isolated / "my-state", isolated / "my-grants"
    state.mkdir()
    grants.mkdir()
    (isolated / "shortcut").symlink_to(grants)
    assert gate("read_file", path=str(state / "accounts")) is None
    configure(isolated, state_dir=str(state), grants_dir=str(grants))
    assert blocked(gate("read_file", path=str(state / "accounts")))
    assert blocked(gate("read_file", path=str(isolated / "shortcut" / "grants.json")))
    assert blocked(gate("terminal", command=f"cat {grants}/grants.json"))
    assert gate("read_file", path=str(isolated / "my-state-notes.txt")) is None
    configure(isolated, state_dir="~/home-state")
    assert blocked(gate("terminal", command="ls ~/home-state"))


def test_a_configuration_that_cannot_be_read_never_blocks_an_ordinary_terminal_call(isolated):
    assert gate("terminal", command="ls") is None               # no config.yaml at all
    assert gate("read_file", path="/repo/notes.md") is None
    (isolated / "home" / ".hermes").mkdir(parents=True)
    (isolated / "home" / ".hermes" / "config.yaml").write_text("plugins: [unclosed\n  - x: {")
    assert gate("terminal", command="ls") is None
    assert gate("read_file", path="/repo/notes.md") is None
    assert blocked(gate("terminal", command="cat ~/.local/state/google-tools/grants/grants.json"))   # defaults hold


def test_the_installed_plugin_is_protected_through_a_link(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "google-tools"
    install.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(install)
    assert blocked(gate("read_file", path=str(link / "package.json")))


# --- files of a sensitive Workspaces area ----------------------------------------------------------


@pytest.fixture
def workspaces(isolated):
    """The default layout under the isolated home: Projects, and Personal (sensitive)."""
    root = isolated / "home" / "Workspaces"
    files = {
        "personal": root / "Personal" / "family" / "data" / "notes.csv",
        "projects": root / "Projects" / "shop" / "data" / "sales.csv",
        "outside": isolated / "elsewhere" / "report.pdf",
    }
    for path in files.values():
        path.parent.mkdir(parents=True)
        path.write_text("x")
    return root, files


def covered(workspaces, isolated, **overrides):
    root, _ = workspaces
    configure(isolated, **{"encrypt_dirs": [str(root / "Personal")], "age_recipients": ["age1examplekey"],
                           **overrides})


def upload(path, **args):
    return gate("google_drive_upload", path=str(path), **args)


def test_an_upload_from_a_sensitive_area_is_refused_when_nothing_covers_it(workspaces, isolated):
    _, files = workspaces
    configure(isolated)
    assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE)
    configure(isolated, encrypt_dirs=[], age_recipients=["age1examplekey"])
    assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE)


def test_an_upload_is_refused_when_encrypt_dirs_do_not_cover_the_file(workspaces, isolated):
    root, files = workspaces
    configure(isolated, encrypt_dirs=[str(root / "Projects"), str(root / "Personal" / "other")],
              age_recipients=["age1examplekey"])
    assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE)
    configure(isolated, encrypt_dirs=["Personal", "relative/dir", 7, None], age_recipients=["age1examplekey"])
    assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE)     # relative entries cover nothing
    configure(isolated, encrypt_dirs=str(root / "Personal" / "family" / "data" / "notes.csv"),
              age_recipients=["age1examplekey"])
    assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE)     # not a directory list: a file is no dir


def test_an_upload_is_refused_when_no_age_recipient_is_set(workspaces, isolated):
    root, files = workspaces
    for recipients in ({}, {"age_recipients": []}, {"age_recipients": "age1examplekey"}, {"age_recipients": None}):
        configure(isolated, encrypt_dirs=[str(root / "Personal")], **recipients)
        assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE), recipients


def test_an_upload_from_a_sensitive_area_passes_when_encrypt_dirs_and_recipients_cover_it(workspaces, isolated):
    root, files = workspaces
    covered(workspaces, isolated)
    assert upload(files["personal"]) is None
    assert upload(files["personal"], name="notes.csv", folder="root") is None
    configure(isolated, encrypt_dirs=["~/Workspaces/Personal"], age_recipients=["age1examplekey"])    # as `~`
    assert upload(files["personal"]) is None
    configure(isolated, encrypt_dirs=[str(root / "Projects"), str(root)], age_recipients=["age1examplekey"])
    assert upload(files["personal"]) is None                                    # the whole root covers it too


def test_a_case_variant_path_is_still_a_sensitive_one(workspaces, isolated):
    root, files = workspaces
    variants = (root / "personal" / "family" / "data" / "notes.csv", root / "PERSONAL" / "family" / "x.csv")
    configure(isolated)
    for path in variants:
        assert upload(path) == block_with(plugin.UPLOAD_MESSAGE), path
    assert upload(str(root).lower() + "/Personal/family/data/notes.csv") == block_with(plugin.UPLOAD_MESSAGE)
    covered(workspaces, isolated)
    for path in variants:
        assert upload(path) is None, path
    covered(workspaces, isolated, encrypt_dirs=[str(root / "personal" / "other")])
    assert upload(variants[0]) == block_with(plugin.UPLOAD_MESSAGE)


def test_a_differently_normalized_name_is_still_a_sensitive_one(isolated, monkeypatch):
    area = "Résumé"
    layout = isolated / "layout.json"
    layout.write_text(json.dumps({"root": str(isolated / "ws"), "areas": [
        {"name": "Projects", "role": "projects"}, {"name": unicodedata.normalize("NFC", area), "role": "personal",
                                                    "sensitive": True}]}))
    monkeypatch.setenv("WORKSPACES_LAYOUT", str(layout))
    configure(isolated)
    decomposed = isolated / "ws" / unicodedata.normalize("NFD", area) / "cv.pdf"
    assert upload(decomposed) == block_with(plugin.UPLOAD_MESSAGE)
    assert upload(isolated / "ws" / "Projects" / "cv.pdf") is None


def test_an_upload_of_a_file_that_is_not_in_a_sensitive_area_passes(workspaces, isolated):
    root, files = workspaces
    configure(isolated)
    assert upload(files["projects"]) is None
    assert upload(files["outside"]) is None
    assert upload(root / "Personal") is None                 # the area folder itself is in no area
    assert upload(root / "Projects" / "nothing-here.csv") is None
    assert upload(root.parent / "Workspaces-notes" / "Personal" / "x.csv") is None


def test_a_link_into_a_sensitive_area_is_judged_by_where_it_leads(workspaces, isolated):
    root, files = workspaces
    link = root / "Projects" / "shop" / "shortcut.csv"
    link.symlink_to(files["personal"])
    configure(isolated)
    assert upload(link) == block_with(plugin.UPLOAD_MESSAGE)
    assert upload(root / "Projects" / ".." / "Personal" / "family" / "data" / "notes.csv") == \
        block_with(plugin.UPLOAD_MESSAGE)
    covered(workspaces, isolated)
    assert upload(link) is None


def test_an_upload_path_is_judged_as_the_tool_resolves_it(workspaces, isolated, monkeypatch):
    root, files = workspaces
    configure(isolated)
    tracked(monkeypatch, root / "Personal" / "family")
    assert upload("data/notes.csv") == block_with(plugin.UPLOAD_MESSAGE)           # against the session directory
    assert upload("~/Workspaces/Personal/family/data/notes.csv") == block_with(plugin.UPLOAD_MESSAGE)
    tracked(monkeypatch, root / "Projects")
    assert upload("shop/data/sales.csv") is None


def test_the_upload_check_runs_after_the_human_and_peer_checks(workspaces, isolated, monkeypatch):
    _, files = workspaces
    configure(isolated)
    no_human(monkeypatch)
    assert upload(files["personal"]) == block_with(plugin.human_gate.refusal("google_drive_upload", "yolo mode is on"))
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert upload(files["personal"]) == block_with("google_drive_upload is not available to inbound A2A requests")


def test_other_writes_and_reads_are_not_judged_by_a_path(workspaces, isolated):
    _, files = workspaces
    configure(isolated)
    assert gate("google_drive_folder_create", path=str(files["personal"])) is None
    assert gate("google_sheets_edit", path=str(files["personal"]), attachments=[str(files["personal"])]) is None
    assert gate("google_drive_read", method="download", path=str(files["personal"])) is None
    assert gate("google_drive_upload") is None               # nothing to judge: the tool refuses it itself
    assert gate("google_drive_upload", path="") is None
    assert gate("google_drive_upload", path=5) is None


def test_an_unreadable_layout_blocks_an_upload_and_an_attachment(workspaces, isolated, monkeypatch):
    _, files = workspaces
    covered(workspaces, isolated)
    layout = isolated / "layout.json"
    layout.write_text("{ not json")
    monkeypatch.setenv("WORKSPACES_LAYOUT", str(layout))
    for message in (upload(files["projects"]), upload(files["outside"]),
                    gate("google_gmail_send", to=["a@example.com"], body="b", attachments=[str(files["outside"])])):
        assert blocked(message) and "layout cannot be read" in message["message"]
    assert gate("google_gmail_send", to=["a@example.com"], body="b") is None      # no file, nothing to judge
    assert gate("google_drive_folder_create", name="x") is None


def test_a_profile_with_no_snapshot_has_no_upload_from_a_sensitive_area(workspaces, isolated):
    root, files = workspaces
    write_config(isolated, encrypt_dirs=[str(root / "Personal")], age_recipients=["age1examplekey"])
    assert upload(files["personal"]) == block_with(plugin.SNAPSHOT_MESSAGE)    # covered now, but never registered
    assert upload(files["projects"]) is None                                  # the snapshot is read only where it decides


def test_an_unreadable_configuration_leaves_a_snapshot_that_covers_nothing(workspaces, isolated):
    root, files = workspaces
    home = isolated / "home" / ".hermes"
    plugin._take_snapshot()                                    # no config.yaml
    assert upload(files["personal"]) == block_with(plugin.SNAPSHOT_MESSAGE)
    home.mkdir(parents=True, exist_ok=True)
    for text in ("- a\n- list\n", "plugins: [unclosed\n  - x: {"):
        (home / "config.yaml").write_text(text)
        plugin._take_snapshot()
        assert upload(files["personal"]) == block_with(plugin.SNAPSHOT_MESSAGE), text
    write_config(isolated, encrypt_dirs=[str(root / "Personal")], age_recipients=["age1examplekey"])
    assert upload(files["personal"]) == block_with(plugin.SNAPSHOT_MESSAGE)    # a readable file is not a snapshot
    assert upload(files["projects"]) is None


def test_a_configuration_without_the_plugin_settings_covers_nothing(workspaces, isolated):
    _, files = workspaces
    home = isolated / "home" / ".hermes"
    home.mkdir(parents=True)
    for text in ("", "plugins:\n", "plugins: 3\n", "plugins:\n  entries:\n    google-tools: x\n",
                 "plugins:\n  entries:\n    google-tools:\n      settings: [a]\n"):
        (home / "config.yaml").write_text(text)
        plugin._take_snapshot()
        assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE), text


def register_with(monkeypatch):
    """Register the guard the way Hermes does, with the previews kept off the real display table."""
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())


def test_register_snapshots_the_settings_of_its_home(workspaces, isolated, monkeypatch):
    root, files = workspaces
    write_config(isolated, encrypt_dirs=[str(root / "Personal")], age_recipients=["age1examplekey"])
    register_with(monkeypatch)
    assert plugin._SNAPSHOTS == {str((isolated / "home" / ".hermes").resolve()): {
        "encrypt_dirs": [str(root / "Personal")], "age_recipients": ["age1examplekey"]}}
    assert upload(files["personal"]) is None
    assert upload(files["projects"]) is None


def test_settings_added_after_the_gateway_started_ask_for_a_restart(workspaces, isolated, monkeypatch):
    root, files = workspaces
    write_config(isolated)
    register_with(monkeypatch)
    assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE)
    write_config(isolated, encrypt_dirs=[str(root / "Personal")], age_recipients=["age1examplekey"])
    assert upload(files["personal"]) == block_with(plugin.RESTART_MESSAGE)      # the package still sends it clear
    write_config(isolated, encrypt_dirs=[str(root / "Personal")])               # still not covered
    assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE)
    register_with(monkeypatch)                                                  # the restart
    assert upload(files["personal"]) == block_with(plugin.UPLOAD_MESSAGE)
    write_config(isolated, encrypt_dirs=[str(root / "Personal")], age_recipients=["age1examplekey"])
    register_with(monkeypatch)
    assert upload(files["personal"]) is None


def test_settings_removed_after_the_gateway_started_change_nothing(workspaces, isolated, monkeypatch):
    # the package still encrypts by what it registered with, so the snapshot alone decides
    root, files = workspaces
    write_config(isolated, encrypt_dirs=[str(root / "Personal")], age_recipients=["age1examplekey"])
    register_with(monkeypatch)
    write_config(isolated)
    assert upload(files["personal"]) is None
    (isolated / "home" / ".hermes" / "config.yaml").unlink()
    assert upload(files["personal"]) is None


def test_the_snapshot_is_kept_per_profile_home(workspaces, isolated, monkeypatch):
    root, files = workspaces
    write_config(isolated, encrypt_dirs=[str(root / "Personal")], age_recipients=["age1examplekey"])
    register_with(monkeypatch)
    other = isolated / "home" / ".hermes" / "profiles" / "worker"
    monkeypatch.setattr(plugin, "_hermes_home", lambda: other)                  # another profile's turn
    assert upload(files["personal"]) == block_with(plugin.SNAPSHOT_MESSAGE)
    monkeypatch.setattr(plugin, "_hermes_home", lambda: isolated / "home" / ".hermes" / "x" / "..")
    assert upload(files["personal"]) is None                                    # keyed by the resolved path


def test_a_registration_that_cannot_snapshot_still_installs_the_hook(workspaces, isolated, monkeypatch):
    _, files = workspaces

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    monkeypatch.setattr(plugin, "_hermes_home", boom)
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.hooks == [("pre_tool_call", plugin.gate)] and plugin._SNAPSHOTS == {}
    assert upload(files["personal"]) == block_with(plugin.UNCHECKED_MESSAGE)      # no home to key a snapshot by
    assert upload(files["projects"]) is None


@pytest.mark.parametrize("tool", MAIL_TOOLS)
def test_a_mail_never_attaches_a_file_of_a_sensitive_area(workspaces, isolated, tool):
    root, files = workspaces
    covered(workspaces, isolated)       # encryption covers uploads only: an attachment goes in the clear
    args = {"to": ["a@example.com"], "body": "hello"}
    assert gate(tool, **args, attachments=[str(files["personal"])]) == block_with(plugin.ATTACHMENT_MESSAGE)
    assert gate(tool, **args, attachments=[str(files["projects"]), str(files["personal"])]) == \
        block_with(plugin.ATTACHMENT_MESSAGE)
    assert gate(tool, **args, attachments=[str(root / "personal" / "family" / "data" / "notes.csv")]) == \
        block_with(plugin.ATTACHMENT_MESSAGE)
    assert gate(tool, **args, attachments=[str(files["projects"]), str(files["outside"])]) is None
    assert gate(tool, **args, attachments=[str(root / "Personal")]) is None
    assert gate(tool, **args) is None
    assert gate(tool, **args, attachments=[]) is None


def test_a_mail_judges_its_attachments_without_a_configuration(workspaces, isolated):
    _, files = workspaces
    assert gate("google_gmail_send", to=["a@example.com"], body="b", attachments=[str(files["outside"])]) is None
    assert blocked(gate("google_gmail_send", to=["a@example.com"], body="b", attachments=[str(files["personal"])]))


def test_a_draft_sent_as_it_is_carries_no_attachments_to_judge(workspaces):
    assert gate("google_gmail_send", draft_id="r123") is None


def test_an_attachment_path_that_cannot_be_resolved_blocks_the_call(workspaces):
    result = gate("google_gmail_send", to=["a@example.com"], body="b", attachments=["/a\0b"])
    assert result == block_with(plugin.UNCHECKED_MESSAGE)


# --- the hook itself --------------------------------------------------------------------------------


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "bypass", boom)
    assert gate("terminal", command="ls") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("read_file", path="a.txt") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("google_sheets_edit", spreadsheet="abc") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("google_grant_create", reason="a reason") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("google_future_write") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("google_sheets_read", method="list") is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("google_gmail_trash") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("google_drive_read", method="search") is None
    assert gate("web_search", query="x") is None


def test_a_failing_file_check_blocks_the_write(monkeypatch, workspaces, isolated):
    _, files = workspaces

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin.workspace_layout, "load", boom)
    assert upload(files["projects"]) == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("google_gmail_send", attachments=[str(files["outside"])]) == block_with(plugin.UNCHECKED_MESSAGE)


def test_a_failing_command_reader_blocks_the_terminal(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin.shell_commands, "runs", boom)
    assert gate("terminal", command="ls") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("read_file", path="a.txt") is None      # the file tools never reach the command reader


def test_the_command_reader_falls_back_to_the_pattern_on_a_line_it_cannot_read():
    # an unclosed quote cannot be read: the pattern alone decides
    assert gate("terminal", command="google-tools-cli login 'x") == block_with(plugin.BYPASS_MESSAGE)
    assert gate("terminal", command="gcloud auth login \"x") == block_with(plugin.BYPASS_MESSAGE)
    assert gate("terminal", command="grep notes 'x") is None


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    assert line("google_sheets_edit", spreadsheet="private", text="a private cell") == "edit sheet"
    assert line("google_gmail_send", to=["private@example.com"], body="a private body") == "send mail"
    assert line("google_drive_upload", path="/private/dir/file.csv", name="private") == "upload file"
    assert line("google_run_service_deploy", service="private", project="private") == "deploy service"
    assert line("google_comments_read", file="private") == "read comments"
    assert line("google_account_read", method="check", account="private") == "check"
    assert line("google_sheets_read", method="values", spreadsheet="private", range="A1") == "values"
    assert line("google_gmail_read", method="search", query="a private query") == "search"
    assert line("google_drive_read", method="download", file="private") == "download"
    assert line("google_run_read", method="iam", project="private") == "iam"
    assert line("google_grant_read", method="log", limit=5) == "log"
    assert line("google_gmail_read", method="a private value", query="a private query") is None


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
    assert set(plugin.METHODS) | {"google_comments_read"} == plugin.READS     # every read but comments has a method
    assert set(plugin.LABELS) == {"google_comments_read", *KNOWN_WRITES}


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
