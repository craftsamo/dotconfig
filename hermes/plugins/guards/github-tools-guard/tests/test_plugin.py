import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("github_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
CHECKOUT = "~/ghq/github.com/craft-agent/github-tools"
# The `provides_tools` list of the github-tools package's plugin.yaml, written out so this runs without
# the package installed.
PROVIDED = (
    "github_issue_close", "github_issue_comment", "github_issue_create", "github_issue_develop",
    "github_issue_edit", "github_issue_read", "github_issue_relate", "github_issue_reopen",
    "github_label_create", "github_label_delete", "github_label_edit", "github_label_read",
    "github_milestone_create", "github_milestone_edit", "github_milestone_read",
    "github_pr_close", "github_pr_comment", "github_pr_create", "github_pr_edit", "github_pr_merge",
    "github_pr_read", "github_pr_ready", "github_pr_reopen", "github_pr_review",
    "github_project_create", "github_project_field_ensure", "github_project_item_add",
    "github_project_item_archive", "github_project_item_convert", "github_project_item_create",
    "github_project_item_edit", "github_project_item_unarchive", "github_project_link",
    "github_project_read", "github_project_unlink", "github_project_view_ensure",
    "github_release_create", "github_release_delete", "github_release_edit", "github_release_publish",
    "github_release_read", "github_repo_archive", "github_repo_create", "github_repo_edit",
    "github_repo_read", "github_repo_unarchive", "github_repo_visibility",
    "github_ruleset_create", "github_ruleset_delete", "github_ruleset_edit", "github_ruleset_read",
    "github_run_cancel", "github_run_read", "github_run_rerun",
    "github_stack_link", "github_stack_read", "github_stack_unlink",
    "github_workflow_read", "github_workflow_run",
)
READS = tuple(tool for tool in PROVIDED if tool.endswith("_read"))
WRITES = (*(tool for tool in PROVIDED if tool not in READS), "github_foo_bar")
OLD_GITHUB_ACCESS = ("github_issue", "github_board", "github_repo", "github_pr", "github_change", "github_mandate")


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
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": None)   # no terminal record
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)     # a person is there to answer cards
    return tmp_path


def gate(tool, **args):
    return plugin.gate(tool_name=tool, args=args)


def terminal(command, **args):
    return gate("terminal", command=command, **args)


def block(message):
    return {"action": "block", "message": message}


def blocked(directive):
    return isinstance(directive, dict) and directive["action"] == "block" and bool(directive["message"])


def no_human(monkeypatch, reason="yolo mode is on"):
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: reason)


def tracked(monkeypatch, cwd):
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": str(cwd))


def test_the_provided_tools_are_the_reads_plus_the_writes():
    assert len(PROVIDED) == len(set(PROVIDED))
    assert set(plugin.READS) == set(READS) == set(plugin.METHODS)
    assert set(plugin.METHODS) | set(plugin.LABELS) == set(PROVIDED)
    assert not set(plugin.METHODS) & set(plugin.LABELS)
    assert all(plugin._is_tool(tool) for tool in PROVIDED)


def test_reads_pass_with_no_human(monkeypatch):
    no_human(monkeypatch)
    for tool in READS:
        assert gate(tool, method="list") is None


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_with_no_human(monkeypatch, tool):
    no_human(monkeypatch)
    assert gate(tool, repo="a/b", body="hi") == block(plugin.human_gate.refusal(tool, "yolo mode is on"))


@pytest.mark.parametrize("reason", [
    "yolo mode is on", "approvals are off (approvals.mode: off)", "this is a cron job",
    "this is a single-query run", "this platform is unattended", "nobody is present to answer",
])
def test_every_reason_nobody_can_answer_blocks_a_write(monkeypatch, reason):
    no_human(monkeypatch, reason)
    assert gate("github_pr_merge", pr="1") == block(plugin.human_gate.refusal("github_pr_merge", reason))
    assert gate("github_pr_read", method="view") is None


