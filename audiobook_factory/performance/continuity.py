#!/usr/bin/env python3
"""
Audiobook Factory - Performance Continuity & Drift Detection (Pillar 3.6).
Tracks character performance metrics across scenes and chapters to ensure
consistent vocal identity without sacrificing dramatic expression.
"""

from __future__ import annotations
import os
import uuid
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from .contracts import PerformanceDirection


class CharacterPerformanceTelemetry(BaseModel):
    """Running performance metrics for a character across scenes and chapters."""
    model_config = ConfigDict(extra="ignore")

    character_name: str
    total_segments: int = 0
    total_duration_sec: float = 0.0
    paces: List[float] = Field(default_factory=list)
    energies: List[float] = Field(default_factory=list)
    restraints: List[float] = Field(default_factory=list)
    emotions_seen: List[str] = Field(default_factory=list)

    # Long-form continuity fields (Phase 18)
    last_emotional_state: Optional[str] = None
    last_energy: Optional[float] = None
    last_pace: Optional[float] = None
    last_physical_state: Optional[str] = None
    voice_identity_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    scene_count: int = 0
    chapter_count: int = 0
    recent_take_ids: List[str] = Field(default_factory=list)

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
    Maintains persistent telemetry across chapter and book boundaries.
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

        # Update last observed state
        telem.last_emotional_state = direction.surface_emotion
        telem.last_energy = direction.energy
        telem.last_pace = direction.pace
        telem.last_physical_state = direction.physical_state

    def record_take(
        self,
        speaker: str,
        take_id: str,
        duration_sec: float = 0.0,
        voice_identity_score: Optional[float] = None,
    ) -> None:
        """Records take generation metadata and updates voice identity confidence."""
        if not speaker or speaker in ("Narrator", "Foley"):
            return

        if speaker not in self.characters:
            self.characters[speaker] = CharacterPerformanceTelemetry(character_name=speaker)

        telem = self.characters[speaker]
        telem.recent_take_ids.append(take_id)
        if len(telem.recent_take_ids) > 20:
            telem.recent_take_ids = telem.recent_take_ids[-20:]

        if voice_identity_score is not None:
            # Running exponential moving average of acoustic consistency
            telem.voice_identity_confidence = round(
                0.85 * telem.voice_identity_confidence + 0.15 * voice_identity_score,
                3,
            )

    def advance_chapter(self, chapter_id: str = "") -> None:
        """Advances chapter counter across all active tracked characters."""
        for telem in self.characters.values():
            telem.chapter_count += 1

    def audit_inter_chapter_transition(
        self,
        speaker: str,
        new_direction: PerformanceDirection,
    ) -> List[str]:
        """
        Audits continuity between previous chapter performance state and new chapter onset.
        Guards against unmotivated physical recovery or violent energy leaps across breaks.
        """
        warnings: List[str] = []
        if speaker not in self.characters:
            return warnings

        telem = self.characters[speaker]

        # 1. Physical state continuity
        if telem.last_physical_state in ("wounded", "exhausted"):
            if new_direction.physical_state in ("combat_strain", "normal"):
                warn = (
                    f"Physical Continuity Alert: {speaker} abruptly transitioned from "
                    f"'{telem.last_physical_state}' to '{new_direction.physical_state}' across boundary"
                )
                warnings.append(warn)
                logger.warning(f"  [!] {warn}")

        # 2. Vocal energy rupture
        if telem.last_energy is not None:
            energy_jump = abs(new_direction.energy - telem.last_energy)
            if energy_jump > 0.55 and new_direction.intensity not in ("explosive", "high"):
                warn = (
                    f"Energy Continuity Alert: {speaker} exhibits unbuffered energy jump "
                    f"({telem.last_energy:.2f} -> {new_direction.energy:.2f}) across chapter boundary"
                )
                warnings.append(warn)
                logger.warning(f"  [!] {warn}")

        self.drift_warnings.extend(warnings)
        return warnings

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

    def save_to_file(self, filepath: Union[Path, str]) -> None:
        """Serializes character performance telemetry atomically to a JSON file."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "2.0.0",
            "characters": {k: v.model_dump() for k, v in self.characters.items()},
            "drift_warnings": self.drift_warnings[-100:],
        }
        tmp_file = p.with_suffix(f".tmp_{os.getpid()}_{uuid.uuid4().hex[:6]}")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, p)
        finally:
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass
        logger.info(f"  [CONTINUITY] Saved character performance telemetry to {p.name}")

    def load_from_file(self, filepath: Union[Path, str]) -> None:
        """Deserializes character performance telemetry from a JSON file."""
        p = Path(filepath)
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            chars_data = data.get("characters", {})
            for k, c_dict in chars_data.items():
                self.characters[k] = CharacterPerformanceTelemetry.model_validate(c_dict)
            self.drift_warnings = data.get("drift_warnings", [])
            logger.info(f"  [CONTINUITY] Loaded continuity state for {len(self.characters)} characters from {p.name}")
        except Exception as e:
            logger.warning(f"  [CONTINUITY] Failed to load continuity file {p.name}: {e}")

    def export_manifest(self) -> Dict[str, Any]:
        """Exports in-memory telemetry as dictionary."""
        return {
            "characters": {k: v.model_dump() for k, v in self.characters.items()},
            "drift_warnings": list(self.drift_warnings),
        }

