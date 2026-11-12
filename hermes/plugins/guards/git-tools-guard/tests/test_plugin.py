import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("git_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
CHECKOUT = "~/ghq/github.com/craft-agent/git-tools"
# The tools the git-tools package registers, written out so this runs without the package installed.
PROVIDED = (
    "git_repo_read", "git_commit_read", "git_rebase_read", "git_worktree_read", "git_push_read",
    "git_commit_stage", "git_commit_create", "git_commit_amend", "git_commit_verify",
    "git_rebase_start", "git_rebase_resume", "git_rebase_split",
    "git_worktree_add", "git_worktree_remove", "git_push_send",
)
READS = tuple(tool for tool in PROVIDED if tool.endswith("_read"))
WRITES = (*(tool for tool in PROVIDED if tool not in READS), "git_foo_bar", "git_commit_squash")
MESSAGE, UNSAFE, UNKNOWN = plugin.git_terminal.MESSAGE, plugin.git_terminal.UNSAFE_MESSAGE, plugin.git_terminal.UNKNOWN_MESSAGE


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
    assert len(PROVIDED) == len(set(PROVIDED)) == 15
    assert set(plugin.READS) == set(READS) == set(plugin.METHODS)
    assert set(plugin.METHODS) | set(plugin.LABELS) == set(PROVIDED)
    assert not set(plugin.METHODS) & set(plugin.LABELS)
    assert all(plugin._is_tool(tool) for tool in PROVIDED)


def test_reads_pass_with_no_human(monkeypatch):
    no_human(monkeypatch)
    for tool in READS:
        assert gate(tool, method="status") is None


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_with_no_human(monkeypatch, tool):
    no_human(monkeypatch)
    assert gate(tool, message="x", branch="main") == block(plugin.human_gate.refusal(tool, "yolo mode is on"))


@pytest.mark.parametrize("reason", [
    "yolo mode is on", "approvals are off (approvals.mode: off)", "this is a cron job",
    "this is a single-query run", "this platform is unattended", "nobody is present to answer",
])
def test_every_reason_nobody_can_answer_blocks_a_write(monkeypatch, reason):
    no_human(monkeypatch, reason)
    assert gate("git_push_send", branch="main") == block(plugin.human_gate.refusal("git_push_send", reason))
    assert gate("git_push_read", method="preview") is None


def test_the_genuine_check_refuses_a_write_in_this_headless_test_run(monkeypatch):
    spec = importlib.util.spec_from_file_location("git_tools_guard_genuine_gate",
                                                  ROOT.parent.parent / "_shared" / "human_gate.py")
    genuine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(genuine)
    monkeypatch.setattr(plugin.human_gate, "no_human", genuine.no_human)
    assert gate("git_commit_create", message="x")["action"] == "block"
    assert gate("git_repo_read", method="status") is None


@pytest.mark.parametrize("tool", WRITES)
def test_writes_pass_with_a_human(tool):
    assert gate(tool, message="x", branch="main") is None


def test_a_tool_a_later_release_adds_counts_as_a_write(monkeypatch):
    assert plugin._is_write("git_foo_bar") and plugin._is_write("git_repo_read_all")
    assert not plugin._is_write("git_repo_read")
    no_human(monkeypatch)
    assert gate("git_foo_bar") == block(plugin.human_gate.refusal("git_foo_bar", "yolo mode is on"))


def test_inbound_a2a_blocks_reads_and_writes(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    for tool in (*READS, *WRITES):
        assert gate(tool) == block(f"{tool} is not available to inbound A2A requests")


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="git-tools-cli") is None
    assert gate("browser_click", ref="git_commit_create") is None
    assert gate("mcp_git_commit_create") is None
    assert gate("github_issue_create", title="x") is None        # github-tools-guard's, not this one
    assert gate("git_worktree", action="add") is None            # no `<area>_<verb>`: not a package tool
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "git status", "git status -sb", "git log", "git log --oneline -n 5", "git log --grep=commit",
    "git log --grep commit", "git log --format=%H -- commit", "git log -c", "git log -- --output=x",
    "git diff", "git diff HEAD~1 --stat", "git diff -u", "git diff --text", "git diff --no-ext-diff",
    "git diff --no-textconv", "git diff --output-indicator-new=+", "git show HEAD:README.md",
    "git blame -L 1,5 file", "git annotate file", "git shortlog -sn", "git describe --tags",
    "git rev-parse --show-toplevel", "git rev-list --count HEAD", "git ls-files", "git ls-tree HEAD",
    "git ls-remote origin", "git cat-file -p HEAD", "git merge-base a b", "git for-each-ref --format='%(refname)'",
    "git show-ref --heads", "git grep -n foo", "git grep -n -e foo", "git grep -nie O", "git count-objects -v",
    "git check-ignore -v x", "git name-rev HEAD", "git whatchanged -3", "git range-diff a...b", "git cherry -v",
    "git var GIT_AUTHOR_IDENT", "git version", "git --version", "git help log", "git", "git --help",
    "git reflog", "git reflog show HEAD", "git reflog HEAD", "git reflog exists HEAD",
    "git -C ~/Worktrees/x log", "git --no-pager log", "git -P log", "git -C /tmp --no-pager diff",
    "git --git-dir=/x/.git --work-tree=/x status", "git --git-dir /x/.git status", "git --literal-pathspecs log",
    "git --no-optional-locks status", "git -p log", "git -C repo",
    "git-status", "git-diff HEAD", "/usr/lib/git-core/git-log",
])
def test_terminal_git_reads_stay_open(command):
    assert terminal(command) is None, command


