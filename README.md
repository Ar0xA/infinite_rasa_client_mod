# Infinite Rasa client mod

A Python-only mod for the Tabula Rasa 1.16.5.0 client, for use with
[Rasa.NET](https://github.com/InfiniteRasa/Rasa.NET). The goal is to let the server
add content the retail client does not know, starting with new missions (their
objectives, dialogue and text).

Status: **experimental.** Tested in the client on 2026-10-20: the loader runs, and
changing an existing mission text works (objective 17243 of mission 427). New
mission IDs are not done yet.

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
5. when a `client.ui.*window` module loads, makes its windows movable
   (`clientmod_movable.py`, experimental): hold ALT and drag a window with the left mouse
   button. The hook sits on the game's root-window mouse handlers
   (`client.inputhandlers`), so the click may land anywhere in the window, also on its title.
   Positions are saved in `client_mod_windows.txt` in the game folder (delete it to reset).
   Turn this off with `MOVABLE_WINDOWS = False` in `clientmod_data.py`, or exclude single
   windows in `MOVABLE_EXCLUDED`.

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
