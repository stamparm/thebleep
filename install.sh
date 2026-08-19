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
#   THEBLEEP_INSTALL_FROM=git        install from the repository instead of
#                                    from PyPI; or give anything else your
#                                    installer understands, such as a fork's
#                                    URL or a local checkout
#   THEBLEEP_ALIAS=name              the alias to suggest (default: bleep)
#   --dry-run                        print the command instead of running it

set -eu

REPO="https://github.com/stamparm/thebleep"
PACKAGE="thebleep"
ALIAS="${THEBLEEP_ALIAS:-bleep}"
DRY_RUN=""

# The alias name ends up in a line we tell people to put in a startup file, so
# it has to be a name and not shell code. A letter or underscore, then letters,
# digits, underscores or hyphens.
case "$ALIAS" in
    *[!A-Za-z0-9_-]* | [0-9-]* | "")
        echo "install.sh: '$ALIAS' cannot be the name of the alias." >&2
        echo "A name is a letter or underscore followed by letters, digits," >&2
        echo "underscores or hyphens. Anything else would be shell code in" >&2
        echo "your startup file." >&2
        exit 2
        ;;
esac

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
    "") fail "found no uv, no pipx, and no python3 3.9 or newer. Install one \
of them and run this again -- uv is the smallest thing to install: \
https://docs.astral.sh/uv/" ;;
    *) fail "THEBLEEP_INSTALLER must be uv, pipx or pip, not $installer" ;;
esac

# -- where the package comes from ---------------------------------------------

# PyPI, and only PyPI, unless you say otherwise.
#
# This used to probe PyPI and fall back to installing from git when the probe
# failed. That is convenient exactly once -- before the first release -- and
# wrong afterwards: an outage, a proxy, or a captive portal would quietly turn
# "install the released version" into "install whatever is on master", which is
# not a decision an installer gets to make on somebody's behalf. If PyPI cannot
# be reached the install fails and says so, and `THEBLEEP_INSTALL_FROM=git` is
# there for anyone who means it.
source_of="${THEBLEEP_INSTALL_FROM:-pypi}"

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

# `--dry-run` prints the whole plan, including the line at the end, rather than
# stopping here: the line at the end is the part worth looking at first.
if [ -n "$DRY_RUN" ]; then
    say "would run: $*"
else
    if ! "$@"; then
        say ""
        say "install.sh: that did not work. Usually it is one of these:"
        if [ "$source_of" = "pypi" ]; then
            say "  - PyPI could not be reached. Try again, or install straight"
            say "    from the repository if you mean to:"
            say "        THEBLEEP_INSTALL_FROM=git sh install.sh"
        fi
        if [ "$installer" = "pip" ]; then
            say "  - your distribution looks after its own Python packages and"
            say "    will not let pip write there (PEP 668). Install pipx or uv"
            say "    and run this again, and it will be used instead."
        fi
        say "  - the full error is above."
        exit 1
    fi

    # -- where it landed ------------------------------------------------------

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
    nu) rc="~/.config/nushell/config.nu" ;;
    *) rc="~/.bashrc" ;;
esac

say ""
say "One more line, and it is yours to run:"
say ""
say "    $PACKAGE --alias-loader $ALIAS >> $rc"
say ""
say "Then open a new shell, make a mistake, and type $ALIAS."
