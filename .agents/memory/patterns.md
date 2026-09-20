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
- **FFmpeg Concat Demuxer on Windows:** Paths inside `concat.txt` must use forward slashes `/` (e.g., `file 'C:/path/...'`). Backslashes cause demuxer parse failures.
- **FFmpeg Resampling Engine:** Never force `aresample=resampler=soxr:osr=48000` because non-GPL/essentials Windows builds omit `libsoxr`. Use universal `aresample=osr=48000`.
- **Windows Console Unicode:** Configure `sys.stdout.reconfigure(encoding="utf-8")` to avoid `'charmap' codec can't encode characters` when printing Devanagari text.
- **Gemini Free-Tier Rate Limits:** Keep 5.0-6.0s pacing between TTS synthesis requests to stay safely under RPM quotas.
- **Gemini Safety Blocking on Fantasy Fiction:** Mature combat scenes ("swords", "blood", "kill", "striga") trigger Gemini's default safety filter, returning empty candidates or conversational refusals ("I cannot provide a direct translation..."). Always configure `safetySettings: BLOCK_NONE` across all 4 categories for literary fiction translation.
- **Linguistic Sanitizer Guardrail:** Always validate translation chunks with `validate_and_sanitize_translation()` before caching or saving. Rejects meta-patterns ("Scene Overview", "I cannot", "Would you like...") and enforces a Devanagari character purity ratio.
- **Screenplay Segment Sanitization:** In `script_builder.py`, `sanitize_screenplay_segment()` automatically purges any leaked English meta-sentences, refusal blocks, or markdown headers from audio scripts.

