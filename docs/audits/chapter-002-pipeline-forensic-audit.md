# Chapter 02 Pipeline Forensic Audit Report (Unstable & Buggy Release)

- **Date**: 2026-10-06
- **Auditor**: Antigravity AI Engineering Suite
- **Scope**: Strictly Read-Only Forensic Root Cause Analysis across Chapter 02 Production Pipeline
- **Project Target**: *Sword of Destiny* (Chapter 02 - "The Bounds of Reason")
- **Status Flag**: `UNSTABLE / BUGGY` (Tagged for remediation)

---

## Executive Summary

During production of Chapter 02 (11.1 minutes, 73 segments), the generated audio output passed all mechanical and technical quality gates (Gate 5 certified at -19.1 LUFS, True Peak -1.8 dBTP). However, artistic and acoustic inspection revealed critical degradation across dialogue fidelity, translation nuance, sound effects staging, and asset retrieval.

This forensic audit identifies the exact technical root causes, source diffs, schema key mismatches, and cascading fallback traps across 7 core failure dimensions.

---

## 1. Dialogue Omission and Attribution Discrepancies

### Evidence & Root Causes:
1. **Source Paragraphs Omitted in Translation**:
   - **Source Paragraph 14**:
     ```text
     'Quiet, Alderman, and stay out of this, or you're in for a hiding,' the spotty-faced man warned.
     ```
     *Finding*: Completely dropped in `translation/chapter_002_hi.md`. The translation jumps directly from the butcher's line to Borch's entry, omitting the verbal threat against the Alderman.
   - **Source Paragraphs 41 & 42**:
     ```text
     [41] 'That pleases me greatly,' the white-haired man smiled. At the sight of the smile burgeoning on his face, the Alderman turned pale.
     [42] The spotty-faced man was also retreating. The spots on his white face were unpleasantly conspicuous. The butcher and the slaughterhouse workers, although they were three to one, were backing away slowly towards the fence.
     ```
     *Finding*: Completely absent in `translation/chapter_002_hi.md`. The translation skips directly from Geralt's combat stance to Borch shouting *"ऐ, वहीं रुक..."* (Source Para 43). Geralt's chilling smile, the Alderman blanching, and the retreat of the butcher's gang were silently discarded.
2. **Dialogue Speaker Attribution Flips**:
   - In `scripts/chapter_002_hi_script.json`, rapid back-and-forth dialogue lines (segments 32, 37, 39) were misassigned by `dramatized_builder.py` between the Alderman, Butcher, and Geralt due to sliding-window attribution confusion.
3. **Missing Audio Takes Gate Bypass**:
   - `chapter_002_performance_report.json` records:
     - `total_segments`: 73
     - `total_takes_generated`: 71
     - `passed`: true
     *Finding*: 2 segments had 0 takes generated, yet Gate 2.8 recorded a 0.95 average score and passed the chapter without blocking.

---

## 2. Translation Degradation & Stiltedness

### Evidence & Root Causes:
1. **Hardcoded Zero Thinking Budget (`thinking_budget = 0`)**:
   - In `audiobook_factory/translation/orchestrator.py` (Line 338):
     ```python
     raw_target = call_llm_fn(
         ...,
         task_type=TaskType.TRANSLATION,
         thinking_budget=0,
     )
     ```
     Depriving the generative model of reasoning tokens forced statistical token completion without character subtext, cadence evaluation, or dramatic planning.
2. **Translation Memory Hallucinations**:
   - Verified by Scene 1 Certification Report (`scene_001/certification.json`):
     - *"watery little eyes"* translated as **"एस्सी डेवेन" (Essi Daven)** — an unauthorized character name hallucinated from later chapters.
     - *"lynx skins"* translated as **"लंगूर की ख़ाल" (langur / monkey skin)**.
     - *"Witcher"* translated inconsistently as *"मायावी शिकारी"* instead of the canonical locked glossary term *"विचर"*.