def test_the_genuine_check_refuses_a_write_in_this_headless_test_run(monkeypatch):
    spec = importlib.util.spec_from_file_location("github_tools_guard_genuine_gate",
                                                  ROOT.parent.parent / "_shared" / "human_gate.py")
    genuine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(genuine)
    monkeypatch.setattr(plugin.human_gate, "no_human", genuine.no_human)
    assert gate("github_issue_create", title="x")["action"] == "block"
    assert gate("github_issue_read", method="list") is None


@pytest.mark.parametrize("tool", WRITES)
def test_writes_pass_with_a_human(tool):
    assert gate(tool, repo="a/b", body="hi") is None


def test_a_tool_a_later_release_adds_counts_as_a_write(monkeypatch):
    assert plugin._is_write("github_foo_bar") and plugin._is_write("github_issue_read_all")
    no_human(monkeypatch)
    assert gate("github_foo_bar") == block(plugin.human_gate.refusal("github_foo_bar", "yolo mode is on"))


def test_inbound_a2a_blocks_reads_and_writes(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in (*READS, *WRITES):
        assert gate(tool) == block(f"{tool} is not available to inbound A2A requests")


def test_the_old_github_access_tools_are_not_this_guards(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in OLD_GITHUB_ACCESS:
        assert not plugin._is_tool(tool)
        assert gate(tool, action="create") is None


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="github-tools-cli") is None
    assert gate("browser_click", ref="github_issue_create") is None
    assert gate("mcp_github_issue_create") is None
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "gh issue create --title x", "gh issue comment 3 --body hi", "gh issue close 3", "gh -R a/b issue edit 3",
    "gh project item-edit --id X", "gh project item-create 1 --owner me", "gh api graphql -f query=x",
    "gh api repos/a/b/issues", "/opt/homebrew/bin/gh issue reopen 2", "GH_TOKEN=x gh issue delete 1",
    "cd repo && gh issue create", "echo ok; gh label create bug", "env gh project link 1",
    "x=$(gh api user)", 'bash -c "gh issue create --title x"', "sh -c 'gh issue close 1'",
    "eval 'gh issue comment 1 -b x'", "gh issue \\\n create --title x", "curl -H \"Authorization: $(gh auth token)\" u",
    "gh auth status --show-token", "gh alias set mk 'issue create'", "gh extension install x/y",
    "echo gh issue create",  # a mention in text reads like a call: blocked, conservatively
    "gh issue -R a/b create --title x", "gh issue --repo=a/b close 3", "gh label -R a/b delete bug",
    "gh auth --hostname=github.com token", "gh issue --org team create",
    "gh repo create a/b --private", "gh repo new a/b --public", "gh repo edit a/b --visibility public",
    "gh repo archive a/b --yes", "gh -R a/b repo unarchive --yes",
    "gh pr create --fill", "gh pr create --repo me/fork --fill", "gh pr merge 3 --squash --admin",
    "gh pr edit 3 --add-reviewer bob", "gh pr comment 3 -b hi", "gh pr ready 3", "gh pr close 3", "gh pr -R a/b reopen 3",
    "gh release create v1 --notes x", "gh release edit v1 --draft=false", "gh run rerun 42 --failed",
    "gh workflow run deploy.yml -f env=prod", "gh -R a/b workflow run 9",
    # the verbs the github_* tools carry on a card, not forbidden outright
    "gh pr review 3 --approve", "gh pr -R a/b review 3 --request-changes", "gh release delete v1 --yes",
    "gh release --repo a/b delete v1", "gh run cancel 42", "gh -R a/b run cancel 42",
])
def test_terminal_gh_writes_are_blocked(command):
    assert terminal(command) == block(plugin.gh_terminal.MESSAGE)


