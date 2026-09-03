#!/bin/sh
# Record one compatibility row inside a Linux container.
#
#     ci/compat_linux.sh IMAGE LABEL OUTDIR [checkout|pypi] [SHELL]
#
# Pulls the image, installs Python, git and sudo the way that distribution
# does, makes an ordinary user with passwordless sudo -- the matrix is about a
# person's shell, and root is never told "permission denied" -- installs The
# Bleep into a virtualenv of that user's, and runs ci/compat_matrix.py as them.
# The row lands in OUTDIR/LABEL.json. The checkout is mounted read-only and
# copied before installing, so the container cannot write into it.
set -eu

image=$1
label=$2
outdir=$3
source=${4:-checkout}
shell=${5:-}
here=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$outdir"

docker pull -q "$image" >/dev/null
docker run -i --rm \
    -e LABEL="$label" -e SOURCE="$source" -e SHELL_WANTED="$shell" \
    -v "$here:/src:ro" -v "$outdir:/out" \
    "$image" sh -s <<'INSIDE'
set -eu
. /etc/os-release
# The shell the row is for, as the distribution packages it. Debian's ksh93
# is the `ksh93u+m` package and its binary is `ksh93`.
extra=''
case "$SHELL_WANTED" in
    ksh93) extra='ksh93u+m' ;;
    '') ;;
    *) extra="$SHELL_WANTED" ;;
esac
case "${ID_LIKE:-} $ID" in
    *debian*|*ubuntu*)
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq >/dev/null
        apt-get install -y -qq --no-install-recommends \
            python3 python3-venv python3-pip git sudo ca-certificates $extra \
            >/dev/null ;;
    *fedora*|*rhel*|*centos*)
        dnf install -y -q python3 python3-pip git sudo >/dev/null ;;
    *arch*)
        pacman -Sy --noconfirm --quiet python git sudo >/dev/null ;;
    *suse*)
        zypper --non-interactive --quiet --gpg-auto-import-keys install -y \
            python3 python3-pip git sudo >/dev/null ;;
    *alpine*)
        apk add --no-cache -q python3 py3-pip git sudo ;;
    *void*)
        xbps-install -Sy python3 git sudo shadow util-linux bash >/dev/null ;;
    *)
        echo "compat_linux.sh: do not know how to set up $ID" >&2; exit 2 ;;
esac

if command -v useradd >/dev/null; then
    useradd -m bleeper
else
    adduser -D bleeper
fi
mkdir -p /etc/sudoers.d
echo 'bleeper ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/bleeper
chmod 0440 /etc/sudoers.d/bleeper

cp -r /src /tmp/src
chown -R bleeper /tmp/src /out
su bleeper -s /bin/sh -c \
    "sh /tmp/src/ci/compat_unix.sh '$LABEL' /tmp/src /out '$SOURCE' '$SHELL_WANTED'"
INSIDE
