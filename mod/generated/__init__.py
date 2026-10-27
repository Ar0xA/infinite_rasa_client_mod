# Infinite Rasa client mod: entry point of the tabula_rasa.cfg way (no python_nca_internal).
#
# The mod folder is a [Data] path in tabula_rasa.cfg, named before GameData. The retail
# clientbootstrap.boot() adds every [Data] path to sys.path (trmain.GetDataPaths()), so the
# client's first 'import generated...' (the game tables) finds this package before the
# one in data/game.zip. The retail generated/__init__ is empty. This file adds the
# game.zip package folder to __path__, so all generated.* modules still come from
# game.zip, and starts the mod (clientmod_loader, in the mod folder).
#
# Python 2.4. Nothing here may stop the game from starting.

import sys
import os


def _game_tables():
    for path in sys.path:
        if os.path.basename(path).lower() == 'game.zip':
            return path + '/generated'
    return None


_tables = _game_tables()
if _tables is not None and _tables not in __path__:
    __path__.append(_tables)

try:
    import clientmod_loader
    if _tables is None:
        clientmod_loader.log('mod folder: game.zip is not on sys.path %r' % (sys.path,))
    clientmod_loader.start('tabula_rasa.cfg, generated=%r' % (__path__,))
except:
    try:
        f = open('client_mod.log', 'a')
        f.write('mod folder: start failed: %s\n' % (sys.exc_info()[1],))
        f.close()
    except:
        pass
