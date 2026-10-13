# Packaging

Both are for the release on PyPI and are checked by building them, not by
reading them: the PKGBUILD with `makepkg` in `archlinux:latest`, the formula
with `brew install --build-from-source` and `brew test` in
`homebrew/brew:latest`, each then correcting `ehco hi`.

## AUR

    git clone ssh://aur@aur.archlinux.org/thebleep.git aur && cd aur
    cp ../packaging/aur/PKGBUILD . && makepkg --printsrcinfo > .SRCINFO
    git add PKGBUILD .SRCINFO && git commit -m 'thebleep <version>' && git push

## Homebrew

A tap is a repository called `homebrew-<name>`: `stamparm/homebrew-thebleep`
with this file at `Formula/thebleep.rb` is installed as

    brew install stamparm/thebleep/thebleep

## A new release

`pkgver` and the sdist's `sha256` in the PKGBUILD, `url` and `sha256` in the
formula -- PyPI's JSON (`https://pypi.org/pypi/thebleep/json`) has both. The
dependencies' resources only change when `psutil` or `pyte` do.