3. **Prompt Over-Regulation (Negative Constraint Traps)**:
   - System prompts injected competing negative guidelines (Kashyap 19-to-21 amplification vs sacred reverence vs "Aate me Namak" formulas), causing artificial, stiff vocabulary transitions.

---

## 3. Inaudible SFX, Foley, and Missing Wallah

### Evidence & Root Causes:
1. **The Smoking Gun Bug: `"foley_tag": ""` Key Mismatch**:
   - In `audiobook_factory/timeline_ledger.py` (Line 327):
     ```python
     foley_events.append({
         "trigger_t_ms": trigger_ms,
         "foley_tag": fc.get("foley_tag", ""),  # BUG: Cues emit 'asset_name' / 'action_verb', NOT 'foley_tag'
         "volume": float(fc.get("volume", 0.30)),
         "stereo_pan": float(fc.get("spatial_pan", 0.0)),
         "description": fc.get("description", ""),
     })
     ```
   - In `chapter_002_hi_timeline_ledger.json`:
     - Every single foley cue (10 out of 10) was populated with `"foley_tag": ""` (empty string).
   - In `audiobook_factory/soundscape_engine/mixer.py` (Line 451):
     - `bank.resolve_sound("")` returned `None`.
     - **Result: EXACTLY 0 FOLEY SOUNDS WERE RENDERED INTO THE FINAL AUDIO MIX.**
2. **Ambience Attenuated to Inaudibility (-32.0 LUFS)**:
   - In `multi_agent_director.py` (Line 586):
     `target_lufs = -32.0` is hardcoded.
   - Compared to Dialogue at `-17.7 LUFS`, the ambient bed is suppressed by 14.3 dB, creating an acoustically dead, anechoic atmosphere.
3. **Wallah (Crowd Presence) Annihilated**:
   - `MultiAgentDirector` planned dynamic crowd automations, but the fail-closed fallback aborted the entire director and ran legacy `SoundSpotter`, which has zero Wallah capability.
4. **Stem Ledger Gain Suppression**:
   - In `chapter_002_stem_ledger.json`:
     - **FX Stem**: `-31.3 LUFS`, RMS level **`-51.81 dB`** (essentially silence).
     - **Music Stem**: `-26.0 LUFS`, RMS level **`-52.97 dB`**.
     - **Dialogue Masking Ratio (DMR)**: **`+28.02 dB`**.
     - Stems were pushed down into the noise floor, 28 dB below dialogue.

---

## 4. Online Asset Staging Failures & Offline Asset Starvation

### Evidence & Root Causes:
1. **Rotten Remote URLs**:
   - Live HTTP requests for virtual assets in `sound_catalog` failed:
     - `https://archive.org/download/SonnissGameAudioGDCPack1/Heavy_Boots_Wet_Gravel_Walk_01.wav` -> **HTTP 503: Service Unavailable**.
     - `https://gamesounds.xyz/Sonniss.com%20-%20GDC%202020%20-%20Game%20Audio%20Bundle/Heavy_Boots_Wet_Gravel_Walk_01.wav` -> **HTTP 404: Not Found**.
2. **The "Single Missing Asset" Death Penalty**:
   - `stage_manifest_assets(strict_fail_closed=True)` threw `SoundAssetStagingError` when 1 virtual asset failed to download.
   - `sound_spotter.py` caught this exception and discarded all 23 Foley cues, 7 Music cues, and 2 Wallah acts planned by the 5 specialized LLMs, falling back to legacy primitive spotting.
3. **Starvation of 27,654 Local Disk Assets**:
   - Audit of `audiobooks/sound_bank/sound_bank.db` verified that **27,654 audio files are physically present on local disk**.
   - However, the resolver queries `sound_catalog` without prioritizing `is_downloaded = 1`. It selected virtual assets with broken URLs instead of available local assets.

---

## 5. Choked LLM Decision-Making & God-Script Overrides