@pytest.mark.parametrize("command", [
    "git fetch", "git fetch origin main", "git fetch --all --prune", "git fetch origin refs/pull/1/head:pr-1",
    "git -C repo fetch --tags", "git fetch -j4 origin", "git fetch -qp",
    "git pull --ff-only", "git pull --ff-only origin main", "git pull -q --ff-only", "git pull --ff-only --recurse-submodules",
    "git clone https://example.com/a/b.git", "git clone --depth 1 -b main url dir", "git clone --recurse-submodules url",
    "git clone -bcustom url", "git clone --no-checkout url", "git clone -o up url", "git clone -- url dir",
])
def test_terminal_git_fetches_and_clones_stay_open(command):
    assert terminal(command) is None, command


@pytest.mark.parametrize("command", [
    "git branch", "git branch -a", "git branch -vv", "git branch -r", "git branch --all --verbose",
    "git branch --list 'feat/*'", "git branch -l", "git branch -l 'x*'", "git branch --show-current",
    "git branch --contains abc", "git branch --merged main", "git branch --no-merged", "git branch --no-merged main",
    "git branch --points-at HEAD", "git branch --format='%(refname)'", "git branch --sort=-committerdate",
    "git branch --sort committerdate", "git branch --color=never -a", "git branch --list -- 'x*'",
    "git tag", "git tag -l 'v*'", "git tag --list", "git tag -n", "git tag -n5", "git tag --contains HEAD",
    "git tag --points-at HEAD", "git tag --sort=-v:refname", "git tag --format='%(refname)' -l",
    "git remote", "git remote -v", "git remote --verbose", "git remote show origin", "git remote -v show origin",
    "git remote get-url origin", "git stash list", "git stash show -p", "git worktree list",
    "git worktree list --porcelain", "git config --get user.name", "git config --get-all remote.origin.fetch",
    "git config --get-regexp '^remote'", "git config --list", "git config -l --show-origin",
    "git config --global --get user.email", "git config --show-scope --list", "git config --name-only --list",
    "git config --local --get-regexp url", "git config get user.name", "git config list", "git config get --all k",
    "git notes list", "git notes show HEAD", "git notes", "git submodule status", "git submodule summary",
    "git submodule", "git submodule status --recursive",
])
def test_terminal_git_list_only_forms_stay_open(command):
    assert terminal(command) is None, command


