import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cloudflare_tools_guard_test", ROOT / "__init__.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)

REAL_TRACKED_CWD = plugin._tracked_cwd
READ_TOOLS = {
    "cloudflare_access_read", "cloudflare_account_read", "cloudflare_analytics_read", "cloudflare_dns_read",
    "cloudflare_email_read", "cloudflare_grant_read", "cloudflare_hyperdrive_read", "cloudflare_pages_read",
    "cloudflare_queues_read", "cloudflare_registrar_read", "cloudflare_rules_read", "cloudflare_storage_read",
    "cloudflare_tunnel_read", "cloudflare_turnstile_read", "cloudflare_vectorize_read", "cloudflare_workers_read",
    "cloudflare_zone_read",
}
KNOWN_WRITES = (
    "cloudflare_dns_record_add", "cloudflare_dns_record_delete", "cloudflare_dns_record_edit",
    "cloudflare_email_address_add", "cloudflare_email_address_delete", "cloudflare_email_catchall_edit",
    "cloudflare_email_rule_add", "cloudflare_email_rule_delete", "cloudflare_email_rule_edit",
    "cloudflare_grant_create", "cloudflare_grant_revoke", "cloudflare_pages_domain_add",
    "cloudflare_pages_domain_remove", "cloudflare_pages_rollback", "cloudflare_rules_add",
    "cloudflare_rules_delete", "cloudflare_rules_edit", "cloudflare_storage_create", "cloudflare_storage_delete",
    "cloudflare_tunnel_route_add", "cloudflare_tunnel_route_edit", "cloudflare_tunnel_route_remove",
    "cloudflare_workers_rollback", "cloudflare_zone_cache_purge", "cloudflare_zone_cache_purge_all",
    "cloudflare_zone_dnssec_disable", "cloudflare_zone_dnssec_enable", "cloudflare_zone_setting_edit",
    "cloudflare_zone_setting_weaken",
)
WRITES = (*KNOWN_WRITES, "cloudflare_future_write", "cloudflare_future_read", "cloudflare_dns_read_all",
          "cloudflare_zone_unread")


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
    for name in ("CLOUDFLARE_TOOLS_GRANTS_DIR", "XDG_STATE_HOME"):
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


def test_the_reads_are_exactly_the_seventeen_named_ones():
    assert plugin.READS == READ_TOOLS
    assert len(READ_TOOLS) == 17


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
    assert gate(tool, zone="example.com") == block_with(plugin.human_gate.refusal(tool, "yolo mode is on"))


@pytest.mark.parametrize("tool", WRITES)
def test_writes_are_blocked_for_an_inbound_peer(monkeypatch, tool):
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate(tool, zone="example.com") == block_with(f"{tool} is not available to inbound A2A requests")


@pytest.mark.parametrize("tool", WRITES)
def test_writes_pass_with_a_human(tool):
    assert gate(tool, zone="example.com") is None


def test_a_tool_added_later_fails_closed(monkeypatch):
    no_human(monkeypatch)
    assert blocked(gate("cloudflare_future_write", zone="example.com"))
    assert blocked(gate("cloudflare_zone_cache_purge_all", zone="example.com"))


def test_the_writes_listed_are_exactly_the_labelled_ones():
    assert set(plugin.LABELS) == set(KNOWN_WRITES)
    assert not set(plugin.LABELS) & plugin.READS


def test_other_tools_are_untouched(monkeypatch):
    no_human(monkeypatch)
    monkeypatch.setattr(plugin, "_inbound_peer", lambda: True)
    assert gate("web_search", query="cloudflare-tools-cli") is None
    assert gate("browser_click", ref="cloudflare_dns_record_add") is None
    assert gate("cloudflare", action="zones") is None      # the retired plugin's own tool
    assert gate("signal_message_send", text="hi") is None
    assert plugin.gate() is None


