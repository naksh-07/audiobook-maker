#!/usr/bin/env python3
"""
Audiobook Factory - Scene Emotional State & Continuity Tracker (Phase 8 & Wave 3).
Maintains continuous 6D emotional vectors:
- valence (-1.0 negative to +1.0 positive)
- arousal (0.0 calm to 1.0 hyper-aroused)
- tension (0.0 relaxed to 1.0 breaking point)
- restraint (0.0 uninhibited to 1.0 iron suppression)
- vulnerability (0.0 armored to 1.0 exposed)
- energy (0.0 depleted to 1.0 explosive)
Enforces emotional continuity across beats, preventing ungrounded emotional teleportation.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger


class SceneEmotionalVector(BaseModel):
    """
    6-Dimensional continuous emotional and energetic state vector.
    """
    model_config = ConfigDict(extra="ignore")

    valence: float = Field(default=0.0, ge=-1.0, le=1.0, description="-1.0 (despair/dread) to +1.0 (ecstasy/triumph)")
    arousal: float = Field(default=0.5, ge=0.0, le=1.0, description="0.0 (lethargic/dormant) to 1.0 (adrenaline surge)")
    tension: float = Field(default=0.5, ge=0.0, le=1.0, description="0.0 (resolution) to 1.0 (crisis/climax)")
    restraint: float = Field(default=0.5, ge=0.0, le=1.0, description="0.0 (unfiltered explosion) to 1.0 (iron discipline)")
    vulnerability: float = Field(default=0.3, ge=0.0, le=1.0, description="0.0 (fortified) to 1.0 (naked exposure)")
    energy: float = Field(default=0.7, ge=0.0, le=1.0, description="0.0 (exhausted whisper) to 1.0 (maximum projection)")

    def distance_to(self, other: SceneEmotionalVector) -> float:
        """Euclidean distance across normalized emotional dimensions."""
        diffs = [
            (self.valence - other.valence) / 2.0,
            self.arousal - other.arousal,
            self.tension - other.tension,
            self.restraint - other.restraint,
            self.vulnerability - other.vulnerability,
            self.energy - other.energy,
        ]
        return float(math.sqrt(sum(d ** 2 for d in diffs) / len(diffs)))


class SceneEmotionalStateTracker:
    """
    Tracks and smooths the emotional trajectory of a scene across dramatic beats.
    Grounds transitions and damps volatile emotional ruptures that lack causal narrative triggers.
    """

    VOLATILE_RUPTURE_THRESHOLD = 0.35

    def __init__(self, scene_id: str = "scene_001"):
        self.scene_id = scene_id
        self.current_vector = SceneEmotionalVector()
        self.character_vectors: Dict[str, SceneEmotionalVector] = {}
        self.history: List[Tuple[int, str, SceneEmotionalVector]] = []

    def update_state(
        self,
        segment_index: int,
        speaker: str,
        target_emotion: str,
        intensity: str = "medium",
        causal_trigger: Optional[str] = None,
        restraint_override: Optional[float] = None,
    ) -> SceneEmotionalVector:
        """
        Transitions emotional vector toward the target state for this speaker.
        If a sudden jump exceeds threshold without a causal trigger, it dampens the leap.
        """
        spk = speaker.strip()
        prev = self.character_vectors.get(spk, self.current_vector)

        # Estimate target vector from emotion and intensity
        raw_target = self._estimate_vector_from_emotion(target_emotion, intensity)
        if restraint_override is not None:
            raw_target.restraint = max(0.0, min(1.0, restraint_override))

        # Check for ungrounded emotional leap
        dist = prev.distance_to(raw_target)
        smoothed = raw_target

        if dist > self.VOLATILE_RUPTURE_THRESHOLD and not causal_trigger:
            # Damp leap: interpolate 50% toward target through tension/restraint
            logger.info(
                f"  [EMOTIONAL SMOOTHER] Damping ungrounded emotional leap for {spk} "
                f"(distance: {dist:.2f} > {self.VOLATILE_RUPTURE_THRESHOLD})."
            )
            smoothed = SceneEmotionalVector(
                valence=round(prev.valence * 0.4 + raw_target.valence * 0.6, 2),
                arousal=round(prev.arousal * 0.4 + raw_target.arousal * 0.6, 2),
                tension=round(max(prev.tension, raw_target.tension), 2),
                restraint=round(min(1.0, max(prev.restraint, raw_target.restraint) + 0.15), 2),
                vulnerability=round(prev.vulnerability * 0.5 + raw_target.vulnerability * 0.5, 2),
                energy=round(prev.energy * 0.4 + raw_target.energy * 0.6, 2),
            )

        self.character_vectors[spk] = smoothed
        self.current_vector = smoothed
        self.history.append((segment_index, spk, smoothed))
        return smoothed

    def get_character_state(self, speaker: str) -> SceneEmotionalVector:
        return self.character_vectors.get(speaker.strip(), self.current_vector)

    @staticmethod
    def _estimate_vector_from_emotion(emotion: str, intensity: str) -> SceneEmotionalVector:
        """Heuristic baseline mapping from dramatic emotion token to 6D vector."""
        e = emotion.lower().strip()
        v = 0.0
        a = 0.5
        t = 0.5
        r = 0.5
        vuln = 0.3
        nrg = 0.7

        if "rage" in e or "anger" in e or "fury" in e:
            v = -0.7
            a = 0.9
            t = 0.85
            r = 0.35
            vuln = 0.1
            nrg = 0.95
        elif "fear" in e or "terror" in e or "panic" in e:
            v = -0.8
            a = 0.85
            t = 0.95
            r = 0.4
            vuln = 0.8
            nrg = 0.65
        elif "grief" in e or "sadness" in e or "despair" in e:
            v = -0.9
            a = 0.3
            t = 0.7
            r = 0.6
            vuln = 0.9
            nrg = 0.4
        elif "joy" in e or "triumph" in e or "happy" in e:
            v = 0.85
            a = 0.7
            t = 0.2
            r = 0.4
            vuln = 0.4
            nrg = 0.8
        elif "whisper" in e or "intimate" in e:
            v = 0.2
            a = 0.3
            t = 0.4
            r = 0.7
            vuln = 0.7
            nrg = 0.35
        elif "sarcastic" in e or "ironic" in e:
            v = -0.1
            a = 0.45
            t = 0.4
            r = 0.75
            vuln = 0.15
            nrg = 0.65
        elif "calm" in e or "neutral" in e:
            v = 0.0
            a = 0.3
            t = 0.3
            r = 0.6
            vuln = 0.2
            nrg = 0.65

        # Intensity modulations
        if intensity == "explosive":
            nrg = min(1.0, nrg + 0.20)
            a = min(1.0, a + 0.15)
        elif intensity == "high":
            nrg = min(0.95, nrg + 0.10)
        elif intensity == "low":
            nrg = max(0.3, nrg - 0.20)

        return SceneEmotionalVector(
            valence=round(v, 2),
            arousal=round(a, 2),
            tension=round(t, 2),
            restraint=round(r, 2),
            vulnerability=round(vuln, 2),
            energy=round(nrg, 2),
        )
