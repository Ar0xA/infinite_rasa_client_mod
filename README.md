# Infinite Rasa client mod

A Python-only mod for the Tabula Rasa 1.16.5.0 client, for use with
[Rasa.NET](https://github.com/InfiniteRasa/Rasa.NET). The goal is to let the server
add content the retail client does not know, starting with new missions (their
objectives, dialogue and text).

Status: **experimental.** Tested in the client on 2026-10-20:

- a new mission works end to end (**Infinite Rasa Welcome**, mission 90000001; see
  [create_missions.md](create_missions.md));
- changing an existing mission text works;
- client windows can be moved (see [Movable windows](#movable-windows));
- native code (a DLL) can run in the game process (see [native_modules.md](native_modules.md)).

## Movable windows

Drag any window to a new place with **Ctrl + left mouse button**: hold Ctrl, push the left
button on the window and move the mouse.

The click may land anywhere in the window, also on its title or on a button. ALT does
not work: the client never sees ALT on a mouse click (the event's `Modifiers` list holds
Ctrl and Shift only). The right and middle buttons are left alone: a right drag did not
always let go of the window, and the middle button zooms.

Each window's place is saved in `client_mod_windows.txt` in the game folder and used
again when the window opens or the game starts. Delete the file to put all windows back
at their default places. In `python_nca_internal/clientmod_data.py`:

- `MOVABLE_WINDOWS = False` turns the feature off;
- `MOVABLE_EXCLUDED` lists `client/ui` modules whose windows never move (the reticle
  and the character creation screen by default).

`client_mod.log` shows `movable: <window> moved to x, y` after each drag.

## Native modules (DLLs)

The loader can import `.pyd` files (32-bit DLLs) from `python_nca_internal`, so native code
runs inside the game. `native/clientmod_native.c` is a small example: it writes to
`client_mod.log` from native code and adds ` [Infinite Rasa mod]` to the window title. It is
off by default (`NATIVE_MODULES` in `clientmod_data.py`) and not in git as a binary; build
it with `native/build.sh`. Details: [native_modules.md](native_modules.md).

## How it works

The client runs its game logic on an embedded Python 2.4 (`python24.dll`). At
startup `tabula_rasa.exe` sets:

```python
sys.path = ['python_nca_internal', '<game>/trpython.zip', '<game>/trpython.zip/client/system']
```

and then imports `clientbootstrap` and calls `clientbootstrap.boot()`.

`python_nca_internal` is relative to the working folder and comes first, and the
retail client does not ship it. A `python_nca_internal/clientbootstrap.py` is
therefore imported in place of the retail module. This mod's loader:

1. loads the retail `clientbootstrap` from `trpython.zip`, so the game starts as before;
2. wraps `boot()` and the import function, and logs when the mission tables and the
   language manager are first imported (`client_mod.log` in the game folder);
3. when a language table loads, sets the texts in `clientmod_data.TEXT_OVERRIDES`.
   Texts must be unicode: the client's text filter rejects anything else.
4. when a mission table loads, adds the rows in `clientmod_data.MISSIONS`;
5. when a `client.ui.*window` module has loaded, wraps its window classes' `Init` and
   `Show` to record each window's root widget and put it at its saved place;
6. wraps the game's root-window mouse handlers (`client.inputhandlers.HandleOtherMouseInputs`
   and `HandleMouseMove`) before `client.gameui.Initialize` registers them. The root window
   sees every click and names the clicked widget (`event['ClickedWidget']`); its parents
   lead to the window to move (`clientmod_movable.py`).
7. at the start of `boot()`, imports the native modules in `clientmod_data.NATIVE_MODULES`
   (none by default).

The mission data lives in plain Python dictionaries once loaded, for example
`generated.client.missionobjective.lookup` and the `lookup` of the
`missiontextlanguage` language module. Later steps add rows to these from
`_on_module_loaded`.

No DLL, no `WINEDLLOVERRIDES` and no change to any game file are needed. It can run
beside the d3d9 GUI injector ([rasa_gui_injection](https://codeberg.org/d10sfan/rasa_gui_injection)).

## Install

The working folder must be the game folder (Lutris: *Working directory*).

```sh
./install.sh "/path/to/Tabula Rasa 1.16.5.0"
```

Start the game and read `client_mod.log` in the game folder. It should show
`loader started`, `loader ready`, `boot: …` and `loaded …` lines.

## Uninstall

```sh
./install.sh "/path/to/Tabula Rasa 1.16.5.0" uninstall
```

or delete the game folder's `python_nca_internal`.

## Rules for code in this repo

- Python 2.4 syntax only: no `with`, no `x if c else y`, no `except X as e`.
- A mod step must never stop the game from starting: guard it and log the error.
