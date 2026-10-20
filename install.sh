#!/usr/bin/env bash
# Install or remove the client mod in a Tabula Rasa 1.16.5.0 game folder.
#   ./install.sh "<game folder>"            copy python_nca_internal/ into the game folder
#   ./install.sh "<game folder>" uninstall  remove it again
# The game folder is the one with tabula_rasa.exe and trpython.zip. No game file is changed.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/python_nca_internal"
GAME="${1:?usage: install.sh <game folder> [uninstall]}"
DEST="$GAME/python_nca_internal"

if [ ! -f "$GAME/tabula_rasa.exe" ] || [ ! -f "$GAME/trpython.zip" ]; then
    echo "Not a Tabula Rasa game folder (no tabula_rasa.exe / trpython.zip): $GAME" >&2
    exit 1
fi

if [ "${2:-}" = "uninstall" ]; then
    rm -rf "$DEST"
    echo "Removed $DEST"
    exit 0
fi

mkdir -p "$DEST"
# Compiled copies of an older version would be loaded in place of the new source.
rm -f "$DEST"/*.pyo "$DEST"/*.pyc
cp "$SRC"/*.py "$DEST"/
echo "Installed into $DEST. Log: $GAME/client_mod.log"
