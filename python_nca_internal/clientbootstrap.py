# Infinite Rasa client mod loader.
#
# tabula_rasa.exe sets sys.path to ['python_nca_internal', '<game>/trpython.zip',
# '<game>/trpython.zip/client/system'] and then imports clientbootstrap and calls
# clientbootstrap.boot(). This folder comes first, so this file is found before the
# retail module. It loads the retail clientbootstrap from trpython.zip, so the game
# starts exactly as before, and adds a hook that sees modules as they are imported.
#
# Python 2.4: no 'with', no conditional expressions, no 'except X as e'.
# Nothing here may stop the game from starting: every mod step is guarded, and only
# a failure to load the retail module itself is raised.

import sys
import os
import time
import zipimport
import __builtin__

LOG_NAME = 'client_mod.log'

# Modules whose first import is logged: the mission tables and the language manager.
WATCH_WORDS = ('mission', 'clientlanguagemanager')


def _log(message):
    try:
        f = open(LOG_NAME, 'a')
        try:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), message))
        finally:
            f.close()
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


# Import watcher: logs the first time a watched module appears in sys.modules.
# Later steps (adding mission rows) hang off _on_module_loaded.
_seen = {}
_module_count = [0]
_real_import = __builtin__.__import__

# Text variants: each language table holds a text twice, keyed (textId, 1) and (textId, 2).
TEXT_VARIANTS = (1, 2)


def _apply_text_overrides(name, module):
    # name is e.g. generated.client.language.english.missiontextlanguage
    import clientmod_data
    table = name.split('.')[-1]
    overrides = clientmod_data.TEXT_OVERRIDES.get(table)
    if not overrides:
        return
    lookup = module.lookup
    for text_id, text in overrides.items():
        # The client's text filter asserts on anything but unicode (textfilter.FilterStaticText).
        if not isinstance(text, unicode):
            text = text.decode('utf-8')
        for variant in TEXT_VARIANTS:
            key = (text_id, variant)
            old = lookup.get(key)
            if old is None:
                lookup[key] = [text]
            else:
                # Keep the container type the table uses (a one-element list or tuple).
                lookup[key] = type(old)([text])
        _log('text %s %d set to %r' % (table, text_id, text))


def _on_module_loaded(name, module):
    _log('loaded %s (%s)' % (name, getattr(module, '__file__', '?')))
    if name.startswith('generated.client.language.') and hasattr(module, 'lookup'):
        _apply_text_overrides(name, module)


def _scan_new_modules():
    count = len(sys.modules)
    if count == _module_count[0]:
        return
    _module_count[0] = count
    for name, module in sys.modules.items():
        if module is None or name in _seen:
            continue
        for word in WATCH_WORDS:
            if word in name:
                _seen[name] = 1
                try:
                    _on_module_loaded(name, module)
                except:
                    _log('hook failed for %s: %s' % (name, sys.exc_info()[1]))
                break


def _watching_import(*args, **kwargs):
    module = _real_import(*args, **kwargs)
    try:
        _scan_new_modules()
    except:
        pass
    return module


def _wrap_boot(retail):
    real_boot = retail.boot

    def boot(*args, **kwargs):
        _log('boot: sys.path=%r' % (sys.path,))
        return real_boot(*args, **kwargs)

    retail.boot = boot


_this = sys.modules.get('clientbootstrap')
_log('loader started: cwd=%r sys.path=%r' % (os.getcwd(), sys.path))
_retail = _load_retail()

try:
    _wrap_boot(_retail)
    __builtin__.__import__ = _watching_import
    _log('loader ready')
except:
    _log('loader setup failed, game continues without the mod: %s' % (sys.exc_info()[1],))

# If this module object is used after all, it forwards to the retail one.
for _name, _value in _retail.__dict__.items():
    if not _name.startswith('__'):
        globals()[_name] = _value
