#!/bin/sh
# Record one compatibility row as the current, ordinary user.
#
#     ci/compat_unix.sh LABEL SRC OUTDIR [checkout|pypi] [SHELL]
#
# A virtualenv in the home directory, The Bleep installed into it from the
# checkout at SRC or from PyPI, and ci/compat_matrix.py run from it. This is
# the part every Unix-like platform shares; making the user and installing
# Python is the caller's, because that is where the platforms differ.
set -eu

label=$1
src=$2
outdir=$3
source=${4:-checkout}
shell=${5:-}
venv=$HOME/thebleep-compat-venv

python3 -m venv "$venv"
"$venv/bin/pip" install -q --disable-pip-version-check -U pip
if [ "$source" = pypi ]; then
    "$venv/bin/pip" install -q --disable-pip-version-check thebleep
else
    "$venv/bin/pip" install -q --disable-pip-version-check "$src"
fi
mkdir -p "$outdir"
"$venv/bin/python" "$src/ci/compat_matrix.py" record \
    --label "$label" --output "$outdir/$label.json" \
    --recorded-by ci --source "$source" ${shell:+--shell "$shell"}
