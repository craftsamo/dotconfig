# secret.zsh — manage secrets in the macOS Keychain (CLI + fzf wizard)
#
#   secret                       interactive wizard (fzf)
#   secret set NAME [-p proj] [-S|--scope X] [--stage S|--no-stage] [-j comment] [-D kind] [--meta K=V]... [--new] [--stdin]
#   secret update NAME [-p proj] [LAYER] [-j comment] [-D kind] [--meta K=V]... [--value|--stdin]
#   secret get NAME [-p proj] [LAYER] [-c|--copy]
#   secret show NAME [-p proj] [LAYER]
#   secret ls [-p proj] [-l|--long] [--meta KEY[=VALUE]] [--stage S|--no-stage]
#   secret projects
#   secret env [-p proj] [--scope X] [--stage S|--no-stage]
#   secret rm NAME [-p proj] [LAYER] [-f|--force]
#   secret link [NAME|--unset]
#   secret export [-p proj|--all] [-o FILE] [--format age|json|env]
#   secret import FILE [-p proj] [-S|--scope X] [--stage S|--no-stage] [-y|--yes]
#   secret migrate [-p proj|--all] [--dry-run]
#   secret keychain create|ls|info|lock|unlock|remember|register|master|rm ...
#   secret help
#
# LAYER flags: default is most-specific-first (DWIM); -S = this repo's
# scope, --scope X = that scope, --shared = the shared layer; --stage S /
# --no-stage pin the stage ($SECRET_STAGE otherwise; production = prod,
# development = dev). Scoped items override shared ones per repository,
# staged items override stage-less ones per environment, within one project.
#
# Data model — native keychain attributes (fully visible in Keychain Access):
#   service = secret.<project>[/<scope>][@<stage>]   account = NAME (unique key)
#   label   = [<scope>/]NAME[@<stage>] inside the project's own keychain,
#             else prefixed with <project>/
#   kind    = -D (upper-cased, default "ENV")  comment = -j (free-form description)
#   type    = -C four-char code: "envn" = never emitted by `secret env`,
#             "envy" or unset = emitted (the ENV setting)
#   generic = -G structured metadata, ";"-separated KEY=VALUE fields
#             (--meta url=... account=...); free text stays in the comment
# Project resolution:
#   -p flag > `git config secret.project` > git toplevel basename > "global"
# Keychain model — strict 1:1, one project = one keychain:
#   project P lives in ~/Library/Keychains/P.keychain-db, auto-created on
#   first write (silently when a master password is set). Files that exist
#   but were never registered in the search list are refused. `-k NAME|PATH`
#   overrides everything; `-k default` targets the login keychain.
#
# Security invariants:
#   - secret values never appear in process argv: writes are piped to
#     `security -i` on stdin, interactive entry uses zsh `read -s`
#   - values are single-line; control characters are rejected
#   - fzf only ever sees names and metadata, never values
#   - clipboard copies are cleared after 45s (unless overwritten meanwhile)
#
# Test hooks: SECRET_AGE_ARGS / SECRET_AGE_DECRYPT_ARGS override the age
# flags used by export/import (default: -p, i.e. passphrase mode).
# SECRET_MASTER_ACCOUNT overrides the login account of the master password
# item; SECRET_TEST_ONLY_KC (glob) limits which custom keychains the
# master set/rotate loops touch. Both exist for the self-tests.

# ---------------------------------------------------------------- helpers --

# This file's own path: the fzf preview runs `secret show` in a fresh zsh
# that sources it, so the wizard previews with the CLI it was loaded from.
typeset -g _SECRET_LIB=${${(%):-%x}:A}
zmodload -F zsh/datetime p:EPOCHSECONDS
# _secret_kc_ensure's memo; the dispatcher shadows it per invocation, this
# one serves helpers called outside it (the wizard, the self-tests)
typeset -gA _kc_unlocked

_secret_err() { print -r -- "secret: $*" >&2; }

_secret_default_keychain() {
  security default-keychain 2>/dev/null \
    | sed -E 's/^[[:space:]]*"(.*)"[[:space:]]*$/\1/'
}

_secret_resolve_keychain() {   # $1: -k value (may be empty) -> path/name on stdout
  local k=$1
  if [[ -z $k || $k == default ]]; then _secret_default_keychain; return; fi
  if [[ -e $k ]]; then print -r -- "$k"
  elif [[ -e $HOME/Library/Keychains/$k ]]; then print -r -- "$HOME/Library/Keychains/$k"
  elif [[ -e $HOME/Library/Keychains/$k.keychain-db ]]; then print -r -- "$HOME/Library/Keychains/$k.keychain-db"
  else print -r -- "$k"        # let security resolve it by name
  fi
}

# Keychain for a project — strict 1:1: every project lives in its own
# ~/Library/Keychains/<project>.keychain-db (only `-k` overrides that).
# Writes go through _secret_kc_prepare, which auto-creates missing
# keychains and refuses files that exist but were never registered in the
# user search list (metadata, parallels_shared, ...).
# Relies on $_kc, $_kc_default, $_kc_explicit, $_kc_sl set by the dispatcher.
_secret_kc_for() {             # $1 project -> keychain path/name on stdout
  if (( _kc_explicit )); then
    print -r -- "$_kc"
  else
    print -r -- "$HOME/Library/Keychains/$1.keychain-db"
  fi
}

_secret_kc_label() {           # $1 project -> keychain name when surprising
  (( _kc_explicit )) && return 0           # explicit -k: target is obvious
  local kc
  kc=$(_secret_kc_for "$1")
  [[ ${${kc:t}%.keychain-db} == "$1" ]] && return 0   # own keychain: obvious
  print -r -- "${${kc:t}%.keychain-db}"
}

_secret_kc_suffix() {          # $1 project -> " [kc:NAME]" for UI headers, or ""
  local l
  l=$(_secret_kc_label "$1")
  [[ -n $l ]] && print -rn -- " [kc:$l]"
  return 0
}

# Auto-unlock: the login keychain may hold unlock passwords as items with
# service "keychain-password":
#   account "<keychain name>"  per-keychain (secret keychain remember)
#   account "master"           shared master (secret keychain master set)
# Lookup order: per-keychain item > master item > give up (GUI prompt).
# No-op for the default keychain or when nothing is stored.
# The lookups and the unlock cost ~60 ms, so one `secret` invocation does
# them once per keychain ($_kc_unlocked, set by the dispatcher, holds the
# time) and trusts the result for a minute — long enough for `env` and
# `export` to read every value, short enough that a keychain re-locked
# during a wizard session is unlocked again. A command substitution runs
# in a child, so a loop that fetches values with $(...) ensures in the
# parent first.
_secret_master_account() { print -r -- "${SECRET_MASTER_ACCOUNT:-master}"; }

_secret_kc_ensure() {          # $1 keychain path/name
  local kc=$1
  [[ -z $kc || $kc == "$_kc_default" ]] && return 0
  (( ${_kc_unlocked[$kc]:-0} + 60 > EPOCHSECONDS )) && return 0
  _kc_unlocked[$kc]=$EPOCHSECONDS
  local pw
  pw=$(security find-generic-password -s 'keychain-password' \
        -a "${${kc:t}%.keychain-db}" -w "$_kc_default" 2>/dev/null)
  if [[ -z $pw ]]; then
    pw=$(security find-generic-password -s 'keychain-password' \
          -a "$(_secret_master_account)" -w "$_kc_default" 2>/dev/null)
  fi
  [[ -n $pw ]] || return 0
  print -r -- "unlock-keychain -p $(_secret_quote_si "$pw") $(_secret_quote_si "$kc")" \
    | security -i >/dev/null 2>&1
  return 0
}

# Write gate for the 1:1 model: make sure the project's keychain exists and
# is ours before storing into it.
#   - missing: auto-create (silently with the master password, interactively
#     on a terminal, otherwise fail with instructions)
#   - exists but not in the user search list: refuse — likely an app/system
#     keychain (metadata, parallels_shared, ...); `secret keychain register`
#     is the deliberate opt-in
_secret_kc_prepare() {         # $1 project  $2 keychain path
  local proj=$1 kc=$2
  (( _kc_explicit )) && return 0          # -k override: caller's choice
  [[ $kc == "$_kc_default" ]] && return 0
  _secret_kc_sl_load
  if [[ -e $kc ]]; then
    (( ${_kc_sl[(Ie)$kc]} )) && return 0
    _secret_err "keychain file exists but is not registered: ${kc:t}"
    _secret_err "if it is yours, opt in with: secret keychain register $proj"
    return 1
  fi
  local mpw
  mpw=$(_secret_master_get)
  if [[ -n $mpw ]]; then
    print -r -- "create-keychain -p $(_secret_quote_si "$mpw") $(_secret_quote_si "$kc")" \
      | security -i >/dev/null 2>&1
    [[ -e $kc ]] || { _secret_err "could not create keychain for project '$proj'"; return 1 }
    security set-keychain-settings -l -u -t 1800 "$kc" 2>/dev/null
    local -a sl
    sl=(${(@f)$(_secret_kc_searchlist)})
    (( ${sl[(Ie)$kc]} )) || security list-keychains -d user -s "${sl[@]}" "$kc"
    _kc_sl+=("$kc")
    print -r -- "created keychain '$proj' (master password, auto-locks on sleep/30 min)" >&2
    return 0
  fi
  if [[ -t 0 && -t 1 ]]; then
    print -r -- "project '$proj' has no keychain yet — creating it now" >&2
    _secret_kc_create "$proj" || return 1
    _kc_sl+=("$kc")
    return 0
  fi
  _secret_err "no keychain for project '$proj'"
  _secret_err "set a master password (secret keychain master set) or run: secret keychain create $proj"
  return 1
}

_secret_resolve_project() {    # $1: -p value (may be empty)
  local p=$1 top conf
  if [[ -n $p ]]; then print -r -- "$p"; return; fi
  if top=$(command git rev-parse --show-toplevel 2>/dev/null) && [[ -n $top ]]; then
    # several repositories can share one project: git config secret.project
    conf=$(command git config --get secret.project 2>/dev/null)
    if [[ -n $conf ]]; then print -r -- "$conf"; return; fi
    print -r -- "${top:t}"; return
  fi
  print -r -- global
}

_secret_check_name() {
  [[ $1 =~ '^[A-Za-z_][A-Za-z0-9_]*$' ]] && return 0
  _secret_err "invalid name '$1' (letters, digits, underscores; must not start with a digit)"
  return 1
}

_secret_check_project() {
  [[ -n $1 && $1 != *[/@$'\t'$'\n']* ]] && return 0
  _secret_err "invalid project name '$1' (must be non-empty, no '/', '@', tabs or newlines)"
  return 1
}

_secret_check_scope() {
  [[ -n $1 && $1 != *[/@$'\t'$'\n']* ]] && return 0
  _secret_err "invalid scope name '$1' (must be non-empty, no '/', '@', tabs or newlines)"
  return 1
}

_secret_check_stage() {
  [[ $1 =~ '^[A-Za-z0-9_-]+$' ]] && return 0
  _secret_err "invalid stage name '$1' (letters, digits, '_' and '-')"
  return 1
}

# One layer per stage whatever the spelling: the frameworks say production
# and development (NODE_ENV, .env.production), the shell says prod and dev.
# The short form names the layer; every command and the shim go through
# here, so `--stage production` and `SECRET_STAGE=prod` meet in @prod.
_secret_canon_stage() {        # $1 stage -> its canonical spelling on stdout
  case $1 in
    production)  print -r -- prod ;;
    development) print -r -- dev ;;
    *)           print -r -- "$1" ;;
  esac
}

# The stages a project holds items in, one per line, sorted.
_secret_stages_of() {          # $1 project
  _secret_rows "$1" | cut -f10 | grep -v '^$' | sort -u
}

# A stage the project has no item in yet is a first use or a typo (prd);
# say which stages are in use, without refusing.
_secret_stage_note() {         # $1 project  $2 stage
  [[ -n $2 ]] || return 0
  local -a have
  have=(${(f)"$(_secret_stages_of "$1")"})
  (( ${have[(Ie)$2]} )) && return 0
  print -r -- "note: '$2' is a new stage for project '$1'${have:+ (in use: ${(j:, :)have})}" >&2
  return 0
}

