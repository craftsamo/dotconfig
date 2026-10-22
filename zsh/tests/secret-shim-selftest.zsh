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
[[ "$(SECRET_STAGE=production penv $R _SECRET_SHIM_PROJ)" == "$PT@prod" && "$(SECRET_STAGE=production penv $R A_ONLY)" == 'kc-a-prod' ]] \
  && ok "proj: SECRET_STAGE=production is the prod layer and sentinel" || bad "proj: SECRET_STAGE=production is the prod layer and sentinel"
[[ "$(_SECRET_SHIM_PROJ=$PT@ SECRET_STAGE=prod penv $R P_ONLY)" == 'prod-only' ]] \
  && ok "proj: a nested launch in another stage injects again" || bad "proj: a nested launch in another stage injects again"
[[ -z "$(_SECRET_SHIM_PROJ=$PT@prod SECRET_STAGE=prod penv $R P_ONLY)" ]] \
  && ok "proj: same stage, sentinel skips" || bad "proj: same stage, sentinel skips"
# a nested launch in another stage swaps the parent's injected values for the
# new stage's — the environment never mixes two stages; what the user
# exported by hand (not in _SECRET_SHIM_NAMES) still wins
[[ "$(penv $R _SECRET_SHIM_NAMES)" == *A_ONLY* && "$(penv $R _SECRET_SHIM_NAMES)" == *D_EXAMPLE* ]] \
  && ok "proj: the injected names are exported to children" || bad "proj: the injected names are exported to children"
[[ "$(_SECRET_SHIM_PROJ=$PT@ _SECRET_SHIM_NAMES='A_ONLY D_EXAMPLE' A_ONLY=kc-a D_EXAMPLE=kc-d SECRET_STAGE=prod penv $R A_ONLY)" == 'kc-a-prod' ]] \
  && ok "proj: another stage replaces a value the parent shim injected" || bad "proj: another stage replaces a value the parent shim injected"
[[ "$(_SECRET_SHIM_PROJ=$PT@prod _SECRET_SHIM_NAMES='A_ONLY P_ONLY' A_ONLY=kc-a-prod P_ONLY=prod-only penv $R A_ONLY)" == 'kc-a' \
   && -z "$(_SECRET_SHIM_PROJ=$PT@prod _SECRET_SHIM_NAMES='A_ONLY P_ONLY' A_ONLY=kc-a-prod P_ONLY=prod-only penv $R P_ONLY)" ]] \
  && ok "proj: leaving prod drops the prod-only values" || bad "proj: leaving prod drops the prod-only values"
[[ "$(_SECRET_SHIM_PROJ=$PT@ _SECRET_SHIM_NAMES='D_EXAMPLE' A_ONLY=mine D_EXAMPLE=kc-d SECRET_STAGE=prod penv $R A_ONLY)" == 'mine' ]] \
  && ok "proj: a hand-exported value survives the stage swap" || bad "proj: a hand-exported value survives the stage swap"
[[ "$(_SECRET_SHIM_PROJ=$PT@ _SECRET_SHIM_NAMES='A_ONLY D_EXAMPLE' A_ONLY=kc-a D_EXAMPLE=kc-d SECRET_STAGE=prod penv $R _SECRET_SHIM_NAMES)" == *P_ONLY* ]] \
  && ok "proj: the swap records the new stage's names" || bad "proj: the swap records the new stage's names"
err=$( cd "$R" && path=("$TD/bin" $path) && SECRET_SHIM_MODE=project _SECRET_SHIM_PROJ=$PT@ _SECRET_SHIM_NAMES='A_ONLY' A_ONLY=kc-a SECRET_STAGE=test "$TD/bin/printenv" A_ONLY 2>&1 >/dev/null )
[[ $err == *"secret-shim: stage $PT@ -> $PT@test"* ]] \
  && ok "proj: the swap is announced on stderr" || bad "proj: the swap is announced on stderr"
err=$( cd "$R" && path=("$TD/bin" $path) && SECRET_SHIM_MODE=project SECRET_STAGE=prod "$TD/bin/printenv" P_ONLY 2>&1 >/dev/null )
[[ $err == *"secret-shim: stage=prod ($PT)"* ]] \
  && ok "proj: a prod launch is announced on stderr" || bad "proj: a prod launch is announced on stderr"
err=$( cd "$R" && path=("$TD/bin" $path) && SECRET_SHIM_MODE=project SECRET_STAGE=test "$TD/bin/printenv" A_ONLY 2>&1 >/dev/null )
[[ -z $err ]] && ok "proj: other stages launch silently" || bad "proj: other stages launch silently"
[[ "$(SECRET_STAGE=prod tool_run TT_TOOL)" == 'tool-1' && "$(SECRET_STAGE=prod tool_run TB_BASE)" == 'base-1' ]] \
  && ok "tool: a stage never reaches a tool" || bad "tool: a stage never reaches a tool"
[[ "$(SECRET_STAGE=prod tool_run SECRET_STAGE)" == 'prod' ]] \
  && ok "tool: SECRET_STAGE itself still passes through" || bad "tool: SECRET_STAGE itself still passes through"
