# Infinite Rasa client mod: the part that is the same for both ways to load the mod.
#
#   - python_nca_internal (side-load): clientbootstrap.py calls install() and, at boot,
#     load_native_modules().
#   - tabula_rasa.cfg (mod folder): the folder is a [Data] path, so the retail boot puts it
#     on sys.path; its generated/__init__.py calls start() when the client first imports
#     the game tables.
#
# install() adds a hook that sees modules as they are imported and changes the mission
# tables, the language tables and some UI modules (quest helper, movable windows).
#
# Python 2.4: no 'with', no conditional expressions, no 'except X as e'.
# Nothing here may stop the game from starting: every mod step is guarded.

import sys
import time
import __builtin__

LOG_NAME = 'client_mod.log'

# Modules whose first import is logged: the mission tables and the language manager.
WATCH_WORDS = ('mission', 'objectiveconversation', 'clientlanguagemanager', 'client.ui.',
               'client.inputhandlers', 'client.gameui')


def log(message):
    try:
        f = open(LOG_NAME, 'a')
        try:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), message))
        finally:
            f.close()
    except:
        pass


_log = log

# Import watcher: logs the first time a watched module appears in sys.modules.
# Later steps (adding mission rows) hang off _on_module_loaded.
_seen = {}
_module_count = [0]
_real_import = [None]

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


# Mission tables and how a MISSIONS entry becomes their rows. Each row value is a
# one-element list, as in the retail tables (e.g. missionconversation[(427, 1)] == [733]).
def _mission_rows(table, mission_id, mission):
    rows = {}
    if table == 'missionconversation':
        for text_type, text_id in mission.get('texts', {}).items():
            rows[(mission_id, text_type)] = [text_id]
    elif table == 'missionobjective':
        for objective_id, texts in mission.get('objectives', {}).items():
            # (name text, body text, three counter texts)
            rows[(mission_id, objective_id)] = [(texts[0], texts[1], None, None, None)]
    elif table == 'objectiveconversation':
        for key, text_id in mission.get('conversations', {}).items():
            objective_id, package_id, flag, conversation_type = key
            rows[(mission_id, objective_id, package_id, flag, conversation_type)] = [text_id]
    return rows


MISSION_TABLES = ('missionconversation', 'missionobjective', 'objectiveconversation')


def _apply_missions(table, module):
    import clientmod_data
    lookup = module.lookup
    for mission_id, mission in clientmod_data.MISSIONS.items():
        rows = _mission_rows(table, mission_id, mission)
        for key, value in rows.items():
            if key in lookup:
                _log('mission %d: %s %r already exists in the client, left alone' % (mission_id, table, key))
                continue
            lookup[key] = value
        _log('mission %d: %d %s rows added' % (mission_id, len(rows), table))


def _on_module_loaded(name, module):
    if name.startswith('client.ui.') or name in ('client.inputhandlers', 'client.gameui'):
        # The module is in sys.modules before its code has run; wait until it has.
        _pending.append((name, module))
        return
    _log('loaded %s (%s)' % (name, getattr(module, '__file__', '?')))
    if not hasattr(module, 'lookup'):
        return
    if name.startswith('generated.client.language.'):
        _apply_text_overrides(name, module)
    elif name.startswith('generated.client.') and name.split('.')[-1] in MISSION_TABLES:
        _apply_missions(name.split('.')[-1], module)


def _on_ui_module_loaded(name, module):
    import clientmod_data
    if getattr(clientmod_data, 'QUEST_HELPER', False):
        if name == 'client.gameui':
            import clientmod_quest_helper
            clientmod_quest_helper.attach_gameui(module, _log)
        elif name == 'client.ui.conversationwindow':
            import clientmod_quest_helper
            clientmod_quest_helper.attach_conversationwindow(module, _log)
    if not getattr(clientmod_data, 'MOVABLE_WINDOWS', False):
        return
    import clientmod_movable
    if name == 'client.inputhandlers':
        clientmod_movable.patch_inputhandlers(module, _log)
    elif name.endswith('window'):
        clientmod_movable.patch_module(name, module, _log,
                                       getattr(clientmod_data, 'MOVABLE_EXCLUDED', ()))


# Modules found in sys.modules whose code may still be running: (name, module).
_pending = []


def _module_running(module):
    frame = sys._getframe(1)
    while frame is not None:
        if frame.f_globals is module.__dict__ and frame.f_code.co_name in ('?', '<module>'):
            return True
        frame = frame.f_back
    return False


def _process_pending():
    for item in _pending[:]:
        name, module = item
        if _module_running(module):
            continue
        _pending.remove(item)
        if sys.modules.get(name) is not module:
            continue  # its import failed
        try:
            _on_ui_module_loaded(name, module)
        except:
            _log('hook failed for %s: %s' % (name, sys.exc_info()[1]))


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
    module = _real_import[0](*args, **kwargs)
    try:
        _scan_new_modules()
        if _pending:
            _process_pending()
    except:
        pass
    return module


def load_native_modules():
    # Native modules (.pyd DLLs on sys.path): importing one runs its native code.
    try:
        import clientmod_data
        names = getattr(clientmod_data, 'NATIVE_MODULES', ())
    except:
        _log('native modules failed: %s' % (sys.exc_info()[1],))
        return
    for name in names:
        try:
            module = __import__(name)
            info = ''
            if hasattr(module, 'info'):
                info = ': %s' % (module.info(),)
            _log('native module %s loaded%s' % (name, info))
        except:
            _log('native module %s not loaded: %s' % (name, sys.exc_info()[1]))


def install():
    # Puts the import hook in place once. Returns True if it is in place.
    if _real_import[0] is not None:
        return True
    try:
        _real_import[0] = __builtin__.__import__
        __builtin__.__import__ = _watching_import
        return True
    except:
        _real_import[0] = None
        _log('loader setup failed, game continues without the mod: %s' % (sys.exc_info()[1],))
        return False


def start(how):
    # Entry point of the tabula_rasa.cfg way (the mod folder's generated/__init__.py).
    if _real_import[0] is not None:
        return
    _log('loader started (%s): sys.path=%r' % (how, sys.path))
    load_native_modules()
    if install():
        _log('loader ready')
        # Modules loaded before this point (the UI and the game modules) are seen now.
        try:
            _scan_new_modules()
        except:
            _log('first scan failed: %s' % (sys.exc_info()[1],))
