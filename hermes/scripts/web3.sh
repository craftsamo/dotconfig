#!/usr/bin/env bash
# Engine manager for the web3 plugins (evm-access and solana-access; docs/web3.md).
#
# Both plugins run their engine with the interpreter of an isolated venv under the ignored
# hermes/local/web3/, built from the hash-locked engines/web3/requirements.lock. The wallet uses
# every Keychain item labelled as a seed phrase or a private key, under any name and project, and
# the optional RPC provider keys; none of them ever lives in a file:
#
#   secret set HERMES_MAIN -p <project> -D MNEMONIC --no-env        a seed phrase Hermes may sign with
#   secret set HERMES_DEPLOY -p <project> -D PRIVATE_KEY --no-env   a private key Hermes may sign with
#   (HERMES as a word of the name marks a Hermes wallet; under any other name a seed phrase or
#    key is watch-only: its addresses are read, it never signs)
#   secret set ALCHEMY_API_KEY -p hermes --scope web3-rpc
#   secret set HELIUS_API_KEY -p hermes --scope web3-rpc
#   secret set ETHERSCAN_API_KEY -p hermes --scope web3-rpc   verified ABIs Sourcify lacks
#
#   install                build or refresh the venv from the lock (Python 3.12.11, uv)
#   status                 engine versions and which wallet items and API keys are stored, by name
#                          (values are never printed)
#   addresses [N] [CHAIN]  every labelled seed's first N accounts (default 5) and every key, on EVM
#                          and Solana, with native balances on CHAIN; addresses only, never a key
#   new-wallet NAME -j PURPOSE [-p PROJECT] [--scope SCOPE] [--words 12|24] [--yes]
#                          a new Hermes seed phrase (NAME with HERMES as a word), made and stored in
#                          the Keychain (--no-env) after the same card the Assistant shows; the phrase
#                          is never printed. PROJECT defaults to the one holding the Hermes wallets;
#                          the comment is PURPOSE plus word count, date and account #0's addresses
set -euo pipefail

HERMES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="$HERMES_DIR/engines/web3/requirements.lock"
VENV="$HERMES_DIR/local/web3/venv"
PYTHON_VERSION="3.12.11"
SECRET="$HOME/.config/bin/secret"
PACKAGES="eth-account eth-abi mnemonic solders"

die() { echo "error: $*" >&2; exit 1; }

versions() {
  # shellcheck disable=SC2086
  "$VENV/bin/python" - $PACKAGES <<'PY'
import importlib.metadata as m, sys
print(", ".join(f"{name} {m.version(name)}" for name in sys.argv[1:]))
PY
}

stored() {  # NAME SCOPE HINT
  if "$SECRET" show "$1" -p hermes --scope "$2" >/dev/null 2>&1; then
    echo "stored ($1, project hermes, scope $2)"
  else
    echo "missing ($3)"
  fi
}

case "${1:-}" in
  install)
    command -v uv >/dev/null 2>&1 || die "uv not found"
    [ -f "$LOCK" ] || die "missing $LOCK"
    if [ ! -x "$VENV/bin/python" ]; then
      UV_NO_CONFIG=1 uv venv "$VENV" --python "$PYTHON_VERSION" --managed-python
    fi
    [ "$("$VENV/bin/python" --version 2>&1)" = "Python $PYTHON_VERSION" ] \
      || die "unexpected Python in $VENV; remove it and run install again"
    UV_NO_CONFIG=1 uv pip sync --python "$VENV/bin/python" --require-hashes --strict "$LOCK"
    echo "installed $(versions) in $VENV"
    ;;
  status)
    if [ -x "$VENV/bin/python" ]; then
      echo "engine:   $(versions) ($VENV)"
    else
      echo "engine:   not installed (run: $0 install)"
    fi
    echo "wallet:"
    found=0
    for project in $("$SECRET" projects 2>/dev/null); do
      # the wallet's own listing parser (stdlib only): kinds may hold spaces
      while IFS= read -r line; do
        echo "  $line"
        found=1
      done < <("$SECRET" ls -p "$project" --long 2>/dev/null | python3 -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("keychain", sys.argv[1])
keychain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keychain)
for item in keychain.parse_listing(sys.argv[2], sys.stdin.read()):
    note = "  <- injected: secret update ... --no-env" if item["use"] == "sign" and item["env"] != "no" else ""
    print("%s  %s (%s)  %s  env %s%s" % (item["project"], item["name"], item["scope"] or "Shared",
                                         "sign" if item["use"] == "sign" else "watch-only", item["env"], note))
