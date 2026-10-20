# Movable windows: drag a client window with the left mouse button to move it. The new place
# is saved and used again the next time the window is set up or shown.
#
# Python 2.4. Experimental: which part of a window takes the drag depends on the engine (a
# click on a button or list goes to that child, not to the window).
#
# How it works: every client/ui/*window module defines a script class whose Init(self) the
# engine calls; self.window is that window's root widget. After Init, this module registers
# mouse handlers on self.window (RegisterPythonMouseEvent, as the inventory does for item
# drags) and moves it with SetAnchorOffset. Anchor offsets may be scaled or point the other
# way (a window anchored to the right or bottom), so the first drag step measures how the
# window's screen rectangle follows its offset and corrects for that.

import sys
import types

POSITIONS_FILE = 'client_mod_windows.txt'

_log = None
_positions = {}      # window key -> (x, y) anchor offset
_scale = {}          # window key -> (sx, sy): offset units per screen pixel
_drag = {}           # window key -> (mouse x, mouse y, offset x, offset y)
_loaded = [False]


def _mouse_pos():
    import gameclient
    pos = gameclient.GetUIManager().GetMousePos()
    return float(pos[0]), float(pos[1])


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
    _log('movable: %s offset units per pixel %r, %r' % (key, sx, sy))


def _handlers(key):
    def on_down(widget, event):
        try:
            mx, my = _mouse_pos()
            ox, oy = widget.GetAnchorOffset()
            if key not in _scale:
                _measure_scale(key, widget, (ox, oy))
            _drag[key] = (mx, my, ox, oy)
        except:
            _log('movable: %s mouse down failed: %s' % (key, sys.exc_info()[1]))

    def on_drag(widget, event):
        try:
            start = _drag.get(key)
            if start is None:
                return
            mx, my = _mouse_pos()
            sx, sy = _scale.get(key, (1.0, 1.0))
            x = start[2] + (mx - start[0]) * sx
            y = start[3] + (my - start[1]) * sy
            widget.SetAnchorOffset(x, y)
        except:
            _log('movable: %s drag failed: %s' % (key, sys.exc_info()[1]))

    def on_up(widget, event):
        try:
            if _drag.pop(key, None) is None:
                return
            x, y = widget.GetAnchorOffset()
            _positions[key] = (x, y)
            _save_positions()
            _log('movable: %s moved to %r, %r' % (key, x, y))
        except:
            _log('movable: %s mouse up failed: %s' % (key, sys.exc_info()[1]))

    return on_down, on_drag, on_up


def _restore(key, script):
    widget = getattr(script, 'window', None)
    if widget is not None and key in _positions:
        x, y = _positions[key]
        widget.SetAnchorOffset(x, y)


def _attach(key, script):
    widget = getattr(script, 'window', None)
    if widget is None:
        _log('movable: %s has no window widget, skipped' % key)
        return
    import uievent
    mouse = uievent.mouse
    on_down, on_drag, on_up = _handlers(key)
    widget.RegisterPythonMouseEvent(mouse.eButton1, mouse.eMouseDown, on_down)
    widget.RegisterPythonMouseEvent(mouse.eButton1, mouse.eMouseDrag, on_drag)
    widget.RegisterPythonMouseEvent(mouse.eButton1, mouse.eMouseUp, on_up)
    _restore(key, script)
    _log('movable: %s ready' % key)


def _wrap(cls, method_name, key, after):
    real = cls.__dict__.get(method_name)
    if real is None:
        return False

    def wrapper(self, *args, **kwargs):
        result = real(self, *args, **kwargs)
        try:
            after(key, self)
        except:
            _log('movable: %s after %s failed: %s' % (key, method_name, sys.exc_info()[1]))
        return result

    wrapper.__name__ = method_name
    setattr(cls, method_name, wrapper)
    return True


def patch_module(name, module, log, excluded):
    """Make the window classes of one client.ui.*window module movable."""
    global _log
    _log = log
    _load_positions()
    short = name.split('.')[-1]
    if short in excluded:
        log('movable: %s excluded' % short)
        return
    for attr, cls in module.__dict__.items():
        if not isinstance(cls, (type, types.ClassType)) or getattr(cls, '__module__', None) != module.__name__:
            continue
        if 'Init' not in cls.__dict__:
            continue
        key = '%s.%s' % (short, attr)
        _wrap(cls, 'Init', key, _attach)
        _wrap(cls, 'Show', key, _restore)
        log('movable: patched %s' % key)
