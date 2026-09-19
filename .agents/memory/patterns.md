# Patterns & Operational Gotchas

## Environment & Audio Gotchas
- **Mobile Audio:** Termux playback uses `termux-media-player play <file.wav>` when synced to shared storage `/storage/emulated/0/Documents/Termux/Audio/`.
- **Audio Mastering:** `audio-master` CLI is available at `/usr/local/bin/audio-master` for 48kHz SOXR sinc resampling and EBU R128 loudness normalization.
- **Client Runner:** `python3 kokoro_client.py set-url <LAPTOP_IP:PORT>` writes to `.env` and immediately tests latency.
