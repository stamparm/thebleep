#!/bin/sh
# Builds the benchmark subjects: this working tree, and upstream The Fuck as
# the baseline to beat. Both go into throwaway virtualenvs so a benchmark run
# never depends on what happens to be installed.
#
#   ./bench/setup_subjects.sh [python] [target-dir]
#
# Upstream The Fuck cannot import on Python 3.12 or newer (it needs distutils),
# so a baseline subject is only created when the interpreter can run it.

set -eu

PYTHON="${1:-python3}"
TARGET="${2:-bench/.venvs}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

VERSION="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
BLEEP="$TARGET/bleep-$VERSION"
BLEEP_SRC="$TARGET/bleep-src-$VERSION"
FUCK="$TARGET/fuck-$VERSION"

mkdir -p "$TARGET"

echo "== the bleep, wheel install (what users get) -> $BLEEP"
rm -rf "$BLEEP"
"$PYTHON" -m venv "$BLEEP"
"$BLEEP/bin/pip" install -q --upgrade pip
"$BLEEP/bin/pip" install -q "$ROOT"

echo "== the bleep, source checkout (what contributors run) -> $BLEEP_SRC"
rm -rf "$BLEEP_SRC"
"$PYTHON" -m venv "$BLEEP_SRC"
"$BLEEP_SRC/bin/pip" install -q --upgrade pip
"$BLEEP_SRC/bin/pip" install -q -e "$ROOT"

echo "== upstream the fuck, baseline -> $FUCK"
rm -rf "$FUCK"
"$PYTHON" -m venv "$FUCK"
"$FUCK/bin/pip" install -q --upgrade pip
if "$FUCK/bin/pip" install -q thefuck 2>/dev/null \
        && "$FUCK/bin/python" -c 'import thefuck.entrypoints.main' 2>/dev/null; then
    echo "   ok"
else
    echo "   unavailable on Python $VERSION (needs distutils), skipping baseline"
    rm -rf "$FUCK"
fi

echo
echo "subjects ready:"
echo "  --subject bleep=$BLEEP/bin/thebleep"
echo "  --subject bleep-src=$BLEEP_SRC/bin/thebleep"
[ -d "$FUCK" ] && echo "  --subject fuck=$FUCK/bin/thefuck"
exit 0
