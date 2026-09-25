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
- **Windows Timezone Fallback (`key_manager.py`):** Python on Windows standard installations lacks `tzdata` by default. Attempting `ZoneInfo("America/Los_Angeles")` raises `ZoneInfoNotFoundError`. Always provide a fallback `timezone(timedelta(hours=-7))` for Pacific Midnight quota resets.
- **Windows CLI 8,191-Char Overflow (`cinema_audio_engine.py`):** Windows `cmd.exe` / `CreateProcess` imposes an 8,191-character command line limit. When complex audio filter graphs exceed 6,000 characters, dynamically spill `filter_complex` into a temporary `.filter` file and call FFmpeg with `-filter_complex_script <file>`.
- **Pre-Flight Voice Registry Validation (`tts_dispatcher.py`):** Before launching multi-track synthesis, invoke `validate_screenplay_speakers()` or run Gate 2 canonical auto-discovery. Reject unmapped characters with `UnregisteredSpeakerError` immediately to prevent silent voice drift to the narrator.
- **Bilingual Foley Anchor Mapping (`agent_director.py`):** To avoid the 50% dead-center pan trap on Hindi dialogue, always map Foley cues using `BILINGUAL_ANCHOR_MAP` (`दरवाजा`, `कदम`, `तलवार`, `हंसी`, etc.) in `_compute_word_level_offset()`.
- **Cumulative Timeline Drift Mitigation (`agent_director.py`):** Segment start times must accumulate both audio duration and pre-roll breath delay (`seg_duration + (seg.pre_roll_breath_ms / 1000.0)`). Omitting breath delays causes downstream Foley and BGM events to desynchronize across chapters.
- **Domestic vs. Weapon Acoustic Isolation (`acoustic_bus_matrix.py`):** Utensils, cutlery, and dishware (`fork`, `spoon`, `cup`, `plate`) must map strictly to `DOMETabl` rather than `WEAPSwd`, preventing eating/drinking scenes from sounding like metallic sword clashes.
- **Sanitizer Bracketed Tag Shield (`sanitizer.py`):** Strip bracketed acting tags (`re.sub(r"\[[^\]]+\]", "", text)`) prior to measuring Latin-to-Devanagari character purity ratios. This prevents acting tags (`[bellowing battlecry]`, `[whispers]`) from triggering false-positive rejection of valid dialogue.
- **Gemini FinishReason Parsing (`tts_dispatcher.py`):** Always guard against empty candidate arrays and parse `finishReason` (`SAFETY`, `RECITATION`, `BLOCKLIST`) with informative diagnostic feedback rather than allowing unhandled `IndexError` on `candidates[0]`.
- **Ghost Event Quarantine Invariant (`memory_store.py`):** When `commit_scene_memory()` encounters conflicting deltas, the corresponding `StoryEvent` is isolated strictly in `store.rejected_events` (and `MemoryValidationReport.rejected_event_ids`). It MUST NOT enter `store.events`, `world_state.timeline`, or character recent events; otherwise, downstream retrievers will retrieve rejected events as dramatic memories.
- **Location Condition Preservation (`memory_delta.py`):** Movement events (`CHARACTER_MOVED`) must omit the `"condition"` key in `location_state` payloads unless `meta.get("location_condition")` is explicitly provided. Blindly defaulting to `"normal"` resets damaged or destroyed locations back to pristine state upon character arrival.
- **Transitive Attack Verb Disambiguation (`events.py`):** In active transitive sentences (*"Arjun stabbed Vikram"*), the character following the attack verb is the injured victim and the preceding character is the instigator. When multiple characters appear in the clause, `SceneChangeDetector` marks `is_ambiguous=True` to safely trigger semantic LLM refinement.
- **Conservative Screenplay Performance Guidance (`memory_context.py`):** When enriching screenplay segments, never overwrite existing explicit delivery styles (inspect both `seg["delivery_style"]` and nested `seg["acting"]["delivery_style"]`). Only inject `memory_vocal_constraint` (e.g. `strained_breath`, `fatigued_low_energy`) when the line's delivery style is neutral.
- **Epistemic Strict Membership (`character_memory.py`):** A character MUST ONLY be added to `fact.known_by` if their epistemic status is `KnowledgeStatus.KNOWN`. If they merely suspect the fact (`SUSPECTED`), they are stored in `fact.character_statuses` and `character_state.suspected_facts`, preventing false-positive knowledge propagation.
- **Pre-Translation Read-Only Invariant (`translator.py`):** `_retrieve_chapter_memory_in_translator()` must remain strictly read-only and never call `commit_scene_memory()` or `store.save()`. All memory commits occur strictly in post-translation `_commit_chapter_memory_in_translator()` after translation succeeds.
- **Top-Level Screenplay Writeback (`orchestrator.py`):** Always write enriched `script_data` back to `script_file` on disk before invoking Gate 2 and `TTSDispatcher`. Otherwise, parallel worker threads will read the un-enriched script from disk, dropping `memory_vocal_constraint` tags during TTS synthesis.


