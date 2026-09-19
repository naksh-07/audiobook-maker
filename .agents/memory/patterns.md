# Patterns & Operational Gotchas

## Environment & Audio Gotchas
- **Mobile Audio:** Termux playback uses `termux-media-player play <file.mp3>` when synced to shared storage `/storage/emulated/0/Documents/Termux/Audio/`.
- **Audio Mastering:** Direct `--master` flag or `/usr/local/bin/audio-master` applies 48kHz SOXR sinc resampling and EBU R128 loudness normalization.
- **Client Commands:**
  - `kokoro-tts status` checks health & GPU latency.
  - `kokoro-tts voices` lists 15 Goonj voices (Hindi & Indian English).
  - `kokoro-tts speak "<text>" --voice <id> [-f mp3|wav] [--master] [--play]` synthesizes speech.
  - `kokoro-tts set-url <url>` updates PC server URL in `.env`.
- **PC Server Port:** Default Kokoro/Goonj FastAPI runs on port 8880 (`http://10.236.21.128:8880`).

