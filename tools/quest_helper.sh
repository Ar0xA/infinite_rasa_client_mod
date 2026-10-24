#!/usr/bin/env bash
# Send commands to the GM quest helper and show its state.
#   tools/quest_helper.sh "<game folder>" send "gm on" "goto 100 200 300"   one command per argument
#   tools/quest_helper.sh "<game folder>" state                              print quest_helper_state.txt
# The commands are written to a temporary file and renamed into place, so the game never reads
# half of them. If the game has not read the last commands yet, this waits up to 10 s for it.
set -euo pipefail
GAME="${1:?usage: quest_helper.sh <game folder> send <command>... | state}"
case "${2:-}" in
    send)
        shift 2
        for _ in $(seq 100); do [ -f "$GAME/quest_helper_cmd.txt" ] || break; sleep 0.1; done
        if [ -f "$GAME/quest_helper_cmd.txt" ]; then
            echo "The game has not read the last commands (is it running, with the helper on?)" >&2
            exit 1
        fi
        tmp="$GAME/quest_helper_cmd.tmp"
        printf '%s\n' "$@" > "$tmp"
        mv "$tmp" "$GAME/quest_helper_cmd.txt"
        ;;
    state)
        cat "$GAME/quest_helper_state.txt"
        ;;
    *)
        echo "usage: quest_helper.sh <game folder> send <command>... | state" >&2
        exit 2
        ;;
esac
