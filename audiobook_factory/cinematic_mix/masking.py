#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: masking.py
Dynamic Dialogue-Aware Masking Analyzer and Guardrails.
Identifies frequency masking regions between lead dialogue and competing stems (MX)
and generates conservative, psychoacoustically safe spectral pocketing automation.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.cinematic_mix.automation import AutomationEvent

logger = logging.getLogger("audiobook_factory.cinematic_mix.masking")

# Hard Guardrail Limits
MAX_NOTCH_DEPTH_DB = -6.50
MIN_SAFE_NOTCH_DEPTH_DB = -1.00
DEFAULT_NOTCH_Q = 1.50
SAFE_DMR_CEILING_DB = 14.00  # If DMR already >= 14dB, music does not mask speech


class MaskingDecision(BaseModel):
    """
    Directorial record of a dynamic dialogue masking calculation.
    """
    model_config = ConfigDict(extra="ignore")

    target_stem: str = Field(default="MX", description="Stem receiving spectral pocketing")
    frequency_hz: int = Field(default=2400, ge=800, le=5000, description="Center frequency for notch pocket in Hz")
    q: float = Field(default=1.5, ge=0.5, le=4.0, description="Q factor / bandwidth of parametric filter")
    depth_db: float = Field(default=-5.0, ge=-8.0, le=0.0, description="Notch attenuation depth in dB")
    reason: str = Field(default="", description="Reason for masking adjustment")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Confidence in masking risk assessment")
    guardrail_applied: bool = Field(default=False, description="Whether conservative guardrails curtailed the adjustment")
    guardrail_reason: Optional[str] = Field(default=None, description="Explanation of applied guardrail")

    @property
    def filter_string(self) -> str:
        """Generates the corresponding FFmpeg parametric equalizer filter string."""
        if abs(self.depth_db) < 0.1:
            return "anull"
        return f"equalizer=f={self.frequency_hz}:width_type=q:w={self.q:.2f}:g={self.depth_db:.2f}"


class DynamicMaskingAnalyzer:
    """
    Analyzes dialogue and competing music context to generate conservative
    dialogue-aware masking automation events.
    Enforces conservative guardrails:
    - Never carves deeper than MAX_NOTCH_DEPTH_DB (-6.5 dB) to prevent hollow music.
    - If DMR is already >= 14 dB: do nothing (depth = 0.0).
    - If focus is music and music_priority >= 0.8: do nothing or minimal cut (-1.5 dB).
    """

    def __init__(self, default_frequency_hz: int = 2400):
        self.default_frequency_hz = default_frequency_hz

    def evaluate_masking(
        self,
        start_sec: float,
        end_sec: float,
        attention_target: str,
        attention_priority: float = 0.50,
        speech_style: Optional[str] = None,
        voice_persona: Optional[str] = None,
        estimated_dmr_db: Optional[float] = None,
        music_priority: float = 0.50,
    ) -> MaskingDecision:
        """
        Computes the conservative masking decision for an attention window.
        """
        style = (speech_style or "").strip().lower()
        persona = (voice_persona or "").strip().lower()

        # Guardrail 1: If DMR is already sufficient, zero masking needed
        if estimated_dmr_db is not None and estimated_dmr_db >= SAFE_DMR_CEILING_DB:
            return MaskingDecision(
                target_stem="MX",
                frequency_hz=self.default_frequency_hz,
                q=DEFAULT_NOTCH_Q,
                depth_db=0.0,
                reason="DMR is already >= 14.0 dB; no vocal masking risk (already compliant)",
                confidence=0.95,
                guardrail_applied=True,
                guardrail_reason=f"Measured DMR {estimated_dmr_db:.1f} dB exceeds 14.0 dB ceiling; notch suppressed to protect music body",
            )

        # Guardrail 2: If scene attention explicitly focuses on music
        if attention_target == "music" and music_priority >= 0.80:
            return MaskingDecision(
                target_stem="MX",
                frequency_hz=self.default_frequency_hz,
                q=DEFAULT_NOTCH_Q,
                depth_db=-1.5,
                reason="Music is narrative focus; minimal spectral carve to maintain melodic fullness (softened for music focus)",
                confidence=0.90,
                guardrail_applied=True,
                guardrail_reason="Music priority >= 0.80; notch relaxed from standard to -1.5 dB",
            )

        # Gender / Persona formant center frequency determination
        if any(k in style for k in ("whisper", "intimate", "quiet", "asides", "secret")):
            freq_hz = 2800
        else:
            female_personas = {"aoede", "kore", "leda", "zephyr", "achernar"}
            if any(p in persona for p in female_personas) or "female" in persona:
                freq_hz = 2600
            elif any(p in persona for p in ("charon", "fenrir", "puck", "zeus", "orpheus")) or "male" in persona:
                freq_hz = 2200
            else:
                freq_hz = self.default_frequency_hz

        # Determine target depth based on speech style and priority
        if any(k in style for k in ("whisper", "intimate", "quiet", "asides", "secret")):
            # Intimate whispers have soft consonant energy; need full pocketing
            raw_depth = -6.0 - (attention_priority * 1.5)
            reason = "Whisper speech requires clean spectral pocketing in vocal corridor"
        elif any(k in style for k in ("shout", "yell", "battlecry", "loud", "rage")):
            # Shouting has high acoustic energy; lighter notch needed unless priority is high
            raw_depth = -3.5 - (attention_priority * 3.5)
            reason = "Shouted speech naturally cuts through music; mild pocketing"
        else:
            # Standard conversational speech
            raw_depth = -5.0 - (attention_priority * 2.0)
            reason = "Standard dialogue presence protection"

        # Music priority relaxation: if music priority is high, soften notch depth
        if music_priority >= 0.70:
            raw_depth = max(-2.5, raw_depth + 3.0)
            reason += "; softened for music focus"

        # Apply Hard Guardrail Ceiling
        final_depth = max(MAX_NOTCH_DEPTH_DB, raw_depth)
        guardrail_applied = bool(final_depth > raw_depth)

        return MaskingDecision(
            target_stem="MX",
            frequency_hz=freq_hz,
            q=DEFAULT_NOTCH_Q,
            depth_db=final_depth,
            reason=reason,
            confidence=0.85,
            guardrail_applied=guardrail_applied,
            guardrail_reason="Capped at -6.5 dB ceiling" if guardrail_applied else None,
        )

    def generate_masking_event(
        self,
        start_sec: float,
        end_sec: float,
        decision: MaskingDecision,
    ) -> AutomationEvent:
        """
        Converts a MaskingDecision into a typed AutomationEvent for the MX stem.
        """
        return AutomationEvent(
            start=start_sec,
            end=end_sec,
            target="MX",
            parameter="eq_depth",
            value=decision.depth_db,
            curve="smooth",
            priority=0.80,
            hierarchy="ATTENTION_PROTECTION",
            reason=decision.reason,
            metadata={
                "frequency_hz": decision.frequency_hz,
                "q": decision.q,
                "filter_string": decision.filter_string,
                "guardrail_applied": decision.guardrail_applied,
            },
        )
