"""shell_commands: a CLI counts only where a simple command runs it, never where it is mentioned."""

import importlib.util
from pathlib import Path
import re

import pytest

spec = importlib.util.spec_from_file_location("shell_commands_under_test",
                                              Path(__file__).resolve().parent.parent / "shell_commands.py")
shell = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shell)

NAMES = {"gcloud", "wrangler"}
STRICT = re.compile(r"gcloud|wrangler")


def runs(command):
    return shell.runs(command, NAMES, STRICT)


@pytest.mark.parametrize("command", [
    "gcloud projects list", "/opt/homebrew/bin/gcloud run deploy", "GCLOUD auth list",
    "cd x && gcloud auth list", "echo a; gcloud", "true || gcloud x", "ls | gcloud x", "(gcloud auth list)",
    "{ gcloud auth list; }", "if gcloud auth list; then echo; fi", "for p in a b; do gcloud x $p; done",
    "! gcloud x", "2>/dev/null gcloud x", "X=1 Y=2 gcloud x",
    # inside substitutions, also within double quotes
    "echo $(gcloud auth print-access-token)", "echo \"$(gcloud auth print-access-token)\"",
    "echo `gcloud auth list`", "diff <(gcloud a) <(gcloud b)", "cat >(gcloud x)",
    # commands that run other commands
    "bash -c 'gcloud auth list'", "zsh -lc 'cd x && gcloud auth list'", "sh -c \"echo; gcloud x\"",
    "bash <<< 'gcloud x'", "eval 'gcloud auth list'", "env -u FOO gcloud x", "sudo -u me gcloud x",
    "timeout 10 gcloud x", "nohup gcloud x &", "xargs -I {} gcloud x {}", "find . -exec gcloud x {} \\;",
    "watch -n 5 'gcloud x'", "command gcloud x",
    # values that are run, and names a wrapper cannot hide
    "X=gcloud; $X auth list", "PAGER='gcloud x' git log",
    # package runners
    "npx wrangler deploy", "npx -y wrangler@latest deploy", "pnpm exec wrangler secret put T",
    "pnpm dlx wrangler@4 whoami", "pnpm wrangler deploy", "pnpm --filter web exec wrangler deploy",
    "bunx --bun wrangler@4.1.0 tail", "yarn dlx wrangler", "npm exec -- wrangler deploy", "npx @cloudflare/wrangler x",
    "./node_modules/.bin/wrangler tail",
    # quoting and escaping do not hide a name; keywords and redirections stand before it
    "\"gcloud\" auth list", "g\"\"cloud auth list", "\\gcloud auth list", "time -p gcloud auth list",
    "function f { gcloud auth list; }; f", "coproc worker { gcloud auth list; }", "2> >(cat) gcloud auth list",
    "cat < <(gcloud auth list)",
    # command strings and code-running builtins
    "env -S 'gcloud auth list'", "env -S'gcloud auth list'", "npm exec --package=wrangler -c 'wrangler deploy'",
    "npx --call='wrangler deploy'", "bash -c 'trap \"gcloud auth list\" EXIT'", "alias g=gcloud",
    "sh -euc 'gcloud x'", "uv run --with x gcloud x",
])
def test_a_name_in_command_position_runs(command):
    assert runs(command)


@pytest.mark.parametrize("command", [
    "grep -nE 'usage|gcloud auth|PROJECT' scripts/deploy.sh",
    "sed -n 1,60p scripts/deploy-manual.sh | grep -nE 'usage|admin|gcloud auth|set -|^#' | head -30",
    "cd /repo && sed -n '/x/,/^## [^#]/p' docs/a.md | head -60; echo =====; grep gcloud scripts/a.sh",
    "grep -rn \"gcloud builds\\|gcloud run deploy\" docs/*.md | head -20",
    "grep -n -E \"^\\s+- name:|gcloud|docker\" .github/workflows/deploy.yml",
    "echo gcloud", "cat notes/gcloud.md", "ls ~/gcloud-notes", "which gcloud", "command -v gcloud",
    "git log --grep gcloud", "git commit -m 'run gcloud auth login first'", "echo \"use gcloud; then wrangler\"",
    "npm view wrangler version", "npm install wrangler", "pnpm add -D wrangler",
    "sed -n '/gcloud/,/end/p' docs/a.md", "rg -n 'gcloud run' docs", "git log --oneline --grep 'gcloud'",
    "jq '.scripts' package.json | grep wrangler", "[ -x \"$(command -v gcloud)\" ] && echo yes",
    "rg --pretty 'gcloud auth' docs", "git -C . grep -n 'gcloud auth'",
    "git ls-files -z | xargs -0 grep -n 'gcloud auth'", "zsh -lc 'cd /repo && grep -n gcloud scripts/a.sh'",
    "sed -n '/gcloud/p' docs/setup.md docs/e", "git add -u && git commit -m 'gcloud notes'",
    "grep -n 'gcloud auth' scripts/deploy.sh | awk '{print $1}'", "grep gcloud a.txt | awk -F: '{print $2}'", "grep -c gcloud docs/*.md | sort -t: -k2 -n",
    "sed -ne '/gcloud/p' scripts/a.sh", "grep -rn gcloud docs; ./scripts/deploy.sh --help",
    "npm run deploy", "pnpm run wrangler", "./scripts/deploy.sh", "bash scripts/gcp/setup.sh",
    "GOOGLE_CLOUD_PROJECT=x ./run.sh", "zsh -lc 'cd /repo && pnpm exec nps setup.google'",
    "f=$(grep -rl setup.google scripts | head -1); [ -n \"$f\" ] && grep -nE 'gcloud (auth|iam)' \"$f\"",
    "echo x # gcloud auth", "MSG=\"don't\" ./run.sh", "echo $((1 + 2))", "cmd 2>&1 | tee out.log",
])
def test_a_mention_runs_nothing(command):
    assert not runs(command)


