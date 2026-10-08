# 📖 Audiobook Studio Documentation Hub

**Standard**: `v6.0-ENTERPRISE-DAG` & `v6.0-STUDIO-UI`  
**System**: Studio Audio Production & Vocal Mastering Engine  
**Platform**: Google Antigravity Plugin & Standalone Python/Node.js Framework  

---

## 🏛️ Authoritative Architecture & Specification Suite

The table below catalogs the authoritative specification suite governing the **v6.0-ENTERPRISE-DAG** decoupled architecture:

| Specification Manual | Scope & Focus | Key Subsystems & Concepts |
|---|---|---|
| **[🏛️ Master Architecture (MAS-001)](ARCHITECTURE.md)** | Master topology & invariants | Hexagonal topology, 2-Tier Content-Addressed TakeBank cache, SQLite WAL ledger DDL (`pipeline_ledger.db`), ADR-008. |
| **[🎛️ Plugin UI & Studio Sidecar](STUDIO_UI_AND_SIDECAR_SPECIFICATION.md)** | Antigravity UI Extension | Aux Pane Webview Sidecar, 4 Visual Zones, Dual-Column Translation Editor, 4D Formant Cast Board, Audio Dock, IPC Bridge. |
| **[📜 Data Contracts & Schemas](CONTRACTS_AND_SCHEMAS.md)** | Pydantic v2 strict models | `schema_version: "2.0"` contracts for all 5 rooms, deterministic canonical SHA-256 serialization. |
| **[⚙️ Core Platform Foundation](CORE_PLATFORM_SPECIFICATION.md)** | Shared decoupled services | 120+ KeyPool rotation, Tier-1 ModelManager (`BLOCK_NONE`), TakeBank LRU cache, DE-01-DE-07 DSP, Two-Pass EBU R128 Loudnorm. |
| **[🚪 Subsystems Specification (Rooms 1 - 5)](SUBSYSTEM_SPECIFICATIONS.md)** | Standalone room engines | Room 1 Ingestion, Room 2 Translation Collective, Room 3 Screenplay & Anti-Swap QA, Room 4 TTS & Editorial, Room 5 Broadcast Master. |
| **[🎛️ DAG Presets & Orchestration](DAG_ORCHESTRATION_AND_PRESETS.md)** | Top-level DAG runner | Dynamic Presets (`AUDIOBOOK_STUDIO`, `ENGLISH_AUDIOBOOK`, `MULTI_HOST_PODCAST`, `STANDALONE_TRANSLATION`), Diff Reconciler. |
| **[🗺️ Migration & Testing Blueprint](plans/v6_implementation_and_migration_blueprint.md)** | Implementation roadmap | 6-Phase migration plan, target package layout, unit/integration test matrices, Definition of Done. |
| **[🛠️ Developer & Contributor Guide](DEVELOPER_GUIDE.md)** | Setup & workflow | Python 3.10+ / Node.js 18+ / FFmpeg setup, running tests, sidecar local debugging, Git hygiene. |

---

## 🧭 Deep-Dive Domain Manuals

