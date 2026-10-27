#!/usr/bin/env bash
# Install or remove the client mod in a Tabula Rasa 1.16.5.0 game folder.
#   ./install.sh "<game folder>"            install as a mod folder (mods/infinite_rasa), named in
#                                           tabula_rasa.cfg [Data] (the default way)
#   ./install.sh "<game folder>" sideload   install as python_nca_internal (the old way)
#   ./install.sh "<game folder>" uninstall  remove the mod (both ways) and its tabula_rasa.cfg line
# Each install removes the other way first, so only one way is in place.
# The mod folder way changes one line in tabula_rasa.cfg (first copy: tabula_rasa.cfg.mod-backup).
# If tabula_rasa.cfg is a symlink, it is replaced by a copy, so the file it points to is not changed.
# The side-load way changes no game file.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/mod"
GAME="${1:?usage: install.sh <game folder> [sideload|uninstall]}"
SIDELOAD="$GAME/python_nca_internal"
MODDIR="$GAME/mods/infinite_rasa"
CFG="$GAME/tabula_rasa.cfg"
# [Data] key of the mod folder. It must come before GameData (see mod/generated/__init__.py):
# the line goes first in [Data], and the name sorts before GameData too.
KEY="AddonInfiniteRasa"

if [ ! -f "$GAME/tabula_rasa.exe" ] || [ ! -f "$GAME/trpython.zip" ]; then
    echo "Not a Tabula Rasa game folder (no tabula_rasa.exe / trpython.zip): $GAME" >&2
    exit 1
fi

copy_mod() {   # copy_mod <folder>: the mod's Python files and native modules
    mkdir -p "$1"
    # Compiled copies of an older version would be loaded in place of the new source.
    rm -f "$1"/*.pyo "$1"/*.pyc
    cp "$SRC"/clientmod_*.py "$1"/
    # Native modules (.pyd), if built (native/build.sh).
    # Remove before copying: a running game has the old file mapped, and overwriting it in
    # place could crash the game; a new file leaves the mapped one alone.
    for f in "$SRC"/*.pyd; do [ -e "$f" ] && rm -f "$1/$(basename "$f")" && cp "$f" "$1"/; done
    return 0
}

edit_cfg() {   # edit_cfg add|remove
    if [ ! -e "$CFG" ]; then
        # Without the file the client uses coded defaults for all paths; a new file with only
        # [Data] would drop them.
        [ "$1" = remove ] && return 0
        echo "No $CFG (the retail game has one); not installed." >&2
        exit 1
    fi
    if [ -L "$CFG" ]; then
        cp --remove-destination "$(readlink -f "$CFG")" "$CFG"
    fi
    [ -e "$CFG.mod-backup" ] || cp "$CFG" "$CFG.mod-backup"
    python3 -I - "$CFG" "$1" "$KEY" <<'EOF'
import re, sys
path, action, key = sys.argv[1:4]
text = open(path, 'rb').read().decode('latin-1')
nl = '\r\n' if '\r\n' in text else '\n'
lines = [l for l in text.split(nl) if not re.match(r'\s*%s\s*=' % re.escape(key), l)]
if action == 'add':
    try:
        i = [l.strip() for l in lines].index('[Data]')
    except ValueError:
        # No [Data] section: the client then uses its coded default, data/game.zip.
        lines += ['', '[Data]', 'GameData = "data/game.zip"']
        i = len(lines) - 2
    lines.insert(i + 1, '%s = "mods/infinite_rasa"' % key)
open(path, 'wb').write(nl.join(lines).encode('latin-1'))
EOF
}

remove_modfolder() {
    rm -rf "$MODDIR"
    rmdir "$GAME/mods" 2>/dev/null || true
    edit_cfg remove
}

case "${2:-}" in
"")
    edit_cfg add
    rm -rf "$SIDELOAD"
    copy_mod "$MODDIR"
    mkdir -p "$MODDIR/generated"
    rm -f "$MODDIR/generated"/*.pyo "$MODDIR/generated"/*.pyc
    cp "$SRC/generated/__init__.py" "$MODDIR/generated/"
    echo "Installed into $MODDIR, named in $CFG [Data]. Log: $GAME/client_mod.log"
    ;;
sideload)
    remove_modfolder
    copy_mod "$SIDELOAD"
    cp "$SRC"/clientbootstrap.py "$SIDELOAD"/
    echo "Installed into $SIDELOAD. Log: $GAME/client_mod.log"
    ;;
uninstall)
    remove_modfolder
    rm -rf "$SIDELOAD"
    echo "Removed $MODDIR, its line in $CFG, and $SIDELOAD"
    ;;
*)
    echo "usage: install.sh <game folder> [sideload|uninstall]" >&2
    exit 1
    ;;
esac
