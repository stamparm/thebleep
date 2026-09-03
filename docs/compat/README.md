# Where it works

Each row is one machine, one shell. The broken command in each
column was typed into that shell by `ci/compat_matrix.py`, what the
shell printed was handed to the correction engine, and the first
suggestion is what the cell says. Nothing suggested was run.

Rows marked *ci* were recorded by the weekly
[compatibility workflow](../../.github/workflows/compat-matrix.yml)
on a fresh runner, container or virtual machine; rows marked *hand*
by a person running the same script on a machine CI cannot reach.

## Debian 13

`debian-13` · bash 5.2.37(1)-release · Python 3.13.5 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 42 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `apt isntall vim` | ✓ `apt install vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## Ubuntu 24.04.4 LTS

`ubuntu-24.04` · bash 5.2.21(1)-release · Python 3.12.3 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 38 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `apt isntall vim` | ✓ `apt install vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## Ubuntu 24.04.4 LTS · by hand

`ubuntu-desktop` · bash 5.2.21(1)-release · Python 3.12.3 · The Bleep 4.0.4 · recorded 2026-09-03 by hand from checkout

Command-only correction in 45 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `apt isntall vim` | ✓ `apt install vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` | `docker pss` | ✓ `docker ps` |
| `npm run bulid` | `npm run bulid` | ✓ `npm run build` |
| `cargo biuld` | `cargo biuld` | ✓ `cargo build` |

## Ubuntu 24.04.4 LTS · GitHub runner

`ubuntu-runner` · bash 5.2.21(1)-release · Python 3.12.14 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 65 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `apt isntall vim` | ✓ `apt install vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` | `docker pss` | ✓ `docker ps` |
| `npm run bulid` | `npm run bulid` | ✓ `npm run build` |
| `cargo biuld` |  | — cargo has no toolchain here |

## Fedora Linux 44

`fedora` · bash 5.3.9(1)-release · Python 3.14.7 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 78 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `dnf isntall vim` | ✓ `dnf install vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## AlmaLinux 9.8

`almalinux-9` · bash 5.1.8(1)-release · Python 3.9.25 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 63 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `dnf isntall vim` | ✓ `dnf install vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## Arch Linux

`arch` · bash 5.3.15(1)-release · Python 3.14.7 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 84 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `pacman -s vim` | ✓ `pacman -S vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## openSUSE Tumbleweed

`opensuse-tumbleweed` · bash 5.3.15(1)-release · Python 3.13.14 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 68 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `zypper isntall vim` | ✓ `zypper install vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## Alpine Linux v3.24 (sh)

`alpine` · sh sh · Python 3.14.7 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 117 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `apk isntall vim` | ✓ `apk add vim` |
| permission denied | `cat /etc/shadow` | ✓ `sudo cat /etc/shadow` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## Void Linux

`void` · bash 5.3.0(1)-release · Python 3.14.7 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 82 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `xbps-instal -S vim` | ✓ `xbps-install -S vim` |
| permission denied | `cat /etc/sudoers` | ✓ `sudo cat /etc/sudoers` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## FreeBSD 14.3-RELEASE (sh)

`freebsd` · sh sh · Python 3.12.14 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 88 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `pkg isntall vim` | ✓ `pkg install vim` |
| permission denied | `cat /etc/master.passwd` | ✓ `sudo cat /etc/master.passwd` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## OpenBSD 7.9 (sh)

`openbsd` · sh sh · Python 3.13.14 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 230 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `pkg_ad vim` | ✓ `pkg_add vim` |
| permission denied | `cat /etc/master.passwd` | ✓ `sudo cat /etc/master.passwd` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## NetBSD 11.0

`netbsd` · bash 5.3.15(1)-release · Python 3.12.13 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 140 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `pkg_ad vim` | ✓ `pkg_add vim` |
| permission denied | `cat /etc/master.passwd` | ✓ `sudo cat /etc/master.passwd` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` |  | — npm is not installed |
| `cargo biuld` |  | — cargo is not installed |

## macOS 26.5.2

`macos-arm64` · zsh 5.9 · Python 3.12.10 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 88 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `brew isntall wget` | ✓ `brew install wget` |
| permission denied | `cat /etc/master.passwd` | ✓ `sudo cat /etc/master.passwd` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` | `npm run bulid` | ✓ `npm run build` |
| `cargo biuld` |  | — cargo has no toolchain here |

## macOS 15.7.9

`macos-intel` · zsh 5.9 · Python 3.12.10 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 163 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `sl -la` | ✓ `ls -la` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `brew isntall wget` | ✓ `brew install wget` |
| permission denied | `cat /etc/master.passwd` | ✓ `sudo cat /etc/master.passwd` |
| `mkdir a/b/c` | `mkdir a/b/c` | ✓ `mkdir -p a/b/c` |
| `./script.sh` without +x | `./script.sh` | ✓ `chmod +x script.sh && ./script.sh` |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory | `rm emptydir` | ✓ `rm -r emptydir` |
| installed, not on PATH | `hellotool` | ✓ `~/.local/bin/hellotool` |
| `cd..` | `cd..` | ✓ `cd ..` |
| `docker pss` |  | — docker is not installed |
| `npm run bulid` | `npm run bulid` | ✓ `npm run build` |
| `cargo biuld` |  | — cargo has no toolchain here |

## Windows Server 2025 (PowerShell 5.1)

`windows-powershell` · powershell 5.1.26100.33296 · Python 3.12.10 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 153 ms, median of 5 runs, Python start included.

| slip | typed | answer |
|---|---|---|
| `gti status` | `gti status` | ✓ `git status` |
| `git psuh` | `git psuh` | ✓ `git push` |
| `sl -la` | `lss` | ✓ `ls` |
| `git status --shrot` | `git status --shrot` | ✓ `git status --short` |
| `apt isntall`, `dnf`, `apk`… | `winget isntall vim` | ✓ `winget install vim` |
| permission denied |  | — no sudo on Windows |
| `mkdir a/b/c` |  | — PowerShell mkdir creates parents by itself |
| `./script.sh` without +x |  | — no execute bit on Windows |
| `cd Documnets` | `cd Documnets` | ✓ `cd Documents` |
| `rm` a directory |  | — PowerShell asks about a directory instead |
| installed, not on PATH | `hellotool` | ✓ `'~\.local\bin\hellotool.cmd'` |
| `cd..` |  | — PowerShell accepts `cd..` as it is |
| `docker pss` | `docker pss` | ✓ `docker ps` |
| `npm run bulid` | `npm run bulid` | ✓ `npm run build` |
| `cargo biuld` |  | — cargo has no toolchain here |
