# 🎬 Stage 11: Cinematic Mix v2 Architecture

## Executive Architectural Law

> **Stage 11 determines the cinematic mix. Stage 12 performs mastering.**

Stage 11 produces a **Cinematic Mix Premaster** (`CINEMATIC_MIX_PREMASTER`), not a final mastered audiobook. Stage 12 performs the final EBU R128 loudness calibration, audio container packaging, and delivery distribution.

---

## 🏗️ The Stage 11 Decision Pipeline

```text
Scene / Existing Mix Inputs
          ↓
    SceneMixIntent
          ↓
     AttentionMap
          ↓
  Automation Planner
          ↓
Mix Automation Timeline
          ↓
Dynamic Masking & Stem Interaction
          ↓
 Existing Cinema Audio Engine
          ↓
Cinematic Mix Premaster
          ↓
    Stage 12 Mastering
```

---

## 🎯 Architecture Lifecycle: Implemented vs. Planned

### 1. Prompt 1 Foundation (Verified & Active)
* **`SceneMixIntent`**: Typed Stage 11 scene mixing intent model.
  * **Constrained Focus**: Strictly constrained narrative focus targets: `dialogue`, `music`, `fx`, `ambience`, `silence`, `environment`.
  * **Normalized Priorities**: Bounded weights in `[0.0, 1.0]` for `dialogue_priority`, `music_priority`, `fx_priority`, and `ambience_priority`.
  * **Emotional Intensity**: Normalized measure `[0.0, 1.0]` from calm ($0.0$) to extreme ($1.0$).
  * **Dynamic Range & Spatial Depth Intent**: Signals scene-level dynamic range and acoustic perspective intent.
  * **Deterministic Serialization**: SHA-256 fingerprinting and JSON serialization.
* **`AttentionMap` & `AttentionEvent`**: Time-aware listener attention model.
  * **Timed Attention Events**: `start`, `end`, `focus_target`, `priority` (0.0 to 1.0), and `reason`.
  * **Attention $\ne$ Dialogue Principle**: Focus can belong to dialogue, music, FX, ambience, or silence based on narrative command.
* **Output Semantics**: First-class `CINEMATIC_MIX_PREMASTER` stem type with backward-compatible `FULL_MASTER` alias.

---

### 2. Prompt 2 Automation & Dynamic Mixing (Implemented & Active)

#### A. Automation Data Model (`MixAutomation` & `AutomationEvent`)
* **Typed Representation**: Independent of concrete DSP implementations.
* **Hierarchy Tiers** (for conflict resolution):
  1. `SAFETY_LIMIT` (Level 50): Hard bounds preventing digital clipping or audio dropouts (`[-36.0 dB, +6.0 dB]`).
  2. `MOMENTARY_EVENT` (Level 40): Urgent narrative spikes (gunshots, sword parries, explosion hits).
  3. `ATTENTION_PROTECTION` (Level 30): Sustained dialogue intelligibility or musical feature envelopes.
  4. `SCENE_INTENT` (Level 20): Baseline fader adjustments driven by scene-level intent.
  5. `BASE_SCENE` (Level 10): Default acoustic bed calibration.
* **Evaluator**: `evaluate_parameter(target, parameter, t)` resolves overlapping events deterministically. For gain/ducking, deepest attenuation wins within the highest active hierarchy tier, bounded by safety limits.

#### B. Deterministic Curve Evaluator (`curves.py`)
* Supports `linear`, `ease_in` (quadratic), `ease_out` (inverted quadratic), and `smooth` (cubic Hermite smoothstep $3p^2 - 2p^3$).
* First derivatives vanish at endpoints for `smooth` mode, eliminating fader click artifacts.
* Rejects zero-duration ($start \ge end$) and invalid modes; gracefully handles out-of-range timestamps.

#### C. Attention $\rightarrow$ Automation Planner (`AutomationPlanner`)
* Discretizes continuous timelines into non-overlapping priority focus windows (`AttentionMap.resolve_windows()`).
* Applies narrative **attack** ($100\text{ms}$) and **release** ($400\text{ms}$) envelopes around speech and attention windows to eliminate abrupt fader pumping.
* Anti-Jitter Filter: Filters micro-slivers ($< 50\text{ms}$) to prevent rapid fader flutter.
* Handles edge cases gracefully:
  * No dialogue active $\rightarrow$ music and ambience breathe naturally without blind ducking.
  * No music or foley stem $\rightarrow$ zero redundant automation filters created.
  * Empty scene $\rightarrow$ clean baseline pass-through.

