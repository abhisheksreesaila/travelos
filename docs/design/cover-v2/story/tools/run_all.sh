#!/bin/sh
# Generate the 2 character sheets, then the 13 panels. Needs GEMINI_KEY_FILE (path to the key file).
set -e
cd "$(dirname "$0")/.."
: "${GEMINI_KEY_FILE:?set GEMINI_KEY_FILE to the key file path}"
pixi run python tools/gen.py sheet-maya-sam
pixi run python tools/gen.py sheet-rosa-tomas
for n in 01 02 03 04 05 06 07 08 09 10 11 12 13; do pixi run python tools/gen.py "$n"; done
