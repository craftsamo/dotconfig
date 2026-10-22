import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin = _load("github_access_plugin_test", ROOT / "__init__.py")


class Ctx:
    def __init__(self, profile):
        self.profile_name = profile
        self.tools = {}
        self.hooks = []
        self.skills = {}

    def register_skill(self, name, path, description="", frontmatter=None):
        assert path.is_file() and frontmatter["name"] == name and description
        self.skills[name] = path

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


def test_the_progress_line_shows_the_action_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx("assistant"))
    line = lambda tool, **args: display.build_tool_preview(tool, args, max_len=0)  # noqa: E731
    assert line("github_issue", action="list", repo="acme/secret", query="someone's name") == "list"
    assert line("github_issue", action="view", issue="acme/secret#3") == "view"
    assert line("github_board", action="items", project="Private plans", search="layoffs") == "items"
    assert line("github_mandate", action="create", purpose="the merger", repos=["acme/secret"]) == "create"
    assert line("github_mandate", action="revoke", mandate="m1a2b3c4d") == "revoke"
    assert line("github_repo", action="milestones", repo="acme/secret") == "milestones"
    assert line("github_pr", action="view", pr="acme/secret#4", query="someone's name") == "view"
    for tool in ("github_issue", "github_board", "github_repo", "github_pr", "github_mandate"):
        assert line(tool, action="anything else", query="someone's name") is None


def test_a_change_list_previews_its_ops_counted_and_nothing_else(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx("assistant"))
    line = lambda **args: display.build_tool_preview("github_change", args, max_len=0)  # noqa: E731
    listing = [{"op": "item_set", "item": "PVTI_1", "fields": {"Status": "Done"}},
               {"op": "draft_note", "item": "PVTI_1", "text": "met the lawyer"},
               {"op": "item_set", "item": "PVTI_2", "fields": {"Status": "Waiting"}},
               {"op": "steal everything", "title": "x"}, "not a change"]
    assert line(changes=listing, repo="acme/secret") == "item_set×2, draft_note"
    assert line(changes=[{"title": "no op"}], repo="acme/secret") is None
    assert line(changes="item_set") is None


def test_only_the_assistant_gets_the_tools():
    ctx = Ctx("creator")
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == []
    ctx = Ctx("assistant")
    plugin.register(ctx)
    assert set(ctx.tools) == set(plugin.HANDLERS) == {"github_issue", "github_board", "github_repo", "github_pr",
                                                      "github_change", "github_mandate"}
    assert ctx.hooks == [("pre_tool_call", plugin.gate)]
    assert {t["toolset"] for t in ctx.tools.values()} == {"github_access"}
    for name, tool in ctx.tools.items():
        params = tool["schema"]["parameters"]
        assert params["additionalProperties"] is False and params["required"] == plugin.REQUIRED[name]


def test_action_enums_match_the_engine():
    ctx = Ctx("assistant")
    plugin.register(ctx)
    props = {name: tool["schema"]["parameters"]["properties"] for name, tool in ctx.tools.items()}
    assert props["github_issue"]["action"]["enum"] == list(plugin.access.ISSUE_ACTIONS)
    assert props["github_board"]["action"]["enum"] == list(plugin.access.BOARD_ACTIONS)
    assert props["github_repo"]["action"]["enum"] == list(plugin.repo_reads.REPO_ACTIONS)
    assert props["github_pr"]["action"]["enum"] == list(plugin.pr_reads.PR_ACTIONS)
    ops = props["github_change"]["changes"]["items"]["properties"]["op"]["enum"]
    assert ops == list(plugin.changes.OPS) and all(op in plugin.CHANGE_DESCRIPTION for op in ops)