' "$HERMES_DIR/plugins/web3/_shared/keychain.py" "$project")
    done
    [ "$found" = 1 ] || echo "  none ($0 new-wallet HERMES_<NAME> -j <purpose> -p <project>)"
    echo "alchemy:  $(stored ALCHEMY_API_KEY web3-rpc "optional; public RPC is used")"
    echo "helius:   $(stored HELIUS_API_KEY web3-rpc "optional; public RPC is used")"
    echo "etherscan: $(stored ETHERSCAN_API_KEY web3-rpc "optional; verified ABIs come from Sourcify only")"
    ;;
  addresses)
    [ -x "$VENV/bin/python" ] || die "engine not installed (run: $0 install)"
    COUNT="${2:-5}"
    CHAIN="${3:-}"
    case "$COUNT" in ''|*[!0-9]*) die "usage: $0 addresses [N] [CHAIN]" ;; esac
    case "$CHAIN" in *[!a-z0-9-]*) die "CHAIN is a name like sepolia or solana-devnet" ;; esac
    printf '{"op": "accounts", "count": %s%s}' "$COUNT" "${CHAIN:+, \"chain\": \"$CHAIN\"}" \
      | env -i HOME="$HOME" PATH=/usr/bin:/bin LANG=en_US.UTF-8 \
          "$VENV/bin/python" "$HERMES_DIR/plugins/web3/_shared/signer.py" \
      | "$VENV/bin/python" -c '
import json, sys
reply = json.load(sys.stdin)
if not reply.get("ok"):
    sys.exit("error: " + reply.get("error", "unknown"))
data = reply["data"]
for row in data["accounts"]:
    print("%-36s  EVM %-42s  Solana %-44s  %s" % (row["account"], row.get("evm", "-"), row.get("solana", "-"),
                                                row.get("balance", "")))
for item in data.get("skipped", []):
    print("skipped %s: %s" % (item["source"], item["problem"]))
if data.get("setup"):
    print(data["setup"])
'
    ;;
  new-wallet)
    [ -x "$VENV/bin/python" ] || die "engine not installed (run: $0 install)"
    shift
    USAGE="usage: $0 new-wallet NAME -j PURPOSE [-p PROJECT] [--scope SCOPE] [--words 12|24] [--yes]"
    NAME="${1:-}"
    case "$NAME" in ''|-*) die "$USAGE" ;; esac
    shift
    PURPOSE="" PROJECT="" SCOPE="" WORDS="" YES=0
    while [ $# -gt 0 ]; do
      case "$1" in
        -j) [ $# -ge 2 ] || die "$USAGE"; PURPOSE="$2"; shift 2 ;;
        -p) [ $# -ge 2 ] || die "$USAGE"; PROJECT="$2"; shift 2 ;;
        --scope) [ $# -ge 2 ] || die "$USAGE"; SCOPE="$2"; shift 2 ;;
        --words) [ $# -ge 2 ] || die "$USAGE"; WORDS="$2"; shift 2 ;;
        --yes) YES=1; shift ;;
        *) die "$USAGE" ;;
      esac
    done
    # the signer runs with a minimal environment, as from the plugins; this script's own state
    # directory keeps the new-wallet cap apart from the Assistant's
    "$VENV/bin/python" - "$HERMES_DIR/plugins/web3/_shared/signer.py" "$HERMES_DIR/local/web3/state" "$YES" \
        "$NAME" "$PURPOSE" "$PROJECT" "$SCOPE" "$WORDS" <<'PY'
import json, os, subprocess, sys
signer, state, yes, name, purpose, project, scope, words = sys.argv[1:]
spec = {"name": name, "purpose": purpose}
spec.update({k: v for k, v in (("project", project), ("scope", scope)) if v})
if words:
    if not words.isdigit():
        sys.exit("error: --words is 12 or 24")
    spec["words"] = int(words)
env = {"HOME": os.environ["HOME"], "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"}

def run(op, **extra):
    proc = subprocess.run([sys.executable, signer], input=json.dumps({"op": op, "state": state, **spec, **extra}),
                          capture_output=True, text=True, env=env, timeout=180)
    reply = json.loads(proc.stdout or '{"ok": false, "error": "the signer failed without a result"}')
    if not reply.get("ok"):
        sys.exit("error: " + reply.get("error", "unknown"))
    return reply["data"]

checked = run("wallet_check")
print(checked["card"])
if yes != "1":
    try:
        with open("/dev/tty") as tty:
            sys.stdout.write("Create this wallet? [y/N] ")
            sys.stdout.flush()
            answer = tty.readline().strip().lower()
    except OSError:
        sys.exit("error: no terminal to confirm on; pass --yes to confirm the card above")
    if answer not in ("y", "yes"):
        sys.exit("not created")
made = run("wallet_create", digest=checked["digest"])
print()
print("created %s (%s, ENV no)" % (made["account"], made["kind"]))
print("EVM     %s" % made["addresses"]["evm"])
print("Solana  %s" % made["addresses"]["solana"])
print("comment %s" % made["comment"])
print()
print(made["note"])
PY
    ;;
  *)
    sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
