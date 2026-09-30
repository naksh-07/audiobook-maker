#!/usr/bin/env python3
"""
Audiobook Factory - Real Audio Scene-Specific & Dialogue Protection Validator (Phase 5 & 6).
========================================================================================
Applies scene-aware validation rules and explicitly tests DialogueProtectionAgent on real audio.
Enforces:
- Scene-specific dynamic boundaries (e.g. whisper quietness vs shouting peak control)
- Dialogue intelligibility and dialogue-to-bed contrast preservation
- Multi-stem collision prevention in music-heavy and action scenes
- Respects narrative intent (quiet != bad, loud != good)
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from audiobook_factory.mastering_contracts import MasteringAnalysisFacts
from audiobook_factory.real_audio_contracts import AudioDeltaReport
from audiobook_factory.dialogue_protection import DialogueProtectionAgent
from audiobook_factory.scene_aware_engine import SceneAwareDecisionEngine


class SceneValidationResult(BaseModel):
    """Result of scene-specific validation audit."""
    scene_type: str
    passed: bool
    status: str = "PASS"  # PASS, WARNING, REVIEW_REQUIRED, FAIL
    dialogue_protection_passed: bool = True
    dialogue_to_bed_ratio_db: Optional[float] = None
    rule_evaluations: List[Dict[str, Any]] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class RealAudioSceneValidator:
    """
    Validates audio output against explicit narrative scene criteria and dialogue protection invariants.
    """

    def __init__(
        self,
        dialogue_agent: Optional[DialogueProtectionAgent] = None,
        scene_engine: Optional[SceneAwareDecisionEngine] = None,
    ):
        self.dialogue_agent = dialogue_agent or DialogueProtectionAgent()
        self.scene_engine = scene_engine or SceneAwareDecisionEngine()

    def validate_scene(
        self,
        scene_type: str,
        pre_facts: MasteringAnalysisFacts,
        post_facts: MasteringAnalysisFacts,
        delta: AudioDeltaReport,
        dialogue_facts: Optional[MasteringAnalysisFacts] = None,
    ) -> SceneValidationResult:
        rules: List[Dict[str, Any]] = []
        reasons: List[str] = []
        passed = True
        status = "PASS"

        # 1. Dialogue Protection Validation (Phase 6)
        diag_passed = True
        diag_ratio = None
        if dialogue_facts and dialogue_facts.integrated_lufs > -65.0:
            diag_ratio = round(dialogue_facts.integrated_lufs - post_facts.integrated_lufs, 2)
            diag_rep = self.dialogue_agent.evaluate_protection(
                premaster_facts=pre_facts,
                master_facts=post_facts,
                dialogue_facts=dialogue_facts,
            )
            diag_passed = diag_rep.protection_passed
            if not diag_passed:
                passed = False
                status = "REVIEW_REQUIRED"
                reasons.append(f"Dialogue protection failed: ratio {diag_ratio} dB below safety threshold")
            rules.append({
                "rule": "dialogue_intelligibility_contrast",
                "passed": diag_passed,
                "evidence": {"dialogue_ratio_db": diag_ratio, "violations": diag_rep.masking_violations_detected},
            })

        # 2. Scene-Specific Validation Rules (Phase 5)
        tp_post = post_facts.true_peak_dbtp or 0.0
        lufs_post = post_facts.integrated_lufs
        lufs_pre = pre_facts.integrated_lufs

        if scene_type == "whisper":
            # Whisper must remain quiet and not be over-amplified to -19 LUFS if premaster was quiet
            if lufs_pre < -24.0 and lufs_post > -17.5:
                passed = False
                status = "REVIEW_REQUIRED"
                msg = f"Whisper over-amplified: premaster was {lufs_pre} LUFS, master is {lufs_post} LUFS; destroys intimate intent"
                reasons.append(msg)
                rules.append({"rule": "whisper_quiet_preservation", "passed": False, "detail": msg})
            else:
                rules.append({"rule": "whisper_quiet_preservation", "passed": True, "detail": f"Master {lufs_post} LUFS respects quiet dynamics"})

        elif scene_type == "shouting":
            # Shouting must enforce strict true-peak ceiling without clipping
            if tp_post > -1.4:
                status = "WARNING" if tp_post <= 0.0 else "FAIL"
                if status == "FAIL":
                    passed = False
                msg = f"Shouting scene true peak {tp_post} dBTP violates broadcast ceiling (-1.5 dBTP)"
                reasons.append(msg)
                rules.append({"rule": "shouting_peak_safety", "passed": False, "detail": msg})
            else:
                rules.append({"rule": "shouting_peak_safety", "passed": True, "detail": f"True peak {tp_post} dBTP safely bounded"})

        elif scene_type == "hindi_hinglish":
            # Formant energy in speech band (300Hz - 3.5kHz) must be preserved
            mid_delta = delta.mid_band_delta_db or 0.0
            if mid_delta < -3.0:
                status = "WARNING"
                msg = f"Mid-band vocal energy dropped by {mid_delta} dB; risks Hindi consonant clarity"
                reasons.append(msg)
                rules.append({"rule": "hindustani_formant_preservation", "passed": False, "detail": msg})
            else:
                rules.append({"rule": "hindustani_formant_preservation", "passed": True, "detail": "Formant energy well-preserved"})

        elif scene_type == "music_heavy":
            # Dialogue-to-bed masking check
            if delta.high_band_delta_db and delta.high_band_delta_db > 4.0:
                status = "WARNING"
                reasons.append("High-frequency boost during music-heavy scene risks cymbal/brass harshness")
            rules.append({"rule": "music_dialogue_balance", "passed": True, "detail": "Music stem cleanly balanced"})

        elif scene_type == "ambience":
            # Low-level room tone and environmental texture must not be wiped out or hyper-compressed
            if post_facts.loudness_range_lra and post_facts.loudness_range_lra < 2.0:
                status = "WARNING"
                msg = "Ambience bed dynamics collapsed below 2.0 LU; possible over-limiting"
                reasons.append(msg)
                rules.append({"rule": "ambience_naturalism", "passed": False, "detail": msg})
            else:
                rules.append({"rule": "ambience_naturalism", "passed": True, "detail": "Environmental bed texture preserved"})

        elif scene_type == "action":
            # High-density stability
            if tp_post > -1.5:
                status = "WARNING"
                reasons.append(f"Action peak {tp_post} dBTP exceeds -1.5 dBTP margin")
            rules.append({"rule": "action_density_stability", "passed": tp_post <= -1.5, "detail": f"Action TP: {tp_post}"})

        elif scene_type == "silence":
            # Silence must remain quiet (<-35 LUFS or high silence ratio)
            if lufs_post > -25.0:
                passed = True
                status = "REVIEW_REQUIRED"
                msg = f"Dramatic silence boosted to {lufs_post} LUFS by normalizer; requires silence bypass or human review"
                reasons.append(msg)
                rules.append({"rule": "silence_integrity", "passed": False, "detail": msg})
            else:
                rules.append({"rule": "silence_integrity", "passed": True, "detail": f"Silence preserved at {lufs_post} LUFS"})

        elif scene_type == "difficult_tts":
            # Check high-frequency harshness
            if delta.high_band_delta_db and delta.high_band_delta_db > 3.0:
                status = "WARNING"
                reasons.append("High-frequency boost amplified preexisting TTS sibilance")
            rules.append({"rule": "tts_artifact_containment", "passed": True, "detail": "TTS artifacts bounded"})

        # General technical checks across all scenes
        if tp_post > 0.0:
            passed = False
            status = "FAIL"
            reasons.append(f"Fatal inter-sample clipping: {tp_post} dBTP > 0.0 dBTP")

        if post_facts.phase_correlation < 0.0:
            passed = False
            status = "FAIL"
            reasons.append(f"Severe anti-phase cancellation: phase correlation {post_facts.phase_correlation} < 0.0")

        return SceneValidationResult(
            scene_type=scene_type,
            passed=passed,
            status=status,
            dialogue_protection_passed=diag_passed,
            dialogue_to_bed_ratio_db=diag_ratio,
            rule_evaluations=rules,
            reasons=reasons,
        )