@pytest.mark.parametrize("command", [
    "gh secret set API_KEY --body x", "gh secret delete API_KEY -R a/b", "gh variable set NAME --body v",
    "gh variable delete NAME", "gh gist create notes.md --public", "gh gist edit 1a2b", "gh gist delete 1a2b",
    "gh repo delete a/b --yes", "gh repo rename new-name", "gh repo fork a/b --clone", "gh repo deploy-key add k.pub",
    "gh repo autolink create JIRA- https://x/<num>", "gh repo sync me/fork", "gh ssh-key add k.pub",
    "gh gpg-key delete ABC", "gh release delete-asset v1 a.zip", "gh run delete 42",
    "gh cache delete --all", "gh -R a/b repo delete --yes", 'bash -c "gh secret set X --body y"',
    "echo gh gist create x",  # a mention reads like a call here too
    "gh pr revert 3", "gh pr update-branch 3", "gh pr lock 3",
    "gh release upload v1 a.zip", "gh workflow disable deploy.yml", "gh workflow enable 9",
    "gh secret -R a/b set X --body y", "gh release --repo a/b delete-asset v1 a.zip", "gh run --repo=a/b delete 1",
    "gh cache -R a/b delete --all", 'sh -c "gh variable -R a/b set X"', "gh secret --org team set X",
    "gh --foo bar secret set X", "gh secret -o team delete X",
])
def test_writes_no_tool_offers_are_blocked_and_say_so(command):
    assert terminal(command) == block(plugin.gh_terminal.NEVER_MESSAGE)


@pytest.mark.parametrize("command", [
    "gh issue view 3", "gh issue list --repo a/b", "gh pr view 3 --json state", "gh repo view a/b --json visibility",
    "gh project list --owner me", "gh project item-list 1 --owner me", "ls ~/Worktrees/x/feat-hermes-github-tools",
    "git log", "gh auth status", "bash -c 'gh issue view 3'", "gh secret list -R a/b", "gh variable list",
    "gh gist view 1a2b", "gh gist list", "gh repo view a/b", "gh repo clone a/b", "gh release view v1",
    "gh run view 42 --log-failed", "gh cache list", "gh ssh-key list", "gh pr checks 3 --repo me/app",
    "gh pr diff 3", "gh pr list --author @me", "gh pr status", "gh release list", "gh release download v1",
    "gh run list --limit 5", "gh run watch 42", "gh workflow list", "gh workflow view deploy.yml",
    "gh issue -R a/b view 3", "gh secret -R a/b list", "gh release --repo a/b view v1",
    "gh repo list me", "gh repo set-default a/b", "gh repo license list", "gh repo gitignore view Python",
    "gh release view delete", "gh issue list --label create", "gh issue list --search 'create login'",
    "gh pr list --json title --jq '.[] | .title'", "gh pr view review", "gh run view cancel",
    "gh", "gh --version", "gh help pr", "gh pr --help", "gh status", "gh search issues login --repo a/b",
    "gh ruleset view 1 --repo a/b", "gh config get editor", "gh -R a/b issue view 3", "gh variable get X",
    "gh attestation verify f.tgz --owner o", "timeout 30 gh run watch 42", "gh pr checkout 12",
    "sh -lc 'gh pr view 3'", "eval 'gh issue list'", "echo use gh auth login",  # a mention of a non-write runs nothing
    "find ~/.config/gh -type f", "rg gh src/", "ls ~/.config/gh", "git log --grep gh", "watch -n 5 gh run list",
    "gh auth status --hostname github.com", "GH_PAGER=cat gh issue view 1", "xargs rg gh src/",
    "sudo ls /opt/gh /opt/bin", "xargs -0 grep -l gh", "nice -n 5 gh pr view 3", "timeout -s KILL 10 gh run view 4",
])
def test_terminal_reads_and_other_work_stay_open(command):
    assert terminal(command) is None


