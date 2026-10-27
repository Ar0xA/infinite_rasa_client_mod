# Infinite Rasa client mod

A Python-only mod for the Tabula Rasa 1.16.5.0 client, for use with
[Rasa.NET](https://github.com/InfiniteRasa/Rasa.NET). The goal is to let the server
add content the retail client does not know, starting with new missions (their
objectives, dialogue and text).

The mod installs as a mod folder (`mods/infinite_rasa`) that the game's own
`tabula_rasa.cfg` names. It needs no DLL, no `WINEDLLOVERRIDES` and no change to
`trpython.zip` or `data/`. The older side-load way (a `python_nca_internal` folder) is
still available.

Status: **experimental.** Tested in the client:

- a new mission works end to end (**Infinite Rasa Welcome**, mission 90000001; see
  [create_missions.md](create_missions.md)) (2026-10-20);
- changing an existing mission text works (2026-10-20);
- native code (a DLL) can run in the game process (see [native_modules.md](native_modules.md))
  (2026-10-20);
- the GM quest helper runs test commands (see [GM quest helper](#gm-quest-helper));
- the mod folder way gives the same result as the side-load way: mission rows, text
  overrides and the quest helper (2026-10-27);
- client windows can be moved, but not with the default drag button yet (see
  [Movable windows](#movable-windows)).

## Install

```sh
./install.sh "/path/to/Tabula Rasa 1.16.5.0"
```

This copies the mod into `mods/infinite_rasa` in the game folder and adds one line as the
first line of the `[Data]` section of `tabula_rasa.cfg`:

```ini
[Data]
AddonInfiniteRasa = "mods/infinite_rasa"
GameData = "data/game.zip"
```

The first copy of the file is kept as `tabula_rasa.cfg.mod-backup`. If
`tabula_rasa.cfg` is a symlink, the script replaces it by a copy, so the file it points
to does not change. The game's patcher can overwrite `tabula_rasa.cfg`; after a patch, run
`install.sh` again.

The working folder must be the game folder (Lutris: *Working directory*). Start the game
and read `client_mod.log` in the game folder. It should show
`loader started (tabula_rasa.cfg, …)`, `loader ready` and `loaded …` lines.

The side-load way, a `python_nca_internal` folder (no file of the game changes):

```sh
./install.sh "/path/to/Tabula Rasa 1.16.5.0" sideload
```

Each install removes the other way first, so only one way is in place.

## Uninstall

```sh
./install.sh "/path/to/Tabula Rasa 1.16.5.0" uninstall
```

This removes `mods/infinite_rasa`, its `[Data]` line and `python_nca_internal`.

## Settings

All settings and data are in `mod/clientmod_data.py` (installed as
`mods/infinite_rasa/clientmod_data.py`):

- `TEXT_OVERRIDES`: client texts to set or add, per language table;
- `MISSIONS`: new missions (see [create_missions.md](create_missions.md));
- `MOVABLE_WINDOWS`, `MOVABLE_EXCLUDED`: movable windows;
- `NATIVE_MODULES`: native modules to load;
- `QUEST_HELPER`, `QUEST_HELPER_GM_MODE`: the GM quest helper.

## How it works

The client runs its game logic on an embedded Python 2.4 (`python24.dll`). At
startup `tabula_rasa.exe` sets:

```python
sys.path = ['python_nca_internal', '<game>/trpython.zip', '<game>/trpython.zip/client/system']
```

and then imports `clientbootstrap` and calls `clientbootstrap.boot()`. The retail
`boot()` calls `trmain.InitApp()` and then `sys.path.extend(trmain.GetDataPaths())`.
`GetDataPaths()` returns every value of the `[Data]` section of `tabula_rasa.cfg`.
Normally that is only `GameData = "data/game.zip"`: the game tables, the `generated`
package.

### The mod folder way (default)

`mods/infinite_rasa` is a `[Data]` path, so the retail `boot()` puts it on `sys.path`
before `data/game.zip`. (The key is first in the section, and its name also sorts before
`GameData`. Which of the two decides is not checked.) The client's first
`import generated…` (the game tables, right after `InitApp`) finds the mod's
`generated` package (`mod/generated/__init__.py`). This file:

1. adds `data/game.zip/generated` to the package's `__path__`, so every table still
   comes from `game.zip` (the retail `generated/__init__` is empty);
2. starts the loader (`clientmod_loader.start`).

### The side-load way

`python_nca_internal` is relative to the working folder and comes first on `sys.path`,
and the retail client does not ship it. A `python_nca_internal/clientbootstrap.py`
(`mod/clientbootstrap.py`) is therefore imported in place of the retail module. It
loads the retail `clientbootstrap` from `trpython.zip`, so the game starts as before,
wraps `boot()` and starts the loader.

### The loader (`clientmod_loader.py`, both ways)

1. wraps the import function, and logs when the mission tables and the language manager
   are first imported (`client_mod.log` in the game folder);
2. when a language table loads, sets the texts in `clientmod_data.TEXT_OVERRIDES`.
   Texts must be unicode: the client's text filter rejects anything else;
3. when a mission table loads, adds the rows in `clientmod_data.MISSIONS`;
4. when a `client.ui.*window` module has loaded, wraps its window classes' `Init` and
   `Show` to record each window's root widget and put it at its saved place;
5. wraps the game's root-window mouse handlers (`client.inputhandlers.HandleOtherMouseInputs`
   and `HandleMouseMove`) before `client.gameui.Initialize` registers them. The root window
   sees every click and names the clicked widget (`event['ClickedWidget']`); its parents
   lead to the window to move (`clientmod_movable.py`);
6. attaches the GM quest helper to `client.gameui` and the conversation window;
7. imports the native modules in `clientmod_data.NATIVE_MODULES` (none by default).

The mission data lives in plain Python dictionaries once loaded, for example
`generated.client.missionobjective.lookup` and the `lookup` of the
`missiontextlanguage` language module. The loader adds rows to these from
`_on_module_loaded`.

The difference between the two ways is only the start time. The mod folder way starts
after `InitApp` (at the first import of the game tables), the side-load way before
`boot()`. Both are before the game sets up its UI and loads the mission tables.

The mod can run beside the d3d9 GUI injector
([rasa_gui_injection](https://codeberg.org/d10sfan/rasa_gui_injection)).

## Movable windows

**Off by default** (`MOVABLE_WINDOWS = False`). The code drags a window with **Shift +
middle mouse button** (push the wheel), but this does not work yet: in a test on
2026-10-24, wheel clicks never reached the root window handler (no event, with or without
Shift). The drag button is `DRAG_BUTTON` in `clientmod_movable.py`. A combination with
the left button (for example Ctrl + Shift + left) does reach the handler.

The click may land anywhere in the window, also on its title or on a button. ALT does
not work: the client never sees ALT on a mouse click (the event's `Modifiers` list holds
Ctrl and Shift only; `uievent`: eModShift=1, eModAlt=2, eModControl=4).

Each window's place is saved in `client_mod_windows.txt` in the game folder and used
again when the window opens or the game starts. Delete the file to put all windows back
at their default places. In `clientmod_data.py`:

- `MOVABLE_WINDOWS = True` turns the feature on;
- `MOVABLE_EXCLUDED` lists `client/ui` modules whose windows never move (the reticle
  and the character creation screen by default).

`client_mod.log` shows `movable: <window> moved to x, y` after each drag.

## Native modules (DLLs)

The loader can import `.pyd` files (32-bit DLLs) from the mod folder, so native code
runs inside the game. `native/clientmod_native.c` is a small example: it writes to
`client_mod.log` from native code and adds ` [Infinite Rasa mod]` to the window title. It is
off by default (`NATIVE_MODULES` in `clientmod_data.py`) and not in git as a binary; build
it with `native/build.sh`. Details: [native_modules.md](native_modules.md).

## GM quest helper

Experimental, for testing quests faster. `clientmod_quest_helper.py` reads commands from
`quest_helper_cmd.txt` in the game folder a few times a second, deletes the file and runs
the commands. It writes what it sees (position, target, open conversation and its choices,
the last results) to `quest_helper_state.txt` every second. Each result is also logged in
`client_mod.log` as `quest: …`.

```sh
tools/quest_helper.sh "/path/to/Tabula Rasa 1.16.5.0" send "gm on" "say .teleport -283 422 848 1497"
tools/quest_helper.sh "/path/to/Tabula Rasa 1.16.5.0" state
```

**Account level 10 only.** The client is not told the account level (`SetIsGM` is only a
yes or no). So when a character enters the world, the helper sends `.flag list` (read-only,
needs level 10) and reads the server's answer in chat. Until the answer comes, commands
wait. If the answer shows a lower level, or no answer comes within 10 s, the helper stays
off for that character and ignores commands. This is a convenience, not security: the
server checks the level of every GM command anyway.

Commands, one per line (entity ids are the server's decimal ids):

| Command | What it does |
|---|---|
| `look <entityId>` / `camera <degrees>` | Turns the camera towards the entity, or to a yaw (0 = +z), with the client's turn keys (`UserController.TurnLeft/TurnRight`) |
| `py <expression>` | Evaluates a Python expression in the client and logs the value (a test aid) |
| `say <text>` | Sends the text as if typed in chat, also GM commands (`.teleport …`) and slash commands |
| `gm on` / `gm off` | GM test mode: `.invisible on` and `.immune all`, or both off |
| `invisible on\|off`, `immune <args>` | One of the two (`.immune` acts on yourself: the target is cleared first) |
| `target <id>`, `untarget` | Sets or clears the target |
| `goto <x> <y> <z> [range]` | Walks to a position (y is up) |
| `walkto <id> [range]` | Walks to an entity |
| `use [id]` | Uses an entity (default: the target), walking to it first if needed |
| `stop` | Stops walking |
| `accept`, `decline`, `complete`, `reward` | The open conversation's buttons |
| `choice <n>` | Picks choice n of the open conversation, as numbered in the state file |
| `wait <ms>` | Waits before the next command |

With `QUEST_HELPER_GM_MODE = True` in `clientmod_data.py`, `gm on` is sent by itself once
the account level is confirmed, each time a character enters the world: the server turns
`.invisible` off at every login, and an immunity lasts only until logout. Send `gm off` for
a test that needs the character to be seen or hurt. `QUEST_HELPER = False` turns the
helper off.

The helper calls the client's own functions: `gameui.RegisterForUpdate` for the periodic
update, `communicator.OnProcessChat` for chat, `UI_DISPLAY_CHAT_MESSAGE` to read the
server's answers, the movement manager's `TrackMoveToPosition` / `TrackEntityMoveNextTo`
(click-to-move) and the conversation window's button handlers.

## Tools

- `tools/quest_helper.sh`: sends quest helper commands and shows its state file.
- `tools/pyo24dis.py`: disassembles the client's Python 2.4 `.pyo` files
  (`trpython.zip`, `data/game.zip`) on Python 3, without running them.

## Rules for code in this repo

- Python 2.4 syntax only: no `with`, no `x if c else y`, no `except X as e`.
- A mod step must never stop the game from starting: guard it and log the error.
