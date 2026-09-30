# 🟠 REAL AUDIO VALIDATION REPORT

> **Report Generated**: `2026-09-30T16:03:01.028945+00:00`  
> **Mastering Engine**: `v2.1.0`  
> **Overall Assessment**: **`REVIEW_REQUIRED`**  

---

## 1. EXECUTIVE SUMMARY

Real Audio Validation completed across 12 fixtures. Passed: 1, Warnings: 10, Review Required: 1, Failed: 0. Overall status: REVIEW_REQUIRED.

| Metric | Count |
|---|---|
| **Fixtures Evaluated** | 12 |
| **Passed (Clean)** | 1 |
| **Passed with Warnings** | 10 |
| **Review Required** | 1 |
| **Failed** | 0 |

---

## 2. CATEGORY RESULTS

| Category | Status | Notes |
|---|---|---|
| **narration** | `WARNING` | Evaluated on calibrated real audio fixture |
| **dialogue** | `WARNING` | Evaluated on calibrated real audio fixture |
| **whisper** | `WARNING` | Evaluated on calibrated real audio fixture |
| **shouting** | `WARNING` | Evaluated on calibrated real audio fixture |
| **emotional** | `WARNING` | Evaluated on calibrated real audio fixture |
| **hindi_hinglish** | `WARNING` | Evaluated on calibrated real audio fixture |
| **music_heavy** | `WARNING` | Evaluated on calibrated real audio fixture |
| **ambience** | `WARNING` | Evaluated on calibrated real audio fixture |
| **foley** | `WARNING` | Evaluated on calibrated real audio fixture |
| **action** | `PASS` | Evaluated on calibrated real audio fixture |
| **silence** | `REVIEW_REQUIRED` | Evaluated on calibrated real audio fixture |
| **difficult_tts** | `WARNING` | Evaluated on calibrated real audio fixture |

---

## 3. QUALITY GATES EVALUATION

| Quality Gate | Status | Score | Primary Rationale |
|---|---|---|---|
| **TECHNICAL_GATE** | `PASS` | 1.00 | Zero clipping; valid formats, sample rates, and channel layouts |
| **DYNAMIC_GATE** | `PASS` | 0.95 | Dynamic range and crest factors transparently preserved |
| **SPECTRAL_GATE** | `PASS` | 0.95 | Smooth spectral balance across bands |
| **DIALOGUE_GATE** | `WARNING` | 0.90 | Minor dialogue warning |
| **ARTIFACT_GATE** | `WARNING` | 0.88 | 5 non-fatal artifact warnings flagged for audit |
| **CONSISTENCY_GATE** | `PASS` | 0.96 | Long-form timeline consistent |

---

## 4. LONG-FORM STRESS TEST

- **Continuous Timeline**: 79.72s across 12 scene blocks
- **Overall Integrated Loudness**: `-17.8 LUFS`
- **Overall LRA**: `10.8 LU`
- **Max True Peak**: `-1.8 dBTP`
- **Loudness Drift (Max Δ)**: `13.5 dB`
- **Spectral Centroid Drift**: `10724.7 Hz`
- **Fatigue Risk Index**: `0.10` (Scale 0.0 - 1.0)
- **Status**: `PASS`

---

## 5. HUMAN REVIEW PACKAGES

| Fixture ID | QC Status | Perceptual Score | Flagged Artifacts | Audit Recommendation |
|---|---|---|---|---|
| `real_01_narration` | `PASS` | 1.00 | None | `HUMAN_AUDIT_RECOMMENDED` |
| `real_02_dialogue` | `PASS` | 1.00 | None | `HUMAN_AUDIT_RECOMMENDED` |
| `real_03_whisper` | `PASS` | 1.00 | 1 flagged | `HUMAN_AUDIT_RECOMMENDED` |
| `real_04_shouting` | `PASS` | 1.00 | None | `HUMAN_AUDIT_RECOMMENDED` |
| `real_05_emotional` | `PASS` | 1.00 | 1 flagged | `HUMAN_AUDIT_RECOMMENDED` |
| `real_06_hindi_hinglish` | `PASS` | 1.00 | None | `HUMAN_AUDIT_RECOMMENDED` |
| `real_07_music_heavy` | `PASS` | 0.96 | None | `HUMAN_AUDIT_RECOMMENDED` |
| `real_08_ambience` | `PASS` | 0.89 | 1 flagged | `HUMAN_AUDIT_RECOMMENDED` |
| `real_09_foley` | `PASS` | 0.96 | None | `HUMAN_AUDIT_RECOMMENDED` |
| `real_10_action` | `PASS` | 1.00 | None | `CLEAR` |
| `real_11_silence` | `PASS` | 0.89 | 2 flagged | `MANDATORY_REVIEW` |
| `real_12_difficult_tts` | `PASS` | 1.00 | None | `HUMAN_AUDIT_RECOMMENDED` |