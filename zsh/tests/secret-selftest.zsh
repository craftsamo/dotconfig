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
#
# It tests the secret.zsh of its own checkout, so a worktree runs its own.
emulate -L zsh
setopt pipefail
source "${${(%):-%x}:A:h}/../functions/secret.zsh"

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
[[ $longout == "$P"$'\n''    NAME'*'KIND'*'ENV  MODIFIED'*$'\n''  shared'$'\n'* ]] \
  && ok "ls --long opens with the project, a column header and the shared group" || bad "ls --long opens with the project, a column header and the shared group"
[[ $longout =~ $'\n''    TEST_BETA[[:space:]]+ENV[[:space:]]+yes[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}' ]] \
  && ok "ls --long rows: name, kind, env, date" || bad "ls --long rows: name, kind, env, date"
# a name longer than the old fixed width must not misalign its row (auto-size)
print -r -- 'v' | secret set TEST_LONG_VARIABLE_NAME_FOR_ALIGNMENT -p $P -D token --stdin >/dev/null 2>&1
[[ "$(secret ls -p $P --long)" =~ 'TEST_LONG_VARIABLE_NAME_FOR_ALIGNMENT[[:space:]]+TOKEN' ]] \
  && ok "ls --long auto-sizes a long name" || bad "ls --long auto-sizes a long name"
secret rm TEST_LONG_VARIABLE_NAME_FOR_ALIGNMENT -p $P -f >/dev/null 2>&1
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
# one invocation unlocks a keychain once, however many values it reads:
# shadow `security` to count the unlock (-i) and the password lookups
security() {
  local tag=$1
  [[ $1 == find-generic-password && $3 == keychain-password ]] && tag=pw-lookup
  print -r -- "$tag" >> "$TD/seccalls"
  command security "$@"
}
: > "$TD/seccalls"
[[ "$(secret env -p $P)" == *TEST_ALPHA*TEST_BETA* ]] \
  && ok "env still emits both items under the counting shim" || bad "env still emits both items under the counting shim"
(( $(grep -c '^-i$' "$TD/seccalls") == 1 )) && ok "env unlocks the keychain once" || bad "env unlocks the keychain once ($(grep -c '^-i$' "$TD/seccalls"))"
(( $(grep -c '^pw-lookup$' "$TD/seccalls") <= 2 )) && ok "env looks the unlock password up once" || bad "env looks the unlock password up once ($(grep -c '^pw-lookup$' "$TD/seccalls"))"
: > "$TD/seccalls"
secret export -p $P --format json -o "$TD/cnt.json" >/dev/null 2>&1
(( $(grep -c '^-i$' "$TD/seccalls") == 1 )) && ok "export unlocks the keychain once" || bad "export unlocks the keychain once ($(grep -c '^-i$' "$TD/seccalls"))"
unfunction security; rm -f "$TD/cnt.json"

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
[[ $lslong == *$'\n''  repo-a/'$'\n''    DB_URL'*$'\n''  repo-b/'$'\n''    DB_URL'* ]] \
  && ok "ls --long groups items under their scope" || bad "ls --long groups items under their scope"
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

# --- env=no (--no-env): readable by get, never emitted by env ---
SEED='word word word word word word word word word word word seed'
print -r -- "$SEED" | secret set TEST_SEED -p $P -D mnemonic -j 'wallet' --no-env --stdin >/dev/null 2>&1 \
  && ok "set --no-env" || bad "set --no-env"
[[ "$(secret get TEST_SEED -p $P)" == "$SEED" ]] && ok "get reads a --no-env item" || bad "get reads a --no-env item"
neout=$(secret env -p $P)
[[ $neout != *TEST_SEED* && $neout != *"$SEED"* ]] && ok "env skips a --no-env item" || bad "env skips a --no-env item"
[[ $neout == *TEST_ALPHA* ]] && ok "env still emits other items" || bad "env still emits other items"
[[ "$(secret ls -p $P --long)" =~ 'TEST_SEED[[:space:]]+MNEMONIC[[:space:]]+no[[:space:]]+[0-9-]+[[:space:]]+wallet' ]] \
  && ok "ls --long shows ENV no" || bad "ls --long shows ENV no"
[[ "$(secret show TEST_SEED -p $P)" =~ 'Env:[[:space:]]+no' ]] && ok "show shows Env no" || bad "show shows Env no"
print -r -- "$SEED" | secret set TEST_SEED -p $P -D mnemonic --stdin >/dev/null 2>&1
[[ "$(secret env -p $P)" != *TEST_SEED* ]] && ok "rewriting the value keeps env=no" || bad "rewriting the value keeps env=no"
secret update TEST_SEED -p $P -j 'renamed memo' >/dev/null 2>&1
[[ "$(secret env -p $P)" != *TEST_SEED* ]] && ok "a comment update keeps env=no" || bad "a comment update keeps env=no"
secret export -p $P --format json -o "$TD/noenv.json" >/dev/null 2>&1
jq -e '.items[] | select(.name == "TEST_SEED") | .env == "no"' "$TD/noenv.json" >/dev/null 2>&1 \
  && ok "json export carries env no" || bad "json export carries env no"
