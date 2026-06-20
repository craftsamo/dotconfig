# wslink.zsh — manage workspace repo links (CLI + fzf wizard)
#
#   wslink                          interactive wizard (fzf): Add/Update/Delete/List/Show/Sync
#   wslink ls [-p GROUP] [-l]       list links with status
#   wslink show NAME [-p GROUP]     details of one link
#   wslink add [-p GROUP] [REPO…]   register + symlink ghq clone(s) into a group
#   wslink update NAME [-p GROUP] [--repair|--repoint|--move GROUP]
#   wslink rm NAME [-p GROUP] [--keep-registry] [-f]
#   wslink sync [-p GROUP]          link registered-but-unlinked repos; report unregistered clones
#   wslink help
#
# A workspace "link" is a symlink Projects/<group>/github/<name> -> a ~/ghq clone.
# The projects registry (pj) is the source of truth for which repo belongs to which
# group; this is a thin, ergonomic layer over `pj` + ghq + the filesystem.
#
# Safety invariants:
#   - the ~/ghq clone itself is NEVER deleted; only symlinks are created/removed
#   - a real file/directory occupying a link path is never overwritten (abort)
#   - registry changes always go through `pj` (never hand-edit the DB)
#
# Implementation note: it mirrors secret.zsh — a dispatcher + `_wslink_cmd_*`
# subcommands, loaded interactively by config.zsh and callable non-interactively
# through bin/wslink (which is also what fzf's preview invokes).

# --------------------------------------------------------------------- helpers

_wslink_err() { print -r -- "wslink: $*" >&2; }

