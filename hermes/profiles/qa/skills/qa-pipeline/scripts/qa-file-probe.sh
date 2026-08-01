#!/bin/sh
# Read-only identity probe for immutable Kanban attachment files.

set -eu

if [ "$#" -lt 1 ]; then
    printf '%s\n' "usage: $0 <attachment-file>..." >&2
    exit 2
fi

root=${HERMES_KANBAN_ATTACHMENTS_ROOT:-"$HOME/.hermes/kanban/attachments"}
if [ ! -d "$root" ]; then
    printf '%s\n' "qa-file-probe: attachment root not found: $root" >&2
    exit 1
fi
root=$(cd "$root" && pwd -P)

for requested in "$@"; do
    directory=$(/usr/bin/dirname "$requested")
    basename=$(/usr/bin/basename "$requested")
    if [ ! -d "$directory" ]; then
        printf '%s\n' "qa-file-probe: attachment directory not found: $requested" >&2
        exit 1
    fi
    directory=$(cd "$directory" && pwd -P)
    path="$directory/$basename"
    case "$path" in
        "$root"/*) ;;
        *)
            printf '%s\n' "qa-file-probe: resolved path is outside Kanban attachments: $requested" >&2
            exit 1
            ;;
    esac
    if [ ! -f "$path" ] || [ -L "$path" ]; then
        printf '%s\n' "qa-file-probe: expected a regular non-symlink file: $requested" >&2
        exit 1
    fi

    digest=$(/usr/bin/shasum -a 256 "$path")
    digest=${digest%% *}
    bytes=$(/usr/bin/wc -c < "$path")
    lines=$(/usr/bin/wc -l < "$path")
    bytes=${bytes##* }
    lines=${lines##* }
    kind=$(/usr/bin/file -b "$path")
    printf 'sha256=%s\tbytes=%s\tlines=%s\ttype=%s\tpath=%s\n' \
        "$digest" "$bytes" "$lines" "$kind" "$path"
done
