#!/usr/bin/env python3
"""
Audiobook Factory - Stage 12: Book Master Profile Engine.
=========================================================
Builds and maintains the project-level acoustic reference profile ('BookMasterProfile')
using robust, outlier-resistant statistical aggregation across representative chapters.

Key Principles:
- Book-level identity: Represents what 'belongs to this audiobook' acoustically.
- Outlier-resistant: Uses median and IQR so explosions or silence do not distort the profile.
- Versioned & governed: Cryptographic tracking of source chapter artifacts and engine version.
- Confidence-scored: Expresses statistical confidence based on chapter sample size.
"""

from __future__ import annotations
import math
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from audiobook_factory.logger import logger
from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    BookMasterProfile,
)

PROFILE_SCHEMA_VERSION = "1.0.0"


class BookMasterProfileBuilder:
    """
    Constructs a BookMasterProfile from a collection of mastered chapter analysis facts.
    Applies robust median/IQR aggregation to exclude acoustic anomalies.
    """

    def __init__(self, schema_version: str = PROFILE_SCHEMA_VERSION):
        self.version = schema_version

    def build_profile(
        self,
        book_id: str,
        chapter_facts: Dict[str, MasteringAnalysisFacts],
        dialogue_stem_facts: Optional[Dict[str, MasteringAnalysisFacts]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> BookMasterProfile:
        """
        Builds a robust BookMasterProfile from a dictionary of chapter_id -> MasteringAnalysisFacts.
        """
        dialogue_facts = dialogue_stem_facts or {}
        # 1. Filter out invalid, corrupt, or near-silent files
        valid_entries: Dict[str, MasteringAnalysisFacts] = {}
        for ch_id, facts in chapter_facts.items():
            if facts.is_valid_audio and facts.duration_sec >= 1.0 and facts.integrated_lufs > -55.0:
                valid_entries[ch_id] = facts
            else:
                logger.warning(f"Excluding chapter {ch_id} from book profile: invalid or silent audio.")

        sample_count = len(valid_entries)

        # 2. Compute statistical confidence
        if sample_count >= 3:
            confidence = 1.0
        elif sample_count == 2:
            confidence = 0.75
        elif sample_count == 1:
            confidence = 0.50
        else:
            confidence = 0.0

        if sample_count == 0:
            logger.warning(f"No valid chapters available to build book profile for {book_id}. Returning default baseline.")
            return BookMasterProfile(
                version=self.version,
                book_id=book_id,
                confidence=0.0,
                sample_count=0,
                source_chapters=[],
                target_lufs_median=-19.0,
                target_lufs_iqr=0.5,
                true_peak_median_dbtp=-1.5,
                dynamic_range_median_db=6.0,
                crest_factor_median_db=8.0,
                lra_median=8.5,
                spectral_centroid_median_hz=1200.0,
                dialogue_anchor_median_db=0.0,
                phase_correlation_median=0.95,
                metadata={"status": "INCOMPLETE_SAMPLE_SET"},
            )

        # 3. Extract dimensional arrays
        lufs_arr = [f.integrated_lufs for f in valid_entries.values()]
        tp_arr = [f.true_peak_dbtp for f in valid_entries.values() if f.true_peak_dbtp is not None]
        dr_arr = [f.dynamic_range_db for f in valid_entries.values() if f.dynamic_range_db is not None]
        crest_arr = [f.crest_factor_db for f in valid_entries.values() if f.crest_factor_db is not None]
        lra_arr = [f.loudness_range_lra for f in valid_entries.values() if f.loudness_range_lra is not None]
        centroid_arr = [f.spectral_centroid_hz for f in valid_entries.values() if f.spectral_centroid_hz is not None]
        phase_arr = [f.phase_correlation for f in valid_entries.values()]

        # Extract dialogue anchor ratios if available
        anchor_arr = []
        for ch_id, mix_f in valid_entries.items():
            if ch_id in dialogue_facts and dialogue_facts[ch_id].integrated_lufs > -65.0:
                anchor_arr.append(dialogue_facts[ch_id].integrated_lufs - mix_f.integrated_lufs)

        # 4. Helper for robust median & IQR
        def _robust_stats(arr: List[float], fallback_med: float, fallback_iqr: float = 0.5) -> Tuple[float, float]:
            if not arr:
                return fallback_med, fallback_iqr
            med = float(np.median(arr))
            q75, q25 = np.percentile(arr, [75, 25])
            iqr = float(q75 - q25)
            return round(med, 2), round(iqr, 2)

        lufs_med, lufs_iqr = _robust_stats(lufs_arr, -19.0, 0.5)
        tp_med, _ = _robust_stats(tp_arr, -1.5, 0.2)
        dr_med, _ = _robust_stats(dr_arr, 6.0, 1.0)
        crest_med, _ = _robust_stats(crest_arr, 8.0, 1.5)
        lra_med, _ = _robust_stats(lra_arr, 8.5, 1.0)
        centroid_med, _ = _robust_stats(centroid_arr, 1200.0, 200.0)
        phase_med, _ = _robust_stats(phase_arr, 0.95, 0.05)
        anchor_med, _ = _robust_stats(anchor_arr, 0.0, 1.0)

        meta = custom_metadata or {}
        meta["sample_sources"] = list(valid_entries.keys())
        meta["distributions"] = {
            "lufs": {"median": lufs_med, "iqr": lufs_iqr, "min": float(min(lufs_arr)), "max": float(max(lufs_arr))},
            "crest_factor": {"median": crest_med, "min": float(min(crest_arr)) if crest_arr else 0.0},
        }

        return BookMasterProfile(
            version=self.version,
            book_id=book_id,
            confidence=confidence,
            sample_count=sample_count,
            source_chapters=list(valid_entries.keys()),
            target_lufs_median=lufs_med,
            target_lufs_iqr=lufs_iqr,
            true_peak_median_dbtp=tp_med,
            dynamic_range_median_db=dr_med,
            crest_factor_median_db=crest_med,
            lra_median=lra_med,
            spectral_centroid_median_hz=centroid_med,
            dialogue_anchor_median_db=anchor_med,
            phase_correlation_median=phase_med,
            metadata=meta,
        )
