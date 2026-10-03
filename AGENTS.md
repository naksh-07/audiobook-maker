# Local Agent Guidelines & Context

- **Canonical Project ID**: proj-audiobook-maker
- **Global Config**: Inherits [Global AGENTS.md](file:///C:/Users/Suraj/.gemini/config/AGENTS.md)

## Domain Context: Studio Audiobook Production Engine
- **Core Architecture**: 6-stage audio drama production pipeline (`SOURCE -> EXTRACTION -> TRANSLATION -> SCREENPLAY -> TTS -> DIRECTING -> CINEMATIC AUDIO -> PACKAGING`).
- **Pillar 1 Forensic Ingestion**: Geometric PDF layout XY-cut reading order (`PDFLayoutReconstructor`), character-accurate `SourceProvenance` indexing (`_PDFPageSpanRecord`), multi-signal candidate quality gate (`PDFQualityAnalyzer`), authentic literary chapters vs. production chunks (`get_literary_chapters()`), non-destructive normalization (sacred `raw_text` vs. sanitized `normalized_text`), canonical AST, and fail-closed Gate 0.1.
- **Audio Standards**: EBU R128 (-19 LUFS vocal target), 48kHz / 24-bit studio pipeline, Hann micro-fades (12ms/18ms), sample-accurate multi-speaker alignment.
- **Universal Novel-Agnostic Invariant**: The factory core (`audiobook_factory`, CLI, quality gates, translation engines, acoustic pipelines) MUST NEVER contain hardcoded novel titles, franchise lore, character rosters, file hashes, or era biases. All book metadata, pronunciation rules, characters, and world acoustic DNA MUST be dynamically derived from source book text, `book_bible.json`, or LLM project classification (`ProjectClassifier`). Quality gates and sound bank search filters MUST default to `UNIVERSAL_CONTEMPORARY` unless dynamically resolved from scene intent.
- **Environment**: High-performance Windows 11 workstation with CUDA acceleration.
- **Active Memory**: Project memory bank in `.agents/memory/` (`activeContext.md` $\le$ 50 lines).
