#!/bin/sh
#
# Installs The Bleep.
#
#   curl -fsSL https://raw.githubusercontent.com/stamparm/thebleep/master/install.sh | sh
#
# It picks whichever of uv, pipx or pip you already have, installs The Bleep
# into its own place, and then prints the one line you need to add to your
# shell's startup file. It does not use sudo, and it does not edit any file of
# yours -- the last step is yours to run.
#
# Knobs, if you want them:
#
#   THEBLEEP_INSTALLER=uv|pipx|pip   force the installer
#   THEBLEEP_INSTALL_FROM=pypi|git   force where the package comes from;
#                                    or anything else your installer
#                                    understands, such as a fork's URL or a
#                                    local checkout
#   THEBLEEP_ALIAS=name              the alias to suggest (default: bleep)
#   --dry-run                        print the command instead of running it

set -eu

REPO="https://github.com/stamparm/thebleep"
PACKAGE="thebleep"
ALIAS="${THEBLEEP_ALIAS:-bleep}"
DRY_RUN=""

for argument in "$@"; do
    case "$argument" in
        --dry-run) DRY_RUN="yes" ;;
        -h|--help)
            awk 'NR > 2 && /^#/ { sub(/^# ?/, ""); print; next }
                 NR > 2 { exit }' "$0"
            exit 0
            ;;
        *) echo "install.sh: unknown option $argument" >&2; exit 2 ;;
    esac
done

say() { printf '%s\n' "$*"; }
fail() { printf 'install.sh: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

# -- what we are working with -------------------------------------------------

python=""
for candidate in python3 python; do
    if have "$candidate" && "$candidate" -c 'import sys; sys.exit(sys.version_info[:2] < (3, 9))' 2>/dev/null; then
        python="$candidate"
        break
    fi
done

installer="${THEBLEEP_INSTALLER:-}"
if [ -z "$installer" ]; then
    # uv and pipx both keep the package in its own environment, which is what
    # you want for a command line tool; plain pip is the fallback.
    for candidate in uv pipx; do
        if have "$candidate"; then
            installer="$candidate"
            break
        fi
    done
    if [ -z "$installer" ] && [ -n "$python" ]; then
        installer="pip"
    fi
fi

case "$installer" in
    uv|pipx) have "$installer" || fail "$installer is not on your PATH" ;;
    pip)
        [ -n "$python" ] || fail "no python3 3.9 or newer found; install one, \
or install uv (https://docs.astral.sh/uv/) and run this again"
        "$python" -m pip --version >/dev/null 2>&1 \
            || fail "$python has no pip; install python3-pip, or install uv"
        ;;
    "") fail "found none of uv, pipx or python3; install one and run again" ;;
    *) fail "THEBLEEP_INSTALLER must be uv, pipx or pip, not $installer" ;;
esac

# -- where the package comes from ---------------------------------------------

on_pypi() {
    if have curl; then
        curl -fsS -o /dev/null -m 6 "https://pypi.org/simple/$PACKAGE/" \
            2>/dev/null
    elif have wget; then
        wget -q -O /dev/null -T 6 "https://pypi.org/simple/$PACKAGE/" \
            2>/dev/null
    else
        return 0    # no way to ask; assume it is there and let the install say
    fi
}

source_of="${THEBLEEP_INSTALL_FROM:-}"
if [ -z "$source_of" ]; then
    if on_pypi; then
        source_of="pypi"
    else
        source_of="git"
    fi
fi

case "$source_of" in
    pypi) target="$PACKAGE" ;;
    git) target="git+$REPO" ;;
    *) target="$source_of" ;;   # a fork, a branch, or a checkout on disk
esac

# -- do it --------------------------------------------------------------------

case "$installer" in
    uv) set -- uv tool install --force "$target" ;;
    pipx) set -- pipx install --force "$target" ;;
    pip)
        # `--user` is what you want, except inside a virtual environment,
        # where pip refuses it and installing into the environment is the
        # point of being in one.
        if "$python" -c 'import sys; sys.exit(sys.prefix != sys.base_prefix)' \
                2>/dev/null; then
            set -- "$python" -m pip install --user --upgrade "$target"
        else
            set -- "$python" -m pip install --upgrade "$target"
        fi
        ;;
esac

say "The Bleep"
if [ -n "$python" ]; then
    say "  python     $("$python" -V 2>&1 | cut -d' ' -f2)"
fi
say "  installer  $installer"
say "  package    $target"
say ""

if [ -n "$DRY_RUN" ]; then
    say "would run: $*"
    exit 0
fi

if ! "$@"; then
    say ""
    say "install.sh: that did not work. Usually it is one of these:"
    if [ "$source_of" = "pypi" ]; then
        say "  - The Bleep is not on PyPI yet, so install it from the"
        say "    repository:  THEBLEEP_INSTALL_FROM=git sh install.sh"
    fi
    if [ "$installer" = "pip" ]; then
        say "  - your distribution looks after its own Python packages and"
        say "    will not let pip write there (PEP 668). Install pipx or uv"
        say "    and run this again, and it will be used instead."
    fi
    say "  - the full error is above."
    exit 1
fi

# -- and tell them what to do next --------------------------------------------

say ""
if have "$PACKAGE"; then
    say "Installed: $(command -v "$PACKAGE")"
else
    for directory in "${UV_TOOL_BIN_DIR:-}" "${PIPX_BIN_DIR:-}" \
                     "$HOME/.local/bin"; do
        [ -n "$directory" ] || continue
        if [ -x "$directory/$PACKAGE" ]; then
            say "Installed: $directory/$PACKAGE"
            say ""
            say "That directory is not on your PATH yet. Add it:"
            say "    export PATH=\"$directory:\$PATH\""
            break
        fi
    done
fi

# The loader defines the alias the first time you use it, so opening a shell
# costs nothing at all.
# The tildes below are deliberate: this is a line for you to read and type,
# and your shell is the one that will expand it.
# shellcheck disable=SC2088
case "$(basename "${SHELL:-sh}")" in
    fish) rc="~/.config/fish/config.fish" ;;
    zsh) rc="~/.zshrc" ;;
    tcsh|csh) rc="~/.cshrc" ;;
    *) rc="~/.bashrc" ;;
esac

say ""
say "One more line, and it is yours to run:"
say ""
say "    $PACKAGE --alias-loader $ALIAS >> $rc"
say ""
say "Then open a new shell, make a mistake, and type $ALIAS."
