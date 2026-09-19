# Active Context: Kokoro TTS Testing Suite

## Live Sprint State
- **Project Goal:** Client & test harness for Kokoro TTS hosted on PC/Laptop Workstation.
- **Current Phase:** Environment cleaned & scaffolded. Waiting for laptop server address/port.
- **Client Runner:** `kokoro_client.py` (Zero pip dependencies, pure Python 3 stdlib).

## Active Blockers & Invariants
- **Hardware Architecture:** Kokoro TTS inference runs on Laptop/PC Workstation to preserve mobile battery/RAM. Termux acts as rapid-response client and audio player.
- **Integration Points:** Audio outputs to `/storage/emulated/0/Documents/Termux/Audio/`, with optional `audio-master` and `termux-media-player` playback.

## Recent Milestones
- [x] Initialized Git repo & `.agents/memory/` bridge.
- [x] Purged all heavy local packages/caches from mobile PRoot.
- [x] Implemented lean zero-dependency client [kokoro_client.py](file:///root/tts_testing/kokoro_client.py).
- [x] Created `.env` and `.env.example` with `set-url` command helper.
