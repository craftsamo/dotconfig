#!/bin/sh
# Manage the local multi-voice Qwen3-TTS catalog and LaunchAgent.
set -e

LABEL=local.qwen3-tts.engine
TMPL="$HOME/.config/hermes/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
RUNTIME_DIR="$HOME/.config/hermes/local/qwen3-tts"
MUTATION_LOCK="$RUNTIME_DIR/.mutation.lock"
SERVER="$HOME/.config/hermes/scripts/qwen3_tts_server.py"
CATALOG="$RUNTIME_DIR/catalog.json"
LEGACY_VOICE_MANIFEST="$RUNTIME_DIR/voice.json"
LOCK="$HOME/.config/hermes/qwen3-tts/requirements.lock"
HEALTH_BASE_URL="http://127.0.0.1:10102/health"
PYTHON_VERSION="3.12.11"
RELEASE_SCHEMA="2"
STARTUP_ATTEMPTS="${QWEN3_TTS_STARTUP_ATTEMPTS:-60}"
STARTUP_SLEEP_SECONDS="${QWEN3_TTS_STARTUP_SLEEP_SECONDS:-5}"

ACTION="${1:-install}"
if [ "$#" -gt 0 ]; then
  shift
fi
MANIFEST_SOURCE=""
VOICE_ID=""
SET_DEFAULT=0
LOCK_HELD=0
CANDIDATE_CATALOG=""
TMP_PLIST=""
OLD_CATALOG=""
OLD_PLIST=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --voice-manifest)
      [ "$#" -ge 2 ] || { echo "--voice-manifest requires a path" >&2; exit 1; }
      MANIFEST_SOURCE="$2"
      shift 2
      ;;
    --voice)
      [ "$#" -ge 2 ] || { echo "--voice requires an id" >&2; exit 1; }
      VOICE_ID="$2"
      shift 2
      ;;
    --default)
      SET_DEFAULT=1
      shift
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 1
      ;;
  esac
done

release_mutation_lock() {
  if [ "$LOCK_HELD" -eq 1 ]; then
    OWNER=""
    if [ -f "$MUTATION_LOCK" ] && [ ! -L "$MUTATION_LOCK" ]; then
      IFS= read -r OWNER < "$MUTATION_LOCK" || true
    fi
    if [ "$OWNER" = "$$" ]; then
      rm -f "$MUTATION_LOCK"
    fi
    LOCK_HELD=0
  fi
}

acquire_mutation_lock() {
  if (set -C; printf '%s\n' "$$" > "$MUTATION_LOCK") 2>/dev/null; then
    LOCK_HELD=1
    return 0
  fi
  OWNER=""
  if [ -f "$MUTATION_LOCK" ] && [ ! -L "$MUTATION_LOCK" ]; then
    IFS= read -r OWNER < "$MUTATION_LOCK" || true
  fi
  case "$OWNER" in
    ''|*[!0-9]*)
      echo "Qwen3-TTS mutation lock is invalid or incomplete; verify no mutation is running before removing $MUTATION_LOCK" >&2
      ;;
    *)
      if kill -0 "$OWNER" 2>/dev/null; then
        echo "another Qwen3-TTS catalog mutation is in progress" >&2
      else
        echo "stale Qwen3-TTS mutation lock owned by PID $OWNER; verify no mutation is running before removing $MUTATION_LOCK" >&2
      fi
      ;;
  esac
  return 1
}

finish_mutation() {
  STATUS=$?
  trap - 0 1 2 15
  rm -f "$CANDIDATE_CATALOG" "$TMP_PLIST" "$OLD_CATALOG" "$OLD_PLIST"
  release_mutation_lock
  exit "$STATUS"
}

require_runtime() {
  [ -f "$TMPL" ] || { echo "template not found: $TMPL" >&2; exit 1; }
  [ -f "$SERVER" ] || { echo "server not found: $SERVER" >&2; exit 1; }
  [ -f "$LOCK" ] || { echo "dependency lock not found: $LOCK" >&2; exit 1; }
  command -v uv >/dev/null 2>&1 || { echo "uv not found" >&2; exit 1; }
  mkdir -p "$RUNTIME_DIR" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
}

