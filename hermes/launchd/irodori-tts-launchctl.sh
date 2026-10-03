#!/usr/bin/env bash
# LaunchAgent manager for the local Irodori-TTS engine (127.0.0.1:10103).
#
# Coexists with qwen3-tts on :10102. Both are loopback-only and need no API key;
# the Hermes tts-fallback chain picks between them, with irodori-tts declining
# English-dominant text so it lands on qwen3-tts.
#
# Everything mutable lives under hermes/local/irodori-tts/, which is gitignored:
# the server checkout, its uv venv, the Hugging Face cache and the voice files.
# Voice audio is private, so it is copied in by `register` and its source path
# never enters tracked config.
#
# One --voice registers voices/<id>.wav. Several register one voice made of
# all of them: the clips are copied to voices/<id>/01.wav, 02.wav, ... in the
# given order and grouped under <id> in voices/voices.json, because the server
# lists every top-level file as its own voice and only an alias groups clips.
# Re-registering an id in either shape replaces the other shape.
#
#   install  [--voice PATH --id NAME [--default]]   build/refresh and load
#   register --voice PATH [--voice PATH ...] --id NAME [--default]
#                                                   add or replace a reference voice
#   unregister --id NAME                            remove a voice (never the default)
#   restart                                         reload the voice catalog
#   (register/unregister take --no-restart so a batch restarts once)
#   register-lexicon --file PATH                    install the pronunciation dict
#   voices                                          list registered voices
#   status                                          plist + health + model state
#   uninstall                                       stop and unload (KeepAlive)
#   purge                                           uninstall + delete runtime
#
# The pronunciation lexicon rewrites Latin proper nouns to katakana before
# synthesis. It is DATA and tends to accumulate names its owner would rather
# not publish, so like the voice audio it is copied into the gitignored runtime
# directory and its source path never enters tracked config. Shape:
#
#   { "terms": { "Terraform": "テラフォーム", "Claude Code": "クロードコード" } }
#
# Longest key wins, and ASCII keys match on word boundaries.
set -euo pipefail

LABEL=local.irodori-tts.engine
CONFIG_DIR="$HOME/.config/hermes"
TMPL="$CONFIG_DIR/launchd/$LABEL.plist.tmpl"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
RUNTIME_DIR="$CONFIG_DIR/local/irodori-tts"
SERVER_DIR="$RUNTIME_DIR/server"
VOICES_DIR="$RUNTIME_DIR/voices"
PINNED="$CONFIG_DIR/engines/irodori-tts/pinned.conf"
LOG="$HOME/Library/Logs/irodori-tts-engine.log"

# 120 x 5 s matches IRODORI_MODEL_LOAD_TIMEOUT below: a first install downloads
# the 12 GB checkpoint inside that window, and a shorter wait reports failure
# while the engine is still loading.
STARTUP_ATTEMPTS="${IRODORI_TTS_STARTUP_ATTEMPTS:-120}"
STARTUP_SLEEP="${IRODORI_TTS_STARTUP_SLEEP_SECONDS:-5}"

ACTION="${1:-install}"
shift || true

# Bash 3.2 (macOS /bin/bash) treats "${a[@]}" of an empty array as unbound
# under set -u, so every expansion of VOICE_SRCS checks VOICE_COUNT first.
VOICE_SRCS=()
VOICE_COUNT=0
VOICE_ID=""
LEXICON_SRC=""
SET_DEFAULT=0
RESTART=1
while [ $# -gt 0 ]; do
  case "$1" in
    --voice) VOICE_SRCS+=("${2:-}"); VOICE_COUNT=$((VOICE_COUNT + 1)); shift 2 ;;
    --id) VOICE_ID="${2:-}"; shift 2 ;;
    --file) LEXICON_SRC="${2:-}"; shift 2 ;;
    --default) SET_DEFAULT=1; shift ;;
    --no-restart) RESTART=0; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

[ -f "$PINNED" ] || die "missing pin file: $PINNED"
# shellcheck disable=SC1090
. "$PINNED"

