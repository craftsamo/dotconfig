#!/usr/bin/env zsh
# Self-test for secret.zsh (the 1:1 project = keychain model).
#
# Safe to run on a machine with real data:
#   - only touches throwaway "secret-selftest*" projects/keychains
#   - the master-password machinery is isolated via SECRET_MASTER_ACCOUNT
#     and SECRET_TEST_ONLY_KC, so the real master item and real keychains
#     are never read, rotated or adopted
#   - cleans up after itself (trap on EXIT)
#
#   zsh -f ~/.config/zsh/tests/secret-selftest.zsh
emulate -L zsh
setopt pipefail
source "$HOME/.config/zsh/functions/secret.zsh"

typeset -i fails=0
ok()  { print -r -- "ok   - $1"; }
bad() { print -r -- "FAIL - $1"; (( fails++ )); }

# every project/keychain name used below must match this glob
export SECRET_MASTER_ACCOUNT=master-selftest
export SECRET_TEST_ONLY_KC='secret-selftest*'
MP='master-pass-one'
MP2='master-pass-two'

P=secret-selftest
P2=secret-selftest2
P3=secret-selftest3
KCN=secret-selftest-kc          # fixture with its own password (testpass)
KCN2=secret-selftest-unlisted   # exists on disk but never registered
KCN3=secret-selftest-mkc        # created via `secret keychain create`
PMAP=secret-selftest-mapped     # via git config secret.project
PREPO=secret-selftest-repo      # via git toplevel basename
PNOM=secret-selftest-nomaster   # write attempt without master
KCP=$HOME/Library/Keychains/$KCN.keychain-db
KCP2=$HOME/Library/Keychains/$KCN2.keychain-db
KCP3=$HOME/Library/Keychains/$KCN3.keychain-db
TD=$(mktemp -d)

DKC=$(security default-keychain | sed -E 's/^[[:space:]]*"(.*)"[[:space:]]*$/\1/')

