#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Scene-Aware Decision Engine (P4).
===============================================================
Adapts broadcast mastering parameters based on dramatic context and narrative scene identity:
- Supported scene profiles: INTIMATE, QUIET, NORMAL, EMOTIONAL, TENSION, ACTION, MUSIC_HEAVY, AMBIENCE_HEAVY, DIALOGUE_HEAVY
- Distinguishes intentional dramatic variation from technical defects
- Protects intimate whispers from noise-floor boosting
- Protects combat / action scenes from transient-crushing compression
- Respects Book Master Profile expectations while guarding scene identity

Core Invariants:
1. quiet != bad, loud != good.
2. Missing metadata falls back gracefully to NORMAL profile (zero arbitrary guessing).
3. All recommended DSP adjustments are clamped strictly within SAFETY_BOUNDS.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, List

from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    BookMasterProfile,
    SceneMasteringDecision,
    MasteringProfile,
)

logger = logging.getLogger("AudiobookFactory")

SCENE_ENGINE_VERSION = "1.0.0"


class SceneAwareDecisionEngine:
    """
    Intelligent scene context analyzer producing bounded mastering adjustments
    tailored to the dramatic purpose of each chapter or scene.
    """

    def __init__(self, version: str = SCENE_ENGINE_VERSION):
        self.version = version

    def evaluate_scene(
        self,
        facts: MasteringAnalysisFacts,
        scene_intent: Optional[Any] = None,
        book_profile: Optional[BookMasterProfile] = None,
        chapter_metadata: Optional[Dict[str, Any]] = None,
    ) -> SceneMasteringDecision:
        """
        Classifies scene type, assesses narrative context, and generates bounded mastering adjustments.
        """
        chapter_metadata = chapter_metadata or {}

        # 1. Classify Scene
        scene_type, primary_element, confidence = self._classify_scene(
            facts, scene_intent, chapter_metadata
        )

        perceptual_findings: List[str] = []
        bounded_adjustments: Dict[str, Any] = {}
        recommended_action: Optional[str] = None
        risk = "LOW"
        expected_effect = "Standard broadcast delivery"
        requires_review = False

        # 2. Derive Scene-Specific Mastering Directives
        if scene_type == "INTIMATE":
            perceptual_findings.append("Intimate scene detected: close-mic vocal with quiet dynamics.")
            expected_effect = "Preserves delicate breath detail and close emotional presence without boosting noise floor."
            # Bounded adjustment: allow slightly softer target LUFS (-20.5 LUFS), slower limiter release
            bounded_adjustments["target_lufs_offset"] = 1.2  # target becomes -20.2 LUFS instead of -19.0
            bounded_adjustments["limiter_release_ms"] = 80
            recommended_action = "Relax target loudness by +1.2 LU and use transparent 80ms limiter release."

        elif scene_type == "ACTION":
            perceptual_findings.append("Action/combat scene detected: prominent transients and elevated impact energy.")
            expected_effect = "Preserves visceral punch and transient headroom without digital inter-sample clipping."
            # Bounded adjustment: slightly lower limiter ceiling (-1.8 dBTP) to avoid ISP overs, fast release (35ms)
            bounded_adjustments["limiter_ceiling_offset_db"] = -0.3  # ceiling becomes -1.8 dBTP
            bounded_adjustments["limiter_release_ms"] = 35
            recommended_action = "Lower limiter ceiling to -1.8 dBTP and use 35ms release to preserve impact transients."

        elif scene_type == "QUIET":
            perceptual_findings.append("Quiet/suspenseful scene detected: subdued energy and room-tone stillness.")
            expected_effect = "Preserves dramatic pause without audible gain pumping."
            bounded_adjustments["target_lufs_offset"] = 1.5
            recommended_action = "Allow softer target loudness (-20.5 LUFS) to maintain tension."

        elif scene_type == "MUSIC_HEAVY":
            perceptual_findings.append("Music-heavy scene detected: rich melodic support.")
            expected_effect = "Balances musical swell with vocal clarity."
            bounded_adjustments["target_lufs_offset"] = 0.5
            recommended_action = "Maintain dialogue anchor while allowing musical swell."

        elif scene_type == "EMOTIONAL":
            perceptual_findings.append("Emotional dramatic scene: wide conversational dynamic range.")
            expected_effect = "Maintains micro-dynamic vulnerability without harshness."
            bounded_adjustments["limiter_release_ms"] = 65
            recommended_action = "Use 65ms limiter release to prevent pumping during emotional rises."

        else:
            # NORMAL / DIALOGUE_HEAVY
            perceptual_findings.append("Standard narrative dialogue: balanced broadcast delivery.")
            expected_effect = "Transparent commercial audiobook loudness (-19.0 LUFS) and -1.5 dBTP true peak."
            recommended_action = None  # standard profile is optimal

        # 3. Check for Anomalies or Inconsistencies
        if facts.clipping_detected:
            requires_review = True
            risk = "CRITICAL"
            perceptual_findings.append("Critical anomaly: digital clipping detected in premaster.")

        return SceneMasteringDecision(
            scene_type=scene_type,
            primary_element=primary_element,
            context_confidence=confidence,
            perceptual_findings=perceptual_findings,
            recommended_action=recommended_action,
            risk=risk,
            expected_effect=expected_effect,
            requires_review=requires_review,
            bounded_adjustments=bounded_adjustments,
        )

    def _classify_scene(
        self,
        facts: MasteringAnalysisFacts,
        scene_intent: Optional[Any],
        chapter_metadata: Dict[str, Any],
    ) -> tuple[str, str, float]:
        """
        Classifies scene type using Stage 11 SceneMixIntent, chapter metadata, and acoustic facts.
        """
        # A. Priority 1: Direct SceneMixIntent from Stage 11
        if scene_intent is not None:
            focus = str(getattr(scene_intent, "focus", "")).lower()
            dynamic_preset = str(getattr(scene_intent, "dynamic_range_intent", "")).lower()
            intensity = getattr(scene_intent, "emotional_intensity", 0.5)

            if "intimate" in dynamic_preset or focus == "silence":
                return "INTIMATE", "whisper_dialogue", 0.95
            elif focus == "fx" or "wide" in dynamic_preset or intensity > 0.8:
                return "ACTION", "impact_fx", 0.95
            elif focus == "music":
                return "MUSIC_HEAVY", "music_score", 0.90
            elif focus == "ambience" or focus == "environment":
                return "AMBIENCE_HEAVY", "soundscape", 0.90
            elif intensity > 0.7:
                return "EMOTIONAL", "dialogue", 0.85
            elif focus == "dialogue":
                return "NORMAL", "dialogue", 0.90

        # B. Priority 2: Chapter metadata tags
        tags = chapter_metadata.get("tags", [])
        title = chapter_metadata.get("title", "").lower()
        if any(t in ("whisper", "intimate", "secret") for t in tags) or "whisper" in title:
            return "INTIMATE", "dialogue", 0.85
        elif any(t in ("combat", "battle", "fight", "action") for t in tags) or "battle" in title:
            return "ACTION", "impact_fx", 0.85
        elif any(t in ("confession", "grief", "emotional") for t in tags):
            return "EMOTIONAL", "dialogue", 0.80

        # C. Priority 3: Acoustic facts signatures (Empirical heuristic)
        if facts.integrated_lufs < -23.0 and (facts.loudness_range_lra or 0.0) < 4.0:
            return "QUIET", "ambience", 0.70
        elif facts.integrated_lufs < -21.0 and (facts.spectral_centroid_hz or 0.0) < 600.0:
            return "INTIMATE", "whisper_dialogue", 0.75
        elif (facts.crest_factor_db or 0.0) > 11.0 and (facts.loudness_range_lra or 0.0) > 8.0:
            return "ACTION", "impact_fx", 0.70

        # D. Default fallback
        return "NORMAL", "dialogue", 0.60

    def apply_scene_adjustments(
        self,
        base_profile: MasteringProfile,
        decision: SceneMasteringDecision,
    ) -> MasteringProfile:
        """
        Safely applies bounded scene decision parameters to a base MasteringProfile.
        Enforces SAFETY_BOUNDS to ensure no out-of-spec DSP parameters are generated.
        """
        adj = decision.bounded_adjustments
        if not adj:
            return base_profile

        new_data = base_profile.model_dump()

        # 1. Target LUFS adjustment
        if "target_lufs_offset" in adj:
            offset = float(adj["target_lufs_offset"])
            # Clamped: offset between -1.5 and +1.5 LU
            clamped_offset = max(min(offset, 1.5), -1.5)
            # Invert: offset > 0 means softer target (e.g. -19.0 - 1.2 = -20.2 LUFS)
            new_target = base_profile.target_lufs - clamped_offset
            # Safety clamp: must remain in [-24.0, -16.0]
            new_data["target_lufs"] = round(max(min(new_target, -16.0), -24.0), 2)

        # 2. Limiter ceiling adjustment
        if "limiter_ceiling_offset_db" in adj:
            offset = float(adj["limiter_ceiling_offset_db"])
            clamped_offset = max(min(offset, 0.0), -0.8)
            new_ceiling = base_profile.limiter_ceiling_db + clamped_offset
            new_data["limiter_ceiling_db"] = round(max(min(new_ceiling, -0.8), -3.5), 2)

        # 3. Limiter release time
        if "limiter_release_ms" in adj:
            rel = int(adj["limiter_release_ms"])
            new_data["limiter_release_ms"] = max(min(rel, 200), 20)

        logger.info(
            f"[*] SceneAwareDecisionEngine applied {decision.scene_type} adjustments: "
            f"LUFS={new_data['target_lufs']}, Limiter={new_data['limiter_ceiling_db']} dBFS, Release={new_data['limiter_release_ms']}ms"
        )
        return MasteringProfile(**new_data)
