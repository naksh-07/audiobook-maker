#!/usr/bin/env python3
"""
Honest Agent Sound Card Engine (Phase 3).
=========================================
Generates epistemically honest, high-density Agent Sound Cards (v3.0).
Provides an AI creative director or autonomous agent complete sound understanding
without loading, decoding, or listening to the underlying audio file.

Strict Epistemic Transparency:
- [MEASURED DSP]: Deterministic physical measurements (LUFS, True Peak, centroid, duration).
- [CLASSIFIER INFERENCE]: Model predictions with explicit probabilities and ranks.
- [CLAP SEMANTIC]: Open-vocabulary geometric similarity scores.
- [SOURCE METADATA]: Original provider tags, titles, and descriptions.
- [KEYWORD INFERRED]: Rule-based taxonomy classifications.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.sonic_candidate_generators import (
    CandidateRecord,
    _compute_metadata_completeness,
)
from audiobook_factory.sonic_hybrid_reranker import ScoredCandidate


class AgentSoundCard(BaseModel):
    """
    Epistemically honest, strongly-typed representation of an audio asset for AI agents.
    """
    model_config = ConfigDict(extra="ignore")

    # 1. IDENTITY
    asset_id: int = Field(..., description="Unique database catalog ID")
    title: str = Field(..., description="Human-readable asset title")
    filename: str = Field(..., description="Audio filename")
    source_collection: str = Field(default="SoundBank", description="Source provider or pack name")
    license: str = Field(default="Royalty-Free")

    # 2. WHAT IT IS (Taxonomy & Physics)
    category: str = Field(default="SFX")
    subcategory: str = Field(default="General")
    physical_action: str = Field(default="unspecified", description="[INFERRED] Physical action")
    exciter: str = Field(default="unspecified", description="[INFERRED] Striking or excitation material")
    resonator: str = Field(default="unspecified", description="[INFERRED] Resonating body material")
    surface: str = Field(default="unspecified", description="[INFERRED] Surface material")
    environment: str = Field(default="unspecified", description="[INFERRED] Acoustic space")

    # 3. ACOUSTIC (Deterministic Measured DSP)
    duration_sec: float = Field(default=0.0, ge=0.0)
    integrated_lufs: Optional[float] = Field(default=None, description="[MEASURED DSP] EBU R128 LUFS")
    true_peak_dbtp: Optional[float] = Field(default=None, description="[MEASURED DSP] True Peak in dBTP")
    spectral_centroid_hz: Optional[float] = Field(default=None, description="[MEASURED DSP] Center frequency in Hz")
    spectral_brightness: str = Field(default="neutral", description="Bright, warm, dark, or neutral")
    transient_character: str = Field(default="transient", description="Transient or continuous")
    energy_profile: str = Field(default="medium", description="Low, medium, or high")

    # 4. SEMANTIC & CLASSIFIER INFERENCES
    tags: List[str] = Field(default_factory=list)
    top_classifier_labels: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="[CLASSIFIER INFERENCE] AudioSet 527 predictions with raw confidences and ranks"
    )
    clap_similarity: Optional[float] = Field(
        default=None,
        description="[CLAP SEMANTIC] Cosine similarity to search query"
    )

    # 5. CONTEXT & MIX SAFETY
    dramatic_role: str = Field(default="general")
    mood: str = Field(default="default")
    voice_masking_risk: str = Field(default="LOW", description="LOW, MODERATE, or SEVERE")
    whisper_compatibility: float = Field(default=0.5, ge=0.0, le=1.0)
    recommended_ducking_db: float = Field(default=-6.0)

    # 6. TEMPORAL EVENTS
    temporal_events: List[Dict[str, Any]] = Field(default_factory=list)

    # 7. QUALITY & COMPLETENESS
    metadata_completeness_pct: int = Field(default=50, ge=0, le=100)
    analysis_status: str = Field(default="partial")

    # 8. PROVENANCE
    provenance_summary: Dict[str, str] = Field(default_factory=dict)

    # 9. AVAILABILITY
    is_local_cached: bool = Field(default=False)
    is_virtual_jit_ready: bool = Field(default=True)
    file_path: Optional[str] = None

    # 10. RETRIEVAL EVIDENCE & EXPLANATION
    retrieval_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    why_matched: List[str] = Field(default_factory=list)

    def to_agent_markdown(self) -> str:
        """
        Formats an honest, high-density Markdown representation for AI reasoning.
        """
        status_str = "LOCAL (Cached)" if self.is_local_cached else "VIRTUAL (JIT Ready)"
        lufs_str = f"{self.integrated_lufs:.1f} LUFS" if self.integrated_lufs is not None else "Unmeasured"
        peak_str = f"{self.true_peak_dbtp:.1f} dBTP" if self.true_peak_dbtp is not None else "Unmeasured"
        centroid_str = f"{self.spectral_centroid_hz:.0f} Hz ({self.spectral_brightness})" if self.spectral_centroid_hz else "Unmeasured"

        # Classifier breakdown
        class_lines = []
        for cl in self.top_classifier_labels[:3]:
            lbl = cl.get("normalized_label") or cl.get("raw_label", "unknown")
            conf = cl.get("raw_score", 0.0)
            rank = cl.get("rank", 1)
            class_lines.append(f"`{lbl}` (conf: {conf:.2f}, rank #{rank})")
        classifier_summary = ", ".join(class_lines) if class_lines else "None (Unclassified)"

        # CLAP representation
        clap_str = f"{self.clap_similarity:.3f}" if self.clap_similarity is not None else "None"

        # Why matched
        why_section = ""
        if self.why_matched:
            bullets = "\n  - " + "\n  - ".join(self.why_matched)
            why_section = f"\n- **Retrieval Evidence**:{bullets}"

        # Temporal events
        ev_str = f"{len(self.temporal_events)} detected onsets/regions" if self.temporal_events else "None"

        card = (
            f"### 🎵 Sound Card [ID: {self.asset_id}] {self.title}\n"
            f"- **File / Status**: `{self.filename}` | {status_str} | **Duration**: {self.duration_sec:.2f}s\n"
            f"- **Source**: {self.source_collection} ({self.license})\n"
            f"- **Taxonomy [INFERRED]**:\n"
            f"  - Category: `{self.category}` / `{self.subcategory}` | Dramatic Role: `{self.dramatic_role}` (Mood: `{self.mood}`)\n"
            f"  - Physical: Exciter: `{self.exciter}` | Resonator: `{self.resonator}` | Action: `{self.physical_action}` | Surface: `{self.surface}`\n"
            f"- **Acoustics [MEASURED DSP]**:\n"
            f"  - Loudness: {lufs_str} | True Peak: {peak_str}\n"
            f"  - Spectral: Centroid {centroid_str} | Dynamics: `{self.energy_profile}` ({self.transient_character})\n"
            f"- **Classifier Inferences [CLASSIFIER]**:\n"
            f"  - AudioSet: {classifier_summary}\n"
            f"- **Semantic Embedding [CLAP]**:\n"
            f"  - Query Similarity: {clap_str}\n"
            f"- **Mix Compatibility**:\n"
            f"  - Voice Masking Risk: `{self.voice_masking_risk}` (Whisper Compatibility: {self.whisper_compatibility:.2f})\n"
            f"  - Recommended Dialogue Ducking: {self.recommended_ducking_db:.0f} dB\n"
            f"- **Temporal Structure**: {ev_str}\n"
            f"- **Provenance & Quality**:\n"
            f"  - Metadata Completeness: {self.metadata_completeness_pct}% | Status: `{self.analysis_status}`\n"
            f"  - Provenance: DSP=`{self.provenance_summary.get('dsp', 'v1.0')}`, AST=`{self.provenance_summary.get('classifier', 'AudioSet-527')}`, CLAP=`{self.provenance_summary.get('clap', 'HTS-AT')}`"
            f"{why_section}"
        )
        return card

    def to_dict(self) -> Dict[str, Any]:
        """Serializes sound card to dictionary representation."""
        return self.model_dump(mode="json")


class SoundCardBuilder:
    """Factory builder for AgentSoundCard instances."""

    @classmethod
    def from_scored_candidate(cls, scored: ScoredCandidate) -> AgentSoundCard:
        """Constructs an AgentSoundCard from a ScoredCandidate record."""
        cand = scored.candidate
        meta = cand.raw_metadata

        # Spectral brightness label
        centroid = meta.get("spectral_centroid_hz")
        if centroid is not None:
            c_val = float(centroid)
            brightness = "bright" if c_val >= 2500 else ("warm" if c_val <= 1200 else "neutral")
        else:
            brightness = meta.get("wave_style") or "neutral"

        # Energy & Voice risk
        v_risk = meta.get("voice_masking_risk") or "LOW"
        w_compat = float(meta.get("whisper_compatibility") or 0.5)
        duck_db = -16.0 if v_risk == "SEVERE" else (-12.0 if v_risk == "MODERATE" else -6.0)

        # Completeness
        completeness_pct = int(cand.evidence.metadata_completeness * 100)

        # Analysis status
        has_dsp = meta.get("integrated_lufs") is not None
        has_class = bool(cand.evidence.classifier_matches)
        has_clap = cand.evidence.clap_similarity is not None
        if has_dsp and has_class and has_clap:
            status = "full_phase2"
        elif has_dsp:
            status = "dsp_only"
        else:
            status = "source_metadata_only"

        # Provenance summary
        prov = {
            "dsp": meta.get("analysis_version") or "deterministic_v1.0",
            "classifier": "MIT/ast-finetuned-audioset-10-10-0.4593",
            "clap": "laion/clap-htsat-unfused",
        }

        # Build card
        return AgentSoundCard(
            asset_id=cand.asset_id,
            title=cand.title or cand.filename,
            filename=cand.filename,
            source_collection=cand.source_collection,
            license=cand.license,
            category=cand.category,
            subcategory=cand.subcategory,
            physical_action=meta.get("action_type") or "unspecified",
            exciter=meta.get("exciter") or "unspecified",
            resonator=meta.get("resonator") or "unspecified",
            surface=meta.get("surface") or "unspecified",
            environment=meta.get("acoustic_space") or "unspecified",
            duration_sec=cand.duration_sec,
            integrated_lufs=meta.get("integrated_lufs"),
            true_peak_dbtp=meta.get("true_peak_db"),
            spectral_centroid_hz=meta.get("spectral_centroid_hz"),
            spectral_brightness=brightness,
            transient_character=meta.get("temporal_character") or "transient",
            energy_profile=meta.get("energy_profile") or "medium",
            tags=cand.tags.split() if cand.tags else [],
            top_classifier_labels=cand.evidence.classifier_matches,
            clap_similarity=cand.evidence.clap_similarity,
            dramatic_role=meta.get("dramatic_role") or "general",
            mood=cand.mood,
            voice_masking_risk=v_risk,
            whisper_compatibility=w_compat,
            recommended_ducking_db=duck_db,
            temporal_events=cand.evidence.temporal_event_matches,
            metadata_completeness_pct=completeness_pct,
            analysis_status=status,
            provenance_summary=prov,
            is_local_cached=cand.is_downloaded,
            is_virtual_jit_ready=not cand.is_downloaded,
            file_path=cand.filepath,
            retrieval_score=scored.final_score,
            why_matched=scored.why_matched,
        )

    @classmethod
    def from_database_row(cls, row_dict: Dict[str, Any], classifier_tags: Optional[List[Dict[str, Any]]] = None) -> AgentSoundCard:
        """Constructs an AgentSoundCard directly from database catalog row."""
        centroid = row_dict.get("spectral_centroid_hz")
        if centroid is not None:
            c_val = float(centroid)
            brightness = "bright" if c_val >= 2500 else ("warm" if c_val <= 1200 else "neutral")
        else:
            brightness = row_dict.get("wave_style") or "neutral"

        v_risk = row_dict.get("voice_masking_risk") or "LOW"
        w_compat = float(row_dict.get("whisper_compatibility") or 0.5)
        duck_db = -16.0 if v_risk == "SEVERE" else (-12.0 if v_risk == "MODERATE" else -6.0)

        tags_str = row_dict.get("tags") or ""

        return AgentSoundCard(
            asset_id=int(row_dict.get("id") or 0),
            title=row_dict.get("title") or row_dict.get("filename", ""),
            filename=row_dict.get("filename", ""),
            source_collection=row_dict.get("source_collection") or "SoundBank",
            license=row_dict.get("license") or "Royalty-Free",
            category=row_dict.get("category") or "SFX",
            subcategory=row_dict.get("subcategory") or "General",
            physical_action=row_dict.get("action_type") or "unspecified",
            exciter=row_dict.get("exciter") or "unspecified",
            resonator=row_dict.get("resonator") or "unspecified",
            surface=row_dict.get("surface") or "unspecified",
            environment=row_dict.get("acoustic_space") or "unspecified",
            duration_sec=float(row_dict.get("duration_sec") or 0.0),
            integrated_lufs=row_dict.get("integrated_lufs"),
            true_peak_dbtp=row_dict.get("true_peak_db"),
            spectral_centroid_hz=row_dict.get("spectral_centroid_hz"),
            spectral_brightness=brightness,
            transient_character=row_dict.get("temporal_character") or "transient",
            energy_profile=row_dict.get("energy_profile") or "medium",
            tags=tags_str.split() if tags_str else [],
            top_classifier_labels=classifier_tags or [],
            clap_similarity=None,
            dramatic_role=row_dict.get("dramatic_role") or "general",
            mood=row_dict.get("mood") or "default",
            voice_masking_risk=v_risk,
            whisper_compatibility=w_compat,
            recommended_ducking_db=duck_db,
            temporal_events=[],
            metadata_completeness_pct=int(_compute_metadata_completeness(row_dict) * 100),
            analysis_status="database_record",
            provenance_summary={"dsp": row_dict.get("analysis_version") or "v1.0"},
            is_local_cached=bool(row_dict.get("is_downloaded")),
            is_virtual_jit_ready=not bool(row_dict.get("is_downloaded")),
            file_path=row_dict.get("filepath"),
            retrieval_score=None,
            why_matched=["Direct asset lookup"],
        )