@pytest.mark.parametrize("command", [
    "wrangler deploy", "npx wrangler d1 execute DB --remote --command x", "pnpm exec wrangler secret put TOKEN",
    "npx wrangler@latest deploy", "pnpm dlx wrangler@4 whoami", "bunx --bun wrangler@4.1.0 tail",
    "npx -y cloudflared@latest tunnel list",
    "cd app && wrangler pages deployment list", "bash -c 'wrangler whoami'", "./node_modules/.bin/wrangler tail",
    "cloudflared tunnel list", "sudo cloudflared service install", "flarectl zone list",
    "env CI=1 wrangler deploy",
    "curl -H 'Authorization: Bearer x' https://api.cloudflare.com/client/v4/zones",
    "echo $CLOUDFLARE_API_TOKEN", "export CF_API_KEY=1", "curl -H 'X-Auth-Key: x' https://example.com",
    "cat ~/.cloudflared/cert.pem", "cat ~/Library/Preferences/.wrangler/config/default.toml",
    "python3 -c 'import cloudflare'", "node -e \"require('cloudflare')\"",
    "secret get CLOUDFLARE_WORK -p hermes --scope cloudflare-access", "secret get X --project=hermes",
    "secret get X -p hermes --scope cloudflare-tools", "secret export -p hermes",
    "security find-generic-password -s secret.hermes", "security dump-keychain", "echo cfut_abcdefghijklmnop",
    "echo cfat_abcdefgh", "echo cfk_abcdefgh",
])
def test_the_guard_blocks_ways_around_the_tools(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE)


@pytest.mark.parametrize("command", [
    "echo $CLOUDFLARE_API_TOKEN_WORK", "echo ${CLOUDFLARE_API_TOKEN_WORK:-}", "echo $CLOUDFLARE_ACCOUNT_ID",
    "echo $CLOUDFLARE_ACCOUNT_ID_WORK", "echo $CLOUDFLARE_API_KEY_WORK", "echo $CF_API_TOKEN_WORK",
    "echo $CLOUDFLARE_TOOLS_GRANT_KEY", "echo $CLOUDFLARE_TOOLS_GRANTS_DIR", "export CLOUDFLARE_TOOLS_READ_ONLY=1",
    "secret show CLOUDFLARE_API_TOKEN_WORK -p hermes",      # names the variable: blocked, a decision
    "CLOUDFLARE_API_TOKEN_WORK=x make",
])
def test_the_guard_blocks_the_token_variables_with_any_label(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE)


@pytest.mark.parametrize("command", [
    "node ~/.hermes/plugins/cloudflare-tools/dist/cli.js dns read",
    "node ~/.hermes/plugins/cloudflare-tools/dist/mcp.js",
    "node node_modules/@craftsamo/cloudflare-tools/dist/cli.js",
    "cloudflare-tools-cli dns read", "cloudflare-tools-cli run cloudflare_dns_record_add",
    "/opt/homebrew/bin/cloudflare-tools-cli grant list",
    "bash -c 'cloudflare-tools-cli dns read'", "sudo cloudflare-tools-cli zone list",
    "npx @craftsamo/cloudflare-tools", "npx -y @craftsamo/cloudflare-tools@0.12.0",
    "pnpm dlx @craftsamo/cloudflare-tools", "npm install -g @craftsamo/cloudflare-tools",
    "cat ~/.local/state/cloudflare-tools/grants/grants.json", "ls ~/.local/state/cloudflare-tools",
    "ls ~/.hermes/plugins/cloudflare-tools", "cat ~/.hermes/plugins/cloudflare-tools/package.json",
    "cat $HOME/.local/state/cloudflare-tools/grants/usage.jsonl",
])
def test_the_guard_blocks_the_plugin_s_cli_install_and_state(command):
    assert gate("terminal", command=command) == block_with(plugin.BYPASS_MESSAGE)