@pytest.mark.parametrize("command", [
    "GIT_DIR=/x/.git git status", "GIT_PAGER=cat git log", "env GIT_DIR=x git status", "env -i GIT_DIR=x git status",
    "command git status", "/usr/bin/git status", "timeout 30 git fetch", "nice -n 5 git log", "sudo -u x git log",
    "xargs -0 git status", "cd repo && git status", "git status | head", "echo ok; git log", "x=$(git rev-parse HEAD)",
    "bash -c 'git status'", "sh -lc 'git fetch'", "eval 'git log'", "watch -n 5 git status", "GIT_DIR=x env git log",
    "git ls-files | xargs rg x", 'bash -c "cd r && git diff"', "find . -name x -exec git log {} \\;",
    "git log \\\n --oneline", "if git diff --quiet; then echo clean; fi", "! git diff --quiet",
])
def test_terminal_git_reads_inside_wrappers_stay_open(command):
    assert terminal(command) is None, command


@pytest.mark.parametrize("command", [
    "ls", "ls ~/.config/git", "cat .gitignore", "rg gitignore src/", "echo use git status", "gh pr view 3",
    "echo hub", "ls git-tools-notes", "hubble --version", "which git", "cat notes/git-lfs-notes.md",
    "cat docs/git-commit.md", "grep -rn 'git-tools' notes.md", "pnpm test", "python3 scripts/check.py",
])
def test_terminal_other_work_stays_open(command):
    assert terminal(command) is None, command


@pytest.mark.parametrize("command", [
    "git add .", "git add -p", "git commit -m x", "git commit --amend", "git push", "git push origin main",
    "git push --force-with-lease", "git reset --hard", "git reset HEAD~1", "git checkout main", "git checkout -b x",
    "git switch -c x", "git restore f", "git merge x", "git rebase -i HEAD~3", "git cherry-pick abc",
    "git revert abc", "git am p.patch", "git apply p.patch", "git clean -fd", "git init", "git rm f", "git mv a b",
    "git gc", "git prune", "git update-ref -d refs/heads/x", "git symbolic-ref HEAD refs/heads/x",
    "git bisect start", "git bisect log", "git filter-branch --all",
    "git stash", "git stash push", "git stash pop", "git stash drop", "git stash apply", "git stash clear",
    "git branch foo", "git branch foo main", "git branch -d foo", "git branch -D foo", "git branch -m a b",
    "git branch -u origin/x", "git branch --set-upstream-to=o/x", "git branch --delete x", "git branch -vv foo",
    "git branch --list -d foo", "git branch --edit-description", "git branch -- x", "git branch -c a b",
    "git tag v1", "git tag -a v1 -m x", "git tag -d v1", "git tag -v v1", "git tag -f v1", "git tag -l -d v1",
    "git remote add o url", "git remote remove o", "git remote set-url o u", "git remote rename a b",
    "git remote prune origin", "git remote update", "git remote -v add o u",
    "git worktree add ../x", "git worktree remove ../x", "git worktree prune", "git worktree",
    "git config user.name x", "git config --global user.name x", "git config --unset k", "git config --add k v",
    "git config --edit", "git config set k v", "git config user.name", "git config --get k --add",
    "git config --list --edit", "git config --global --replace-all k v", "git config --remove-section s",
    "git notes add -m x", "git notes edit", "git notes append -m x", "git submodule update --init",
    "git submodule add u", "git submodule foreach 'git push'", "git submodule sync",
    "git reflog expire --all", "git reflog delete HEAD@{1}", "git reflog expire",
    "git pull", "git pull --rebase", "git pull -r", "git pull -qr", "git pull origin main", "git pull --ff",
    "git pull --ff-only --no-ff", "git pull --ff-only --rebase", "git pull --ff-only --autostash",
    "git pull --ff-only --rebase=true", "git pull --ff-only --squash",
    "git -C repo commit -m x", "git --no-pager push", "git -C a -C b push", "git --git-dir=x push",
    "git --help push",
    "env git push", "sudo -u x git push", "cd r && git push", "echo ok; git add .", 'bash -c "git commit -m x"',
    "sh -c 'git reset --hard'", "eval 'git push'", "git commit \\\n -m x", "timeout 10 git push", "xargs git rm",
    "find . -name x -exec git rm {} \\;", "x=$(git add .)", "git status; git commit -m x", "git log | git apply",
    "GIT_DIR=x git push", "nohup git push &", "git-commit -m x", "git-push", "/usr/lib/git-core/git-add f",
    "hub commit", "hub push", "lazygit", "gitui", "/opt/homebrew/bin/lazygit -p repo", "env lazygit",
    "watch 'git branch -D x'", "if git push; then echo done; fi", "GIT_PAGER='git push' git log",
    "git branch -D x && git log", "bash -c 'true; \"git\" branch -D x'",
    "echo git commit",  # a mention in text reads like a call: blocked, conservatively
    "grep -rn 'git push' docs/", 'python3 -c "import os; os.system(\'git push\')"',
    "command " * 3 + "git stash",
])
def test_terminal_git_changes_are_blocked_with_the_tools_message(command):
    assert terminal(command) == block(MESSAGE), command