normalize_manifest_source() {
  [ -n "$MANIFEST_SOURCE" ] || return 0
  case "$MANIFEST_SOURCE" in
    /*) ;;
    *) MANIFEST_SOURCE="$PWD/$MANIFEST_SOURCE" ;;
  esac
  [ -f "$MANIFEST_SOURCE" ] || {
    echo "voice manifest not found: $MANIFEST_SOURCE" >&2
    exit 1
  }
}

prune_inactive_releases() {
  ACTIVE_RELEASE_ID="$1"
  PREVIOUS_RELEASE_ID="$2"
  RELEASES_DIR="$RUNTIME_DIR/releases"
  [ -d "$RELEASES_DIR" ] || return 0
  for RELEASE_PATH in "$RELEASES_DIR"/*; do
    [ -d "$RELEASE_PATH" ] && [ ! -L "$RELEASE_PATH" ] || continue
    CANDIDATE_RELEASE_ID=${RELEASE_PATH##*/}
    case "$CANDIDATE_RELEASE_ID" in
      *[!0-9a-f]*) continue ;;
    esac
    [ "${#CANDIDATE_RELEASE_ID}" -eq 64 ] || continue
    [ "$CANDIDATE_RELEASE_ID" = "$ACTIVE_RELEASE_ID" ] && continue
    [ -n "$PREVIOUS_RELEASE_ID" ] && [ "$CANDIDATE_RELEASE_ID" = "$PREVIOUS_RELEASE_ID" ] && continue
    if ! rm -rf "$RELEASE_PATH"; then
      echo "warning: failed to prune inactive release $CANDIDATE_RELEASE_ID" >&2
    fi
  done
}