#### D. Dynamic Dialogue Masking (`DynamicMaskingAnalyzer`)
* **Spectral Carving**: Dynamically carves vocal corridor frequencies from competing music stems rather than bludgeoning music volume.
* **Formant Frequency Detection**:
  * Whisper / intimate speech $\rightarrow 2800\text{ Hz}$ (protects soft sibilance and consonant air).
  * Standard speech $\rightarrow 2400\text{ Hz}$.
  * Female vocal persona $\rightarrow 2600\text{ Hz}$.
  * Deep male vocal persona $\rightarrow 2200\text{ Hz}$.
* **Hard Safety Guardrails**:
  * **Notch Depth Ceiling**: Maximum notch depth is strictly capped at $-6.5\text{ dB}$ (never carves out music completely).
  * **DMR Ceiling Bypass**: If estimated Dialogue-to-Masking Ratio (DMR) is already $\ge 14.0\text{ dB}$, notch is a no-op ($0.0\text{ dB}$) to preserve full acoustic power.
  * **Music Priority Relaxation**: High music priority ($\ge 0.70$) softens notch depth to preserve thematic score presence.

#### E. Stem Interaction Engine (`StemInteractionEngine`)
* **Environmental Naturalism Invariant**: Normal dialogue must **NEVER** mute the ambient world. Ambient attenuation during speech is modest ($-1.5\text{ dB}$ to $-3.5\text{ dB}$), preserving a cohesive acoustic room tone.
* **Intimate Whisper**: Deeper music suppression ($-10\text{ dB}$ to $-14\text{ dB}$) with vocal pocketing, while subtle room tone is maintained.
* **Combat & High Intensity**: FX transient punches are prioritized ($0.0\text{ dB}$ attenuation), while driving music remains energized (attenuation $\le -3.0\text{ dB}$).
* **Musical Revelation**: Thematic score commands focus ($0.0\text{ dB}$ attenuation); dialogue retains intelligibility through localized pocketing.

#### F. Engine Adapter & Cinema Audio Engine Integration (`engine_adapter.py`)
* Converts abstract `MixAutomation` into native FFmpeg filter expressions:
  * Dynamic gain: `volume='if(between(t, s, e), g, 1.0)':eval=frame`
  * Dynamic spectral notch: `equalizer=f=2400:t=q:w=1.50:g=-5.50`
* Modulates discrete stems in-place before ME summing.
* Fully backward compatible: if no intent or attention map is provided, the engine runs its pristine baseline pipeline.

#### G. Inspectable Decision Audit Trace
* Every automation decision is recorded in `MixAutomation.decision_trace` and saved to `chapter_XXX_stem_ledger.json` under `metadata["automation_decisions"]`.
* Records: `time`, `focus`, `target`, `parameter`, `before`, `after`, `reason`, `source`, `priority`, and guardrails.

---

### 3. Prompt 3 Cinematic Behavior (Implemented & Active)

#### A. Architectural Law
> **The three behavior directors are decision/planning layers, NOT parallel audio rendering engines.**
> They emit typed `AutomationEvent` instances into the unified `MixAutomation` timeline, which are rendered deterministically by `CinemaAudioEngine`.

```text
Scene / Mix Inputs
        ↓
SceneMixIntent
        ↓
AttentionMap
        ↓
Behavior Directors
   ┌────┼─────────────┐
   ↓    ↓             ↓
Acoustic  Silence    Impact
Perspective Director Director
   └────┼─────────────┘
        ↓
Mix Automation Timeline (Level 35 CINEMATIC_BEHAVIOR)
        ↓
Dynamic Mixing & Masking
        ↓
Existing CinemaAudioEngine
        ↓
Cinematic Mix Premaster
```

#### B. Acoustic Perspective (`AcousticPerspective` & `PerspectiveDirector`)
* **Physical Distance Modeling**:
  * `close`: Direct energy $+1.0\text{ dB}$, width $1.0$, cutoff $20000\text{ Hz}$, reverb send $0.05$.
  * `near`: Direct energy $0.0\text{ dB}$, width $0.95$, cutoff $16000\text{ Hz}$, reverb send $0.15$.
  * `medium`: Direct energy $-3.5\text{ dB}$, width $0.80$, cutoff $10000\text{ Hz}$, reverb send $0.35$.
  * `far`: Direct energy $-9.0\text{ dB}$, width $0.50$, cutoff $5000\text{ Hz}$, reverb send $0.65$.
