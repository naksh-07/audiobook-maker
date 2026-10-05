<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Maker Production Engine & Hollywood Directing Suite

## Milestone: Option A Pre-Production Master State Locked (COMPLETE)
- **Status**: COMPLETE & MASTER_LOCKED (19/19 regression tests green).
- **Deliverables**: Canonical `book_dossier.json`, `book_dna.json` (`DARK_FANTASY_GRIT`), `book_bible.json`, `sonic_bible.json`, and collision-free `cast_lock.json` for *Sword of Destiny*.

## Milestone: Chapter 1 Production & Cinematic Audio Master (COMPLETE)
- **Status**: COMPLETE & EBU R128 CERTIFIED (-19.0 LUFS, -1.8 dBTP, 0.875 Phase Correlation).
- **Deliverables**:
  1. Translation & Script: `chapter_001_hi.md` translated; `chapter_001_hi_script.json` (10 segments).
  2. TTS Synthesis: 10 speech segments cached in `audio_chunks/`; dialogue composite `chapter_001_hi_dialogue.wav`.
  3. Discrete 5-Track Stems: Rendered `chapter_001_stem_DX.wav`, `_stem_FX.wav`, `_stem_MX.wav`, `_stem_AMB.wav`, `_stem_ME.wav`.
  4. Final Broadcast Master: `chapter_001_hi_cinematic.m4a` & `chapter_001_cinema_master.wav` (0.97 min).

## Milestone: Chapter 2 Production & Read-Only Forensic Audit (COMPLETED & TAGGED)
- **Status**: TAGGED AS `v4.0.0-unstable-buggy` — Production audio verified mechanically but flagged acoustically/artistically.
- **Audit Findings**:
  1. Dialogue: Dropped source paras 14, 41, 42; 2 segments missing takes (passed by Gate 2.8).
  2. Translation: `thinking_budget=0`, Essi Daven & langur hallucinations, "मायावी शिकारी" drift.
  3. SFX/Foley: `timeline_ledger.py` line 327 `foley_tag` key mismatch caused 100% empty cues; 0 foley rendered; FX stem at -51.81 dB RMS.
  4. Online/Offline: Archive.org 503 & Gamesounds 404 aborted MultiAgentDirector to legacy spotter; 27,654 local files bypassed.
  5. Gates: Gate 5 & MixJudge rubber-stamped silent FX/MX as 1.0; Scene 1 REVIEW_REQUIRED ignored.
- **Artifact**: `docs/audits/chapter-002-pipeline-forensic-audit.md`.

## Active State: Paused for Future Remediation
- **Tag**: `v4.0.0-unstable-buggy` pushed to GitHub.
- **Next Focus**: Foley schema key fix, local-first sound bank retrieval, graceful download fallback, thinking budget restoration, and gate rigor overhaul.
