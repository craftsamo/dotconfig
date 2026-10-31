# Function to change directory using fzf for selection
function _fzf_change_directory {
  fzf | perl -pe 's/([ ()])/\\\\$1/g' | read -r foo
  if [ "$foo" ]; then
    cd "$foo"
  fi
}

# Keep only the first occurrence per resolved (symlink-followed) path.
# Listed-first wins, so grouped repository symlinks beat their ghq originals.
function _dedup_by_realpath {
  local -A seen
  local line real
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    real=${line:A}
    if [ -z "${seen[$real]}" ]; then
      seen[$real]=1
      print -r -- "$line"
    fi
  done
}

# The Workspaces root, then the projects area, then every area, one a line, from
# ws-layout (the shared layout); the public defaults when it is not installed.
function _workspace_layout_lines {
  (( $+commands[ws-layout] )) && ws-layout --lines 2>/dev/null && return
  print -l -- "$HOME/Workspaces" Projects Projects Personal
}

# Function to list directories and invoke _fzf_change_directory for selection
function fzf_change_directory {
  local -a layout areas
  layout=("${(@f)$(_workspace_layout_lines)}")
  local ws=$layout[1] projects=$layout[2]
  areas=("${(@)layout[3,-1]/#/$ws/}")
  local gh=("$ws/$projects"/*/github(N/))
  {
    # Config dir + Workspaces root
    echo "$HOME/.config"
    echo "$ws"
    # Every area's group dirs (docs/data/AGENTS.md homes)
    find "${areas[@]}" -mindepth 1 -maxdepth 1 -type d ! -name '.*' 2>/dev/null
    # Repos via their grouped symlinks (listed before ghq so grouped wins on dedup)
    (( $#gh )) && find -L "${gh[@]}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null
    # ghq repos (catch-all incl. ungrouped tool clones); anchored sed keeps .github intact
    find "$(ghq root)" -maxdepth 4 -type d -name .git | sed 's#/\.git$##'
    # Directories in the current directory
    ls -d */ 2>/dev/null | perl -pe "s#^#$PWD/#"
  } | sed -e 's/\/$//' | _dedup_by_realpath | _fzf_change_directory "$@"
}