@pytest.mark.parametrize("command", [
    "grep wrangler package.json", "brew install cloudflared", "cat wrangler.toml", "npm view wrangler version",
    "dig example.com", "curl https://www.cloudflarestatus.com/api/v2/status.json", "secret ls -p hermes",
    "secret show CLOUDFLARE_WORK -p hermes", "ls .wrangler/state", "git log --grep cloudflare",
    "grep -n 'wrangler deploy' docs/deploy.md", "grep -En 'wrangler (pages|d1)' package.json | head",
    "echo \"run wrangler login first\"", "npm run deploy",
    "grep -n cloudflare-tools-cli notes.md", "echo \"run cloudflare-tools-cli later\"",
    "cat docs/cloudflare-tools.md", "git log -- hermes/plugins/guards/cloudflare-tools-guard",
    "ls ~/.hermes/plugins/guards/cloudflare-tools-guard", "ls /work/hermes-cloudflare-tools/hermes",
    "ls /work/feat-cloudflare-tools-guard", "cat /x/Worktrees/dotconfig/feat-hermes-cloudflare-tools/README.md",
    "git log -- hermes/plugins/cloudflare_tools_guard",
    "ls ~/.local/state", "ls ~/.local/state/*", "ls ~/.local/state*", "ls ~/.local/st*",
    "ls ~/.local/state/cloudflare-b*", "cd ~/.local/state && ls",
    "ls ~/.hermes/profiles/assistant/skills", "echo $HOME", "echo \"$CLOUDFLARE\"",
])
def test_the_guard_leaves_ordinary_commands_alone(command):
    assert gate("terminal", command=command) is None


@pytest.mark.parametrize("command", [
    "cd ~/.local/state && cat cloudflare-tools/grants/grants.json",
    "cat ~/.local/state//cloudflare-tools/grants/grants.json",
    "cat ~/.local/state/./cloudflare-tools/grants/grants.json",
    'cat ~/.local/state/"cloudflare-tools"/grants/grants.json',
    "cat ~/.local/state/cloudflare''-tools/grants/grants.json",
    "cd ~/.local/state && cat cloudflare-'tools'/grants/grants.json",
    "cat ${HOME}/.local/state/cloudflare-tools/grants/grants.json",
    "cat --file=~/.local/state//cloudflare-tools/grants/grants.json",
    "ls ~/.local/state/cloudflare-tool?",
    "cat ~/.local/state/cloudflare-tool*/grants/grants.json",
    "cat ~/.local/state/*tools/grants/grants.json",
    "cd ~/.local/state && ls cloudflare-tool?",
    "cat ~/.hermes/profiles/assistant/plugins/cloudflare-t*ls/dist/cli.js",
    "(cd ~/.hermes/plugins && cat cloudflare-tools/package.json)",
    "bash -c 'cd ~/.hermes/plugins; cat cloudflare-tools/package.json'",
    "bash -c 'cat ~/.local/state/cloudflare-tools/grants/x'",
    "cd ~/.local/state && cd cloudflare-tools",
    "pushd ~/.local/state && ls cloudflare-tools",
])
def test_terminal_blocks_single_line_forms(command):
    assert blocked(gate("terminal", command=command)), command


@pytest.mark.parametrize("command", [
    "git push origin hermes/cloudflare-tools",
    "git checkout hermes/cloudflare-tools",
    "git log origin/main..hermes/cloudflare-tools",
    "git branch -d cloudflare-tools",
    "git checkout -b feat/cloudflare-tools",
    "git merge origin/cloudflare-tools",
    "git rebase hermes/cloudflare-tools",
    "cd ~/ghq/github.com/me/shop && git push origin hermes/cloudflare-tools",
    "bash -c 'git push origin hermes/cloudflare-tools'",
    "ls ~/.hermes/profiles/assistant/plugins/cloudflare-tools",      # no copy of the package there
    "ls /elsewhere/cloudflare-tools/dist-not",
    "git commit -m 'remove cloudflare-access'",
])
def test_a_git_ref_or_a_name_that_resolves_to_nothing_passes(command, isolated, monkeypatch):
    tracked(monkeypatch, isolated)
    assert gate("terminal", command=command) is None, command
    assert gate("terminal", command=command, workdir=str(isolated)) is None, command


