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

Command-only correction in 35 ms, median of 5 runs, Python start included.

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

## Fedora Linux 44

`fedora` · bash 5.3.9(1)-release · Python 3.14.7 · The Bleep 4.0.5 · recorded 2026-09-03 by ci from checkout

Command-only correction in 53 ms, median of 5 runs, Python start included.

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

Command-only correction in 42 ms, median of 5 runs, Python start included.

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

Command-only correction in 54 ms, median of 5 runs, Python start included.

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

Command-only correction in 51 ms, median of 5 runs, Python start included.

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

Command-only correction in 80 ms, median of 5 runs, Python start included.

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

Command-only correction in 58 ms, median of 5 runs, Python start included.

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