@pytest.mark.parametrize("command", [
    "gh auth login", "gh auth refresh -s delete_repo", "gh auth logout", "gh config set editor vim",
    "gh codespace create", "gh agent-task create 'fix it'", "gh copilot suggest x", "gh my-extension run",
    "bash -c 'gh auth login'", "sh -lc \"gh config set prompt disabled\"", "eval 'gh auth logout'",
    "timeout 10 gh auth setup-git", "xargs -0 gh auth login", "env -i GH_HOST=x gh auth login",
    "bash -c 'true; \"gh\" auth login'",  # a quote cut by the separator
    "gh auth --hostname status login",  # read as `auth login --hostname status` by gh
    "gh pr --foo view create-later",
    "sudo -u x gh auth login", "xargs -I {} gh auth login", "bash <<< 'gh auth login'", "bash -c -- 'gh auth login'",
    "bash -o pipefail -c 'gh auth login'", "bash -c -o pipefail 'gh auth login'",
    "GH_PAGER='sh -c \"gh auth login\"' gh issue view 1",  # a pager gh starts is a command too
    "env GH_PAGER='gh auth login' GH_FORCE_TTY=1 gh issue view 1", "sudo nice -n 5 gh auth login",
    "timeout -s KILL 10 gh auth login",
    "command " * 12 + "\"gh\" issue view 3",  # nesting past the limit fails closed
    "nice " + "-x nice " * 30 + "gh pr view 3",  # so do readings past the budget, quickly
])
def test_any_other_gh_command_is_blocked_by_default(command):
    assert terminal(command) == block(plugin.gh_terminal.UNKNOWN_MESSAGE)


def test_a_nested_write_is_blocked_with_its_own_message():
    message, never = plugin.gh_terminal.MESSAGE, plugin.gh_terminal.NEVER_MESSAGE
    for command, expected in (("bash -c 'gh label -R a/b create x'", message),
                              ("eval \"gh pr -R a/b review 3 --approve\"", message),
                              ("gh auth login; gh repo -R a/b fork", never),
                              ("gh run cancel 3; gh secret set X", never),
                              ("find . -prune -exec \"gh\" issue create -R me/app -t x -b y \\;", message),
                              ("gh auth --hostname=github.com status --show-token", message),
                              ("gh auth status -t", message), ("gh auth status -ht", message),
                              # -c runs its script; the here-string is only its input
                              ("bash -c '\"gh\" issue create -R me/app -t x -b y' <<< ignored", message)):
        assert terminal(command) == block(expected), command


def test_the_gh_messages_name_the_tools():
    assert "github_*" in plugin.gh_terminal.MESSAGE and "github_issue_read" in plugin.gh_terminal.MESSAGE
    assert "github_run_read" in plugin.gh_terminal.UNKNOWN_MESSAGE
    for message in (plugin.gh_terminal.MESSAGE, plugin.gh_terminal.NEVER_MESSAGE,
                    plugin.gh_terminal.UNKNOWN_MESSAGE):
        assert message.endswith("Nothing was run.")
    assert "review" not in plugin.gh_terminal.NEVER_MESSAGE
    assert "Tell the user" in plugin.gh_terminal.NEVER_MESSAGE


def test_the_tools_verbs_left_the_never_list():
    never = plugin.gh_terminal.NEVER
    assert "review" not in never["pr"] and "cancel" not in never["run"] and "delete" not in never["release"]
    assert {"delete-asset", "upload"} == never["release"]
    assert {"review"} <= plugin.gh_terminal.TOOL_WRITES["pr"]
    assert {"cancel", "rerun"} == plugin.gh_terminal.TOOL_WRITES["run"]
    assert "delete" in plugin.gh_terminal.TOOL_WRITES["release"]


