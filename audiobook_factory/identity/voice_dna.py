#!/usr/bin/env python3
"""
Audiobook Factory - Character Voice DNA Engine (Pillar 3.1 & Wave 2).
Defines persistent multi-layer vocal identity:
1. Identity Layer: Base acoustic timbre, pitch, perceived age, resonance, vocal weight, accent.
2. Behavior Layer: Baseline pace, baseline energy, articulation, pause style, breath behavior, restraint.
3. Emotional Layer: Character-specific delivery tendencies across core emotional states.
4. Forbidden Layer: Strict behavioral boundaries that the voice must NEVER exhibit.
"""

from __future__ import annotations
import os
import json
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger


class VoiceDNAIdentityLayer(BaseModel):
    """Core acoustic identity attributes that remain invariant across scenes."""
    model_config = ConfigDict(extra="ignore")

    base_timbre: str = Field(default="resonant", description="Invariant acoustic color / texture")
    base_pitch_category: str = Field(default="medium", description="low, medium_low, medium, medium_high, high")
    perceived_age: str = Field(default="prime_adult", description="young_adult, prime_adult, mature_adult, elder")
    resonance: str = Field(default="chest", description="chest, throat, head, whisper_air")
    vocal_weight: str = Field(default="medium", description="light, medium, heavy")
    accent: str = Field(default="Standard", description="Regional or sociolect cadence")


class VoiceDNABehaviorLayer(BaseModel):
    """Habitual prosodic and physical delivery baseline."""
    model_config = ConfigDict(extra="ignore")

    baseline_pace: float = Field(default=1.0, ge=0.5, le=2.0)
    baseline_energy: float = Field(default=0.75, ge=0.0, le=1.0)
    articulation: str = Field(default="natural", description="crisp, natural, colloquial, sharp, sluggish")
    pause_style: str = Field(default="measured", description="measured, pregnant, staccato, conversational")
    breath_behavior: str = Field(default="steady", description="steady, suppressed, labored, audible")
    restraint: float = Field(default=0.50, ge=0.0, le=1.0, description="0=raw/unfiltered, 1=iron restraint")


class VoiceDNAEmotionalLayer(BaseModel):
    """Character-specific delivery tendencies when experiencing specific emotions."""
    model_config = ConfigDict(extra="ignore")

    anger: str = Field(default="controlled cold fury, low resonant chest growl")
    fear: str = Field(default="tightened breath, guarded suppression, clipped tempo")
    sadness: str = Field(default="softened vocal weight, weary drawl, downward inflections")
    joy: str = Field(default="subtle warm resonance, loosened pacing, dry smile")
    humor: str = Field(default="deadpan ironic delivery, pregnant pauses, sardonic cadence")
    intimacy: str = Field(default="close-mic whisper-air, low energy, softened projection")
    tension: str = Field(default="tightened jaw, iron suppression, measured spacing")


class VoiceDNAForbiddenLayer(BaseModel):
    """Hard boundaries: delivery styles that must NEVER occur for this character."""
    model_config = ConfigDict(extra="ignore")

    forbidden_behaviors: List[str] = Field(
        default_factory=lambda: [
            "shrill screaming",
            "cartoon panic",
            "bubbly melodrama",
            "servile whining",
            "slurred monotone",
        ]
    )


