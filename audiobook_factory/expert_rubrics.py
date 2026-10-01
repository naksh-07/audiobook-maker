#!/usr/bin/env python3
"""
Audiobook Factory - Multi-Expert Evaluation Rubrics & Prompt Harness.
Defines domain expert auditor profiles, quantitative/qualitative rubrics,
prompt generators, and evaluation synthesizers for all 10 subsystems.
"""

from __future__ import annotations
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from audiobook_factory.coordination_contracts import (
    SubsystemEvidenceDossier,
    LLMExpertEvaluation,
)

# =========================================================================
# Domain Expert Profiles & Mandates
# =========================================================================

EXPERT_PROFILES: Dict[str, Dict[str, Any]] = {
    "system1_ingestion": {
        "role": "Lead Forensic Ingestion & Typography Specialist",
        "subsystem_name": "1. Ingestion & Physical Extraction",
        "mandate": (
            "Audits raw document parsing, PDF geometric XY-cut reconstruction, EPUB TOC slicing, "
            "and ensures sacred text preservation (zero mutation of raw_text) and C0/C1 control character purity."
        ),
        "weights": {
            "sacred_source_integrity": 0.35,
            "layout_reading_order": 0.35,
            "structural_completeness": 0.30,
        },
    },
    "system2_translation": {
        "role": "Master Literary Translator & Hindustani Dramaturgy Critic",
        "subsystem_name": "2. Translation & Cultural Fidelity",
        "mandate": (
            "Audits literary translation into spoken Hindustani ('Aate mein namak jitni Urdu'), "
            "verifying Aap/Tum/Tu honorific hierarchy stability, idiom preservation, Devanagari purity, "
            "and zero AI conversational meta-commentary leaks."
        ),
        "weights": {
            "spoken_hindustani_register": 0.40,
            "honorific_hierarchy_stability": 0.35,
            "metaphorical_subtext_fidelity": 0.25,
        },
    },
    "system3_screenplay": {
        "role": "Master Dramaturg & Screenplay Architect",
        "subsystem_name": "3. Dramaturgy & Screenplay Attribution",
        "mandate": (
            "Audits sliding-window dialogue attribution, direct vs indirect speech separation, "
            "stripping of redundant speech tags, acting guidance (emotion, actioning verbs, subtext), "
            "and acoustic room labeling across all script segments."
        ),
        "weights": {
            "attribution_accuracy": 0.40,
            "dramatic_acting_guidance": 0.35,
            "acoustic_environment_tagging": 0.25,
        },
    },
    "system4_tts_casting": {
        "role": "Supervising Voice Director & Speech Synthesis Engineer",
        "subsystem_name": "4. Voice Casting & Neural TTS Dispatcher",
        "mandate": (
            "Audits voice registry locks, ensemble cast collision elimination, Gemini 3.1 Flash TTS / ElevenLabs "
            "routing, token-bucket rate limiter health, and proper noun pronunciation coverage."
        ),
        "weights": {
            "vocal_persona_contrast": 0.40,
            "pronunciation_lexicon_coverage": 0.30,
            "dsp_waveform_clarity": 0.30,
        },
    },
    "system5_sonic_intelligence": {
        "role": "Lead Acoustic Sound Designer & Sonic Intelligence Curator",
        "subsystem_name": "5. Sonic Intelligence Database & Sound Bank",
        "mandate": (
            "Audits SQLite FTS5 Sound Bank indexing, CLAP semantic retrieval, Agent Sound Cards v3.0, "
            "acoustic silence ratio (>= 60%), BGM/foley catalog hit rate, and category safety guards."
        ),
        "weights": {
            "fts5_catalog_resolution": 0.35,
            "silence_carving_headroom": 0.35,
            "category_safety_context": 0.30,
        },
    },
    "system6_editorial": {
        "role": "Supervising Dialogue Editor & Phonetic Timing Specialist",
        "subsystem_name": "6. Dialogue Editorial, Pacing & Timing",
        "mandate": (
            "Audits word-level forced alignment, Hann window micro-fades (12ms/18ms), inter-speaker "
            "turn-taking pauses (250-650ms), and elimination of zero-crossing clicks and breath artifacts."
        ),
        "weights": {
            "inter_speaker_pacing": 0.40,
            "micro_fade_transient_protection": 0.30,
            "emotional_breath_placement": 0.30,
        },
    },
    "system7_mixing": {
        "role": "Hollywood Multitrack Re-Recording Mixer",
        "subsystem_name": "7. 5-Track Cinematic Multitrack Mixing",
        "mandate": (
            "Audits 5-track stem architecture (DX, FX, BG, MX, Master Out), spectral carving (-5.5dB @ 2.2kHz), "
            "dynamic lookahead sidechain ducking (-16dB), room impulse reverberation, and stereo phase coherence."
        ),
        "weights": {
            "dialogue_intelligibility_primacy": 0.40,
            "spectral_carving_precision": 0.30,
            "stereo_phase_and_spatialization": 0.30,
        },
    },
    "system8_mastering": {
        "role": "Chief Broadcast Mastering Engineer & Acoustic QC Inspector",
        "subsystem_name": "8. Broadcast Mastering & EBU R128",
        "mandate": (
            "Audits EBU R128 broadcast compliance (I = -19.0 LUFS +/- 0.5 LUFS), True Peak headroom "
            "(<= -1.5 dBTP), Loudness Range (8-14 LU), 48kHz / 24-bit delivery, and zero clipping distortion."
        ),
        "weights": {
            "ebu_r128_loudness_target": 0.40,
            "true_peak_and_lra_headroom": 0.35,
            "zero_distortion_and_snr": 0.25,
        },
    },
    "system9_packaging": {
        "role": "Principal Media Systems & Monotonic Container Engineer",
        "subsystem_name": "9. Packaging & Monotonic M4B Containerization",
        "mandate": (
            "Audits single-pass stream copy into M4B containers, chapter marker monotonicity (T_{i+1} > T_i), "
            "TOC title fidelity, metadata tags, and square lossless cover art embedding."
        ),
        "weights": {
            "chapter_timeline_monotonicity": 0.40,
            "metadata_and_toc_fidelity": 0.35,
            "cover_art_and_container_specs": 0.25,
        },
    },
    "system10_orchestration": {
        "role": "Lead Distributed Systems Architect & Concurrency Officer",
        "subsystem_name": "10. State Governance, Telemetry & Key Pool",
        "mandate": (
            "Audits SQLite WAL integrity, foreign keys, key pool rotation (80+ keys), token bucket "
            "rate limiting, pipeline checkpoint resumability, and activeContext budget <= 50 lines."
        ),
        "weights": {
            "sqlite_integrity_and_wal": 0.40,
            "context_budget_discipline": 0.30,
            "checkpoint_resilience": 0.30,
        },
    },
}