def test_a_directory_named_like_the_package_is_caught_when_it_exists(monkeypatch, isolated):
    checkout = isolated / "home" / "ghq" / "github.com" / "craft-agent" / "cloudflare-tools"
    profile_copy = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "cloudflare-tools"
    workspace = isolated / "work"
    for directory in (checkout, profile_copy, workspace / "cloudflare-tools" / "sub"):
        directory.mkdir(parents=True)
    tracked(monkeypatch, workspace)
    for command in ("cd ~/ghq/github.com/craft-agent/cloudflare-tools", f"cd {checkout}", f"ls {checkout}/src",
                    f"ls {profile_copy}", "ls ~/.hermes/profiles/assistant/plugins/cloudflare-tools",
                    "bash -c 'cd ~/.hermes/profiles/assistant/plugins; cat cloudflare-tools/package.json'",
                    "cat cloudflare-tools/sub/x", "git branch -d cloudflare-tools"):
        assert blocked(gate("terminal", command=command)), command
    assert gate("terminal", command="git push origin hermes/cloudflare-tools") is None   # workspace/hermes/… is absent
    assert blocked(gate("read_file", path=str(checkout / "README.md")))
    assert blocked(gate("read_file", path=str(profile_copy / "package.json")))
    assert blocked(gate("read_file", path=str(workspace / "cloudflare-tools" / "sub" / "x")))
    assert gate("read_file", path=str(workspace / "cloudflare-tools-notes" / "x")) is None


def test_a_link_to_an_existing_package_directory_is_followed(isolated):
    package = isolated / "elsewhere" / "cloudflare-tools"
    package.mkdir(parents=True)
    (isolated / "shortcut").symlink_to(package)
    assert blocked(gate("read_file", path=str(isolated / "shortcut" / "package.json")))
    assert blocked(gate("terminal", command=f"cat {isolated}/shortcut/package.json"))


@pytest.mark.parametrize("command", [
    "env", "env | grep -i cloud", "env > /tmp/x", "env -0", "env; ls", "env && ls", "env 2>&1 | head",
    "/usr/bin/env", "sudo env", "cd /tmp && env", "echo $(env)", "bash -c 'env'", "bash -c \"env | sort\"",
    "if true; then env; fi", "env FOO=1", "env -u X",
    "printenv", "printenv HOME", "echo x | xargs printenv", "/usr/bin/printenv", "bash -c printenv",
    "export -p", "export", "export | grep X", "declare -p", "declare -x", "typeset -x", "typeset -p",
    "declare -px", "set", "set | grep X",
    "ps eww -p 1", "ps -Eww", "ps auxe", "ps ae", "ps -p 1 -E", "ps -ax -E | head",
    "python3 -c 'import os; print(dict(os.environ))'", "node -e 'console.log(process.env)'",
    "python3 - <<'PY'\nimport os\nprint(os.environ)\nPY", "awk 'BEGIN{for(k in ENVIRON) print k}'",
    "cat /proc/self/environ", "tr '\\0' '\\n' < /proc/1/environ", "strings /proc/$$/environ",
    "launchctl getenv PATH", "launchctl procinfo 1", "launchctl print gui/501/ai.hermes.multiplex",
    "launchctl list ai.hermes.multiplex",
    "jq -n env", "jq -n '$ENV'", "jq -n 'env | keys'", "jq -r '. | env' x.json", "jq -n '$ENV | to_entries'",
    "jq --arg a b -n 'env'", "echo {} | jq env", "jq -n -r $ENV",
    "perl -e 'print %ENV'", "perl -e 'print \"$_=$ENV{$_}\\n\" for keys %ENV'",
    "ruby -e 'p ENV'", "ruby -e 'puts ENV.to_h'", "ruby -e 'ENV.each { |k, v| puts k }'", "ruby -e 'puts ENV.keys'",
    "ruby -e 'puts ENV.map { |k, v| k }'", "sudo ruby -e 'p ENV'",
    "php -r 'print_r(getenv());'", "php -r 'var_dump($_ENV);'", "php -r 'print_r($_SERVER);'", "php -r 'phpinfo();'",
    "awk 'BEGIN{for(k in ENVIRON) print k, ENVIRON[k]}'",
    "compgen -e", "compgen -v", "compgen -A variable", "compgen -A export", "compgen -ev", "bash -c 'compgen -e'",
    "echo ${!CLOUD*}", "echo \"${!name}\"", "for v in ${!CLOUD*}; do echo $v; done",
    "for i in \"${!arr[@]}\"; do echo $i; done",       # a known false positive: the indirect forms are not told apart
])
def test_terminal_refuses_commands_that_print_the_environment(command):
    assert gate("terminal", command=command) == block_with(plugin.ENV_MESSAGE), command


