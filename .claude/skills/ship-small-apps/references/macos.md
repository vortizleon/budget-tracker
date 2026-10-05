# macOS delivery notes

Facts below were hit in practice unless marked *(not verified here)*.

## Getting the app onto a machine
- Browser and AirDrop downloads get the `com.apple.quarantine` attribute; unsigned `.command` scripts are then
  blocked ("unidentified developer"). `curl`/`tar` downloads don't get it. Prefer a pasted Terminal command:
  `curl -fsSL <tarball-url> | tar -xz -C ~/Documents` (use `-f` so a failed download stops instead of extracting junk).
- Make the command safe to run twice (skip the download if the folder exists).
- Have the installer clear the flag on its own folder: `xattr -dr com.apple.quarantine "$DIR"` (own files, no sudo).
- A signed + notarized app avoids all of this but costs an Apple Developer account *(not done here)*.

## Prerequisites
- Don't depend on Homebrew, git or the system Python. On a fresh Mac `git` and `python3` are stubs that trigger the
  Xcode Command Line Tools install prompt, which may need a macOS update.
- `uv` is one downloaded binary: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then `uv venv --python 3.13 venv`
  and `uv pip install --python venv/bin/python -r requirements.txt`. It downloads a managed Python and prebuilt wheels,
  so nothing compiles. Installs to `~/.local/bin`; put the app's command symlink there too and add that dir to `~/.zprofile`.
- Check prebuilt wheels exist for both Apple Silicon and Intel for every compiled dependency (e.g. lxml).

## Scripts people double-click
- `.command` files open Terminal. Make them work with stdin closed: a trailing `read -n 1` returns non-zero with no TTY,
  so write `read ... || true` and finish with `exit 0`.
- Resolve the script's own folder (follow symlinks) and `cd` there; don't assume the working directory.
- Give people a second double-click launcher (start the server, open the browser) so they never need Terminal after install.
- Desktop shortcuts can trigger a "Terminal wants to access Desktop" prompt; treat creating one as optional.

## What CI can and cannot tell you
- GitHub's `macos-latest` runner (Apple Silicon) can run the installer end to end - worth doing, it found a real bug.
- It already has Xcode tools and Homebrew, so it cannot reproduce "fresh Mac" prerequisite failures, Gatekeeper, or old macOS.
- A Linux cloud sandbox cannot run macOS at all. Say so; rely on the runner.
- Cheapest real check: a new **standard user account** on a Mac (fresh shell and PATH, no venv), installing from a
  browser-downloaded file. About five minutes; only when installer/download files change.

## Other platforms *(not verified here)*
- Windows: downloaded files carry a "Mark of the Web" and SmartScreen warns on unsigned executables; `winget`/`scoop` or a
  PowerShell one-liner is the analogue of the Terminal command; use `venv\Scripts\python`, not `venv/bin/python`.
- Linux: usually simplest; check the distro's system Python and `lsof` equivalents.
- Things that were macOS-only in this project: `lsof`, `open -na "Google Chrome"`, the Darwin check in the installer.