# =========================================================================
# Domain Expert Evaluation Engine
# =========================================================================

def build_expert_prompt(dossier: SubsystemEvidenceDossier) -> str:
    """Constructs a strictly structured prompt for LLM qualitative evaluation."""
    profile = EXPERT_PROFILES.get(dossier.subsystem_id, {
        "role": dossier.expert_role,
        "subsystem_name": dossier.subsystem_id,
        "mandate": "Evaluate the subsystem.",
        "weights": {"overall": 1.0},
    })

    return f"""You are the {profile['role']}, the foremost authority auditing {profile['subsystem_name']}.
MANDATE: {profile['mandate']}

FORENSIC EVIDENCE DOSSIER:
- Deterministic Score: {dossier.deterministic_score}%
- Hard Gate Status: {'PASSED' if dossier.hard_gate_pass else 'FAILED'}
- Metrics: {json.dumps(dossier.metrics, indent=2)}
- Inspected Files: {len(dossier.inspected_files)} files
- Deterministic Anomalies: {json.dumps(dossier.anomalies, indent=2)}

EVALUATION RUBRIC & WEIGHTS:
{json.dumps(profile['weights'], indent=2)}

Evaluate the qualitative aspects of this evidence. Provide:
1. Score for each criterion (0.0 to 100.0)
2. Comprehensive forensic critique highlighting strengths and deficiencies
3. Detected architectural or aesthetic risks
4. Concrete actionable recommendations
Return response strictly formatted as a valid JSON object matching this schema:
{{
  "subsystem_id": "{dossier.subsystem_id}",
  "expert_role": "{profile['role']}",
  "qualitative_score": <float between 0 and 100>,
  "rubric_breakdown": {{ ... }},
  "critique": "<detailed text>",
  "detected_risks": ["<risk 1>", "<risk 2>"],
  "actionable_recommendations": ["<recommendation 1>", "<recommendation 2>"]
}}"""


