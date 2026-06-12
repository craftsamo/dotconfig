#!/usr/bin/env zsh
# Self-test for bin/secret-shim (tool/project modes, dotenv precedence).
#
# Safe to run on a machine with real data:
#   - only touches throwaway "secret-selftest*" projects/keychains
#   - the master-password machinery is isolated via SECRET_MASTER_ACCOUNT
#     and SECRET_TEST_ONLY_KC, so the real master item and real keychains
#     are never read, rotated or adopted
#   - cleans up after itself (trap on EXIT)
#
#   zsh -f ~/.config/zsh/tests/secret-shim-selftest.zsh
emulate -L zsh
setopt pipefail
source "$HOME/.config/zsh/functions/secret.zsh"

typeset -i fails=0
ok()  { print -r -- "ok   - $1"; }
bad() { print -r -- "FAIL - $1"; (( fails++ )); }

# every project/keychain name used below must match this glob
export SECRET_MASTER_ACCOUNT=master-selftest
export SECRET_TEST_ONLY_KC='secret-selftest*'
MP='master-pass-shim'

SHIM=$HOME/.config/bin/secret-shim
PT=secret-selftest-shimproj      # project-mode project (via git config)
PB=secret-selftest-shimbase      # tool-mode base layer (SECRET_SHIM_BASE)
PTOOL=secret-selftest-shimtool   # tool-mode layer == fake command name
PNOKC=secret-selftest-shimnokc   # mapped project without a keychain
TD=$(mktemp -d)

cleanup() {
  local f p n
  for f in $HOME/Library/Keychains/secret-selftest*.keychain-db(N); do
    security delete-keychain "$f" >/dev/null 2>&1
  done
  for p in $PT $PB $PTOOL $PNOKC; do
    secret -k default ls -p $p 2>/dev/null | while read -r n; do
      while security delete-generic-password -s "secret.$p" -a "$n" >/dev/null 2>&1; do :; done
    done
    security delete-generic-password -s 'keychain-password' -a "$p" >/dev/null 2>&1
  done
  security delete-generic-password -s 'keychain-password' -a master-selftest >/dev/null 2>&1
  rm -rf "$TD"
}
trap cleanup EXIT
cleanup 2>/dev/null   # leftovers from a previous run
mkdir -p "$TD"

# --- fixtures -------------------------------------------------------------
print -r -- "$MP" | secret keychain master set --stdin >/dev/null 2>&1 \
  && ok "master set (bootstrap)" || bad "master set (bootstrap)"

# fake commands: $TD/bin holds shim symlinks, $TD/real the "real" binaries
mkdir -p "$TD/bin" "$TD/real" "$TD/outside"
ln -s "$SHIM" "$TD/bin/$PTOOL"
ln -s "$SHIM" "$TD/bin/printenv"
ln -s "$SHIM" "$TD/bin/secret-selftest-shimmissing"
cat > "$TD/real/$PTOOL" <<'EOF'
#!/bin/sh
if [ "$1" = "--args" ]; then shift; printf '%s\n' "$@"; exit 0; fi
exec /usr/bin/printenv "$@"
EOF
chmod +x "$TD/real/$PTOOL"

# project-mode repo: root .env, monorepo package .env, template file
git -C "$TD" init -q repo
git -C "$TD/repo" config secret.project $PT
mkdir -p "$TD/repo/apps/web" "$TD/repo/apps/api"
printf 'B_DOTENV=fromfile\nexport E_EXPORTED=fromfile\n' > "$TD/repo/.env"
printf 'C_SUB=fromsub\n' > "$TD/repo/apps/web/.env"
printf 'D_EXAMPLE=placeholder\n' > "$TD/repo/.env.example"

# keychain content
for kv in A_ONLY:kc-a B_DOTENV:kc-b C_SUB:kc-c D_EXAMPLE:kc-d E_EXPORTED:kc-e; do
  print -r -- "${kv#*:}" | secret set "${kv%%:*}" -p $PT --stdin >/dev/null 2>&1
done
print -r -- 'kc-scoped' | secret set SCOPED_V -p $PT --scope repo --stdin >/dev/null 2>&1
print -r -- 'base-1' | secret set TB_BASE -p $PB --stdin >/dev/null 2>&1
print -r -- 'base-both' | secret set TB_BOTH -p $PB --stdin >/dev/null 2>&1
print -r -- 'tool-1' | secret set TT_TOOL -p $PTOOL --stdin >/dev/null 2>&1
print -r -- 'tool-both' | secret set TB_BOTH -p $PTOOL --stdin >/dev/null 2>&1