def test_inbound_a2a_is_refused(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    result = json.loads(plugin.github_board({"action": "items"}))
    assert result["ok"] is False and "A2A" in result["error"]


def test_handlers_return_json_errors_and_refuse_oversized_results(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    result = json.loads(plugin.github_issue({"action": "view"}))
    assert result == {"ok": False, "error": "issue is required"}
    monkeypatch.setitem(plugin.ENGINES, "github_board", lambda args: {"x": "y" * plugin.LIMIT})
    result = json.loads(plugin.github_board({"action": "items"}))
    assert result["ok"] is False and "narrow" in result["error"]


CHANGE = {"changes": [{"op": "draft_add", "title": "Capture"}]}
PLAN = {"steps": [], "targets": [{"kind": "board", "name": "me/1 Roadmap", "tier": "own"}], "tier": "own",
        "classes": ["create"]}


def _fake_engine(monkeypatch, applied, plans=None):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)
    monkeypatch.setattr(plugin.changes, "plan", lambda args: plans.pop(0) if plans else PLAN)
    monkeypatch.setattr(plugin.changes, "binding", lambda planned: [[t["kind"], t["name"], t["tier"]] for t in planned["targets"]])
    monkeypatch.setattr(plugin.mandate, "covering", lambda home, planned: (None, []))
    monkeypatch.setattr(plugin, "_home", lambda: Path("/nonexistent-home"))
    monkeypatch.setattr(plugin.changes, "card",
                        lambda planned, note=None: "GitHub · 1 change" + (f"\nNot covered by a mandate: {note}"
                                                                           if note else ""))
    monkeypatch.setattr(plugin.changes, "apply", lambda planned: applied.append(planned) or {"ok": True, "done": []})
    plugin._DECISIONS.clear()


def test_a_change_list_gets_one_card_under_a_fresh_key(monkeypatch):
    _fake_engine(monkeypatch, [])
    first = plugin.gate(tool_name="github_change", args=CHANGE)
    second = plugin.gate(tool_name="github_change", args=CHANGE)
    assert first["action"] == "approve" and first["message"] == "GitHub · 1 change"
    assert first["rule_key"].startswith("github-access:change:") and first["rule_key"] != second["rule_key"]


def test_the_handler_runs_only_what_the_hook_decided_and_only_once(monkeypatch):
    applied = []
    _fake_engine(monkeypatch, applied)
    refused = json.loads(plugin.github_change(CHANGE))
    assert refused["ok"] is False and "not decided by the approval hook" in refused["error"] and applied == []
    plugin.gate(tool_name="github_change", args=CHANGE)
    assert json.loads(plugin.github_change(CHANGE)) == {"ok": True, "done": []} and len(applied) == 1
    assert json.loads(plugin.github_change(CHANGE))["ok"] is False and len(applied) == 1
    other = {"changes": [{"op": "draft_add", "title": "Something else"}]}
    plugin.gate(tool_name="github_change", args=CHANGE)
    assert json.loads(plugin.github_change(other))["ok"] is False


def test_a_write_whose_targets_changed_since_the_card_is_refused(monkeypatch):
    applied = []
    public = {**PLAN, "targets": [{"kind": "board", "name": "me/1 Roadmap", "tier": "shared"}]}
    _fake_engine(monkeypatch, applied, plans=[PLAN, public])
    plugin.gate(tool_name="github_change", args=CHANGE)
    result = json.loads(plugin.github_change(CHANGE))
    assert result["ok"] is False and "changed since it was decided" in result["error"] and applied == []


def test_a_list_inside_a_mandate_runs_without_a_card_even_unattended(monkeypatch):
    applied = []
    _fake_engine(monkeypatch, applied)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    monkeypatch.setattr(plugin.mandate, "covering", lambda home, planned: ("m1a2b3c4d", []))
    monkeypatch.setattr(plugin.mandate, "still_fits", lambda home, mid, planned: None)
    assert plugin.gate(tool_name="github_change", args=CHANGE) is None
    assert json.loads(plugin.github_change(CHANGE)) == {"ok": True, "done": []} and len(applied) == 1


def test_a_list_that_left_its_mandate_before_the_write_is_refused(monkeypatch):
    applied = []
    _fake_engine(monkeypatch, applied)
    monkeypatch.setattr(plugin.mandate, "covering", lambda home, planned: ("m1a2b3c4d", []))
    monkeypatch.setattr(plugin.mandate, "still_fits", lambda home, mid, planned: "mandate m1a2b3c4d is no longer in force")
    assert plugin.gate(tool_name="github_change", args=CHANGE) is None
    result = json.loads(plugin.github_change(CHANGE))
    assert result["ok"] is False and "no longer fits the mandate" in result["error"] and applied == []


def test_a_change_list_whose_card_cannot_be_shown_is_blocked_undecided(monkeypatch):
    _fake_engine(monkeypatch, [])

    def too_long(planned, note=None):
        raise plugin.access.AccessError("the approval card cannot show this change list; split it into smaller ones")
    monkeypatch.setattr(plugin.changes, "card", too_long)
    directive = plugin.gate(tool_name="github_change", args=CHANGE)
    assert directive["action"] == "block" and "split it" in directive["message"]
    assert plugin._DECISIONS == {}


def test_a_mandate_whose_card_cannot_be_shown_is_blocked_undecided(monkeypatch):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: False)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)
    monkeypatch.setattr(plugin.mandate, "terms", lambda args: dict(TERMS))

    def too_long(terms, say):
        raise plugin.access.AccessError("the mandate's card cannot show all its bounds")
    monkeypatch.setattr(plugin.mandate, "card", too_long)
    plugin._DECISIONS.clear()
    directive = plugin.gate(tool_name="github_mandate", args=MAKE)
    assert directive["action"] == "block" and "all its bounds" in directive["message"]
    assert plugin._DECISIONS == {}


