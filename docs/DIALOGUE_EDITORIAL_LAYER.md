# ✂️ Dialogue Editorial Layer (DE-01 through DE-07)

**Module:** `audiobook_factory.dialogue_editing`  
**Pipeline Placement:** Between Take Selection (Stage 3.5 / TakeBank) and Vocal Mastering (Stage 4 / `mastering.py`)  
**Status:** Production Ready (666/666 tests passing, 100% green)

---

## 1. Overview & Objective

The **Dialogue Editorial Layer** is the production editing intelligence for `audiobook-maker`. It transitions the system from mechanical take concatenation into a commercial, Hollywood-grade dialogue assembly.

In natural human conversation, speakers do not begin and end on abrupt clip boundaries separated by static 400ms gaps. Human speech is characterized by:
- **Organic Respiratory Dynamics**: Preparatory inhalations, tension exhales, and emotional releases.
- **Contextual Turn-Taking Latencies**: Pacing governed by power dynamics, high-stakes combat compression, thoughtful hesitation, and tragic aposiopesis.
- **Clean Acoustic Transitions**: Zero-crossing phase alignment, true raised-cosine micro-fades, and surgical elimination of high-frequency vocoder/watermark artifacts without clipping stop consonants.
- **Fail-Closed Protection**: Automated audio audits that safeguard original performances against accidental speech truncation, distortion, or phase cancellation.

---

## 2. Architecture & Data Flow

The Dialogue Editorial Layer operates **non-destructively**. Original takes in `audio_chunks/` remain completely immutable.

```
       Stage 3.5: TakeBank / Golden Take Selection
                           │
                           ▼
               [ Raw Chunks: audio_chunks/ ]
                           │
                           ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                 Dialogue Editorial Layer                     │
  │                                                              │
  │  1. EndpointEditor      - Safety buffers (40ms/60ms)         │
  │                         - Dynamic speech floor (-52 dBFS)    │
  │                         - Sub-millisecond zero-crossing snap │
  │                         - Plosive-safe C2PA burst scrub      │
  │                                                              │
  │  2. BreathEditor        - Multi-signal intent (KEEP/REDUCE)  │
  │                         - High-restraint sob protection      │
  │                         - Relative acoustic delta thresholds │
  │                                                              │
  │  3. PauseEditor         - Contextual turn latencies          │
  │                         - Tragic aposiopesis preservation    │
  │                         - Vocal power & leverage dynamics    │
  │                         - Deterministic hash pseudo-jitter   │
  │                                                              │
  │  4. DialogueEditingQC   - Fail-closed speech truncation test │
  │                         - NaN / Inf & rail-clipping guard    │
  │                         - Chapter-wide cadence audit         │
  │                                                              │
  │  5. 16-Bit PCM Renderer - True Hann raised-cosine fades      │
  │                         - Deterministic TPDF dither          │
  │                         - Multi-format ingestion (24/32-bit) │
  └──────────────────────────────────────────────────────────────┘
                           │
                           ▼
          [ Edited Chunks: edited_chunks/ ]
          [ DialogueEditPlan[] manifests ]
                           │
                           ▼
       Stage 4: Vocal Mastering (concatenate_and_master_chapter)
                           │
                           ▼
       Mastered Dialogue Stem (EBU R128 -19 LUFS)
```

---

## 3. Subsystem Breakdown

### 3.1 Editorial Contracts (`contracts.py`)
- **`DialogueEditPlan`**: Strongly typed Pydantic v2 schema encapsulating source take identification, head/tail trims (in high-precision float ms), breath action decisions, boundary micro-fades, pre/post pause durations, gain adjustments (`ge=-24.0, le=12.0`), confidence, and explainability audit metadata.
- **`DialogueEditorialConfig`**: Centralized configuration defining safety buffers (40ms head, 60ms tail), baseline 5.0ms de-click micro-fades, max 15.0ms editorial transitions, and pause ranges.
- **`DialogueQCReport`**: Structured report tracking chapter-level editorial actions, warnings, and hard failures with an `@model_validator` guaranteeing `passed=False` whenever hard failures occur.