| Guide | Description | Target Audience |
|---|---|---|
| **[📜 Forensic Ingestion Engine](FORENSIC_DOCUMENT_INGESTION.md)** | Geometric XY-cut layout reconstructor, character-accurate `SourceProvenance`, and Gate 0.1 AST monotonicity. | System Architects, NLP Engineers |
| **[🧠 Literary Translation Intelligence](LITERARY_TRANSLATION_INTELLIGENCE.md)** | 4-Agent Translation Collective, Dual-Rule Invariant (`CLASSIC_REVERENT` vs `RAW_UNRATED`), and Tri-Partite Entity Partition. | Literary Translators, NLP Engineers |
| **[🎭 Dramatic Adaptation & Screenplay](DRAMATIC_ADAPTATION_AND_SCREENPLAY.md)** | Prose-to-screenplay parser, Gate 2.0 Anti-Swap attribution audit (0% $A \leftrightarrow B$ flips), and physical acting directives. | Dramaturges, Directing Agents |
| **[🎭 Voice Casting & 4D Formants](VOICE_CASTING_DIRECTOR_GUIDE.md)** | 4D acoustic formant matrices (pitch $\pm 4-12\%$, tempo, parametric EQ curves), character dossiers, and non-colliding casting. | Casting Directors, Dramaturges |
| **[🇮🇳 Complete Hindi Voice Catalog](HINDI_VOICE_CATALOG.md)** | Catalog of 114 native Hindi voices across Awadhi, Bhojpuri, Haryanvi, Bundeli, and Urdu/Delhi dialects with timbre classifications. | Casting Directors, Dramaturges |
| **[🎙️ Gemini Flash TTS Directing](GEMINI_TTS_SYNTHESIS_AND_DIRECTING.md)** | Generative neural speech synthesis, speech tags, Stanislavski directives, and token-bucket concurrency. | Audio Engineers, Developers |
| **[✂️ Dialogue Editorial Layer (DE-01 - DE-07)](DIALOGUE_EDITORIAL_LAYER.md)** | Endpoint zero-crossing snapping (-52 dBFS), Hann micro-fades (12ms/18ms), dynamic pause realization, and breath attenuation. | Dialogue Editors, Audio Engineers |
| **[🎛️ Audio Engineering & Vocal Mastering](AUDIO_ENGINEERING.md)** | Two-pass measured linear loudnorm (EBU R128 -19.0 LUFS / -1.5 dBTP), Kaiser Sinc 48kHz / 24-bit PCM, and M4B packaging. | Audio Engineers, Mastering Specialists |
| **[🛡️ Quality Gates Specifications](QUALITY_GATES.md)** | Comprehensive specifications for fail-closed quality verification (Gates 0.1 through 5.0). | QA Engineers, Audio Engineers |
| **[💻 CLI Reference Manual](CLI_REFERENCE.md)** | Complete CLI syntax for autonomous DAG runs, standalone room subcommands, and Sidecar IPC bridges. | Developers, Operators |
| **[🎓 End-to-End Production Tutorial](TUTORIAL_E2E.md)** | Step-by-step recipes for full novel production, English-only novels, podcasts, surgical beat patching, and UI directing. | Developers, Directors |
| **[🤖 AI Agent & MCP Integration](MCP_AGENT_INTEGRATION.md)** | Directing `@audiobook-director` assistant, Antigravity skills, and MCP tool schemas. | Agent Architects, Integrators |

---

## 📦 Decoupled & Archived Subsystems

The legacy 5-track cinematic audio engine (dynamic BGM scoring, sound bank FTS5 search, and multitrack Foley mixdowns) has been permanently decoupled and archived in `archive/cinematic_audio/`:
- **[🎬 Cinematic Mix Architecture](CINEMATIC_MIX_ARCHITECTURE.md)** *(Archived)*
- **[🎬 Cinematic Sound Design & Adult Fidelity](CINEMATIC_SOUND_DESIGN_AND_ADULT_FIDELITY.md)** *(Archived)*
- **[🎵 Commercial Sound Design Subsystem](CINEMATIC_SOUND_DESIGN_SUBSYSTEM.md)** *(Archived)*
- **[🎹 Sound Bank & Asset Catalog](SOUND_BANK.md)** *(Archived)*

---

## ⚡ Quick Repository Links
- Root Project Portal: [`README.md`](../README.md)
- Core Python Engine: [`audiobook_factory/`](../audiobook_factory/)
- Sidecar Webview Studio Panel: [`sidecars/studio-panel/`](../sidecars/studio-panel/)
- Antigravity Plugin Rules: [`rules/AGENTS.md`](../rules/AGENTS.md)
- Antigravity Director Agent: [`agents/audiobook-director.md`](../agents/audiobook-director.md)
- Test Suite: [`tests/`](../tests/)
