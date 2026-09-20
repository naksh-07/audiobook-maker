# Ambient Music & Soundscape Stems Library

Place any royalty-free background loop files in this folder matching the mood name:

- `peaceful.mp3` (or `.wav`, `.m4a`, `.flac`)
- `mysterious.mp3`
- `tense.mp3`
- `emotional.mp3`
- `epic.mp3`
- `default.mp3`

### How It Works:
1. When `audiobook-maker bgm <book>` runs, Gemini detects the mood of each scene.
2. If a matching file (e.g. `mysterious.mp3`) is present here, FFmpeg loops and master-resamples it automatically.
3. If no file is present, FFmpeg automatically synthesizes an organic procedural ambient drone bed in real-time.
4. In either case, **dynamic sidechain ducking (-16dB)** is automatically applied during character speech.
5. **Cost:** 100% Free, Zero API tokens used!
