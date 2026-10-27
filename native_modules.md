# Native modules (DLLs)

The loader can run native code in the game process: it imports `.pyd` files from the
mod folder (`mods/infinite_rasa`, or `python_nca_internal` in the side-load way). A `.pyd` is a normal Windows DLL that Python loads as a module.
Tested in the client on 2026-10-20 under Wine 11.0 (Proton): the example module loaded,
logged from native code, answered a call from Python and changed the window title.

Off by default. To use it, build the example and enable it (see below).

## Why it works

- `tabula_rasa.exe` embeds Python 2.4 (`python24.dll`), and that Python can import C
  extension modules: `python24.dll` contains `load_dynamic` and the `.pyd` suffix.
- The mod folder is on `sys.path` (a `[Data]` path in `tabula_rasa.cfg`, or
  `python_nca_internal`, the first entry), so `import name` finds `name.pyd` in it.
- Importing `name.pyd` calls its exported function `initname()`. From there the DLL can do
  anything a DLL can: start threads, call Windows APIs, `LoadLibrary` other DLLs, hook
  functions.

Requirements for a `.pyd`:

- **32-bit x86** (`tabula_rasa.exe` and `python24.dll` are `PE32 ... Intel 80386`).
- **File name** `<module>.pyd` with an export `init<module>` (cdecl, no arguments). A file
  named `.dll` is not found by `import`.
- **Python 2.4 C API only** if it talks to Python. Python 2.4 itself uses `MSVCR71.dll`;
  do not pass C runtime objects (`FILE*`, `malloc`ed memory) between the DLL and Python.
- Only Windows APIs that Wine implements, if it must run under Wine/Proton.

## How the loader loads it

`clientmod_loader.load_native_modules()` runs when the mod starts: when the client first
imports the game tables (mod folder way, right after `InitApp`), or at the start of
`boot()` (side-load way). Both are before the game sets up its UI. For each name in `clientmod_data.NATIVE_MODULES` it does
`__import__(name)`, calls `module.info()` if the module has it, and logs the result:

```
native module clientmod_native loaded: pid 308, exe S:\...\tabula_rasa.exe, Wine 11.0
native module foo not loaded: No module named foo
```

The import is in a `try`/`except`: a missing or broken `.pyd` does not stop the game. A
crash inside native code does, though; Python cannot catch that.

## The example: `native/clientmod_native.c`

On import it:

1. writes `native: pid ..., exe ..., Wine <version>` to `client_mod.log` (the Wine version
   comes from `ntdll.wine_get_version`; on real Windows it says `none (not Wine)`);
2. starts a thread that adds ` [Infinite Rasa mod]` to the game window title. It checks
   every 2 seconds, because the game creates more than one window and sets its title
   itself; the first 10 changes are logged (`native: window ... title set to "..."`);
3. registers the module with one function, `clientmod_native.info()`, which returns the
   same text as step 1.

It uses no Python headers and no import library: `Py_InitModule4` and
`PyString_FromString` are looked up in `python24.dll` with `GetProcAddress`. Only kernel32
and user32 are called, no C runtime functions.

## Build and enable

1. Get a compiler for 32-bit Windows. Either:
   - Zig, without root: `uv venv /tmp/zigenv && VIRTUAL_ENV=/tmp/zigenv uv pip install ziglang`
     (or `pip install ziglang`), or
   - MinGW: `sudo apt install gcc-mingw-w64-i686`.
2. Build:
   ```sh
   ZIG="/tmp/zigenv/bin/python -m ziglang" native/build.sh   # Zig
   CC=i686-w64-mingw32-gcc native/build.sh                    # or MinGW
   ```
   This writes `mod/clientmod_native.pyd` (not in git: `*.pyd` is ignored).
3. In `mod/clientmod_data.py`, remove the `#` in front of
   `'clientmod_native'` in `NATIVE_MODULES`.
4. `./install.sh "<game folder>"` and start the game. The window title ends with
   `[Infinite Rasa mod]`; `client_mod.log` has the `native` lines above.

`install.sh` copies `*.pyd` files too. It deletes the old file first: a running game has
the old DLL mapped, and overwriting it in place could crash the game. A new `.pyd` is used
only after a game restart.

Zig links the Universal C runtime (`api-ms-win-crt-*`). Wine and Windows 10+ have it.

## Writing your own

Start from `native/clientmod_native.c`: rename the module (file name, `init<name>`, the
name passed to `Py_InitModule4`), keep `initname` short and do lengthy work in a thread,
add the name to `NATIVE_MODULES`. A module that only loads another DLL can skip Python
entirely: `LoadLibraryA("other.dll")` in `initname`, then call `Py_InitModule4` so the
import succeeds.

Native code runs with the full rights of the game process. Only load DLLs you built or
trust.
