#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: stem_interaction.py
Manages context-aware stem interactions across DX, MX, FX, and AMB.
Prevents uncalibrated blanket ducking while preserving environmental naturalism.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent


class StemInteractionPlan(BaseModel):
    """
    Directorial stem interaction plan for an active attention window.
    Specifies relative attenuation adjustments across all four stems.
    """
    model_config = ConfigDict(extra="ignore")

    dx_gain_db: float = Field(default=0.0, description="Lead dialogue gain adjustment in dB")
    mx_attenuation_db: float = Field(default=0.0, description="Music stem attenuation in dB (<= 0.0)")
    fx_attenuation_db: float = Field(default=0.0, description="Foley/SFX stem attenuation in dB (<= 0.0)")
    amb_attenuation_db: float = Field(default=0.0, description="Ambience stem attenuation in dB (<= 0.0)")
    mx_notch_needed: bool = Field(default=False, description="Whether spectral pocketing is required on MX")
    active_pairs: List[str] = Field(default_factory=list, description="Interaction pairs evaluated (e.g. ['DX-MX', 'DX-FX'])")
    reason: str = Field(default="", description="Narrative rationale for interaction adjustments")


class StemInteractionEngine:
    """
    Evaluates multitrack interactions between DX, MX, FX, and AMB.
    Core Invariant: Preserves environmental naturalism. Never turns the audio drama
    into a sterile vacuum by muting the ambient world during normal dialogue.
    """

    def evaluate_interactions(
        self,
        scene_intent: SceneMixIntent,
        focus_target: str,
        focus_priority: float = 0.50,
        speech_style: Optional[str] = None,
        is_dialogue_active: bool = True,
    ) -> StemInteractionPlan:
        """
        Determines the appropriate stem interaction plan given narrative focus and scene intent.
        """
        f = (focus_target or "").lower().strip()
        style = (speech_style or "").lower().strip()
        pairs = []

        # If no dialogue is active, music and ambience should NEVER duck blindly
        if not is_dialogue_active:
            if f in ("fx", "door", "strike", "impact", "explosion"):
                # FX transient occurs during dialogue pause
                pairs.extend(["MX-FX", "AMB-FX"])
                mx_att = -3.0 if scene_intent.music_priority >= 0.75 else -8.0
                return StemInteractionPlan(
                    dx_gain_db=0.0,
                    mx_attenuation_db=mx_att,
                    fx_attenuation_db=0.0,
                    amb_attenuation_db=-4.0,
                    mx_notch_needed=False,
                    active_pairs=pairs,
                    reason="Transient FX punch during speech pause; momentary MX/AMB tuck",
                )
            elif f in ("silence", "pause", "smother_cut"):
                pairs.extend(["MX-AMB", "MX-FX"])
                return StemInteractionPlan(
                    dx_gain_db=0.0,
                    mx_attenuation_db=-24.0,
                    fx_attenuation_db=-18.0,
                    amb_attenuation_db=-14.0,
                    mx_notch_needed=False,
                    active_pairs=pairs,
                    reason="Intentional silence window; negative sound design",
                )
            else:
                # Normal pause between speech: Music and ambience breathe naturally
                return StemInteractionPlan(
                    dx_gain_db=0.0,
                    mx_attenuation_db=0.0,
                    fx_attenuation_db=0.0,
                    amb_attenuation_db=0.0,
                    mx_notch_needed=False,
                    active_pairs=[],
                    reason="Dialogue pause; ambient and musical beds breathe unattenuated",
                )

        # Dialogue is active:
        # Case 1: Intimate Whisper
        if any(k in f or k in style for k in ("whisper", "intimate", "secret", "quiet")):
            pairs.extend(["DX-MX", "DX-FX", "DX-AMB"])
            # Whisper needs deep music suppression, selective Foley attenuation, but subtle room tone preserved
            mx_att = -14.0 if scene_intent.music_priority < 0.7 else -10.0
            return StemInteractionPlan(
                dx_gain_db=0.0,
                mx_attenuation_db=mx_att,
                fx_attenuation_db=-6.0,
                amb_attenuation_db=-3.5,
                mx_notch_needed=True,
                active_pairs=pairs,
                reason="Protect delicate whispered dialogue intelligibility",
            )

        # Case 2: Music is Primary Focus (e.g. musical revelation, leitmotif climax)
        if f in ("music", "score", "theme", "revelation", "orchestra") or (
            scene_intent.focus == "music" and scene_intent.music_priority >= 0.80
        ):
            pairs.extend(["MX-DX", "MX-AMB", "MX-FX"])
            # Music is foreground! Dialogue protected only with minimal pocketing; music does not duck heavily
            return StemInteractionPlan(
                dx_gain_db=0.0,
                mx_attenuation_db=-2.0 if focus_priority > 0.9 else -4.0,
                fx_attenuation_db=-5.0,
                amb_attenuation_db=-5.0,
                mx_notch_needed=True,
                active_pairs=pairs,
                reason="Musical revelation commands listener attention; score remains prominent",
            )

        # Case 3: Action / Shouting / Combat
        if any(k in f or k in style for k in ("shout", "battle", "combat", "yell", "roar")):
            pairs.extend(["DX-MX", "FX-MX"])
            # In battle, dialogue and Foley are both energetic; music stays driving
            return StemInteractionPlan(
                dx_gain_db=0.0,
                mx_attenuation_db=-6.0,
                fx_attenuation_db=0.0,
                amb_attenuation_db=-2.0,
                mx_notch_needed=True,
                active_pairs=pairs,
                reason="Combat energy; driving music with unattenuated physical Foley impacts",
            )

        # Case 4: Standard Conversational Speech
        pairs.extend(["DX-MX"])
        mx_att = -8.0 if scene_intent.dialogue_priority >= 0.8 else -5.0
        return StemInteractionPlan(
            dx_gain_db=0.0,
            mx_attenuation_db=mx_att,
            fx_attenuation_db=-1.0,  # Subtle touch, mostly preserved
            amb_attenuation_db=-1.5,  # Room tone preserved (Section 19 naturalism!)
            mx_notch_needed=True,
            active_pairs=pairs,
            reason="Standard exposition; speech protection with preserved environmental naturalism",
        )