# Layers: a scope (per-repository override) and a stage (per-environment
# override: prod, test, ...) inside one project. Internally a layer is one
# string, "<scope>[@<stage>]" — "" is the shared layer, "@prod" the shared
# layer of stage prod, "api@prod" scope api of stage prod.
#   service "secret.<project>"                 shared layer
#   service "secret.<project>/<scope>"         scoped layer
#   service "secret.<project>@<stage>"         shared layer of a stage
#   service "secret.<project>/<scope>@<stage>" scoped layer of a stage
_secret_service() {            # $1 project  $2 layer ("" = shared)
  local scope=${2%%@*} stage=""
  [[ $2 == *@* ]] && stage=${2#*@}
  print -r -- "secret.$1${scope:+/$scope}${stage:+@$stage}"
}

_secret_layer() {              # $1 scope  $2 stage -> layer string
  print -r -- "$1${2:+@$2}"
}

_secret_layer_scope() { print -r -- "${1%%@*}"; }
_secret_layer_stage() { [[ $1 == *@* ]] && print -r -- "${1#*@}"; return 0; }

# "<project>/<scope>/NAME@<stage>" — how an item is named in messages
_secret_disp() {               # $1 project  $2 layer  $3 name
  local scope stage
  scope=$(_secret_layer_scope "$2"); stage=$(_secret_layer_stage "$2")
  print -r -- "$1/${scope:+$scope/}$3${stage:+@$stage}"
}

# The stage every command works in: --stage S > $SECRET_STAGE > none;
# --no-stage forces the stage-less layers whatever the environment says.
_secret_resolve_stage() {      # $1 --stage value ("" if absent)  $2 --no-stage flag (0/1)
  if (( $2 )); then return 0; fi
  local s=${1:-${SECRET_STAGE:-}}
  [[ -z $s ]] && return 0
  _secret_check_stage "$s" || return 1
  _secret_canon_stage "$s"
}

# The repository basename is only a scope when it is a valid scope name: a
# directory called "api@prod" would otherwise read as scope api of stage
# prod. Such a repository has no ambient scope (reads fall through to the
# shared layer); -S on it is refused below.
_secret_ambient_scope() {      # $1 project -> repo-derived scope ("" when none)
  local top
  top=$(command git rev-parse --show-toplevel 2>/dev/null)
  [[ -z $top ]] && return 0
  local sc=${top:t}
  [[ $sc == "$1" ]] && return 0     # the repo IS the project: shared
  _secret_check_scope "$sc" 2>/dev/null || return 0
  print -r -- "$sc"
}

# Resolve the target scope from flags.
#   $1 --scope value ("" if absent)   $2 -S flag (0/1)   $3 project
# Bare -S needs a repository; --scope <project> normalises to shared.
_secret_resolve_scope() {
  local explicit=$1 scoped=$2 proj=$3
  if [[ -n $explicit ]]; then
    [[ $explicit == "$proj" ]] && return 0
    _secret_check_scope "$explicit" || return 1
    print -r -- "$explicit"
    return 0
  fi
  (( scoped )) || return 0
  local top
  if ! top=$(command git rev-parse --show-toplevel 2>/dev/null) || [[ -z $top ]]; then
    _secret_err "-S/--scoped needs a git repository (or use --scope NAME)"
    return 1
  fi
  if [[ ${top:t} != "$proj" ]] && ! _secret_check_scope "${top:t}"; then
    _secret_err "-S/--scoped: the repository name is no scope name (use --scope NAME)"
    return 1
  fi
  _secret_ambient_scope "$proj"
}

_secret_fmt_date() {           # 20250612053000Z -> 2025-06-12 05:30
  local d=$1
  if [[ ${#d} -ge 12 && $d == [0-9]* ]]; then
    print -r -- "${d[1,4]}-${d[5,6]}-${d[7,8]} ${d[9,10]}:${d[11,12]}"
  else
    print -r -- "$d"
  fi
}

_secret_quote_si() {           # quote one argument for the `security -i` parser
  local s=$1
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  print -r -- "\"$s\""
}

_secret_prompt_value() {       # $1 display label; hidden double prompt, value on stdout
  local v1 v2
  IFS= read -rs "v1?value for $1 (hidden): " || { print '' >&2; return 1 }
  print '' >&2
  IFS= read -rs "v2?retype to confirm: " || { print '' >&2; return 1 }
  print '' >&2
  [[ "$v1" == "$v2" ]] || { _secret_err "values do not match, aborted"; return 1 }
  print -r -- "$v1"
}

# Canonical kind labels offered by the fzf pickers (one per line). "Other"
# lets the user type a free-form kind; every write is normalised by
# _secret_norm_kind, so casing/spacing stays consistent whatever the source.
_secret_kind_choices() {
  print -rl -- ENV 'API KEY' TOKEN PASSWORD SECRET URL \
    'WEBHOOK SECRET' 'MNEMONIC PHRASE' 'PRIVATE KEY' 'Other'
}

# Normalise a kind label: upper-case, collapse whitespace runs to one space,
# trim both ends, default to ENV when empty. Applied on every write so the
# stored kind is consistent regardless of -D casing or origin (set/update/import).
_secret_norm_kind() {          # $1 raw kind -> canonical kind on stdout
  local k=${(U)1}
  k=${k//[[:space:]]##/ }
  k=${${k##[[:space:]]#}%%[[:space:]]#}
  print -r -- "${k:-ENV}"
}

# The ENV setting lives in the item's type attribute, a four-character code
# ("type", -C): envn — the item never appears in `secret env`, so no shell,
# shim or helper that injects a layer ever receives it (get still reads it);
# envy or unset — emitted, the historical behaviour. A type can be rewritten
# but never cleared, hence the explicit envy. Items written before the type
# carried env=no in the generic attribute; that marker is still honoured
# until `secret migrate` moves it, and only when no type is set.
_secret_env_on() {             # $1 type  $2 generic attribute -> success when `secret env` may emit the item
  case $1 in
    envn) return 1 ;;
    envy) return 0 ;;
  esac
  [[ ";$2;" != *";env=no;"* ]]
}

_secret_env_code() {           # $1 yes|no -> four-char type code on stdout
  [[ $1 == no ]] && print -rn -- envn || print -rn -- envy
}

# Structured metadata lives in the generic attribute ("gena", -G):
# ';'-separated KEY=VALUE fields, split at the first '='. Keys are
# identifiers ([A-Za-z][A-Za-z0-9_-]*; "env" is reserved for the legacy
# marker above), values hold anything single-line without ';'. Fields are
# kept sorted by key so equal metadata always serialises the same way.
_secret_meta_check_key() {     # $1 key
  if [[ $1 == env ]]; then
    _secret_err "meta key 'env' is reserved (use --env/--no-env)"; return 1
  fi
  [[ $1 =~ '^[A-Za-z][A-Za-z0-9_-]*$' ]] && return 0
  _secret_err "invalid meta key '$1' (letters, digits, '_' and '-'; must start with a letter)"
  return 1
}

_secret_meta_check_value() {   # $1 key  $2 value
  if [[ $2 == *';'* ]]; then
    _secret_err "meta $1: ';' is not allowed in a value"; return 1
  fi
  if [[ $2 == *[[:cntrl:]]* ]]; then
    _secret_err "meta $1: control characters are not allowed in a value"; return 1
  fi
  return 0
}

_secret_meta_fields() {        # $1 generic attribute -> one KEY=VALUE per line (legacy env=* dropped)
  local token
  for token in ${(s:;:)1}; do
    [[ -n $token && $token == *=* && $token != env=* ]] && print -r -- "$token"
  done
  return 0
}

_secret_meta_get() {           # $1 generic attribute  $2 key -> value on stdout; fails when absent
  local token
  for token in ${(s:;:)1}; do
    [[ ${token%%=*} == "$2" && $token == *=* ]] || continue
    print -r -- "${token#*=}"
    return 0
  done
  return 1
}

# Apply --meta edits to the current attribute: KEY=VALUE sets a field, KEY=
# removes it. Validates every edit; prints the new attribute string.
_secret_meta_merge() {         # $1 current generic attribute  $2.. KEY=VALUE edits
  local cur=$1 edit key val token
  shift
  local -A fields
  for token in ${(f)"$(_secret_meta_fields "$cur")"}; do
    fields[${token%%=*}]=${token#*=}
  done
  for edit in "$@"; do
    if [[ $edit != *=* ]]; then
      _secret_err "meta: expected KEY=VALUE, got '$edit'"; return 1
    fi
    key=${edit%%=*} val=${edit#*=}
    _secret_meta_check_key "$key" || return 1
    if [[ -z $val ]]; then
      unset "fields[$key]"
    else
      _secret_meta_check_value "$key" "$val" || return 1
      fields[$key]=$val
    fi
  done
  local -a out
  for key in ${(ko)fields}; do out+=("$key=${fields[$key]}"); done
  print -r -- "${(j:;:)out}"
}

_secret_meta_matches() {       # $1 generic attribute  $2 KEY or KEY=VALUE filter
  local want
  if [[ $2 == *=* ]]; then
    want=$(_secret_meta_get "$1" "${2%%=*}") || return 1
    [[ $want == "${2#*=}" ]]
  else
    _secret_meta_get "$1" "$2" >/dev/null
  fi
}

_secret_row_of() {             # $1 name  $2 project  $3 layer -> the item's TSV row ("" when absent)
  _secret_rows "$2" | awk -F'\t' -v n="$1" -v s="$(_secret_layer_scope "$3")" -v t="$(_secret_layer_stage "$3")" \
    '$2 == n && $7 == s && $10 == t { print; exit }'
}

# $6 env: yes|no writes the type code, "keep" / absent leaves an existing
# item's setting as it is — a value rewrite never re-enables what --no-env
# turned off. $7 meta: the whole generic attribute to write ("" clears every
# field), or "keep" / absent to leave it alone.
_secret_store() {              # $1 name $2 project $3 comment $4 kind $5 layer [$6 env [$7 meta [$8 new]]] ; value on stdin
  local name=$1 proj=$2 comment=$3 kind=$4 layer=$5 env=${6-keep} meta=${7-keep} create=${8-} value extra err
  IFS= read -r value
  if IFS= read -r extra; then
    _secret_err "$proj/$name: multi-line values are not supported"; return 1
  fi
  if [[ -z $value ]]; then
    _secret_err "$proj/$name: empty value, skipped"; return 1
  fi
  if [[ $value == *[[:cntrl:]]* ]]; then
    _secret_err "$proj/$name: control characters are not supported"; return 1
  fi
  local kc svc
  kc=$(_secret_kc_for "$proj")
  svc=$(_secret_service "$proj" "$layer")
  _secret_kc_prepare "$proj" "$kc" || return 1
  _secret_kc_ensure "$kc"
  # label: NAME (shared) / "<scope>/NAME" (scoped) / "...@<stage>" (staged)
  # inside the project's own keychain; prefixed with "<project>/" elsewhere
  # (-k default, cross -k)
  local label
  label=$(_secret_disp "$proj" "$layer" "$name")
  [[ ${${kc:t}%.keychain-db} == "$proj" ]] && label=${label#$proj/}
  # -U updates an existing item in place; a create-only write (--new) leaves it out, so security
  # itself refuses an item that already exists
  local cmd="add-generic-password"
  [[ $create == new ]] || cmd+=" -U"
  cmd+=" -a $(_secret_quote_si "$name")"
  cmd+=" -s $(_secret_quote_si "$svc")"
  cmd+=" -l $(_secret_quote_si "$label")"
  cmd+=" -D $(_secret_quote_si "$(_secret_norm_kind "$kind")")"
  cmd+=" -j $(_secret_quote_si "$comment")"
  # -U without -C / -G keeps the stored type / generic attribute; -G '' clears the fields
  [[ $env == keep ]] || cmd+=" -C $(_secret_env_code "$env")"
  [[ $meta == keep ]] || cmd+=" -G $(_secret_quote_si "$meta")"
  cmd+=" -w $(_secret_quote_si "$value")"
  cmd+=" $(_secret_quote_si "$kc")"
  err=$(print -r -- "$cmd" | security -i 2>&1 >/dev/null)
  # create-only: any complaint from security (an existing item, in whatever language) is a refusal,
  # even if an item of that name is there now: it may not be this one
  if [[ $create == new && -n $err ]]; then
    _secret_err "$(_secret_disp "$proj" "$layer" "$name") was not stored as new — ${err//$'\n'/ }"
    return 1
  fi
  if ! security find-generic-password -s "$svc" -a "$name" "$kc" >/dev/null 2>&1; then
    _secret_err "failed to store $(_secret_disp "$proj" "$layer" "$name")${err:+ — ${err//$'\n'/ }}"
    return 1
  fi
}

_secret_get_value() {          # $1 name  $2 project  $3 layer -> value on stdout
  local kc
  kc=$(_secret_kc_for "$2")
  _secret_kc_ensure "$kc"
  security find-generic-password -s "$(_secret_service "$2" "$3")" -a "$1" -w "$kc" 2>/dev/null
}

_secret_exists() {             # $1 name  $2 project  $3 layer (attributes only)
  local kc
  kc=$(_secret_kc_for "$2")
  _secret_kc_ensure "$kc"
  security find-generic-password -s "$(_secret_service "$2" "$3")" -a "$1" "$kc" >/dev/null 2>&1
}

_secret_delete() {             # $1 name  $2 project  $3 layer
  local kc
  kc=$(_secret_kc_for "$2")
  _secret_kc_ensure "$kc"
  security delete-generic-password -s "$(_secret_service "$2" "$3")" -a "$1" "$kc" >/dev/null 2>&1
}

# Layer resolution for read/modify commands, most specific first: the
# stage's scoped layer, the stage's shared layer, the scoped layer, the
# shared layer (whichever of scope / stage apply).
#   $1 name  $2 project  $3 candidate scope  $4 candidate stage
# Prints the layer that holds the item; returns 1 if none.
_secret_find_layer() {
  local name=$1 proj=$2 scope=$3 stage=$4 cand
  local -a cands
  [[ -n $scope && -n $stage ]] && cands+=("$(_secret_layer "$scope" "$stage")")
  [[ -n $stage ]] && cands+=("$(_secret_layer "" "$stage")")
  [[ -n $scope ]] && cands+=("$scope")
  cands+=("")
  for cand in "${cands[@]}"; do
    if _secret_exists "$name" "$proj" "$cand"; then
      print -r -- "$cand"
      return 0
    fi
  done
  return 1
}

# All secret.* items in one keychain ($1, defaults to $_kc).
# TSV rows: project \t name \t label \t kind \t comment \t mdate \t scope \t meta \t type \t stage
_secret_dump_items() {
  local kc=${1:-$_kc}
  _secret_kc_ensure "$kc"
  # an attribute holding anything but printable ASCII (a "·", Japanese text) is dumped as
  # 0x<hex>  "<octal escapes>": the hex is decoded to its bytes, so ls/show print the text itself
  # (awk runs in the C locale, so each %c is one byte and the UTF-8 survives)
  security dump-keychain "$kc" 2>/dev/null | LC_ALL=C awk '
    function hexval(c) { return index("0123456789abcdef", tolower(c)) - 1 }
    function unhex(h,   out, i, b) {
      out = ""
      for (i = 3; i < length(h); i += 2) {
        b = hexval(substr(h, i, 1)) * 16 + hexval(substr(h, i + 1, 1))
        if (b == 0) continue
        out = out ((b == 9 || b == 10 || b == 13) ? " " : sprintf("%c", b))
      }
      return out
    }
    function val(s,   hex) {
      sub(/^[^=]*=/, "", s)
      if (s == "<NULL>") return ""
      if (match(s, /^0x[0-9A-Fa-f]+/)) return unhex(substr(s, 1, RLENGTH))
      gsub(/^"|"$/, "", s)
      return s
    }
    function flush(   rest, at, slash, proj, scope, stage) {
      if (item && svce ~ /^secret\./) {
        rest = substr(svce, 8)
        at = index(rest, "@")
        if (at > 0) { stage = substr(rest, at + 1); rest = substr(rest, 1, at - 1) }
        else        { stage = "" }
        slash = index(rest, "/")
        if (slash > 0) { proj = substr(rest, 1, slash - 1); scope = substr(rest, slash + 1) }
        else           { proj = rest; scope = "" }
        printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", proj, acct, labl, desc, icmt, mdat, scope, gena, ctyp, stage
      }
      item = 0
    }
    /^keychain:/            { flush() }
    /^class: "genp"/        { item = 1; acct = svce = labl = desc = icmt = mdat = gena = ctyp = ""; next }
    !item                   { next }
    /^ *"acct"<blob>=/      { acct = val($0) }
    /^ *"svce"<blob>=/      { svce = val($0) }
    /^ *0x00000007 <blob>=/ { labl = val($0) }
    /^ *"desc"<blob>=/      { desc = val($0) }
    /^ *"icmt"<blob>=/      { icmt = val($0) }
    /^ *"gena"<blob>=/      { gena = val($0) }
    /^ *"type"<uint32>=/    { ctyp = val($0) }
    /^ *"mdat"<timedate>=/  {
      if (match($0, /"[0-9]+Z\\000"/)) mdat = substr($0, RSTART + 1, RLENGTH - 6)
    }
    END { flush() }
  '
}

# Unlock, in the calling process, every keychain _secret_rows "$1" dumps:
# the dump itself runs in a pipeline, so this is what lets the memo serve
# the value reads that follow (env, export).
_secret_rows_ensure() {        # $1 project ("" = every registered keychain)
  local kc
  if [[ -n $1 ]]; then
    _secret_kc_ensure "$(_secret_kc_for "$1")"
  elif (( _kc_explicit )); then
    _secret_kc_ensure "$_kc"
  else
    _secret_kc_sl_load         # here, so the $(...) below and the dump reuse it
    for kc in ${(f)"$(_secret_kc_customs)"}; do
      [[ -n $kc ]] && _secret_kc_ensure "$kc"
    done
  fi
  return 0
}

_secret_rows() {               # $1 project ("" = every registered keychain)
  _secret_rows_ensure "$1"
  if [[ -n $1 ]]; then
    _secret_dump_items "$(_secret_kc_for "$1")" | awk -F'\t' -v p="$1" '$1 == p'
  elif (( _kc_explicit )); then
    _secret_dump_items "$_kc"
  else
    local kc
    for kc in ${(f)"$(_secret_kc_customs)"}; do
      [[ -n $kc ]] && _secret_dump_items "$kc"
    done
  fi | sort -t$'\t' -k1,1 -k10,10 -k7,7 -k2,2
}

_secret_row_layer() {          # $1 TSV row -> its layer string
  local -a f
  f=("${(@ps:\t:)1}")
  _secret_layer "${f[7]}" "${f[10]}"
}

_secret_clip() {               # copy $1, auto-clear after 45s if still ours
  print -rn -- "$1" | pbcopy
  ( sleep 45
    [[ "$(pbpaste 2>/dev/null)" == "$1" ]] && pbcopy </dev/null
  ) >/dev/null 2>&1 &!
}

_secret_tsv_unescape() {       # undo jq @tsv escaping
  local s=$1
  s=${s//'\\'/$'\x01'}
  s=${s//'\t'/$'\t'}
  s=${s//'\n'/$'\n'}
  s=${s//'\r'/$'\r'}
  s=${s//$'\x01'/\\}
  print -r -- "$s"
}

# ------------------------------------------------------------ subcommands --

# Plan the ENV / meta attributes of a write from the item's current row and
# the caller's --env/--no-env and --meta edits. Sets $_plan_env (yes|no|keep)
# and $_plan_meta (attribute string|keep) in the caller's scope. Rewriting
# the meta of an item whose ENV still lives in the legacy marker pins the
# setting into the type first, so the marker can be dropped without change.
_secret_plan_attrs() {         # $1 row ("" = new item)  $2 env_opt (yes|no|"")  $3.. meta edits
  local row=$1 env_opt=$2
  shift 2
  local -a f
  f=("${(@ps:\t:)row}")
  _plan_env=${env_opt:-keep}
  _plan_meta=keep
  (( $# )) || return 0
  _plan_meta=$(_secret_meta_merge "${f[8]}" "$@") || return 1
  if [[ $_plan_env == keep && -z ${f[9]} ]]; then
    _secret_env_on "${f[9]}" "${f[8]}" && _plan_env=yes || _plan_env=no
  fi
  return 0
}

_secret_cmd_set() {
  local name="" proj="" comment="" kind="" from_stdin=0 scoped=0 scope_opt="" env_opt="" create=""
  local stage_opt="" no_stage=0
  local -a meta_opts
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      -j) comment=$2; shift 2 ;;
      -D) kind=$2; shift 2 ;;
      -S|--scoped) scoped=1; shift ;;
      --scope) scope_opt=$2; shift 2 ;;
      --stage) stage_opt=$2; shift 2 ;;
      --no-stage) no_stage=1; shift ;;
      --meta) meta_opts+=("$2"); shift 2 ;;
      --new) create=new; shift ;;
      --stdin) from_stdin=1; shift ;;
      --env) env_opt=yes; shift ;;
      --no-env) env_opt=no; shift ;;
      -*) _secret_err "set: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  [[ -z $name ]] && { _secret_err "set: NAME required"; return 2 }
  _secret_check_name "$name" || return 2
  proj=$(_secret_resolve_project "$proj")
  _secret_check_project "$proj" || return 2
  local scope stage layer
  scope=$(_secret_resolve_scope "$scope_opt" $scoped "$proj") || return 2
  stage=$(_secret_resolve_stage "$stage_opt" $no_stage) || return 2
  layer=$(_secret_layer "$scope" "$stage")
  _secret_stage_note "$proj" "$stage"
  local disp
  disp=$(_secret_disp "$proj" "$layer" "$name")
  if [[ $create == new ]] && _secret_exists "$name" "$proj" "$layer"; then
    _secret_err "set: $disp already exists; --new never overwrites"
    return 1
  fi
  # no --env/--no-env/--meta: an existing item keeps its attributes, a new one has none
  local row="" _plan_env _plan_meta
  local -a f
  if [[ -n $env_opt ]] || (( ${#meta_opts} )); then
    row=$(_secret_row_of "$name" "$proj" "$layer")
  fi
  _secret_plan_attrs "$row" "$env_opt" "${meta_opts[@]}" || return 2
  f=("${(@ps:\t:)row}")

  if (( from_stdin )) || [[ ! -t 0 ]]; then
    _secret_store "$name" "$proj" "$comment" "$kind" "$layer" "$_plan_env" "$_plan_meta" "$create" || return 1
  else
    local value
    value=$(_secret_prompt_value "$disp") || return 1
    print -r -- "$value" | _secret_store "$name" "$proj" "$comment" "$kind" "$layer" "$_plan_env" "$_plan_meta" "$create" || return 1
  fi
  local lbl note=""
  lbl=$(_secret_kc_label "$proj")
  if [[ $_plan_env == no ]]; then
    note=" (env: no)"
  elif [[ $_plan_env == keep ]]; then
    [[ -n $row ]] || row=$(_secret_row_of "$name" "$proj" "$layer")
    f=("${(@ps:\t:)row}")
    _secret_env_on "${f[9]}" "${f[8]}" || note=" (env: no)"
  fi
  print -r -- "stored $disp$note${lbl:+ [keychain: $lbl]}"
}

# Shared layer-targeting flags for get/show/rm/update:
#   (none)      DWIM — the stage's scoped layer, the stage's shared layer,
#               the ambient scope, then the shared layer
#   -S/--scoped the ambient scope only
#   --scope X   that scope only
#   --shared    the shared layer only
#   --stage S / --no-stage pin the stage ($SECRET_STAGE otherwise); with a
#   stage, the exact flags above address that stage's layer
# Sets $_layer_scope, $_layer_stage and $_layer_mode (auto|exact) in the
# caller's scope.
_secret_layer_flags() {        # $1 scope_opt  $2 scoped  $3 shared  $4 project  $5 stage_opt  $6 no_stage
  _layer_stage=$(_secret_resolve_stage "${5-}" "${6-0}") || return 1
  if [[ -n $1 ]]; then
    _layer_scope=$(_secret_resolve_scope "$1" 0 "$4") || return 1
    _layer_mode=exact
  elif (( $3 )); then
    _layer_scope=""
    _layer_mode=exact
  elif (( $2 )); then
    _layer_scope=$(_secret_resolve_scope "" 1 "$4") || return 1
    _layer_mode=exact
  else
    _layer_scope=$(_secret_ambient_scope "$4")
    _layer_mode=auto
  fi
  return 0
}

# Locate an item according to $_layer_mode/$_layer_scope/$_layer_stage.
# Prints the owning layer; returns 1 when the item is not found.
_secret_locate() {             # $1 name  $2 project
  if [[ $_layer_mode == exact ]]; then
    local layer
    layer=$(_secret_layer "$_layer_scope" "$_layer_stage")
    _secret_exists "$1" "$2" "$layer" || return 1
    print -r -- "$layer"
    return 0
  fi
  _secret_find_layer "$1" "$2" "$_layer_scope" "$_layer_stage"
}

# "not found" wording for the layer flags in effect
_secret_layer_disp() {         # $1 project  $2 name -> display for $_layer_scope/$_layer_stage
  _secret_disp "$1" "$(_secret_layer "$_layer_scope" "$_layer_stage")" "$2"
}

# The token `ls` prints, "[scope/]NAME[@stage]", is accepted wherever a NAME
# is (get/show/update/rm): it names that exact layer, as if the layer flags
# had been given. A bare NAME passes through untouched. Rewrites argv into
# $reply; options that take a value are skipped so a comment or meta value
# holding '/' or '@' is never mistaken for a token.
_secret_argv_expand() {        # $@ argv -> reply
  reply=()
  local a skip=0 _tok_name _tok_layer
  local -a _tok_flags
  for a in "$@"; do
    if (( skip )); then reply+=("$a"); skip=0; continue; fi
    case $a in
      -p|-j|-D|--scope|--stage|--meta) reply+=("$a"); skip=1 ;;
      -*) reply+=("$a") ;;
      *[/@]*)
        _secret_ui_split_token "$a"
        reply+=("$_tok_name" "${_tok_flags[@]}") ;;
      *) reply+=("$a") ;;
    esac
  done
}

_secret_cmd_update() {
  local name="" proj="" comment="" kind="" env_opt=""
  local comment_set=0 kind_set=0 want_value=0 from_stdin=0
  local scoped=0 shared=0 scope_opt="" stage_opt="" no_stage=0
  local -a meta_opts reply
  _secret_argv_expand "$@"; set -- "${reply[@]}"
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      -j) comment=$2; comment_set=1; shift 2 ;;
      -D) kind=$2; kind_set=1; shift 2 ;;
      --meta) meta_opts+=("$2"); shift 2 ;;
      --env) env_opt=yes; shift ;;
      --no-env) env_opt=no; shift ;;
      -S|--scoped) scoped=1; shift ;;
      --scope) scope_opt=$2; shift 2 ;;
      --shared) shared=1; shift ;;
      --stage) stage_opt=$2; shift 2 ;;
      --no-stage) no_stage=1; shift ;;
      --value) want_value=1; shift ;;
      --stdin) from_stdin=1; shift ;;
      -*) _secret_err "update: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  [[ -z $name ]] && { _secret_err "update: NAME required"; return 2 }
  proj=$(_secret_resolve_project "$proj")
  local _layer_scope _layer_stage _layer_mode layer disp
  _secret_layer_flags "$scope_opt" $scoped $shared "$proj" "$stage_opt" $no_stage || return 2
  if ! layer=$(_secret_locate "$name" "$proj"); then
    _secret_err "not found: $(_secret_layer_disp "$proj" "$name") (use 'secret set' to create it)"
    return 1
  fi
  disp=$(_secret_disp "$proj" "$layer" "$name")
  if (( ! want_value && ! from_stdin && ! comment_set && ! kind_set && ! ${#meta_opts} )) && [[ -z $env_opt ]]; then
    _secret_err "update: nothing to do (use --value/--stdin, -j COMMENT, -D KIND, --meta K=V, --env/--no-env)"
    return 2
  fi

  # merge with current metadata
  local row _plan_env _plan_meta
  row=$(_secret_row_of "$name" "$proj" "$layer")
  local -a f
  f=("${(@ps:\t:)row}")
  (( kind_set )) || kind=${f[4]}
  (( comment_set )) || comment=${f[5]}
  _secret_plan_attrs "$row" "$env_opt" "${meta_opts[@]}" || return 2

  if (( from_stdin )) || ( (( want_value )) && [[ ! -t 0 ]] ); then
    _secret_store "$name" "$proj" "$comment" "$kind" "$layer" "$_plan_env" "$_plan_meta" || return 1
  else
    local value
    if (( want_value )); then
      value=$(_secret_prompt_value "$disp") || return 1
    else
      value=$(_secret_get_value "$name" "$proj" "$layer") || {
        _secret_err "cannot read current value of $disp"; return 1
      }
    fi
    print -r -- "$value" | _secret_store "$name" "$proj" "$comment" "$kind" "$layer" "$_plan_env" "$_plan_meta" || return 1
  fi

  local -a parts
  (( want_value || from_stdin )) && parts+=(value)
  (( comment_set )) && parts+=(comment)
  (( kind_set )) && parts+=(kind)
  (( ${#meta_opts} )) && parts+=(meta)
  [[ -n $env_opt ]] && parts+=("env: $env_opt")
  local lbl
  lbl=$(_secret_kc_label "$proj")
  print -r -- "updated $disp (${(j:, :)parts})${lbl:+ [keychain: $lbl]}"
}

_secret_cmd_get() {
  local name="" proj="" copy=0 scoped=0 shared=0 scope_opt="" stage_opt="" no_stage=0
  local -a reply
  _secret_argv_expand "$@"; set -- "${reply[@]}"
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      -c|--copy) copy=1; shift ;;
      -S|--scoped) scoped=1; shift ;;
      --scope) scope_opt=$2; shift 2 ;;
      --shared) shared=1; shift ;;
      --stage) stage_opt=$2; shift 2 ;;
      --no-stage) no_stage=1; shift ;;
      -*) _secret_err "get: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  [[ -z $name ]] && { _secret_err "get: NAME required"; return 2 }
  proj=$(_secret_resolve_project "$proj")
  local _layer_scope _layer_stage _layer_mode layer v disp
  _secret_layer_flags "$scope_opt" $scoped $shared "$proj" "$stage_opt" $no_stage || return 2
  if ! layer=$(_secret_locate "$name" "$proj"); then
    _secret_err "not found: $(_secret_layer_disp "$proj" "$name")"
    return 1
  fi
  disp=$(_secret_disp "$proj" "$layer" "$name")
  v=$(_secret_get_value "$name" "$proj" "$layer") || {
    _secret_err "cannot read $disp"; return 1
  }
  if (( copy )); then
    _secret_clip "$v"
    print -r -- "copied $disp to clipboard (clears in 45s)"
  else
    print -r -- "$v"
  fi
}