@pytest.mark.parametrize("command", [
    "git -c core.pager=x log", "git -c alias.x=!sh status", "git -ccore.pager=x log", "git --config-env=a=B log",
    "git --config-env a=B log", "git --exec-path=/x status", "git --exec-path status", "git --upload-pack=x status",
    "git --bare status", "git --namespace=x log", "git -C r -c x=y log", "git --foo log",
    "GIT_CONFIG_COUNT=1 git log", "GIT_CONFIG_GLOBAL=/x git log", "GIT_CONFIG_NOSYSTEM=1 git status",
    "GIT_SSH_COMMAND='ssh -i k' git fetch", "GIT_SSH=/x git fetch", "GIT_EXEC_PATH=/x git status",
    "GIT_ASKPASS=/x git fetch", "SSH_ASKPASS=/x git fetch", "GIT_EXTERNAL_DIFF=/x git diff", "GIT_EDITOR=vim git log",
    "GIT_SEQUENCE_EDITOR=x git log", "GIT_PROXY_COMMAND=/x git fetch", "export GIT_SSH_COMMAND=ssh; git fetch",
    "env GIT_SSH_COMMAND=ssh git fetch", "GIT_CONFIG_COUNT=1 env git log", "bash -c 'GIT_ASKPASS=x git fetch'",
    "git diff --ext-diff", "git diff --textconv", "git log --output=x", "git diff --output x", "git diff --outp=x",
    "git show --textconv HEAD:f", "git cat-file --textconv HEAD:f", "git log -p --ext-diff",
    "git ls-remote --upload-pack=x origin", "git ls-remote --exec=x origin", "git fetch --upload-pack=x origin",
    "git fetch --upload-pack x origin", "git fetch -u origin x:main", "git fetch -qu origin", "git fetch --update-head-ok",
    "git fetch --receive-pack x", "git pull --ff-only --upload-pack=x",
    "git clone -u x url", "git clone --upload-pack x url", "git clone -c core.fsmonitor=x url",
    "git clone -ccore.x=y url", "git clone -qc x=y url", "git clone --config x=y url", "git clone --template=/t url",
    "git clone --template /t url", "git grep -O less foo", "git grep --open-files-in-pager=less foo",
    "git grep -nOless foo", "git branch --output=x", "git tag --upload-pack=x",
])
def test_terminal_git_options_that_run_a_program_or_set_config_are_blocked(command):
    assert terminal(command) == block(UNSAFE), command


@pytest.mark.parametrize("command", [
    "git fsck", "git foo", "git ci", "git mytool --x", "git lfs pull", "git-lfs pull", "git-upload-pack .",
    "git format-patch -1", "git archive HEAD", "git sparse-checkout list", "git maintenance run", "git bundle create b",
    "git svn fetch", "git send-email x", "git credential fill", "git diff-tree HEAD", "git status-all",
    "bash -c 'git fsck'", "timeout 5 git foo",
    "command " * 12 + "\"git\" status",  # nesting past the limit fails closed
    "nice " + "-x nice " * 30 + "git status",  # so do readings past the budget, quickly
])
def test_any_other_git_command_is_blocked_by_default(command):
    assert terminal(command) == block(UNKNOWN), command


