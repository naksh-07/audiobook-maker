#!/usr/bin/env python3
"""
Audiobook Factory - Performance Continuity & Drift Detection (Pillar 3.6).
Tracks character performance metrics across scenes and chapters to ensure
consistent vocal identity without sacrificing dramatic expression.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from .contracts import PerformanceDirection


class CharacterPerformanceTelemetry(BaseModel):
    """Running performance metrics for a character across scenes."""
    model_config = ConfigDict(extra="ignore")

    character_name: str
    total_segments: int = 0
    total_duration_sec: float = 0.0
    paces: List[float] = Field(default_factory=list)
    energies: List[float] = Field(default_factory=list)
    restraints: List[float] = Field(default_factory=list)
    emotions_seen: List[str] = Field(default_factory=list)

    @property
    def average_pace(self) -> float:
        return float(sum(self.paces) / len(self.paces)) if self.paces else 1.0

    @property
    def average_energy(self) -> float:
        return float(sum(self.energies) / len(self.energies)) if self.energies else 0.75

    @property
    def average_restraint(self) -> float:
        return float(sum(self.restraints) / len(self.restraints)) if self.restraints else 0.50


class PerformanceContinuityTracker:
    """
    Monitors character performance arcs across chapters to detect and prevent
    unintended actor drift or abrupt emotional rupture.
    """

    def __init__(self):
        self.characters: Dict[str, CharacterPerformanceTelemetry] = {}
        self.drift_warnings: List[str] = []

    def record_direction(self, direction: PerformanceDirection, duration_sec: float = 0.0) -> None:
        """Records a completed performance direction into character telemetry."""
        spk = direction.speaker
        if not spk or spk in ("Narrator", "Foley"):
            return

        if spk not in self.characters:
            self.characters[spk] = CharacterPerformanceTelemetry(character_name=spk)

        telem = self.characters[spk]
        telem.total_segments += 1
        telem.total_duration_sec += duration_sec
        telem.paces.append(direction.pace)
        telem.energies.append(direction.energy)
        telem.restraints.append(direction.restraint)
        if len(telem.paces) > 200:
            telem.paces = telem.paces[-200:]
            telem.energies = telem.energies[-200:]
            telem.restraints = telem.restraints[-200:]
        if direction.surface_emotion not in telem.emotions_seen:
            telem.emotions_seen.append(direction.surface_emotion)

    def audit_scene_continuity(
        self,
        scene_directions: List[PerformanceDirection],
    ) -> List[str]:
        """
        Audits a scene's directions for anomalous performance drift or breaks.
        """
        warnings: List[str] = []
        char_scene_paces: Dict[str, List[float]] = {}

        for d in scene_directions:
            spk = d.speaker
            if spk in ("Narrator", "Foley"):
                continue

            if spk not in char_scene_paces:
                char_scene_paces[spk] = []
            char_scene_paces[spk].append(d.pace)

        for spk, paces in char_scene_paces.items():
            if spk in self.characters and len(self.characters[spk].paces) >= 5:
                est_pace = self.characters[spk].average_pace
                scene_pace = sum(paces) / len(paces)
                pace_diff = abs(scene_pace - est_pace) / est_pace
                if pace_diff > 0.30:
                    warn = (
                        f"Performance Drift Alert: {spk} average pace shifted by {pace_diff*100:.1f}% "
                        f"in scene (established: {est_pace:.2f}, scene: {scene_pace:.2f})."
                    )
                    warnings.append(warn)
                    logger.warning(f"  [!] {warn}")

        self.drift_warnings.extend(warnings)
        return warnings
