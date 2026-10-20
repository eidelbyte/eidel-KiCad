#!/bin/sh
# Run every test with KiCad's Python (KICAD_PYTHON overrides its path).
KPY=${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3}
cd "$(dirname "$0")/.." || exit 1
for t in tests/test_core.py tests/test_kicad.py tests/test_bambu.py; do
	echo "== $t"
	"$KPY" -I "$t" || exit 1
done