* **Barrier Occlusion**:
  * `curtain`: Soft fabric HF dampening to $8500\text{ Hz}$, $-1.5\text{ dB}$ loss.
  * `door`: Solid wooden barrier muffling to $2200\text{ Hz}$, $-9.5\text{ dB}$ direct energy loss.
  * `wall`: Heavy brick/concrete occlusion to $1100\text{ Hz}$, $-16.5\text{ dB}$ direct energy loss.
* **Acoustic Conflict Resolution**:
  * When multiple low-pass events overlap, the lowest cutoff frequency dominates (`min(cutoff)`), accurately simulating physical acoustic obstruction.
* **Discrete Stem Rendering**: Added `"DX"` to dynamic modulation in `CinemaAudioEngine`, allowing speech behind doors or walls to be physically low-pass filtered and attenuated.

#### C. Silence Director (`SilenceEvent` & `SilenceDirector`)
* **Negative Sound Design**: Treats silence as an intentional dramatic punctuation, never plain digital black.
* **6 Narrative Silence Types**:
  1. `NONE`: No-op passthrough.
  2. `DRAMATIC`: Deep music plunge ($-20\text{ dB}$), FX drops ($-14\text{ dB}$), ambience slightly ducked ($-5\text{ dB}$ if `room_tone` preserved).
  3. `SUSPENSE`: Score thins out, ambience lowers, spot FX remain razor sharp.
  4. `SHOCK`: Post-explosion ear-ring / near-black (down to $-28\text{ dB}$), preserving only decaying `fx_tail`.
  5. `EMOTIONAL`: Gentle intimate dip ($-8\text{ dB}$ to $-12\text{ dB}$), vocal breath ($0\text{ dB}$) and room tone preserved.
  6. `TRANSITION`: Scene boundary crossfade dip.
* **3-Stage Envelopes**:
  * **Approach Phase**: Smooth Hermite transition from baseline $0.0\text{ dB}$ to silence floor `cut_db`.
  * **Floor Phase**: Steady hold across the silence duration.
  * **Release Phase**: Smooth acoustic recovery back to $0.0\text{ dB}$ baseline with zero residual offset.

#### D. Impact Director (`ImpactEvent` & `ImpactDirector`)
* **4-Phase Physical Impact Trajectory**:
  1. `PRE_IMPACT`: Subtle anticipation dip ($-1.5\text{ dB}$ to $-3.5\text{ dB}$) preparing the listener ear.
  2. `IMPACT`: Transient peak slam with instant dynamic ducking of competing beds ($-6\text{ dB}$ to $-14\text{ dB}$).
  3. `AFTERMATH`: Lingering impact tail stabilization ($-3\text{ dB}$ to $-7\text{ dB}$).
  4. `RECOVERY`: Smooth release envelope back to $100\%$ baseline gain ($0.0\text{ dB}$).
* **Non-Destructive Attention Shift**:
  * `derive_attention_shift(attention_map, impact_events)` clones the input `AttentionMap` and injects temporary high-priority transient focus windows without mutating the caller's map.
* **Intensity Scaling**: All ducking depths and durations scale proportionally with bounded `intensity` $[0.0, 1.0]$. Events with intensity $\le 0.05$ are safely bypassed.

---

### 4. Prompt 4 Mix Judge, Golden Suite & Automatic Diagnosis (Implemented & Active)

#### A. Target Pipeline Architecture
```text
Scene / Mix Inputs
        ↓
SceneMixIntent
        ↓
AttentionMap
        ↓
Cinematic Behavior (Perspective, Silence, Impact)
        ↓
Automation Planner (Hierarchy Level 35)
        ↓
CinemaAudioEngine
        ↓
Cinematic Mix Premaster (`CINEMATIC_MIX_PREMASTER`)
        ↓
┌──────────────────────────────────────────────┐
│                  MIX JUDGE                   │
│                                              │
│ 1. Technical Safety   7. Spatial Coherence   │
│ 2. Dialogue Focus     8. Masking / Ducking   │
│ 3. Music Integration  9. Silence Behavior    │
│ 4. FX Clarity        10. Impact Behavior     │
│ 5. Ambience Nat.     11. Transition Quality  │
│ 6. Dynamic Contrast  12. Cinematic Intent    │
└──────────────────────────────────────────────┘
        ↓
PASS / PASS_WITH_WARNINGS / REMIX / FAIL
        ↓ (if REMIX)
RemixPlan (Actionable Target, Parameter, Delta)
        ↓
RemixController (Bounded Cycle, Max 2 Attempts, Convergence Epsilon)
        ↓
Cinematic Mix Premaster (Certified)
        ↓
Stage 12 Mastering
```

