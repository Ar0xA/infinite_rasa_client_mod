#!/usr/bin/env bash
# Build native/clientmod_native.c into mod/clientmod_native.pyd
# (32-bit x86 Windows DLL, like tabula_rasa.exe and python24.dll).
# Needs Zig (https://ziglang.org): either `zig` on PATH, or ZIG="python -m ziglang" from
# `pip install ziglang`. Any i686 MinGW gcc works too: CC=i686-w64-mingw32-gcc.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/../mod/clientmod_native.pyd"
if [ -n "${CC:-}" ]; then
    $CC -O2 -shared -s -o "$OUT" "$HERE/clientmod_native.c" -luser32 -lkernel32
else
    ${ZIG:-zig} cc -target x86-windows-gnu -O2 -shared -s -o "$OUT" "$HERE/clientmod_native.c" -luser32 -lkernel32
fi
rm -f "${OUT%.pyd}.pdb" "${OUT%.pyd}.lib"
echo "Built $OUT"
