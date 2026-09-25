# Local Agent Guidelines & Context

- **Canonical Project ID**: proj-audiobook-maker
- **Global Config**: Inherits [Global AGENTS.md](file:///C:/Users/Suraj/.gemini/config/AGENTS.md)

## Domain Context: Studio Audiobook Production Engine
- **Core Architecture**: 6-stage audio drama production pipeline (`SOURCE -> EXTRACTION -> TRANSLATION -> SCREENPLAY -> TTS -> DIRECTING -> CINEMATIC AUDIO -> PACKAGING`).
- **Pillar 1 Forensic Ingestion**: Geometric PDF layout XY-cut reading order (`PDFLayoutReconstructor`), character-accurate `SourceProvenance` indexing (`_PDFPageSpanRecord`), multi-signal candidate quality gate (`PDFQualityAnalyzer`), authentic literary chapters vs. production chunks (`get_literary_chapters()`), non-destructive normalization (sacred `raw_text` vs. sanitized `normalized_text`), canonical AST, and fail-closed Gate 0.1.
- **Audio Standards**: EBU R128 (-19 LUFS vocal target), 48kHz / 24-bit studio pipeline, Hann micro-fades (12ms/18ms), sample-accurate multi-speaker alignment.
- **Environment**: High-performance Windows 11 workstation with CUDA acceleration.
- **Active Memory**: Project memory bank in `.agents/memory/` (`activeContext.md` $\le$ 50 lines).