def test_outside_every_mandate_the_card_says_why(monkeypatch):
    _fake_engine(monkeypatch, [])
    monkeypatch.setattr(plugin.mandate, "covering",
                        lambda home, planned: (None, ["m1: team/web is shared: a mandate never covers create changes there"]))
    directive = plugin.gate(tool_name="github_change", args=CHANGE)
    assert directive["action"] == "approve"
    assert "\nNot covered by a mandate: m1: team/web is shared" in directive["message"]   # handed to the card


TERMS = {"boards": [], "repos": [{"id": "R_app", "name": "me/app", "tier": "own"}], "parent": None,
         "classes": ["routine"], "days": 7, "expires": 4102444800, "purpose": "Track the release"}
MAKE = {"action": "create", "repos": ["me/app"], "classes": ["routine"], "days": 7, "purpose": "Track the release"}


def test_a_mandate_is_made_only_on_its_own_card(monkeypatch):
    made = []
    _fake_engine(monkeypatch, [])
    monkeypatch.setattr(plugin.mandate, "terms", lambda args: TERMS)
    monkeypatch.setattr(plugin.mandate, "create", lambda home, terms: made.append(terms) or {"id": "m00000001"})
    refused = json.loads(plugin.github_mandate(MAKE))
    assert refused["ok"] is False and "only on its own card" in refused["error"] and made == []
    first = plugin.gate(tool_name="github_mandate", args=MAKE)
    second = plugin.gate(tool_name="github_mandate", args=MAKE)
    assert first["action"] == "approve" and first["message"].startswith("GitHub · Mandate")
    assert first["rule_key"].startswith("github-access:mandate:") and first["rule_key"] != second["rule_key"]
    assert json.loads(plugin.github_mandate(MAKE)) == {"ok": True, "mandate": {"id": "m00000001"}} and made == [TERMS]


def test_a_mandate_is_never_made_unattended_or_from_a_peer(monkeypatch):
    _fake_engine(monkeypatch, [])
    monkeypatch.setattr(plugin.mandate, "terms", lambda args: TERMS)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    assert plugin.gate(tool_name="github_mandate", args=MAKE)["action"] == "block"
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert plugin.gate(tool_name="github_mandate", args={"action": "list"})["action"] == "block"


def test_listing_and_revoking_need_no_card(monkeypatch):
    _fake_engine(monkeypatch, [])
    monkeypatch.setattr(plugin.mandate, "active", lambda home: [])
    monkeypatch.setattr(plugin.mandate, "revoke", lambda home, mid: {"revoked": mid})
    assert plugin.gate(tool_name="github_mandate", args={"action": "list"}) is None
    assert plugin.gate(tool_name="github_mandate", args={"action": "revoke", "mandate": "m1"}) is None
    assert json.loads(plugin.github_mandate({"action": "list"})) == {"ok": True, "mandates": []}
    assert json.loads(plugin.github_mandate({"action": "revoke", "mandate": "m1"})) == {"ok": True, "revoked": "m1"}


def test_a_call_the_engine_refuses_is_blocked_without_a_card(monkeypatch):
    _fake_engine(monkeypatch, [])

    def refuse(args):
        raise plugin.access.AccessError("no write permission on me/ro")
    monkeypatch.setattr(plugin.changes, "plan", refuse)
    directive = plugin.gate(tool_name="github_change", args=CHANGE)
    assert directive == {"action": "block", "message": "github_change: not done. no write permission on me/ro"}
    assert plugin._DECISIONS == {}


