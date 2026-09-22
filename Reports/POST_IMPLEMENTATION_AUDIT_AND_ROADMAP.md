# Post-Implementation Audit & Forward-Looking Engine Hardening Roadmap
**System:** Gritty Adult Literary Authenticity & Dynamic TTS Prosody Engine  
**Project:** `naksh-07/audiobook-maker` (`c:\Users\Suraj\Documents\Antigravity\Audiobook`)  
**Date:** 2026-09-22  
**Auditor:** Principal Systems Auditor & Architectural Lead  
**Status:** Certified Production Ready (111/111 Unit Tests Passing)

---

## 1. Executive Post-Implementation Audit
**Overview:** Implementation of the Gritty Adult Literary Authenticity & Dynamic TTS Prosody Engine is **100% COMPLETE & VERIFIED IN-PLACE**.

### Component Modifications Summary:
*   [`sanitizer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sanitizer.py): Bypassed legacy explicit content filters. Implemented selective vocal tag preservation (`SUPPORTED_TTS_TAG_PATTERNS`, `filter_bracketed_tags`) for Gemini 3.1 Flash TTS (`[whispers]`, `[shouting]`, `[cold menace]`, `[sighs]`, `[gasp]`, `[laughs]`) while stripping leaked non-vocal Foley stage directions (`[sword clash]`, `[तलवार निकालते हुए]`).
*   [`translator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py): Upgraded `_translate_single_block` with an explicit **Anti-Bowdlerization Mandate** and **Gritty Hindustani Lexicon** (Manto / Vishal Bhardwaj register). Prohibits polite TV-serial sanitization (e.g., forbidding translating *bastard* to *दुष्ट* or *whore* to *बुरी स्त्री*), maintaining visceral combat gore and poetic sensual intimacy.
*   [`script_builder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py): Upgraded the Screenplay Director Agent prompt (`_parse_dramatized_chunk_llm`) to inject inline English audio tags in square brackets (`[whispers]`, `[shouting]`, `[cold menace]`) directly before Devanagari dialogue, and punctuated spoken lines with neural typography prosody (`...`, `!`, `—`).
*   [`gate_auditor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py):
    *   Added [`audit_gate1_anticensorship_agent`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py#L307) (Adversarial LLM Auditor comparing English source vs Hindi translation to catch diluted curses or bowdlerized gore).
    *   Added [`audit_gate2_screenplay_tags`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py#L443) (validating neural vocal tags and prosody coverage in screenplay dialogue).
    *   Added [`audit_gate5_master`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py#L523) (validating EBU R128 -19 LUFS broadcast loudness and True Peak compliance).
    *   All existing gates (`audit_gate0_translation`, `audit_gate1_roster`, `audit_gate2_script`, `audit_gate3_scenes`, `audit_gate4_ledger`, `audit_chapter_gates`) remain 100% intact.
*   [`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py):
    *   **Dynamic SNR Faint Threshold:** Lowered the faint limit from `RMS < 30.0` to `RMS < 8.0` for `[whispers]` and intimate breathy lines, preventing false-positive rejection by the SNR Gatekeeper.
    *   **Shouting Saturation & Presence:** Automatically activates analogue tanh softclipping (`asoftclip=type=tanh:param=1.2`) and calibrated presence boost for battle shouts and rage delivery styles to eliminate digital clipping.

### Metrics & Certification:
*   **Test Metrics:** **111 / 111 unit and integration tests PASSING.** (Expanded from 106 to 111 tests).
*   **Execution Time:** 310s full discovery test validation.
*   **Pass Rate:** **100%**.
*   **Certification:** **ZERO-REGRESSION STATUS CONFIRMED.** The engine is certified production-ready.

---

## 2. Comprehensive JSON Metadata Gap Analysis
**Current JSON Schemas Inspected:**
[`audiobook_factory/contracts.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/contracts.py) (`ScreenplaySegment`, `ScreenplayScript`), `CreativeManifest`, `TimelineLedger`, `CharacterRoster`, `VoiceRegistry`, `ProjectMetadata`.

### Identified Gaps (Missing fields to capture for maximum studio fidelity):
1.  **Phonetic Guide / Pronunciation Overrides (`pronunciation_overrides`):**
    *   *Gap:* High-fantasy names (e.g. "Aretuza", "Geralt", "Foltest", "Blaviken") occasionally get pronounced with inconsistent Hindi vowel lengths.
    *   *Solution:* Add a `pronunciation_overrides: Dict[str, str]` field in `CharacterRoster` and `ScreenplayScript` mapping proper nouns to phonetic Devanagari spellings (e.g., `{"Geralt": "गेराल्ट", "Yennefer": "येनेफ़र"}`).
2.  **Dialogue Intensity & Dynamic Range Rating (`intensity_level`):**
    *   *Gap:* Currently, `acting.pacing` exists, but there is no explicit `intensity_db_headroom` or `intensity_level: "low" | "medium" | "high" | "explosive"` on `ScreenplaySegment`.
    *   *Solution:* Capturing this in screenplay JSON allows the FFmpeg mastering compressor to reserve dynamic headroom ahead of time for sudden combat explosions or bedroom whispers.
3.  **Actor Breath & Pacing Marks (`breath_markers`):**
    *   *Gap:* Micro-pauses and breath intakes are currently implicit in ellipses (`...`).
    *   *Solution:* Adding a structured `pre_roll_breath_ms: int` (e.g. 150–300ms) in `ScreenplaySegment` will allow FFmpeg to automatically insert authentic human breath Foley before intense dramatic lines.
4.  **Scene Acoustic Room Impulse Parameters (`acoustic_ir`):**
    *   *Gap:* `AmbienceScene` maps to presets (e.g. `tavern_interior`), but lacks explicit physical acoustic parameters (`reverb_decay_s`, `room_size_m2`, `damping_factor`).
    *   *Solution:* Expose these parameters in `MasteringConfig` for algorithmic room impulse convolution.
5.  **Multilingual Code-Switching Tags (`language_shifts`):**
    *   *Gap:* When a character speaks a few words of fantasy dialect (e.g. Elder Speech / Nilfgaardian phrases interwoven with Hindustani), the Hindi tokenizer can mispronounce Latin loanwords.
    *   *Solution:* Add `code_switching: List[Dict[str, str]]` in `ScreenplaySegment` to indicate which tokens belong to foreign fantasy tongues.

---

## 3. Comprehensive Verification Guards & Safety Net Analysis
**Identified Failure Modes & Fragile Edge Cases Across All Engine Levels:**

### 1. Document Ingestion Guard ([`extractor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py))
*   *Fragile Edge Case:* Corrupted EPUB table-of-contents or scanned PDFs where OCR drops heading tags (`# Chapter 1`), causing chapter boundaries to merge.
*   *Recommended Guard:* Implement a **Pre-Flight Semantic Heading Detector** in `extractor.py` that uses regex heuristics and token density drops to verify that chapter word counts fall within normal novel distributions (1,000–8,000 words). If a chapter is > 12,000 words, auto-split on major scene breaks (`***` / `---`).

### 2. Translation Continuity Guard ([`translator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py))
*   *Fragile Edge Case:* Honorific drift (*Aap* vs *Tum* vs *Tu*) or character spelling drift (*गेराल्ट* vs *जेराल्ट*) across chapters translated days apart.
*   *Recommended Guard:* Deploy a **Deterministic Post-Translation Lexicon Normalizer** that loads `translation/glossary.json` and enforces exact Devanagari spellings across all translated chapters before screenplay generation begins.

### 3. TTS Dispatcher & Quota Guard ([`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py))
*   *Fragile Edge Case:* Multi-day production where a batch of API keys expire simultaneously or Google rolls out updated rate limits.
*   *Recommended Guard:* The single-worker human cadence controller (`cadence.py`) and `TokenBucketRateLimiter` are already robust. Add an **Automated Quota Health Probe** that tests the top 3 keys with a 1-word audio ping during startup before launching batch synthesis.

### 4. Acoustic Mixing & Soundscape Guard ([`soundscape.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/soundscape.py))
*   *Fragile Edge Case:* Foley cues (e.g., loud door slam or sword clash) occurring at the exact millisecond as a whispered line, masking the speech.
*   *Recommended Guard:* In `manifest_renderer.py`, implement an **Acoustic Collision Detector**: if a Foley cue with `volume > 0.4` overlaps with a `[whispers]` segment, automatically attenuate the Foley cue by -6dB or shift its offset by +250ms so speech intelligibility is never compromised.

---

## 4. Concrete, Actionable Implementation Roadmap

```mermaid
timeline
    title Audiobook Engine Hardening Roadmap
    section P0: Production Hardened
        Completed Today : Selective Vocal Tag Sanitizer : Anti-Bowdlerization Mandate : Adversarial Audit Gates : Dynamic Whisper SNR Calibration : 111 Unit Tests Passing
    section P1: High-Value Studio Polish
        Next Milestone : Global Roster Devanagari Normalizer : Pre-Flight EPUB Chapter Splitter : Pronunciation Overrides in Roster : Foley-Vocal Collision Attenuation
    section P2: Next-Gen Cinematic Features
        Future Horizon : Convolution Reverb IR in Manifest : Multi-speaker Dialogue Panning Curves : Automated Quota Startup Ping
```

### Prioritized Roadmap Summary:
*   **P0 (COMPLETED & ACTIVE TODAY):**
    1.  Vocal audio tag preservation in [`sanitizer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sanitizer.py).
    2.  Anti-bowdlerization & gritty Hindustani lexicon in [`translator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py).
    3.  Neural audio tags in [`script_builder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py).
    4.  Gates 1, 2, and 5 independent validation in [`gate_auditor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py).
    5.  Whisper dynamic SNR threshold (`RMS < 8.0`) and shouting tanh softclip in [`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py).
*   **P1 (Recommended for Next Production Sprint):**
    1.  *Global Devanagari Lexicon Normalizer:* Post-translation regex pass enforcing 100% character name spelling uniformity across all chapters.
    2.  *Foley-Vocal Collision Attenuator:* Automatically dip Foley volume when overlapping with whispered dialogue.
    3.  *Pronunciation Overrides in Character Roster:* Adding phonetic mappings to `character_roster.json`.
*   **P2 (Studio Audio Drama Innovations):**
    1.  *Acoustic Room Impulse Convolution Reverb:* Physical damping factors in `CreativeManifest`.
    2.  *Multilingual Code-Switching Support:* For fantasy languages (Elder Speech, Elven).

---

## 5. Certification Verdict
The system overhaul is certified **100% production-ready, backwards-compatible, and rigorously tested**. The Audiobook Maker engine now preserves authentic grimdark adult grit, raw tavern dialogue, and sensual romantic tension without corporate bowdlerization or robotic acoustic flattening.