@pytest.mark.parametrize("command", [
    "github-tools-cli run github_issue_create",
    "/opt/homebrew/bin/github-tools-cli run github_pr_merge",
    "bash -c 'github-tools-cli run github_issue_create'",
    "github-tools",
    "/opt/homebrew/bin/github-tools",
    "npx github-tools-cli list",
    "npx -y @craftsamo/github-tools",
    "pnpm dlx @craftsamo/github-tools",
    "bunx @craftsamo/github-tools",
    "node ~/.hermes/plugins/github-tools/dist/cli.js run github_issue_create",
    "node $HOME/.hermes/plugins/github-tools/dist/mcp.js",
    "bun ~/ghq/github.com/craft-agent/github-tools/dist/cli.js",
    "cat ~/.hermes/plugins/github-tools/__init__.py",
    "ls ~/.hermes/plugins/github-tools",
    "cd ~/.hermes/plugins/github-tools && ls",
    "cd ~/.hermes/plugins/github-tools",
    "ls ${HOME}/.hermes/plugins/github-tools/dist",
    "cat ~/.hermes/profiles/work/plugins/github-tools/package.json",
    "cat ~/.hermes/plugins/github-t*ls/dist/cli.js",
    "cat ~/.hermes/plugins/github-tool?/package.json",
])
def test_terminal_blocks_ways_around_the_tools(command):
    assert blocked(terminal(command)), command


@pytest.mark.parametrize("command", [
    f"cd {CHECKOUT}",
    f"cd {CHECKOUT} && ls",
    f"cd {CHECKOUT} && pnpm test",
    f"cd {CHECKOUT} && bun test",
    f"cd {CHECKOUT} && node scripts/check.mjs",
    f"ls {CHECKOUT}/src",
    f"cat {CHECKOUT}/package.json",
    f"git -C {CHECKOUT} log --oneline",
    f"grep -rn approval {CHECKOUT}/src",
    "ls ~/.hermes/plugins",
    "ls ~/.hermes/plugins/signal-tools",
    "git log -- hermes/plugins/guards/github-tools-guard",
    "ls ~/Worktrees/repo/feat-github-tools",
    "cat docs/github-tools.md",
    'grep -r "github tools" notes.md',
    "ls ~/.hermes/plugins/github-tools-guard",
])
def test_terminal_allows_the_source_checkout_and_plain_work(command):
    assert terminal(command) is None, command


def test_a_link_in_a_word_is_followed(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "github-tools"
    install.mkdir(parents=True)
    (isolated / "shortcut").symlink_to(install)
    assert blocked(terminal(f"cat {isolated}/shortcut/package.json"))
    assert terminal(f"cat {isolated}/home/package.json") is None


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    plugins = isolated / "home" / ".hermes" / "plugins"
    (plugins / "github-tools").mkdir(parents=True)
    assert terminal("cat github-tools/package.json") is None            # no record of the directory
    tracked(monkeypatch, plugins)
    assert blocked(terminal("cat github-tools/package.json"))
    assert blocked(terminal("cat ./github-tools/../github-tools/package.json"))
    assert terminal("ls") is None
    tracked(monkeypatch, isolated / "home" / "checkout")
    assert terminal("cat github-tools/package.json") is None


def test_a_terminal_inside_the_installed_plugin_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "github-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    assert terminal("ls") == block(plugin.CWD_MESSAGE)
    tracked(monkeypatch, install / "dist")
    assert blocked(terminal("ls"))
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert blocked(terminal("ls"))


def test_a_terminal_in_a_profiles_own_copy_is_blocked(monkeypatch, isolated):
    copy = isolated / "somewhere" / "plugins" / "github-tools"
    copy.mkdir(parents=True)
    tracked(monkeypatch, copy)
    assert blocked(terminal("ls"))
    monkeypatch.setenv("HERMES_HOME", str(isolated / "profile-home"))
    assert blocked(terminal("ls", workdir=str(isolated / "profile-home" / "plugins" / "github-tools")))


def test_the_source_checkout_is_a_fine_working_directory(monkeypatch, isolated):
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent" / "github-tools"
    (checkout / "dist").mkdir(parents=True)
    tracked(monkeypatch, checkout)
    assert terminal("ls") is None
    assert terminal("pnpm test") is None
    assert terminal("ls", workdir=str(checkout / "dist")) is None
    assert terminal("cat package.json") is None


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "github-tools"
    tracked(monkeypatch, install)
    assert terminal("node build.js", workdir=str(isolated)) is None
    assert terminal("ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(terminal("ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".hermes" / "plugins")
    assert blocked(terminal("ls", workdir="github-tools"))      # relative: the recorded one


def test_the_hook_hands_its_ids_to_the_terminal_record(monkeypatch):
    asked = []
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": asked.append((task_id, session_id)))
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}, task_id="t1", session_id="s1") is None
    assert plugin.gate(tool_name="read_file", args={"path": "a.txt"}, task_id="t1", session_id="s1") is None
    assert asked == [("t1", "s1"), ("t1", "s1")]