def test_a_nested_change_is_blocked_with_its_own_message():
    for command, expected in (("bash -c 'git -C r commit -m x'", MESSAGE),
                              ("eval \"git branch -D x\"", MESSAGE),
                              ("git fsck; git push", MESSAGE),
                              ("git fsck; git -c a=b log", UNSAFE),
                              ("git foo; git -c a=b log", UNSAFE),
                              ("git foo; git status", UNKNOWN),
                              ("git status; git foo", UNKNOWN),
                              ("find . -prune -exec \"git\" rm x \\;", MESSAGE),
                              # -c runs its script; the here-string is only its input
                              ("bash -c '\"git\" rm x' <<< ignored", MESSAGE),
                              ("bash <<< 'git push'", MESSAGE),
                              ("bash -o pipefail -c 'git push'", MESSAGE),
                              ("sudo nice -n 5 git push", MESSAGE)):
        assert terminal(command) == block(expected), command


def test_the_package_entry_points_are_not_git_commands_to_the_terminal_check():
    assert plugin.git_terminal.blocked("git-tools-cli run git_commit_create") is None
    assert plugin.git_terminal.blocked("/opt/homebrew/bin/git-tools") is None
    assert terminal("git-tools-cli run git_commit_create") == block(plugin.BYPASS_MESSAGE)


def test_the_git_messages_name_the_tools_and_where_commits_go():
    for message in (MESSAGE, UNSAFE, UNKNOWN):
        assert message.endswith("Nothing was run.")
        assert "git_*" in message and "OpenCode" in message and "git_worktree_remove" in message
        assert "engineering pipeline" in message
    assert "git_commit_read" in MESSAGE and "git_commit_read" in UNKNOWN
    assert len({MESSAGE, UNSAFE, UNKNOWN}) == 3


def test_the_read_list_holds_no_write_and_the_write_list_no_read():
    git_terminal = plugin.git_terminal
    assert not git_terminal.READ_COMMANDS & git_terminal.WRITES
    assert {"fsck", "bisect", "stash", "config", "branch", "tag", "fetch", "pull", "clone"}.isdisjoint(
        git_terminal.READ_COMMANDS)
    assert "bisect" in git_terminal.WRITES and "fsck" not in git_terminal.WRITES
    assert {"status", "log", "diff", "show", "ls-remote", "cat-file", "reflog", "var", "range-diff"} <= \
        git_terminal.READ_COMMANDS


@pytest.mark.parametrize("command", [
    "git-tools-cli run git_commit_create",
    "/opt/homebrew/bin/git-tools-cli run git_push_send",
    "bash -c 'git-tools-cli run git_commit_create'",
    "git-tools",
    "/opt/homebrew/bin/git-tools",
    "npx git-tools-cli list",
    "npx -y @craftsamo/git-tools",
    "pnpm dlx @craftsamo/git-tools",
    "bunx @craftsamo/git-tools",
    "node ~/.hermes/plugins/git-tools/dist/cli.js run git_commit_create",
    "node $HOME/.hermes/plugins/git-tools/dist/mcp.js",
    "bun ~/ghq/github.com/craft-agent/git-tools/dist/cli.js",
    "cat ~/.hermes/plugins/git-tools/__init__.py",
    "ls ~/.hermes/plugins/git-tools",
    "cd ~/.hermes/plugins/git-tools && ls",
    "cd ~/.hermes/plugins/git-tools",
    "ls ${HOME}/.hermes/plugins/git-tools/dist",
    "cat ~/.hermes/profiles/work/plugins/git-tools/package.json",
    "cat ~/.hermes/plugins/git-t*ls/dist/cli.js",
    "cat ~/.hermes/plugins/git-tool?/package.json",
    "git clone https://example.com/craftsamo/git-tools ~/.hermes/plugins/git-tools",
    "git -C ~/.hermes/plugins/git-tools log",
])
def test_terminal_blocks_ways_around_the_tools(command):
    assert blocked(terminal(command)), command


