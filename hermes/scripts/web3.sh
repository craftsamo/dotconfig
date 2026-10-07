#!/usr/bin/env bash
# Engine manager for the web3 plugins (chain-read and wallet; docs/web3.md).
#
# Both plugins run their engine with the interpreter of an isolated venv under the ignored
# hermes/local/web3/, built from the hash-locked engines/web3/requirements.lock. The wallet's
# seed phrases and the optional RPC provider keys live only in the Keychain, never in a file;
# a seed named in web3-wallet.yaml as "work-x" is the item WEB3_SEED_WORK_X:
#
#   secret set WEB3_SEED_MAIN -p hermes --scope web3-wallet -D MNEMONIC
#   secret set ALCHEMY_API_KEY -p hermes --scope web3-rpc
#   secret set HELIUS_API_KEY -p hermes --scope web3-rpc
#
#   install              build or refresh the venv from the lock (Python 3.12.11, uv)
#   status               engine versions and which secrets are stored (values are never printed)
#   addresses SEED [N]   that seed's first N accounts (default 3) on EVM and Solana, to fund them;
#                        addresses only, never a key
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
    seeds=$("$SECRET" ls -p hermes 2>/dev/null | sed -n 's#^web3-wallet/\(WEB3_SEED_[A-Z0-9_]*\)$#\1#p' | tr '\n' ' ')
    echo "seeds:    ${seeds:-none (secret set WEB3_SEED_MAIN -p hermes --scope web3-wallet -D MNEMONIC)}"
    echo "alchemy:  $(stored ALCHEMY_API_KEY web3-rpc "optional; public RPC is used")"
    echo "helius:   $(stored HELIUS_API_KEY web3-rpc "optional; public RPC is used")"
    ;;
  addresses)
    [ -x "$VENV/bin/python" ] || die "engine not installed (run: $0 install)"
    SEED="${2:-}"
    COUNT="${3:-3}"
    case "$SEED" in ''|*[!a-z0-9-]*) die "usage: $0 addresses SEED [N] (SEED as named in web3-wallet.yaml)" ;; esac
    case "$COUNT" in ''|*[!0-9]*) die "N must be a number" ;; esac
    printf '{"op": "derive", "seed": "%s", "count": %s}' "$SEED" "$COUNT" \
      | env -i HOME="$HOME" PATH=/usr/bin:/bin LANG=en_US.UTF-8 \
          "$VENV/bin/python" "$HERMES_DIR/plugins/web3/wallet/signer.py" \
      | "$VENV/bin/python" -c '
import json, sys
reply = json.load(sys.stdin)
if not reply.get("ok"):
    sys.exit("error: " + reply.get("error", "unknown"))
print("seed " + reply["data"]["seed"])
for row in reply["data"]["accounts"]:
    print("%3d  EVM %s  Solana %s" % (row["index"], row["evm"], row["solana"]))
'
    ;;
  *)
    sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
