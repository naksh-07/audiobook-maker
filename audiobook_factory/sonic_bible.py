#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: Book Sonic Bible & Leitmotif Registry (Pydantic v2).
"New Room 1": Manages top-level acoustic identity, thematic leitmotif assignments,
world acoustic environments, and global audio drama loudness governance.
Persisted as dedicated `sound_bible.json`.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

logger = logging.getLogger("audiobook_factory.sonic_bible")


class LeitmotifDefinition(BaseModel):
    """
    Thematic musical signature bound to a key dramatic character, faction, or concept.
    Enforces aesthetic coherence across entire multi-hour book productions.
    """
    model_config = ConfigDict(extra="ignore")

    motif_id: str = Field(..., description="Unique slug for the leitmotif (e.g. 'lm_protagonist_destiny')")
    entity_type: Literal["character", "faction", "location", "prophecy", "philosophical_theme"] = Field(
        ..., description="Category of dramatic entity this leitmotif binds to"
    )
    associated_entity: str = Field(..., description="Name of character, location, or faction")
    track_id: Union[int, str] = Field(..., description="Catalog track identifier or source filename")
    track_name: str = Field(..., description="Descriptive track name or soundtrack title")
    primary_instrument: str = Field(..., description="Lead acoustic timbre (e.g. 'solo cello', 'hurdy-gurdy', 'silver flute')")
    canonical_tempo_bpm: int = Field(default=90, ge=30, le=280, description="Nominal tempo in beats per minute")
    dramatic_intent: str = Field(..., description="Artistic narrative purpose of this theme")
    priority_level: int = Field(default=5, ge=1, le=10, description="Dramaturgical priority (10 = protagonist theme)")
    default_section_start_sec: float = Field(default=0.0, ge=0.0, description="Default section cue offset in seconds")


class WorldAcousticProfile(BaseModel):
    """
    Acoustic environment impulse and reverberation profile for physical world spaces.
    Decoupled from audio files; specifies spatial propagation physics.
    """
    model_config = ConfigDict(extra="ignore")

    env_id: str = Field(..., description="Unique space slug (e.g. 'crypt_tomb', 'great_castle_hall', 'swamp_marsh')")
    display_name: str = Field(..., description="Human-readable environment name")
    space_type: Literal["indoor_small", "indoor_large", "subterranean", "outdoor_open", "outdoor_enclosed", "ethereal"] = Field(
        ..., description="Physical enclosure geometry"
    )
    estimated_rt60_ms: int = Field(default=1200, ge=50, le=12000, description="Estimated reverberation time T60 in milliseconds")
    high_freq_damping: float = Field(default=0.5, ge=0.0, le=1.0, description="High-frequency air/wall damping factor")
    early_reflections_level_db: float = Field(default=-14.0, le=0.0, description="Early reflection gain in dB")
    reverb_tail_level_db: float = Field(default=-18.0, le=0.0, description="Late diffuse reverb tail gain in dB")
    ir_preset: str = Field(default="room", description="Impulse response convolution preset (e.g. 'cave', 'wood_hall')")


class GlobalLoudnessPolicy(BaseModel):
    """
    Macro-level broadcast compliance targets adhering to EBU R128 and BBC/Netflix cinema audio specs.
    """
    model_config = ConfigDict(extra="ignore")

    target_lufs: float = Field(default=-19.0, ge=-30.0, le=-14.0, description="Integrated loudness target in LUFS")
    true_peak_dbtp: float = Field(default=-1.5, ge=-6.0, le=-0.1, description="Maximum allowable True Peak in dBTP")
    loudness_range_lra_max: float = Field(default=8.5, ge=2.0, le=20.0, description="Maximum allowable dynamic loudness range in LU")
    min_dialogue_to_music_ratio_db: float = Field(default=14.0, ge=6.0, le=30.0, description="Minimum DMR in 300Hz-3.5kHz corridor")
    min_phase_correlation: float = Field(default=0.20, ge=-1.0, le=1.0, description="Minimum stereo phase correlation coefficient")