: "${IRODORI_SERVER_REPO:?}" "${IRODORI_SERVER_REV:?}" "${IRODORI_BACKEND_EXTRA:?}"
: "${IRODORI_PYTHON_VERSION:?}"
: "${IRODORI_PORT:?}" "${IRODORI_HF_CHECKPOINT:?}" "${IRODORI_CODEC_REPO:?}"
: "${IRODORI_MODEL_DEVICE:?}" "${IRODORI_CODEC_DEVICE:?}" "${IRODORI_PRECISION:?}"

HEALTH="http://127.0.0.1:$IRODORI_PORT/health"
VENV_PYTHON="$SERVER_DIR/.venv/bin/python"

need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required but not on PATH"; }

# ---------------------------------------------------------------- voices ----

check_voice_id() {
  # An empty id passes the character-class test below (the pattern cannot match
  # an empty string), which would register a hidden ".wav" and leave the default
  # voice blank while still reporting success.
  [ -n "${VOICE_ID:-}" ] || die "$1 needs a non-empty --id NAME"
  case "$VOICE_ID" in
    *[!A-Za-z0-9_-]*) die "voice id must be [A-Za-z0-9_-]: $VOICE_ID" ;;
  esac
}

# voices.json is derived, never edited: one alias per voices/<id>/ directory,
# listing its clips in name order. Ids are [A-Za-z0-9_-] and clips NN.wav, so
# nothing needs JSON escaping, and no interpreter is needed (python3 on PATH
# may be a Keychain shim). With no group left the file is removed, so a
# single-clip install keeps the plain one-file-per-voice layout.
is_group() {
  # A group is a voices/<id>/ directory with a valid id and at least one clip;
  # anything else is ignored rather than turned into a broken alias.
  local dir="$1" clip
  [ -d "$dir" ] || return 1
  case "$(basename "$dir")" in
    ""|*[!A-Za-z0-9_-]*) return 1 ;;
  esac
  for clip in "$dir"*.wav; do
    [ -f "$clip" ] && return 0
  done
  return 1
}

