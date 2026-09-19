# Active Context: Kokoro & Goonj-1-82M TTS Testing Suite

## Live Sprint State
- **Project Goal:** Client & test harness for Kokoro & Goonj-1-82M TTS hosted on PC Workstation (RTX 4050 GPU).
- **Current Phase:** Connected & Operational. Laptop server active at `http://10.236.21.128:8880`.
- **Client Runner:** [kokoro_client.py](file:///root/tts_testing/kokoro_client.py) + Global CLI `kokoro-tts` / `kokoro`.

## Active Blockers & Invariants
- **Hardware Architecture:** Kokoro/Goonj inference runs on PC (RTX 4050 CUDA) to preserve mobile battery/RAM. Termux handles rapid-response client calls, audio conversion, and playback.
- **Integration Points:** Direct MP3 conversion (FFmpeg 192k), studio mastering (SOXR sinc + EBU R128), and audio sync to `/storage/emulated/0/Documents/Termux/Audio/`.

## Recent Milestones
- [x] Connected to PC speech server at `http://10.236.21.128:8880` (Latency: ~40ms).
- [x] Configured `.env` with default voice `hi_meera` and fallback voices.
- [x] Upgraded [kokoro_client.py](file:///root/tts_testing/kokoro_client.py) with `/health`, `/voices`, shorthand synthesis, and MP3 conversion.
- [x] Created global CLI symlinks (`/usr/local/bin/kokoro-tts`, `/usr/local/bin/kokoro`).
- [x] Registered `kokoro-tts` MCP server and created `kokoro-tts` skill.
- [x] Verified synthesis with Hindi and Indian English voices (`hi_meera`, `hi_shivani`, `en_aman`, `en_arjun`).
