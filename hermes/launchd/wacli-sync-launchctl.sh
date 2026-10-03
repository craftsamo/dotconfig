#!/usr/bin/env bash
# LaunchAgent manager for wacli sync, one agent per named wacli account.
#
# The whatsapp-access plugin reads each account's local mirror (~/.wacli/accounts/<name>)
# and sends through the running sync's store socket; this keeps that sync alive.
# Phone numbers never enter tracked files: pairing takes the number on the command
# line and wacli keeps the session in its own store.
#
#   pair      ACCOUNT +NUMBER   pair by phone code (adds the account if needed; the code
#                               is entered on the phone under Linked devices > Link with
#                               phone number), then install. Refuses an account that is
#                               still paired; a revoked one has its dead session moved
#                               aside first (the message mirror stays)
#   install   ACCOUNT           render, load and start the agent (account must be paired)
#   uninstall ACCOUNT           stop and remove the agent (the pairing stays)
#   restart   ACCOUNT           reload the agent (after a wacli upgrade)
#   status    [ACCOUNT]         agent state and wacli doctor, for one or every account
#
# Unpairing is `wacli --account ACCOUNT auth logout` after `uninstall`.
set -euo pipefail

CONFIG_DIR="$HOME/.config/hermes"
TMPL="$CONFIG_DIR/launchd/local.wacli.sync.plist.tmpl"

die() { echo "error: $*" >&2; exit 1; }

ACTION="${1:-}"
ACCOUNT="${2:-}"
PHONE="${3:-}"

WACLI="$(command -v wacli || true)"
[ -n "$WACLI" ] || die "wacli is not on PATH (brew install openclaw/tap/wacli)"

check_account() {
  [ -n "$ACCOUNT" ] || die "$ACTION needs an ACCOUNT name"
  case "$ACCOUNT" in
    [A-Za-z0-9]*) ;;
    *) die "account names start with a letter or digit: $ACCOUNT" ;;
  esac
  case "$ACCOUNT" in
    *[!A-Za-z0-9._-]*) die "account names use [A-Za-z0-9._-]: $ACCOUNT" ;;
  esac
}

label() { echo "local.wacli.sync.$1"; }
dest() { echo "$HOME/Library/LaunchAgents/$(label "$1").plist"; }

known_accounts() {
  "$WACLI" --read-only --json accounts list 2>/dev/null \
    | /usr/bin/plutil -extract data.accounts json -o - - 2>/dev/null \
    | /usr/bin/grep -o '"name":"[^"]*"' | /usr/bin/sed 's/"name":"\(.*\)"/\1/' || true
}

has_account() { known_accounts | /usr/bin/grep -Fqx "$1"; }

paired() {
  "$WACLI" --account "$1" --read-only --json auth status 2>/dev/null | /usr/bin/grep -q '"authenticated":true'
}

revoked() {
  "$WACLI" --account "$1" --read-only --json doctor 2>/dev/null | /usr/bin/grep -q '"session_revoked":true'
}

store_dir() {
  "$WACLI" --account "$1" --read-only --json doctor 2>/dev/null \
    | /usr/bin/sed -n 's/.*"store_dir":"\([^"]*\)".*/\1/p'
}

# WhatsApp revoked the link: wacli keeps the dead device record (and `auth logout` cannot
# connect to clear it), so phone pairing would be skipped. Move the session database aside,
# keeping the message mirror (wacli.db); the old file stays for inspection.
reset_revoked_session() {
  local dir stamp f
  dir="$(store_dir "$1")"
  [ -n "$dir" ] && [ -d "$dir" ] || die "cannot find the store of '$1'"
  stamp="$(date +%Y%m%d%H%M%S)"
  for f in session.db session.db-wal session.db-shm; do
    [ -e "$dir/$f" ] && mv "$dir/$f" "$dir/$f.revoked-$stamp"
  done
  echo "moved the revoked session of '$1' aside ($dir/session.db.revoked-$stamp)"
}

unload_agent() {
  launchctl bootout "gui/$UID/$(label "$1")" 2>/dev/null || true
  # bootout returns before the job is gone; bootstrapping into that window fails.
  local i
  for i in $(seq 1 50); do
    launchctl print "gui/$UID/$(label "$1")" >/dev/null 2>&1 || return 0
    sleep 0.2
  done
  echo "warning: $(label "$1") still present after bootout" >&2
}