write_aliases() {
  local dir clip voice_id sep_voice sep_clip tmp
  tmp="$VOICES_DIR/.voices.json.partial"
  sep_voice=""
  {
    printf '{'
    for dir in "$VOICES_DIR"/*/; do
      is_group "$dir" || continue
      voice_id="$(basename "$dir")"
      printf '%s\n  "%s": {"ref_wavs": [' "$sep_voice" "$voice_id"
      sep_clip=""
      for clip in "$dir"*.wav; do
        [ -f "$clip" ] || continue
        printf '%s"%s/%s"' "$sep_clip" "$voice_id" "$(basename "$clip")"
        sep_clip=", "
      done
      printf ']}'
      sep_voice=","
    done
    printf '\n}\n'
  } > "$tmp"
  if [ -n "$sep_voice" ]; then
    mv "$tmp" "$VOICES_DIR/voices.json"
  else
    rm -f "$tmp" "$VOICES_DIR/voices.json"
  fi
}

register_voice() {
  [ "$VOICE_COUNT" -gt 0 ] || die "register needs --voice PATH"
  check_voice_id register
  local src i staging
  for src in "${VOICE_SRCS[@]}"; do
    [ -f "$src" ] || die "voice file not found: $src"
  done

  mkdir -p "$VOICES_DIR"
  # Copied, not linked: the source lives in a private tree and the engine must
  # keep working if that tree moves.
  if [ "$VOICE_COUNT" -eq 1 ]; then
    cp "${VOICE_SRCS[0]}" "$VOICES_DIR/$VOICE_ID.wav"
    rm -rf "${VOICES_DIR:?}/$VOICE_ID"
    echo "registered voice '$VOICE_ID'"
  else
    # Staged beside the target (ids cannot contain a dot, so no collision) and
    # swapped in whole, so a failed copy never leaves a half-replaced voice.
    staging="$VOICES_DIR/.$VOICE_ID.partial"
    rm -rf "$staging"
    mkdir -p "$staging"
    i=0
    for src in "${VOICE_SRCS[@]}"; do
      i=$((i + 1))
      cp "$src" "$staging/$(printf '%02d.wav' "$i")"
    done
    rm -rf "${VOICES_DIR:?}/$VOICE_ID"
    mv "$staging" "$VOICES_DIR/$VOICE_ID"
    rm -f "$VOICES_DIR/$VOICE_ID.wav"
    echo "registered voice '$VOICE_ID' ($VOICE_COUNT clips)"
  fi
  write_aliases

  if [ "$SET_DEFAULT" -eq 1 ]; then
    printf '%s\n' "$VOICE_ID" > "$RUNTIME_DIR/default-voice"
    echo "default voice is now '$VOICE_ID'"
  fi
}

unregister_voice() {
  check_voice_id unregister
  [ -f "$VOICES_DIR/$VOICE_ID.wav" ] || [ -d "$VOICES_DIR/$VOICE_ID" ] \
    || die "voice '$VOICE_ID' is not registered"
  # Removing the default would silently move every unnamed request to whichever
  # voice sorts first; make the change explicit by registering a new default.
  [ "$(default_voice || true)" != "$VOICE_ID" ] \
    || die "'$VOICE_ID' is the default voice; register another voice with --default first"
  rm -rf "${VOICES_DIR:?}/$VOICE_ID"
  rm -f "$VOICES_DIR/$VOICE_ID.wav"
  write_aliases
  echo "unregistered voice '$VOICE_ID'"
}

# Every registered voice id: single-file voices plus multi-clip groups.
registered_ids() {
  local f
  for f in "$VOICES_DIR"/*.wav; do
    [ -f "$f" ] && basename "$f" .wav
  done
  for f in "$VOICES_DIR"/*/; do
    if is_group "$f"; then basename "$f"; fi
  done
  return 0
}

restart_agent() {
  write_env
  if [ -f "$DEST" ]; then
    # The voice catalog is read at startup, so a changed voice needs a restart.
    unload_agent
    load_agent
    wait_healthy || true
  fi
}

register_lexicon() {
  [ -n "${LEXICON_SRC:-}" ] || die "register-lexicon needs --file PATH"
  [ -f "$LEXICON_SRC" ] || die "lexicon file not found: $LEXICON_SRC"
  need python3
  # Validated before install so a typo cannot silently disable substitution:
  # the plugin treats an unreadable lexicon as "no lexicon" and carries on.
  python3 - "$LEXICON_SRC" <<'PY' || die "lexicon is not valid: $LEXICON_SRC"
import json, sys
raw = json.load(open(sys.argv[1], encoding="utf-8"))
terms = raw.get("terms") if isinstance(raw, dict) else None
if not isinstance(terms, dict) or not terms:
    sys.exit('expected a non-empty {"terms": {...}} object')
bad = [k for k, v in terms.items() if not isinstance(k, str) or not isinstance(v, str) or not k]
if bad:
    sys.exit(f"non-string or empty keys: {bad[:5]}")
print(f"  {len(terms)} term(s) validated")
PY
  mkdir -p "$RUNTIME_DIR"
  # A symlink here means an overlay owns the file (the private-dotconfig
  # install.sh links its master in). `cp` would follow the link and silently
  # rewrite that master, so refuse and point at it instead.
  if [ -L "$RUNTIME_DIR/lexicon.json" ]; then
    die "$RUNTIME_DIR/lexicon.json is a symlink to
       $(readlink "$RUNTIME_DIR/lexicon.json")
       An overlay owns it. Edit that file directly, or remove the link first."
  fi
  cp "$LEXICON_SRC" "$RUNTIME_DIR/lexicon.json"
  echo "installed lexicon -> $RUNTIME_DIR/lexicon.json"
  echo "note: the plugin caches it per process; restart the gateway to apply."
}

default_voice() {
  if [ -f "$RUNTIME_DIR/default-voice" ]; then
    head -n 1 "$RUNTIME_DIR/default-voice"
  else
    # First registered voice, so a single-voice install needs no extra step.
    registered_ids | LC_ALL=C sort -u | head -n 1
  fi
}

# ---------------------------------------------------------------- build -----

sync_server() {
  need git
  need uv
  mkdir -p "$RUNTIME_DIR" "$VOICES_DIR" "$RUNTIME_DIR/cache"

  if [ ! -d "$SERVER_DIR/.git" ]; then
    echo "cloning $IRODORI_SERVER_REPO"
    git clone --quiet "$IRODORI_SERVER_REPO" "$SERVER_DIR"
  fi
  git -C "$SERVER_DIR" fetch --quiet origin
  git -C "$SERVER_DIR" checkout --quiet --detach "$IRODORI_SERVER_REV"
  echo "server pinned at $IRODORI_SERVER_REV"

  # --frozen keeps uv on the committed uv.lock, so the pin above fixes the whole
  # dependency graph including the git-sourced irodori-tts package.
  #
  # --python is not optional. Left to itself uv takes the default interpreter,
  # and on 3.12 the pinned sentencepiece 0.1.99 has no wheel, so uv falls back to
  # building it from source and dies in build_bundled.sh. 3.10 has wheels for the
  # whole graph and matches upstream's .python-version.
  ( cd "$SERVER_DIR" \
    && UV_NO_CONFIG=1 uv sync --frozen \
         --python "$IRODORI_PYTHON_VERSION" \
         --extra "$IRODORI_BACKEND_EXTRA" )
  [ -x "$VENV_PYTHON" ] || die "uv sync did not produce $VENV_PYTHON"
  local got
  got="$("$VENV_PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  [ "$got" = "$IRODORI_PYTHON_VERSION" ] \
    || die "venv is Python $got, expected $IRODORI_PYTHON_VERSION"
}

write_env() {
  local voice
  voice="$(default_voice || true)"
  {
    echo "# Rendered by irodori-tts-launchctl.sh -- edit pinned.conf instead."
    echo "IRODORI_HOST=127.0.0.1"
    echo "IRODORI_PORT=$IRODORI_PORT"
    echo "IRODORI_HF_CHECKPOINT=$IRODORI_HF_CHECKPOINT"
    echo "IRODORI_CODEC_REPO=$IRODORI_CODEC_REPO"
    echo "IRODORI_MODEL_NAME=irodori-tts"
    echo "IRODORI_MODEL_DEVICE=$IRODORI_MODEL_DEVICE"
    echo "IRODORI_CODEC_DEVICE=$IRODORI_CODEC_DEVICE"
    echo "IRODORI_MODEL_PRECISION=$IRODORI_PRECISION"
    echo "IRODORI_CODEC_PRECISION=$IRODORI_PRECISION"
    echo "IRODORI_COMPILE_MODEL=false"
    echo "IRODORI_COMPILE_DYNAMIC=false"
    # Load at startup so a failure shows up in the log immediately instead of
    # stalling the first reply that needs speech.
    echo "IRODORI_PRELOAD=true"
    echo "IRODORI_MODEL_LOAD_TIMEOUT=600"
    echo "IRODORI_MAX_CONCURRENT_SYNTHESIS=1"
    echo "IRODORI_SYNTHESIS_WAIT_TIMEOUT=600"
    echo "IRODORI_VOICES_DIR=$VOICES_DIR"
    [ -n "$voice" ] && echo "IRODORI_DEFAULT_VOICE=$voice"
    echo "IRODORI_ALLOW_NO_REF_VOICE=true"
    echo "IRODORI_DEFAULT_RESPONSE_FORMAT=wav"
    echo "IRODORI_DEFAULT_CHUNKING_ENABLED=true"
    echo "IRODORI_DEFAULT_CHUNK_MIN_CHARS=80"
  } > "$SERVER_DIR/.env"
  echo "wrote $SERVER_DIR/.env (default voice: ${voice:-none})"
}

render_plist() {
  [ -f "$TMPL" ] || die "missing template: $TMPL"
  local tmp
  tmp="$(mktemp)"
  sed -e "s|__PYTHON__|$VENV_PYTHON|g" \
      -e "s|__SERVER_DIR__|$SERVER_DIR|g" \
      -e "s|__RUNTIME_DIR__|$RUNTIME_DIR|g" \
      -e "s|__PORT__|$IRODORI_PORT|g" \
      -e "s|__HOME__|$HOME|g" \
      "$TMPL" > "$tmp"
  plutil -lint "$tmp" >/dev/null || { rm -f "$tmp"; die "rendered plist is invalid"; }
  mkdir -p "$(dirname "$DEST")"
  mv "$tmp" "$DEST"
}

unload_agent() {
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
  # bootout returns before the job is actually gone. Bootstrapping into that
  # window fails with "Input/output error 5" and leaves the engine down, so
  # wait for the label to disappear from the domain first.
  local i
  for i in $(seq 1 50); do
    launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1 || return 0
    sleep 0.2
  done
  echo "warning: $LABEL still present after bootout" >&2
}

load_agent() {
  local i
  for i in 1 2 3; do
    if launchctl bootstrap "gui/$UID" "$DEST" 2>/dev/null; then
      launchctl enable "gui/$UID/$LABEL" 2>/dev/null || true
      return 0
    fi
    sleep 1
  done
  die "launchctl bootstrap failed for $DEST"
}

wait_healthy() {
  local i
  for i in $(seq 1 "$STARTUP_ATTEMPTS"); do
    if curl -fsS -m 3 "$HEALTH" 2>/dev/null | grep -q '"loaded": *true'; then
      echo "engine ready after $(( i * STARTUP_SLEEP ))s"
      return 0
    fi
    sleep "$STARTUP_SLEEP"
  done
  echo "warning: engine did not report loaded within $(( STARTUP_ATTEMPTS * STARTUP_SLEEP ))s" >&2
  echo "         check $LOG" >&2
  return 1
}

# ---------------------------------------------------------------- actions ---

case "$ACTION" in
  install)
    if [ "$VOICE_COUNT" -gt 0 ]; then register_voice; fi
    sync_server
    write_env
    render_plist
    unload_agent
    load_agent
    wait_healthy || true
    ;;

  register-lexicon)
    register_lexicon
    ;;

  register)
    register_voice
    if [ "$RESTART" -eq 1 ]; then restart_agent; fi
    ;;

  unregister)
    unregister_voice
    if [ "$RESTART" -eq 1 ]; then restart_agent; fi
    ;;

  restart)
    restart_agent
    ;;

  voices)
    if curl -fsS -m 5 "http://127.0.0.1:$IRODORI_PORT/v1/audio/voices" 2>/dev/null; then
      echo
    else
      echo "engine not reachable; registered voices:"
      registered_ids | LC_ALL=C sort -u | sed "s/^/  /" | grep . || echo "  (none)"
    fi
    ;;

  status)
    echo "label     : $LABEL"
    echo "plist     : $DEST $([ -f "$DEST" ] && echo '(installed)' || echo '(absent)')"
    echo "server    : $SERVER_DIR"
    if [ -d "$SERVER_DIR/.git" ]; then
      echo "revision  : $(git -C "$SERVER_DIR" rev-parse HEAD) (pinned $IRODORI_SERVER_REV)"
    fi
    echo "default   : $(default_voice || echo none)"
    if launchctl print "gui/$UID/$LABEL" >/tmp/.irodori-print.$$ 2>/dev/null; then
      grep -E '^[[:space:]]+(state|pid|last exit code) = ' /tmp/.irodori-print.$$ \
        | head -3 | sed 's/^[[:space:]]*/  /'
    else
      echo "  not loaded"
    fi
    rm -f /tmp/.irodori-print.$$
    echo "health    :"
    curl -fsS -m 5 "$HEALTH" 2>/dev/null || echo "  unreachable"
    echo
    ;;

  uninstall)
    unload_agent
    rm -f "$DEST"
    echo "unloaded and removed $DEST"
    ;;

  purge)
    unload_agent
    rm -f "$DEST"
    rm -rf "$RUNTIME_DIR"
    echo "unloaded and deleted $RUNTIME_DIR"
    ;;

  *)
    die "unknown action '$ACTION' (install|register|unregister|restart|register-lexicon|voices|status|uninstall|purge)"
    ;;
esac
