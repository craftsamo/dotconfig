#!/usr/bin/env zsh
# Self-test for conf.d/opencode-pair.zsh (the `opencode pair` wrapper).
#
# Safe to run anywhere: `opencode` and `tailscale` are fakes in a temp dir, so
# the real OpenCode service and Tailscale are never touched.
#
#   zsh -f zsh/tests/opencode-pair-selftest.zsh
#   OPENCODE_PAIR_UNDER_TEST=<file> zsh -f ...   (another copy of the wrapper)
emulate -L zsh
setopt pipefail
SRC=${OPENCODE_PAIR_UNDER_TEST:-${0:A:h}/../conf.d/opencode-pair.zsh}
JQ=${commands[jq]}

typeset -i fails=0
ok()  { print -r -- "ok   - $1"; }
bad() { print -r -- "FAIL - $1"; (( fails++ )); }

TD=$(mktemp -d)
cleanup() { rm -rf "$TD"; }
trap cleanup EXIT

# --- fixtures -------------------------------------------------------------
mkdir -p "$TD/bin" "$TD/bin-nots"
cat > "$TD/bin/opencode" <<'EOF'
#!/bin/sh
if [ "$1 $2" = "service status" ]; then
  echo "${FAKE_SERVER:-http://127.0.0.1:49374}"
else
  printf '%s\n' "$@"
fi
exit "${FAKE_RC:-0}"
EOF
cat > "$TD/bin/tailscale" <<'EOF'
#!/bin/sh
if [ "$1 $2 $3" = "serve status --json" ]; then
  [ -n "$FAKE_TS_JSON" ] && cat "$FAKE_TS_JSON"
  exit "${FAKE_TS_RC:-0}"
fi
exit 1
EOF
cp "$TD/bin/opencode" "$TD/bin-nots/opencode"
chmod +x "$TD/bin/opencode" "$TD/bin/tailscale" "$TD/bin-nots/opencode"
ln -s "$JQ" "$TD/bin/jq"
ln -s "$JQ" "$TD/bin-nots/jq"

route() {                      # $1 file name, $2 json -> FAKE_TS_JSON path
  print -r -- "$2" > "$TD/$1.json"
  print -r -- "$TD/$1.json"
}
J443=$(route r443 '{"TCP":{"443":{"HTTPS":true}},"Web":{"host.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:49374"}}}}}')
J8443=$(route r8443 '{"TCP":{"8443":{"HTTPS":true}},"Web":{"host.ts.net:8443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:49374"}}}}}')
JLOCAL=$(route rlocal '{"TCP":{"443":{"HTTPS":true}},"Web":{"host.ts.net:443":{"Handlers":{"/":{"Proxy":"http://localhost:49374/"}}}}}')
JOTHER=$(route rother '{"TCP":{"443":{"HTTPS":true}},"Web":{"host.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:3000"}}}}}')
JEMPTY=$(route rempty '{}')
JODD=$(route rodd '{"TCP":{"443":{"HTTPS":true}},"Web":{"no-port":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:49374"}}},"host.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:49374"}}}}}')

# run DIR JSON ARGS...: stdout -> $OUT, stderr -> $ERR, status -> $RC
run() {
  local dir=$1 json=$2; shift 2
  OUT=$( ( path=("$TD/$dir" /usr/bin /bin); rehash
           source "$SRC"
           FAKE_TS_JSON=$json opencode "$@" 2>"$TD/err" ) )
  RC=$?
  ERR=$(<"$TD/err")
}
L=$'\n'
NOROUTE='no Tailscale Serve route'   # fallback notice the wrapper prints

run bin $J443 pair
[[ $OUT == "pair${L}--url${L}https://host.ts.net" ]] \
  && ok "pair: route on 443 adds --url" || bad "pair: route on 443 adds --url ($OUT)"

run bin $J443 pair --name 'a b' -x
[[ $OUT == "pair${L}--url${L}https://host.ts.net${L}--name${L}a b${L}-x" ]] \
  && ok "pair: extra args kept verbatim after the url" || bad "pair: extra args kept verbatim after the url ($OUT)"

for a in '--url x' --url=x --remote --help; do
  run bin $J443 pair ${=a}
  [[ $OUT == "pair${L}${a// /$L}" ]] \
    && ok "pair: $a passed through unchanged" || bad "pair: $a passed through unchanged ($OUT)"
done

run bin $J8443 pair
[[ $OUT == "pair${L}--url${L}https://host.ts.net:8443" ]] \
  && ok "pair: non-default port kept" || bad "pair: non-default port kept ($OUT)"

run bin $JLOCAL pair
[[ $OUT == "pair${L}--url${L}https://host.ts.net" ]] \
  && ok "pair: localhost proxy with trailing slash matches" || bad "pair: localhost proxy with trailing slash matches ($OUT)"

run bin $JOTHER pair
[[ $OUT == pair && $ERR == *"$NOROUTE"* ]] \
  && ok "pair: route to another port falls back" || bad "pair: route to another port falls back ($OUT / $ERR)"

run bin-nots $J443 pair
[[ $OUT == pair && $ERR == *"$NOROUTE"* ]] \
  && ok "pair: tailscale absent falls back" || bad "pair: tailscale absent falls back ($OUT / $ERR)"

FAKE_TS_RC=1 run bin $J443 pair
[[ $OUT == pair && $ERR == *"$NOROUTE"* ]] \
  && ok "pair: failing tailscale falls back" || bad "pair: failing tailscale falls back ($OUT / $ERR)"

run bin $JEMPTY pair
[[ $OUT == pair && $ERR == *"$NOROUTE"* ]] \
  && ok "pair: empty serve config falls back" || bad "pair: empty serve config falls back ($OUT / $ERR)"

run bin $JODD pair
[[ $OUT == "pair${L}--url${L}https://host.ts.net" ]] \
  && ok "pair: an unparsable Serve entry is skipped" || bad "pair: an unparsable Serve entry is skipped ($OUT)"

run bin $J443 run 'a b'
[[ $OUT == "run${L}a b" && -z $ERR ]] \
  && ok "other commands pass through verbatim" || bad "other commands pass through verbatim ($OUT / $ERR)"

FAKE_RC=3 run bin $J443 pair
(( RC == 3 )) && ok "exit status passes through (pair)" || bad "exit status passes through (pair): $RC"
FAKE_RC=3 run bin $J443 run x
(( RC == 3 )) && ok "exit status passes through (other)" || bad "exit status passes through (other): $RC"

print ''
if (( fails == 0 )); then
  print -r -- "ALL TESTS PASSED"
else
  print -r -- "$fails TEST(S) FAILED"
fi
exit $fails