load_agent() {
  local i
  for i in 1 2 3; do
    if launchctl bootstrap "gui/$UID" "$(dest "$1")" 2>/dev/null; then
      launchctl enable "gui/$UID/$(label "$1")" 2>/dev/null || true
      return 0
    fi
    sleep 1
  done
  die "launchctl bootstrap failed for $(dest "$1")"
}

render_plist() {
  [ -f "$TMPL" ] || die "missing template: $TMPL"
  local tmp
  tmp="$(mktemp)"
  sed -e "s|__WACLI__|$WACLI|g" -e "s|__ACCOUNT__|$1|g" -e "s|__HOME__|$HOME|g" "$TMPL" > "$tmp"
  plutil -lint "$tmp" >/dev/null || { rm -f "$tmp"; die "rendered plist is invalid"; }
  mkdir -p "$(dirname "$(dest "$1")")"
  mv "$tmp" "$(dest "$1")"
}

install_agent() {
  has_account "$1" || die "no wacli account '$1' (pair it first: $0 pair $1 +NUMBER)"
  paired "$1" || die "account '$1' is not paired (run: $0 pair $1 +NUMBER)"
  render_plist "$1"
  unload_agent "$1"
  load_agent "$1"
  echo "loaded $(label "$1"); log: $HOME/Library/Logs/wacli-sync-$1.log"
}

show_status() {
  local name="$1"
  echo "== $name"
  echo "plist   : $(dest "$name") $([ -f "$(dest "$name")" ] && echo '(installed)' || echo '(absent)')"
  if launchctl print "gui/$UID/$(label "$name")" >"/tmp/.wacli-print.$$" 2>/dev/null; then
    grep -E '^[[:space:]]+(state|pid|last exit code) = ' "/tmp/.wacli-print.$$" \
      | head -3 | sed 's/^[[:space:]]*/  /'
  else
    echo "  not loaded"
  fi
  rm -f "/tmp/.wacli-print.$$"
  "$WACLI" --account "$name" --read-only doctor 2>&1 | sed 's/^/  /'
}

case "$ACTION" in
  pair)
    check_account
    case "$PHONE" in
      +[0-9]*) ;;
      *) die "pair needs the number in international form: $0 pair $ACCOUNT +819012345678" ;;
    esac
    if has_account "$ACCOUNT"; then
      if revoked "$ACCOUNT"; then
        unload_agent "$ACCOUNT"
        reset_revoked_session "$ACCOUNT"
      elif paired "$ACCOUNT"; then
        die "'$ACCOUNT' is already paired; to link it again, run uninstall, then
       wacli --account $ACCOUNT auth logout, then pair"
      fi
      unload_agent "$ACCOUNT"
      "$WACLI" --account "$ACCOUNT" auth --phone "$PHONE"
    else
      "$WACLI" accounts add "$ACCOUNT" --phone "$PHONE"
    fi
    install_agent "$ACCOUNT"
    ;;
  install)
    check_account
    install_agent "$ACCOUNT"
    ;;
  uninstall)
    check_account
    unload_agent "$ACCOUNT"
    rm -f "$(dest "$ACCOUNT")"
    echo "unloaded and removed $(dest "$ACCOUNT")"
    ;;
  restart)
    check_account
    [ -f "$(dest "$ACCOUNT")" ] || die "not installed: $(dest "$ACCOUNT")"
    unload_agent "$ACCOUNT"
    load_agent "$ACCOUNT"
    echo "reloaded $(label "$ACCOUNT")"
    ;;
  status)
    if [ -n "$ACCOUNT" ]; then
      check_account
      show_status "$ACCOUNT"
    else
      names="$(known_accounts)"
      [ -n "$names" ] || { echo "no wacli accounts"; exit 0; }
      while IFS= read -r name; do show_status "$name"; done <<< "$names"
    fi
    ;;
  *)
    die "usage: $0 pair ACCOUNT +NUMBER | install ACCOUNT | uninstall ACCOUNT | restart ACCOUNT | status [ACCOUNT]"
    ;;
esac