@pytest.mark.parametrize("command", [
    "env FOO=1 make", "env -u X ls", "env -i FOO=1 sh -c 'echo $FOO'", "env -C /tmp ls", "env -- ls",
    "/usr/bin/env python3 script.py", "sudo env FOO=1 ls", "env CI=1 pnpm run build", "env FOO=1 make; ls",
    "env -S 'make test'", "env -i", "make env", "ls env", "cat env.sh", "git log --grep env", "man env",
    "which printenv", "type env", "command -v env", "grep -n printenv docs/x.md", "echo \"run printenv\"",
    "echo \"env\"", "grep -rn 'os.environ' src", "grep -rn process.env src", "git log --grep environ",
    "sed -n 1,20p docs/env.md", "cat .env.example", "ls environments",
    "export PATH=$PATH:/x", "export FOO=1 BAR=2", "export -n FOO", "set -euo pipefail", "set -e", "declare -A map",
    "declare -x FOO=1", "typeset -r FOO=1", "setopt noglob",
    "ps aux", "ps -ef", "ps -e", "ps -p 1 -o etime=", "ps -ax -o pid,command | grep node",
    "launchctl list", "launchctl print gui/501/com.example.other",
    "python3 script.py", "node build.js", "python3 -c 'print(1)'", "cat /proc/cpuinfo",
    "jq . package.json", "jq '.env' config.json", "jq -r '.scripts.env' package.json", "jq -n 'env.HOME'",
    "jq -n '$ENV.PATH'", "jq . env.json", "jq -r .name ./env", "cat x.json | grep env", "grep -rn 'jq -n env' docs",
    "echo 'jq -n env'",
    "grep -rn '%ENV' lib/", "perl script.pl", "perl -e 'print $ENV{HOME}'", "perl -e 'print 1'",
    "ruby script.rb", "ruby -e 'puts ENV[\"HOME\"]'", "ruby -e 'puts ENV.fetch(\"HOME\")'",
    "ruby -e 'puts 1'", "grep -n 'ENV.to_h' app.rb", "grep -n 'p ENV' app.rb", "make ENV=prod",
    "echo \"ENV NODE_ENV production\" >> Dockerfile",
    "php script.php", "php -r 'echo getenv(\"HOME\");'", "php -r 'echo $_SERVER[\"argv\"][0];'", "php -v",
    "compgen -c", "compgen -f -- foo", "compgen -W 'a b' -- a", "grep -n compgen docs/x.md", "man compgen",
    "echo ${HOME}", "echo ${#arr}", "echo ${arr[@]}", "echo ${HOME:-x}", "echo $((1+2))",
])
def test_terminal_leaves_commands_that_run_something_else_alone(command):
    assert gate("terminal", command=command) is None, command


def test_the_environment_form_judged_without_a_readable_line_is_judged_by_pattern():
    # an unclosed quote cannot be read: the pattern alone decides
    assert gate("terminal", command="env | grep 'x") == block_with(plugin.ENV_MESSAGE)
    assert gate("terminal", command="env FOO=1 make 'x") is None


def test_a_mention_of_a_dump_on_a_line_that_runs_fed_input_is_refused():
    assert blocked(gate("terminal", command="echo printenv | sh"))


def test_the_token_variable_wins_over_the_environment_message_only_in_text():
    assert gate("terminal", command="echo $CLOUDFLARE_API_TOKEN_WORK") == block_with(plugin.BYPASS_MESSAGE)
    assert gate("terminal", command="printenv CLOUDFLARE_API_TOKEN_WORK") == block_with(plugin.ENV_MESSAGE)


def tracked(monkeypatch, cwd):
    monkeypatch.setattr(plugin, "_tracked_cwd", lambda task_id="", session_id="": str(cwd))


