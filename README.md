# ALX 2.0

**A customizable edit-hold, instant-build, and macro-builder tool for Fortnite.**

Dark-blue glass UI, Python + PySide6, open-source, builds to a single
Windows `.exe`.

> **Heads-up.** Automating gameplay violates Fortnite's TOS and anti-cheat
> can detect injected input. Use on an alt account at your own risk — the
> repo author is not responsible for bans.

---

## Features

- **Edit Hold (drag edit).** Hold the edit key → automatic confirm click
  after your chosen settle delay → release on key-up.
- **Instant Builds (B1–B4).** Four extra hold-slots, each mapping a key
  to a piece-place in the same rhythm as edit hold.
- **Custom Macro Builder.** A drag-and-drop block palette for composing
  your own sequences — press key, click, wait, move mouse, scroll, repeat
  loops. Bind a trigger key, done.
- **Post Key.** Auto-press a key after an edit or build (e.g. swap back to
  your weapon when the piece lands).
- **Humanizer.** Normal- or uniform-distribution jitter on settle, hold,
  post-key delay, and microjitter. Optional miss chance. Optional warmup
  slowdown on the first few presses.
- **Fast-Tap Rescue.** A low-level keyboard hook that catches key-ups the
  settle timer would otherwise lose — no more missed edits on quick flicks.
- **Four-tab Qt UI.** CORE / INSTANT BUILDS / BUILDER / HUMANIZE / ADVANCED.
  Dark-blue + black palette, animated glow cards, pill toggles, drop
  shadows, Windows 11 mica backdrop where available.
- **mb4 / mb5 capture.** Focus a key field, physically press the mouse
  button, the field binds it.
- **Import / Export.** Share macros as `.macro.json` files (compatible
  with the [alxstore](#related) community hub).


## Install

### From a release (recommended)

1. Grab the latest `ALX2.0.exe` from the [Releases page][releases].
2. Put it anywhere. Double-click to run.
3. If you want auto-updates, also grab the
   [ALX2.0 Launcher](#auto-updater-alx20-launcher).

### From source

```bash
git clone https://github.com/alx12222/ALX2.0
cd ALX2.0
pip install -r requirements.txt
python main.py
```

Requires Python 3.10+. On first launch ALX will self-install PySide6 into
the interpreter that's running `main.py`, so `pip` is only needed if you
want to install it manually.

[releases]: https://github.com/alx12222/ALX2.0/releases

## Quick start

1. Open ALX, go to **CORE → Edit Hold**.
2. Click **Edit key**, press your in-game edit key (default `F`).
3. Click **Reset key**, press your in-game edit-reset key (default `C`).
4. Set **Settle (ms)** to taste: `80` is balanced, `50` is aggressive.
5. Flip the **Macro** toggle (or hit `F8`) to arm it. The status dot in the
   corner goes blue when it's holding.

### Add an instant build

1. Open **INSTANT BUILDS**.
2. Pick a slot. Click **Key**, press the key you want to use in-game.
3. Click **Enable this slot**.
4. Hold the key in build mode — ALX hits the auto-click for you after the
   settle window.

### Build your own macro

1. Open **BUILDER**, hit **＋ New** on the left.
2. Drag blocks from the right (Press Key, Wait, Click, Repeat…) into the
   sequence in the middle. Or double-click a palette block to append.
3. Select a sequence block to edit its parameters on the right.
4. Pick a **Trigger key** at the top (click the field, press the key/mouse
   button).
5. Flip **Enabled**. Pressing the trigger in-game runs the sequence.

## Hotkeys

| key | action |
|-----|--------|
| `F8` | toggle the macro on/off |
| `F9` | exit |

Both are rebindable in **ADVANCED → Hotkeys**.
## Config

All settings live in `config.json` next to the exe. Deleting it restores
defaults on next launch. The file is human-editable; the app saves on
every change.

Interesting fields:

- `main.selectButton`: `"LButton"` or `"RButton"` — which button ALX uses
  for the auto-click confirm.
- `main.postKey` / `main.postTrigger`: the post-action key and what fires it.
- `humanize.*`: all the randomness knobs.
- `custom_macros`: your BUILDER sequences.
- `systems`: slot 0 is edit hold; 1–4 are the B-slots.

## Related

- **[alxstore][alxstore]** — community hub for sharing configs and
  macros. Anonymous auto-signin, drag-and-drop uploads, live search.

[alxstore]: alxstore.surge.sh

## Auto-updater (ALX2.0 Launcher)

A separate ~5 MB tkinter + urllib launcher that lives next to
`ALX2.0.exe`. On run it:

1. Hits `https://api.github.com/repos/alx12222/ALX2.0/releases/latest`
2. Compares the tag with `launcher.state.json`
3. If newer, downloads the matching asset with a progress bar
4. Launches `ALX2.0.exe` and exits

Fully offline-tolerant — a network failure just starts the installed copy
without blocking the user.

## Troubleshooting

- **"PySide6 not found"** — ALX self-installs it on first launch. If that
  fails, open a terminal and run `py -m pip install PySide6` (use `py`,
  not `python`, on Windows — picks the launcher Python that `main.py`
  actually runs on).
- **Edit hold misses every few presses** — raise **Settle** by 10–20 ms,
  or make sure **Fast-Tap Rescue** is on in ADVANCED.
- **Instant build fires the wrong piece** — check that **Build Binds** on
  the CORE tab match your in-game keybinds.
- **mb4/mb5 not captured** — click directly in the key field first so it
  gets focus, then press the mouse button. Some gaming mice remap XButtons
  at the driver level — turn remapping off for the test.
- **Trigger key seems slow** — turn off Humanizer in that tab, or lower
  `settle_jitter_ms` and `microjitter_ms`.


Built by alx12222. UI inspired by recent glassmorphism trends and whichever
dark-theme dashboards were in my browser history that week.
