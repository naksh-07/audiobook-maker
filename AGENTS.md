# Local Agent Guidelines & Context

- **Canonical Project ID**: proj-audiobook-maker
- **Global Config**: Inherits [Global AGENTS.md](file:///C:/Users/Suraj/.gemini/config/AGENTS.md)

## Domain Context: Studio Audiobook Production Engine
- **Core Architecture**: 6-stage audio drama production pipeline (`SOURCE -> EXTRACTION -> TRANSLATION -> SCREENPLAY -> TTS -> DIRECTING -> CINEMATIC AUDIO -> PACKAGING`).
- **Pillar 1 Forensic Ingestion**: Non-destructive normalization, structural EPUB extraction, layout-aware PDF analysis, canonical AST projection, and fail-closed quality gates.
- **Audio Standards**: EBU R128 (-19 LUFS vocal target), 48kHz / 24-bit studio pipeline, Hann micro-fades (12ms/18ms), sample-accurate multi-speaker alignment.
- **Environment**: High-performance Windows 11 workstation with CUDA acceleration.
- **Active Memory**: Project memory bank in `.agents/memory/` (`activeContext.md` $\le$ 50 lines).