def test_the_terminal_directory_kept_between_calls_is_judged(monkeypatch, isolated):
    home = isolated / "home"
    assert gate("terminal", command="cd ~/.local/state") is None            # call 1: nothing named yet
    tracked(monkeypatch, home / ".local" / "state")
    assert blocked(gate("terminal", command="cd cloudflare-tools"))         # call 2
    assert blocked(gate("terminal", command="cat cloudflare-tools/grants/grants.json"))
    assert gate("terminal", command="ls") is None


def test_a_terminal_inside_a_protected_directory_is_blocked(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "cloudflare-tools"
    (install / "dist").mkdir(parents=True)
    tracked(monkeypatch, install)
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    tracked(monkeypatch, install / "dist")
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    (isolated / "shortcut").symlink_to(install)
    tracked(monkeypatch, isolated / "shortcut")
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)


def test_a_terminal_inside_the_state_root_is_blocked(monkeypatch, isolated):
    state = isolated / "home" / ".local" / "state" / "cloudflare-tools" / "grants"
    state.mkdir(parents=True)
    tracked(monkeypatch, state)
    assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE)
    tracked(monkeypatch, isolated)
    (isolated / "shortcut").symlink_to(state)
    assert gate("terminal", command="ls", workdir=str(isolated / "shortcut")) == block_with(plugin.CWD_MESSAGE)
    assert blocked(gate("terminal", command="ls", workdir=str(state)))
    assert gate("terminal", command="ls", workdir=str(isolated)) is None


def test_a_terminal_inside_a_cli_login_is_blocked(monkeypatch, isolated):
    for name in (".cloudflared", ".wrangler/config"):
        directory = isolated / "home" / name
        directory.mkdir(parents=True)
        tracked(monkeypatch, directory)
        assert gate("terminal", command="ls") == block_with(plugin.CWD_MESSAGE), name
    tracked(monkeypatch, isolated / "home" / ".wrangler")
    assert gate("terminal", command="ls") is None


def test_a_workdir_replaces_the_recorded_directory(monkeypatch, isolated):
    install = isolated / "home" / ".hermes" / "profiles" / "assistant" / "plugins" / "cloudflare-tools"
    install.mkdir(parents=True)
    tracked(monkeypatch, install)
    assert gate("terminal", command="node dist/cli.js", workdir=str(isolated)) is None
    assert gate("terminal", command="ls", workdir="~/Workspaces") is None
    tracked(monkeypatch, isolated)
    assert blocked(gate("terminal", command="ls", workdir=str(install)))
    tracked(monkeypatch, isolated / "home" / ".local" / "state")
    assert blocked(gate("terminal", command="ls", workdir="cloudflare-tools"))      # relative: the recorded one


def test_relative_words_resolve_against_the_terminal_directory(monkeypatch, isolated):
    grants = isolated / "grants-dir"
    grants.mkdir()
    monkeypatch.setenv("CLOUDFLARE_TOOLS_GRANTS_DIR", str(grants))
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
    assert gate("terminal", command=f"cat {isolated}/elsewhere/grants.json") is None
    monkeypatch.setenv("CLOUDFLARE_TOOLS_GRANTS_DIR", str(state))
    assert blocked(gate("terminal", command=f"cat {isolated}/elsewhere/grants.json"))


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
    assert blocked(gate("terminal", command="ls", workdir="~/.local/state/cloudflare-tools"))