def test_a_write_is_refused_where_nobody_can_answer_its_card(monkeypatch):
    applied = []
    _fake_engine(monkeypatch, applied)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "this is a cron job")
    directive = plugin.gate(tool_name="github_change", args=CHANGE)
    assert directive["action"] == "block" and "this is a cron job" in directive["message"]
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: None)
    plugin.gate(tool_name="github_change", args=CHANGE)
    monkeypatch.setattr(plugin.human_gate, "no_human", lambda: "yolo mode is on")
    result = json.loads(plugin.github_change(CHANGE))
    assert result["ok"] is False and "yolo mode is on" in result["error"] and applied == []


def test_the_genuine_check_refuses_a_write_in_this_headless_test_run(monkeypatch):
    genuine = _load("github_access_human_gate_genuine", ROOT.parent / "_shared" / "human_gate.py")
    _fake_engine(monkeypatch, [])
    monkeypatch.setattr(plugin.human_gate, "no_human", genuine.no_human)
    assert plugin.gate(tool_name="github_change", args=CHANGE)["action"] == "block"


def test_inbound_a2a_cannot_change_anything(monkeypatch):
    _fake_engine(monkeypatch, [])
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert plugin.gate(tool_name="github_change", args=CHANGE)["action"] == "block"
    assert json.loads(plugin.github_change(CHANGE))["ok"] is False


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
])
def test_terminal_gh_writes_are_blocked(command):
    assert plugin.gate(tool_name="terminal", args={"command": command}) == {"action": "block",
                                                                           "message": plugin.guard.MESSAGE}


@pytest.mark.parametrize("command", [
    "gh secret set API_KEY --body x", "gh secret delete API_KEY -R a/b", "gh variable set NAME --body v",
    "gh variable delete NAME", "gh gist create notes.md --public", "gh gist edit 1a2b", "gh gist delete 1a2b",
    "gh repo delete a/b --yes", "gh repo rename new-name", "gh repo fork a/b --clone", "gh repo deploy-key add k.pub",
    "gh repo autolink create JIRA- https://x/<num>", "gh repo sync me/fork", "gh ssh-key add k.pub",
    "gh gpg-key delete ABC", "gh release delete v1 --yes", "gh release delete-asset v1 a.zip", "gh run delete 42",
    "gh cache delete --all", "gh -R a/b repo delete --yes", 'bash -c "gh secret set X --body y"',
    "echo gh gist create x",  # a mention reads like a call here too
    "gh pr review 3 --approve", "gh pr revert 3", "gh pr update-branch 3", "gh pr lock 3",
    "gh release upload v1 a.zip", "gh run cancel 42", "gh workflow disable deploy.yml", "gh workflow enable 9",
    "gh secret -R a/b set X --body y", "gh release --repo a/b delete v1", "gh run --repo=a/b delete 1",
    "gh cache -R a/b delete --all", 'sh -c "gh variable -R a/b set X"', "gh secret --org team set X",
    "gh --foo bar secret set X", "gh secret -o team delete X",
])
def test_writes_the_assistant_never_makes_are_blocked_and_say_so(command):
    assert plugin.gate(tool_name="terminal", args={"command": command}) == {"action": "block",
                                                                           "message": plugin.guard.NEVER_MESSAGE}