### Evidence & Root Causes:
1. **Fragile Fallback Cascades**:
   - A single missing sound file triggered an exception that nullified the output of 5 specialized LLMs (Showrunner, Scenographer, Foley Specialist, Music Supervisor, Wallah Director) in favor of a hardcoded Python script.
2. **Prompt Handcuffs**:
   - Prompts forced artificial scarcity: `"max 2-3 cues per scene"`, `"keep silence >= 65%"`. Models were constrained like accountants rather than artistic sound designers.
3. **Deterministic Overwrites**:
   - Downstream generators stripped LLM cues (e.g. `sfx_cues = []` in screenplay builder).

---

## 6. Rubber-Stamping Quality Gates

### Evidence & Root Causes:
1. **Gate 5 / MasteringEngineV2 Blindness**:
   - In `chapter_002_mastering_ledger.json`, `perceptual_evaluation` assigned a **1.0 (PASS / PERFECT)** across all dimensions (intelligibility, naturalness, spatial coherence).
   - The certifier only checked integrated loudness (-19.1 LUFS) and peak (-1.8 dBTP). An audio file with a dry voice and 85% silence on all other tracks passes Gate 5 automatically.
2. **MixJudge False Positives**:
   - `MixJudge` scored "FX clarity" as **1.0 (PASS)** with reason *"Foley and impact transients are crisp and discernible"*, despite the FX stem RMS being **-51.81 dB** (inaudible). MixJudge only checked if dialogue was unmasked.
3. **Translation Gate REVIEW_REQUIRED Ignored**:
   - Scene 1 had `certified: false` and `overall_status: REVIEW_REQUIRED` due to hallucinations (Essi Daven) and additions, yet the production pipeline proceeded to TTS without intervention.

---

## 7. Sonic Database Engine Analysis

### Database Audit (`audiobooks/sound_bank/sound_bank.db`):

| Metric | Measured Value | Notes |
| :--- | :--- | :--- |
| **Total Catalog Records** | 61,043 | Comprehensive multi-source catalog |
| **Physical Assets on Disk** | 27,654 (45.3%) | Verified on disk (`is_downloaded = 1`) |
| **Virtual Assets (Require URL)** | 33,388 (54.7%) | Rely on remote CDNs / mirrors |
| **Unverified Remote URLs** | 43,462 (71.2%) | Untested links susceptible to rot |
| **Verified Working URLs** | 17,567 (28.7%) | CDNs verified reachable |
| **Confirmed Broken URLs** | 14 | Archive.org 503 / Gamesounds 404 |

### Structural Bugs:
- **Missing Local-First Preference**: Retrieval does not sort by `is_downloaded DESC`.
- **FTS5 Semantic Misses**: Exact-match FTS5 fails on compound or synonym searches without prefix matching (`*`) or morphological stemming.

---

## Remediation Roadmap (Action Plan for Future Sprints)

1. **Foley Schema Alignment**:
   - Patch `timeline_ledger.py` line 327 to inspect `fc.get("asset_name")`, `fc.get("action_verb")`, and `fc.get("anchor_word")` in addition to `foley_tag`.
2. **Local-First Sound Retrieval**:
   - Enforce `ORDER BY is_downloaded DESC` in all database queries to utilize the 27,654 local files.
3. **Graceful Asset Staging Substitution**:
   - Modify `stage_manifest_assets` so that a failed download substitutes an existing local asset rather than aborting `MultiAgentDirector`.
4. **Restore LLM Autonomy**:
   - Set `thinking_budget = 1024` for literary translation and screenplay adaptation.
   - Remove negative handcuffs (`max 2-3 cues`, `silence >= 65%`).
5. **Acoustic & Semantic Quality Gate Overhaul**:
   - Enforce minimum RMS / LUFS thresholds for active FX/MX stems in `MixJudge` so silent tracks fail rather than pass.
   - Fail closed when Translation Gate reports `REVIEW_REQUIRED` or `certified: false`.

---
*Report archived in `docs/audits/` under tag `v4.0.0-unstable-buggy`.*