def test_a_project_runs_its_own_wrangler_through_its_package_manager(isolated, monkeypatch):
    project = isolated / "ghq" / "shop"
    (project / ".git").mkdir(parents=True)
    (project / ".git" / "config").write_text('[remote "origin"]\n\turl = git@github.com:me/shop.git\n')
    monkeypatch.setattr(plugin.project_place, "_roots", lambda: [(isolated / "ghq").resolve()])
    monkeypatch.setattr(plugin.project_place, "_own_common", lambda: None)
    deploy = {"command": "pnpm exec wrangler deploy", "workdir": str(project)}
    assert gate("terminal", **deploy) == block_with(plugin.BYPASS_MESSAGE)   # not one of its dependencies
    (project / "node_modules" / ".bin").mkdir(parents=True)
    (project / "node_modules" / ".bin" / "wrangler").write_text("")
    assert gate("terminal", **deploy) is None
    assert gate("terminal", command=f"cd {project} && pnpm run deploy") is None
    for command in ("wrangler deploy", "pnpm dlx wrangler deploy", "npx -y wrangler deploy", "cloudflared tunnel list",
                    "cloudflare-tools-cli dns read", "printenv", "echo $CLOUDFLARE_API_TOKEN"):
        assert blocked(gate("terminal", command=command, workdir=str(project))), command
    assert gate("terminal", command="pnpm exec wrangler deploy", workdir=str(isolated)) == \
        block_with(plugin.BYPASS_MESSAGE)


def test_file_tools_may_read_the_plugin_source_but_not_the_state_or_the_cli_logins():
    (Path.home() / ".hermes" / "profiles" / "assistant" / "plugins" / "cloudflare-tools").mkdir(parents=True)
    guard_source = ROOT / "__init__.py"
    assert gate("read_file", path=str(guard_source)) is None
    assert gate("search_files", pattern="x", path=str(ROOT)) is None
    assert gate("read_file", path="/repo/wrangler.toml") is None
    assert gate("write_file", path="/repo/notes.md", content="set CLOUDFLARE_API_TOKEN and call api.cloudflare.com") is None
    for tool, args in (("read_file", {"path": "/Users/x/.cloudflared/cert.pem"}),
                       ("search_files", {"pattern": "x", "path": "/Users/x/.wrangler/config"}),
                       ("read_file", {"path": "~/.local/state/cloudflare-tools/grants/grants.json"}),
                       ("write_file", {"path": "~/.hermes/plugins/cloudflare-tools/dist/cli.js", "content": "x"}),
                       ("patch", {"path": "~/.hermes/plugins/cloudflare-tools/package.json", "old": "a", "new": "b"}),
                       ("read_file", {"path": "~/.hermes/profiles/assistant/plugins/cloudflare-tools/x"})):
        assert gate(tool, **args) == block_with(plugin.BYPASS_MESSAGE), args
    assert gate("read_file", path="/proc/self/environ") == block_with(plugin.ENV_MESSAGE)


def test_a_worktree_path_with_the_package_name_in_it_passes():
    path = "/x/Worktrees/dotconfig/hermes-cloudflare-tools/README.md"
    assert gate("read_file", path=path) is None
    assert gate("terminal", command=f"cat {path}") is None


def test_file_tools_block_the_state_root_by_real_path(monkeypatch, isolated):
    state = isolated / "state-dir"      # no pattern names it: only its real path does
    (state / "grants").mkdir(parents=True)
    (state / "grants" / "grants.json").write_text("x")
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("CLOUDFLARE_TOOLS_GRANTS_DIR", str(state))
    for path in (state / "grants" / "grants.json", state, link / "grants" / "grants.json", link,
                 isolated / "other" / ".." / "state-dir" / "grants"):
        assert blocked(gate("read_file", path=str(path))), path
    assert blocked(gate("write_file", path=str(link / "new.txt"), content="x"))
    assert gate("read_file", path=str(isolated / "state-dir-notes.txt")) is None


def test_the_xdg_state_root_is_protected(monkeypatch, isolated):
    state = isolated / "xdg" / "cloudflare-tools"
    state.mkdir(parents=True)
    link = isolated / "elsewhere"
    link.symlink_to(state)
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert blocked(gate("read_file", path=str(link / "grants")))
    assert gate("read_file", path=str(isolated / "xdg" / "cloudflare-tools-notes.txt")) is None
    assert gate("read_file", path=str(isolated / "xdg")) is None


def test_a_relative_xdg_state_home_is_ignored_as_the_package_does(monkeypatch, isolated):
    default = str(isolated / "home" / ".local" / "state" / "cloudflare-tools")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", "relative/state")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", "~/state")
    assert plugin._state_root() == default
    monkeypatch.setenv("XDG_STATE_HOME", str(isolated / "xdg"))
    assert plugin._state_root() == str(isolated / "xdg" / "cloudflare-tools")