secret export -p $P --format env -o "$TD/noenv.env" >/dev/null 2>&1
grep -q '^#no-env# export TEST_SEED=' "$TD/noenv.env" 2>/dev/null \
  && ok "env export comments out a --no-env item" || bad "env export comments out a --no-env item"
( source "$TD/noenv.env"; [[ -z ${TEST_SEED-} ]] ) \
  && ok "sourcing an env export never exports it" || bad "sourcing an env export never exports it"

# --- non-ASCII attributes (security dumps them as hex) read back as text ---
print -r -- 'v' | secret set TEST_UTF8 -p $P -j 'テスト用 · memo' --stdin >/dev/null 2>&1
[[ "$(secret ls -p $P --long)" == *'テスト用 · memo'* ]] \
  && ok "ls --long shows a non-ASCII comment as text" || bad "ls --long shows a non-ASCII comment as text"
[[ "$(secret show TEST_UTF8 -p $P)" == *'テスト用 · memo'* ]] \
  && ok "show shows a non-ASCII comment as text" || bad "show shows a non-ASCII comment as text"
secret rm TEST_UTF8 -p $P -f >/dev/null 2>&1

# --- set --new: create-only ---
print -r -- 'other value' | secret set TEST_SEED -p $P -D mnemonic --new --stdin >/dev/null 2>&1 \
  && bad "--new refuses an existing item" || ok "--new refuses an existing item"
[[ "$(secret get TEST_SEED -p $P)" == "$SEED" ]] && ok "--new leaves the existing value" || bad "--new leaves the existing value"
# past the pre-check (an item that appeared after it): security itself refuses without -U
print -r -- 'other value' | _secret_store TEST_SEED $P '' mnemonic '' keep keep new >/dev/null 2>&1 \
  && bad "a create-only write refuses an existing item" || ok "a create-only write refuses an existing item"
[[ "$(secret get TEST_SEED -p $P)" == "$SEED" ]] \
  && ok "a create-only write leaves the existing value" || bad "a create-only write leaves the existing value"
print -r -- 'fresh value' | secret set TEST_FRESH -p $P --scope newscope --new --no-env --stdin >/dev/null 2>&1 \
  && ok "--new stores a new item" || bad "--new stores a new item"
[[ "$(secret get TEST_FRESH -p $P --scope newscope)" == 'fresh value' ]] \
  && ok "--new item reads back" || bad "--new item reads back"
secret rm TEST_SEED -p $P -f >/dev/null 2>&1
secret import "$TD/noenv.json" -y >/dev/null 2>&1
[[ "$(secret env -p $P)" != *TEST_SEED* && "$(secret get TEST_SEED -p $P)" == "$SEED" ]] \
  && ok "json import restores env=no" || bad "json import restores env=no"
secret rm TEST_SEED -p $P -f >/dev/null 2>&1
secret import "$TD/noenv.env" -p $P -y >/dev/null 2>&1
[[ "$(secret env -p $P)" != *TEST_SEED* && "$(secret get TEST_SEED -p $P)" == "$SEED" ]] \
  && ok "env import restores env=no from the marker" || bad "env import restores env=no from the marker"
secret update TEST_SEED -p $P --env >/dev/null 2>&1
[[ "$(secret env -p $P)" == *TEST_SEED* ]] && ok "update --env lifts it" || bad "update --env lifts it"
secret rm TEST_SEED -p $P -f >/dev/null 2>&1

# --- ENV lives in the type code (envn/envy), never in the generic attribute ---
kcdump() { security dump-keychain "$HOME/Library/Keychains/$P.keychain-db" 2>/dev/null \
  | awk -v n="$1" '/^class:/{blk=""} {blk=blk"\n"$0} /"type"|"gena"/{ if (blk ~ "\"acct\"<blob>=\"" n "\"") print $0 }'; }
print -r -- 'v' | secret set TEST_TYPE -p $P --no-env --stdin >/dev/null 2>&1
[[ "$(kcdump TEST_TYPE)" == *'"type"<uint32>="envn"'* ]] && ok "--no-env writes type envn" || bad "--no-env writes type envn"
[[ "$(kcdump TEST_TYPE)" != *'env=no'* ]] && ok "--no-env leaves the generic attribute alone" || bad "--no-env leaves the generic attribute alone"
secret update TEST_TYPE -p $P --env >/dev/null 2>&1
[[ "$(kcdump TEST_TYPE)" == *'"type"<uint32>="envy"'* ]] && ok "--env writes type envy" || bad "--env writes type envy"
secret rm TEST_TYPE -p $P -f >/dev/null 2>&1

# --- meta: structured KEY=VALUE fields in the generic attribute ---
print -r -- 'v' | secret set TEST_META -p $P --meta 'url=https://example.com/a?b=1' --meta account=ops -j 'memo' --stdin >/dev/null 2>&1 \
  && ok "set --meta" || bad "set --meta"
[[ "$(kcdump TEST_META)" == *'"gena"<blob>="account=ops;url=https://example.com/a?b=1"'* ]] \
  && ok "meta is stored sorted by key" || bad "meta is stored sorted by key"