@pytest.mark.parametrize("command", [
    f"cd {CHECKOUT}",
    f"cd {CHECKOUT} && ls",
    f"cd {CHECKOUT} && pnpm test",
    f"cd {CHECKOUT} && bun test",
    f"cd {CHECKOUT} && node scripts/check.mjs",
    f"cd {CHECKOUT} && git status",
    f"ls {CHECKOUT}/src",
    f"cat {CHECKOUT}/package.json",
    f"git -C {CHECKOUT} log --oneline",
    f"grep -rn approval {CHECKOUT}/src",
    "ls ~/.hermes/plugins",
    "ls ~/.hermes/plugins/signal-tools",
    "ls ~/.hermes/plugins/github-tools",
    "git log -- hermes/plugins/guards/git-tools-guard",
    "ls ~/Worktrees/repo/feat-git-tools",
    "cat docs/git-tools.md",
    'grep -r "git tools" notes.md',
    "ls ~/.hermes/plugins/git-tools-guard",
])
def test_terminal_allows_the_source_checkout_and_plain_work(command):
    assert terminal(command) is None, command


def test_a_link_in_a_word_is_followed(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "git-tools"
    install.mkdir(parents=True)
    (isolated / "shortcut").symlink_to(install)
    assert blocked(terminal(f"cat {isolated}/shortcut/package.json"))
    assert terminal(f"cat {isolated}/home/package.json") is None


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    plugins = isolated / "home" / ".hermes" / "plugins"
    (plugins / "git-tools").mkdir(parents=True)
    assert terminal("cat git-tools/package.json") is None            # no record of the directory
    tracked(monkeypatch, plugins)
    assert blocked(terminal("cat git-tools/package.json"))
    assert blocked(terminal("cat ./git-tools/../git-tools/package.json"))
    assert terminal("ls") is None
    tracked(monkeypatch, isolated / "home" / "checkout")
    assert terminal("cat git-tools/package.json") is None


def test_a_terminal_inside_the_installed_plugin_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "git-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    assert terminal("ls") == block(plugin.CWD_MESSAGE)
    assert terminal("git status") == block(plugin.CWD_MESSAGE)
    tracked(monkeypatch, install / "dist")
    assert blocked(terminal("ls"))
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert blocked(terminal("ls"))


def test_a_terminal_in_a_profiles_own_copy_is_blocked(monkeypatch, isolated):
    copy = isolated / "somewhere" / "plugins" / "git-tools"
    copy.mkdir(parents=True)
    tracked(monkeypatch, copy)
    assert blocked(terminal("ls"))
    monkeypatch.setenv("HERMES_HOME", str(isolated / "profile-home"))
    assert blocked(terminal("ls", workdir=str(isolated / "profile-home" / "plugins" / "git-tools")))


def test_the_source_checkout_is_a_fine_working_directory(monkeypatch, isolated):
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent" / "git-tools"
    (checkout / "dist").mkdir(parents=True)
    tracked(monkeypatch, checkout)
    assert terminal("ls") is None
    assert terminal("pnpm test") is None
    assert terminal("git status") is None
    assert terminal("git log --oneline", workdir=str(checkout / "dist")) is None
    assert terminal("cat package.json") is None
    assert terminal("git commit -m x") == block(MESSAGE)          # a checkout does not open writes


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "git-tools"
    tracked(monkeypatch, install)
    assert terminal("node build.js", workdir=str(isolated)) is None
    assert terminal("ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(terminal("ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".hermes" / "plugins")
    assert blocked(terminal("ls", workdir="git-tools"))      # relative: the recorded one


def test_the_hook_hands_its_ids_to_the_terminal_record(monkeypatch):
    asked = []
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": asked.append((task_id, session_id)))
    assert plugin.gate(tool_name="terminal", args={"command": "ls"}, task_id="t1", session_id="s1") is None
    assert plugin.gate(tool_name="read_file", args={"path": "a.txt"}, task_id="t1", session_id="s1") is None
    assert asked == [("t1", "s1"), ("t1", "s1")]


def test_a_file_tools_relative_path_resolves_against_the_recorded_directory(monkeypatch, isolated):
    plugins = isolated / "home" / ".hermes" / "plugins"
    (plugins / "git-tools" / "dist").mkdir(parents=True)
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent"
    (checkout / "git-tools").mkdir(parents=True)
    assert gate("write_file", path="git-tools/dist/cli.js", content="x") is None     # no record of the directory
    tracked(monkeypatch, plugins)
    assert gate("write_file", path="git-tools/dist/cli.js", content="x") == block(plugin.BYPASS_MESSAGE)
    assert blocked(gate("read_file", path="./git-tools/../git-tools/package.json"))
    assert blocked(gate("search_files", pattern="x", path="git-tools"))
    assert gate("read_file", path="notes.md") is None                   # the recorded directory alone is no reason
    tracked(monkeypatch, checkout)
    assert gate("read_file", path="git-tools/README.md") is None
    assert gate("write_file", path="git-tools/notes.md", content="x") is None


def v4a(*headers):
    return "\n".join(["*** Begin Patch", *headers, "@@ hint @@", "-old", "+new", "*** End Patch"])


def test_a_patchs_file_headers_resolve_against_the_recorded_directory(monkeypatch, isolated):
    plugins = isolated / "home" / ".hermes" / "plugins"
    (plugins / "git-tools" / "dist").mkdir(parents=True)
    tracked(monkeypatch, plugins)
    for header in ("*** Update File: git-tools/dist/cli.js", "*** Add File: git-tools/new.js",
                   "*** Delete File: ./git-tools/package.json", "***Update File:   git-tools/x.js  ",
                   "*** Move File: notes.md -> git-tools/notes.md",
                   "*** Move File: git-tools/a.js -> notes.md"):
        assert blocked(gate("patch", mode="patch", patch=v4a("*** Update File: notes.md", header))), header
    assert blocked(gate("patch", mode="patch", patch=v4a("*** Update File: git-tools/dist/cli.js").replace("\n", "\r\n")))
    assert gate("patch", mode="patch", patch=v4a("*** Update File: notes.md")) is None
    assert gate("patch", mode="patch", patch=v4a("*** Move File: a.md -> b.md")) is None
    tracked(monkeypatch, isolated / "home" / "checkout")
    assert gate("patch", mode="patch", patch=v4a("*** Update File: git-tools/dist/cli.js")) is None
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": None)      # no record
    assert gate("patch", mode="patch", patch=v4a("*** Update File: git-tools/dist/cli.js")) is None
    assert blocked(gate("patch", mode="patch", patch=v4a("*** Update File: ~/.hermes/plugins/git-tools/x.js")))
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
    ("read_file", {"path": "~/.hermes/plugins/git-tools/__init__.py"}),
    ("read_file", {"path": "$HOME/.hermes/plugins/git-tools/dist/cli.js"}),
    ("write_file", {"path": "~/.hermes/plugins/git-tools/dist/cli.js", "content": "x"}),
    ("search_files", {"pattern": "x", "path": "~/.hermes/plugins/git-tools"}),
    ("patch", {"path": "/tmp/x", "patch": "*** Update File: ~/.hermes/plugins/git-tools/plugin.yaml"}),
    ("read_file", {"path": "~/.hermes/profiles/work/plugins/git-tools/plugin.yaml"}),
])
def test_file_tools_block_the_installed_plugin_by_text(tool, args):
    assert gate(tool, **args) == block(plugin.BYPASS_MESSAGE)