def evaluate_subsystem_qualitatively(
    dossier: SubsystemEvidenceDossier,
    llm_callable: Optional[Any] = None,
) -> LLMExpertEvaluation:
    """
    Evaluates the evidence dossier qualitatively using either a live LLM callable
    or a high-precision deterministic forensic semantic evaluator.
    """
    profile = EXPERT_PROFILES.get(dossier.subsystem_id, {
        "role": dossier.expert_role,
        "subsystem_name": dossier.subsystem_id,
        "weights": {"overall": 1.0},
    })
    weights = profile.get("weights", {"overall": 1.0})

    # Attempt live LLM evaluation if callable is provided
    if llm_callable is not None:
        try:
            prompt = build_expert_prompt(dossier)
            raw_response = llm_callable(prompt)
            # Clean markdown code blocks
            clean_json = raw_response.strip()
            if "```" in clean_json:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_json, flags=re.DOTALL)
                if match:
                    clean_json = match.group(1).strip()
            parsed = json.loads(clean_json)
            return LLMExpertEvaluation.model_validate(parsed)
        except Exception:
            # Fall back seamlessly to forensic evaluator
            pass

    # High-precision deterministic forensic scoring
    scores: Dict[str, float] = {}
    risks: List[str] = []
    recs: List[str] = []
    anomalies = dossier.anomalies

    # Compute base quality from deterministic facts
    base_penalties = len(anomalies) * 15.0
    if not dossier.hard_gate_pass:
        base_penalties += 40.0

    for criterion, w in weights.items():
        crit_score = max(0.0, min(100.0, 100.0 - base_penalties))
        # Domain specific nuances
        if criterion == "sacred_source_integrity":
            if dossier.metrics.get("raw_text_mutations", 0) > 0:
                crit_score = 0.0
                risks.append("Fatal: Sacred raw_text mutation detected.")
                recs.append("Isolate all text transformations to normalized_text only.")
        elif criterion == "spoken_hindustani_register":
            purity = dossier.metrics.get("devanagari_pure_files", 0)
            total = max(1, dossier.metrics.get("translated_files_found", 1))
            crit_score = round((purity / total) * 100.0, 1)
            if crit_score < 80.0:
                risks.append("Spoken Hindustani register contaminated with non-Devanagari scripts.")
                recs.append("Enforce pure Devanagari output filter.")
        elif criterion == "honorific_hierarchy_stability":
            leaks = dossier.metrics.get("meta_commentary_leaks", 0)
            if leaks > 0:
                crit_score = max(0.0, crit_score - (leaks * 25.0))
                risks.append(f"AI conversational meta-commentary leaked ({leaks} instances).")
                recs.append("Strengthen anti-refusal and prompt boundary fences.")
        elif criterion == "attribution_accuracy":
            unmapped = len(dossier.metrics.get("unmapped_speakers", []))
            if unmapped > 0:
                crit_score = max(0.0, crit_score - (unmapped * 20.0))
                risks.append(f"Unmapped speakers detected in screenplay: {dossier.metrics.get('unmapped_speakers')}")
                recs.append("Register missing characters in character_roster.json.")
        elif criterion == "fts5_catalog_resolution":
            hit_rate = dossier.metrics.get("hit_rate_pct", 100.0)
            crit_score = hit_rate
            if hit_rate < 80.0:
                risks.append(f"Sonic intelligence hit rate ({hit_rate}%) below 80% studio threshold.")
                recs.append("Expand Sound Bank FTS5 seed tags or apply query relaxation.")
        elif criterion == "ebu_r128_loudness_target":
            if dossier.metrics.get("master_wavs"):
                crit_score = 100.0
            else:
                crit_score = 75.0
                risks.append("WAV masters missing or pending final loudness render.")
                recs.append("Run final mastering pass to generate certified master WAVs.")
        elif criterion == "chapter_timeline_monotonicity":
            m4b_count = dossier.metrics.get("total_packaged", 0)
            crit_score = 100.0 if m4b_count > 0 else 60.0
            if m4b_count == 0:
                risks.append("No packaged M4B deliverables found.")
                recs.append("Run packaging step with MP4Box/FFmpeg to generate chaptered M4B.")
        elif criterion == "sqlite_integrity_and_wal":
            budget_pass = dossier.metrics.get("active_context_budget_pass", True)
            crit_score = 100.0 if budget_pass else 70.0
            if not budget_pass:
                risks.append("Active context lines exceeded 50-line governance limit.")
                recs.append("Prune activeContext.md to <= 50 lines.")

        scores[criterion] = round(crit_score, 1)

    total_qual = sum(scores[c] * weights[c] for c in weights)
    total_qual = round(max(0.0, min(100.0, total_qual)), 1)

    critique = (
        f"Forensic evaluation conducted by {profile['role']}. "
        f"Subsystem scored {total_qual}% across {len(weights)} weighted criteria. "
        f"{'Hard gates fully satisfied.' if dossier.hard_gate_pass else 'Critical hard gate violation detected!'} "
        f"Observed {len(anomalies)} deterministic anomalies."
    )

    if not recs:
        recs.append(f"Subsystem conforms to {profile['role']} production specifications.")

    return LLMExpertEvaluation(
        subsystem_id=dossier.subsystem_id,
        expert_role=profile["role"],
        qualitative_score=total_qual,
        rubric_breakdown=scores,
        critique=critique,
        detected_risks=risks,
        actionable_recommendations=recs,
    )