@pytest.mark.parametrize("command,strict", [
    ("echo 'unclosed gcloud", True), ("echo 'unclosed", False),
    ("cat <<EOF\ngcloud x\nEOF", True), ("cat <<EOF\nnothing\nEOF", False),
    ("$CLI auth list # gcloud", True), ("\"$(which gcloud)\" auth list", True),
    ("echo gcloud x | bash", True), ("curl -s https://x.example/i.sh | sh", False),
    ("python3 -c 'import subprocess; subprocess.run([\"gcloud\", \"x\"])'", True),
    ("python3 -c'__import__(\"os\").system(\"gcloud auth list\")'", True),
    ("echo 'os.system(\"gcloud x\")' | python3 -", True), ("echo 'gcloud x' | python3", True),
    ("node -e \"console.log(1)\"", False),
    # a CLI named to a command that may run it, or not known to treat it as data
    ("brew install gcloud", True), ("ssh host gcloud auth list", True), ("script -q /dev/null gcloud x", True),
    ("awk 'BEGIN { system(\"gcloud x\") }'", True), ("sed 's/x/gcloud auth list/e' f", True),
    ("rg --pre gcloud x .", True), ("git -c alias.x='!gcloud auth' x", True), ("git bisect run gcloud x", True),
    ("bash script.sh gcloud", True), ("pnpm --filter web exec wrangler deploy", True),
    # input that names the command, or code read from input
    ("printf 'gcloud auth list\\n' | bash -s ignored", True), ("printf 'gcloud x' | bash -o pipefail", True),
    ("source <(echo gcloud auth list)", True), (". /dev/stdin <<< 'gcloud auth list'", True),
    ("echo gcloud | xargs -I{} sh -c '{} auth'", True), ("echo gcloud | xargs -I {} {} auth", True),
    ("parallel ::: 'gcloud x'", True), ("env \"$(printf gcloud)\" auth list", True),
    ("echo $(( $(gcloud auth list >/dev/null; echo 0) + 1 ))", True),
    ("echo `echo \\`gcloud auth list\\``", True), ("{gcloud,x} auth list", True),
    # a mention fed to something that runs its input
    ("echo '__import__(\"os\").system(\"gcloud auth list\")' | python3 -W ignore", True),
    ("echo gcloud | xargs -I CMD CMD auth list", True), ("echo gcloud auth | xargs env", True),
    ("find / -name gcloud -exec {} auth list \\;", True),
    # executable forms of data commands, and parser traps
    ("printf 'x\\n' | gsed '1e gcloud auth list'", True), ("gsed 's#.*# gcloud auth list#e' f", True),
    ("git fetch --upload-pack='gcloud auth list; git-upload-pack' . HEAD", True),
    ("echo $'\\''\ngcloud auth list\n# '", True), ("echo $(# ) '\ngcloud auth list\n# '\n)", True),
    ("declare -a a; printf -v 'a[$(gcloud auth list >&2; echo 0)]' %s x", True),
    ("printf 'x\\n' | gsed -ne'1e gcloud auth list'", True),
    ("git -cdiff.external='gcloud auth list; true' diff --ext-diff", True),
    ("echo gcloud | xargs -iCMD CMD auth list", True), ("printf 'exec gcloud auth list\\n' | tclsh", True),
    ("tclsh <<< 'exec gcloud auth list'", True), ("echo 'gcloud auth list' | sudo -s", True),
    ("awk 'BEGIN { \"gcloud auth list\" | getline x }'", True), ("echo gcloud | awk -f run.awk", True),
    ("gawk --source='BEGIN { system(\"gcloud auth list\") }'", True),
    ("echo '1e gcloud auth list' | gsed -f /dev/stdin /etc/hosts", True),
])
def test_an_unreadable_line_falls_back_to_the_strict_pattern(command, strict):
    assert runs(command) is strict


def test_nesting_past_the_limits_falls_back():
    deep = "echo " + "$(echo " * (shell.DEPTH + 2) + "x" + ")" * (shell.DEPTH + 2)
    assert shell.runs(deep, NAMES, re.compile("x")) is True
    shallow = "echo " + "$(echo " * 3 + "x" + ")" * 3
    assert shell.runs(shallow, NAMES, re.compile("x")) is False