def test_a_file_tools_relative_path_resolves_against_the_recorded_directory(monkeypatch, isolated):
    plugins = isolated / "home" / ".hermes" / "plugins"
    (plugins / "github-tools" / "dist").mkdir(parents=True)
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent"
    (checkout / "github-tools").mkdir(parents=True)
    assert gate("write_file", path="github-tools/dist/cli.js", content="x") is None     # no record of the directory
    tracked(monkeypatch, plugins)
    assert gate("write_file", path="github-tools/dist/cli.js", content="x") == block(plugin.BYPASS_MESSAGE)
    assert blocked(gate("read_file", path="./github-tools/../github-tools/package.json"))
    assert blocked(gate("search_files", pattern="x", path="github-tools"))
    assert gate("read_file", path="notes.md") is None                   # the recorded directory alone is no reason
    tracked(monkeypatch, checkout)
    assert gate("read_file", path="github-tools/README.md") is None
    assert gate("write_file", path="github-tools/notes.md", content="x") is None


def v4a(*headers):
    return "\n".join(["*** Begin Patch", *headers, "@@ hint @@", "-old", "+new", "*** End Patch"])


def test_a_patchs_file_headers_resolve_against_the_recorded_directory(monkeypatch, isolated):
    plugins = isolated / "home" / ".hermes" / "plugins"
    (plugins / "github-tools" / "dist").mkdir(parents=True)
    tracked(monkeypatch, plugins)
    for header in ("*** Update File: github-tools/dist/cli.js", "*** Add File: github-tools/new.js",
                   "*** Delete File: ./github-tools/package.json", "***Update File:   github-tools/x.js  ",
                   "*** Move File: notes.md -> github-tools/notes.md",
                   "*** Move File: github-tools/a.js -> notes.md"):
        assert blocked(gate("patch", mode="patch", patch=v4a("*** Update File: notes.md", header))), header
    assert blocked(gate("patch", mode="patch", patch=v4a("*** Update File: github-tools/dist/cli.js").replace("\n", "\r\n")))
    assert gate("patch", mode="patch", patch=v4a("*** Update File: notes.md")) is None
    assert gate("patch", mode="patch", patch=v4a("*** Move File: a.md -> b.md")) is None
    tracked(monkeypatch, isolated / "home" / "checkout")
    assert gate("patch", mode="patch", patch=v4a("*** Update File: github-tools/dist/cli.js")) is None
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": None)      # no record
    assert gate("patch", mode="patch", patch=v4a("*** Update File: github-tools/dist/cli.js")) is None
    assert blocked(gate("patch", mode="patch", patch=v4a("*** Update File: ~/.hermes/plugins/github-tools/x.js")))
    assert gate("patch", mode="patch", patch=None) is None


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


