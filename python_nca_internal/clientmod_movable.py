# Movable windows: drag a client window with the right mouse button, or with Ctrl + left
# mouse button, to move it.
# The new place is saved and used again the next time the window is set up or shown.
#
# Python 2.4. Experimental.
#
# How it works:
# - Every client/ui/*window module defines a script class whose Init(self) the engine calls;
#   self.window is that window's root widget. patch_module wraps Init (and Show) to record
#   which widget belongs to which window and to put it back at its saved place.
# - The game registers its own mouse handlers on the UI root window (client.gameui.Initialize):
#   client.inputhandlers.HandleOtherMouseInputs for button down/up and HandleMouseMove for
#   moves. The root window sees every click; event['ClickedWidget'] is the widget under the
#   mouse. patch_inputhandlers wraps those two functions before gameui registers them.
#   When the right button is down and the mouse moves 4 pixels (or on Ctrl + left button
#   down), the clicked widget's parents are searched for a recorded window; that window then
#   follows the mouse (SetAnchorOffset) until the button goes up. A right click without
#   movement still reaches the game (context menus).
# - Anchor offsets may be scaled or point the other way (a window anchored to the right or
#   bottom), so the first drag measures how the window's screen rectangle follows its offset.

import sys

POSITIONS_FILE = 'client_mod_windows.txt'

_log = None
_positions = {}      # window key -> (x, y) anchor offset
_scale = {}          # window key -> (sx, sy): offset units per screen pixel
_windows = []        # [(root widget, window key)] of every window that ran Init
_drag = []           # [widget, key, mouse x, mouse y, offset x, offset y] while dragging
_loaded = [False]
_misses = [0]


def _say(message):
    if _log is not None:
        _log('movable: ' + message)


def _load_positions():
    if _loaded[0]:
        return
    _loaded[0] = True
    try:
        f = open(POSITIONS_FILE, 'r')
    except IOError:
        return
    try:
        for line in f.readlines():
            parts = line.split()
            if len(parts) == 3:
                try:
                    _positions[parts[0]] = (float(parts[1]), float(parts[2]))
                except ValueError:
                    pass
    finally:
        f.close()


def _save_positions():
    f = open(POSITIONS_FILE, 'w')
    try:
        keys = _positions.keys()
        keys.sort()
        for key in keys:
            x, y = _positions[key]
            f.write('%s %r %r\n' % (key, x, y))
    finally:
        f.close()


# --- mouse --------------------------------------------------------------------------------

def _mouse_pos(event):
    try:
        return float(event['LocX']), float(event['LocY'])
    except:
        import gameclient
        pos = gameclient.GetUIManager().GetMousePos()
        return float(pos[0]), float(pos[1])


def _modifier_down(event):
    # Mouse events carry Ctrl and Shift only: Windows mouse messages have no ALT flag, so
    # uievent.eModAlt never appears in event['Modifiers'] (checked in game, 2026-10-20).
    import uievent
    try:
        return uievent.eModControl in event['Modifiers']
    except:
        return False


def _same(a, b):
    if a is b:
        return True
    # The engine may hand out a new Python object for the same widget; its repr holds the
    # engine address (<PyUIObject type=Window @0x0AE94130>).
    try:
        return a == b or repr(a) == repr(b)
    except:
        return False


def _find_window(widget):
    # The clicked widget, or one of its parents, is the root widget of a recorded window.
    depth = 0
    while widget is not None and depth < 64:
        for root, key in _windows:
            if _same(root, widget):
                return root, key
        try:
            widget = widget.GetParent()
        except:
            return None
        depth += 1
    return None


def _measure_scale(key, widget, offset):
    # Move the window 10 offset units on each axis and see how far its rectangle goes.
    left, top, right, bottom = widget.GetScreenRect()
    widget.SetAnchorOffset(offset[0] + 10, offset[1] + 10)
    left2, top2, right2, bottom2 = widget.GetScreenRect()
    widget.SetAnchorOffset(offset[0], offset[1])
    sx = sy = 1.0
    if left2 != left:
        sx = 10.0 / (left2 - left)
    if top2 != top:
        sy = 10.0 / (top2 - top)
    _scale[key] = (sx, sy)
    _say('%s offset units per pixel %r, %r' % (key, sx, sy))


def _start_drag(clicked, mx, my):
    found = _find_window(clicked)
    if found is None:
        if _misses[0] < 5:
            _misses[0] += 1
            _say('drag click on %r, which is not in a known window' % (clicked,))
        return False
    widget, key = found
    ox, oy = widget.GetAnchorOffset()
    if key not in _scale:
        _measure_scale(key, widget, (ox, oy))
    _drag[:] = [widget, key, mx, my, ox, oy]
    return True


def _move_drag(event):
    widget, key, mx0, my0, ox, oy = _drag
    mx, my = _mouse_pos(event)
    sx, sy = _scale.get(key, (1.0, 1.0))
    widget.SetAnchorOffset(ox + (mx - mx0) * sx, oy + (my - my0) * sy)