# dotenv skipping follows the stage: with none, every .env* counts (the
# application may read any of them); with SECRET_STAGE=S only .env,
# .env.local and .env.S{,.local} do — another stage's file never keeps the
# asked-for stage's value out
printf 'A_ONLY=fromtest\n' > "$R/.env.test"
printf 'P_ONLY=fromprod\n' > "$R/.env.production"
[[ -z "$(penv $R A_ONLY)" && -z "$(penv $R P_ONLY)" ]] \
  && ok "dotenv: no stage, every stage file's names are skipped" || bad "dotenv: no stage, every stage file's names are skipped"
[[ "$(SECRET_STAGE=prod penv $R A_ONLY)" == 'kc-a-prod' ]] \
  && ok "dotenv: another stage's file does not keep the stage's value out" || bad "dotenv: another stage's file does not keep the stage's value out"
[[ -z "$(SECRET_STAGE=prod penv $R P_ONLY)" ]] \
  && ok "dotenv: the stage's own file is still respected" || bad "dotenv: the stage's own file is still respected"
[[ -z "$(SECRET_STAGE=production penv $R P_ONLY)" && "$(SECRET_STAGE=production penv $R A_ONLY)" == 'kc-a-prod' ]] \
  && ok "dotenv: 'production' reads .env.production and the prod layer" || bad "dotenv: 'production' reads .env.production and the prod layer"
[[ -z "$(SECRET_STAGE=test penv $R A_ONLY)" && -z "$(SECRET_STAGE=prod penv $R B_DOTENV)" ]] \
  && ok "dotenv: .env and the stage's file are skipped under a stage" || bad "dotenv: .env and the stage's file are skipped under a stage"
rm -f "$R/.env.test" "$R/.env.production"

# --- mode by link target ----------------------------------------------------
# the launcher a command is linked to declares its mode, without
# SECRET_SHIM_MODE and without a name table: secret-shim-project for
# project mode, secret-shim-plain for none, secret-shim itself for tool mode
ln -s "${SHIM:h}/secret-shim-project" "$TD/bin/anytool"
ln -s "$SHIM" "$TD/bin/docker"
for c in anytool docker; do
  cat > "$TD/real/$c" <<'EOF'
#!/bin/sh
exec /usr/bin/printenv "$@"
EOF
  chmod +x "$TD/real/$c"
done
linkenv() {                    # $1 command; like penv, but no SECRET_SHIM_MODE forcing
  local c=$1; shift
  ( cd "$TD/repo" || exit 9
    path=("$TD/bin" "$TD/real" $path)
    SECRET_SHIM_BASE=$PB "$TD/bin/$c" "$@" 2>/dev/null )
}
[[ "$(linkenv anytool A_ONLY)" == 'kc-a' ]] \
  && ok "mode: a link to secret-shim-project is project mode" || bad "mode: a link to secret-shim-project is project mode"
[[ -z "$(linkenv anytool B_DOTENV)" ]] \
  && ok "mode: ... and respects the dotenv skip" || bad "mode: ... and respects the dotenv skip"
[[ -z "$(linkenv docker A_ONLY)" && "$(linkenv docker TB_BASE)" == 'base-1' ]] \
  && ok "mode: a link to secret-shim is tool mode, whatever the name" || bad "mode: a link to secret-shim is tool mode, whatever the name"
[[ -L ${SHIM:h}/secret-shim-project && ${SHIM:h}/secret-shim-project -ef $SHIM && -L ${SHIM:h}/secret-shim-plain && ${SHIM:h}/secret-shim-plain -ef $SHIM ]] \
  && ok "mode: secret-shim-project and -plain are links to secret-shim" || bad "mode: secret-shim-project and -plain are links to secret-shim"
# a link to a link (a bin elsewhere pointing at ~/.config/bin/node) still finds its mode
mkdir -p "$TD/bin2"; ln -s "$TD/bin/anytool" "$TD/bin2/anytool"
[[ "$( cd "$TD/repo" && path=("$TD/bin2" "$TD/real" $path) && SECRET_SHIM_BASE=$PB "$TD/bin2/anytool" A_ONLY 2>/dev/null )" == 'kc-a' ]] \
  && ok "mode: a link to a link follows the chain" || bad "mode: a link to a link follows the chain"
# the mode does not depend on a readlink found through PATH
mkdir -p "$TD/broken"; printf '#!/bin/sh\nexit 1\n' > "$TD/broken/readlink"; chmod +x "$TD/broken/readlink"
[[ "$( cd "$TD/repo" && path=("$TD/broken" "$TD/bin" "$TD/real" $path) && SECRET_SHIM_BASE=$PB "$TD/bin/anytool" A_ONLY 2>/dev/null )" == 'kc-a' ]] \
  && ok "mode: chosen without readlink on PATH" || bad "mode: chosen without readlink on PATH"

# --- mise pin ---------------------------------------------------------------
# a caller that swaps HOME (and drops MISE_*) still gets the real home's dirs
ln -s "${SHIM:h}/secret-shim-plain" "$TD/bin/pip"
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