### 3.2 Intelligent Endpoint Editor (`endpoint_editor.py`)
- **Dynamic Speech Floor**: Evaluates overall take RMS and establishes a floating floor down to `-52 dBFS`, ensuring intimate whispers, dying breaths, and vocal fry decays are preserved.
- **Sub-Millisecond Zero-Crossing Snapping**: Finds exact waveform zero crossings closest to target trim points and returns float millisecond values, preventing sample-offset quantization error.
- **C2PA Burst vs. Stop Plosive Discrimination**: Unvoiced stop consonants (/p/, /t/, /k/) feature 40–90ms silence closures followed by release bursts. The editor requires silence valleys $\ge 100$ms and consults forced alignment word boundaries to guarantee genuine consonant releases are never clipped.
- **Emotional Release Preservation**: Automatically expands tail buffers to 180–200ms with a gentle 50ms fade-out for lines tagged with grief, weeping, panting, or trailing decay.

### 3.3 Conservative Breath Editor (`breath_editor.py`)
- **`KEEP` (0.0 dB)**: Mandatory preservation for directed inhalations (`pre_roll_breath_ms > 0`), physical strain (`combat_strain`, `exhausted`), intense emotions (`panic`, `grief`, `rage`, `defiance`), and ambiguous low-confidence signals.
- **`REDUCE` (-6.0 dB)**: Gentle raised-cosine attenuation applied only when an inhale is disproportionately loud relative to a calm, neutral spoken line.
- **`REMOVE` (-36.0 dB)**: High-confidence surgical silencing reserved strictly for synthetic vocoder clicks on iron-restraint lines devoid of emotional sobbing.
- **Suppressed Sob Safeguard**: Characters under iron restraint (`restraint >= 0.85`) experiencing suppressed grief or trauma retain shuddering intakes as authentic acting.

### 3.4 Contextual Pause & Turn-Taking Editor (`pause_editor.py`)
- **Elimination of Arbitrary 400ms Defaults**: Pauses are derived dynamically:
  - *Interrupted Cutoff*: 25–35ms.
  - *Rapid Turn / Escalation*: 100–140ms.
  - *Standard Turn*: 220–280ms.
  - *Hesitation / Thinking*: 450–750ms.
  - *Dramatic Silence / Emotional Freeze*: 1100–1800ms.
- **Aposiopesis Supremacy**: Trailing em-dashes (`—`) on lines with grief, shock, or dramatic freeze preserve the full 1200–1800ms silence rather than triggering rapid cutoffs.
- **Conversational Power & Leverage**:
  - Subordinates responding to dominant authority answer promptly (`0.90x` latency compression).
  - Dominant authorities responding to subordinates take their time (`1.20x` latency expansion).
- **Deterministic Anti-Mechanical Jitter**: Injects $\pm 25$ms SHA256-seeded jitter based on segment UID and text tokens, eliminating metronome pacing without non-deterministic test flapping.

### 3.5 Robust Master Coordinator & Renderer (`editor.py`)
- **Multi-Format Ingestion**: Decodes 16-bit PCM, 24-bit packed PCM (`sampwidth == 3`), and 32-bit float (`sampwidth == 4`), downmixing multi-channel audio to mono float32.
- **True Hann Raised-Cosine Micro-Fades**: Implements $0.5(1 - \cos(\pi t / T))$ micro-fades with $w'(0) = 0$, eliminating acceleration spikes and spectral edge splatter.
- **Deterministic TPDF Dither & Zero Pinning**: Replaced randomized seeds with stable `hashlib.sha256(f"{source_take}:{segment_uid}")` seeding. Quantization dither is 100% bit-exact across independent process runs, and hard-pins boundary samples (`int16_samples[0] = 0`, `int16_samples[-1] = 0`) to guarantee click-free assembly.
- **Fail-Closed Fallback**: If QC detects hard failures or corrupt files, `orchestrator.py` automatically resets `edited_segments = segments` and `edit_plans = None`, falling back to unedited raw takes.

