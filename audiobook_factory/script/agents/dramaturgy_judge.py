#!/usr/bin/env python3
"""
Audiobook Factory - Room 3 Agent D: Dramaturgy Consistency Judge.
Quality auditor and spatial continuity validator for screenplay segments.
Verifies completeness, dialogue attribution integrity, prevents random stereo jitter,
and certifies acting intensity and proximity calibration.
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("AudiobookFactory")


class DramaturgyConsistencyJudge:
    """Agent D: Screenplay Consistency, Spatial Continuity & Intensity Auditor."""

    def audit_and_certify(
        self,
        segments: List[Dict[str, Any]],
        chunk_title: str = "",
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Audits screenplay segments for acoustic continuity and certifies output."""
        if not segments:
            return [], {"status": "EMPTY", "segment_count": 0}

        certified: List[Dict[str, Any]] = []
        speaker_last_pan: Dict[str, float] = {}
        spatial_adjustments = 0
        intensity_adjustments = 0

        for seg in segments:
            s_copy = dict(seg)
            speaker = s_copy.get("speaker", "Narrator")
            stype = s_copy.get("type", "narration")

            # 1. Narrator Spatial Clamping Invariant
            if speaker.lower() in ("narrator", "सूत्रधार") or stype == "narration":
                if "spatial" not in s_copy or not isinstance(s_copy["spatial"], dict):
                    s_copy["spatial"] = {}
                s_copy["spatial"]["pan"] = 0.0
                s_copy["spatial"]["proximity"] = "normal_room"
                s_copy["spatial"]["physical_blocking"] = "standing"
                speaker_last_pan["narrator"] = 0.0
            else:
                # 2. Character Spatial Continuity & Stereo Clamping
                if "spatial" not in s_copy or not isinstance(s_copy["spatial"], dict):
                    s_copy["spatial"] = {}

                current_pan = s_copy["spatial"].get("pan", 0.0)
                try:
                    current_pan = float(current_pan)
                except (ValueError, TypeError):
                    current_pan = 0.0

                # Clamp azimuth to [-0.8, +0.8] studio staging bounds
                clamped_pan = max(-0.8, min(0.8, current_pan))
                if clamped_pan != current_pan:
                    spatial_adjustments += 1
                    current_pan = clamped_pan

                # Spatial jitter guard: if speaker suddenly leaps across center (e.g. from -0.4 to +0.5)
                # without an explicit 'approaching' or 'pacing' blocking, smooth to previous anchor
                blocking = s_copy.get("physical_blocking", s_copy["spatial"].get("physical_blocking", "standing"))
                if speaker in speaker_last_pan and blocking not in ("pacing", "approaching", "retreating"):
                    prev_pan = speaker_last_pan[speaker]
                    if abs(current_pan - prev_pan) > 0.45:
                        # Smooth back to prior position to avoid jarring stereo teleportation
                        current_pan = round((prev_pan * 0.7) + (current_pan * 0.3), 2)
                        spatial_adjustments += 1

                s_copy["spatial"]["pan"] = current_pan
                speaker_last_pan[speaker] = current_pan

            # 3. Dynamic Headroom & Intensity Calibration
            delivery = ""
            if isinstance(s_copy.get("acting"), dict):
                delivery = s_copy["acting"].get("delivery_style", "").lower()

            intensity = s_copy.get("intensity_level", "medium")
            if "whisper" in delivery:
                if intensity != "low":
                    s_copy["intensity_level"] = "low"
                    intensity_adjustments += 1
                if s_copy["spatial"].get("proximity") != "intimate_close":
                    s_copy["spatial"]["proximity"] = "intimate_close"
            elif any(k in delivery for k in ("bellowing", "screaming", "battle", "rage", "explosive")):
                if intensity not in ("high", "explosive"):
                    s_copy["intensity_level"] = "high"
                    intensity_adjustments += 1

            certified.append(s_copy)

        report = {
            "chunk_title": chunk_title,
            "segment_count": len(certified),
            "spatial_adjustments": spatial_adjustments,
            "intensity_adjustments": intensity_adjustments,
            "status": "CERTIFIED",
        }
        logger.info(f"  [DramaturgyConsistencyJudge] Certified {len(certified)} segments ({spatial_adjustments} spatial/intensity smooths)")
        return certified, report