def test_file_tools_block_the_installed_plugin_by_real_path(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "git-tools"
    install.mkdir(parents=True)
    (install / "package.json").write_text("{}")
    link = isolated / "shortcut"
    link.symlink_to(install)
    for path in (install / "package.json", install, link / "package.json", link,
                 isolated / "other" / ".." / "home" / ".hermes" / "plugins" / "git-tools"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "home" / ".hermes" / "plugins")) is None
    monkeypatch.setenv("HERMES_HOME", str(isolated / "profile"))
    assert blocked(gate("read_file", path=str(isolated / "profile" / "plugins" / "git-tools" / "x")))


def test_file_tools_read_the_source_checkout(isolated):
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent" / "git-tools"
    (checkout / "dist").mkdir(parents=True)
    (checkout / "dist" / "cli.js").write_text("x")
    assert gate("read_file", path=f"{CHECKOUT}/src/core/commits/read.ts") is None
    assert gate("read_file", path=str(checkout / "dist" / "cli.js")) is None
    assert gate("write_file", path=str(checkout / "notes.md"), content="x") is None
    assert gate("search_files", pattern="approval", path=CHECKOUT) is None
    assert gate("read_file", path=str(isolated / "home" / ".hermes" / "plugins" / "git-tools-guard")) is None