@pytest.mark.parametrize("command", [
    "gh issue view 3", "gh issue list --repo a/b", "gh pr view 3 --json state", "gh repo view a/b --json visibility",
    "gh project list --owner me", "gh project item-list 1 --owner me", "ls ~/Worktrees/x/feat-hermes-github-access",
    "git log", "gh auth status", "bash -c 'gh issue view 3'", "gh secret list -R a/b", "gh variable list",
    "gh gist view 1a2b", "gh gist list", "gh repo view a/b", "gh repo clone a/b", "gh release view v1",
    "gh run view 42 --log-failed", "gh cache list", "gh ssh-key list", "gh pr checks 3 --repo me/app",
    "gh pr diff 3", "gh pr list --author @me", "gh pr status", "gh release list", "gh release download v1",
    "gh run list --limit 5", "gh run watch 42", "gh workflow list", "gh workflow view deploy.yml",
    "gh issue -R a/b view 3", "gh secret -R a/b list", "gh release --repo a/b view v1",
    "gh repo list me", "gh repo set-default a/b", "gh repo license list", "gh repo gitignore view Python",
    "gh release view delete", "gh issue list --label create", "gh issue list --search 'create login'",
    "gh pr list --json title --jq '.[] | .title'",
    "gh", "gh --version", "gh help pr", "gh pr --help", "gh status", "gh search issues login --repo a/b",
    "gh ruleset view 1 --repo a/b", "gh config get editor", "gh -R a/b issue view 3", "gh variable get X",
    "gh attestation verify f.tgz --owner o", "timeout 30 gh run watch 42", "gh pr checkout 12",
    "sh -lc 'gh pr view 3'", "eval 'gh issue list'", "echo use gh auth login",  # a mention of a non-write runs nothing
    "find ~/.config/gh -type f", "rg gh src/", "ls ~/.config/gh", "git log --grep gh", "watch -n 5 gh run list",
    "gh auth status --hostname github.com", "GH_PAGER=cat gh issue view 1", "xargs rg gh src/",
    "sudo ls /opt/gh /opt/bin", "xargs -0 grep -l gh", "nice -n 5 gh pr view 3", "timeout -s KILL 10 gh run view 4",
])
def test_terminal_reads_and_other_work_stay_open(command):
    assert plugin.gate(tool_name="terminal", args={"command": command}) is None


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
    assert plugin.gate(tool_name="terminal", args={"command": command}) == {"action": "block",
                                                                           "message": plugin.guard.UNKNOWN_MESSAGE}


def test_a_nested_write_is_blocked_with_its_own_message():
    for command, message in (("bash -c 'gh label -R a/b create x'", plugin.guard.MESSAGE),
                             ("eval \"gh pr -R a/b review 3 --approve\"", plugin.guard.NEVER_MESSAGE),
                             ("gh auth login; gh repo -R a/b fork", plugin.guard.NEVER_MESSAGE),
                             ("find . -prune -exec \"gh\" issue create -R me/app -t x -b y \\;", plugin.guard.MESSAGE),
                             ("gh auth --hostname=github.com status --show-token", plugin.guard.MESSAGE),
                             ("gh auth status -t", plugin.guard.MESSAGE), ("gh auth status -ht", plugin.guard.MESSAGE),
                             # -c runs its script; the here-string is only its input
                             ("bash -c '\"gh\" issue create -R me/app -t x -b y' <<< ignored", plugin.guard.MESSAGE)):
        assert plugin.gate(tool_name="terminal", args={"command": command}) == {"action": "block", "message": message}


def test_the_state_directory_is_closed_to_file_and_terminal_calls(tmp_path):
    blocked = {"action": "block", "message": plugin.guard.MESSAGE}
    assert plugin.gate(tool_name="read_file", args={"path": "~/.hermes/profiles/assistant/github-access/mandates/x.json"}) == blocked
    assert plugin.gate(tool_name="terminal", args={"command": "cat ~/.hermes/profiles/assistant/github-access/head.json"}) == blocked
    assert plugin.gate(tool_name="write_file", args={"path": "~/.hermes/profiles/assistant/GITHUB-ACCESS/head.json",
                                                     "content": "{}"}) == blocked
    state = tmp_path / "home" / "github-access"
    state.mkdir(parents=True)
    alias = tmp_path / "innocent"
    alias.symlink_to(state)
    assert plugin.gate(tool_name="patch", args={"path": str(alias / "head.json")}) == blocked
    assert plugin.gate(tool_name="read_file", args={"path": str(tmp_path / "home" / "x" / ".." / "github-access")}) == blocked
    assert plugin.gate(tool_name="read_file", args={"path": "~/.hermes/plugins/github-access/__init__.py"}) is None
    assert plugin.gate(tool_name="read_file", args={"path": "hermes/docs/github-access.md"}) is None


def test_the_skills_reach_only_the_assistant():
    for profile, names in (("assistant", set(plugin.SKILLS)), ("marketer", set()), ("creator", set())):
        ctx = Ctx(profile)
        plugin.register(ctx)
        assert set(ctx.skills) == names
