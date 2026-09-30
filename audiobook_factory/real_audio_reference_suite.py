#!/usr/bin/env python3
"""
Audiobook Factory - Real Audio Reference Suite (Phase 3).
=========================================================
Governs target-quality reference profiles and expected acoustic behavior.
Enforces the core principle:
REFERENCE != TRUTH
Closer to reference does NOT automatically mean better;
natural narrative performances can legitimately vary.
Reference comparison captures:
deviation + risk + context
without blindly forcing audio toward a static target.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from audiobook_factory.mastering_contracts import MasteringAnalysisFacts


class ReferenceAudioProfile(BaseModel):
    """Target-quality reference definition for a specific scene or performance type."""
    reference_id: str
    scene_type: str
    language: str = "en"
    performance_type: str = "natural"
    target_lufs: float = -19.0
    lufs_tolerance: float = 0.5
    true_peak_ceiling_dbtp: float = -1.5
    expected_lra_min: float = 5.0
    expected_lra_max: float = 12.0
    expected_centroid_min_hz: float = 300.0
    expected_centroid_max_hz: float = 3500.0
    dialogue_to_bed_ratio_min_db: float = 1.0
    known_constraints: List[str] = Field(default_factory=list)
    source_provenance: str = "Audiobook Factory Calibrated Reference Standard"


class ReferenceDeviationReport(BaseModel):
    """Diagnostic comparison against reference profile."""
    reference_id: str
    scene_type: str
    lufs_deviation: float
    lra_deviation: float
    true_peak_margin: float
    spectral_deviation_hz: float
    is_within_tolerance: bool
    context_risks: List[str] = Field(default_factory=list)
    recommendation: str = "NO_ACTION"
    confidence: float = 0.90


CANONICAL_REFERENCES: Dict[str, ReferenceAudioProfile] = {
    "ref_narration_standard": ReferenceAudioProfile(
        reference_id="ref_narration_standard",
        scene_type="narration",
        language="en",
        performance_type="formal_narration",
        target_lufs=-19.0,
        lufs_tolerance=0.5,
        true_peak_ceiling_dbtp=-1.5,
        expected_lra_min=5.0,
        expected_lra_max=9.5,
        expected_centroid_min_hz=400.0,
        expected_centroid_max_hz=2800.0,
        dialogue_to_bed_ratio_min_db=3.0,
        known_constraints=["Must maintain pristine vocal clarity and zero fatigue across sustained listening."],
    ),
    "ref_dialogue_cinematic": ReferenceAudioProfile(
        reference_id="ref_dialogue_cinematic",
        scene_type="dialogue",
        language="en",
        performance_type="conversational",
        target_lufs=-19.0,
        lufs_tolerance=0.6,
        true_peak_ceiling_dbtp=-1.5,
        expected_lra_min=6.0,
        expected_lra_max=11.0,
        expected_centroid_min_hz=350.0,
        expected_centroid_max_hz=3200.0,
        dialogue_to_bed_ratio_min_db=2.0,
        known_constraints=["Preserve distinct vocal timbres and natural conversational turn-taking."],
    ),
    "ref_whisper_intimate": ReferenceAudioProfile(
        reference_id="ref_whisper_intimate",
        scene_type="whisper",
        language="en",
        performance_type="intimate",
        target_lufs=-22.0,  # Legitimate quiet target
        lufs_tolerance=2.5,
        true_peak_ceiling_dbtp=-2.0,
        expected_lra_min=4.0,
        expected_lra_max=9.0,
        expected_centroid_min_hz=300.0,
        expected_centroid_max_hz=2200.0,
        dialogue_to_bed_ratio_min_db=1.5,
        known_constraints=["Do NOT squash or artificially boost whisper to broadcast speech levels."],
    ),
    "ref_shouting_dynamic": ReferenceAudioProfile(
        reference_id="ref_shouting_dynamic",
        scene_type="shouting",
        language="en",
        performance_type="aggressive",
        target_lufs=-18.0,
        lufs_tolerance=1.0,
        true_peak_ceiling_dbtp=-1.5,
        expected_lra_min=7.0,
        expected_lra_max=13.0,
        expected_centroid_min_hz=600.0,
        expected_centroid_max_hz=3600.0,
        dialogue_to_bed_ratio_min_db=3.0,
        known_constraints=["Zero clipping on transient peaks; maintain vocal power without shrill fatigue."],
    ),
    "ref_emotional_drama": ReferenceAudioProfile(
        reference_id="ref_emotional_drama",
        scene_type="emotional",
        language="en",
        performance_type="dramatic",
        target_lufs=-19.5,
        lufs_tolerance=1.5,
        true_peak_ceiling_dbtp=-1.5,
        expected_lra_min=6.5,
        expected_lra_max=12.5,
        expected_centroid_min_hz=350.0,
        expected_centroid_max_hz=3000.0,
        dialogue_to_bed_ratio_min_db=2.0,
        known_constraints=["Preserve trembling vocal micro-dynamics and emotional decay tails."],
    ),
    "ref_hindi_authentic": ReferenceAudioProfile(
        reference_id="ref_hindi_authentic",
        scene_type="hindi_hinglish",
        language="hi",
        performance_type="natural_hindustani",
        target_lufs=-19.0,
        lufs_tolerance=0.7,
        true_peak_ceiling_dbtp=-1.5,
        expected_lra_min=5.5,
        expected_lra_max=10.5,
        expected_centroid_min_hz=400.0,
        expected_centroid_max_hz=3100.0,
        dialogue_to_bed_ratio_min_db=2.5,
        known_constraints=["Preserve retroflex consonants, aspirated phonemes, and colloquial cadence."],
    ),
    "ref_action_epic": ReferenceAudioProfile(
        reference_id="ref_action_epic",
        scene_type="action",
        language="en",
        performance_type="intense_soundscape",
        target_lufs=-18.5,
        lufs_tolerance=1.0,
        true_peak_ceiling_dbtp=-1.5,
        expected_lra_min=8.0,
        expected_lra_max=14.0,
        expected_centroid_min_hz=250.0,
        expected_centroid_max_hz=3800.0,
        dialogue_to_bed_ratio_min_db=1.5,
        known_constraints=["Limiter must not pump during rapid transitions between explosions and dialogue."],
    ),
    "ref_ambience_foley": ReferenceAudioProfile(
        reference_id="ref_ambience_foley",
        scene_type="ambience",
        language="non_speech",
        performance_type="environmental",
        target_lufs=-24.0,
        lufs_tolerance=3.0,
        true_peak_ceiling_dbtp=-2.0,
        expected_lra_min=4.0,
        expected_lra_max=12.0,
        expected_centroid_min_hz=200.0,
        expected_centroid_max_hz=4500.0,
        dialogue_to_bed_ratio_min_db=0.0,
        known_constraints=["Subtle room tone and environmental texture must remain transparent."],
    ),
    "ref_silence_dramatic": ReferenceAudioProfile(
        reference_id="ref_silence_dramatic",
        scene_type="silence",
        language="non_speech",
        performance_type="dramatic_pause",
        target_lufs=-45.0,
        lufs_tolerance=15.0,
        true_peak_ceiling_dbtp=-10.0,
        expected_lra_min=2.0,
        expected_lra_max=10.0,
        expected_centroid_min_hz=100.0,
        expected_centroid_max_hz=2000.0,
        dialogue_to_bed_ratio_min_db=0.0,
        known_constraints=["Intentional silence must not trigger gate pumping or noise floor boost."],
    ),
    "ref_difficult_tts": ReferenceAudioProfile(
        reference_id="ref_difficult_tts",
        scene_type="difficult_tts",
        language="en",
        performance_type="stressed_speech",
        target_lufs=-19.0,
        lufs_tolerance=1.0,
        true_peak_ceiling_dbtp=-1.5,
        expected_lra_min=4.0,
        expected_lra_max=10.0,
        expected_centroid_min_hz=400.0,
        expected_centroid_max_hz=3500.0,
        dialogue_to_bed_ratio_min_db=2.0,
        known_constraints=["Mastering must tame harsh sibilance without obliterating consonant intelligibility."],
    ),
}


class RealAudioReferenceSuite:
    """Evaluates master deliverables against canonical target references."""

    def __init__(self, profiles: Optional[Dict[str, ReferenceAudioProfile]] = None):
        self.profiles = profiles or CANONICAL_REFERENCES

    def evaluate(self, facts: MasteringAnalysisFacts, scene_type: str) -> ReferenceDeviationReport:
        # Match closest profile
        profile_key = f"ref_{scene_type}_standard"
        if profile_key not in self.profiles:
            # Fallback matching
            matches = [k for k in self.profiles if scene_type in k]
            profile_key = matches[0] if matches else "ref_narration_standard"

        ref = self.profiles[profile_key]
        lufs_dev = round(facts.integrated_lufs - ref.target_lufs, 2)
        lra = facts.loudness_range_lra or 8.0
        lra_dev = 0.0
        if lra < ref.expected_lra_min:
            lra_dev = round(lra - ref.expected_lra_min, 2)
        elif lra > ref.expected_lra_max:
            lra_dev = round(lra - ref.expected_lra_max, 2)

        tp = facts.true_peak_dbtp if facts.true_peak_dbtp is not None else -1.5
        tp_margin = round(ref.true_peak_ceiling_dbtp - tp, 2)

        sc = facts.spectral_centroid_hz or 1000.0
        sc_dev = 0.0
        if sc < ref.expected_centroid_min_hz:
            sc_dev = round(sc - ref.expected_centroid_min_hz, 1)
        elif sc > ref.expected_centroid_max_hz:
            sc_dev = round(sc - ref.expected_centroid_max_hz, 1)

        risks = []
        is_ok = True
        if abs(lufs_dev) > ref.lufs_tolerance:
            risks.append(f"Loudness deviation of {lufs_dev} LU exceeds reference tolerance ±{ref.lufs_tolerance} LU")
            is_ok = False
        if tp_margin < 0.0:
            risks.append(f"True peak exceeds reference ceiling by {abs(tp_margin)} dBTP")
            is_ok = False
        if abs(lra_dev) > 3.0:
            risks.append(f"LRA deviation of {lra_dev} LU outside expected reference envelope")

        rec = "NO_ACTION"
        if not is_ok:
            rec = "REVIEW_INTENTIONAL_ARTISTIC_DEVIATION" if scene_type in ("whisper", "silence", "action") else "ADJUST_GAIN_CEILING"

        return ReferenceDeviationReport(
            reference_id=ref.reference_id,
            scene_type=scene_type,
            lufs_deviation=lufs_dev,
            lra_deviation=lra_dev,
            true_peak_margin=tp_margin,
            spectral_deviation_hz=sc_dev,
            is_within_tolerance=is_ok,
            context_risks=risks,
            recommendation=rec,
            confidence=0.88,
        )
