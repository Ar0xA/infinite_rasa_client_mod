# Infinite Rasa client mod loader (side-load way: the python_nca_internal folder).
#
# tabula_rasa.exe sets sys.path to ['python_nca_internal', '<game>/trpython.zip',
# '<game>/trpython.zip/client/system'] and then imports clientbootstrap and calls
# clientbootstrap.boot(). This folder comes first, so this file is found before the
# retail module. It loads the retail clientbootstrap from trpython.zip, so the game
# starts exactly as before, and adds the mod's import hook (clientmod_loader).
# The other way to load the mod, a mod folder named in tabula_rasa.cfg: README.md.
#
# Python 2.4: no 'with', no conditional expressions, no 'except X as e'.
# Nothing here may stop the game from starting: every mod step is guarded, and only
# a failure to load the retail module itself is raised.

import sys
import os
import zipimport


def _log(message):
    try:
        import clientmod_loader
        clientmod_loader.log(message)
    except:
        pass


def _find_archive():
    for path in sys.path:
        if os.path.basename(path).lower() == 'trpython.zip':
            return path
    return None


def _load_retail():
    archive = _find_archive()
    if archive is None:
        raise ImportError('client mod: trpython.zip is not on sys.path %r' % (sys.path,))
    # Take this module out of sys.modules first, so the retail module is a module of
    # its own; the import that loaded this file then returns the retail one.
    if sys.modules.get('clientbootstrap') is _this:
        del sys.modules['clientbootstrap']
    return zipimport.zipimporter(archive).load_module('clientbootstrap')


def _wrap_boot(retail):
    real_boot = retail.boot

    def boot(*args, **kwargs):
        _log('boot: sys.path=%r' % (sys.path,))
        try:
            import clientmod_loader
            clientmod_loader.load_native_modules()
        except:
            _log('native modules failed: %s' % (sys.exc_info()[1],))
        return real_boot(*args, **kwargs)

    retail.boot = boot


_this = sys.modules.get('clientbootstrap')
_log('loader started: cwd=%r sys.path=%r' % (os.getcwd(), sys.path))
_retail = _load_retail()

try:
    _wrap_boot(_retail)
    import clientmod_loader
    if clientmod_loader.install():
        _log('loader ready')
except:
    _log('loader setup failed, game continues without the mod: %s' % (sys.exc_info()[1],))

# If this module object is used after all, it forwards to the retail one.
for _name, _value in _retail.__dict__.items():
    if not _name.startswith('__'):
        globals()[_name] = _value