class VoiceDNA(BaseModel):
    """
    First-Class Character Voice DNA Contract.
    Preserves recognizable vocal identity across thousands of lines and dozens of chapters.
    """
    model_config = ConfigDict(extra="ignore")

    character_id: str
    character_name: str
    voice_id: str
    version: str = "1.0.0"
    identity: VoiceDNAIdentityLayer = Field(default_factory=VoiceDNAIdentityLayer)
    behavior: VoiceDNABehaviorLayer = Field(default_factory=VoiceDNABehaviorLayer)
    emotional: VoiceDNAEmotionalLayer = Field(default_factory=VoiceDNAEmotionalLayer)
    forbidden: VoiceDNAForbiddenLayer = Field(default_factory=VoiceDNAForbiddenLayer)
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())

    def get_emotional_tendency(self, emotion: str) -> str:
        """Looks up specific emotional tendency or falls back to neutral."""
        e_clean = emotion.lower().strip()
        if hasattr(self.emotional, e_clean):
            return getattr(self.emotional, e_clean)
        for k, v in self.emotional.model_dump().items():
            if k in e_clean or e_clean in k:
                return v
        return f"{emotion} delivery with {self.behavior.restraint:.2f} restraint"

    def to_tts_guidance(self) -> Dict[str, Any]:
        """Translates Voice DNA into actionable guidance for TTS performance adapter."""
        return {
            "timbre": self.identity.base_timbre,
            "resonance": self.identity.resonance,
            "articulation": self.behavior.articulation,
            "restraint": self.behavior.restraint,
            "baseline_pace": self.behavior.baseline_pace,
            "forbidden": self.forbidden.forbidden_behaviors,
        }

    @classmethod
    def synthesize_from_casting(
        cls,
        character_id: str,
        character_name: str,
        voice_id: str,
        catalog_voice_meta: Optional[Dict[str, Any]] = None,
        casting_profile: Optional[Any] = None,
        performance_profile: Optional[Any] = None,
    ) -> VoiceDNA:
        """
        Synthesizes a complete VoiceDNA by harmonizing casting catalog metadata,
        casting profile, and dramaturgy performance profile.
        """
        v_meta = catalog_voice_meta or {}
        timbre = v_meta.get("invariant_timbre") or "grounded chest resonance"
        pitch = v_meta.get("pitch_category") or "medium"
        age = v_meta.get("perceived_age") or "prime_adult"
        weight = "heavy" if "heavy" in str(timbre).lower() or pitch == "low" else "medium"

        base_pace = 1.0
        base_energy = 0.75
        articulation = "natural"
        restraint = 0.50
        custom_emo: Dict[str, str] = {}

        if performance_profile:
            base_pace = getattr(performance_profile, "baseline_pace", 1.0)
            base_energy = getattr(performance_profile, "baseline_energy", 0.75)
            articulation = getattr(performance_profile, "articulation", "natural")
            restraint = getattr(performance_profile, "restraint_level", 0.50)
            eb = getattr(performance_profile, "emotional_behaviors", {})
            if isinstance(eb, dict):
                custom_emo = eb

        if casting_profile:
            restraint = getattr(casting_profile, "restraint", restraint)
            base_pace = getattr(casting_profile, "pace", base_pace)
            articulation = getattr(casting_profile, "articulation", articulation)
            weight = getattr(casting_profile, "vocal_weight", weight)

        # Merge catalog forbidden styles with character forbidden styles
        forbidden_list = []
        if v_meta.get("elasticity", {}).get("forbidden_styles"):
            forbidden_list.extend(v_meta["elasticity"]["forbidden_styles"])
        if casting_profile and getattr(casting_profile, "forbidden_styles", None):
            forbidden_list.extend(casting_profile.forbidden_styles)
        if not forbidden_list:
            forbidden_list = ["shrill screaming", "cartoon panic", "melodramatic whining"]

        # Deduplicate forbidden styles
        seen = set()
        clean_forbidden = []
        for f in forbidden_list:
            fl = f.strip().lower()
            if fl and fl not in seen:
                seen.add(fl)
                clean_forbidden.append(f.strip())

        emo_layer = VoiceDNAEmotionalLayer()
        if "anger" in custom_emo:
            emo_layer.anger = custom_emo["anger"]
        if "fear" in custom_emo:
            emo_layer.fear = custom_emo["fear"]

        return cls(
            character_id=character_id,
            character_name=character_name,
            voice_id=voice_id,
            identity=VoiceDNAIdentityLayer(
                base_timbre=timbre,
                base_pitch_category=pitch,
                perceived_age=age,
                resonance="chest" if pitch in ("low", "medium_low") else "throat",
                vocal_weight=weight,
                accent=v_meta.get("ethnicity_accent", "Standard"),
            ),
            behavior=VoiceDNABehaviorLayer(
                baseline_pace=base_pace,
                baseline_energy=base_energy,
                articulation=articulation,
                restraint=restraint,
            ),
            emotional=emo_layer,
            forbidden=VoiceDNAForbiddenLayer(forbidden_behaviors=clean_forbidden),
        )


class VoiceDNABank:
    """
    Project-level repository of Character Voice DNA (voice_dna.json).
    """

    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir).resolve()
        self.dna_file = self.project_dir / "voice_dna.json"
        self.dnas: Dict[str, VoiceDNA] = self._load()

    def _load(self) -> Dict[str, VoiceDNA]:
        if self.dna_file.exists():
            try:
                with open(self.dna_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {k: VoiceDNA.model_validate(v) for k, v in data.items()}
            except Exception as e:
                logger.warning(f"  [VOICE DNA BANK] Notice reading {self.dna_file.name}: {e}")
        return {}

    def save(self) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dna_file.with_suffix(f".tmp_{os.getpid()}_{uuid.uuid4().hex[:6]}")
        try:
            dump_data = {k: v.model_dump() for k, v in self.dnas.items()}
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.dna_file)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    def get_dna(self, character_name_or_id: str) -> Optional[VoiceDNA]:
        clean = character_name_or_id.strip().lower()
        clean_norm = clean.replace("_", " ")
        for cid, dna in self.dnas.items():
            if cid.lower() == clean or dna.character_name.lower() == clean:
                return dna
            if cid.lower().replace("_", " ") == clean_norm or dna.character_name.lower().replace("_", " ") == clean_norm:
                return dna
        return None

    def register_dna(self, dna: VoiceDNA) -> None:
        self.dnas[dna.character_id] = dna
        self.save()
        logger.info(f"  [VOICE DNA BANK] Stored Voice DNA for '{dna.character_name}' ({dna.character_id}).")
