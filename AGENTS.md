# Local Agent Guidelines & Context

- **Canonical Project ID**: proj-audiobook-studio
- **Plugin Name**: audiobook-studio
- **Global Config**: Inherits [Global AGENTS.md](file:///C:/Users/Suraj/.gemini/config/AGENTS.md)

## Domain Context: Studio Audiobook Production Engine (Pure Vocals-Only)
- **Core Architecture**: 5-Room Pure Vocals-Only Pipeline (`SOURCE -> EXTRACTION -> PRE-PRODUCTION (Room 1) -> TRANSLATION COLLECTIVE (Room 2) -> SCREENPLAY & ANTI-SWAP ATTRIBUTION (Room 3) -> 4D FORMANT MULTI-VOICE TTS & EDITORIAL (Room 4) -> BROADCAST VOCAL MASTERING & M4B PACKAGING (Room 5)`).
- **Vocals-Only Architectural Invariant**: Background music (BGM), sound effects (SFX), Archive.org sound bank scraping, and 5-track multitrack mixdowns are **STRICTLY PROHIBITED AND DECOUPLED** on this branch. Production is 100% focused on Audible-standard vocal excellence, character acting, dialogue nuance, and pristine narration.
- **Vocal & Directing Stack**:
  1. Google Gemini Flash TTS (120+ active API keys, SQLite round-robin pool, token-bucket concurrency).
  2. 4D Acoustic Formants: Pitch ($\pm 4-12\%$), tempo, and 4D parametric EQ curves (`equalizer=f=...`) eliminating vocal convergence.
  3. Room 3 Anti-Swap `DialogueAttributionAuditor` ensuring 0% speaker turn inversion ($A \leftrightarrow B$).
  4. Room 2 Translation Collective with Dual-Rule Invariant (`CLASSIC_REVERENT` dignity vs `RAW_UNRATED` visceral combat gore & intimacy).
  5. Dialogue Editorial Layer (DE-01 - DE-07) with Hann micro-fades (12ms/18ms) and contextual turn latency.
  6. Broadcast EBU R128 (-19.0 LUFS, -1.5 dBTP) vocal loudness mastering and chaptered `.m4b` container with embedded cover art.
- **Pillar 1 Forensic Ingestion**: Geometric PDF layout XY-cut reading order (`PDFLayoutReconstructor`), character-accurate `SourceProvenance` indexing (`_PDFPageSpanRecord`), multi-signal candidate quality gate (`PDFQualityAnalyzer`), authentic literary chapters vs. production chunks (`get_literary_chapters()`), non-destructive normalization (sacred `raw_text` vs. sanitized `normalized_text`), canonical AST, and fail-closed Gate 0.1.
- **Audio Standards**: EBU R128 (-19 LUFS vocal target, -1.5 dBTP ceiling), SOXR 48kHz / 24-bit studio pipeline, Hann micro-fades (12ms/18ms), sample-accurate multi-speaker alignment.
- **Universal Novel-Agnostic Invariant**: The factory core (`audiobook_factory`, CLI, quality gates, translation engines) MUST NEVER contain hardcoded novel titles, franchise lore, character rosters, file hashes, or era biases. All book metadata, pronunciation rules, characters, and dialects MUST be dynamically derived from source book text, `book_bible.json`, or LLM project classification (`ProjectClassifier`).
- **Environment**: High-performance Windows 11 workstation with CUDA acceleration.
- **Active Memory**: Project memory bank in `.agents/memory/` (`activeContext.md` $\le$ 50 lines).