deploy_catalog() {
  CANDIDATE_CATALOG="$1"
  python3 "$SERVER" check-catalog "$CANDIDATE_CATALOG"
  LOCK_HASH=$(shasum -a 256 "$LOCK" | cut -d ' ' -f 1)
  SERVER_HASH=$(shasum -a 256 "$SERVER" | cut -d ' ' -f 1)
  RELEASE_ID=$(printf '%s-%s-%s-%s\n' "$RELEASE_SCHEMA" "$PYTHON_VERSION" "$LOCK_HASH" "$SERVER_HASH" | shasum -a 256 | cut -d ' ' -f 1)
  RELEASE_DIR="$RUNTIME_DIR/releases/$RELEASE_ID"
  VENV="$RELEASE_DIR/venv"
  RELEASE_SERVER="$RELEASE_DIR/qwen3_tts_server.py"
  mkdir -p "$RELEASE_DIR"
  if [ ! -f "$RELEASE_SERVER" ]; then
    cp "$SERVER" "$RELEASE_SERVER"
  fi
  cmp -s "$SERVER" "$RELEASE_SERVER" || {
    echo "release server hash mismatch: $RELEASE_SERVER" >&2
    exit 1
  }
  if [ ! -x "$VENV/bin/python" ]; then
    UV_NO_CONFIG=1 uv venv "$VENV" --python "$PYTHON_VERSION" --managed-python
  fi
  [ "$("$VENV/bin/python" --version 2>&1)" = "Python $PYTHON_VERSION" ] || {
    echo "unexpected Qwen3-TTS Python version; expected $PYTHON_VERSION" >&2
    exit 1
  }
  UV_NO_CONFIG=1 uv pip sync --python "$VENV/bin/python" --require-hashes --strict "$LOCK"
  CATALOG_HASH=$("$VENV/bin/python" "$RELEASE_SERVER" check-catalog "$CANDIDATE_CATALOG" --digest)

  TMP_PLIST="$DEST.$$"
  OLD_CATALOG="$RUNTIME_DIR/.previous.$$.catalog.json"
  OLD_PLIST="$RUNTIME_DIR/.previous.$$.plist"
  HOME_ESCAPED=$(printf '%s\n' "$HOME" | sed 's/[&|]/\\&/g')
  PYTHON_ESCAPED=$(printf '%s\n' "$VENV/bin/python" | sed 's/[&|]/\\&/g')
  SERVER_ESCAPED=$(printf '%s\n' "$RELEASE_SERVER" | sed 's/[&|]/\\&/g')
  CATALOG_ESCAPED=$(printf '%s\n' "$CATALOG" | sed 's/[&|]/\\&/g')
  RELEASE_ID_ESCAPED=$(printf '%s\n' "$RELEASE_ID" | sed 's/[&|]/\\&/g')
  sed \
    -e "s|__HOME__|$HOME_ESCAPED|g" \
    -e "s|__PYTHON__|$PYTHON_ESCAPED|g" \
    -e "s|__SERVER__|$SERVER_ESCAPED|g" \
    -e "s|__VOICE_CATALOG__|$CATALOG_ESCAPED|g" \
    -e "s|__RELEASE_ID__|$RELEASE_ID_ESCAPED|g" \
    "$TMPL" > "$TMP_PLIST"
  plutil -lint "$TMP_PLIST" >/dev/null

  HAD_OLD_CATALOG=0
  if [ -f "$CATALOG" ]; then
    HAD_OLD_CATALOG=1
    cp "$CATALOG" "$OLD_CATALOG"
  fi
  HAD_OLD_PLIST=0
  OLD_RELEASE_ID=""
  OLD_RELEASE_ID_VALID=1
  if [ -f "$DEST" ]; then
    HAD_OLD_PLIST=1
    cp "$DEST" "$OLD_PLIST"
    OLD_PYTHON=$(plutil -extract ProgramArguments.0 raw -o - "$OLD_PLIST" 2>/dev/null || true)
    case "$OLD_PYTHON" in
      "$RUNTIME_DIR/releases/"*/venv/bin/python)
        OLD_RELEASE_PATH=${OLD_PYTHON#"$RUNTIME_DIR/releases/"}
        OLD_RELEASE_ID=${OLD_RELEASE_PATH%%/*}
        case "$OLD_RELEASE_ID" in
          *[!0-9a-f]*) OLD_RELEASE_ID_VALID=0 ;;
        esac
        [ "${#OLD_RELEASE_ID}" -eq 64 ] || OLD_RELEASE_ID_VALID=0
        ;;
      *) OLD_RELEASE_ID_VALID=0 ;;
    esac
  fi
  TRANSACTION_ACTIVE=0
  rollback_install() {
    ROLLBACK_STATUS=0
    launchctl unload "$DEST" 2>/dev/null || true
    if [ "$HAD_OLD_CATALOG" -eq 1 ]; then
      cp "$OLD_CATALOG" "$CATALOG"
    else
      rm -f "$CATALOG"
    fi
    if [ "$HAD_OLD_PLIST" -eq 1 ]; then
      cp "$OLD_PLIST" "$DEST"
      if ! launchctl load -w "$DEST"; then
        echo "failed to reload previous $LABEL" >&2
        ROLLBACK_STATUS=1
      fi
    else
      rm -f "$DEST"
    fi
    return "$ROLLBACK_STATUS"
  }

  finish_install() {
    STATUS=$?
    trap - 0 1 2 15
    if [ "$TRANSACTION_ACTIVE" -eq 1 ]; then
      if ! rollback_install; then
        STATUS=2
      fi
    fi
    rm -f "$CANDIDATE_CATALOG" "$TMP_PLIST" "$OLD_CATALOG" "$OLD_PLIST"
    release_mutation_lock
    exit "$STATUS"
  }
  trap finish_install 0
  trap 'exit 130' 1 2 15

  TRANSACTION_ACTIVE=1
  mv -f "$CANDIDATE_CATALOG" "$CATALOG"
  mv -f "$TMP_PLIST" "$DEST"
  launchctl unload "$DEST" 2>/dev/null || true
  if ! launchctl load -w "$DEST"; then
    if ! rollback_install; then
      TRANSACTION_ACTIVE=0
      exit 2
    fi
    TRANSACTION_ACTIVE=0
    echo "failed to load $LABEL; previous voice catalog restored" >&2
    exit 1
  fi

  HEALTH_URL="$HEALTH_BASE_URL?release_id=$RELEASE_ID&catalog_sha256=$CATALOG_HASH"
  READY=0
  ATTEMPT=0
  while [ "$ATTEMPT" -lt "$STARTUP_ATTEMPTS" ]; do
    if curl -fs -m 3 -o /dev/null "$HEALTH_URL"; then
      READY=1
      break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    sleep "$STARTUP_SLEEP_SECONDS"
  done
  if [ "$READY" -ne 1 ]; then
    if ! rollback_install; then
      TRANSACTION_ACTIVE=0
      exit 2
    fi
    TRANSACTION_ACTIVE=0
    echo "failed to start $LABEL; previous release restored" >&2
    exit 1
  fi

  TRANSACTION_ACTIVE=0
  trap - 0 1 2 15
  trap finish_mutation 0
  trap 'exit 130' 1 2 15
  rm -f "$CANDIDATE_CATALOG" "$TMP_PLIST" "$OLD_CATALOG" "$OLD_PLIST"
  if [ -L "$LEGACY_VOICE_MANIFEST" ]; then
    rm -f "$LEGACY_VOICE_MANIFEST"
  fi
  if [ "$OLD_RELEASE_ID_VALID" -eq 1 ]; then
    prune_inactive_releases "$RELEASE_ID" "$OLD_RELEASE_ID"
  else
    echo "warning: previous release could not be identified; inactive releases retained" >&2
  fi
  trap - 0 1 2 15
  release_mutation_lock
  echo "loaded $LABEL ($DEST)"
  echo "registered voice catalog: $CATALOG"
}

case "$ACTION" in
  install|register|unregister)
    require_runtime
    acquire_mutation_lock
    trap finish_mutation 0
    trap 'exit 130' 1 2 15
    normalize_manifest_source
    CANDIDATE_CATALOG="$RUNTIME_DIR/.catalog.$$.json"
    case "$ACTION" in
      install)
        if [ -n "$MANIFEST_SOURCE" ]; then
          if [ -f "$CATALOG" ]; then
            python3 "$SERVER" catalog-register --output "$CANDIDATE_CATALOG" --catalog "$CATALOG" --manifest "$MANIFEST_SOURCE" --default
          else
            python3 "$SERVER" catalog-register --output "$CANDIDATE_CATALOG" --manifest "$MANIFEST_SOURCE" --default
          fi
        elif [ -f "$CATALOG" ]; then
          cp "$CATALOG" "$CANDIDATE_CATALOG"
        elif [ -f "$LEGACY_VOICE_MANIFEST" ]; then
          python3 "$SERVER" catalog-register --output "$CANDIDATE_CATALOG" --manifest "$LEGACY_VOICE_MANIFEST" --default
        else
          echo "voice catalog is empty; pass --voice-manifest PATH" >&2
          exit 1
        fi
        ;;
      register)
        [ -n "$MANIFEST_SOURCE" ] || {
          echo "register requires --voice-manifest PATH" >&2
          exit 1
        }
        if [ -f "$CATALOG" ]; then
          if [ "$SET_DEFAULT" -eq 1 ]; then
            python3 "$SERVER" catalog-register --output "$CANDIDATE_CATALOG" --catalog "$CATALOG" --manifest "$MANIFEST_SOURCE" --default
          else
            python3 "$SERVER" catalog-register --output "$CANDIDATE_CATALOG" --catalog "$CATALOG" --manifest "$MANIFEST_SOURCE"
          fi
        else
          python3 "$SERVER" catalog-register --output "$CANDIDATE_CATALOG" --manifest "$MANIFEST_SOURCE" --default
        fi
        ;;
      unregister)
        [ -n "$VOICE_ID" ] || {
          echo "unregister requires --voice ID" >&2
          exit 1
        }
        [ -f "$CATALOG" ] || {
          echo "voice catalog is not registered" >&2
          exit 1
        }
        python3 "$SERVER" catalog-unregister --output "$CANDIDATE_CATALOG" --catalog "$CATALOG" --voice "$VOICE_ID"
        ;;
    esac
    deploy_catalog "$CANDIDATE_CATALOG"
    ;;
  voices)
    [ -f "$CATALOG" ] || { echo "voice catalog is not registered" >&2; exit 1; }
    python3 "$SERVER" catalog-list "$CATALOG"
    ;;
  uninstall)
    mkdir -p "$RUNTIME_DIR"
    acquire_mutation_lock
    trap finish_mutation 0
    trap 'exit 130' 1 2 15
    launchctl unload -w "$DEST" 2>/dev/null || true
    rm -f "$DEST"
    trap - 0 1 2 15
    release_mutation_lock
    echo "unloaded + removed $LABEL (catalog, model cache, and venv retained)"
    ;;
  status)
    launchctl list | grep "$LABEL" || echo "$LABEL not loaded"
    echo "--- engine health ---"
    curl -s -m 3 "$HEALTH_BASE_URL" || echo "engine not ready on :10102"
    echo
    lsof -nP -iTCP:10102 -sTCP:LISTEN +c 0 2>/dev/null | grep LISTEN || true
    ;;
  *)
    echo "usage: $0 install [--voice-manifest PATH] | register --voice-manifest PATH [--default] | unregister --voice ID | voices | status | uninstall" >&2
    exit 1
    ;;
esac