#### B. The 12 Category Evaluators
1. **Technical Safety**: Evaluates file integrity, non-zero duration, true peak clipping ($\le 0.0\text{ dBTP}$ ceiling, $> +0.5\text{ dBTP}$ hard fail), total silence dropouts ($< -65\text{ LUFS}$ hard fail), and stereo phase correlation ($r < 0.0$ hard fail).
2. **Dialogue Focus**: Evaluates vocal corridor DMR ($300\text{Hz}-3.5\text{kHz}$) using exact DSP bandpass filtering. Asserts DMR $\ge 6.0\text{ dB}$ (standard) and $\ge 8.0\text{ dB}$ (whisper), while permitting score dominance when music is intentionally declared as scene focus.
3. **Music Integration**: Detects over-ducking ($< -40\text{ LUFS}$ when score should be present), under-ducking (music dominating whisper), and erratic fader pumping ($\ge 4$ unmotivated gain oscillations).
4. **FX Clarity**: Asserts physical presence and audibility of narrative foley transients and impacts (peak FX $\ge -36\text{ dB}$ during impact windows).
5. **Ambience Naturalism**: Enforces the Environmental Naturalism Invariant (ambience is never sterilized to digital silence $< -55\text{ dB}$ during speech).
6. **Dynamic Contrast**: Evaluates loudness range (LRA) and peak-to-RMS ratio against `dynamic_range_intent` (`compressed_intimate`, `natural_dialogue`, `cinematic_wide`, `extreme_dynamic`).
7. **Spatial Coherence**: Asserts dialogue center stability and verifies that physical occlusion (door/wall) translates to dynamic lowpass filtering.
8. **Masking / Ducking**: Asserts that spectral carving notch depth strictly respects the $-6.5\text{ dB}$ safety ceiling and gain automation stays in $[-36.0, +6.0\text{ dB}]$.
9. **Silence Behavior**: Asserts negative sound design depth for dramatic/suspense pauses and verifies preserved elements (`room_tone` $\ge -42\text{ dB}$, `breath`, `fx_tail`).
10. **Impact Behavior**: Asserts 4-phase physical trajectory (`PRE_IMPACT`, `IMPACT`, `AFTERMATH`, `RECOVERY`) and clean return to $0.0\text{ dB}$ baseline with zero residual offset.
11. **Transition Quality**: Asserts smooth boundary transitions, Hermite curve interpolation, and click-free start/end points.
12. **Cinematic Intent**: Reconciles the rendered stem hierarchy against high-level narrative focus.

#### C. Hard Fail vs. Remix Distinction
* **`FAIL` (Hard Fail)**: Unrecoverable technical/stream defect (missing premaster, digital clipping $> +0.5\text{ dBTP}$, complete silence dropout, severe anti-phase correlation $r < 0.0$). Halts the pipeline immediately without wasting iterations adjusting faders.
* **`REMIX`**: Technically valid audio with narrative/cinematic mismatch (dialogue buried, whisper masked, music over-ducked, ambience sterilized, impact buried, silence shallow). Generates a structured `RemixPlan`.
* **`PASS_WITH_WARNINGS`**: Audio is compliant and acceptable, but carries minor non-critical warnings for human logging.
* **`PASS`**: Full technical compliance and cinematic intent alignment.

#### D. Automatic Diagnosis & Bounded Remix Loop (`RemixController`)
* **`MixDiagnosis`**: Structured error records containing `category`, `status`, `reason`, `evidence`, `likely_cause`, and `recommended_action`.
* **`RemixPlan`**: Actionable remediation items detailing `target`, `parameter`, `current_value`, `recommended_value`, `action_code`, and `priority`.
* **Remix Convergence & Attempt Limit**:
  * Default `max_attempts = 2` (maximum 3 renders per scene).
  * Evaluates score delta $\Delta S = S_{n} - S_{n-1}$. If $\Delta S < 0.04$, halts loop with `converged=False` to prevent infinite thrashing.

