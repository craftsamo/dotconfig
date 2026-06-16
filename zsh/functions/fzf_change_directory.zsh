# Function to change directory using fzf for selection
function _fzf_change_directory {
  fzf | perl -pe 's/([ ()])/\\\\$1/g' | read -r foo
  if [ "$foo" ]; then
    cd "$foo"
  fi
}

# Keep only the first occurrence per resolved (symlink-followed) path.
# Listed-first wins, so grouped Projects symlinks beat their ghq originals.
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

# Function to list directories and invoke _fzf_change_directory for selection
function fzf_change_directory {
  local gh=("$HOME"/Workspaces/Projects/*/github(N/))
  {
    # Config dir + Workspaces root
    echo "$HOME/.config"
    echo "$HOME/Workspaces"
    # Project & personal group dirs (docs/data/AGENTS.md homes)
    find "$HOME/Workspaces/Projects" "$HOME/Workspaces/Personal" \
      -mindepth 1 -maxdepth 1 -type d ! -name '.*' 2>/dev/null
    # Repos via their grouped symlinks (listed before ghq so grouped wins on dedup)
    (( $#gh )) && find -L "${gh[@]}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null
    # ghq repos (catch-all incl. ungrouped tool clones); anchored sed keeps .github intact
    find "$(ghq root)" -maxdepth 4 -type d -name .git | sed 's#/\.git$##'
    # Directories in the current directory
    ls -d */ 2>/dev/null | perl -pe "s#^#$PWD/#"
  } | sed -e 's/\/$//' | _dedup_by_realpath | _fzf_change_directory "$@"
}