def test_a_configured_grants_directory_is_protected_through_a_link(monkeypatch, isolated):
    custom = isolated / "custom"
    custom.mkdir()
    (isolated / "shortcut").symlink_to(custom)
    assert gate("read_file", path=str(isolated / "shortcut" / "grants.json")) is None
    monkeypatch.setenv("CLOUDFLARE_TOOLS_GRANTS_DIR", str(custom))
    assert blocked(gate("read_file", path=str(custom / "grants.json")))
    assert blocked(gate("read_file", path=str(isolated / "shortcut" / "grants.json")))


def test_the_installed_plugin_is_protected_through_a_link(isolated):
    install = isolated / "home" / ".hermes" / "plugins" / "cloudflare-tools"
    install.mkdir(parents=True)
    link = isolated / "shortcut"
    link.symlink_to(install)
    assert blocked(gate("read_file", path=str(link / "package.json")))


def test_the_cli_logins_are_protected_through_a_link(isolated):
    for name in (".cloudflared", ".wrangler/config"):
        directory = isolated / "home" / name
        directory.mkdir(parents=True)
        link = isolated / (name.replace("/", "-") + "-link")
        link.symlink_to(directory)
        assert blocked(gate("read_file", path=str(link / "x"))), name
    assert gate("read_file", path=str(isolated / "home" / ".wrangler" / "state")) is None


def test_a_failing_check_blocks_what_it_guards(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin, "bypass", boom)
    assert gate("terminal", command="ls") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("read_file", path="a.txt") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("web_search", query="x") is None
    monkeypatch.setattr(plugin.human_gate, "no_human", boom)
    assert gate("cloudflare_dns_record_add", zone="example.com") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("cloudflare_zone_cache_purge_all", zone="example.com") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("cloudflare_future_write") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("cloudflare_dns_read", method="list") is None
    monkeypatch.setattr(plugin, "_inbound_peer", boom)
    assert gate("cloudflare_rules_delete") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("cloudflare_zone_read", method="list") is None
    assert gate("web_search", query="x") is None


def test_a_failing_command_reader_blocks_the_terminal(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(plugin.shell_commands, "runs", boom)
    assert gate("terminal", command="ls") == block_with(plugin.UNCHECKED_MESSAGE)
    assert gate("read_file", path="a.txt") is None      # the file tools never reach the command reader


def test_the_progress_line_names_the_operation_only(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    plugin.register(Ctx())

    def line(tool, **args):
        return display.build_tool_preview(tool, args, max_len=0)

    assert line("cloudflare_dns_record_add", zone="private.example", content="a private value") == "add DNS records"
    assert line("cloudflare_zone_cache_purge", zone="private.example", urls=["https://private.example/x"]) == \
        "purge cache"
    assert line("cloudflare_zone_cache_purge_all", zone="private.example") == "purge whole cache"
    assert line("cloudflare_workers_rollback", script="a-private-worker") == "roll back Worker"
    assert line("cloudflare_grant_revoke", id="grant_0123456789ab") == "revoke grant"
    assert line("cloudflare_dns_read", method="list", zone="private.example") == "list"
    assert line("cloudflare_dns_read", method="export", zone="private.example") == "export"
    assert line("cloudflare_dns_read", method="a private value", name="private.example") is None
    assert line("cloudflare_analytics_read", method="security_events", zone="private.example") == "security_events"
    assert line("cloudflare_grant_read", method="log", limit=5) == "log"
    assert line("cloudflare_storage_read", method="databases") == "databases"
    assert line("cloudflare_workers_read", method="schedules", script="a-private-worker") == "schedules"


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
    assert set(plugin.METHODS) == plugin.READS      # every read declares a method


def test_register_installs_one_hook_and_no_tool(monkeypatch):
    display = pytest.importorskip("agent.display")
    monkeypatch.setattr(display, "_PREVIEW_BUILDERS", {})
    ctx = Ctx()
    plugin.register(ctx)
    assert ctx.tools == {} and ctx.hooks == [("pre_tool_call", plugin.gate)]