_wslink_need_commands() {
  emulate -L zsh
  local -a missing
  local c
  for c in pj ghq fzf jq; do
    command -v "$c" >/dev/null 2>&1 || missing+=("$c")
  done
  if (( ${#missing[@]} )); then
    _wslink_err "missing command(s): ${missing[*]}"
    return 1
  fi
}

_wslink_ghq_root() {
  emulate -L zsh
  local r
  r=$(ghq root 2>/dev/null)
  [[ -n $r ]] || r=${GHQ_ROOT:-$HOME/ghq}
  print -r -- "$r"
}

# ~/ghq/<host>/<owner>/<repo> -> "host\towner\trepo\thttps://host/owner/repo"
_wslink_parse_ghq_path() {
  emulate -L zsh
  local rp="$1"
  local root="${2:-$(_wslink_ghq_root)}"
  local rel host owner repo
  [[ -n $root ]] || return 1
  rp="${rp:A}"; root="${root:A}"
  rel="${rp#$root/}"
  [[ $rel != $rp ]] || return 1
  [[ $rel == */*/* ]] || return 1
  host="${rel%%/*}"; rel="${rel#*/}"
  owner="${rel%%/*}"; repo="${rel#*/}"
  [[ -n $host && -n $owner && -n $repo && $repo != */* ]] || return 1
  print -r -- "$host"$'\t'"$owner"$'\t'"$repo"$'\t'"https://$host/$owner/$repo"
}

_wslink_resolve_symlink() {
  emulate -L zsh
  local lp="$1" target
  target=$(readlink "$lp") || return 1
  if [[ $target == /* ]]; then print -r -- "$target"
  else print -r -- "${lp:h}/$target"; fi
}

# state token for a (link_path, ghq_path) pair; "-" ghq means unknown
_wslink_state() {
  emulate -L zsh
  local lp="$1" ghq="$2" target
  [[ $ghq == "-" ]] && ghq=""
  if [[ -L $lp ]]; then
    target=$(_wslink_resolve_symlink "$lp") || { print -r -- broken-link; return; }
    if [[ ! -e $target ]]; then print -r -- broken-link
    elif [[ -n $ghq && -e $ghq && ${target:A} != ${ghq:A} ]]; then print -r -- wrong-target
    else print -r -- ok; fi
  elif [[ -e $lp ]]; then
    print -r -- conflict
  elif [[ -n $ghq && -e $ghq ]]; then
    print -r -- declared
  elif [[ -n $ghq ]]; then
    print -r -- missing-clone
  else
    print -r -- declared
  fi
}

# _wslink_sigil <state> [force-color]  — colored when stdout is a tty or force=1
_wslink_sigil() {
  emulate -L zsh
  local st="$1" force="${2:-0}" glyph color
  case "$st" in
    ok)            glyph='●'; color=32 ;;
    declared)      glyph='○'; color=33 ;;
    unregistered)  glyph='+'; color=36 ;;
    broken-link)   glyph='✗'; color=31 ;;
    wrong-target)  glyph='≠'; color=35 ;;
    orphan-link)   glyph='?'; color=33 ;;
    conflict)      glyph='!'; color=31 ;;
    missing-clone) glyph='…'; color=2 ;;
    *)             print -rn -- ' '; return ;;
  esac
  if (( force )) || [[ -t 1 ]]; then
    print -rn -- $'\e['"$color"$'m'"$glyph"$'\e[0m'
  else
    print -rn -- "$glyph"
  fi
}

# groups: "id\tdir_path" for every non-archived project with a dir_path
_wslink_groups() {
  emulate -L zsh
  pj projects --json 2>/dev/null \
    | jq -r '.data.projects[] | select(.status != "archived") | select(.dir_path != null) | [.id, .dir_path] | @tsv'
}

_wslink_group_dir() {
  emulate -L zsh
  pj projects --json 2>/dev/null \
    | jq -r --arg g "$1" '.data.projects[] | select(.id == $g) | .dir_path' | head -n1
}

_wslink_registered_keys() {
  emulate -L zsh
  pj repos --json 2>/dev/null \
    | jq -r '.data.repos[] | [(.host // "github.com"), (.owner // "-"), .name] | @tsv'
}

# machine row (9 TSV fields): state group name link ghq kind owner host url
_wslink_group_entries() {
  emulate -L zsh
  local g="$1" dir="$2"
  local name owner host url ghq link st
  local repos_json p base target parsed root
  local -a pc
  typeset -A seen

  repos_json=$(pj repos --json --project "$g" 2>/dev/null) || return 1
  while IFS=$'\t' read -r name owner host url ghq link; do
    [[ -n $name ]] || continue
    seen[$name]=1
    [[ $ghq == "-" && $owner != "-" ]] && ghq="$HOME/ghq/$host/$owner/$name"
    [[ $link == "-" ]] && link="$dir/github/$name"
    st=$(_wslink_state "$link" "$ghq")
    print -r -- "$st"$'\t'"$g"$'\t'"$name"$'\t'"$link"$'\t'"$ghq"$'\t'registry$'\t'"$owner"$'\t'"$host"$'\t'"$url"
  done < <(print -r -- "$repos_json" | jq -r \
    '.data.repos[] | [.name, (.owner // "-"), (.host // "github.com"), (.url // "-"), (.ghq_path // "-"), (.link_path // "-")] | @tsv')

  root=$(_wslink_ghq_root)
  for p in "$dir"/github/*(ND); do
    [[ -e $p || -L $p ]] || continue
    base="${p:t}"
    [[ -n ${seen[$base]} ]] && continue
    owner=-; host=-; url=-; ghq=-
    if [[ -L $p ]]; then
      target=$(_wslink_resolve_symlink "$p") || target=-
      ghq=$target
      st=orphan-link
      [[ $target == "-" || ! -e $target ]] && st=broken-link
      if parsed=$(_wslink_parse_ghq_path "$target" "$root" 2>/dev/null); then
        pc=("${(@ps:\t:)parsed}"); host="${pc[1]}"; owner="${pc[2]}"; url="${pc[4]}"
      fi
    else
      st=conflict
    fi
    print -r -- "$st"$'\t'"$g"$'\t'"$base"$'\t'"$p"$'\t'"$ghq"$'\t'orphan$'\t'"$owner"$'\t'"$host"$'\t'"$url"
  done
}

_wslink_all_entries() {
  emulate -L zsh
  local g dir
  while IFS=$'\t' read -r g dir; do
    [[ -n $g && -n $dir ]] || continue
    _wslink_group_entries "$g" "$dir"
  done < <(_wslink_groups)
}

# ghq clones with no registry row (machine rows, kind=clone)
_wslink_add_candidates() {
  emulate -L zsh
  local root rp parsed key kh ko kn regkey
  local -a pc
  typeset -A reg
  while IFS=$'\t' read -r kh ko kn; do regkey="$kh/$ko/$kn"; reg[$regkey]=1; done < <(_wslink_registered_keys)
  root=$(_wslink_ghq_root)
  while IFS= read -r rp; do
    parsed=$(_wslink_parse_ghq_path "$rp" "$root") || continue
    pc=("${(@ps:\t:)parsed}")
    key="${pc[1]}/${pc[2]}/${pc[3]}"
    [[ -n ${reg[$key]} ]] && continue
    print -r -- unregistered$'\t'-$'\t'"${pc[3]}"$'\t'-$'\t'"$rp"$'\t'clone$'\t'"${pc[2]}"$'\t'"${pc[1]}"$'\t'"${pc[4]}"
  done < <(ghq list -p 2>/dev/null)
}

_wslink_confirm() {
  emulate -L zsh
  local prompt="$1" r src
  if [[ -r /dev/tty && -w /dev/tty ]]; then src=/dev/tty
  elif [[ -t 0 ]]; then src=/dev/stdin
  else _wslink_err "confirmation needs a terminal (pass -f/--yes)"; return 1; fi
  read -q "r?$prompt [y/N] " <"$src" || { print '' >&2; return 1; }
  print '' >&2
  return 0
}

_wslink_pause() {
  emulate -L zsh
  local r
  read -k1 -s "r?(press any key to continue)" </dev/tty 2>/dev/null
  print '' >&2
}

_wslink_safe_unlink() {
  emulate -L zsh
  local lp="$1"
  if [[ -L $lp ]]; then
    rm "$lp"
  elif [[ -e $lp ]]; then
    _wslink_err "refusing to remove real entry: $lp"
    return 1
  fi
}

# abort if any selected row's link path is occupied by a real (non-symlink) entry
_wslink_abort_on_conflicts() {
  emulate -L zsh
  local row lp
  local -a c conflicts
  for row in "$@"; do
    c=("${(@ps:\t:)row}")
    lp="${c[4]}"
    [[ -e $lp && ! -L $lp ]] && conflicts+=("$lp")
  done
  if (( ${#conflicts[@]} )); then
    _wslink_err "aborting; real file/directory exists at:"
    print -ru2 -- "${(F)conflicts}"
    return 1
  fi
}

_wslink_repo_set() {
  emulate -L zsh
  local project="$1" name="$2" owner="$3" host="$4" url="$5" ghq="$6"
  local -a args
  args=(repo-set --project "$project" --name "$name")
  [[ -n $owner && $owner != "-" ]] && args+=(--owner "$owner")
  [[ -n $host  && $host  != "-" ]] && args+=(--host "$host")
  [[ -n $url   && $url   != "-" ]] && args+=(--url "$url")
  [[ -n $ghq   && $ghq   != "-" ]] && args+=(--ghq-path "$ghq")
  [[ -n $ghq   && -f "$ghq/AGENTS.md" ]] && args+=(--has-agents-md)
  pj "${args[@]}" >/dev/null
}

# locate a clone by "repo" or "owner/repo"; print its ghq path
_wslink_find_clone() {
  emulate -L zsh
  local q="$1" root rp parsed
  local -a pc hits
  root=$(_wslink_ghq_root)
  while IFS= read -r rp; do
    parsed=$(_wslink_parse_ghq_path "$rp" "$root") || continue
    pc=("${(@ps:\t:)parsed}")
    if [[ $q == */* ]]; then
      [[ "${pc[2]}/${pc[3]}" == "$q" ]] && hits+=("$rp")
    else
      [[ "${pc[3]}" == "$q" ]] && hits+=("$rp")
    fi
  done < <(ghq list -p 2>/dev/null)
  case ${#hits[@]} in
    0) _wslink_err "no ghq clone matches '$q'"; return 1 ;;
    1) print -r -- "${hits[1]}" ;;
    *) _wslink_err "'$q' is ambiguous; use owner/name"; return 1 ;;
  esac
}

# resolve group from -p flag, else the current directory, else "" (caller decides)
_wslink_group_from_cwd() {
  emulate -L zsh
  local g dir cwd="${PWD:A}"
  while IFS=$'\t' read -r g dir; do
    [[ -n $g && -n $dir ]] || continue
    [[ $cwd == "${dir:A}"/github/* || $cwd == "${dir:A}" ]] && { print -r -- "$g"; return 0; }
  done < <(_wslink_groups)
  return 1
}

# compact, full-width fzf for the wizard (no preview pane, like secret)
_wslink_fzf() {
  fzf --height=45% --reverse --no-sort "$@"
}

# pick a group; with --all, prepend "[all groups]" (returns "*"). prints id or "*"
_wslink_ui_pick_group() {
  emulate -L zsh
  local all=0
  [[ "$1" == --all ]] && { all=1; shift; }
  local header="${1:-wslink › choose a group}"
  local sel g
  local -a items
  (( all )) && items+=('[all groups]')
  while IFS=$'\t' read -r g _; do [[ -n $g ]] && items+=("$g"); done < <(_wslink_groups)
  (( ${#items[@]} )) || { _wslink_err "no groups found"; return 1; }
  sel=$(print -rl -- "${items[@]}" | _wslink_fzf --prompt='group> ' --header="$header") || return 1
  [[ -n $sel ]] || return 1
  [[ $sel == '[all groups]' ]] && { print -r -- '*'; return 0; }
  print -r -- "$sel"
}

# find a single entry by NAME (optionally scoped to GROUP); prints machine row
_wslink_find_entry() {
  emulate -L zsh
  local name="$1" group="$2" row
  local -a rows matches c
  if [[ -n $group ]]; then
    rows=("${(@f)$(_wslink_group_entries "$group" "$(_wslink_group_dir "$group")")}")
  else
    rows=("${(@f)$(_wslink_all_entries)}")
  fi
  for row in "${rows[@]}"; do
    [[ -n $row ]] || continue
    c=("${(@ps:\t:)row}")
    [[ "${c[3]}" == "$name" ]] && matches+=("$row")
  done
  case ${#matches[@]} in
    0) return 1 ;;
    1) print -r -- "${matches[1]}"; return 0 ;;
    *) _wslink_err "'$name' exists in multiple groups; pass -p GROUP"; return 2 ;;
  esac
}

# --------------------------------------------------------------- core actions

# create registry row + symlink for one clone into a group
_wslink_add_clone() {
  emulate -L zsh
  local group="$1" clone="$2" dir parsed name host owner url link
  local -a pc
  parsed=$(_wslink_parse_ghq_path "$clone") || { _wslink_err "not a ghq clone: $clone"; return 1; }
  pc=("${(@ps:\t:)parsed}")
  host="${pc[1]}"; owner="${pc[2]}"; name="${pc[3]}"; url="${pc[4]}"
  dir=$(_wslink_group_dir "$group")
  [[ -n $dir ]] || { _wslink_err "unknown group: $group"; return 1; }
  link="$dir/github/$name"
  if [[ -e $link && ! -L $link ]]; then
    _wslink_err "refusing: real entry at $link"; return 1
  fi
  _wslink_repo_set "$group" "$name" "$owner" "$host" "$url" "$clone" || return 1
  pj link-repo --project "$group" --name "$name" >/dev/null \
    && print -r -- "added $group/$name -> $clone" \
    || { _wslink_err "link failed: $group/$name"; return 1; }
}

_wslink_repair_rows() {
  emulate -L zsh
  local -a rows=("$@") c
  local row group name link ghq kind st
  _wslink_abort_on_conflicts "${rows[@]}" || return 1
  for row in "${rows[@]}"; do
    [[ -n $row ]] || continue
    c=("${(@ps:\t:)row}")
    st="${c[1]}"; group="${c[2]}"; name="${c[3]}"; link="${c[4]}"; ghq="${c[5]}"; kind="${c[6]}"
    if [[ $kind != registry ]]; then
      _wslink_err "skip (not in registry): $name — use 'wslink add'"; continue
    fi
    [[ -L $link && $st != ok ]] && { _wslink_safe_unlink "$link" || continue; }
    pj link-repo --project "$group" --name "$name" >/dev/null \
      && print -r -- "repaired $group/$name" \
      || _wslink_err "repair failed: $group/$name"
  done
}

_wslink_repoint_row() {
  emulate -L zsh
  local row="$1" clone="$2"
  local -a c pc
  local group name link parsed host owner url
  c=("${(@ps:\t:)row}")
  group="${c[2]}"; name="${c[3]}"; link="${c[4]}"
  parsed=$(_wslink_parse_ghq_path "$clone") || { _wslink_err "not a ghq clone: $clone"; return 1; }
  pc=("${(@ps:\t:)parsed}")
  host="${pc[1]}"; owner="${pc[2]}"; url="${pc[4]}"
  [[ "${pc[3]}" != "$name" ]] && _wslink_err "note: link '$name' will point at clone '${pc[3]}'"
  [[ -L $link ]] && { _wslink_safe_unlink "$link" || return 1; }
  _wslink_repo_set "$group" "$name" "$owner" "$host" "$url" "$clone" || return 1
  pj link-repo --project "$group" --name "$name" >/dev/null \
    && print -r -- "repointed $group/$name -> $clone" \
    || { _wslink_err "repoint failed: $group/$name"; return 1; }
}

_wslink_move_rows() {
  emulate -L zsh
  local dest="$1"; shift
  local -a rows=("$@") c
  local destdir row group name link ghq kind owner host url destlink
  local -a conflicts
  destdir=$(_wslink_group_dir "$dest")
  [[ -n $destdir ]] || { _wslink_err "unknown group: $dest"; return 1; }
  _wslink_abort_on_conflicts "${rows[@]}" || return 1
  for row in "${rows[@]}"; do
    [[ -n $row ]] || continue
    c=("${(@ps:\t:)row}")
    name="${c[3]}"; destlink="$destdir/github/$name"
    [[ -e $destlink || -L $destlink ]] && conflicts+=("$destlink")
  done
  if (( ${#conflicts[@]} )); then
    _wslink_err "aborting; destination already has:"; print -ru2 -- "${(F)conflicts}"; return 1
  fi
  for row in "${rows[@]}"; do
    [[ -n $row ]] || continue
    c=("${(@ps:\t:)row}")
    group="${c[2]}"; name="${c[3]}"; link="${c[4]}"; ghq="${c[5]}"; kind="${c[6]}"
    owner="${c[7]}"; host="${c[8]}"; url="${c[9]}"
    [[ $group == "$dest" ]] && { _wslink_err "skip: $name already in $dest"; continue; }
    _wslink_repo_set "$dest" "$name" "$owner" "$host" "$url" "$ghq" || continue
    pj link-repo --project "$dest" --name "$name" >/dev/null || { _wslink_err "link failed in $dest: $name"; continue; }
    _wslink_safe_unlink "$link" || continue
    [[ $kind == registry ]] && pj repo-rm --project "$group" --name "$name" >/dev/null 2>&1
    print -r -- "moved $name: $group -> $dest"
  done
}

_wslink_delete_rows() {
  emulate -L zsh
  local keep_registry="$1"; shift
  local -a rows=("$@") c
  local row group name link kind
  _wslink_abort_on_conflicts "${rows[@]}" || return 1
  for row in "${rows[@]}"; do
    [[ -n $row ]] || continue
    c=("${(@ps:\t:)row}")
    group="${c[2]}"; name="${c[3]}"; link="${c[4]}"; kind="${c[6]}"
    _wslink_safe_unlink "$link" || continue
    if [[ $kind == registry ]]; then
      if [[ $keep_registry == 1 ]]; then
        pj repo-set --project "$group" --name "$name" --status declared >/dev/null \
          && print -r -- "unlinked $group/$name (registry kept)"
      else
        pj repo-rm --project "$group" --name "$name" >/dev/null \
          && print -r -- "removed $group/$name (link + registry)"
      fi
    else
      print -r -- "unlinked $group/$name (orphan)"
    fi
  done
}

_wslink_show_row() {
  emulate -L zsh
  local row="$1"
  local -a c
  local st group name link ghq kind owner host url target color=0
  c=("${(@ps:\t:)row}")
  st="${c[1]}"; group="${c[2]}"; name="${c[3]}"; link="${c[4]}"; ghq="${c[5]}"
  kind="${c[6]}"; owner="${c[7]}"; host="${c[8]}"; url="${c[9]}"
  [[ -t 1 ]] && color=1
  printf '%-10s %s %s\n' 'State:' "$(_wslink_sigil "$st" $color)" "$st"
  printf '%-10s %s\n' 'Group:' "$group" 'Name:' "$name" 'Kind:' "$kind"
  [[ $owner != "-" ]] && printf '%-10s %s\n' 'Owner:' "$owner"
  [[ $url != "-" ]] && printf '%-10s %s\n' 'URL:' "$url"
  printf '%-10s %s\n' 'Link:' "$link" 'Target:' "$ghq"
  if [[ -L $link ]]; then
    target=$(_wslink_resolve_symlink "$link") && printf '%-10s %s\n' 'Resolves:' "$target"
  fi
  if [[ -n $ghq && $ghq != "-" && -e "$ghq/.git" ]] || { [[ -d "$ghq/.git" ]] }; then
    local branch dirty
    branch=$(git -C "$ghq" branch --show-current 2>/dev/null)
    [[ -n $(git -C "$ghq" status --porcelain 2>/dev/null) ]] && dirty="dirty" || dirty="clean"
    printf '%-10s %s\n' 'Git:' "${branch:-?} ($dirty)"
  fi
  local amd="no"
  [[ -f "$link/AGENTS.md" || -f "$ghq/AGENTS.md" ]] && amd="yes"
  printf '%-10s %s\n' 'AGENTS.md:' "$amd"
}

# ------------------------------------------------------------- subcommands

_wslink_cmd_help() {
  emulate -L zsh
  cat >&2 <<'EOF'
wslink — manage workspace repo links (symlinks under Projects/<group>/github)

  wslink                          interactive wizard (Add/Update/Delete/List/Show/Sync)
  wslink ls [-p GROUP] [-l]       list links with status
  wslink show NAME [-p GROUP]     details of one link
  wslink add [-p GROUP] [REPO…]   register + symlink ghq clone(s) into a group
  wslink update NAME [-p GROUP] [--repair|--repoint|--move GROUP] [-f]
  wslink rm NAME [-p GROUP] [--keep-registry] [-f]
  wslink sync [-p GROUP]          link registered-but-unlinked repos; report unregistered
  wslink help

Status: ● ok  ○ declared  + unregistered  ✗ broken  ≠ wrong-target
        ? orphan  ! conflict  … missing-clone
EOF
}

_wslink_cmd_ls() {
  emulate -L zsh
  local group="" long=0
  while (( $# )); do
    case "$1" in
      -p) group="$2"; shift 2 ;;
      -l|--long) long=1; shift ;;
      -*) _wslink_err "ls: unknown option '$1'"; return 2 ;;
      *) _wslink_err "ls: unexpected argument '$1'"; return 2 ;;
    esac
  done
  local st g name link ghq kind owner host url sig color=0
  local gen
  [[ -t 1 ]] && color=1
  if [[ -n $group ]]; then
    local dir; dir=$(_wslink_group_dir "$group")
    [[ -n $dir ]] || { _wslink_err "unknown group: $group"; return 1; }
    gen=("_wslink_group_entries" "$group" "$dir")
  else
    gen=("_wslink_all_entries")
  fi
  "${gen[@]}" | while IFS=$'\t' read -r st g name link ghq kind owner host url; do
    [[ -n $st ]] || continue
    sig=$(_wslink_sigil "$st" $color)
    if (( long )); then
      printf '%s %-46s %-14s %s\n' "$sig" "$g/$name" "$st" "$ghq"
    else
      printf '%s %-46s %s\n' "$sig" "$g/$name" "${owner}/${name}"
    fi
  done
}

_wslink_cmd_show() {
  emulate -L zsh
  local name="" group=""
  while (( $# )); do
    case "$1" in
      -p) group="$2"; shift 2 ;;
      -*) _wslink_err "show: unknown option '$1'"; return 2 ;;
      *) name="$1"; shift ;;
    esac
  done
  [[ -n $name ]] || { _wslink_err "show: NAME required"; return 2 }
  [[ -z $group ]] && group=$(_wslink_group_from_cwd)
  local row
  row=$(_wslink_find_entry "$name" "$group") || {
    (( $? == 2 )) || _wslink_err "not found: $name"; return 1
  }
  _wslink_show_row "$row"
}

_wslink_cmd_add() {
  emulate -L zsh
  local group=""
  local -a repos
  while (( $# )); do
    case "$1" in
      -p) group="$2"; shift 2 ;;
      -*) _wslink_err "add: unknown option '$1'"; return 2 ;;
      *) repos+=("$1"); shift ;;
    esac
  done
  [[ -z $group ]] && group=$(_wslink_group_from_cwd)

  if (( ${#repos[@]} )); then
    [[ -n $group ]] || { [[ -t 0 ]] && group=$(_wslink_ui_pick_group); }
    [[ -n $group ]] || { _wslink_err "add: -p GROUP required (or run inside a group)"; return 2 }
    local r clone rc=0
    for r in "${repos[@]}"; do
      clone=$(_wslink_find_clone "$r") || { rc=1; continue; }
      _wslink_add_clone "$group" "$clone" || rc=1
    done
    return $rc
  fi

  # interactive: hand off to the wizard add flow (no args = pick clones + group)
  [[ -t 0 ]] || { _wslink_err "add: REPO required in non-interactive use"; return 2 }
  _wslink_ui_add "$group"
}

_wslink_cmd_update() {
  emulate -L zsh
  local name="" group="" mode="repair" dest="" force=0
  while (( $# )); do
    case "$1" in
      -p) group="$2"; shift 2 ;;
      --repair) mode="repair"; shift ;;
      --repoint) mode="repoint"; shift ;;
      --move) mode="move"; dest="$2"; shift 2 ;;
      -f|--yes) force=1; shift ;;
      -*) _wslink_err "update: unknown option '$1'"; return 2 ;;
      *) name="$1"; shift ;;
    esac
  done
  [[ -n $name ]] || { _wslink_err "update: NAME required"; return 2 }
  [[ -z $group ]] && group=$(_wslink_group_from_cwd)
  local row
  row=$(_wslink_find_entry "$name" "$group") || {
    (( $? == 2 )) || _wslink_err "not found: $name"; return 1
  }
  case "$mode" in
    repair) _wslink_repair_rows "$row" ;;
    repoint)
      [[ -t 0 ]] || { _wslink_err "update --repoint needs a terminal"; return 2 }
      local clone
      clone=$(_wslink_ui_pick_clone "wslink › repoint $name › choose target clone") || return 0
      [[ -n $clone ]] || return 0
      (( force )) || _wslink_confirm "Repoint $group/$name to $clone?" || return 1
      _wslink_repoint_row "$row" "$clone"
      ;;
    move)
      [[ -n $dest ]] || { _wslink_err "update --move needs a destination GROUP"; return 2 }
      (( force )) || _wslink_confirm "Move $name from $group to $dest?" || return 1
      _wslink_move_rows "$dest" "$row"
      ;;
  esac
}

# pick any ghq clone (full-width, no preview); prints its ghq path
_wslink_ui_pick_clone() {
  emulate -L zsh
  local header="${1:-wslink › choose a clone}" sel root rp parsed
  local -a pc c
  root=$(_wslink_ghq_root)
  sel=$(
    while IFS= read -r rp; do
      parsed=$(_wslink_parse_ghq_path "$rp" "$root") || continue
      pc=("${(@ps:\t:)parsed}")
      printf '%-50s\t%s\n' "${pc[2]}/${pc[3]}" "$rp"
    done < <(ghq list -p 2>/dev/null) \
      | _wslink_fzf --prompt='clone> ' --header="$header" --delimiter=$'\t' --with-nth=1
  ) || return 1
  [[ -n $sel ]] || return 1
  c=("${(@ps:\t:)sel}")
  print -r -- "${c[2]}"
}

_wslink_cmd_rm() {
  emulate -L zsh
  local name="" group="" keep=0 force=0
  while (( $# )); do
    case "$1" in
      -p) group="$2"; shift 2 ;;
      --keep-registry) keep=1; shift ;;
      -f|--force) force=1; shift ;;
      -*) _wslink_err "rm: unknown option '$1'"; return 2 ;;
      *) name="$1"; shift ;;
    esac
  done
  [[ -n $name ]] || { _wslink_err "rm: NAME required"; return 2 }
  [[ -z $group ]] && group=$(_wslink_group_from_cwd)
  local row
  row=$(_wslink_find_entry "$name" "$group") || {
    (( $? == 2 )) || _wslink_err "not found: $name"; return 1
  }
  local -a c=("${(@ps:\t:)row}")
  if (( ! force )); then
    [[ -t 0 ]] || { _wslink_err "rm needs a terminal to confirm (or pass -f)"; return 1 }
    _wslink_confirm "Delete link ${c[2]}/${c[3]}$( (( keep )) && print -n ' (keep registry)' )?" || return 1
  fi
  _wslink_delete_rows "$keep" "$row"
}

_wslink_cmd_sync() {
  emulate -L zsh
  local group=""
  while (( $# )); do
    case "$1" in
      -p) group="$2"; shift 2 ;;
      -*) _wslink_err "sync: unknown option '$1'"; return 2 ;;
      *) _wslink_err "sync: unexpected argument '$1'"; return 2 ;;
    esac
  done
  local st g name link ghq kind owner host url
  local -a report
  local gen
  if [[ -n $group ]]; then
    local dir; dir=$(_wslink_group_dir "$group")
    [[ -n $dir ]] || { _wslink_err "unknown group: $group"; return 1; }
    gen=("_wslink_group_entries" "$group" "$dir")
  else
    gen=("_wslink_all_entries")
  fi
  while IFS=$'\t' read -r st g name link ghq kind owner host url; do
    [[ -n $st ]] || continue
    if [[ $kind == registry ]]; then
      case "$st" in
        ok) ;;
        declared)
          pj link-repo --project "$g" --name "$name" >/dev/null \
            && print -r -- "linked $g/$name" || _wslink_err "link failed: $g/$name" ;;
        broken-link)
          if [[ -n $ghq && -e $ghq ]]; then
            _wslink_safe_unlink "$link" && pj link-repo --project "$g" --name "$name" >/dev/null \
              && print -r -- "repaired $g/$name"
          else
            report+=("missing clone: $g/$name (ghq get $url)")
          fi ;;
        missing-clone) report+=("missing clone: $g/$name (ghq get $url)") ;;
        wrong-target)  report+=("wrong target: $g/$name (wslink update $name -p $g --repair)") ;;
        conflict)      report+=("conflict: real entry at $link") ;;
      esac
    else
      report+=("orphan link: $g/$name (wslink rm $name -p $g)")
    fi
  done < <("${gen[@]}")

  # unregistered clones (only when syncing all)
  if [[ -z $group ]]; then
    local crow
    local -a cc
    while IFS=$'\t' read -r st g name link ghq kind owner host url; do
      [[ -n $name ]] || continue
      report+=("not linked: $owner/$name (wslink add $name)")
    done < <(_wslink_add_candidates)
  fi

  if (( ${#report[@]} )); then
    print -ru2 -- "--- needs attention ---"
    print -rl -- "${report[@]}"
  fi
}

_wslink_cmd_preview() {
  emulate -L zsh
  local group="$1" name="$2" link="$3" ghq="$4" kind="$5"
  local st target
  st=$(_wslink_state "$link" "$ghq")
  printf '%-9s %s %s\n' 'State:' "$(_wslink_sigil "$st" 1)" "$st"
  printf '%-9s %s\n' 'Group:' "$group" 'Name:' "$name" 'Kind:' "$kind"
  printf '%-9s %s\n' 'Link:' "$link" 'Target:' "$ghq"
  if [[ -L $link ]]; then
    target=$(_wslink_resolve_symlink "$link") && printf '%-9s %s\n' 'Resolves:' "$target"
  fi
  if [[ -n $ghq && $ghq != "-" && -d "$ghq/.git" ]]; then
    local branch dirty remote
    remote=$(git -C "$ghq" remote get-url origin 2>/dev/null)
    branch=$(git -C "$ghq" branch --show-current 2>/dev/null)
    [[ -n $(git -C "$ghq" status --porcelain 2>/dev/null) ]] && dirty="dirty" || dirty="clean"
    printf '%-9s %s\n' 'Remote:' "${remote:-?}"
    printf '%-9s %s\n' 'Git:' "${branch:-?} ($dirty)"
  fi
  local amd="no"
  [[ -f "$link/AGENTS.md" || -f "$ghq/AGENTS.md" ]] && amd="yes"
  printf '%-9s %s\n' 'AGENTS:' "$amd"
}

# ------------------------------------------------------------- wizard (UI)
# Nested, secret-style: an action menu, then full-width single-column pickers
# (no preview pane), one action per invocation. Details live in Show.

# machine rows for a scope ("*" = all groups, else a group id)
_wslink_ui_links_rows() {
  emulate -L zsh
  local scope="$1"
  if [[ $scope == '*' ]]; then
    _wslink_all_entries
  else
    _wslink_group_entries "$scope" "$(_wslink_group_dir "$scope")"
  fi
}

# pick link(s) in a scope; prints selected "group<TAB>name" token(s), one per line
_wslink_ui_pick_links() {
  emulate -L zsh
  local scope="$1" header="$2" multi="$3"
  local out _disp g name
  local -a fzopts
  [[ $multi == multi ]] && fzopts+=(--multi)
  out=$(
    _wslink_ui_links_rows "$scope" \
      | while IFS=$'\t' read -r st g name link ghq kind owner host url; do
          [[ -n $st ]] || continue
          printf '%s %-48s %s\t%s\t%s\n' "$(_wslink_sigil "$st" 1)" "$g/$name" "$st" "$g" "$name"
        done \
      | _wslink_fzf "${fzopts[@]}" --ansi --prompt='link> ' --header="$header" \
          --delimiter=$'\t' --with-nth=1
  ) || return 1
  [[ -n $out ]] || return 1
  print -r -- "$out" | while IFS=$'\t' read -r _disp g name; do
    [[ -n $g && -n $name ]] && print -r -- "$g"$'\t'"$name"
  done
}

_wslink_ui_add() {
  emulate -L zsh
  local group="$1" out line
  local -a lines c
  out=$(
    _wslink_add_candidates \
      | while IFS=$'\t' read -r st g name link ghq kind owner host url; do
          [[ -n $ghq && $ghq != "-" ]] || continue
          printf '%-50s\t%s\n' "$owner/$name" "$ghq"
        done \
      | _wslink_fzf --multi --prompt='clone> ' \
          --header='wslink › add › choose clone(s) (Tab=multi)' --delimiter=$'\t' --with-nth=1
  ) || return 0
  lines=("${(@f)out}")
  (( ${#lines[@]} )) || { print -r -- "no unregistered clones"; _wslink_pause; return 0; }
  [[ -n $group ]] || group=$(_wslink_ui_pick_group 'wslink › add › choose target group') || return 0
  print -r -- "add to $group:"
  for line in "${lines[@]}"; do c=("${(@ps:\t:)line}"); print -r -- "  ${c[1]}"; done
  _wslink_confirm "Add ${#lines[@]} repo(s) to $group?" || return 0
  for line in "${lines[@]}"; do
    c=("${(@ps:\t:)line}")
    _wslink_add_clone "$group" "${c[2]}"
  done
  _wslink_pause
}

_wslink_ui_update() {
  emulate -L zsh
  local scope token g name row type clone dest
  scope=$(_wslink_ui_pick_group --all 'wslink › update › choose group') || return 0
  token=$(_wslink_ui_pick_links "$scope" 'wslink › update › choose link') || return 0
  IFS=$'\t' read -r g name <<<"$token"
  [[ -n $g && -n $name ]] || return 0
  row=$(_wslink_find_entry "$name" "$g") || { _wslink_err "not found: $name"; _wslink_pause; return 0; }
  type=$(printf '%s\n' \
      'Repair    recreate the symlink from the registry' \
      'Repoint   aim this link at a different clone' \
      'Move      move the link to another group' \
    | _wslink_fzf --header="wslink › $g/$name › update" --prompt='update> ') || return 0
  case "${${(z)type}[1]:l}" in
    repair)
      _wslink_repair_rows "$row" ;;
    repoint)
      clone=$(_wslink_ui_pick_clone "wslink › repoint $name › choose target clone") || return 0
      [[ -n $clone ]] || return 0
      _wslink_confirm "Repoint $g/$name to $clone?" || return 0
      _wslink_repoint_row "$row" "$clone" ;;
    move)
      dest=$(_wslink_ui_pick_group "wslink › move $name › destination group") || return 0
      [[ $dest == "$g" ]] && { _wslink_err "destination is the same group"; _wslink_pause; return 0; }
      _wslink_confirm "Move $name from $g to $dest?" || return 0
      _wslink_move_rows "$dest" "$row" ;;
    *) return 0 ;;
  esac
  _wslink_pause
}

_wslink_ui_delete() {
  emulate -L zsh
  local scope tokens token g name
  local -a toks rows
  scope=$(_wslink_ui_pick_group --all 'wslink › delete › choose group') || return 0
  tokens=$(_wslink_ui_pick_links "$scope" 'wslink › delete › choose link(s) (Tab=multi)' multi) || return 0
  toks=("${(@f)tokens}")
  (( ${#toks[@]} )) || return 0
  print -r -- "delete (unlink + remove registry row):"
  for token in "${toks[@]}"; do
    IFS=$'\t' read -r g name <<<"$token"
    [[ -n $g && -n $name ]] || continue
    print -r -- "  $g/$name"
    rows+=("$(_wslink_find_entry "$name" "$g")")
  done
  (( ${#rows[@]} )) || return 0
  _wslink_confirm "Delete ${#rows[@]} link(s)?" || return 0
  _wslink_delete_rows 0 "${rows[@]}"
  _wslink_pause
}

_wslink_ui_list() {
  emulate -L zsh
  local scope
  scope=$(_wslink_ui_pick_group --all 'wslink › list › choose group') || return 0
  if [[ $scope == '*' ]]; then _wslink_cmd_ls -l; else _wslink_cmd_ls -p "$scope" -l; fi
  _wslink_pause
}

_wslink_ui_show() {
  emulate -L zsh
  local scope token g name row
  scope=$(_wslink_ui_pick_group --all 'wslink › show › choose group') || return 0
  token=$(_wslink_ui_pick_links "$scope" 'wslink › show › choose link') || return 0
  IFS=$'\t' read -r g name <<<"$token"
  [[ -n $g && -n $name ]] || return 0
  row=$(_wslink_find_entry "$name" "$g") || { _wslink_err "not found: $name"; _wslink_pause; return 0; }
  _wslink_show_row "$row"
  _wslink_pause
}

_wslink_ui_sync() {
  emulate -L zsh
  local scope
  scope=$(_wslink_ui_pick_group --all 'wslink › sync › choose group') || return 0
  if [[ $scope == '*' ]]; then _wslink_cmd_sync; else _wslink_cmd_sync -p "$scope"; fi
  _wslink_pause
}

_wslink_ui() {
  emulate -L zsh
  _wslink_need_commands || return 1
  local choice
  choice=$(printf '%s\n' \
      'Add      register + link a ghq clone into a group' \
      'Update   repair / repoint / move a link' \
      'Delete   unlink and remove from the workspace' \
      'List     list links in a group' \
      'Show     inspect one link' \
      'Sync     link the unlinked; report drift' \
    | _wslink_fzf --header='wslink › choose an action' --prompt='action> ') || return 0
  [[ -n $choice ]] || return 0
  case "${${(z)choice}[1]:l}" in
    add)    _wslink_ui_add ;;
    update) _wslink_ui_update ;;
    delete) _wslink_ui_delete ;;
    list)   _wslink_ui_list ;;
    show)   _wslink_ui_show ;;
    sync)   _wslink_ui_sync ;;
  esac
}

# ------------------------------------------------------------- dispatcher

wslink() {
  emulate -L zsh
  local cmd="${1:-}"
  (( $# )) && shift
  case "$cmd" in
    "")            if [[ -t 0 && -t 1 ]]; then _wslink_ui; else _wslink_cmd_help; fi ;;
    add)           _wslink_cmd_add "$@" ;;
    ls|list)       _wslink_cmd_ls "$@" ;;
    show)          _wslink_cmd_show "$@" ;;
    update)        _wslink_cmd_update "$@" ;;
    rm|remove|delete) _wslink_cmd_rm "$@" ;;
    sync)          _wslink_cmd_sync "$@" ;;
    __preview)     _wslink_cmd_preview "$@" ;;
    help|-h|--help) _wslink_cmd_help ;;
    *)             _wslink_err "unknown command '$cmd' (try: wslink help)"; return 2 ;;
  esac
}
