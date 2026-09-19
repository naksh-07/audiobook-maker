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
- **Python 3.14 Regex Gotcha:** Do NOT use inline flags `(?im)` inside grouped patterns `(|)`; pass `flags=re.IGNORECASE | re.MULTILINE` explicitly.
- **StyleTTS2 / Kokoro Chunking:** Text strings > 220 chars return HTTP 500 on GPU; auto-split on punctuation `(?<=[।\.?!])\s+` and stitch with FFmpeg.
- **M4B Chapter Injection:** Inject `FFMETADATA1` with millisecond timestamps `TIMEBASE=1/1000` via `-map_metadata 1` and `-c copy`.