metashow=$(secret show TEST_META -p $P)
[[ $metashow =~ 'Meta:[[:space:]]+account=ops' && $metashow == *'url=https://example.com/a?b=1'* ]] \
  && ok "show lists meta fields" || bad "show lists meta fields"
[[ "$(secret ls -p $P --long)" =~ 'TEST_META[[:space:]]+ENV[[:space:]]+yes[[:space:]]+[0-9-]+[[:space:]]+account=ops;url=https://example.com/a\?b=1[[:space:]]+memo' ]] \
  && ok "ls --long has a META column" || bad "ls --long has a META column"
[[ "$(secret ls -p $P --meta account)" == TEST_META ]] && ok "ls --meta KEY filters" || bad "ls --meta KEY filters"
[[ "$(secret ls -p $P --meta account=ops --meta url)" == TEST_META ]] && ok "ls --meta stacks filters" || bad "ls --meta stacks filters"
# width: META and COMMENT are cut with an ellipsis so no row exceeds COLUMNS; --wide never cuts
print -r -- 'v' | secret set TEST_WIDE -p $P --meta 'url=https://example.com/a/very/long/path/that/keeps/going/and/going' -j 'a comment that is also rather long for a narrow terminal' --stdin >/dev/null 2>&1
wideout=$(COLUMNS=72 secret ls -p $P --long)
widest=0; for wl in ${(f)wideout}; do (( ${#wl} > widest )) && widest=${#wl}; done
(( widest <= 72 )) && ok "ls --long fits COLUMNS" || bad "ls --long fits COLUMNS (widest $widest)"
[[ $wideout =~ 'TEST_WIDE[[:space:]]+ENV[[:space:]]+yes[[:space:]]+[0-9-]+[[:space:]]+url=https://[^ ]*…[[:space:]]+a comment[^\n]*…' ]] \
  && ok "ls --long cuts meta and comment with an ellipsis" || bad "ls --long cuts meta and comment with an ellipsis"
[[ "$(COLUMNS=72 secret ls -p $P --long --wide)" == *'url=https://example.com/a/very/long/path/that/keeps/going/and/going  a comment that is also rather long for a narrow terminal'* ]] \
  && ok "ls --long --wide keeps everything" || bad "ls --long --wide keeps everything"
[[ "$(COLUMNS=72 secret ls -p $P --long)" != *' '$'\n'* ]] && ok "ls --long rows carry no trailing blanks" || bad "ls --long rows carry no trailing blanks"
[[ "$(COLUMNS=72 secret ls -p $P --long)" =~ $'\n''    NAME[[:space:]]+KIND  ENV  MODIFIED[[:space:]]+META[[:space:]]+COMMENT'$'\n' ]] \
  && ok "ls --long heads META and COMMENT when present" || bad "ls --long heads META and COMMENT when present"
secret rm TEST_WIDE -p $P -f >/dev/null 2>&1
# --all spans every registered keychain, prefixing the project
allout=$(secret ls --all)
[[ $allout == *"$P/TEST_META"* && $allout == *"$P2/"* ]] && ok "ls --all prefixes tokens with the project" || bad "ls --all prefixes tokens with the project"
alllong=$(secret ls --all --long)
[[ "$(secret ls -p $P2 --long)" != *META* ]] \
  && ok "ls --long omits META/COMMENT headers when the project has none" || bad "ls --long omits META/COMMENT headers when the project has none"
[[ $alllong == "$P"$'\n''    NAME'*$'\n''  shared'* && $alllong == *$'\n'"$P2"$'\n''    NAME'*$'\n''  shared'* ]] \
  && ok "ls --all --long blocks per project" || bad "ls --all --long blocks per project"
[[ "$(secret ls -p $P --meta account --long | head -1)" == "$P" ]] \
  && ok "ls --meta --long starts with the header" || bad "ls --meta --long starts with the header"
[[ -z "$(secret ls -p $P --meta account=dev 2>/dev/null)" ]] && ok "ls --meta KEY=VALUE mismatch hides" || bad "ls --meta KEY=VALUE mismatch hides"
secret ls -p $P --meta env >/dev/null 2>&1 && bad "ls --meta rejects the reserved key" || ok "ls --meta rejects the reserved key"
secret update TEST_META -p $P --meta url= --meta zone=eu >/dev/null 2>&1 && ok "update --meta" || bad "update --meta"
[[ "$(kcdump TEST_META)" == *'"gena"<blob>="account=ops;zone=eu"'* ]] \
  && ok "update --meta KEY= removes, KEY=VALUE adds" || bad "update --meta KEY= removes, KEY=VALUE adds"
print -r -- 'v2' | secret set TEST_META -p $P --stdin >/dev/null 2>&1
[[ "$(kcdump TEST_META)" == *'account=ops;zone=eu'* ]] && ok "a value rewrite keeps meta" || bad "a value rewrite keeps meta"
secret update TEST_META -p $P --meta 'bad key=1' >/dev/null 2>&1 && bad "rejects a meta key with spaces" || ok "rejects a meta key with spaces"
secret update TEST_META -p $P --meta 'x=a;b' >/dev/null 2>&1 && bad "rejects ';' in a meta value" || ok "rejects ';' in a meta value"
secret update TEST_META -p $P --meta env=no >/dev/null 2>&1 && bad "rejects the reserved meta key env" || ok "rejects the reserved meta key env"
secret update TEST_META -p $P --meta novalue >/dev/null 2>&1 && bad "rejects --meta without '='" || ok "rejects --meta without '='"
secret export -p $P --format json -o "$TD/meta.json" >/dev/null 2>&1
[[ "$(jq -r '.items[] | select(.name == "TEST_META") | .meta.zone' "$TD/meta.json" 2>/dev/null)" == eu ]] \
  && ok "json export carries meta as an object" || bad "json export carries meta as an object"
secret export -p $P --format env -o "$TD/meta.env" >/dev/null 2>&1
grep -q '^#meta:account=ops;zone=eu$' "$TD/meta.env" 2>/dev/null \
  && ok "env export writes a #meta: line" || bad "env export writes a #meta: line"
( source "$TD/meta.env"; [[ ${TEST_META-} == v2 ]] ) \
  && ok "an env export with meta still sources" || bad "an env export with meta still sources"
secret rm TEST_META -p $P -f >/dev/null 2>&1
secret import "$TD/meta.json" -y >/dev/null 2>&1
[[ "$(kcdump TEST_META)" == *'"gena"<blob>="account=ops;zone=eu"'* ]] && ok "json import restores meta" || bad "json import restores meta"
secret rm TEST_META -p $P -f >/dev/null 2>&1
secret import "$TD/meta.env" -p $P -y >/dev/null 2>&1
[[ "$(kcdump TEST_META)" == *'"gena"<blob>="account=ops;zone=eu"'* ]] && ok "env import restores meta from the marker" || bad "env import restores meta from the marker"
secret rm TEST_META -p $P -f >/dev/null 2>&1

# --- migrate: the pre-type env=no marker moves into the type code ---
print -r -- "add-generic-password -U -a TEST_LEGACY -s secret.$P -l TEST_LEGACY -D ENV -j \"\" -G \"env=no;url=old\" -w legacy \"$HOME/Library/Keychains/$P.keychain-db\"" \
  | security -i >/dev/null 2>&1
[[ "$(secret env -p $P)" != *TEST_LEGACY* ]] && ok "a legacy env=no marker is still honoured" || bad "a legacy env=no marker is still honoured"
[[ "$(secret show TEST_LEGACY -p $P)" =~ 'Meta:[[:space:]]+url=old' ]] && ok "show hides the legacy marker from meta" || bad "show hides the legacy marker from meta"
[[ "$(secret migrate -p $P --dry-run)" == *'would migrate'*TEST_LEGACY* ]] && ok "migrate --dry-run lists it" || bad "migrate --dry-run lists it"
[[ "$(kcdump TEST_LEGACY)" == *'env=no'* ]] && ok "migrate --dry-run changes nothing" || bad "migrate --dry-run changes nothing"
secret migrate -p $P >/dev/null 2>&1 && ok "migrate" || bad "migrate"
legacydump=$(kcdump TEST_LEGACY)
[[ $legacydump == *'"type"<uint32>="envn"'* && $legacydump == *'"gena"<blob>="url=old"'* ]] \
  && ok "migrate sets envn and strips the marker" || bad "migrate sets envn and strips the marker"
[[ "$(secret get TEST_LEGACY -p $P)" == legacy ]] && ok "migrate keeps the value" || bad "migrate keeps the value"
[[ "$(secret env -p $P)" != *TEST_LEGACY* ]] && ok "migrated item is still hidden from env" || bad "migrated item is still hidden from env"
[[ "$(secret migrate -p $P)" == 'nothing to migrate'* ]] && ok "migrate is idempotent" || bad "migrate is idempotent"
# touching the meta of a not-yet-migrated item pins ENV into the type first
print -r -- "add-generic-password -U -a TEST_LEGACY2 -s secret.$P -l TEST_LEGACY2 -D ENV -j \"\" -G \"env=no\" -w legacy \"$HOME/Library/Keychains/$P.keychain-db\"" \
  | security -i >/dev/null 2>&1
secret update TEST_LEGACY2 -p $P --meta note=x >/dev/null 2>&1
legacydump=$(kcdump TEST_LEGACY2)
[[ $legacydump == *'"type"<uint32>="envn"'* && $legacydump == *'"gena"<blob>="note=x"'* ]] \
  && ok "a meta edit on a legacy item keeps env=no via the type" || bad "a meta edit on a legacy item keeps env=no via the type"
# a type set after the marker (update --env) stays authoritative: migrate only drops the marker
print -r -- "add-generic-password -U -a TEST_LEGACY3 -s secret.$P -l TEST_LEGACY3 -D ENV -j \"\" -G \"env=no\" -C envy -w legacy \"$HOME/Library/Keychains/$P.keychain-db\"" \
  | security -i >/dev/null 2>&1
[[ "$(secret env -p $P)" == *TEST_LEGACY3* ]] && ok "type envy beats a stale env=no marker" || bad "type envy beats a stale env=no marker"
secret migrate -p $P >/dev/null 2>&1
legacydump=$(kcdump TEST_LEGACY3)
[[ $legacydump == *'"type"<uint32>="envy"'* && $legacydump != *'env=no'* ]] \
  && ok "migrate keeps envy and strips the stale marker" || bad "migrate keeps envy and strips the stale marker"
secret rm TEST_LEGACY -p $P -f >/dev/null 2>&1
secret rm TEST_LEGACY2 -p $P -f >/dev/null 2>&1
secret rm TEST_LEGACY3 -p $P -f >/dev/null 2>&1

# --- untrusted JSON meta is validated field by field ---
print -r -- '{"items":[{"name":"TEST_BADMETA","value":"v","project":"'$P'","meta":{"url":"a;b=c"}}]}' > "$TD/badmeta.json"
secret import "$TD/badmeta.json" -y >/dev/null 2>&1 && bad "json import rejects ';' inside a meta value" || ok "json import rejects ';' inside a meta value"
secret show TEST_BADMETA -p $P >/dev/null 2>&1 && bad "a rejected item is not stored" || ok "a rejected item is not stored"
print -r -- '{"items":[{"name":"TEST_BADMETA","value":"v","project":"'$P'","meta":{"a=b":"c"}}]}' > "$TD/badmeta.json"
secret import "$TD/badmeta.json" -y >/dev/null 2>&1 && bad "json import rejects a meta key with '='" || ok "json import rejects a meta key with '='"
print -r -- '{"items":[{"name":"TEST_BADMETA","value":"v","project":"'$P'","meta":{"env":"no"}}]}' > "$TD/badmeta.json"
secret import "$TD/badmeta.json" -y >/dev/null 2>&1 && bad "json import rejects the reserved meta key env" || ok "json import rejects the reserved meta key env"
secret rm TEST_BADMETA -p $P -f >/dev/null 2>&1

# --- stages: per-environment layers on top of scopes ---
unset SECRET_STAGE
print -r -- 'db-shared' | secret set ST_DB -p $P --stdin >/dev/null 2>&1
print -r -- 'db-api' | secret set ST_DB -p $P --scope api --stdin >/dev/null 2>&1
print -r -- 'db-prod' | secret set ST_DB -p $P --stage prod --stdin >/dev/null 2>&1 \
  && ok "set --stage" || bad "set --stage"
print -r -- 'db-api-prod' | secret set ST_DB -p $P --scope api --stage prod --stdin >/dev/null 2>&1 \
  && ok "set --scope --stage" || bad "set --scope --stage"
print -r -- 'log-shared' | secret set ST_LOG -p $P --stdin >/dev/null 2>&1
print -r -- 'tok-test' | secret set ST_TOK -p $P --stage test --stdin >/dev/null 2>&1
print -r -- 'hid-prod' | secret set ST_HID -p $P --stage prod --no-env --stdin >/dev/null 2>&1
print -r -- 'hid-shared' | secret set ST_HID -p $P --stdin >/dev/null 2>&1
security find-generic-password -s "secret.$P@prod" -a ST_DB "$HOME/Library/Keychains/$P.keychain-db" >/dev/null 2>&1 \
  && ok "a staged item lives in service secret.<project>@<stage>" || bad "a staged item lives in service secret.<project>@<stage>"
security find-generic-password -s "secret.$P/api@prod" -a ST_DB "$HOME/Library/Keychains/$P.keychain-db" >/dev/null 2>&1 \
  && ok "a scoped staged item lives in secret.<project>/<scope>@<stage>" || bad "a scoped staged item lives in secret.<project>/<scope>@<stage>"
[[ "$(secret show ST_DB -p $P --scope api --stage prod)" =~ 'Label:[[:space:]]+api/ST_DB@prod' ]] \
  && ok "label carries scope and stage" || bad "label carries scope and stage"
# get: DWIM and exact
[[ "$(secret get ST_DB -p $P)" == db-shared ]] && ok "get without a stage reads the stage-less layer" || bad "get without a stage reads the stage-less layer"
[[ "$(secret get ST_DB -p $P --stage prod)" == db-prod ]] && ok "get --stage reads the stage's shared layer" || bad "get --stage reads the stage's shared layer"
[[ "$(secret get ST_DB -p $P --stage prod --scope api)" == db-api-prod ]] && ok "get --stage --scope reads the stage's scoped layer" || bad "get --stage --scope reads the stage's scoped layer"
[[ "$(secret get ST_DB -p $P --stage test)" == db-shared ]] && ok "get --stage falls back to the stage-less layer" || bad "get --stage falls back to the stage-less layer"
[[ "$(SECRET_STAGE=prod secret get ST_DB -p $P)" == db-prod ]] && ok "SECRET_STAGE selects the stage" || bad "SECRET_STAGE selects the stage"
[[ "$(SECRET_STAGE=prod secret get ST_DB -p $P --no-stage)" == db-shared ]] && ok "--no-stage overrides SECRET_STAGE" || bad "--no-stage overrides SECRET_STAGE"
secret get ST_TOK -p $P >/dev/null 2>&1 && bad "a staged-only item is invisible without its stage" || ok "a staged-only item is invisible without its stage"
# env overlay: shared < scoped < shared@stage < scoped@stage; other stages never emitted
stenv=$(secret env -p $P)
[[ $stenv == *"ST_DB='db-shared'"* && $stenv != *ST_TOK* && $stenv != *db-prod* ]] \
  && ok "env without a stage emits no staged value" || bad "env without a stage emits no staged value"
stenv=$(secret env -p $P --stage prod)
[[ $stenv == *"ST_DB='db-prod'"* && $stenv == *"ST_LOG='log-shared'"* && $stenv != *ST_TOK* ]] \
  && ok "env --stage overlays the stage and falls back for the rest" || bad "env --stage overlays the stage and falls back for the rest"
[[ $stenv != *ST_HID* ]] && ok "a --no-env item in the stage hides the shared one" || bad "a --no-env item in the stage hides the shared one"
[[ "$(secret env -p $P --stage prod --scope api)" == *"ST_DB='db-api-prod'"* ]] \
  && ok "env --stage --scope: the stage's scoped layer wins" || bad "env --stage --scope: the stage's scoped layer wins"
[[ "$(secret env -p $P --scope api)" == *"ST_DB='db-api'"* ]] \
  && ok "env --scope without a stage: the scoped layer wins" || bad "env --scope without a stage: the scoped layer wins"
[[ "$(SECRET_STAGE=test secret env -p $P)" == *"ST_TOK='tok-test'"* ]] && ok "env honours SECRET_STAGE" || bad "env honours SECRET_STAGE"
[[ "$(SECRET_STAGE=prod secret env -p $P --no-stage)" == *"ST_DB='db-shared'"* ]] && ok "env --no-stage ignores SECRET_STAGE" || bad "env --no-stage ignores SECRET_STAGE"
# ls
lsarr=(${(f)"$(secret ls -p $P)"})
(( ${lsarr[(Ie)ST_DB@prod]} && ${lsarr[(Ie)api/ST_DB@prod]} && ${lsarr[(Ie)ST_DB]} )) \
  && ok "ls shows [scope/]NAME[@stage] tokens" || bad "ls shows [scope/]NAME[@stage] tokens"
lsarr=(${(f)"$(secret ls -p $P --stage prod)"})
(( ${lsarr[(Ie)ST_DB@prod]} && ! ${lsarr[(Ie)ST_DB]} && ! ${lsarr[(Ie)ST_TOK@test]} )) \
  && ok "ls --stage filters to that stage" || bad "ls --stage filters to that stage"
lsarr=(${(f)"$(secret ls -p $P --no-stage)"})
(( ${lsarr[(Ie)ST_DB]} && ! ${lsarr[(Ie)ST_DB@prod]} )) && ok "ls --no-stage filters to stage-less layers" || bad "ls --no-stage filters to stage-less layers"
stlong=$(secret ls -p $P --long)
[[ $stlong == *$'\n''  @prod'$'\n'*'    ST_DB '* && $stlong == *$'\n''  api/ @prod'$'\n''    ST_DB '* ]] \
  && ok "ls --long groups stage layers as @stage and scope/ @stage" || bad "ls --long groups stage layers as @stage and scope/ @stage"
[[ $stlong == *'  shared'*'  api/'*'  @prod'*'  api/ @prod'* ]] \
  && ok "ls --long orders groups shared, scopes, then stages" || bad "ls --long orders groups shared, scopes, then stages"
# validation
print -r -- 'v' | secret set ST_X -p 'a@b' --stdin >/dev/null 2>&1 && bad "rejects '@' in a project name" || ok "rejects '@' in a project name"
print -r -- 'v' | secret set ST_X -p $P --scope 'a@b' --stdin >/dev/null 2>&1 && bad "rejects '@' in a scope name" || ok "rejects '@' in a scope name"
print -r -- 'v' | secret set ST_X -p $P --stage 'pr od' --stdin >/dev/null 2>&1 && bad "rejects a stage name with spaces" || ok "rejects a stage name with spaces"
print -r -- 'v' | SECRET_STAGE='bad@stage' secret set ST_X -p $P --stdin >/dev/null 2>&1 && bad "rejects an invalid SECRET_STAGE" || ok "rejects an invalid SECRET_STAGE"
# update / rm address the exact layer
secret update ST_DB -p $P --stage prod -j 'prod memo' >/dev/null 2>&1
[[ "$(secret show ST_DB -p $P --stage prod)" == *'prod memo'* && "$(secret show ST_DB -p $P --no-stage)" != *'prod memo'* ]] \
  && ok "update --stage touches the stage's item only" || bad "update --stage touches the stage's item only"
secret rm ST_DB -p $P --scope api --stage prod -f >/dev/null 2>&1 && ok "rm --scope --stage" || bad "rm --scope --stage"
secret get ST_DB -p $P --stage prod --scope api >/dev/null 2>&1 && bad "exact layer flags address only that layer" || ok "exact layer flags address only that layer"
[[ "$(secret get ST_DB -p $P --stage prod)" == db-prod && "$(secret get ST_DB -p $P --scope api)" == db-api ]] \
  && ok "rm removed only that layer" || bad "rm removed only that layer"
# export / import round-trip
secret export -p $P --format json -o "$TD/stage.json" >/dev/null 2>&1
[[ "$(jq -r '.items[] | select(.name == "ST_TOK") | .stage' "$TD/stage.json" 2>/dev/null)" == test ]] \
  && ok "json export records the stage" || bad "json export records the stage"
secret export -p $P --format env -o "$TD/stage.env" >/dev/null 2>&1
grep -q '(stage: prod)' "$TD/stage.env" 2>/dev/null && ok "env export names the stage in its headers" || bad "env export names the stage in its headers"
secret rm ST_DB -p $P --stage prod -f >/dev/null 2>&1
secret rm ST_TOK -p $P --stage test -f >/dev/null 2>&1
secret import "$TD/stage.json" -y >/dev/null 2>&1
[[ "$(secret get ST_DB -p $P --stage prod)" == db-prod && "$(secret get ST_TOK -p $P --stage test)" == tok-test ]] \
  && ok "json import restores stages" || bad "json import restores stages"
secret import "$TD/stage.env" -p $P --stage qa -y >/dev/null 2>&1
[[ "$(secret get ST_LOG -p $P --stage qa)" == log-shared && -z "$(secret ls -p $P --stage qa 2>/dev/null | grep -v '@qa$')" ]] \
  && ok "import --stage forces every item into that stage" || bad "import --stage forces every item into that stage"
SECRET_STAGE=uat secret import "$TD/stage.env" -p $P -y >/dev/null 2>&1
[[ "$(secret get ST_LOG -p $P --stage uat)" == log-shared ]] && ok "env import lands in SECRET_STAGE" || bad "env import lands in SECRET_STAGE"
SECRET_STAGE=uat secret import "$TD/stage.json" -y >/dev/null 2>&1
[[ "$(secret ls -p $P --stage uat | grep -c ST_DB)" == 1 ]] \
  && ok "json import keeps recorded stages despite SECRET_STAGE" || bad "json import keeps recorded stages despite SECRET_STAGE"
# a recorded scope/stage that is no valid name never turns into a staged layer
print -r -- '{"items":[{"name":"ST_EVIL","value":"v","project":"'$P'","scope":"api@prod","stage":""}]}' > "$TD/evil.json"
secret import "$TD/evil.json" --no-stage -y >/dev/null 2>&1 && bad "import rejects a recorded scope holding '@'" || ok "import rejects a recorded scope holding '@'"
security find-generic-password -s "secret.$P/api@prod" -a ST_EVIL "$HOME/Library/Keychains/$P.keychain-db" >/dev/null 2>&1 \
  && bad "a rejected scope never lands in a stage" || ok "a rejected scope never lands in a stage"
print -r -- '{"items":[{"name":"ST_EVIL","value":"v","project":"'$P'","stage":"pr od"}]}' > "$TD/evil.json"
secret import "$TD/evil.json" -y >/dev/null 2>&1 && bad "import rejects an invalid recorded stage" || ok "import rejects an invalid recorded stage"
# a repository whose name is no scope name has no ambient scope
git -C "$TD" init -q 'at@repo' && git -C "$TD/at@repo" config secret.project $P
print -r -- 'v' | ( cd "$TD/at@repo" && secret set ST_AT -S --stdin ) >/dev/null 2>&1 \
  && bad "-S is refused in a repository named with '@'" || ok "-S is refused in a repository named with '@'"
[[ "$( cd "$TD/at@repo" && secret get ST_DB )" == db-shared ]] \
  && ok "such a repository reads the shared layer" || bad "such a repository reads the shared layer"
[[ "$( cd "$TD/at@repo" && secret env )" == *"ST_DB='db-shared'"* ]] \
  && ok "such a repository injects the shared layer" || bad "such a repository injects the shared layer"
# every "[scope/]NAME[@stage]" token ls prints maps back to exact layer flags
for tok in ${(f)"$(secret ls -p $P | grep 'ST_')"}; do
  _secret_ui_split_token "$tok"
  secret rm "$_tok_name" -p $P "${_tok_flags[@]}" -f >/dev/null 2>&1
done
[[ -z "$(secret ls -p $P 2>/dev/null | grep 'ST_')" ]] && ok "ls tokens round-trip into rm layer flags" || bad "ls tokens round-trip into rm layer flags"

# --- "[scope/]NAME[@stage]" is accepted as NAME by get/show/update/rm ---
print -r -- 'tk-shared' | secret set TK_DB -p $P --meta url=https://ex.com -D 'api key' --stdin >/dev/null 2>&1
print -r -- 'tk-api-prod' | secret set TK_DB -p $P --scope api --stage prod -j 'prod memo' --no-env --stdin >/dev/null 2>&1
[[ "$(secret get api/TK_DB@prod -p $P)" == tk-api-prod ]] && ok "get accepts a layer token as NAME" || bad "get accepts a layer token as NAME"
[[ "$(secret get TK_DB -p $P)" == tk-shared ]] && ok "a bare NAME still reads DWIM" || bad "a bare NAME still reads DWIM"
[[ "$(secret show api/TK_DB@prod -p $P)" =~ 'Stage:[[:space:]]+prod' ]] && ok "show accepts a layer token" || bad "show accepts a layer token"
secret update api/TK_DB@prod -p $P --meta 'url=https://x/y@z' -j 'a/b@c' >/dev/null 2>&1 \
  && ok "update accepts a layer token" || bad "update accepts a layer token"
tkshow=$(secret show api/TK_DB@prod -p $P)
[[ $tkshow == *'url=https://x/y@z'* && $tkshow == *'a/b@c'* ]] \
  && ok "option values holding '/' or '@' are not read as tokens" || bad "option values holding '/' or '@' are not read as tokens"
secret rm api/TK_DB@prod -p $P -f >/dev/null 2>&1 && ok "rm accepts a layer token" || bad "rm accepts a layer token"
[[ "$(secret get TK_DB -p $P --stage prod)" == tk-shared ]] && ok "rm by token removed only that layer" || bad "rm by token removed only that layer"

# --- the fzf picker: visible columns, hidden token and meta, preview ---
print -r -- 'tk-api-prod' | secret set TK_DB -p $P --scope api --stage prod -j 'prod memo' --no-env --stdin >/dev/null 2>&1
_secret_fzf() { cat; }                  # the picker's lines, unfiltered
pick=$(_secret_ui_pick_items $P hdr "" 2>/dev/null)
[[ $pick == $'TK_DB\napi/TK_DB@prod' ]] && ok "picker returns one token per line" || bad "picker returns one token per line"
_secret_fzf() { tee /dev/stderr >/dev/null; }   # the raw lines, to inspect
raw=$(_secret_ui_pick_items $P hdr "" 2>&1 >/dev/null)
[[ $raw == *$'TK_DB '*'API KEY'*'yes'*$'\tTK_DB\turl=https://ex.com'* ]] \
  && ok "picker lines carry columns, token and meta as tab fields" || bad "picker lines carry columns, token and meta as tab fields"
[[ $raw == *'api/TK_DB@prod '*'no '*'prod memo'$'\tapi/TK_DB@prod\t'* ]] \
  && ok "picker shows env no and the comment" || bad "picker shows env no and the comment"
_secret_fzf() { print -r -- "$*" >&2; cat >/dev/null; }
args=$(_secret_ui_pick_items $P hdr "" 2>&1 >/dev/null)
[[ $args == *"--with-nth=1"* && $args == *"--preview=zsh -fc 'source"*"secret show"*" {2} $P"* ]] \
  && ok "picker previews with secret show on the token" || bad "picker previews with secret show on the token"
preview=${${args#*--preview=}%% --preview-window*}
[[ "$(eval "${preview//\{2\}/api/TK_DB@prod}" 2>/dev/null)" =~ 'Comment:[[:space:]]+prod memo' ]] \
  && ok "the preview command runs against this checkout" || bad "the preview command runs against this checkout"
_secret_fzf() { print ctrl-y; head -1; }
[[ "$(_secret_ui_pick_items $P hdr expect --expect=ctrl-y 2>/dev/null)" == $'ctrl-y\nTK_DB' ]] \
  && ok "expect mode returns the key and the token" || bad "expect mode returns the key and the token"
_secret_fzf() { print ctrl-y; }
[[ "$(_secret_ui_pick_items $P hdr expect --expect=ctrl-y 2>/dev/null)" == 'ctrl-y' ]] \
  && ok "expect mode with nothing picked returns the key alone" || bad "expect mode with nothing picked returns the key alone"
unfunction _secret_fzf
_secret_fzf() { fzf --height=40% --reverse --no-sort "$@"; }
# ^f copies a meta field (or the comment) plainly; ^o opens url=
pbcopy() { cat > "$TD/clip"; }
_secret_ui_copy_field $P TK_DB >/dev/null 2>&1
[[ "$(<"$TD/clip")" == 'https://ex.com' ]] && ok "copy field: a lone field copies at once" || bad "copy field: a lone field copies at once"
_secret_fzf() { grep '^comment='; }
_secret_ui_copy_field $P api/TK_DB@prod >/dev/null 2>&1
[[ "$(<"$TD/clip")" == 'prod memo' ]] && ok "copy field: the comment is offered as a field" || bad "copy field: the comment is offered as a field"
unfunction _secret_fzf pbcopy
_secret_fzf() { fzf --height=40% --reverse --no-sort "$@"; }
open() { print -r -- "OPEN $1"; }
[[ "$(_secret_ui_open_url $P TK_DB 2>/dev/null)" == *'OPEN https://ex.com'* ]] && ok "open url: opens the url= field" || bad "open url: opens the url= field"
[[ "$(_secret_ui_open_url $P api/TK_DB@prod 2>/dev/null)" == *'no url= field'* ]] && ok "open url: says when there is none" || bad "open url: says when there is none"
secret update TK_DB -p $P --meta 'url=file:///etc/passwd' >/dev/null 2>&1
_secret_ui_open_url $P TK_DB >/dev/null 2>&1 && bad "open url: refuses a non-http url" || ok "open url: refuses a non-http url"
unfunction open
secret rm TK_DB -p $P -f >/dev/null 2>&1
secret rm api/TK_DB@prod -p $P -f >/dev/null 2>&1

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