_secret_cmd_show() {
  local name="" proj="" scoped=0 shared=0 scope_opt="" stage_opt="" no_stage=0
  local -a reply
  _secret_argv_expand "$@"; set -- "${reply[@]}"
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      -S|--scoped) scoped=1; shift ;;
      --scope) scope_opt=$2; shift 2 ;;
      --shared) shared=1; shift ;;
      --stage) stage_opt=$2; shift 2 ;;
      --no-stage) no_stage=1; shift ;;
      -*) _secret_err "show: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  [[ -z $name ]] && { _secret_err "show: NAME required"; return 2 }
  proj=$(_secret_resolve_project "$proj")
  local _layer_scope _layer_stage _layer_mode layer
  _secret_layer_flags "$scope_opt" $scoped $shared "$proj" "$stage_opt" $no_stage || return 2
  if ! layer=$(_secret_locate "$name" "$proj"); then
    _secret_err "not found: $(_secret_layer_disp "$proj" "$name")"
    return 1
  fi
  local row
  row=$(_secret_row_of "$name" "$proj" "$layer")
  [[ -z $row ]] && { _secret_err "not found: $(_secret_disp "$proj" "$layer" "$name")"; return 1 }
  local -a f fields
  f=("${(@ps:\t:)row}")
  fields=(${(f)"$(_secret_meta_fields "${f[8]}")"})
  printf '%-10s %s\n' \
    'Name:'     "${f[2]}" \
    'Project:'  "${f[1]}" \
    'Scope:'    "${f[7]:-Shared}" \
    'Stage:'    "${f[10]:-(none)}" \
    'Label:'    "${f[3]}" \
    'Kind:'     "${f[4]}" \
    'Comment:'  "${f[5]}" \
    'Env:'      "$(_secret_env_on "${f[9]}" "${f[8]}" && print yes || print 'no (never emitted by secret env)')" \
    'Meta:'     "${fields[1]:-(none)}"
  local fld
  for fld in "${fields[@]:1}"; do printf '%-10s %s\n' '' "$fld"; done
  printf '%-10s %s\n' \
    'Modified:' "$(_secret_fmt_date "${f[6]}")" \
    'Keychain:' "$(_secret_kc_for "$proj")"
}

