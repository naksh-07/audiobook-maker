# Chapter 9 Hardening Verification Benchmark Report

## 1. Executive Summary
The Chapter 9 standard benchmark was executed non-destructively against `scene_001` and `scene_002`.
All artifacts were saved to `audiobooks/standards/chapter_009_hardened_benchmark/`.
Canonical standard files (`chapter_009_hi_old_canonical.md`, `chapter_009_hi_standard.md`, `chapter_009_hi.md`) remain 100% untouched.

## 2. Before vs. After Semantic Extraction Metrics

| Metric | scene_001 (Old) | scene_001 (Hardened) | scene_002 (Old) | scene_002 (Hardened) |
| :--- | :--- | :--- | :--- | :--- |
| **Total Propositions (Beats)** | 191 | 191 | 48 | 48 |
| **Action Extraction Rate** | 0/191 (0.0%) | **191/191 (100.0%)** | 0/48 (0.0%) | **48/48 (100.0%)** |
| **Actor Population Rate** | 29/191 (15.2%) | **92/191 (48.2%)** | 4/48 (8.3%) | **29/48 (60.4%)** |
| **Dialogue Beats Tracked** | 62 | 151 | 10 | 31 |
| **Time Markers Extracted** | 0 (Field missing) | **13** | 0 (Field missing) | **5** |
| **Location Markers Extracted** | 0 (Field missing) | **11** | 0 (Field missing) | **2** |

## 3. Target Semantic Map & Alignment Verification

### Scene 1 Alignment
- **Paragraphs**: 60 Source $\leftrightarrow$ 54 Target
- **Negation Parity**: False
- **Average Beat Coverage**: 1.641
- **Affected Paragraphs**: [1, 2, 3, 4, 7, 11, 12, 13, 16, 20, 21, 22, 23, 24, 25, 27, 28, 29, 30, 31, 33, 34, 35, 37, 38, 39, 40, 41, 42, 43, 44, 45, 47, 49, 50, 51, 52, 54, 59]

### Scene 2 Alignment
- **Paragraphs**: 15 Source $\leftrightarrow$ 14 Target
- **Negation Parity**: False
- **Average Beat Coverage**: 1.27
- **Affected Paragraphs**: [0, 1, 3, 4, 5, 7, 8, 9, 10, 11]

## 4. Literary Intensity Calibration (Gate T8)

| Dimension / Metric | scene_001 Source | scene_001 Target | scene_002 Source | scene_002 Target |
| :--- | :--- | :--- | :--- | :--- |
| **Profanity** | 0.2 | 0.0 | 0.3 | 0.0 |
| **Violence** | 0.1 | 0.1 | 0.2 | 0.0 |
| **Emotional Intensity** | 3.8 | 5.0 | 2.6 | 5.0 |
| **Max Delta** | **2.7** | - | **2.4** | - |
| **Gate T8 Status** | **FAIL** | - | **FAIL** | - |

## 5. Certification Gate Status Summary

- **Scene 1 Status**: `REVIEW_REQUIRED` (Certified: False)
- **Scene 2 Status**: `REVIEW_REQUIRED` (Certified: False)

```json
{
  "scene_001": {
    "old": {
      "beats": 191,
      "actors_populated": "29/191 (15.2%)",
      "action_populated": "0/191 (0.0%)",
      "dialogue_beats": 62,
      "negation_beats": 34
    },
    "new": {
      "beats": 191,
      "actors_populated": "92/191 (48.2%)",
      "action_populated": "191/191 (100.0%)",
      "dialogue_beats": 151,
      "negation_beats": 39,
      "time_markers_extracted": 13,
      "location_markers_extracted": 11
    },
    "alignment": {
      "total_source_paragraphs": 60,
      "total_target_paragraphs": 54,
      "overall_negation_parity": false,
      "average_coverage": 1.641,
      "affected_paragraphs": [
        1,
        2,
        3,
        4,
        7,
        11,
        12,
        13,
        16,
        20,
        21,
        22,
        23,
        24,
        25,
        27,
        28,
        29,
        30,
        31,
        33,
        34,
        35,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
        44,
        45,
        47,
        49,
        50,
        51,
        52,
        54,
        59
      ]
    },
    "intensity": {
      "source_profanity": 0.2,
      "source_violence": 0.1,
      "source_emotional": 3.8,
      "target_profanity": 0.0,
      "target_violence": 0.1,
      "target_emotional": 5.0,
      "max_delta": 2.7,
      "status": "FAIL"
    },
    "certification": {
      "overall_status": "REVIEW_REQUIRED",
      "certified": false,
      "gates": {
        "T0_source_integrity": "PASS",
        "T5_terminology": "PASS",
        "T2_semantic_fidelity": "FAIL",
        "T3_omission": "PASS",
        "T4_addition": "PASS",
        "T7_character_voice": "PASS",
        "T8_intensity": "FAIL",
        "T9_naturalness": "PASS",
        "T10_register_balance": "PASS"
      },
      "affected_paragraphs": [
        1,
        2,
        3,
        4,
        7,
        11,
        12,
        13,
        16,
        20,
        21,
        22,
        23,
        24,
        25,
        27,
        28,
        29,
        30,
        31,
        33,
        34,
        35,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
        44,
        45,
        47,
        49,
        50,
        51,
        52,
        54,
        59
      ]
    }
  },
  "scene_002": {
    "old": {
      "beats": 48,
      "actors_populated": "4/48 (8.3%)",
      "action_populated": "0/48 (0.0%)",
      "dialogue_beats": 10,
      "negation_beats": 9
    },
    "new": {
      "beats": 48,
      "actors_populated": "29/48 (60.4%)",
      "action_populated": "48/48 (100.0%)",
      "dialogue_beats": 31,
      "negation_beats": 9,
      "time_markers_extracted": 5,
      "location_markers_extracted": 2
    },
    "alignment": {
      "total_source_paragraphs": 15,
      "total_target_paragraphs": 14,
      "overall_negation_parity": false,
      "average_coverage": 1.27,
      "affected_paragraphs": [
        0,
        1,
        3,
        4,
        5,
        7,
        8,
        9,
        10,
        11
      ]
    },
    "intensity": {
      "source_profanity": 0.3,
      "source_violence": 0.2,
      "source_emotional": 2.6,
      "target_profanity": 0.0,
      "target_violence": 0.0,
      "target_emotional": 5.0,
      "max_delta": 2.4,
      "status": "FAIL"
    },
    "certification": {
      "overall_status": "REVIEW_REQUIRED",
      "certified": false,
      "gates": {
        "T0_source_integrity": "PASS",
        "T5_terminology": "PASS",
        "T2_semantic_fidelity": "FAIL",
        "T3_omission": "PASS",
        "T4_addition": "PASS",
        "T7_character_voice": "PASS",
        "T8_intensity": "FAIL",
        "T9_naturalness": "PASS",
        "T10_register_balance": "PASS"
      },
      "affected_paragraphs": [
        0,
        1,
        3,
        4,
        5,
        7,
        8,
        9,
        10,
        11
      ]
    }
  }
}
```
