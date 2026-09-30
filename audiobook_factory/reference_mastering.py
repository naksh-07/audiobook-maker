#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Reference Mastering (P4).
======================================================
Provides contextual acoustic and perceptual benchmarking against versioned reference profiles:
- Reference types: narration, dialogue, intimate, emotional, action, quiet, music_heavy
- Extracts normalized profiles (LUFS, crest, dynamic range, spectral centroid, phase)
- Evaluates contextual match: MATCH, MILD_DEVIATION, SIGNIFICANT_DEVIATION, INAPPROPRIATE_COMPARISON

Core Invariants:
1. REFERENCE != TRUTH: A reference is advisory evidence, never a command.
2. Contextual appropriateness: Comparing an intimate whisper to an action profile is rejected as INAPPROPRIATE_COMPARISON.
3. Reference matching is optional: If no reference exists, the pipeline degrades gracefully with zero errors.
"""

from __future__ import annotations
import logging
from typing import Dict, Any, Optional, List

from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    ReferenceProfile,
    ReferenceComparisonResult,
)

logger = logging.getLogger("AudiobookFactory")

REFERENCE_SCHEMA_VERSION = "1.0.0"

# Canonical studio benchmarks for audiobook production
CANONICAL_REFERENCE_PROFILES: Dict[str, ReferenceProfile] = {
    "narration": ReferenceProfile(
        reference_id="canonical_narration_v1",
        reference_type="narration",
        version=REFERENCE_SCHEMA_VERSION,
        target_lufs=-19.0,
        dynamic_range_db=7.5,
        crest_factor_db=9.5,
        spectral_centroid_hz=1150.0,
        tolerance_lufs=1.0,
        tolerance_crest=2.5,
        metadata={"description": "Standard narrative voice delivery with high intelligibility."},
    ),
    "dialogue": ReferenceProfile(
        reference_id="canonical_dialogue_v1",
        reference_type="dialogue",
        version=REFERENCE_SCHEMA_VERSION,
        target_lufs=-19.5,
        dynamic_range_db=7.0,
        crest_factor_db=9.0,
        spectral_centroid_hz=1200.0,
        tolerance_lufs=1.2,
        tolerance_crest=2.5,
        metadata={"description": "Multi-speaker character dialogue interaction."},
    ),
    "intimate": ReferenceProfile(
        reference_id="canonical_intimate_v1",
        reference_type="intimate",
        version=REFERENCE_SCHEMA_VERSION,
        target_lufs=-21.0,
        dynamic_range_db=6.5,
        crest_factor_db=8.0,
        spectral_centroid_hz=950.0,
        tolerance_lufs=1.8,
        tolerance_crest=3.0,
        metadata={"description": "Intimate close-mic whisper or quiet conversational confession."},
    ),
    "emotional": ReferenceProfile(
        reference_id="canonical_emotional_v1",
        reference_type="emotional",
        version=REFERENCE_SCHEMA_VERSION,
        target_lufs=-19.5,
        dynamic_range_db=8.5,
        crest_factor_db=10.5,
        spectral_centroid_hz=1300.0,
        tolerance_lufs=1.5,
        tolerance_crest=3.0,
        metadata={"description": "Dramatic scene with wide dynamic vulnerability."},
    ),
    "action": ReferenceProfile(
        reference_id="canonical_action_v1",
        reference_type="action",
        version=REFERENCE_SCHEMA_VERSION,
        target_lufs=-18.5,
        dynamic_range_db=10.0,
        crest_factor_db=12.0,
        spectral_centroid_hz=1600.0,
        tolerance_lufs=1.5,
        tolerance_crest=3.5,
        metadata={"description": "High-intensity action and combat soundscape with punchy transients."},
    ),
    "quiet": ReferenceProfile(
        reference_id="canonical_quiet_v1",
        reference_type="quiet",
        version=REFERENCE_SCHEMA_VERSION,
        target_lufs=-22.5,
        dynamic_range_db=5.5,
        crest_factor_db=7.0,
        spectral_centroid_hz=850.0,
        tolerance_lufs=2.0,
        tolerance_crest=3.0,
        metadata={"description": "Tense stillness, room tone, and subtle environmental bed."},
    ),
    "music_heavy": ReferenceProfile(
        reference_id="canonical_music_heavy_v1",
        reference_type="music_heavy",
        version=REFERENCE_SCHEMA_VERSION,
        target_lufs=-18.0,
        dynamic_range_db=9.0,
        crest_factor_db=11.0,
        spectral_centroid_hz=1400.0,
        tolerance_lufs=1.2,
        tolerance_crest=3.0,
        metadata={"description": "Orchestral musical swell supporting narrative monologue."},
    ),
}


class ReferenceMasteringAuditor:
    """
    Audits mastered audio against versioned reference profiles.
    Distinguishes appropriate vs inappropriate comparisons and protects narrative intent.
    """

    def extract_reference_profile(
        self,
        facts: MasteringAnalysisFacts,
        reference_type: str,
        reference_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ReferenceProfile:
        """Constructs an inspectable, normalized ReferenceProfile from analyzed audio facts."""
        if not facts.is_valid_audio:
            raise ValueError(f"Cannot extract reference profile from invalid audio: {facts.filepath}")

        return ReferenceProfile(
            reference_id=reference_id,
            reference_type=reference_type,  # type: ignore[arg-type]
            version=REFERENCE_SCHEMA_VERSION,
            target_lufs=round(facts.integrated_lufs, 2),
            dynamic_range_db=round(facts.dynamic_range_db or 6.0, 2),
            crest_factor_db=round(facts.crest_factor_db or 8.0, 2),
            spectral_centroid_hz=round(facts.spectral_centroid_hz or 1200.0, 1),
            phase_correlation=round(facts.phase_correlation, 3),
            tolerance_lufs=1.2,
            tolerance_crest=2.5,
            metadata=metadata or {},
        )

    def compare_to_reference(
        self,
        facts: MasteringAnalysisFacts,
        reference: Optional[ReferenceProfile],
        scene_type: Optional[str] = None,
    ) -> Optional[ReferenceComparisonResult]:
        """
        Compares mastered audio metrics against a reference profile.
        Returns None if reference is omitted (safe fallback).
        """
        if reference is None:
            return None

        notes: List[str] = []
        deviations: Dict[str, float] = {}

        # 1. Appropriateness Check
        # Whispers or quiet scenes compared to action/music-heavy references are inappropriate
        is_appropriate = True
        if scene_type:
            st = scene_type.upper()
            rt = reference.reference_type.lower()
            if st in ("INTIMATE", "QUIET") and rt in ("action", "music_heavy"):
                is_appropriate = False
                notes.append(
                    f"Inappropriate comparison: {st} scene should not be benchmarked against {rt} reference."
                )
            elif st == "ACTION" and rt in ("quiet", "intimate"):
                is_appropriate = False
                notes.append(
                    f"Inappropriate comparison: ACTION scene should not be benchmarked against {rt} reference."
                )

        if not is_appropriate:
            return ReferenceComparisonResult(
                reference_id=reference.reference_id,
                reference_type=reference.reference_type,
                comparison_status="INAPPROPRIATE_COMPARISON",
                is_appropriate=False,
                deviations={},
                notes=notes,
            )

        # 2. Compute Metric Deviations
        lufs_delta = round(facts.integrated_lufs - reference.target_lufs, 2)
        deviations["lufs_delta"] = lufs_delta

        crest_delta = round((facts.crest_factor_db or 0.0) - reference.crest_factor_db, 2)
        deviations["crest_delta_db"] = crest_delta

        if facts.spectral_centroid_hz:
            centroid_delta = round(facts.spectral_centroid_hz - reference.spectral_centroid_hz, 1)
            deviations["centroid_delta_hz"] = centroid_delta

        # 3. Determine Match Status
        abs_lufs = abs(lufs_delta)
        abs_crest = abs(crest_delta)

        if abs_lufs <= reference.tolerance_lufs and abs_crest <= reference.tolerance_crest:
            comparison_status = "MATCH"
            notes.append("Audio matches reference acoustic profile within studio tolerances.")
        elif abs_lufs <= reference.tolerance_lufs * 1.8 and abs_crest <= reference.tolerance_crest * 1.8:
            comparison_status = "MILD_DEVIATION"
            notes.append(
                f"Mild acoustic deviation from reference ({abs_lufs:.1f} LU loudness delta, {abs_crest:.1f} dB crest delta)."
            )
        else:
            comparison_status = "SIGNIFICANT_DEVIATION"
            notes.append(
                f"Significant deviation from reference ({abs_lufs:.1f} LU loudness delta, {abs_crest:.1f} dB crest delta)."
            )

        return ReferenceComparisonResult(
            reference_id=reference.reference_id,
            reference_type=reference.reference_type,
            comparison_status=comparison_status,
            is_appropriate=True,
            deviations=deviations,
            notes=notes,
        )