def test_file_tools_may_write_about_the_package(isolated):
    assert gate("write_file", path="notes.md", content="npx -y @craftsamo/git-tools, git-tools/dist/cli.js") is None
    assert gate("write_file", path="notes.md", content="git commit -m x") is None      # text for a file is not a command


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    real_bypass = plugin.bypass
    monkeypatch.setattr(plugin, "bypass", boom)
    assert terminal("ls") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("read_file", path="a.txt") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin, "bypass", real_bypass)
    monkeypatch.setattr(plugin.git_terminal, "blocked", boom)
    assert terminal("git status") == block(plugin.UNCHECKED_MESSAGE)
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("git_commit_create", message="x") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("git_foo_bar") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("git_repo_read", method="status") is None
    assert gate("git_repo", action="status") is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("git_push_send", branch="main") == block(plugin.UNCHECKED_MESSAGE)
    assert gate("git_push_read", method="preview") is None
    assert gate("web_search", query="x") is None


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    private = "private words"
    assert line("git_commit_create", message=private, path=private, branch="secret/branch") == "commit"
    assert line("git_commit_amend", message=private, name=private) == "amend"
    assert line("git_push_send", branch="secret/branch", remote="origin", name=private) == "push"
    assert line("git_worktree_add", path="/Users/x/secret", branch="secret/branch") == "add worktree"
    assert line("git_worktree_remove", path="/Users/x/secret") == "remove worktree"
    assert line("git_repo_read", method="status", path="/Users/x/secret", query=private) == "status"
    assert line("git_repo_read", method="origin", name=private) == "origin"
    assert line("git_commit_read", method="secrets", path=private) == "secrets"
    assert line("git_rebase_read", method="stack", query=private) == "stack"
    assert line("git_push_read", method="preview", query=private) == "preview"
    assert line("git_repo_read", method=private, query=private) is None
    assert line("git_worktree_read", method="status", query=private) is None
    assert line("git_repo_read", query=private) is None


def test_every_tool_has_a_progress_line_that_carries_no_free_text(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())
    private = "private words"
    free = {key: private for key in ("query", "text", "path", "name", "body", "title", "command", "url", "message",
                                     "branch", "remote", "cwd")}
    for tool in PROVIDED:
        assert tool in display._PREVIEW_BUILDERS, tool
        if tool in plugin.METHODS:
            assert display.build_tool_preview(tool, {**free, "method": private}, max_len=0) is None
            for method in plugin.METHODS[tool]:
                assert display.build_tool_preview(tool, {**free, "method": method}, max_len=0) == method
        else:
            line = display.build_tool_preview(tool, free, max_len=0)
            assert line == plugin.LABELS[tool] and private not in line


def test_the_progress_labels_are_the_agreed_ones():
    assert plugin.LABELS == {
        "git_commit_stage": "stage", "git_commit_create": "commit", "git_commit_amend": "amend",
        "git_commit_verify": "verify commits", "git_rebase_start": "rebase", "git_rebase_resume": "resume rebase",
        "git_rebase_split": "split stack", "git_worktree_add": "add worktree",
        "git_worktree_remove": "remove worktree", "git_push_send": "push",
    }
    assert plugin.METHODS == {
        "git_repo_read": ("status", "conflicts", "conventions", "origin"),
        "git_commit_read": ("lint", "secrets", "hunks", "amend"),
        "git_rebase_read": ("stack",), "git_worktree_read": ("list",), "git_push_read": ("preview",),
    }


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
