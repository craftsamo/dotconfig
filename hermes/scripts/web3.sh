#!/usr/bin/env bash
# Engine manager for the web3 plugins (chain-read and wallet; docs/web3.md).
#
# Both plugins run their engine with the interpreter of an isolated venv under the ignored
# hermes/local/web3/, built from the hash-locked engines/web3/requirements.lock. The wallet's
# seed phrase and the optional RPC provider keys live only in the Keychain, never in a file:
#
#   secret set WEB3_MNEMONIC -p hermes --scope web3-wallet -D MNEMONIC
#   secret set ALCHEMY_API_KEY -p hermes --scope web3-rpc
#   secret set HELIUS_API_KEY -p hermes --scope web3-rpc
#
#   install   build or refresh the venv from the lock (Python 3.12.11, uv)
#   status    engine versions and which secrets are stored (values are never printed)
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
    echo "seed:     $(stored WEB3_MNEMONIC web3-wallet "secret set WEB3_MNEMONIC -p hermes --scope web3-wallet -D MNEMONIC")"
    echo "alchemy:  $(stored ALCHEMY_API_KEY web3-rpc "optional; public RPC is used")"
    echo "helius:   $(stored HELIUS_API_KEY web3-rpc "optional; public RPC is used")"
    ;;
  *)
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