cleanup() {
  local f p n
  # keychains (also drops their search-list entries)
  for f in $HOME/Library/Keychains/secret-selftest*.keychain-db(N); do
    security delete-keychain "$f" >/dev/null 2>&1
  done
  # login leftovers: -k default test items and stored unlock passwords
  for p in $P $P2 $P3 $KCN $KCN2 $KCN3 $PMAP $PREPO $PNOM; do
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

V1='sp ace "dq" \back\slash $dollar !bang '\''sq'\'' end'
V2='simple-token-123'

# --- master bootstrap (no keychains in scope yet: adopts nothing) ---
print -r -- "$MP" | secret keychain master set --stdin >/dev/null 2>&1 \
  && ok "master set (bootstrap)" || bad "master set (bootstrap)"
[[ "$(secret keychain master reveal)" == "$MP" ]] && ok "master reveal" || bad "master reveal"

# --- set auto-creates the project keychain ---
print -r -- "$V1" | secret set TEST_ALPHA -p $P -j 'comment with "quotes" and spaces' -D 'api key' --stdin >/dev/null 2>&1 \
  && ok "set TEST_ALPHA (stdin)" || bad "set TEST_ALPHA (stdin)"
[[ -e $HOME/Library/Keychains/$P.keychain-db ]] \
  && ok "keychain auto-created on first write" || bad "keychain auto-created on first write"
slarr=(${(f)"$(security list-keychains -d user | sed -E 's/^[[:space:]]*"(.*)"[[:space:]]*$/\1/')"})
(( ${slarr[(Ie)$HOME/Library/Keychains/$P.keychain-db]} )) \
  && ok "auto-created keychain registered" || bad "auto-created keychain registered"
[[ "$(security show-keychain-info $HOME/Library/Keychains/$P.keychain-db 2>&1)" == *1800* ]] \
  && ok "auto-created keychain has autolock settings" || bad "auto-created keychain has autolock settings"
print -r -- "$V2" | secret set TEST_BETA -p $P --stdin >/dev/null 2>&1 \
  && ok "set TEST_BETA (stdin)" || bad "set TEST_BETA (stdin)"

# --- get ---
[[ "$(secret get TEST_ALPHA -p $P)" == "$V1" ]] \
  && ok "get round-trips special chars" || bad "get round-trips special chars"
[[ "$(secret get TEST_BETA -p $P)" == "$V2" ]] \
  && ok "get simple value" || bad "get simple value"

# --- update via set -U ---
print -r -- 'updated-456' | secret set TEST_BETA -p $P --stdin >/dev/null 2>&1
[[ "$(secret get TEST_BETA -p $P)" == 'updated-456' ]] \
  && ok "set -U updates existing item" || bad "set -U updates existing item"

# --- validation ---
print -r -- 'x' | secret set '1BAD' -p $P --stdin >/dev/null 2>&1 \
  && bad "rejects invalid name" || ok "rejects invalid name"
printf 'a\nb\n' | secret set TEST_MULTI -p $P --stdin >/dev/null 2>&1 \
  && bad "rejects multi-line value" || ok "rejects multi-line value"
secret get TEST_NOPE -p $P >/dev/null 2>&1 \
  && bad "get of missing item fails" || ok "get of missing item fails"

# --- ls / show / projects ---
lsarr=(${(f)"$(secret ls -p $P)"})
(( ${lsarr[(Ie)TEST_ALPHA]} )) && ok "ls lists item" || bad "ls lists item"
[[ ${#lsarr} -eq 2 ]] && ok "ls shows 2 items" || bad "ls shows 2 items"
longout=$(secret ls -p $P --long)
[[ $longout == *'API KEY'* ]] && ok "ls --long shows normalized kind" || bad "ls --long shows normalized kind"
[[ $longout =~ 'TEST_BETA[[:space:]]+Shared[[:space:]]+ENV[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}' ]] \
  && ok "ls --long shows Shared scope + aligns columns" || bad "ls --long shows Shared scope + aligns columns"
showout=$(secret show TEST_ALPHA -p $P)
[[ $showout == *'comment with "quotes" and spaces'* ]] && ok "show displays comment" || bad "show displays comment"
[[ $showout =~ 'Modified:[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}' ]] && ok "show displays modified date" || bad "show displays modified date"
[[ $showout != *$V1* ]] && ok "show never prints value" || bad "show never prints value"
[[ "$(print -r -- "$showout" | awk '/^Label:/ {print $2}')" == "TEST_ALPHA" ]] \
  && ok "label is NAME in own keychain" || bad "label is NAME in own keychain"
[[ $showout == *"$P.keychain-db"* ]] && ok "show reports own keychain" || bad "show reports own keychain"
projarr=(${(f)"$(secret projects)"})
(( ${projarr[(Ie)$P]} )) && ok "projects lists auto-created project" || bad "projects lists auto-created project"

# --- env / eval ---
envout=$(secret env -p $P)
( eval "$envout"; [[ "$TEST_ALPHA" == "$V1" && "$TEST_BETA" == 'updated-456' ]] ) \
  && ok "env output is eval-safe" || bad "env output is eval-safe"

# --- export json / import ---
secret export -p $P --format json -o "$TD/x.json" >/dev/null 2>&1 \
  && ok "export json" || bad "export json"
jq -e '.items | length == 2' "$TD/x.json" >/dev/null 2>&1 && ok "json has 2 items" || bad "json has 2 items"
jq -e '.items[] | select(.name == "TEST_ALPHA") | .kind == "API KEY"' "$TD/x.json" >/dev/null 2>&1 \
  && ok "json keeps metadata" || bad "json keeps metadata"
jq -e '.items[] | select(.name == "TEST_BETA") | .comment == ""' "$TD/x.json" >/dev/null 2>&1 \
  && ok "json empty comment stays empty" || bad "json empty comment stays empty"
[[ "$(stat -f %Lp "$TD/x.json" 2>/dev/null)" == 600 ]] && ok "export chmod 600" || bad "export chmod 600"

secret rm TEST_ALPHA -p $P -f >/dev/null && secret rm TEST_BETA -p $P -f >/dev/null
[[ -z "$(secret ls -p $P 2>/dev/null)" ]] && ok "rm removes items" || bad "rm removes items"

secret import "$TD/x.json" >/dev/null 2>&1 && ok "import json (project from file)" || bad "import json (project from file)"
[[ "$(secret get TEST_ALPHA -p $P)" == "$V1" ]] && ok "json round-trip value" || bad "json round-trip value"
[[ "$(secret show TEST_ALPHA -p $P)" == *'comment with'* ]] && ok "json round-trip comment" || bad "json round-trip comment"

# regression: an empty comment must not swallow the following columns
print -r -- 'tok-1' | secret set TEST_GAMMA -p $P -D 'token' --stdin >/dev/null 2>&1
secret export -p $P --format json -o "$TD/gamma.json" >/dev/null 2>&1
secret rm TEST_GAMMA -p $P -f >/dev/null
secret import "$TD/gamma.json" >/dev/null 2>&1
gshow=$(secret show TEST_GAMMA -p $P)
[[ $gshow =~ 'Kind:[[:space:]]+TOKEN' ]] \
  && ok "import keeps kind despite empty comment" || bad "import keeps kind despite empty comment"
[[ $gshow != *'Comment:   token'* ]] \
  && ok "empty comment stays empty on import" || bad "empty comment stays empty on import"
secret rm TEST_GAMMA -p $P -f >/dev/null 2>&1

# --- export env / import into another project (auto-creates its keychain) ---
secret export -p $P --format env -o "$TD/x.env" >/dev/null 2>&1 && ok "export env" || bad "export env"
secret import "$TD/x.env" -p $P2 >/dev/null 2>&1 && ok "import env -> other project" || bad "import env -> other project"
[[ -e $HOME/Library/Keychains/$P2.keychain-db ]] \
  && ok "import auto-created target keychain" || bad "import auto-created target keychain"
[[ "$(secret get TEST_ALPHA -p $P2)" == "$V1" ]] && ok "env round-trip special chars" || bad "env round-trip special chars"

# --- export --all spans every registered keychain ---
secret export --all --format json -o "$TD/all.json" >/dev/null 2>&1 \
  && ok "export --all" || bad "export --all"
jq -e "[.items[].project] | (index(\"$P\") != null) and (index(\"$P2\") != null)" "$TD/all.json" >/dev/null 2>&1 \
  && ok "export --all spans keychains" || bad "export --all spans keychains"

# --- age round trip (recipient/identity so it runs non-interactively) ---
age-keygen -o "$TD/key.txt" >/dev/null 2>&1
rec=$(awk '/public key/ {print $NF}' "$TD/key.txt")
SECRET_AGE_ARGS="-r $rec" secret export -p $P -o "$TD/x.json.age" >/dev/null 2>&1 \
  && ok "export age" || bad "export age"
[[ "$(head -c 21 "$TD/x.json.age" 2>/dev/null)" == 'age-encryption.org/v1' ]] \
  && ok "age file is encrypted" || bad "age file is encrypted"
SECRET_AGE_DECRYPT_ARGS="-i $TD/key.txt" secret import "$TD/x.json.age" -p $P3 >/dev/null 2>&1 \
  && ok "import age" || bad "import age"
[[ "$(secret get TEST_ALPHA -p $P3)" == "$V1" ]] && ok "age round-trip value" || bad "age round-trip value"

# --- format inference from -o suffix ---
secret export -p $P -o "$TD/infer.env" >/dev/null 2>&1
grep -q 'export TEST_ALPHA=' "$TD/infer.env" 2>/dev/null \
  && ok "format inferred from .env suffix" || bad "format inferred from .env suffix"

# --- update (partial) ---
print -r -- 'rotated-789' | secret update TEST_ALPHA -p $P --stdin >/dev/null \
  && ok "update value via stdin" || bad "update value via stdin"
[[ "$(secret get TEST_ALPHA -p $P)" == 'rotated-789' ]] \
  && ok "updated value readable" || bad "updated value readable"
upshow=$(secret show TEST_ALPHA -p $P)
[[ $upshow == *'comment with "quotes" and spaces'* ]] \
  && ok "value update keeps comment" || bad "value update keeps comment"
[[ $upshow =~ 'Kind:[[:space:]]+API KEY' ]] \
  && ok "value update keeps kind" || bad "value update keeps kind"
secret update TEST_ALPHA -p $P -j 'fresh comment' >/dev/null \
  && ok "update comment only" || bad "update comment only"
[[ "$(secret get TEST_ALPHA -p $P)" == 'rotated-789' ]] \
  && ok "comment update keeps value" || bad "comment update keeps value"
upshow=$(secret show TEST_ALPHA -p $P)
[[ $upshow == *'fresh comment'* ]] && ok "comment updated" || bad "comment updated"
[[ $upshow =~ 'Kind:[[:space:]]+API KEY' ]] \
  && ok "comment update keeps kind" || bad "comment update keeps kind"
secret update TEST_ALPHA -p $P -D 'token' >/dev/null \
  && ok "update kind only" || bad "update kind only"
upshow=$(secret show TEST_ALPHA -p $P)
[[ $upshow =~ 'Kind:[[:space:]]+TOKEN' ]] && ok "kind updated" || bad "kind updated"
[[ $upshow == *'fresh comment'* ]] && ok "kind update keeps comment" || bad "kind update keeps comment"
[[ "$(secret get TEST_ALPHA -p $P)" == 'rotated-789' ]] \
  && ok "kind update keeps value" || bad "kind update keeps value"
secret update TEST_ALPHA -p $P -D '  private   key ' >/dev/null \
  && ok "update messy kind" || bad "update messy kind"
[[ "$(secret show TEST_ALPHA -p $P)" =~ 'Kind:[[:space:]]+PRIVATE KEY' ]] \
  && ok "kind normalised on write (case + whitespace)" || bad "kind normalised on write (case + whitespace)"
secret update TEST_ALPHA -p $P -j '' >/dev/null \
  && ok "update clears comment with -j ''" || bad "update clears comment with -j ''"
[[ "$(secret show TEST_ALPHA -p $P)" != *'fresh comment'* ]] \
  && ok "comment cleared" || bad "comment cleared"
secret update TEST_ALPHA -p $P >/dev/null 2>&1 \
  && bad "update with no flags fails" || ok "update with no flags fails"
secret update TEST_NOPE -p $P -j 'x' >/dev/null 2>&1 \
  && bad "update of missing item fails" || ok "update of missing item fails"

# --- project resolution: git config secret.project + toplevel basename ---
mkdir -p "$TD/repo-a" "$TD/repo-b" "$TD/$PREPO"
( cd "$TD/repo-a" && git init -q . && git config secret.project $PMAP \
  && print -r -- 'map-v1' | secret set MAP_ONE --stdin >/dev/null 2>&1 ) \
  && ok "set resolves project from git config" || bad "set resolves project from git config"
[[ -e $HOME/Library/Keychains/$PMAP.keychain-db ]] \
  && ok "mapped project got its own keychain" || bad "mapped project got its own keychain"
( cd "$TD/repo-b" && git init -q . && git config secret.project $PMAP \
  && [[ "$(secret get MAP_ONE)" == 'map-v1' ]] ) \
  && ok "second repo shares the mapped project" || bad "second repo shares the mapped project"
( cd "$TD/$PREPO" && git init -q . \
  && print -r -- 'repo-v' | secret set REPO_ONE --stdin >/dev/null 2>&1 \
  && [[ "$(secret get REPO_ONE)" == 'repo-v' ]] ) \
  && ok "project falls back to git toplevel name" || bad "project falls back to git toplevel name"
[[ -e $HOME/Library/Keychains/$PREPO.keychain-db ]] \
  && ok "toplevel project got its own keychain" || bad "toplevel project got its own keychain"

# --- scopes: per-repository overrides inside one project ---
( cd "$TD/repo-a" \
  && print -r -- 'shared-db' | secret set DB_URL --stdin >/dev/null 2>&1 \
  && print -r -- 'scoped-a'  | secret set DB_URL -S --stdin >/dev/null 2>&1 ) \
  && ok "set shared and scoped same NAME" || bad "set shared and scoped same NAME"
( cd "$TD/repo-b" && print -r -- 'scoped-b' | secret set DB_URL -S --stdin >/dev/null 2>&1 ) \
  && ok "set scoped in second repo" || bad "set scoped in second repo"
[[ "$(cd "$TD/repo-a" && secret get DB_URL)" == 'scoped-a' ]] \
  && ok "get prefers the repo scope" || bad "get prefers the repo scope"
[[ "$(cd "$TD/repo-b" && secret get DB_URL)" == 'scoped-b' ]] \
  && ok "scopes are isolated between repos" || bad "scopes are isolated between repos"
[[ "$(cd "$TD/repo-a" && secret get DB_URL --shared)" == 'shared-db' ]] \
  && ok "--shared forces the shared layer" || bad "--shared forces the shared layer"
[[ "$(cd "$TD/repo-a" && secret get DB_URL --scope repo-b)" == 'scoped-b' ]] \
  && ok "--scope X targets another scope" || bad "--scope X targets another scope"
[[ "$(secret get DB_URL -p $PMAP)" == 'shared-db' ]] \
  && ok "no matching scope falls back to shared" || bad "no matching scope falls back to shared"
[[ "$(cd "$TD/repo-a" && secret get MAP_ONE)" == 'map-v1' ]] \
  && ok "scoped lookup falls through to shared" || bad "scoped lookup falls through to shared"

lsout=$(secret ls -p $PMAP)
[[ $lsout == *'repo-a/DB_URL'* && $lsout == *'repo-b/DB_URL'* ]] \
  && ok "ls shows scope prefixes" || bad "ls shows scope prefixes"
lslong=$(secret ls -p $PMAP --long)
[[ $lslong =~ 'DB_URL[[:space:]]+repo-a[[:space:]]' ]] \
  && ok "ls --long puts scope in its own column" || bad "ls --long puts scope in its own column"
showsc=$(cd "$TD/repo-a" && secret show DB_URL)
[[ $showsc =~ 'Scope:[[:space:]]+repo-a' ]] && ok "show reports the scope" || bad "show reports the scope"
[[ "$(print -r -- "$showsc" | awk '/^Label:/ {print $2}')" == 'repo-a/DB_URL' ]] \
  && ok "scoped label is scope/NAME" || bad "scoped label is scope/NAME"

envsc=$(cd "$TD/repo-a" && secret env)
( eval "$envsc"; [[ "$DB_URL" == 'scoped-a' && "$MAP_ONE" == 'map-v1' ]] ) \
  && ok "env overlays scoped over shared" || bad "env overlays scoped over shared"
[[ "$(print -r -- "$envsc" | grep -c '^export ')" == 2 ]] \
  && ok "env emits each name once" || bad "env emits each name once"
envb=$(cd "$TD/repo-a" && secret env --scope repo-b)
( eval "$envb"; [[ "$DB_URL" == 'scoped-b' ]] ) \
  && ok "env --scope X overlays that scope" || bad "env --scope X overlays that scope"

( cd "$TD/repo-a" && secret update DB_URL -j 'scoped note' >/dev/null 2>&1 ) \
  && ok "update targets the scoped layer (DWIM)" || bad "update targets the scoped layer (DWIM)"
[[ "$(cd "$TD/repo-a" && secret show DB_URL)" == *'scoped note'* ]] \
  && ok "scoped comment updated" || bad "scoped comment updated"
[[ "$(cd "$TD/repo-a" && secret show DB_URL --shared)" != *'scoped note'* ]] \
  && ok "shared layer untouched by scoped update" || bad "shared layer untouched by scoped update"

secret export -p $PMAP --format json -o "$TD/scoped.json" >/dev/null 2>&1
jq -e '.items[] | select(.name == "DB_URL" and .scope == "repo-a")' "$TD/scoped.json" >/dev/null 2>&1 \
  && ok "export json records scope" || bad "export json records scope"
jq -e '.items[] | select(.name == "DB_URL" and .scope == "")' "$TD/scoped.json" >/dev/null 2>&1 \
  && ok "export json records shared layer" || bad "export json records shared layer"
( cd "$TD/repo-a" && secret rm DB_URL -S -f >/dev/null 2>&1 ) \
  && ok "rm -S removes the scoped item" || bad "rm -S removes the scoped item"
[[ "$(cd "$TD/repo-a" && secret get DB_URL)" == 'shared-db' ]] \
  && ok "shared survives scoped rm" || bad "shared survives scoped rm"
secret import "$TD/scoped.json" >/dev/null 2>&1
[[ "$(cd "$TD/repo-a" && secret get DB_URL)" == 'scoped-a' ]] \
  && ok "import restores the scope layer" || bad "import restores the scope layer"
( cd "$TD/repo-a" && secret rm DB_URL -f >/dev/null 2>&1 )
[[ "$(cd "$TD/repo-a" && secret get DB_URL)" == 'shared-db' ]] \
  && ok "rm DWIM removes scoped first" || bad "rm DWIM removes scoped first"
( cd "$TD/repo-a" && secret rm DB_URL -f >/dev/null 2>&1 )
( cd "$TD/repo-a" && secret get DB_URL >/dev/null 2>&1 ) \
  && bad "rm falls back to shared" || ok "rm falls back to shared"
( cd "$TD" && print -r -- 'v' | secret set SC_ERR -p $PMAP -S --stdin >/dev/null 2>&1 ) \
  && bad "-S outside a repository fails" || ok "-S outside a repository fails"

# --- link ---
linkshow=$(cd "$TD/$PREPO" && secret link)
[[ $linkshow == *"project:    $PREPO"* && $linkshow == *'repository name'* ]] \
  && ok "link shows resolution" || bad "link shows resolution"
( cd "$TD/$PREPO" && secret link $PMAP >/dev/null 2>&1 ) \
  && ok "link sets the mapping" || bad "link sets the mapping"
[[ "$(git -C "$TD/$PREPO" config --get secret.project)" == "$PMAP" ]] \
  && ok "link writes git config" || bad "link writes git config"
[[ "$(cd "$TD/$PREPO" && secret link)" == *'git config secret.project'* ]] \
  && ok "link reports git config source" || bad "link reports git config source"
( cd "$TD/$PREPO" && secret link --unset >/dev/null 2>&1 ) \
  && ok "link --unset" || bad "link --unset"
git -C "$TD/$PREPO" config --get secret.project >/dev/null 2>&1 \
  && bad "unset removes git config" || ok "unset removes git config"
( cd "$TD" && secret link somewhere >/dev/null 2>&1 ) \
  && bad "link outside a repository fails" || ok "link outside a repository fails"

# --- unregistered existing keychain file: writes are refused ---
security create-keychain -p testpass "$KCP2" 2>/dev/null
projarr2=(${(f)"$(secret projects)"})
if (( ${projarr2[(Ie)$KCN2]} )); then
  bad "projects omits unregistered keychain"
else
  ok "projects omits unregistered keychain"
fi
print -r -- 'unlisted-v' | secret set KC_UL -p $KCN2 --stdin >/dev/null 2>&1 \
  && bad "write to unregistered file refused" || ok "write to unregistered file refused"
security find-generic-password -s "secret.$KCN2" -a KC_UL "$KCP2" >/dev/null 2>&1 \
  && bad "nothing written into unregistered file" || ok "nothing written into unregistered file"
security find-generic-password -s "secret.$KCN2" -a KC_UL "$DKC" >/dev/null 2>&1 \
  && bad "nothing leaked into login" || ok "nothing leaked into login"
secret keychain register $KCN2 >/dev/null 2>&1 && ok "keychain register" || bad "keychain register"
security unlock-keychain -p testpass "$KCP2" 2>/dev/null
print -r -- 'unlisted-v' | secret set KC_UL -p $KCN2 --stdin >/dev/null 2>&1 \
  && ok "write works after register" || bad "write works after register"
[[ "$(secret get KC_UL -p $KCN2)" == 'unlisted-v' ]] \
  && ok "read works after register" || bad "read works after register"
security delete-keychain "$KCP2" >/dev/null 2>&1

# --- -k default escape hatch (login keychain) ---
print -r -- 'kc-value-2' | secret -k default set KC_TWO -p $KCN --stdin >/dev/null 2>&1
security find-generic-password -s "secret.$KCN" -a KC_TWO "$DKC" >/dev/null 2>&1 \
  && ok "-k default stores in login" || bad "-k default stores in login"
[[ "$(secret -k default get KC_TWO -p $KCN)" == 'kc-value-2' ]] \
  && ok "-k default get" || bad "-k default get"
[[ "$(secret -k default show KC_TWO -p $KCN | awk '/^Label:/ {print $2}')" == "$KCN/KC_TWO" ]] \
  && ok "label prefixed outside own keychain" || bad "label prefixed outside own keychain"

# --- fixture keychain with its own password + remember/auto-unlock ---
security create-keychain -p testpass "$KCP" 2>/dev/null \
  && ok "fixture: create keychain" || bad "fixture: create keychain"
secret keychain register $KCN >/dev/null 2>&1
security unlock-keychain -p testpass "$KCP" 2>/dev/null
print -r -- 'kc-value-1' | secret set KC_ONE -p $KCN --stdin >/dev/null 2>&1 \
  && ok "set into registered fixture" || bad "set into registered fixture"
print -r -- 'wrongpass' | secret keychain remember $KCN --stdin >/dev/null 2>&1 \
  && bad "remember rejects wrong password" || ok "remember rejects wrong password"
security unlock-keychain -p testpass "$KCP" 2>/dev/null
print -r -- 'testpass' | secret keychain remember $KCN --stdin >/dev/null 2>&1 \
  && ok "keychain remember --stdin" || bad "keychain remember --stdin"
security find-generic-password -s 'keychain-password' -a $KCN -w "$DKC" >/dev/null 2>&1 \
  && ok "unlock password stored in login" || bad "unlock password stored in login"
secret keychain lock $KCN >/dev/null 2>&1
[[ "$(secret get KC_ONE -p $KCN)" == 'kc-value-1' ]] \
  && ok "auto-unlock via individual item" || bad "auto-unlock via individual item"
lockedls=$(secret keychain lock $KCN >/dev/null 2>&1; secret ls -p $KCN)
[[ $lockedls == *KC_ONE* ]] && ok "auto-unlock covers ls/dump" || bad "auto-unlock covers ls/dump"
secret keychain forget $KCN >/dev/null 2>&1 && ok "keychain forget" || bad "keychain forget"
security find-generic-password -s 'keychain-password' -a $KCN "$DKC" >/dev/null 2>&1 \
  && bad "forget removed login item" || ok "forget removed login item"
security unlock-keychain -p testpass "$KCP" 2>/dev/null

# --- master adoption (fixture has a different password + stored item) ---
print -r -- 'testpass' | secret keychain remember $KCN --stdin >/dev/null 2>&1
msetout=$(print -r -- "$MP" | secret keychain master set --stdin 2>&1) \
  && ok "master set (adoption run)" || bad "master set (adoption run)"
[[ $msetout == *adopted:*$KCN* ]] \
  && ok "master set adopts via stored item" || bad "master set adopts via stored item"
security find-generic-password -s 'keychain-password' -a $KCN "$DKC" >/dev/null 2>&1 \
  && bad "adoption removes individual item" || ok "adoption removes individual item"
secret keychain lock $KCN >/dev/null 2>&1
[[ "$(secret get KC_ONE -p $KCN)" == 'kc-value-1' ]] \
  && ok "auto-unlock via master fallback" || bad "auto-unlock via master fallback"
[[ "$(secret keychain master status)" == *'master: stored'* ]] \
  && ok "master status shows stored" || bad "master status shows stored"

# --- keychain create (headless thanks to master) ---
secret keychain create $KCN3 --no-autolock >/dev/null 2>&1 \
  && ok "headless create via master" || bad "headless create via master"
[[ -e $KCP3 ]] && ok "created keychain file exists" || bad "created keychain file exists"
print -r -- 'mkc-v' | secret set MK_ONE -p $KCN3 --stdin >/dev/null 2>&1
[[ "$(secret get MK_ONE -p $KCN3)" == 'mkc-v' ]] \
  && ok "master-created keychain usable" || bad "master-created keychain usable"

# --- keychain subcommands ---
kcls=$(secret keychain ls)
[[ $kcls == *$KCN* ]] && ok "keychain ls lists custom" || bad "keychain ls lists custom"
[[ $kcls == *'(default)'* ]] && ok "keychain ls marks default" || bad "keychain ls marks default"
[[ "$(secret keychain info $KCN 2>&1)" == *"$KCP"* ]] \
  && ok "keychain info shows path" || bad "keychain info shows path"
secret keychain lock $KCN >/dev/null 2>&1 && ok "keychain lock" || bad "keychain lock"
security unlock-keychain -p "$MP" "$KCP" 2>/dev/null
[[ "$(secret get KC_ONE -p $KCN)" == 'kc-value-1' ]] \
  && ok "readable after raw unlock" || bad "readable after raw unlock"

# --- master rotate ---
print -r -- "$MP2" | secret keychain master rotate --stdin >/dev/null 2>&1 \
  && ok "master rotate --stdin" || bad "master rotate --stdin"
[[ "$(secret keychain master reveal)" == "$MP2" ]] \
  && ok "reveal shows rotated value" || bad "reveal shows rotated value"
secret keychain lock $KCN >/dev/null 2>&1
[[ "$(secret get KC_ONE -p $KCN)" == 'kc-value-1' ]] \
  && ok "unlock works after rotate" || bad "unlock works after rotate"
security lock-keychain "$KCP" 2>/dev/null
print -r -- "unlock-keychain -p \"$MP\" \"$KCP\"" | security -i >/dev/null 2>&1 \
  && bad "old master password rejected" || ok "old master password rejected"
print -r -- "unlock-keychain -p \"$MP2\" \"$KCP\"" | security -i >/dev/null 2>&1

# --- master forget + no-master behaviour ---
secret keychain master forget >/dev/null 2>&1 && ok "master forget" || bad "master forget"
secret keychain master reveal >/dev/null 2>&1 \
  && bad "reveal fails after forget" || ok "reveal fails after forget"
print -r -- 'v' | secret set NOM_ONE -p $PNOM --stdin >/dev/null 2>&1 \
  && bad "headless write without master fails" || ok "headless write without master fails"
[[ ! -e $HOME/Library/Keychains/$PNOM.keychain-db ]] \
  && ok "no keychain created without master" || bad "no keychain created without master"

# --- keychain rm ---
secret keychain rm $KCN3 -f >/dev/null 2>&1 && ok "keychain rm" || bad "keychain rm"
[[ ! -e $KCP3 ]] && ok "keychain file removed" || bad "keychain file removed"
secret keychain rm $KCN3 -f >/dev/null 2>&1 \
  && bad "keychain rm of missing fails" || ok "keychain rm of missing fails"

print ''
if (( fails == 0 )); then
  print -r -- "ALL TESTS PASSED"
else
  print -r -- "$fails TEST(S) FAILED"
fi
exit $fails