tool_run() {                   # tool mode: run the fake tool, args -> printenv
  ( path=("$TD/bin" "$TD/real" $path)
    SECRET_SHIM_BASE=$PB "$TD/bin/$PTOOL" "$@" 2>/dev/null )
}
penv() {                       # project mode: $1 dir, $2.. -> printenv args
  local d=$1; shift
  ( cd "$d" || exit 9
    path=("$TD/bin" $path)
    SECRET_SHIM_MODE=project "$TD/bin/printenv" "$@" 2>/dev/null )
}

# --- tool mode ------------------------------------------------------------
[[ "$(tool_run TB_BASE)" == 'base-1' ]] \
  && ok "tool: base layer injected" || bad "tool: base layer injected"
[[ "$(tool_run TT_TOOL)" == 'tool-1' ]] \
  && ok "tool: tool layer injected" || bad "tool: tool layer injected"
[[ "$(tool_run TB_BOTH)" == 'tool-both' ]] \
  && ok "tool: tool layer overrides base" || bad "tool: tool layer overrides base"
[[ "$(TB_BOTH=external tool_run TB_BOTH)" == 'external' ]] \
  && ok "tool: inherited environment wins" || bad "tool: inherited environment wins"
[[ -z "$(_SECRET_SHIM_TOOL=$PTOOL tool_run TB_BASE)" ]] \
  && ok "tool: sentinel skips re-injection" || bad "tool: sentinel skips re-injection"
[[ "$(tool_run _SECRET_SHIM_TOOL)" == "$PTOOL" ]] \
  && ok "tool: sentinel exported to children" || bad "tool: sentinel exported to children"
out=$(tool_run --args one 'two words' three)
[[ $out == 'one'$'\n''two words'$'\n''three' ]] \
  && ok "tool: arguments passed through verbatim" || bad "tool: arguments passed through verbatim"

# --- project mode ---------------------------------------------------------
R=$TD/repo
[[ "$(penv $R A_ONLY)" == 'kc-a' ]] \
  && ok "proj: keychain-only name injected" || bad "proj: keychain-only name injected"
[[ -z "$(penv $R B_DOTENV)" ]] \
  && ok "proj: .env name skipped" || bad "proj: .env name skipped"
[[ -z "$(penv $R C_SUB)" ]] \
  && ok "proj: package .env respected from root (union)" || bad "proj: package .env respected from root (union)"
[[ "$(penv $R D_EXAMPLE)" == 'kc-d' ]] \
  && ok "proj: .env.example ignored" || bad "proj: .env.example ignored"
[[ -z "$(penv $R E_EXPORTED)" ]] \
  && ok "proj: 'export NAME=' dotenv lines parsed" || bad "proj: 'export NAME=' dotenv lines parsed"
[[ "$(penv $R SCOPED_V)" == 'kc-scoped' ]] \
  && ok "proj: ambient scope overlay applies" || bad "proj: ambient scope overlay applies"
[[ "$(penv $R/apps/api C_SUB)" == 'kc-c' ]] \
  && ok "proj: sibling .env out of scope inside a package" || bad "proj: sibling .env out of scope inside a package"
[[ -z "$(penv $R/apps/api B_DOTENV)" ]] \
  && ok "proj: ancestor .env respected inside a package" || bad "proj: ancestor .env respected inside a package"
[[ "$(A_ONLY=external penv $R A_ONLY)" == 'external' ]] \
  && ok "proj: inherited environment wins" || bad "proj: inherited environment wins"
[[ -z "$(_SECRET_SHIM_PROJ=$PT penv $R A_ONLY)" ]] \
  && ok "proj: sentinel skips re-injection" || bad "proj: sentinel skips re-injection"
[[ "$(penv $R _SECRET_SHIM_PROJ)" == "$PT" ]] \
  && ok "proj: sentinel exported to children" || bad "proj: sentinel exported to children"
[[ -z "$(penv $TD/outside A_ONLY)" ]] \
  && ok "proj: no injection outside a git repository" || bad "proj: no injection outside a git repository"

# mapped project without a keychain: command must still run
git -C "$TD" init -q nokc
git -C "$TD/nokc" config secret.project $PNOKC
penv "$TD/nokc" PATH >/dev/null \
  && ok "proj: missing keychain never blocks a launch" || bad "proj: missing keychain never blocks a launch"

# --- exec behaviour -------------------------------------------------------
penv $R THIS_VAR_DOES_NOT_EXIST >/dev/null
(( $? == 1 )) \
  && ok "exec: exit code passed through" || bad "exec: exit code passed through"
( path=("$TD/bin" $path)
  "$TD/bin/secret-selftest-shimmissing" >/dev/null 2>&1 )
(( $? == 127 )) \
  && ok "exec: 127 when no real binary exists" || bad "exec: 127 when no real binary exists"

print ''
if (( fails == 0 )); then
  print -r -- "ALL TESTS PASSED"
else
  print -r -- "$fails TEST(S) FAILED"
fi
exit $fails