class SonicBible(BaseModel):
    """
    Top-Level Book Sonic Bible & Leitmotif Registry.
    Dedicated room for book-wide acoustic aesthetics, recurring leitmotifs, and world space profiles.
    Persisted to `sound_bible.json`.
    """
    model_config = ConfigDict(extra="ignore")

    bible_version: str = Field(default="1.0", description="Schema version")
    book_title: str = Field(..., description="Title of book/work")
    project_id: str = Field(default="", description="Unique project slug")
    loudness_policy: GlobalLoudnessPolicy = Field(default_factory=GlobalLoudnessPolicy)
    leitmotifs: Dict[str, LeitmotifDefinition] = Field(
        default_factory=dict,
        description="Keyed by associated entity (e.g. character name) or motif_id"
    )
    acoustic_spaces: Dict[str, WorldAcousticProfile] = Field(
        default_factory=dict,
        description="Keyed by env_id"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def register_leitmotif(self, motif: LeitmotifDefinition) -> None:
        """Register or update a leitmotif definition."""
        self.leitmotifs[motif.associated_entity.lower()] = motif
        self.leitmotifs[motif.motif_id.lower()] = motif

    def register_space(self, space: WorldAcousticProfile) -> None:
        """Register or update an acoustic space environment profile."""
        self.acoustic_spaces[space.env_id.lower()] = space

    def resolve_theme_for_character(self, name: str) -> Optional[LeitmotifDefinition]:
        """
        Dynamically resolves the leitmotif definition for a given character or concept.
        Case-insensitive with token subset matching.
        """
        if not name:
            return None
        q = name.strip().lower()
        if q in self.leitmotifs:
            return self.leitmotifs[q]

        # Fuzzy word containment match
        for key, motif in self.leitmotifs.items():
            if key in q or q in key:
                return motif
        return None

    def resolve_acoustic_space(self, env_id: str) -> Optional[WorldAcousticProfile]:
        """Resolve world acoustic space profile by environment slug."""
        if not env_id:
            return None
        q = env_id.strip().lower()
        if q in self.acoustic_spaces:
            return self.acoustic_spaces[q]
        for key, space in self.acoustic_spaces.items():
            if key in q or q in key:
                return space
        return None

    def save_to_disk(self, target_path: Union[str, Path]) -> Path:
        """Saves SonicBible to dedicated `sound_bible.json`."""
        p = Path(target_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        logger.info(f"[+] Saved Sonic Bible to: {p}")
        return p

    @classmethod
    def load_from_disk(cls, target_path: Union[str, Path]) -> SonicBible:
        """Loads SonicBible from disk."""
        p = Path(target_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Sonic Bible file not found: {p}")
        content = p.read_text(encoding="utf-8")
        data = json.loads(content)
        return cls.model_validate(data)

    def audit_sonic_bible_integrity(self, sound_bank: Optional[Any] = None) -> Dict[str, Any]:
        """
        Level 1 Guard: Book-Level Sonic Bible Integrity Guard.
        Validates:
        - Unique motif identifiers and valid associated entities.
        - Canonical tempo sanity (30-280 BPM) and valid instrumentation descriptions.
        - Acoustic space RT60 bounds (50ms - 12000ms) and dampening factors.
        - Physical audio track resolution via SoundBank if provided.
        """
        errors: List[str] = []
        warnings: List[str] = []
        checked_motifs = 0
        checked_spaces = 0

        # Audit leitmotifs
        seen_ids = set()
        for key, motif in self.leitmotifs.items():
            if motif.motif_id in seen_ids:
                continue
            seen_ids.add(motif.motif_id)
            checked_motifs += 1

            if not motif.associated_entity.strip():
                errors.append(f"Leitmotif '{motif.motif_id}' has empty associated_entity.")
            if not motif.primary_instrument.strip():
                errors.append(f"Leitmotif '{motif.motif_id}' has empty primary_instrument.")
            if not (30 <= motif.canonical_tempo_bpm <= 280):
                errors.append(f"Leitmotif '{motif.motif_id}' tempo {motif.canonical_tempo_bpm} outside valid range (30-280 BPM).")

            # Check track resolution in sound bank if available
            if sound_bank is not None:
                track_ident = str(motif.track_id or motif.track_name)
                resolved = None
                try:
                    resolved = sound_bank.resolve_sound(track_ident) or sound_bank.resolve_asset_path(track_ident)
                except Exception:
                    pass
                if not resolved or not resolved.exists():
                    warnings.append(f"Leitmotif '{motif.motif_id}' track '{track_ident}' could not be resolved on disk.")

        # Audit acoustic spaces
        for env_id, space in self.acoustic_spaces.items():
            checked_spaces += 1
            if not (50 <= space.estimated_rt60_ms <= 12000):
                errors.append(f"Space '{env_id}' RT60 {space.estimated_rt60_ms}ms outside safe acoustic limits (50-12000ms).")
            if not (0.0 <= space.high_freq_damping <= 1.0):
                errors.append(f"Space '{env_id}' damping {space.high_freq_damping} outside [0.0, 1.0].")

        passed = len(errors) == 0
        return {
            "guard": "Level 1 (Sonic Bible Integrity Guard)",
            "status": "PASS" if passed else "FAIL",
            "passed": passed,
            "checked_motifs": checked_motifs,
            "checked_spaces": checked_spaces,
            "warnings": warnings,
            "errors": errors,
        }
