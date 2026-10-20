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
#   SECRET_SHIM_UNDER_TEST=<worktree>/bin/secret-shim zsh -f ...   (a candidate shim,
#       together with the secret.zsh beside it; SECRET_SHIM_LIB picks another)
emulate -L zsh
setopt pipefail
SHIM=${SECRET_SHIM_UNDER_TEST:-$HOME/.config/bin/secret-shim}
export SECRET_SHIM_LIB=${SECRET_SHIM_LIB:-${SHIM:A:h}/../zsh/functions/secret.zsh}
source "$SECRET_SHIM_LIB"

typeset -i fails=0
ok()  { print -r -- "ok   - $1"; }
bad() { print -r -- "FAIL - $1"; (( fails++ )); }

# every project/keychain name used below must match this glob
export SECRET_MASTER_ACCOUNT=master-selftest
export SECRET_TEST_ONLY_KC='secret-selftest*'
MP='master-pass-shim'
unset SECRET_STAGE

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
ln -s "$SHIM" "$TD/bin/opencode"
ln -s "$SHIM" "$TD/bin/secret-selftest-shimmissing"
cat > "$TD/real/$PTOOL" <<'EOF'
#!/bin/sh
if [ "$1" = "--args" ]; then shift; printf '%s\n' "$@"; exit 0; fi
exec /usr/bin/printenv "$@"
EOF
chmod +x "$TD/real/$PTOOL"
cat > "$TD/real/opencode" <<'EOF'
#!/bin/sh
printf '%s\n' "$@"
EOF
chmod +x "$TD/real/opencode"

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
print -r -- 'tool-scoped' | secret set TS_SCOPED -p $PTOOL --scope shimscope --stdin >/dev/null 2>&1
git -C "$TD" init -q shimscope    # a repository whose name is that scope