_secret_cmd_ls() {
  local proj="" long=0 all=0 wide=0 json=0
  local -a meta_filters
  local stage_filter="" stage_set=0
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      -l|--long) long=1; shift ;;
      --json) json=1; shift ;;
      --all) all=1; shift ;;
      --wide) wide=1; shift ;;
      --meta) meta_filters+=("$2"); shift 2 ;;
      --stage) stage_filter=$2; stage_set=1; shift 2 ;;
      --no-stage) stage_filter=""; stage_set=1; shift ;;
      -*) _secret_err "ls: unknown option '$1'"; return 2 ;;
      *) _secret_err "ls: unexpected argument '$1'"; return 2 ;;
    esac
  done
  local flt
  for flt in "${meta_filters[@]}"; do
    _secret_meta_check_key "${flt%%=*}" || return 2
  done
  [[ -n $stage_filter ]] && { _secret_check_stage "$stage_filter" || return 2; stage_filter=$(_secret_canon_stage "$stage_filter") }
  (( json && long )) && { _secret_err "ls: --json and --long are exclusive"; return 2 }
  local where
  if (( all )); then
    proj=""; where="any project"
  else
    proj=$(_secret_resolve_project "$proj"); where="project '$proj'"
  fi
  local rows row kept=""
  local -a f
  rows=$(_secret_rows "$proj")
  if [[ -z $rows ]]; then
    (( json )) && { print -r -- "[]"; return 0 }
    print -r -- "no secrets in $where" >&2; return 0
  fi
  if (( ${#meta_filters} || stage_set )); then
    # every --meta KEY[=VALUE] must match (fields are column 8); --stage S
    # keeps that stage's layers only, --no-stage the stage-less ones
    while IFS= read -r row; do
      f=("${(@ps:\t:)row}")
      (( stage_set )) && [[ ${f[10]} != "$stage_filter" ]] && continue
      for flt in "${meta_filters[@]}"; do
        _secret_meta_matches "${f[8]}" "$flt" || continue 2
      done
      kept+="$row"$'\n'
    done <<< "$rows"
    rows=${kept%$'\n'}
    if [[ -z $rows ]]; then
      (( json )) && { print -r -- "[]"; return 0 }
      print -r -- "no secrets in $where match the filters" >&2; return 0
    fi
  fi
  if (( json )); then
    _secret_ls_json "$rows"
  elif (( long )); then
    local -i width=0
    if (( ! wide )); then
      if [[ -n ${COLUMNS:-} ]]; then width=$COLUMNS
      elif [[ -t 1 ]]; then width=$(tput cols 2>/dev/null || print 0)
      fi
    fi
    _secret_ls_long "$rows" $width
  elif (( all )); then
    print -r -- "$rows" | awk -F'\t' '{ print $1 "/" ($7 == "" ? "" : $7 "/") $2 ($10 == "" ? "" : "@" $10) }'
  else
    # "scope/NAME@stage" — the token the fzf pickers hand back to the layer flags
    print -r -- "$rows" | awk -F'\t' '{ print ($7 == "" ? "" : $7 "/") $2 ($10 == "" ? "" : "@" $10) }'
  fi
}

_secret_json_str() {           # $1 text -> a JSON string literal
  local s=$1
  s=${s//\\/\\\\}; s=${s//\"/\\\"}
  s=${s//$'\t'/\\t}; s=${s//$'\n'/\\n}; s=${s//$'\r'/\\r}
  s=${s//[[:cntrl:]]/ }
  print -rn -- "\"$s\""
}

# The listing for programs: a JSON array, one object per item, with the
# fields (and their spelling) of `export --format json` minus the value —
# `ls` never reads one. This is the format to parse; the --long table is for
# people and changes with them. Needs nothing but zsh, so a caller with a bare
# PATH (/usr/bin:/bin, no jq) can use it.
_secret_ls_json() {            # $1 TSV rows
  local row kv out="" sep=""
  local -a f fields
  while IFS= read -r row; do
    [[ -n $row ]] || continue
    f=("${(@ps:\t:)row}")
    fields=()
    for kv in ${(f)"$(_secret_meta_fields "${f[8]}")"}; do
      [[ -n $kv ]] || continue
      fields+=("$(_secret_json_str "${kv%%=*}"): $(_secret_json_str "${kv#*=}")")
    done
    out+="$sep  {\"project\": $(_secret_json_str "${f[1]}"), \"scope\": $(_secret_json_str "${f[7]}"),"
    out+=" \"stage\": $(_secret_json_str "${f[10]}"), \"name\": $(_secret_json_str "${f[2]}"),"
    out+=" \"kind\": $(_secret_json_str "${f[4]}"), \"comment\": $(_secret_json_str "${f[5]}"),"
    out+=" \"env\": \"$(_secret_env_on "${f[9]}" "${f[8]}" && print -n yes || print -n no)\","
    out+=" \"meta\": {${(j:, :)fields}}, \"modified\": $(_secret_json_str "$(_secret_fmt_date "${f[6]}")")}"
    sep=$',\n'
  done <<< "$1"
  local nl=$'\n'
  print -r -- "[${out:+$nl}$out${out:+$nl}]"
}

_secret_fit() {                # $1 text  $2 width -> text cut to width with an ellipsis
  local s=$1
  local -i w=$2
  (( w <= 0 )) && { print -rn -- ""; return 0 }
  if (( ${#s} > w )); then
    (( w == 1 )) && s="…" || s="${s[1,w-1]}…"
  fi
  print -rn -- "$s"
}

# The long listing: one block per project, inside it one group per layer
# (shared, scope/, @stage, scope/ @stage) with NAME, KIND, ENV, MODIFIED,
# META and COMMENT rows. The four leading columns are sized to the project's
# content; META and COMMENT share what is left of the width and are cut
# with an ellipsis (COMMENT keeps at least a third), so a row never wraps.
# Width 0 means unbounded (--wide, or no terminal). Colour only on a
# terminal and without NO_COLOR: project bold, stage groups magenta, ENV no
# yellow.
_secret_ls_long() {            # $1 TSV rows  $2 width
  local rows=$1
  local -i width=$2
  local bold="" dim="" mag="" yel="" off=""
  if [[ -t 1 && -z ${NO_COLOR:-} ]]; then
    bold=$'\e[1m' dim=$'\e[2m' mag=$'\e[35m' yel=$'\e[33m' off=$'\e[0m'
  fi
  local row proj="" group="" g mod meta env comment name kind line
  local -a f
  # pass 1: per-project column widths (name, kind), longest meta and comment
  local -A wn wk wt wc
  local -i i
  while IFS= read -r row; do
    f=("${(@ps:\t:)row}")
    meta=${(j:;:)${(f)"$(_secret_meta_fields "${f[8]}")"}}
    (( ${#f[2]} > ${wn[${f[1]}]:-4} )) && wn[${f[1]}]=${#f[2]}
    (( ${#f[4]} > ${wk[${f[1]}]:-4} )) && wk[${f[1]}]=${#f[4]}
    (( ${#meta} > ${wt[${f[1]}]:-0} )) && wt[${f[1]}]=${#meta}
    (( ${#f[5]} > ${wc[${f[1]}]:-0} )) && wc[${f[1]}]=${#f[5]}
  done <<< "$rows"
  local -i cn ck ct cc avail
  while IFS= read -r row; do
    f=("${(@ps:\t:)row}")
    if [[ ${f[1]} != "$proj" ]]; then
      proj=${f[1]}; group=""
      [[ -n $proj ]] && print -r -- "${bold}${proj}${off}"
      cn=${wn[$proj]:-4}; ck=${wk[$proj]:-4}
      # 4 indent + name + 2 + kind + 2 + env(3) + 2 + date(10) + 2
      avail=$(( width - 4 - cn - 2 - ck - 2 - 3 - 2 - 10 - 2 ))
      ct=${wt[$proj]:-0}; cc=${wc[$proj]:-0}
      if (( width > 0 )); then
        (( avail < 0 )) && avail=0
        if (( ct + (cc > 0 ? cc + 2 : 0) > avail )); then
          if (( cc > 0 )); then
            (( cc > avail / 3 )) && cc=$(( avail / 3 ))
            (( ct > avail - cc - 2 )) && ct=$(( avail - cc - 2 ))
            (( ct < 0 )) && ct=0
          else
            ct=$avail
          fi
        fi
      fi
      # column header, with META / COMMENT only when the project has any
      printf -v line "    %-${cn}s  %-${ck}s  %s  %-10s" NAME KIND ENV MODIFIED
      if (( ${wc[$proj]:-0} > 0 )); then
        printf -v line "%s  %-${ct}s  %s" "$line" META COMMENT
      elif (( ${wt[$proj]:-0} > 0 )); then
        line+="  META"
      fi
      print -r -- "${dim}${line%%[[:space:]]#}${off}"
    fi
    g="${f[7]:+${f[7]}/}${f[10]:+${f[7]:+ }@${f[10]}}"
    [[ -z $g ]] && g=shared
    if [[ $g != "$group" ]]; then
      group=$g
      if [[ -n ${f[10]} ]]; then print -r -- "  ${mag}${g}${off}"; else print -r -- "  ${dim}${g}${off}"; fi
    fi
    name=${f[2]}; kind=${f[4]}
    mod=$(_secret_fmt_date "${f[6]}"); mod=${mod[1,10]}
    meta=${(j:;:)${(f)"$(_secret_meta_fields "${f[8]}")"}}
    comment=${f[5]}
    if _secret_env_on "${f[9]}" "${f[8]}"; then env="yes"; else env="${yel}no ${off}"; fi
    if (( width > 0 )); then
      meta=$(_secret_fit "$meta" $ct); comment=$(_secret_fit "$comment" $cc)
    fi
    if [[ -n $comment ]]; then
      printf -v line "    %-${cn}s  %-${ck}s  %s  %-10s  %-${ct}s  %s" "$name" "$kind" "$env" "$mod" "$meta" "$comment"
    else
      printf -v line "    %-${cn}s  %-${ck}s  %s  %-10s  %s" "$name" "$kind" "$env" "$mod" "$meta"
    fi
    print -r -- "${line%%[[:space:]]#}"
  done <<< "$rows"
}

_secret_cmd_projects() {
  # 1:1 model: a project is a registered custom keychain (names only —
  # nothing is dumped, so locked keychains never trigger unlock prompts)
  if (( _kc_explicit )); then
    _secret_dump_items "$_kc" | cut -f1 | sort -u
    return
  fi
  local kc
  for kc in ${(f)"$(_secret_kc_customs)"}; do
    [[ -n $kc ]] && print -r -- "${${kc:t}%.keychain-db}"
  done | sort -u
}

_secret_cmd_env() {
  local proj="" scope_opt="" stage_opt="" no_stage=0
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      --scope) scope_opt=$2; shift 2 ;;
      --stage) stage_opt=$2; shift 2 ;;
      --no-stage) no_stage=1; shift ;;
      -*) _secret_err "env: unknown option '$1'"; return 2 ;;
      *) _secret_err "env: unexpected argument '$1'"; return 2 ;;
    esac
  done
  proj=$(_secret_resolve_project "$proj")
  local scope stage
  if [[ -n $scope_opt ]]; then
    scope=$(_secret_resolve_scope "$scope_opt" 0 "$proj") || return 2
  else
    scope=$(_secret_ambient_scope "$proj")
  fi
  stage=$(_secret_resolve_stage "$stage_opt" $no_stage) || return 2
  # overlay, least to most specific: shared < scoped < shared@stage <
  # scoped@stage — a stage layer always beats a stage-less one, so asking
  # for prod never hands out a repository's dev value; names a stage does
  # not hold fall back to the stage-less layers. Items of other stages are
  # never emitted. An item flagged env=no is never emitted, and its name
  # stays out even when a lower layer holds one: the winning layer decides.
  local row name
  local -a f
  local -A rank_of layer_of noenv_of
  local -i rank
  _secret_rows_ensure "$proj"   # once, here: the dump and every value run in $(...)
  while IFS= read -r row; do
    [[ -n $row ]] || continue
    f=("${(@ps:\t:)row}")
    if [[ -n ${f[10]} ]]; then
      [[ -n $stage && ${f[10]} == "$stage" ]] || continue
      rank=3
    else
      rank=1
    fi
    if [[ -n ${f[7]} ]]; then
      [[ -n $scope && ${f[7]} == "$scope" ]] || continue
      (( rank++ ))
    fi
    (( rank > ${rank_of[${f[2]}]:-0} )) || continue
    rank_of[${f[2]}]=$rank
    layer_of[${f[2]}]=$(_secret_layer "${f[7]}" "${f[10]}")
    if _secret_env_on "${f[9]}" "${f[8]}"; then
      unset "noenv_of[${f[2]}]"
    else
      noenv_of[${f[2]}]=1
    fi
  done <<< "$(_secret_rows "$proj")"
  local v lay
  for name in ${(ko)layer_of}; do
    [[ -n ${noenv_of[$name]-} ]] && continue
    lay=${layer_of[$name]}
    if ! v=$(_secret_get_value "$name" "$proj" "$lay"); then
      _secret_err "skipped $(_secret_disp "$proj" "$lay" "$name") (unreadable)"; continue
    fi
    print -r -- "export ${name}=${(qq)v}"
  done
}

_secret_cmd_rm() {
  local name="" proj="" force=0 scoped=0 shared=0 scope_opt="" stage_opt="" no_stage=0
  local -a reply
  _secret_argv_expand "$@"; set -- "${reply[@]}"
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      -f|--force) force=1; shift ;;
      -S|--scoped) scoped=1; shift ;;
      --scope) scope_opt=$2; shift 2 ;;
      --shared) shared=1; shift ;;
      --stage) stage_opt=$2; shift 2 ;;
      --no-stage) no_stage=1; shift ;;
      -*) _secret_err "rm: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  [[ -z $name ]] && { _secret_err "rm: NAME required"; return 2 }
  proj=$(_secret_resolve_project "$proj")
  local _layer_scope _layer_stage _layer_mode layer disp
  _secret_layer_flags "$scope_opt" $scoped $shared "$proj" "$stage_opt" $no_stage || return 2
  if ! layer=$(_secret_locate "$name" "$proj"); then
    _secret_err "not found: $(_secret_layer_disp "$proj" "$name")"
    return 1
  fi
  disp=$(_secret_disp "$proj" "$layer" "$name")
  if (( ! force )) && [[ -t 0 ]]; then
    local reply
    if ! read -q "reply?delete $disp? [y/N] "; then print '' >&2; return 1; fi
    print '' >&2
  fi
  if _secret_delete "$name" "$proj" "$layer"; then
    local lbl
    lbl=$(_secret_kc_label "$proj")
    print -r -- "deleted $disp${lbl:+ [keychain: $lbl]}"
  else
    _secret_err "failed to delete $disp"; return 1
  fi
}

_secret_export_json() {        # $1 project ("" = all); JSON document on stdout
  local row v
  local -a f
  _secret_rows "$1" | while IFS= read -r row; do
    f=("${(@ps:\t:)row}")
    v=$(_secret_get_value "${f[2]}" "${f[1]}" "$(_secret_row_layer "$row")") || continue
    # meta: one KEY=VALUE per line, turned into an object (values never hold ';')
    print -r -- "$v" | jq -Rc \
      --arg project "${f[1]}" --arg name "${f[2]}" --arg kind "${f[4]}" \
      --arg comment "${f[5]}" --arg scope "${f[7]}" --arg stage "${f[10]}" \
      --arg env "$(_secret_env_on "${f[9]}" "${f[8]}" && print yes || print no)" \
      --arg meta "$(_secret_meta_fields "${f[8]}")" \
      '{project: $project, scope: $scope, stage: $stage, name: $name, kind: $kind, comment: $comment, env: $env,
        meta: ($meta | split("\n") | map(select(length > 0) | capture("^(?<k>[^=]*)=(?<v>.*)$")
                                        | {key: .k, value: .v}) | from_entries),
        value: .}'
  done | jq -s --arg exported "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{version: 1, exported: $exported, items: .}'
}

_secret_export_env() {         # $1 project ("" = all); export lines on stdout
  local row v meta last=""
  local -a f
  _secret_rows "$1" | while IFS= read -r row; do
    f=("${(@ps:\t:)row}")
    v=$(_secret_get_value "${f[2]}" "${f[1]}" "$(_secret_row_layer "$row")") || continue
    if [[ "${f[1]}|${f[7]}|${f[10]}" != "$last" ]]; then
      print -r -- "# === project: ${f[1]}${f[7]:+ (scope: ${f[7]})}${f[10]:+ (stage: ${f[10]})} ==="
      last="${f[1]}|${f[7]}|${f[10]}"
    fi
    # meta rides on a comment line right above the item ("#meta:K=V;..."),
    # so the file still sources; import attaches it to the export that follows.
    # An env=no item stays commented out, so sourcing the file never exports
    # it; import reads the marker back as env=no
    meta=${(j:;:)${(f)"$(_secret_meta_fields "${f[8]}")"}}
    [[ -n $meta ]] && print -r -- "#meta:$meta"
    _secret_env_on "${f[9]}" "${f[8]}" || print -rn -- "#no-env# "
    print -r -- "export ${f[2]}=${(qq)v}"
  done
}

_secret_cmd_export() {
  local proj="" all=0 out="" fmt=""
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      --all) all=1; shift ;;
      -o) out=$2; shift 2 ;;
      --format) fmt=$2; shift 2 ;;
      --age) fmt=age; shift ;;
      --json) fmt=json; shift ;;
      --env|--plain) fmt=env; shift ;;
      *) _secret_err "export: unknown option '$1'"; return 2 ;;
    esac
  done
  if (( all )); then
    proj=""
  else
    proj=$(_secret_resolve_project "$proj")
  fi
  local rows
  _secret_rows_ensure "$proj"   # the dump and the value reads below run in children
  rows=$(_secret_rows "$proj")
  [[ -z $rows ]] && { _secret_err "nothing to export (project: ${proj:-all})"; return 1 }

  if [[ -z $fmt && -n $out ]]; then
    case $out in
      *.age) fmt=age ;;
      *.json) fmt=json ;;
      *.env) fmt=env ;;
    esac
  fi
  : ${fmt:=age}
  case $fmt in
    age|json|env) ;;
    *) _secret_err "export: unknown format '$fmt' (age|json|env)"; return 2 ;;
  esac
  if [[ -z $out ]]; then
    local ext=$fmt
    [[ $fmt == age ]] && ext="json.age"
    out="secret-export-${proj:-all}-$(date +%Y%m%d).$ext"
  fi

  command -v jq >/dev/null 2>&1 || { _secret_err "jq is required (brew install jq)"; return 1 }
  [[ $fmt == age ]] && { command -v age >/dev/null 2>&1 || { _secret_err "age is required (brew install age)"; return 1 } }
  [[ $fmt == age ]] || print -r -- "warning: '$out' will contain plaintext secrets" >&2
  # The file is private from its first byte and either whole or absent: it is
  # written under umask 077 into a temporary file beside the destination and
  # renamed over it on success — the rename brings its own 0600, so a wider
  # mode an existing file had is not kept — and removed on failure.
  [[ -d $out ]] && { _secret_err "'$out' is a directory"; return 1 }
  local tmp="" rc=0 oldmask
  oldmask=$(umask)
  {
    umask 077
    tmp=$(mktemp "${out:h}/.${out:t}.XXXXXX" 2>/dev/null) || {
      _secret_err "cannot create a file in '${out:h}'"; rc=1
    }
    if (( ! rc )); then
      case $fmt in
        age)  _secret_export_json "$proj" | age ${=SECRET_AGE_ARGS:--p} -o "$tmp" || { rc=1; _secret_err "age encryption failed" } ;;
        json) _secret_export_json "$proj" > "$tmp" || rc=1 ;;
        env)  _secret_export_env "$proj" > "$tmp" || rc=1 ;;
      esac
    fi
  } always {
    umask "$oldmask"                        # also on an interrupt
    (( rc )) && [[ -n $tmp ]] && rm -f -- "$tmp"
  }
  if (( rc )); then
    _secret_err "export failed; '$out' left untouched"
    return 1
  fi
  chmod 600 "$tmp"
  mv -f -- "$tmp" "$out" || { rm -f -- "$tmp"; _secret_err "could not write '$out'"; return 1 }
  local count lbl=""
  [[ -n $proj ]] && lbl=$(_secret_kc_label "$proj")
  count=$(print -r -- "$rows" | wc -l | tr -d ' ')
  print -r -- "exported $count item(s) (project: ${proj:-all})${lbl:+ [keychain: $lbl]} -> $out"
}