@pytest.mark.parametrize("tool, args", [
    ("read_file", {"path": "~/.hermes/plugins/github-tools/__init__.py"}),
    ("read_file", {"path": "$HOME/.hermes/plugins/github-tools/dist/cli.js"}),
    ("write_file", {"path": "~/.hermes/plugins/github-tools/dist/cli.js", "content": "x"}),
    ("search_files", {"pattern": "x", "path": "~/.hermes/plugins/github-tools"}),
    ("patch", {"path": "/tmp/x", "patch": "*** Update File: ~/.hermes/plugins/github-tools/plugin.yaml"}),
    ("read_file", {"path": "~/.hermes/profiles/work/plugins/github-tools/plugin.yaml"}),
])
def test_file_tools_block_the_installed_plugin_by_text(tool, args):
    assert gate(tool, **args) == block(plugin.BYPASS_MESSAGE)


def test_file_tools_block_the_installed_plugin_by_real_path(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "github-tools"
    install.mkdir(parents=True)
    (install / "package.json").write_text("{}")
    link = isolated / "shortcut"
    link.symlink_to(install)
    for path in (install / "package.json", install, link / "package.json", link,
                 isolated / "other" / ".." / "home" / ".hermes" / "plugins" / "github-tools"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "home" / ".hermes" / "plugins")) is None
    monkeypatch.setenv("HERMES_HOME", str(isolated / "profile"))
    assert blocked(gate("read_file", path=str(isolated / "profile" / "plugins" / "github-tools" / "x")))


def test_file_tools_read_the_source_checkout(isolated):
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent" / "github-tools"
    (checkout / "dist").mkdir(parents=True)
    (checkout / "dist" / "cli.js").write_text("x")
    assert gate("read_file", path=f"{CHECKOUT}/src/core/issues/read.ts") is None
    assert gate("read_file", path=str(checkout / "dist" / "cli.js")) is None
    assert gate("write_file", path=str(checkout / "notes.md"), content="x") is None
    assert gate("search_files", pattern="approval", path=CHECKOUT) is None
    assert gate("read_file", path=str(isolated / "home" / ".hermes" / "plugins" / "github-tools-guard")) is None


def test_file_tools_may_write_about_the_package(isolated):
    assert gate("write_file", path="notes.md", content="npx -y @craftsamo/github-tools, github-tools/dist/cli.js") is None


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "bypass", boom)
    assert terminal("ls") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("read_file", path="a.txt") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("github_issue_create", title="x") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("github_foo_bar") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("github_issue_read", method="list") is None
    assert gate("github_issue", action="list") is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("github_pr_merge", pr="1") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("github_repo_read", method="view") is None
    assert gate("web_search", query="x") is None


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    private = "private words"
    assert line("github_issue_create", title=private, body=private, repo="acme/secret") == "create issue"
    assert line("github_pr_merge", pr="acme/secret#3", name=private) == "merge PR"
    assert line("github_issue_comment", issue="acme/secret#3", body=private) == "comment on issue"
    assert line("github_issue_read", method="list", query=private) == "list"
    assert line("github_issue_read", method="view", issue="acme/secret#3") == "view"
    assert line("github_pr_read", method="diff", pr="acme/secret#3") == "diff"
    assert line("github_pr_read", method="checks", pr="acme/secret#3") == "checks"
    assert line("github_project_read", method="item_list", query=private) == "item_list"
    assert line("github_label_read", method="list", name=private) == "list"
    assert line("github_issue_read", method=private, query=private) is None
    assert line("github_label_read", method="view", query=private) is None
    assert line("github_issue_read", query=private) is None


def test_every_tool_has_a_progress_line_that_carries_no_free_text(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())
    private = "private words"
    free = {key: private for key in ("query", "text", "path", "name", "body", "title", "command", "url")}
    for tool in PROVIDED:
        assert tool in display._PREVIEW_BUILDERS, tool
        if tool in plugin.METHODS:
            assert display.build_tool_preview(tool, {**free, "method": private}, max_len=0) is None
            for method in plugin.METHODS[tool]:
                assert display.build_tool_preview(tool, {**free, "method": method}, max_len=0) == method
        else:
            line = display.build_tool_preview(tool, free, max_len=0)
            assert line == plugin.LABELS[tool] and private not in line


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