def _end_drag(event):
    _move_drag(event)
    widget, key = _drag[0], _drag[1]
    del _drag[:]
    x, y = widget.GetAnchorOffset()
    _positions[key] = (x, y)
    _save_positions()
    _say('%s moved to %r, %r' % (key, x, y))


_debug_left = [10]   # button events still to log, to see what the root window receives


def _debug_event(what, event):
    if _debug_left[0] <= 0:
        return
    _debug_left[0] -= 1
    try:
        _say('%s Type=%r Phase=%r ButtonID=%r DownButtons=%r Modifiers=%r ClickedWidget=%r'
             % (what, event.get('Type'), event.get('Phase'), event.get('ButtonID'),
                event.get('DownButtons'), event.get('Modifiers'), event.get('ClickedWidget')))
    except:
        pass


# event['Phase']: 1 button down, 2 button up, 0 mouse move; event['ButtonID']: 1 left
# (seen in game, 2026-10-20).
PHASE_DOWN = 1
PHASE_UP = 2
LEFT = 1
RIGHT = 2
DRAG_START_PIXELS = 4

_right = []          # [clicked widget, mouse x, mouse y] while the right button is down


def _wrap_button_handler(real):
    def HandleOtherMouseInputs(widget, event):
        try:
            import uievent
            _debug_event('button', event)
            phase = event.get('Phase')
            button = event.get('ButtonID')
            if phase == PHASE_UP:
                del _right[:]
                if _drag:
                    _end_drag(event)
                    # The game still sees the button go up, so its own state stays right.
                    real(widget, event)
                    return uievent.eHandledStop
            elif phase == PHASE_DOWN and not _drag:
                if button == LEFT and _modifier_down(event):
                    mx, my = _mouse_pos(event)
                    if _start_drag(event.get('ClickedWidget'), mx, my):
                        return uievent.eHandledStop
                elif button == RIGHT:
                    # A right click stays a right click; the drag starts once the mouse moves.
                    mx, my = _mouse_pos(event)
                    _right[:] = [event.get('ClickedWidget'), mx, my]
        except:
            del _drag[:]
            del _right[:]
            _say('mouse button hook failed: %s' % (sys.exc_info()[1],))
        return real(widget, event)
    return HandleOtherMouseInputs


def _wrap_move_handler(real):
    def HandleMouseMove(widget, event):
        try:
            if _right and not _drag:
                clicked, x0, y0 = _right
                mx, my = _mouse_pos(event)
                if abs(mx - x0) + abs(my - y0) >= DRAG_START_PIXELS:
                    del _right[:]
                    _start_drag(clicked, x0, y0)
            if _drag:
                import uievent
                _move_drag(event)
                return uievent.eHandledStop
        except:
            del _drag[:]
            del _right[:]
            _say('mouse move hook failed: %s' % (sys.exc_info()[1],))
        return real(widget, event)
    return HandleMouseMove


def patch_inputhandlers(module, log):
    """Wrap the game's root-window mouse handlers; call before client.gameui.Initialize."""
    global _log
    _log = log
    module.HandleOtherMouseInputs = _wrap_button_handler(module.HandleOtherMouseInputs)
    module.HandleMouseMove = _wrap_move_handler(module.HandleMouseMove)
    _say('right drag and Ctrl + left drag hooked on the root window handlers')


# --- windows ------------------------------------------------------------------------------

def _restore(key, script):
    widget = getattr(script, 'window', None)
    if widget is not None and key in _positions:
        x, y = _positions[key]
        widget.SetAnchorOffset(x, y)


def _record(key, script):
    widget = getattr(script, 'window', None)
    if widget is None:
        _say('%s has no window widget, skipped' % key)
        return
    for i in range(len(_windows)):
        if _windows[i][1] == key:
            _windows[i] = (widget, key)
            break
    else:
        _windows.append((widget, key))
    _restore(key, script)
    _say('%s ready' % key)


def _wrap(cls, method_name, key, after):
    real = cls.__dict__.get(method_name)
    if real is None:
        return False

    def wrapper(self, *args, **kwargs):
        result = real(self, *args, **kwargs)
        try:
            after(key, self)
        except:
            _say('%s after %s failed: %s' % (key, method_name, sys.exc_info()[1]))
        return result

    wrapper.__name__ = method_name
    setattr(cls, method_name, wrapper)
    return True


def patch_module(name, module, log, excluded):
    """Record and restore the windows of one client.ui.*window module (fully loaded)."""
    global _log
    _log = log
    _load_positions()
    short = name.split('.')[-1]
    if short in excluded:
        _say('%s excluded' % short)
        return
    for attr, cls in module.__dict__.items():
        if not hasattr(cls, '__bases__') or getattr(cls, '__module__', None) != module.__name__:
            continue
        if 'Init' not in cls.__dict__:
            continue
        key = '%s.%s' % (short, attr)
        _wrap(cls, 'Init', key, _record)
        _wrap(cls, 'Show', key, _restore)
        _say('patched %s' % key)
