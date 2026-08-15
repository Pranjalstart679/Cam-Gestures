# Task plan: voice-activated gesture control

Goal: run from VS Code (or later as an app), stay idle until a wake word, then control the screen with hand gestures. The physical mouse stays optional for most navigation.

See also [README.md](README.md).

## Target flow

```text
python main.py --enable-voice --hands-free
        ↓
LISTENING  (mic on, camera off)
        ↓  say "activate" or press Space
ACTIVE     (camera on, gestures move/click/scroll/drag)
        ↓  say "stop" or press Esc
LISTENING
        ↓  say "quit" or press Q
exit
```

## Status

| # | Phase | Status |
|---|--------|--------|
| 1–9 | Webcam, landmarks, cursor, pinch, scroll, fist drag, state manager, JSON, overlay | Complete |
| 10 | Idle / active session lifecycle + `--hands-free` | Complete |
| 11 | Voice wake / stop (offline Vosk) | Complete (model download still required on each machine) |
| 12 | Extra gestures (right-click, double-click) | Not started |
| 13 | VS Code launch config and docs polish | Complete |
| 14 | PySide6 settings GUI and profiles | Not started |

## Phase 10 — Session lifecycle

- [x] Document this plan in-repo
- [x] `SessionController`: `LISTENING` ↔ `ACTIVE` without restarting the process
- [x] Camera and hand tracker created only while `ACTIVE`, released on deactivate
- [x] `--hands-free` implies `--enable-cursor` and `--enable-gesture-actions`
- [x] Keyboard fallback: Space activates, Esc deactivates (voice mode) or quits, Q always quits
- [x] Auto `mouse_up()` if the hand is lost while dragging

## Phase 11 — Voice activation

- [x] `voice/commands.py` phrase matcher (testable, no hardware)
- [x] `voice/listener.py` background mic thread using Vosk + sounddevice
- [x] Optional `voice` section in `config/gestures.json`
- [x] `--enable-voice` / `--no-voice` CLI overrides
- [x] Wake phrase starts camera; stop phrase releases mouse and returns to listening
- [x] Model path not committed; download documented

## Phase 12 — Extra gestures

- [ ] Right-click gesture
- [ ] Double-click (two quick pinches)
- [ ] Open-palm hold as emergency deactivate (optional)

## Phase 13 — Developer experience

- [x] `.vscode/launch.json` for preview vs hands-free vs voice
- [x] README: mic permissions, Vosk model download, one-command run
- [x] Clean stale “Phase 5 / reserved for later” comments

## Phase 14 — Later

- [ ] JSON profiles (`--profile precise`)
- [ ] PySide6 tray / settings GUI
- [ ] Improved / customizable gesture recognition

Out of scope for this version: cloud APIs, LLM integration, automatic keyboard shortcuts, voice typing.

## Success criteria

1. `python main.py --enable-voice --hands-free` starts listening with the camera off.
2. Saying **activate** (or pressing Space) turns on the camera and gesture control.
3. Point / pinch / two-finger / fist control the desktop without touching the mouse.
4. Saying **stop** (or Esc in voice mode) turns the camera off and returns to listening.
5. The physical mouse remains available as a backup; typing still uses the keyboard.