_secret_cmd_import() {
  local file="" proj_flag="" yes=0 scoped=0 scope_opt="" stage_opt="" no_stage=0
  while (( $# )); do
    case $1 in
      -p) proj_flag=$2; shift 2 ;;
      -y|--yes) yes=1; shift ;;
      -S|--scoped) scoped=1; shift ;;
      --scope) scope_opt=$2; shift 2 ;;
      --stage) stage_opt=$2; shift 2 ;;
      --no-stage) no_stage=1; shift ;;
      -*) _secret_err "import: unknown option '$1'"; return 2 ;;
      *) file=$1; shift ;;
    esac
  done
  [[ -z $file ]] && { _secret_err "import: FILE required"; return 2 }
  [[ -r $file ]] || { _secret_err "cannot read '$file'"; return 1 }

  local content
  if [[ $file == *.age || "$(head -c 21 -- "$file" 2>/dev/null)" == "age-encryption.org/v1" ]]; then
    command -v age >/dev/null 2>&1 || { _secret_err "age is required (brew install age)"; return 1 }
    content=$(age -d ${=SECRET_AGE_DECRYPT_ARGS} -- "$file") || {
      _secret_err "decryption failed"; return 1
    }
  else
    content=$(<"$file")
  fi

  # envs: yes / no from the file, or "" when it says nothing (older exports):
  # then an item being overwritten keeps its setting. metas: the item's
  # fields, one KEY=VALUE per line ("" clears them), or "keep" when the file
  # says nothing (no .meta key / no marker line), or "invalid-key" when a
  # JSON key is no identifier — neither word can be a real field (no '=')
  local -a names values projs comments kinds scopes stages envs metas
  local trimmed=${content##[[:space:]]#}
  local is_json=0
  if [[ $trimmed == \{* || $trimmed == \[* ]]; then
    is_json=1
    command -v jq >/dev/null 2>&1 || { _secret_err "jq is required (brew install jq)"; return 1 }
    # split with (ps:\t:) — IFS=tab read would collapse empty fields
    # (an empty comment used to swallow the following columns)
    local line
    local -a jf
    while IFS= read -r line; do
      [[ -n $line ]] || continue
      jf=("${(@ps:\t:)line}")
      names+=("$(_secret_tsv_unescape "${jf[1]}")")
      values+=("$(_secret_tsv_unescape "${jf[2]}")")
      projs+=("$(_secret_tsv_unescape "${jf[3]}")")
      comments+=("$(_secret_tsv_unescape "${jf[4]}")")
      kinds+=("$(_secret_tsv_unescape "${jf[5]}")")
      scopes+=("$(_secret_tsv_unescape "${jf[6]}")")
      envs+=("$(_secret_tsv_unescape "${jf[7]}")")
      metas+=("$(_secret_tsv_unescape "${jf[8]}")")
      stages+=("$(_secret_tsv_unescape "${jf[9]}")")
    done < <(print -r -- "$content" \
      | jq -r '.items[] | [.name, .value, (.project // ""), (.comment // ""), (.kind // ""), (.scope // ""),
                           (if .env == "no" or .env == false then "no" elif .env == "yes" or .env == true then "yes"
                            else "" end),
                           (if (.meta | type) != "object" then "keep"
                            elif any(.meta | keys[]; test("^[A-Za-z][A-Za-z0-9_-]*$") | not) then "invalid-key"
                            else (.meta | to_entries | sort_by(.key)
                                  | map("\(.key)=\(.value | tostring)") | join("\n")) end),
                           (.stage // "")] | @tsv') || true
  else
    local line n v e m="keep"
    while IFS= read -r line; do
      line=${line%$'\r'}
      [[ -z ${line//[[:space:]]/} ]] && continue
      line=${line##[[:space:]]#}
      if [[ $line == '#meta:'* ]]; then
        m=${${line#'#meta:'}//;/$'\n'}
        continue
      fi
      e=""
      if [[ $line == '#no-env# '* ]]; then
        line=${line#'#no-env# '}
        e=no
      fi
      [[ $line == \#* ]] && { m="keep"; continue }
      line=${line#export }
      [[ $line == *=* ]] || continue
      n=${line%%=*}
      v=${line#*=}
      n=${n%%[[:space:]]#}
      v=${(Q)v}
      names+=("$n"); values+=("$v"); projs+=(""); comments+=(""); kinds+=(""); scopes+=(""); stages+=(""); envs+=("$e")
      metas+=("$m"); m="keep"
    done <<< "$content"
  fi
  (( ${#names} )) || { _secret_err "no items found in '$file'"; return 1 }

  local base
  base=$(_secret_resolve_project "$proj_flag")
  # --stage/--no-stage override every item; otherwise JSON items keep their
  # recorded stage (none for older exports) and env files land in the
  # ambient stage ($SECRET_STAGE), like any other write
  local stage_all="" stage_forced=0
  if [[ -n $stage_opt ]] || (( no_stage )) || (( ! is_json )); then
    stage_all=$(_secret_resolve_stage "$stage_opt" $no_stage) || return 2
    stage_forced=1
  fi
  # a recorded scope or stage is validated on its own before the two are
  # joined into a layer: "api@prod" as a scope must not become stage prod
  local -a targets tlayers tbad
  local i tp ts tg bad
  for (( i = 1; i <= ${#names}; i++ )); do
    bad=0
    if [[ -n $proj_flag ]]; then tp=$base
    elif [[ -n ${projs[i]} ]]; then tp=${projs[i]}
    else tp=$base
    fi
    targets+=("$tp")
    # -S/--scope overrides every item; otherwise keep the recorded scope
    if (( scoped )) || [[ -n $scope_opt ]]; then
      ts=$(_secret_resolve_scope "$scope_opt" $scoped "$tp") || return 2
    else
      ts=${scopes[i]}
      [[ $ts == "$tp" ]] && ts=""
      if [[ -n $ts ]] && ! _secret_check_scope "$ts" 2>/dev/null; then
        _secret_err "${names[i]}: invalid recorded scope '$ts'"; bad=1
      fi
    fi
    if (( stage_forced )); then
      tg=$stage_all
    else
      tg=${stages[i]}
      if [[ -n $tg ]] && ! _secret_check_stage "$tg" 2>/dev/null; then
        _secret_err "${names[i]}: invalid recorded stage '$tg'"; bad=1
      fi
      tg=$(_secret_canon_stage "$tg")
    fi
    tbad+=($bad)
    tlayers+=("$(_secret_layer "$ts" "$tg")")
  done
  if (( stage_forced )) && [[ -n $stage_all ]]; then
    for tp in ${(u)targets}; do _secret_stage_note "$tp" "$stage_all"; done
  fi

  local lbl
  print -r -- "importing ${#names} item(s):"
  for (( i = 1; i <= ${#names}; i++ )); do
    lbl=$(_secret_kc_label "${targets[i]}")
    print -r -- "  $(_secret_disp "${targets[i]}" "${tlayers[i]}" "${names[i]}")${lbl:+ [kc:$lbl]}"
  done
  if (( ! yes )) && [[ -t 0 && -t 1 ]]; then
    local reply
    if ! read -q "reply?proceed? [y/N] "; then print '' >&2; return 1; fi
    print '' >&2
  fi

  local ok=0 fail=0 env meta
  local -a edits cf
  for (( i = 1; i <= ${#names}; i++ )); do
    if (( tbad[i] )) || ! _secret_check_name "${names[i]}" || ! _secret_check_project "${targets[i]}"; then
      (( fail++ )); continue
    fi
    # the file's meta replaces the item's (validated field by field); an
    # item that keeps its meta but has its ENV in the legacy marker gets the
    # setting pinned into the type so nothing is lost either way
    env=${envs[i]:-keep} meta=${metas[i]}
    if [[ $meta == invalid-key ]]; then
      _secret_err "${names[i]}: a meta key is not an identifier (letters, digits, '_', '-')"
      (( fail++ )); continue
    fi
    if [[ $meta != keep ]]; then
      edits=(${(f)meta})
      meta=$(_secret_meta_merge "" "${edits[@]}") || { (( fail++ )); continue }
      if [[ $env == keep ]]; then
        cf=("${(@ps:\t:)"$(_secret_row_of "${names[i]}" "${targets[i]}" "${tlayers[i]}")"}")
        if [[ -z ${cf[9]} ]]; then
          _secret_env_on "${cf[9]}" "${cf[8]}" && env=yes || env=no
        fi
      fi
    fi
    if print -r -- "${values[i]}" \
        | _secret_store "${names[i]}" "${targets[i]}" "${comments[i]}" "${kinds[i]}" "${tlayers[i]}" "$env" "$meta"; then
      (( ok++ ))
    else
      (( fail++ ))
    fi
  done
  print -r -- "imported $ok item(s)$( (( fail )) && print -rn -- ", $fail failed" )"
  (( fail == 0 ))
}

# Move the legacy env=no marker out of the generic attribute into the type
# code, so the attribute holds nothing but --meta fields. Only items that
# still carry the marker are rewritten (value re-stored unchanged, type set
# to envn, marker dropped); everything else is left untouched.
_secret_cmd_migrate() {
  local proj="" all=0 dry=0
  while (( $# )); do
    case $1 in
      -p) proj=$2; shift 2 ;;
      --all) all=1; shift ;;
      -n|--dry-run) dry=1; shift ;;
      -*) _secret_err "migrate: unknown option '$1'"; return 2 ;;
      *) _secret_err "migrate: unexpected argument '$1'"; return 2 ;;
    esac
  done
  if (( all )); then
    proj=""
  else
    proj=$(_secret_resolve_project "$proj")
  fi
  local row v meta env layer target ok=0 fail=0 seen=0
  local -a f
  while IFS= read -r row; do
    [[ -n $row ]] || continue
    f=("${(@ps:\t:)row}")
    [[ ";${f[8]};" == *";env=no;"* ]] || continue
    (( seen++ ))
    layer=$(_secret_row_layer "$row")
    target=$(_secret_disp "${f[1]}" "$layer" "${f[2]}")
    # a type already set (update --env after the marker was written) stays
    # authoritative: only the stale marker goes
    _secret_env_on "${f[9]}" "${f[8]}" && env=yes || env=no
    if (( dry )); then
      print -r -- "would migrate $target (env=no marker -> type $(_secret_env_code "$env"))"
      continue
    fi
    meta=$(_secret_meta_merge "${f[8]}") || { (( fail++ )); continue }
    if ! v=$(_secret_get_value "${f[2]}" "${f[1]}" "$layer"); then
      _secret_err "skipped $target (unreadable)"; (( fail++ )); continue
    fi
    if print -r -- "$v" | _secret_store "${f[2]}" "${f[1]}" "${f[5]}" "${f[4]}" "$layer" "$env" "$meta"; then
      print -r -- "migrated $target"
      (( ok++ ))
    else
      (( fail++ ))
    fi
  done <<< "$(_secret_rows "$proj")"
  if (( seen == 0 )); then
    print -r -- "nothing to migrate (project: ${proj:-all})"
    return 0
  fi
  (( dry )) && return 0
  print -r -- "migrated $ok item(s)$( (( fail )) && print -rn -- ", $fail failed" )"
  (( fail == 0 ))
}

# ---------------------------------------------------- keychain management --

_secret_kc_searchlist() {      # user-domain search list, one path per line
  security list-keychains -d user 2>/dev/null \
    | sed -E 's/^[[:space:]]*"(.*)"[[:space:]]*$/\1/'
}

# $_kc_sl on first use: only the write gate and the custom-keychain listing
# need the search list, so a read of one project never pays for it (~40 ms)
_secret_kc_sl_load() {
  (( ${_kc_sl_loaded:-0} )) && return 0
  _kc_sl=(${(@f)$(_secret_kc_searchlist)})
  _kc_sl_loaded=1
}

_secret_kc_customs() {         # registered custom keychain paths, one per line
  local f short
  _secret_kc_sl_load
  for f in "${_kc_sl[@]}"; do
    [[ $f == $HOME/Library/Keychains/*.keychain-db ]] || continue
    [[ $f == "$_kc_default" ]] && continue
    short=${${f:t}%.keychain-db}
    [[ $short == login ]] && continue
    if [[ -n $SECRET_TEST_ONLY_KC ]]; then
      [[ $short == ${~SECRET_TEST_ONLY_KC} ]] || continue
    fi
    print -r -- "$f"
  done
}

# Validate a keychain password. The keychain must be locked for macOS to
# actually check it, so this locks first; a WRONG password leaves the
# keychain locked (callers report that). Exit 0 = password is correct.
_secret_kc_try_pw() {          # $1 keychain  $2 password
  unset "_kc_unlocked[$1]"     # the lock below invalidates _secret_kc_ensure's memo
  security lock-keychain "$1" 2>/dev/null
  print -r -- "unlock-keychain -p $(_secret_quote_si "$2") $(_secret_quote_si "$1")" \
    | security -i >/dev/null 2>&1
}

_secret_master_get() {         # master password on stdout (fails if not stored)
  security find-generic-password -s 'keychain-password' \
    -a "$(_secret_master_account)" -w "$_kc_default" 2>/dev/null
}

_secret_master_store() {       # $1 password; store/update the master item in login
  local macct
  macct=$(_secret_master_account)
  local cmd="add-generic-password -U"
  cmd+=" -a $(_secret_quote_si "$macct")"
  cmd+=" -s \"keychain-password\""
  cmd+=" -l $(_secret_quote_si "keychain-password/$macct")"
  cmd+=" -D \"keychain password\""
  cmd+=" -j \"master password for secret.zsh custom keychains\""
  cmd+=" -w $(_secret_quote_si "$1")"
  cmd+=" $(_secret_quote_si "$_kc_default")"
  print -r -- "$cmd" | security -i >/dev/null 2>&1
  security find-generic-password -s 'keychain-password' -a "$macct" \
    "$_kc_default" >/dev/null 2>&1
}

_secret_kc_create() {
  local name="" timeout_min=30 autolock=1
  while (( $# )); do
    case $1 in
      --timeout) timeout_min=$2; shift 2 ;;
      --no-autolock) autolock=0; shift ;;
      -*) _secret_err "keychain create: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  [[ -z $name ]] && { _secret_err "keychain create: NAME required"; return 2 }
  [[ $name == default || $name == login || $name == "$(_secret_master_account)" ]] \
    && { _secret_err "'$name' is reserved"; return 2 }
  _secret_check_project "$name" || return 2
  [[ $timeout_min == <-> && $timeout_min -gt 0 ]] || {
    _secret_err "keychain create: --timeout expects minutes (integer)"; return 2
  }
  local kcpath=$HOME/Library/Keychains/$name.keychain-db
  [[ -e $kcpath ]] && { _secret_err "keychain already exists: $kcpath"; return 1 }
  local mpw used_master=0
  mpw=$(_secret_master_get)
  if [[ -n $mpw ]]; then
    # master password set: create with it, no prompt (argv-free via security -i)
    print -r -- "create-keychain -p $(_secret_quote_si "$mpw") $(_secret_quote_si "$kcpath")" \
      | security -i >/dev/null 2>&1
    [[ -e $kcpath ]] || { _secret_err "create failed"; return 1 }
    used_master=1
  else
    if [[ ! -t 0 ]]; then
      _secret_err "keychain create is interactive (password prompt needs a terminal)"
      return 1
    fi
    # password is prompted (hidden, confirmed) by security itself — never in argv
    security create-keychain "$kcpath" || { _secret_err "create failed"; return 1 }
  fi
  if (( autolock )); then
    security set-keychain-settings -l -u -t $(( timeout_min * 60 )) "$kcpath" \
      || _secret_err "warning: could not apply auto-lock settings"
  fi
  # append to the search list so Keychain Access and `security` can see it
  local -a sl
  sl=(${(@f)$(_secret_kc_searchlist)})
  if (( ! ${sl[(Ie)$kcpath]} )); then
    security list-keychains -d user -s "${sl[@]}" "$kcpath" \
      || _secret_err "warning: could not add to the keychain search list"
    _kc_sl_loaded=0            # $_kc_sl is reread on its next use
  fi
  print -r -- "created keychain '$name' ($kcpath)"
  (( used_master )) && print -r -- "password: master (unlocks with the master password)"
  if (( autolock )); then
    print -r -- "auto-lock: on sleep and after ${timeout_min} min idle"
  else
    print -r -- "auto-lock: disabled"
  fi
  print -r -- "secrets with project '$name' are stored there (one project = one keychain)"
}

_secret_kc_ls() {
  local -a sl
  sl=(${(@f)$(_secret_kc_searchlist)})
  local f base flags
  for f in $HOME/Library/Keychains/*.keychain-db(N); do
    base=${${f:t}%.keychain-db}
    flags=""
    [[ $f == "$_kc_default" ]] && flags+=" (default)"
    (( ${sl[(Ie)$f]} )) && flags+=" (search list)"
    print -r -- "$base$flags"
  done
}

_secret_kc_info() {
  local name=$1
  [[ -z $name ]] && { _secret_err "keychain info: NAME required"; return 2 }
  local kcpath
  kcpath=$(_secret_resolve_keychain "$name")
  [[ -e $kcpath ]] || { _secret_err "no such keychain: $name"; return 1 }
  print -r -- "path:        $kcpath"
  [[ $kcpath == "$_kc_default" ]] && print -r -- "default:     yes"
  local -a sl
  sl=(${(@f)$(_secret_kc_searchlist)})
  (( ${sl[(Ie)$kcpath]} )) && print -r -- "search list: yes" || print -r -- "search list: no"
  local settings
  if settings=$(security show-keychain-info "$kcpath" 2>&1); then
    print -r -- "settings:    ${settings#Keychain *\" }"
  else
    print -r -- "settings:    (unavailable — keychain may be locked)"
  fi
}

_secret_kc_lock() {
  if [[ $1 == --all || $1 == -a ]]; then
    _kc_unlocked=()
    security lock-keychain -a && print -r -- "locked all keychains"
    return
  fi
  [[ -z $1 ]] && { _secret_err "keychain lock: NAME or --all required"; return 2 }
  local kcpath
  kcpath=$(_secret_resolve_keychain "$1")
  [[ -e $kcpath ]] || { _secret_err "no such keychain: $1"; return 1 }
  unset "_kc_unlocked[$kcpath]"
  security lock-keychain "$kcpath" && print -r -- "locked $1"
}

_secret_kc_unlock() {
  [[ -z $1 ]] && { _secret_err "keychain unlock: NAME required"; return 2 }
  local kcpath
  kcpath=$(_secret_resolve_keychain "$1")
  [[ -e $kcpath ]] || { _secret_err "no such keychain: $1"; return 1 }
  # password prompted by security itself (hidden) — never in argv
  security unlock-keychain "$kcpath" && print -r -- "unlocked $1"
}

_secret_kc_remember() {        # NAME [--stdin]: store keychain password in login
  local name="" from_stdin=0
  while (( $# )); do
    case $1 in
      --stdin) from_stdin=1; shift ;;
      -*) _secret_err "keychain remember: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  [[ -z $name ]] && { _secret_err "keychain remember: NAME required"; return 2 }
  [[ $name == "$(_secret_master_account)" ]] && {
    _secret_err "'$name' is the master account (use: secret keychain master set)"; return 2
  }
  local kcpath
  kcpath=$(_secret_resolve_keychain "$name")
  [[ -e $kcpath ]] || { _secret_err "no such keychain: $name"; return 1 }
  [[ $kcpath == "$_kc_default" ]] && {
    _secret_err "refusing: that is the default keychain itself"; return 1
  }
  local short=${${kcpath:t}%.keychain-db}
  local pw
  if (( from_stdin )) || [[ ! -t 0 ]]; then
    IFS= read -r pw
  else
    IFS= read -rs "pw?password of keychain '$short' (hidden): " || { print '' >&2; return 1 }
    print '' >&2
  fi
  # verify the password: lock, then unlock with it (argv-free via security -i)
  unset "_kc_unlocked[$kcpath]"
  security lock-keychain "$kcpath" 2>/dev/null
  if ! print -r -- "unlock-keychain -p $(_secret_quote_si "$pw") $(_secret_quote_si "$kcpath")" \
      | security -i >/dev/null 2>&1; then
    _secret_err "wrong password for '$short' (keychain left locked)"
    return 1
  fi
  # store in the login keychain (service "keychain-password", account NAME)
  local cmd="add-generic-password -U"
  cmd+=" -a $(_secret_quote_si "$short")"
  cmd+=" -s \"keychain-password\""
  cmd+=" -l $(_secret_quote_si "keychain-password/$short")"
  cmd+=" -D \"keychain password\""
  cmd+=" -j \"unlock password used by secret.zsh auto-unlock\""
  cmd+=" -w $(_secret_quote_si "$pw")"
  cmd+=" $(_secret_quote_si "$_kc_default")"
  print -r -- "$cmd" | security -i >/dev/null 2>&1
  if ! security find-generic-password -s 'keychain-password' -a "$short" \
      "$_kc_default" >/dev/null 2>&1; then
    _secret_err "failed to store the password in the login keychain"
    return 1
  fi
  print -r -- "stored password for '$short' in the login keychain"
  print -r -- "secret will now unlock it automatically when needed"
}

_secret_kc_forget() {          # NAME: remove the stored keychain password
  [[ -z $1 ]] && { _secret_err "keychain forget: NAME required"; return 2 }
  local short=$1
  short=${${short:t}%.keychain-db}
  if security delete-generic-password -s 'keychain-password' -a "$short" \
      "$_kc_default" >/dev/null 2>&1; then
    print -r -- "forgot stored password for '$short'"
  else
    _secret_err "no stored password for '$short'"
    return 1
  fi
}

_secret_kc_rm() {
  local name="" force=0
  while (( $# )); do
    case $1 in
      -f|--force) force=1; shift ;;
      -*) _secret_err "keychain rm: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  [[ -z $name ]] && { _secret_err "keychain rm: NAME required"; return 2 }
  local kcpath
  kcpath=$(_secret_resolve_keychain "$name")
  [[ -e $kcpath ]] || { _secret_err "no such keychain: $name"; return 1 }
  [[ $kcpath == "$_kc_default" ]] && { _secret_err "refusing to delete the default keychain"; return 1 }
  if (( ! force )); then
    if [[ ! -t 0 ]]; then
      _secret_err "keychain rm needs a terminal to confirm (or pass -f)"
      return 1
    fi
    local reply
    if ! read -q "reply?delete keychain '$name' and ALL items in it? [y/N] "; then
      print '' >&2; return 1
    fi
    print '' >&2
  fi
  security delete-keychain "$kcpath" || { _secret_err "delete failed"; return 1 }
  _kc_sl_loaded=0; unset "_kc_unlocked[$kcpath]"
  # drop any stored unlock password for it
  security delete-generic-password -s 'keychain-password' \
    -a "${${kcpath:t}%.keychain-db}" "$_kc_default" >/dev/null 2>&1
  print -r -- "deleted keychain $name"
}

_secret_kc_register() {        # add an existing .keychain-db to the search list
  [[ -z $1 ]] && { _secret_err "keychain register: NAME required"; return 2 }
  local kcpath
  kcpath=$(_secret_resolve_keychain "$1")
  [[ -e $kcpath ]] || { _secret_err "no such keychain file: $1"; return 1 }
  local -a sl
  sl=(${(@f)$(_secret_kc_searchlist)})
  if (( ${sl[(Ie)$kcpath]} )); then
    print -r -- "already registered: ${${kcpath:t}%.keychain-db}"
    return 0
  fi
  security list-keychains -d user -s "${sl[@]}" "$kcpath" \
    || { _secret_err "could not update the search list"; return 1 }
  _kc_sl_loaded=0
  print -r -- "registered ${${kcpath:t}%.keychain-db} in the search list"
}

_secret_master_set() {
  local from_stdin=0
  while (( $# )); do
    case $1 in
      --stdin) from_stdin=1; shift ;;
      *) _secret_err "keychain master set: unknown option '$1'"; return 2 ;;
    esac
  done
  local pw
  if (( from_stdin )) || [[ ! -t 0 ]]; then
    IFS= read -r pw
  else
    pw=$(_secret_prompt_value "the master (all custom keychains)") || return 1
  fi
  [[ -n $pw ]] || { _secret_err "empty master password, aborted"; return 1 }

  local kc short cur
  local -a adopted skipped failed
  for kc in ${(f)"$(_secret_kc_customs)"}; do
    [[ -n $kc ]] || continue
    short=${${kc:t}%.keychain-db}
    # already on the master password?
    if _secret_kc_try_pw "$kc" "$pw"; then
      adopted+=("$short")
      security delete-generic-password -s 'keychain-password' -a "$short" \
        "$_kc_default" >/dev/null 2>&1
      continue
    fi
    # find its current password: stored item, else ask
    cur=$(security find-generic-password -s 'keychain-password' -a "$short" \
          -w "$_kc_default" 2>/dev/null)
    if [[ -z $cur ]] && (( ! from_stdin )) && [[ -t 0 ]]; then
      IFS= read -rs "cur?current password of '$short' (hidden, Enter to skip): "
      print '' >&2
    fi
    if [[ -z $cur ]]; then
      _secret_kc_ensure "$kc"   # restore unlock if an item exists
      skipped+=("$short")
      continue
    fi
    if ! _secret_kc_try_pw "$kc" "$cur"; then
      _secret_err "wrong current password for '$short' (left locked)"
      failed+=("$short")
      continue
    fi
    if print -r -- "set-keychain-password -o $(_secret_quote_si "$cur") -p $(_secret_quote_si "$pw") $(_secret_quote_si "$kc")" \
        | security -i >/dev/null 2>&1 && _secret_kc_try_pw "$kc" "$pw"; then
      adopted+=("$short")
      security delete-generic-password -s 'keychain-password' -a "$short" \
        "$_kc_default" >/dev/null 2>&1
    else
      failed+=("$short")
    fi
  done

  _secret_master_store "$pw" \
    || { _secret_err "failed to store the master password in login"; return 1 }
  print -r -- "master password stored in the login keychain"
  (( ${#adopted} )) && print -r -- "adopted: ${(j:, :)adopted}"
  (( ${#skipped} )) && print -r -- "skipped (current password unknown): ${(j:, :)skipped}"
  (( ${#failed} ))  && print -r -- "FAILED: ${(j:, :)failed}"
  print -r -- "keep this password in your password manager — it is the recovery key"
  (( ${#failed} == 0 ))
}

_secret_master_rotate() {
  local from_stdin=0
  [[ $1 == --stdin ]] && { from_stdin=1; shift }
  local old new
  old=$(_secret_master_get) || {
    _secret_err "no master password stored (run: secret keychain master set)"; return 1
  }
  if (( from_stdin )) || [[ ! -t 0 ]]; then
    IFS= read -r new
  else
    new=$(_secret_prompt_value "the NEW master") || return 1
  fi
  [[ -n $new ]] || { _secret_err "empty master password, aborted"; return 1 }

  local kc short
  local -a rotated notmaster failed
  for kc in ${(f)"$(_secret_kc_customs)"}; do
    [[ -n $kc ]] || continue
    short=${${kc:t}%.keychain-db}
    if ! _secret_kc_try_pw "$kc" "$old"; then
      _secret_kc_ensure "$kc"   # not on master; restore unlock if possible
      notmaster+=("$short")
      continue
    fi
    if print -r -- "set-keychain-password -o $(_secret_quote_si "$old") -p $(_secret_quote_si "$new") $(_secret_quote_si "$kc")" \
        | security -i >/dev/null 2>&1 && _secret_kc_try_pw "$kc" "$new"; then
      rotated+=("$short")
    else
      failed+=("$short")
    fi
  done
  _secret_master_store "$new" \
    || { _secret_err "failed to update the master item in login"; return 1 }
  print -r -- "master password rotated"
  (( ${#rotated} ))   && print -r -- "rotated: ${(j:, :)rotated}"
  (( ${#notmaster} )) && print -r -- "not on master (untouched): ${(j:, :)notmaster}"
  (( ${#failed} ))    && print -r -- "FAILED: ${(j:, :)failed}"
  print -r -- "update your password manager with the new value"
  (( ${#failed} == 0 ))
}

_secret_master_status() {
  local macct
  macct=$(_secret_master_account)
  if security find-generic-password -s 'keychain-password' -a "$macct" \
      "$_kc_default" >/dev/null 2>&1; then
    print -r -- "master: stored in login"
  else
    print -r -- "master: not set"
  fi
  local kc short src state
  printf '%-26s %-12s %s\n' 'KEYCHAIN' 'UNLOCK VIA' 'STATE'
  for kc in ${(f)"$(_secret_kc_customs)"}; do
    [[ -n $kc ]] || continue
    short=${${kc:t}%.keychain-db}
    if security find-generic-password -s 'keychain-password' -a "$short" \
        "$_kc_default" >/dev/null 2>&1; then
      src=individual
    elif security find-generic-password -s 'keychain-password' -a "$macct" \
        "$_kc_default" >/dev/null 2>&1; then
      src=master
    else
      src='none (prompts)'
    fi
    security show-keychain-info "$kc" >/dev/null 2>&1 && state=unlocked || state=locked
    printf '%-26s %-12s %s\n' "$short" "$src" "$state"
  done
}

_secret_master_reveal() {
  local copy=0
  [[ $1 == -c || $1 == --copy ]] && copy=1
  local pw
  pw=$(_secret_master_get) || { _secret_err "no master password stored"; return 1 }
  if (( copy )); then
    _secret_clip "$pw"
    print -r -- "master password copied to clipboard (clears in 45s)"
  else
    print -r -- "$pw"
  fi
}

_secret_master_forget() {
  if security delete-generic-password -s 'keychain-password' \
      -a "$(_secret_master_account)" "$_kc_default" >/dev/null 2>&1; then
    print -r -- "master password removed from login (keychain passwords unchanged;"
    print -r -- "keep the master in your password manager — access will prompt now)"
  else
    _secret_err "no master password stored"
    return 1
  fi
}

_secret_cmd_master() {
  local sub=${1:-status}
  (( $# )) && shift
  case $sub in
    set)    _secret_master_set "$@" ;;
    rotate) _secret_master_rotate "$@" ;;
    status) _secret_master_status ;;
    reveal) _secret_master_reveal "$@" ;;
    forget) _secret_master_forget ;;
    *) _secret_err "keychain master: unknown subcommand '$sub' (set|rotate|status|reveal|forget)"; return 2 ;;
  esac
}

_secret_cmd_keychain() {
  local sub=${1:-ls}
  (( $# )) && shift
  case $sub in
    create)    _secret_kc_create "$@" ;;
    ls|list)   _secret_kc_ls ;;
    info)      _secret_kc_info "$@" ;;
    lock)      _secret_kc_lock "$@" ;;
    unlock)    _secret_kc_unlock "$@" ;;
    remember)  _secret_kc_remember "$@" ;;
    forget)    _secret_kc_forget "$@" ;;
    register)  _secret_kc_register "$@" ;;
    master)    _secret_cmd_master "$@" ;;
    rm|delete) _secret_kc_rm "$@" ;;
    *) _secret_err "keychain: unknown subcommand '$sub' (create|ls|info|lock|unlock|remember|forget|register|master|rm)"; return 2 ;;
  esac
}

_secret_cmd_link() {
  local unset_flag=0 name=""
  while (( $# )); do
    case $1 in
      --unset) unset_flag=1; shift ;;
      -*) _secret_err "link: unknown option '$1'"; return 2 ;;
      *) name=$1; shift ;;
    esac
  done
  local top
  top=$(command git rev-parse --show-toplevel 2>/dev/null)

  if (( unset_flag )); then
    [[ -n $top ]] || { _secret_err "link --unset: not inside a git repository"; return 1 }
    if command git config --unset secret.project 2>/dev/null; then
      print -r -- "unlinked: project now resolves to '${top:t}' (repository name)"
    else
      _secret_err "no secret.project mapping was set"
      return 1
    fi
    return 0
  fi

  if [[ -n $name ]]; then
    [[ -n $top ]] || { _secret_err "link: not inside a git repository"; return 1 }
    _secret_check_project "$name" || return 2
    command git config secret.project "$name" \
      || { _secret_err "could not write git config"; return 1 }
    print -r -- "linked: $top -> project '$name'"
    local amb
    amb=$(_secret_ambient_scope "$name")
    [[ -n $amb ]] && print -r -- "scope for -S in this repository: $amb"
    return 0
  fi

  # no arguments: show how this directory resolves
  local proj via conf
  proj=$(_secret_resolve_project "")
  if [[ -n $top ]]; then
    conf=$(command git config --get secret.project 2>/dev/null)
    if [[ -n $conf ]]; then via="git config secret.project"
    else via="repository name"
    fi
    print -r -- "repository: $top"
  else
    via="default (not in a git repository)"
  fi
  print -r -- "project:    $proj  (via $via)"
  local amb
  amb=$(_secret_ambient_scope "$proj")
  print -r -- "scope (-S): ${amb:-(none — repository name equals the project)}"
  print -r -- "stage:      ${SECRET_STAGE:-(none — set SECRET_STAGE or pass --stage)}"
  local kc
  kc=$(_secret_kc_for "$proj")
  if [[ -e $kc ]]; then
    print -r -- "keychain:   $kc"
  else
    print -r -- "keychain:   $kc (will be created on first write)"
  fi
}

_secret_cmd_help() {
  cat <<'EOF'
secret — manage secrets in the macOS Keychain

USAGE
  secret                                    interactive wizard (fzf)
  secret [-k KEYCHAIN] <command> [args]

COMMANDS
  set NAME [-p proj] [-S|--scope X] [--stage S|--no-stage] [-j comment] [-D kind] [--meta K=V]... [--no-env|--env] [--new] [--stdin]
        store a secret; prompts for the value (no echo), or reads one
        line from stdin with --stdin / when piped. Default layer: shared,
        in the stage $SECRET_STAGE names (none otherwise); -S stores into
        this repository's scope, --stage S / --no-stage pin the stage (see
        STAGES). --meta adds structured fields (see META). --no-env keeps
        it out of `secret env` (see ENV); without --env/--no-env an
        existing item keeps its setting. --new stores only a new item: an
        existing one in that layer is refused, never overwritten
  update NAME [-p proj] [LAYER] [-j comment] [-D kind] [--meta K=V]... [--no-env|--env] [--value|--stdin]
        partially update an existing secret: --value prompts for a new
        value (--stdin reads it from stdin), -j/-D replace comment/kind
        (-j '' clears the comment), --meta K=V sets one field and
        --meta K= removes it, --no-env/--env change the ENV setting;
        everything else is kept as-is
  get NAME [-p proj] [LAYER] [-c|--copy]
        print the value (or copy to clipboard, auto-clears in 45s)
  show NAME [-p proj] [LAYER]  metadata only (never prints the value)
  ls [-p proj|--all] [-l|--long|--json] [--wide] [--meta KEY[=VALUE]]... [--stage S|--no-stage]
        list every layer of the project; short form prints one
        "[scope/]NAME[@stage]" token per item (--all: prefixed with the
        project). --long groups items under their layer (shared, scope/,
        @stage, scope/ @stage) with kind, env, modified, meta and comment,
        cut with an ellipsis to fit the terminal width — --wide never
        cuts. --json prints the items as a JSON array (the fields of
        `export --format json`, never a value): the format for programs,
        while --long is for people and may change. --meta keeps only
        items whose field KEY exists (or equals VALUE), repeatable (all
        must match); --stage S keeps that stage's
        layers only, --no-stage the stage-less ones; --all spans every
        registered keychain
  projects                     list all projects
  env [-p proj] [--scope X] [--stage S|--no-stage]
        emit `export NAME=...` lines: the shared layer overlaid with the
        repository scope, then with the stage's shared and scoped layers
        (most specific wins; other stages are never emitted), skipping
        items set --no-env, e.g.:
          eval "$(secret env)"
          SECRET_STAGE=test npm test        # through the shim
  rm NAME [-p proj] [LAYER] [-f]   delete a secret
  link [NAME|--unset]
        map this repository to project NAME (git config secret.project);
        without arguments, show how this directory resolves
  export [-p proj|--all] [-o FILE] [--format age|json|env]
        write secrets to a file; age (encrypted JSON, default), json,
        or env (plaintext export lines; kind and comment are lost, ENV
        and META survive as markers: `#no-env# export ...` and a
        `#meta:K=V;...` comment line right above the item)
  import FILE [-p proj] [-S|--scope X] [--stage S|--no-stage] [-y]
        load secrets from .json.age / .json / .env files; -p forces all
        items into one project, -S/--scope forces one scope, --stage /
        --no-stage one stage; otherwise JSON items keep their own
        project, scope and stage, and env files land in $SECRET_STAGE
  migrate [-p proj|--all] [-n|--dry-run]
        move the pre-type env=no marker out of the generic attribute into
        the type code (see ENV); items already migrated are untouched

  LAYER (get/show/rm/update): default is DWIM — the stage's layer of this
  repository's scope, the stage's shared layer, this repository's scope,
  then the shared layer. -S/--scoped = the repo scope only, --scope X =
  that scope only, --shared = the shared layer only; --stage S / --no-stage
  pin the stage ($SECRET_STAGE otherwise), and with one the exact flags
  address that stage's layer. NAME may also be the token `ls` prints,
  "[scope/]NAME[@stage]": it names that exact layer (`secret get
  api/DATABASE_URL@prod`).

  The wizard's List is a browser: every item with a preview of its
  metadata, matched on name, meta and comment; ^y copies the value, ^f
  copies one meta field or the comment, ^o opens the url= field in the
  browser, ^e updates, ^d deletes — each returns to the list; enter
  prints the item's details and leaves, esc leaves.
  keychain create NAME [--timeout MIN] [--no-autolock]
        create ~/Library/Keychains/NAME.keychain-db (auto-locks on sleep
        and after 30 min by default) and add it to the search list
  keychain master set|rotate [--stdin]|status|reveal [-c]|forget
        ONE password for every custom keychain: `set` rotates all
        registered custom keychains to the master password and stores it
        in login for auto-unlock; keep that password in your password
        manager — it is the recovery key for every .keychain-db file.
        With a master set, `keychain create` needs no password prompt.
  keychain remember NAME [--stdin]
        store NAME's own unlock password in the login keychain (per-
        keychain override; takes precedence over the master)
  keychain register NAME
        add an existing .keychain-db (e.g. copied from another Mac) to
        the search list so auto-mapping sees it
  keychain ls|info NAME|lock NAME|--all|unlock NAME|forget NAME|rm NAME [-f]
        manage custom keychains
  help                     this help

PROJECTS
  -p flag > `git config secret.project` > basename of the enclosing git
  repo > "global". Run `secret link NAME` in each clone of a multi-repo
  product so they all share one project.
  Stored as keychain attributes: service "secret.<project>" (shared) or
  "secret.<project>/<scope>" (scoped), account NAME, plus label, kind
  (-D), comment (-j), type (ENV) and generic (META) — all visible in
  Keychain Access.

SCOPES
  Inside one project, scoped items override shared ones per repository:
  store org-wide values in the shared layer and repo-specific values
  (DATABASE_URL, PORT, ...) with -S. The scope name defaults to the
  repository basename, so two linked repos never collide. `secret env`
  emits shared + this repo's scope, scoped values winning.

STAGES
  A stage is a per-environment layer on top of scopes: prod, test,
  staging, ... Store the same NAME once per stage (`secret set
  DATABASE_URL --stage prod`), and `secret env --stage prod` / the shims
  under SECRET_STAGE=prod emit that value; names a stage does not hold
  fall back to the stage-less layers, so environment-neutral values are
  stored once. A stage layer always beats a stage-less one (shared <
  scoped < shared@stage < scoped@stage) and other stages are never
  emitted. Without --stage and SECRET_STAGE nothing staged is emitted:
  prod only ever leaves the keychain when asked for by name. Tool-mode
  shims (opencode, claude, ...) never receive a stage. Stage names are
  letters, digits, '_' and '-'; production and development are spellings
  of prod and dev (one layer each, @prod / @dev), other stages are stored
  as typed. A set or import into a stage the project has no item in yet
  is noted on stderr with the stages in use, so a typo (prd) is noticed.
  Project and scope names may not contain '@' (the service is
  "secret.<project>[/<scope>]@<stage>").

ENV
  Every item is emitted by `secret env` — and so injected by every shell,
  shim or helper built on it — unless it is set --no-env: then only
  `get` (and export/import, which carry the setting) ever reads it. Use it
  for what no process environment should hold, such as a wallet's seed
  phrase. Stored in the item's type attribute as the four-character code
  envn (envy or no type = emitted); rewriting the value keeps it,
  `update --env` lifts it. `ls --long` and `show` display it. Items
  written before the type code kept env=no in the generic attribute;
  that is still honoured, and `secret migrate` moves it over.

META
  --meta KEY=VALUE attaches structured fields to an item, as many as you
  like: where a key was issued (url=https://dashboard.stripe.com), which
  account it belongs to (account=ops@example.com), what a mnemonic is for
  (purpose=cold-storage). Keys are identifiers (letters, digits, '_',
  '-'), values are single-line and may not contain ';'. Fields live in
  the item's generic attribute as KEY=VALUE;KEY=VALUE, sorted by key.
  `update --meta KEY=` removes a field; `show` lists them, `ls --long`
  has a META column, `ls --meta KEY[=VALUE]` filters by them, and
  export/import carry them. Free-form notes belong in the comment (-j).

KINDS
  -D sets the item's kind, a short type label shown in Keychain Access.
  It is normalised on write (upper-cased, whitespace collapsed; default
  ENV). The wizard offers ENV, API KEY, TOKEN, PASSWORD, SECRET, URL,
  WEBHOOK SECRET, MNEMONIC PHRASE, PRIVATE KEY, or Other to type your own.

KEYCHAINS
  One project = one keychain: project P lives in
  ~/Library/Keychains/P.keychain-db. Missing keychains are created on
  first write — silently when a master password is set, interactively on
  a terminal otherwise. Files that exist but were never registered in
  the user search list (app/system keychains) are refused; opt in with
  `secret keychain register NAME` if one really is yours.
  `-k NAME|PATH` overrides everything; `-k default` targets the login
  keychain, which only holds the keychain-password items.
  `projects` lists registered keychain names; `export --all` spans every
  registered keychain. Locked keychains are never dumped unasked.
EOF
}

# ----------------------------------------------------------------- fzf UI --

_secret_fzf() {
  fzf --height=40% --reverse --no-sort "$@"
}

_secret_ui_pick_project() {    # $1 header  $2.. extra entries; selection on stdout
  local header=$1; shift
  local cur
  cur=$(_secret_resolve_project "")
  local -a existing extras
  extras=("$@")
  existing=(${(@f)$(_secret_cmd_projects)})
  if (( ${existing[(Ie)$cur]} )); then
    existing=("$cur" ${existing:#$cur})
  fi
  local -a items
  items=(${extras:#} $existing)
  (( ${#items} )) || { _secret_err "no projects yet — use 'secret set' or the Add action first"; return 1 }
  print -rl -- "${items[@]}" | _secret_fzf --header="$header" --prompt='project> '
}

# The stage picker for a new item: the stages the project already holds
# items in, so an existing one is chosen rather than retyped (prd ≠ prod),
# `(none)` for the stage-less layer and `(new)` to type one. $SECRET_STAGE,
# when set, leads the list as the default. Prints the stage ("" for none);
# returns 1 when the user backs out.
_secret_ui_pick_stage() {      # $1 project  $2 header -> stage on stdout
  local proj=$1 header=$2 cur=${SECRET_STAGE:-} s mark
  [[ -n $cur ]] && cur=$(_secret_canon_stage "$cur")
  local -a have lines
  have=(${(f)"$(_secret_stages_of "$proj")"})
  if [[ -n $cur ]]; then
    mark="SECRET_STAGE"; (( ${have[(Ie)$cur]} )) && mark+=", in use"
    lines+=("$(printf '%-10s %s' "$cur" "$mark")")
  fi
  lines+=("$(printf '%-10s %s' '(none)' 'the stage-less layer')")
  for s in "${have[@]}"; do
    [[ $s == "$cur" ]] && continue
    lines+=("$(printf '%-10s %s' "$s" 'in use')")
  done
  lines+=("$(printf '%-10s %s' '(new)' 'type a stage name')")
  s=$(print -rl -- "${lines[@]}" | _secret_fzf --header="$header" --prompt='stage> ') || return 1
  [[ -z $s ]] && return 1
  s=${${s%%$'\n'*}%% *}
  case $s in
    '(none)') print -r -- ""; return 0 ;;
    '(new)')
      read -r "s?stage name: " || return 1
      s=${${s##[[:space:]]#}%%[[:space:]]#}
      [[ -n $s ]] || { print -r -- ""; return 0 }
      _secret_check_stage "$s" || return 1
      ;;
  esac
  _secret_canon_stage "$s"
}

# The item picker. Each fzf line is three tab-separated fields: the visible
# columns (token, kind, env, modified, comment), the token
# "[scope/]NAME[@stage]", and the item's meta fields — fzf shows the first
# and matches on all three, so typing a meta value finds the item. The
# preview pane runs `secret show` on the highlighted token, in a fresh zsh
# that sources this file, so nothing here ever has to fit the pane width.
#   $3 mode: "" (one token), "multi" (one per line), "expect" (the key
#   pressed on the first line, the token on the second); $4.. extra fzf
#   options (an --expect list for the expect mode).
_secret_ui_pick_items() {      # $1 project  $2 header  $3 mode  $4.. fzf options; tokens on stdout
  local proj=$1 header=$2 mode=$3
  shift 3
  local rows
  rows=$(_secret_rows "$proj")
  [[ -z $rows ]] && { _secret_err "no secrets in project '$proj'"; return 1 }
  local row tok env meta lines=""
  local -a f
  local -i wt=4
  while IFS= read -r row; do
    f=("${(@ps:\t:)row}")
    tok="${f[7]:+${f[7]}/}${f[2]}${f[10]:+@${f[10]}}"
    (( ${#tok} > wt )) && wt=${#tok}
  done <<< "$rows"
  while IFS= read -r row; do
    f=("${(@ps:\t:)row}")
    tok="${f[7]:+${f[7]}/}${f[2]}${f[10]:+@${f[10]}}"
    _secret_env_on "${f[9]}" "${f[8]}" && env=yes || env=no
    meta=${(j: :)${(f)"$(_secret_meta_fields "${f[8]}")"}}
    lines+="$(printf "%-${wt}s  %-14s %-3s %-16s %s" \
      "$tok" "${f[4]}" "$env" "$(_secret_fmt_date "${f[6]}")" "${f[5]}")"$'\t'"$tok"$'\t'"$meta"$'\n'
  done <<< "$rows"
  local preview
  preview="zsh -fc 'source \"\$1\"; secret show \"\$2\" -p \"\$3\"' -- ${(q)_SECRET_LIB} {2} ${(q)proj}"
  local -a fzopts
  fzopts=(--delimiter=$'\t' --with-nth=1 --preview="$preview" --preview-window='right,50%,wrap')
  [[ $mode == multi ]] && fzopts+=(--multi)
  local out
  out=$(print -rn -- "$lines" \
    | _secret_fzf "${fzopts[@]}" --header="$header" --prompt='secret> ' "$@") || return $?
  if [[ $mode == expect ]]; then
    print -r -- "${out%%$'\n'*}"
    [[ $out == *$'\n'* ]] || return 0
    out=${out#*$'\n'}
  fi
  print -r -- "$out" | awk -F'\t' 'NF { print $2 }'
}

# Picker tokens are "[scope/]NAME[@stage]". Split one token into the bare
# name ($_tok_name), exact layer flags ($_tok_flags array) and the layer
# string ($_tok_layer).
_secret_ui_split_token() {     # $1 token
  local tok=$1 scope="" stage=""
  if [[ $tok == *@* ]]; then
    stage=${tok#*@}
    tok=${tok%%@*}
  fi
  if [[ $tok == */* ]]; then
    scope=${tok%%/*}
    tok=${tok#*/}
  fi
  _tok_name=$tok
  _tok_layer=$(_secret_layer "$scope" "$stage")
  if [[ -n $scope ]]; then _tok_flags=(--scope "$scope"); else _tok_flags=(--shared); fi
  if [[ -n $stage ]]; then _tok_flags+=(--stage "$stage"); else _tok_flags+=(--no-stage); fi
}

_secret_ui_get() {
  local proj tok _tok_name _tok_layer
  local -a _tok_flags
  proj=$(_secret_ui_pick_project 'secret › get › choose project') || return 0
  [[ -z $proj ]] && return 0
  tok=$(_secret_ui_pick_items "$proj" "secret › $proj$(_secret_kc_suffix "$proj") › get (copies to clipboard)" "") || return 0
  [[ -z $tok ]] && return 0
  _secret_ui_split_token "$tok"
  _secret_cmd_get "$_tok_name" -p "$proj" "${_tok_flags[@]}" --copy
}

_secret_ui_add() {
  local proj name kind comment
  proj=$(_secret_ui_pick_project 'secret › add › choose project' '[+ new project]') || return 0
  [[ -z $proj ]] && return 0
  if [[ $proj == '[+ new project]' ]]; then
    read -r "proj?new project name: " || return 0
    proj=${${proj##[[:space:]]#}%%[[:space:]]#}
    _secret_check_project "$proj" || return 1
  fi
  while true; do
    read -r "name?variable name (e.g. STRIPE_KEY): " || return 0
    _secret_check_name "$name" && break
  done
  local amb layer=""
  amb=$(_secret_ambient_scope "$proj")
  if [[ -n $amb ]]; then
    layer=$(printf '%s\n' \
        'shared    visible to every repository of the project' \
        "scoped    only this repository ($amb), overrides shared" \
      | _secret_fzf --header="secret › $proj/$name › layer" --prompt='layer> ') || return 0
    [[ -z $layer ]] && return 0
    layer=${${(z)layer}[1]}
  fi
  kind=$(_secret_kind_choices \
    | _secret_fzf --header="secret › $proj/$name › kind" --prompt='kind> ') || return 0
  if [[ $kind == 'Other' ]]; then
    read -r "kind?kind: " || return 0
  fi
  read -r "comment?comment (optional): " || return 0
  local stage
  stage=$(_secret_ui_pick_stage "$proj" "secret › $proj/$name › stage") || return 0
  local -a args
  args=("$name" -p "$proj")
  [[ $layer == scoped ]] && args+=(-S)
  if [[ -n $stage ]]; then args+=(--stage "$stage"); else args+=(--no-stage); fi
  [[ -n $kind ]] && args+=(-D "$kind")
  [[ -n $comment ]] && args+=(-j "$comment")
  local field
  while true; do
    read -r "field?meta field KEY=VALUE (optional; empty line to finish): " || return 0
    [[ -z $field ]] && break
    args+=(--meta "$field")
  done
  _secret_cmd_set "${args[@]}"
}

_secret_ui_update() {
  local proj tok
  proj=$(_secret_ui_pick_project 'secret › update › choose project') || return 0
  [[ -z $proj ]] && return 0
  tok=$(_secret_ui_pick_items "$proj" "secret › $proj$(_secret_kc_suffix "$proj") › update" "") || return 0
  [[ -z $tok ]] && return 0
  _secret_ui_update_token "$proj" "$tok"
}

_secret_ui_update_token() {    # $1 project  $2 token: the update dialogue for one item
  local proj=$1 tok=$2 fields fld c k _tok_name _tok_layer
  local -a _tok_flags
  _secret_ui_split_token "$tok"
  local name=$_tok_name row
  row=$(_secret_row_of "$name" "$proj" "$_tok_layer")
  local -a f
  f=("${(@ps:\t:)row}")
  fields=$(printf '%s\n' \
      'value     change the secret value (hidden prompt)' \
      'comment   change the comment' \
      'kind      change the kind' \
      'meta      set or remove a KEY=VALUE field' \
    | _secret_fzf --multi \
        --header="secret › $proj/$tok › what to update (TAB to multi-select)" \
        --prompt='update> ') || return 0
  [[ -z $fields ]] && return 0
  local -a args
  args=("$name" -p "$proj" "${_tok_flags[@]}")
  for fld in ${(f)fields}; do
    case ${${(z)fld}[1]} in
      value)
        args+=(--value)
        ;;
      comment)
        print -r -- "current comment: ${f[5]:-(none)}"
        read -r "c?new comment (empty clears): " || return 0
        args+=(-j "$c")
        ;;
      meta)
        local cur_meta
        cur_meta=${(j: :)${(f)"$(_secret_meta_fields "${f[8]}")"}}
        print -r -- "current meta: ${cur_meta:-(none)}"
        while true; do
          read -r "c?field KEY=VALUE (KEY= removes; empty line to finish): " || return 0
          [[ -z $c ]] && break
          args+=(--meta "$c")
        done
        ;;
      kind)
        k=$(_secret_kind_choices \
          | _secret_fzf --header="secret › $proj/$tok › new kind (current: ${f[4]:-ENV})" \
              --prompt='kind> ') || return 0
        if [[ $k == 'Other' ]]; then
          read -r "k?kind: " || return 0
        fi
        [[ -z $k ]] && return 0
        args+=(-D "$k")
        ;;
    esac
  done
  _secret_cmd_update "${args[@]}"
}

# Metadata is not secret: a field's value goes to the clipboard as it is,
# without the 45 s clearing a value gets. One field copies at once, several
# go through a small picker; the comment is offered alongside the fields.
_secret_ui_copy_field() {      # $1 project  $2 token
  local proj=$1 tok=$2 _tok_name _tok_layer row pick
  local -a _tok_flags f choices
  _secret_ui_split_token "$tok"
  row=$(_secret_row_of "$_tok_name" "$proj" "$_tok_layer")
  [[ -z $row ]] && { _secret_err "not found: $tok"; return 1 }
  f=("${(@ps:\t:)row}")
  choices=(${(f)"$(_secret_meta_fields "${f[8]}")"})
  [[ -n ${f[5]} ]] && choices+=("comment=${f[5]}")
  if (( ${#choices} == 0 )); then
    print -r -- "$tok has no meta fields or comment"
    return 0
  elif (( ${#choices} == 1 )); then
    pick=${choices[1]}
  else
    pick=$(print -rl -- "${choices[@]}" \
      | _secret_fzf --header="secret › $tok › copy which field" --prompt='field> ') || return 0
    [[ -z $pick ]] && return 0
  fi
  print -rn -- "${pick#*=}" | pbcopy
  print -r -- "copied ${pick%%=*} of $tok to clipboard"
}

_secret_ui_open_url() {        # $1 project  $2 token: open the url= field in the browser
  local proj=$1 tok=$2 _tok_name _tok_layer row url
  local -a _tok_flags f
  _secret_ui_split_token "$tok"
  row=$(_secret_row_of "$_tok_name" "$proj" "$_tok_layer")
  [[ -z $row ]] && { _secret_err "not found: $tok"; return 1 }
  f=("${(@ps:\t:)row}")
  if ! url=$(_secret_meta_get "${f[8]}" url); then
    print -r -- "$tok has no url= field (add one: secret update $tok -p $proj --meta url=...)"
    return 0
  fi
  if [[ $url != http://* && $url != https://* ]]; then
    _secret_err "$tok: url= is not an http(s) URL, not opening it"
    return 1
  fi
  open "$url" && print -r -- "opened $url"
}

# List is a browser: the picker with its preview, with the item actions on
# keys so a look at a secret flows straight into the next step without
# going back through the top menu. A key action returns to the list; enter
# settles on an item, prints its details and leaves.
_secret_ui_list() {
  local proj out key tok reply _tok_name _tok_layer
  local -a _tok_flags
  proj=$(_secret_ui_pick_project 'secret › list › choose project') || return 0
  [[ -z $proj ]] && return 0
  local header="secret › $proj$(_secret_kc_suffix "$proj") › list    enter: show & leave  ^y: copy  ^f: field  ^o: open url  ^e: update  ^d: delete  esc: back"
  while true; do
    out=$(_secret_ui_pick_items "$proj" "$header" expect --expect=ctrl-y,ctrl-f,ctrl-o,ctrl-e,ctrl-d --height=70%) || return 0
    key=${out%%$'\n'*}
    tok=${out#*$'\n'}
    [[ -n $tok && $tok != "$out" ]] || return 0
    _secret_ui_split_token "$tok"
    case $key in
      ctrl-y)
        _secret_cmd_get "$_tok_name" -p "$proj" "${_tok_flags[@]}" --copy
        ;;
      ctrl-f)
        _secret_ui_copy_field "$proj" "$tok"
        ;;
      ctrl-o)
        _secret_ui_open_url "$proj" "$tok"
        ;;
      ctrl-e)
        _secret_ui_update_token "$proj" "$tok"
        ;;
      ctrl-d)
        if read -q "reply?delete $(_secret_disp "$proj" "$_tok_layer" "$_tok_name")? [y/N] "; then
          print '' >&2
          _secret_cmd_rm "$_tok_name" -p "$proj" "${_tok_flags[@]}" -f
        else
          print '' >&2
        fi
        ;;
      *)
        _secret_cmd_show "$_tok_name" -p "$proj" "${_tok_flags[@]}"
        return
        ;;
    esac
    print ''
  done
}

_secret_ui_show() {
  local proj tok _tok_name _tok_layer
  local -a _tok_flags
  proj=$(_secret_ui_pick_project 'secret › show › choose project') || return 0
  [[ -z $proj ]] && return 0
  tok=$(_secret_ui_pick_items "$proj" "secret › $proj$(_secret_kc_suffix "$proj") › show" "") || return 0
  [[ -z $tok ]] && return 0
  _secret_ui_split_token "$tok"
  _secret_cmd_show "$_tok_name" -p "$proj" "${_tok_flags[@]}"
}

_secret_ui_delete() {
  local proj names n _tok_name _tok_layer
  local -a _tok_flags
  proj=$(_secret_ui_pick_project 'secret › delete › choose project') || return 0
  [[ -z $proj ]] && return 0
  names=$(_secret_ui_pick_items "$proj" "secret › $proj$(_secret_kc_suffix "$proj") › delete (TAB to multi-select)" multi) || return 0
  [[ -z $names ]] && return 0
  print -r -- "selected:"
  for n in ${(f)names}; do print -r -- "  $proj/$n"; done
  local reply
  if ! read -q "reply?delete ${#${(f)names}} secret(s)? [y/N] "; then print '' >&2; return 0; fi
  print '' >&2
  for n in ${(f)names}; do
    _secret_ui_split_token "$n"
    _secret_cmd_rm "$_tok_name" -p "$proj" "${_tok_flags[@]}" -f
  done
}

_secret_ui_export() {
  local proj fmt out
  proj=$(_secret_ui_pick_project 'secret › export › choose project' '[all projects]') || return 0
  [[ -z $proj ]] && return 0
  fmt=$(printf '%s\n' \
      'age    encrypted JSON, passphrase (recommended)' \
      'json   plaintext JSON, metadata kept' \
      'env    plaintext export lines, no metadata' \
    | _secret_fzf --header='secret › export › format' --prompt='format> ') || return 0
  fmt=${${(z)fmt}[1]}
  local ext=$fmt pname=$proj
  [[ $fmt == age ]] && ext="json.age"
  [[ $proj == '[all projects]' ]] && pname=all
  local def="secret-export-${pname}-$(date +%Y%m%d).$ext"
  read -r "out?output file [$def]: " || return 0
  out=${out:-$def}
  local -a args
  args=(--format "$fmt" -o "$out")
  if [[ $proj == '[all projects]' ]]; then
    args+=(--all)
  else
    args+=(-p "$proj")
  fi
  _secret_cmd_export "${args[@]}"
}

_secret_ui_import() {
  local file proj
  local -a cands
  cands=(*.env(N) *.json(N) *.age(N))
  file=$(print -rl -- "${cands[@]}" '[enter a path]' | grep -v '^$' \
    | _secret_fzf --header='secret › import › choose file' --prompt='file> ') || return 0
  [[ -z $file ]] && return 0
  if [[ $file == '[enter a path]' ]]; then
    read -r "file?file path: " || return 0
    file=${file/#\~\//$HOME/}
    [[ -z $file ]] && return 0
  fi
  proj=$(_secret_ui_pick_project 'secret › import › target project' \
    '[auto / as recorded in file]' '[+ new project]') || return 0
  [[ -z $proj ]] && return 0
  if [[ $proj == '[+ new project]' ]]; then
    read -r "proj?new project name: " || return 0
    proj=${${proj##[[:space:]]#}%%[[:space:]]#}
    _secret_check_project "$proj" || return 1
  fi
  local -a args
  args=("$file")
  [[ $proj != '[auto / as recorded in file]' ]] && args+=(-p "$proj")
  _secret_cmd_import "${args[@]}"
}

_secret_ui() {
  if ! command -v fzf >/dev/null 2>&1; then
    _secret_err "the interactive UI needs fzf (brew install fzf); CLI subcommands still work"
    return 1
  fi
  local choice
  choice=$(printf '%s\n' \
      'Get      copy a secret to the clipboard' \
      'Add      store a new secret' \
      'Update   change the value or metadata of a secret' \
      'List     browse a project: preview, then show / copy / update / delete' \
      'Show     inspect metadata (never the value)' \
      'Delete   delete secrets (TAB to multi-select)' \
      'Export   write secrets to a file (age/json/env)' \
      'Import   load secrets from a file' \
    | _secret_fzf --header='secret › choose an action' --prompt='action> ') || return 0
  [[ -z $choice ]] && return 0
  case ${${(z)choice}[1]:l} in
    get)    _secret_ui_get ;;
    add)    _secret_ui_add ;;
    update) _secret_ui_update ;;
    list)   _secret_ui_list ;;
    show)   _secret_ui_show ;;
    delete) _secret_ui_delete ;;
    export) _secret_ui_export ;;
    import) _secret_ui_import ;;
  esac
}

# ------------------------------------------------------------- dispatcher --

secret() {
  emulate -L zsh
  setopt local_options pipefail extended_glob
  local _kc_opt="" _kc_explicit=0
  while [[ $1 == -k || $1 == --keychain ]]; do
    [[ -n $2 ]] || { _secret_err "-k requires a keychain name or path"; return 2 }
    _kc_opt=$2
    _kc_explicit=1
    shift 2
  done
  local _kc _kc_default
  local -a _kc_sl              # the user search list, read on first use (_secret_kc_sl_load)
  local _kc_sl_loaded=0
  local -A _kc_unlocked        # keychain -> when _secret_kc_ensure last ran
  _kc_default=$(_secret_default_keychain)
  if (( _kc_explicit )); then
    _kc=$(_secret_resolve_keychain "$_kc_opt")
  else
    _kc=$_kc_default   # only reached via keychain mgmt / "" rows; items are 1:1
  fi
  [[ -n $_kc ]] || { _secret_err "could not resolve the target keychain"; return 1 }
  local cmd=${1:-}
  (( $# )) && shift
  case $cmd in
    '')             _secret_ui ;;
    ui)             _secret_ui ;;
    set)            _secret_cmd_set "$@" ;;
    update|edit)    _secret_cmd_update "$@" ;;
    get)            _secret_cmd_get "$@" ;;
    show)           _secret_cmd_show "$@" ;;
    ls|list)        _secret_cmd_ls "$@" ;;
    rm|del|delete)  _secret_cmd_rm "$@" ;;
    env)            _secret_cmd_env "$@" ;;
    export)         _secret_cmd_export "$@" ;;
    import)         _secret_cmd_import "$@" ;;
    migrate)        _secret_cmd_migrate "$@" ;;
    projects)       _secret_cmd_projects ;;
    link)           _secret_cmd_link "$@" ;;
    keychain|kc)    _secret_cmd_keychain "$@" ;;
    help|-h|--help) _secret_cmd_help ;;
    *)              _secret_err "unknown command '$cmd' (try: secret help)"; return 2 ;;
  esac
}