### 3.6 Conversational Interruption & Overlap (DE-05)
- **Controlled Cross-Talk Realization**: Supports `overlap_start` (default 150ms overlap, 0ms pause) for natural dialogue interruptions where Speaker B talks over the end of Speaker A.
- **Fade-Under Ducking**: Supports `fade_under` (120ms overlap), applying an automated smooth cosine ducking curve (-9dB / factor 0.35) over the final 120ms of the interrupted speaker's line.
- **Abrupt Cutoffs**: Supports `abrupt_cut` (35ms gap, crisp 2.0ms zero-crossing micro-fade) for sharp interjections without clicks or long trailing decays.
- **Mastering Cross-Talk Stitching**: In `mastering.py`, overlapping takes are split into `body_A` $\rightarrow$ `transition_AB` (equal-power mixed $A_{\text{tail}} + B_{\text{head}}$) $\rightarrow$ `body_B`. Integrates seamlessly with FFmpeg concat demuxer and preserves 3D stereo spatial soundstages.
- **QC Safety Gates**: Rejects any overlap exceeding 400ms or 50% of take duration as `HARD_FAILURE`.

### 3.7 Take Boundary Continuity (DE-06)
- **Inter-Take Gain Leveling**: Computes speech RMS across adjacent takes in a scene. When volume jumps exceed 1.2dB without intentional dramatic justification (e.g. whispering or shouting), smooths the volume jump by adjusting `plan.gain_adjustment_db` up to $\pm 2.5$dB.
- **Elevated Noise-Floor Tapering**: Detects elevated vocoder background noise floors ($> -48.0$ dBFS) at take boundaries and expands micro-fades from 5.0ms to 15.0ms Hann tapers (`room_match_required = True`), preventing audible digital silence dropouts.

### 3.8 Intra-Segment Mid-Line Breath Editing (DE-07)
- **Multi-Signal Mid-Line Discovery**: Scans for internal breath events within speech boundaries using forced alignment pause intervals, inter-word gaps, or acoustic energy dips ($>14$dB drop for 120–900ms).
- **whitelist Protection for Emotional Breaths**: Strictly preserves (`KEEP`) authentic gasps, sobs, and labored breathing during combat strain, fear, grief, crying, or high-restraint moments (`restraint >= 0.85`).
- **Targeted Calm Inhale Reduction**: Attenuates exaggerated TTS gasps on calm dialogue lines by -6.0dB using professional trapezoidal Hann crossfade envelopes (20ms entry/exit tapers with stable mid-gap hold).
- **Word Encroachment QC**: Verifies that mid-line breath edits never encroach into aligned spoken words (20ms tolerance), failing closed with `MID_BREATH_WORD_COLLISION` if violated.

---

## 4. Verification & Quality Gates

The Dialogue Editorial Layer is protected by a dedicated 46-test suite:
1. `tests/test_dialogue_editorial_layer.py` (18 unit tests): Schema defaults, 5ms micro-fades, dead-air trimming, prep-breath retention, emotional decay, cadence audits, PCM rendering.
2. `tests/test_dialogue_editing_integration.py` (3 E2E integration tests): Golden 7 dialogue scenarios, E2E mastering path, fail-closed fallback execution.
3. `tests/test_dialogue_editorial_audit_remediation.py` (13 adversarial audit tests): 24/32-bit audio decoding, stereo downmix, float zero-crossing, gain application, whisper dynamic floor, aposiopesis, power dynamics, sob protection, NaN/Inf detection.
4. `tests/test_dialogue_editorial_de05_de07.py` (12 tests): Interruption abrupt cuts, overlap start cross-talk, fade-under ducking, aposiopesis em-dash eager counters, mastering overlap stitching, inter-take gain leveling, elevated noise-floor micro-fades, mid-line breath reduction and emotional preservation, QC word collision and overlap limits, bit-exact TPDF dither determinism.

**Full Test Suite Run:** `666 passed in 346.39s (0:05:46)` (0 failures, 0 regressions, 100% green).