tool_run() {                   # tool mode: run the fake tool, args -> printenv
  ( path=("$TD/bin" "$TD/real" $path)
    SECRET_SHIM_BASE=$PB "$TD/bin/$PTOOL" "$@" 2>/dev/null )
}
opencode_run() {               # skip Keychain access; test serve's auth guard
  ( path=("$TD/bin" "$TD/real" $path)
    unset OPENCODE_SERVER_PASSWORD
    _SECRET_SHIM_TOOL=opencode "$TD/bin/opencode" "$@" )
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
[[ -z "$(cd "$TD/shimscope" && tool_run TS_SCOPED)" && "$(cd "$TD/shimscope" && tool_run TT_TOOL)" == 'tool-1' ]] \
  && ok "tool: a repository scope never reaches a tool" || bad "tool: a repository scope never reaches a tool"
[[ -z "$(_SECRET_SHIM_TOOL=$PTOOL tool_run TB_BASE)" ]] \
  && ok "tool: sentinel skips re-injection" || bad "tool: sentinel skips re-injection"
[[ "$(tool_run _SECRET_SHIM_TOOL)" == "$PTOOL" ]] \
  && ok "tool: sentinel exported to children" || bad "tool: sentinel exported to children"
out=$(tool_run --args one 'two words' three)
[[ $out == 'one'$'\n''two words'$'\n''three' ]] \
  && ok "tool: arguments passed through verbatim" || bad "tool: arguments passed through verbatim"
[[ "$(opencode_run tui 2>/dev/null)" == 'tui' ]] \
  && ok "tool: bare opencode does not require server auth" || bad "tool: bare opencode does not require server auth"
opencode_run serve --port 4096 >/dev/null 2>&1
(( $? == 1 )) \
  && ok "tool: opencode serve rejects a missing password" || bad "tool: opencode serve rejects a missing password"
out=$(path=("$TD/bin" "$TD/real" $path) _SECRET_SHIM_TOOL=opencode \
  OPENCODE_SERVER_PASSWORD=test "$TD/bin/opencode" serve --port 4096 2>/dev/null)
[[ $out == 'serve'$'\n''--port'$'\n''4096' ]] \
  && ok "tool: opencode serve accepts an injected password" || bad "tool: opencode serve accepts an injected password"
out=$(path=("$TD/bin" "$TD/real" $path) _SECRET_SHIM_TOOL=opencode \
  OPENCODE_PASSWORD=test "$TD/bin/opencode" serve --port 4096 2>/dev/null)
[[ $out == 'serve'$'\n''--port'$'\n''4096' ]] \
  && ok "tool: opencode serve accepts OPENCODE_PASSWORD" || bad "tool: opencode serve accepts OPENCODE_PASSWORD"

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
[[ -z "$(_SECRET_SHIM_PROJ=$PT@ penv $R A_ONLY)" ]] \
  && ok "proj: sentinel skips re-injection" || bad "proj: sentinel skips re-injection"
[[ "$(penv $R _SECRET_SHIM_PROJ)" == "$PT@" ]] \
  && ok "proj: sentinel exported to children" || bad "proj: sentinel exported to children"
[[ -z "$(penv $TD/outside A_ONLY)" ]] \
  && ok "proj: no injection outside a git repository" || bad "proj: no injection outside a git repository"

# --- stages ---------------------------------------------------------------
print -r -- 'kc-a-prod' | secret set A_ONLY -p $PT --stage prod --stdin >/dev/null 2>&1
print -r -- 'kc-scoped-prod' | secret set SCOPED_V -p $PT --scope repo --stage prod --stdin >/dev/null 2>&1
print -r -- 'prod-only' | secret set P_ONLY -p $PT --stage prod --stdin >/dev/null 2>&1
print -r -- 'tool-prod' | secret set TT_TOOL -p $PTOOL --stage prod --stdin >/dev/null 2>&1
print -r -- 'base-prod' | secret set TB_BASE -p $PB --stage prod --stdin >/dev/null 2>&1
[[ "$(penv $R A_ONLY)" == 'kc-a' && -z "$(penv $R P_ONLY)" ]] \
  && ok "proj: no stage, no staged value" || bad "proj: no stage, no staged value"
[[ "$(SECRET_STAGE=prod penv $R A_ONLY)" == 'kc-a-prod' ]] \
  && ok "proj: SECRET_STAGE selects the stage's shared layer" || bad "proj: SECRET_STAGE selects the stage's shared layer"
[[ "$(SECRET_STAGE=prod penv $R SCOPED_V)" == 'kc-scoped-prod' ]] \
  && ok "proj: the stage's scoped layer wins" || bad "proj: the stage's scoped layer wins"
[[ "$(SECRET_STAGE=prod penv $R P_ONLY)" == 'prod-only' && "$(SECRET_STAGE=prod penv $R D_EXAMPLE)" == 'kc-d' ]] \
  && ok "proj: staged-only and stage-less names both injected" || bad "proj: staged-only and stage-less names both injected"
[[ "$(SECRET_STAGE=test penv $R A_ONLY)" == 'kc-a' && -z "$(SECRET_STAGE=test penv $R P_ONLY)" ]] \
  && ok "proj: another stage never sees prod" || bad "proj: another stage never sees prod"
[[ "$(SECRET_STAGE=prod penv $R _SECRET_SHIM_PROJ)" == "$PT@prod" ]] \
  && ok "proj: sentinel carries the stage" || bad "proj: sentinel carries the stage"
[[ "$(_SECRET_SHIM_PROJ=$PT@ SECRET_STAGE=prod penv $R P_ONLY)" == 'prod-only' ]] \
  && ok "proj: a nested launch in another stage injects again" || bad "proj: a nested launch in another stage injects again"
[[ -z "$(_SECRET_SHIM_PROJ=$PT@prod SECRET_STAGE=prod penv $R P_ONLY)" ]] \
  && ok "proj: same stage, sentinel skips" || bad "proj: same stage, sentinel skips"
err=$( cd "$R" && path=("$TD/bin" $path) && SECRET_SHIM_MODE=project SECRET_STAGE=prod "$TD/bin/printenv" P_ONLY 2>&1 >/dev/null )
[[ $err == *"secret-shim: stage=prod ($PT)"* ]] \
  && ok "proj: a prod launch is announced on stderr" || bad "proj: a prod launch is announced on stderr"
err=$( cd "$R" && path=("$TD/bin" $path) && SECRET_SHIM_MODE=project SECRET_STAGE=test "$TD/bin/printenv" A_ONLY 2>&1 >/dev/null )
[[ -z $err ]] && ok "proj: other stages launch silently" || bad "proj: other stages launch silently"
[[ "$(SECRET_STAGE=prod tool_run TT_TOOL)" == 'tool-1' && "$(SECRET_STAGE=prod tool_run TB_BASE)" == 'base-1' ]] \
  && ok "tool: a stage never reaches a tool" || bad "tool: a stage never reaches a tool"
[[ "$(SECRET_STAGE=prod tool_run SECRET_STAGE)" == 'prod' ]] \
  && ok "tool: SECRET_STAGE itself still passes through" || bad "tool: SECRET_STAGE itself still passes through"

# --- mode table -----------------------------------------------------------
# real command names must select their mode without SECRET_SHIM_MODE
ln -s "$SHIM" "$TD/bin/docker"
cat > "$TD/real/docker" <<'EOF'
#!/bin/sh
exec /usr/bin/printenv "$@"
EOF
chmod +x "$TD/real/docker"
dockenv() {                    # like penv, but no SECRET_SHIM_MODE forcing
  ( cd "$TD/repo" || exit 9
    path=("$TD/bin" "$TD/real" $path)
    "$TD/bin/docker" "$@" 2>/dev/null )
}
[[ "$(dockenv A_ONLY)" == 'kc-a' ]] \
  && ok "mode table: docker maps to project mode" || bad "mode table: docker maps to project mode"
[[ -z "$(dockenv B_DOTENV)" ]] \
  && ok "mode table: docker respects dotenv skip" || bad "mode table: docker respects dotenv skip"

# --- mise pin ---------------------------------------------------------------
# a caller that swaps HOME (and drops MISE_*) still gets the real home's dirs
ln -s "$SHIM" "$TD/bin/pip"
cat > "$TD/real/pip" <<'EOF'
#!/bin/sh
exec /usr/bin/printenv "$@"
EOF
chmod +x "$TD/real/pip"
mkdir -p "$TD/fakehome"
RH=$(setopt no_nomatch; print -r -- ${~:-"~$USERNAME"})   # the user database's home
[[ $OSTYPE == darwin* ]] && RCACHE=$RH/Library/Caches/mise || RCACHE=$RH/.cache/mise
swapped() {                    # $1 command name, $2.. -> printenv args
  local c=$1; shift
  ( cd "$TD/repo" || exit 9
    path=("$TD/bin" "$TD/real" $path)
    unset MISE_DATA_DIR MISE_CONFIG_DIR MISE_STATE_DIR MISE_CACHE_DIR
    HOME=$TD/fakehome "$TD/bin/$c" "$@" 2>/dev/null )
}
[[ "$(swapped $PTOOL MISE_DATA_DIR)" == "$RH/.local/share/mise" \
   && "$(swapped $PTOOL MISE_CONFIG_DIR)" == "$RH/.config/mise" \
   && "$(swapped $PTOOL MISE_CACHE_DIR)" == "$RCACHE" ]] \
  && ok "mise: dirs pinned to the real home under a swapped HOME" \
  || bad "mise: dirs pinned to the real home under a swapped HOME"
out=$(cd "$TD/repo" && path=("$TD/bin" "$TD/real" $path) \
  MISE_DATA_DIR=/inherited HOME=$TD/fakehome "$TD/bin/$PTOOL" MISE_DATA_DIR 2>/dev/null)
[[ $out == '/inherited' ]] \
  && ok "mise: inherited dir wins" || bad "mise: inherited dir wins"
[[ "$(swapped docker MISE_STATE_DIR)" == "$RH/.local/state/mise" ]] \
  && ok "mise: project mode pins too" || bad "mise: project mode pins too"
pipenv() {                     # plain mode in a mapped repo, real HOME
  ( cd "$TD/repo" || exit 9
    path=("$TD/bin" "$TD/real" $path)
    "$TD/bin/pip" "$@" 2>/dev/null )
}
[[ -z "$(pipenv A_ONLY)" && -z "$(SECRET_SHIM_BASE=$PB pipenv TB_BASE)" ]] \
  && ok "plain: pip injects no secrets" || bad "plain: pip injects no secrets"
[[ "$(unset MISE_CACHE_DIR; pipenv MISE_CACHE_DIR)" == "$RCACHE" ]] \
  && ok "plain: pip still pins mise" || bad "plain: pip still pins mise"

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