#### E. 20-Scenario Golden Cinematic Mix Regression Benchmark
Permanent deterministic benchmark exercising the 20 canonical literary/dramatic scenarios:
1. `01_intimate_conversation`
2. `02_normal_dialogue`
3. `03_whisper`
4. `04_emotional_confession`
5. `05_shouting`
6. `06_multi_speaker_conversation`
7. `07_dialogue_plus_music`
8. `08_music_led_emotional_scene`
9. `09_dialogue_plus_ambience`
10. `10_dialogue_plus_heavy_fx`
11. `11_sudden_impact`
12. `12_combat`
13. `13_horror_reveal`
14. `14_dramatic_silence`
15. `15_suspense_build`
16. `16_behind_door_distant_voice`
17. `17_spatial_movement`
18. `18_crowded_layered_scene`
19. `19_transition_between_rooms`
20. `20_chapter_scene_transition`

---

### 5. Prompt 5 Final Integration, Optimization & Audit (Implemented & Active)

#### A. End-to-End Orchestrator & Audio Engine Wiring
* **Seamless Pipeline Integration**: `render_discrete_stems()` in `cinema_audio_engine.py` directly executes `MixJudge.evaluate()` on rendered stems and the premaster.
* **Persistent Audit Telemetry**: Full `MixJudgeResult` model dumps, overall scores, and status verdicts (`PASS`, `PASS_WITH_WARNINGS`, `REMIX`, `FAIL`) are recorded in `chapter_XXX_stem_ledger.json` under `metadata["mix_judge_audit"]`.
* **Bounded Remediation within Render Pipeline**: Passing `enable_remix=True` allows `render_discrete_stems()` to automatically invoke `RemixController` to apply actionable parameter adjustments to `MixAutomation`, re-render affected stems/premaster, and verify convergence without external orchestration complexity.
* **Orchestrator Observability**: `orchestrator.py` inspects `stem_ledger.metadata["mix_judge_status"]` and logs structured audit telemetry, catching critical failures before chapter delivery.

#### B. High-Performance Deterministic Analysis Caching
* **Subprocess & DSP Overhead Elimination**: Both `DeterministicAudioAnalyzer` and `MixJudge` feature in-memory stat-based caches (`_format_cache`, `_loudness_cache`, `_corridor_cache`, `_phase_cache`).
* **Cache Key**: `(resolved_file_path, file_size_bytes, mtime_ns)` guarantees deterministic zero-latency retrieval without stale data risks.
* **Double-Probe Elimination**: Evaluator categories sharing audio metrics (e.g. `technical_safety` and `dynamic_contrast` both inspecting premaster loudness) execute the second check in $O(1)$ memory lookup time.
* **Remix Loop Acceleration**: Stems untouched by remix adjustments (e.g. dialogue `DX` during a music bed remix) bypass expensive re-analysis completely.

#### C. Comprehensive Test Suite & Regression Verification
* **8 Test Suites**: 115 passing tests across unit, integration, behavior, automation, judge, golden regression, and legacy cinema gates.
* **20/20 Golden Scenarios**: 100% pass rate on literary/dramatic regression benchmark.
* **Fail-Closed Gate**: Critical audio defects (digital silence dropouts, severe digital clipping $> +0.5\text{ dBTP}$, anti-phase correlation) immediately flag `compliance_status = False` and halt the pipeline.

---

## 📊 Pipeline Boundary Definition

| Aspect | Stage 11: Cinematic Mix | Stage 12: Mastering |
|---|---|---|
| **Primary Goal** | Direct listener attention and balance narrative elements across DME stems | Final loudness normalization and multi-format audio packaging |
| **Output File** | `chapter_XXX_cinema_master.wav` (`CINEMATIC_MIX_PREMASTER`) | Final Distribution M4B / MP3 / FLAC Container |
| **Integrated LUFS** | Target guideline ($-19.0$ LUFS reference) | Strict contractual broadcast enforcement ($\pm 0.5$ LU) |
| **True Peak** | Technical anti-clipping limiter ($\le -1.5$ dBTP) | Final inter-sample peak ceiling certification ($\le -1.5$ dBTP) |
| **Automation** | Dynamic faders, ducking envelopes, spatial pans, focus tracking | Fixed-chain limiter, SOXR resampler, dithering |
