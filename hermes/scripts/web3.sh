#!/usr/bin/env bash
# Engine manager for the web3 plugins (chain-read and wallet; docs/web3.md).
#
# Both plugins run their engine with the interpreter of an isolated venv under the ignored
# hermes/local/web3/, built from the hash-locked engines/web3/requirements.lock. The wallet uses
# every Keychain item labelled as a seed phrase or a private key, under any name and project, and
# the optional RPC provider keys; none of them ever lives in a file:
#
#   secret set HERMES_MAIN -p <project> -D MNEMONIC        a seed phrase Hermes may sign with
#   secret set HERMES_DEPLOY -p <project> -D PRIVATE_KEY   a private key Hermes may sign with
#   (HERMES as a word of the name marks a Hermes wallet; under any other name a seed phrase or
#    key is watch-only: its addresses are read, it never signs)
#   secret set ALCHEMY_API_KEY -p hermes --scope web3-rpc
#   secret set HELIUS_API_KEY -p hermes --scope web3-rpc
#
#   install                build or refresh the venv from the lock (Python 3.12.11, uv)
#   status                 engine versions and which wallet items and RPC keys are stored, by name
#                          (values are never printed)
#   addresses [N] [CHAIN]  every labelled seed's first N accounts (default 5) and every key, on EVM
#                          and Solana, with native balances on CHAIN; addresses only, never a key
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
      while IFS= read -r line; do
        echo "  $project  $line"
        found=1
      done < <("$SECRET" ls -p "$project" --long 2>/dev/null | tail -n +2 \
                 | grep -iE '[[:space:]](mnemonic|seed phrase|private[ _-]?key)[[:space:]]' \
                 | awk '{n = split(tolower($1), w, /[-_.]/); use = "watch-only"
                         for (i = 1; i <= n; i++) if (w[i] == "hermes") use = "sign"
                         print $1, "(" $2 ")", use}')
    done
    [ "$found" = 1 ] || echo "  none labelled (secret set <NAME> -p <project> -D MNEMONIC)"
    echo "alchemy:  $(stored ALCHEMY_API_KEY web3-rpc "optional; public RPC is used")"
    echo "helius:   $(stored HELIUS_API_KEY web3-rpc "optional; public RPC is used")"
    ;;
  addresses)
    [ -x "$VENV/bin/python" ] || die "engine not installed (run: $0 install)"
    COUNT="${2:-5}"
    CHAIN="${3:-}"
    case "$COUNT" in ''|*[!0-9]*) die "usage: $0 addresses [N] [CHAIN]" ;; esac
    case "$CHAIN" in *[!a-z0-9-]*) die "CHAIN is a name like sepolia or solana-devnet" ;; esac
    printf '{"op": "accounts", "count": %s%s}' "$COUNT" "${CHAIN:+, \"chain\": \"$CHAIN\"}" \
      | env -i HOME="$HOME" PATH=/usr/bin:/bin LANG=en_US.UTF-8 \
          "$VENV/bin/python" "$HERMES_DIR/plugins/web3/wallet/signer.py" \
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
  *)
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
