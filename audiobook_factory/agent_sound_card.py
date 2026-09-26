#!/usr/bin/env python3
"""
Honest Agent Sound Card Engine (Phase 3 Hardened).
=================================================
Generates epistemically honest, high-density Agent Sound Cards (v3.1).
Provides an AI creative director or autonomous agent complete sound understanding
without loading, decoding, or listening to the underlying audio file.

Strict Epistemic Transparency Hierarchy:
- [MEASURED DSP]: Deterministic physical measurements (LUFS, True Peak, centroid, speech corridor density, duration).
- [CLASSIFIER INFERENCE]: Model predictions with explicit probabilities and ranks (AST AudioSet-527).
- [CLAP SEMANTIC]: Open-vocabulary geometric similarity scores (LAION-CLAP 512-d).
- [SOURCE METADATA]: Original provider tags, titles, descriptions, and catalog attributes.
- [AGENT INTERPRETATION]: Creative, narrative, or mix decisions rendered by an autonomous agent.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.sonic_candidate_generators import (
    CandidateRecord,
    _compute_metadata_completeness,
)
from audiobook_factory.sonic_hybrid_reranker import ScoredCandidate


class AgentInterpretation(BaseModel):
    """Creative, narrative, or mix interpretation produced by an autonomous agent."""
    model_config = ConfigDict(extra="ignore")

    evaluator_agent: str = Field(..., description="Agent name (e.g. 'SoundDesignDirector', 'MusicCueDirector', 'MixDirector', 'RetrievalAgent')")
    evaluated_at: str = Field(..., description="ISO 8601 timestamp of evaluation")
    scene_context: Optional[str] = Field(default=None, description="Scene ID or dramatic context")

    # Creative / Directorial Decisions (Evaluated at scene/usage time)
    assigned_dramatic_role: Optional[str] = Field(default=None, description="Contextual dramatic role assigned by director")
    scene_purpose: Optional[str] = Field(default=None, description="Specific dramatic purpose in scene")
    emotional_suitability: Optional[str] = Field(default=None, description="Contextual emotional suitability / mood")
    assigned_mood: Optional[str] = Field(default=None, description="Contextual mood (alias to emotional_suitability)")
    voice_masking_judgment: Optional[str] = Field(default=None, description="Voice masking judgment: LOW, MODERATE, SEVERE")
    voice_masking_assessment: Optional[str] = Field(default=None, description="Voice masking assessment (alias to voice_masking_judgment)")
    dialogue_ducking_amount_db: Optional[float] = Field(default=None, description="Target dialogue ducking in dB")
    contextual_ducking_db: Optional[float] = Field(default=None, description="Contextual ducking in dB (alias to dialogue_ducking_amount_db)")
    placement_usage: Optional[str] = Field(default=None, description="Timeline placement and recommended usage in scene")
    final_taxonomy: Optional[str] = Field(default=None, description="Final creative taxonomy when requiring interpretation")

    mix_notes: Optional[str] = Field(default=None, description="Directorial or acoustic mix notes")
    creative_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Confidence of the agent's interpretation; None if unprovided")
    conflict_notes: Optional[str] = Field(default=None, description="Explanations of any tension between source tags and classifier evidence")

    def model_post_init(self, __context: Any) -> None:
        if self.emotional_suitability is None and self.assigned_mood is not None:
            self.emotional_suitability = self.assigned_mood
        elif self.assigned_mood is None and self.emotional_suitability is not None:
            self.assigned_mood = self.emotional_suitability

        if self.voice_masking_judgment is None and self.voice_masking_assessment is not None:
            self.voice_masking_judgment = self.voice_masking_assessment
        elif self.voice_masking_assessment is None and self.voice_masking_judgment is not None:
            self.voice_masking_assessment = self.voice_masking_judgment

        if self.dialogue_ducking_amount_db is None and self.contextual_ducking_db is not None:
            self.dialogue_ducking_amount_db = self.contextual_ducking_db
        elif self.contextual_ducking_db is None and self.dialogue_ducking_amount_db is not None:
            self.contextual_ducking_db = self.dialogue_ducking_amount_db


class AgentSoundCard(BaseModel):
    """
    Epistemically honest, strongly-typed representation of an audio asset for AI agents.
    Communicates strict evidence levels:
    MEASURED > CLASSIFIER > SOURCE_METADATA > AGENT_INTERPRETATION
    """
    model_config = ConfigDict(extra="ignore")

    # 1. IDENTITY
    asset_id: int = Field(..., description="Unique database catalog ID")
    title: str = Field(..., description="Human-readable asset title")
    filename: str = Field(..., description="Audio filename")
    source_collection: str = Field(default="SoundBank", description="[SOURCE_METADATA] Source provider or pack name")
    license: str = Field(default="Royalty-Free", description="[SOURCE_METADATA] License terms")

    # 2. WHAT IT IS (Taxonomy & Source Metadata)
    category: str = Field(default="SFX", description="[SOURCE_METADATA] Category")
    subcategory: str = Field(default="General", description="[SOURCE_METADATA] Subcategory")
    physical_action: str = Field(default="unspecified", description="[SOURCE_METADATA] Physical action")
    exciter: str = Field(default="unspecified", description="[SOURCE_METADATA] Striking or excitation material")
    resonator: str = Field(default="unspecified", description="[SOURCE_METADATA] Resonating body material")
    surface: str = Field(default="unspecified", description="[SOURCE_METADATA] Surface material")
    environment: str = Field(default="unspecified", description="[SOURCE_METADATA] Acoustic space")

    # 3. ACOUSTIC (Deterministic Measured DSP)
    duration_sec: float = Field(default=0.0, ge=0.0, description="[MEASURED] Total duration in seconds")
    integrated_lufs: Optional[float] = Field(default=None, description="[MEASURED] EBU R128 LUFS")
    true_peak_dbtp: Optional[float] = Field(default=None, description="[MEASURED] True Peak in dBTP")
    spectral_centroid_hz: Optional[float] = Field(default=None, description="[MEASURED] Center frequency in Hz")
    spectral_brightness: str = Field(default="neutral", description="[MEASURED] Bright, warm, dark, or neutral")
    transient_character: str = Field(default="transient", description="[MEASURED] Transient or continuous")
    energy_profile: str = Field(default="medium", description="[MEASURED] Low, medium, or high")
    speech_corridor_density: Optional[float] = Field(
        default=None,
        description="[MEASURED] Ratio of energy in 1kHz-4kHz human voice corridor"
    )

    # 4. SEMANTIC & CLASSIFIER INFERENCES
    tags: List[str] = Field(default_factory=list, description="[SOURCE_METADATA] Original tags")
    top_classifier_labels: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="[CLASSIFIER] AudioSet 527 predictions with raw confidences and ranks"
    )
    vocal_speech_probability: Optional[float] = Field(
        default=None,
        description="[CLASSIFIER] AudioSet prediction probability for speech/vocal classes"
    )
    clap_similarity: Optional[float] = Field(
        default=None,
        description="[CLASSIFIER] Cosine similarity to search query"
    )

    # 5. CONTEXT & METADATA (Epistemically Qualified)
    source_mood: Optional[str] = Field(default=None, description="[SOURCE_METADATA] Original pack mood")
    classifier_mood: Optional[str] = Field(default=None, description="[CLASSIFIER] AudioSet mood prediction")
    mood: str = Field(default="UNINTERPRETED", description="[AGENT_INTERPRETATION / EVIDENCE] Resolved mood display or conflict")
    mood_evidence: str = Field(default="[AWAITING_AGENT_EVALUATION]")
    emotional_suitability: str = Field(default="UNINTERPRETED", description="[AGENT_INTERPRETATION] Contextual emotional suitability")
    emotional_suitability_evidence: str = Field(default="[AWAITING_AGENT_EVALUATION]")

    dramatic_role: str = Field(default="UNASSIGNED", description="[AGENT_INTERPRETATION] Dramatic role (unassigned until evaluated by scene agent)")
    dramatic_role_evidence: str = Field(default="[AWAITING_AGENT_EVALUATION]")
    scene_purpose: str = Field(default="UNASSIGNED", description="[AGENT_INTERPRETATION] Specific dramatic scene purpose")
    scene_purpose_evidence: str = Field(default="[AGENT_INTERPRETATION: Awaiting SoundDirector]")

    voice_masking_judgment: str = Field(default="UNASSESSED", description="[AGENT_INTERPRETATION] Voice masking judgment")
    voice_masking_risk: Optional[str] = Field(default="UNASSESSED", description="[AGENT_INTERPRETATION] Voice masking risk alias")
    voice_masking_evidence: str = Field(
        default="[UNASSESSED: Requires Mix Agent evaluation based on measured speech corridor density]"
    )
    whisper_compatibility: Optional[float] = Field(default=None, description="[AGENT_INTERPRETATION / EMPIRICAL] Empirical whisper compatibility score if calibrated")
    whisper_compatibility_evidence: str = Field(default="[NOT_CALIBRATED]")
    dialogue_ducking_amount_db: Optional[float] = Field(default=None, description="[AGENT_INTERPRETATION] Target dialogue ducking in dB")
    recommended_ducking_db: Optional[float] = Field(default=None, description="[AGENT_INTERPRETATION] Target dialogue ducking in dB set by mix agent")
    recommended_ducking_evidence: str = Field(default="[SCENE_DEPENDENT / DEFERRED_TO_MIX_AGENT]")

    placement_usage: str = Field(default="UNASSIGNED", description="[AGENT_INTERPRETATION] Timeline placement and recommended usage")
    placement_usage_evidence: str = Field(default="[AGENT_INTERPRETATION: Awaiting SoundDirector]")
    final_taxonomy: str = Field(default="UNASSIGNED", description="[AGENT_INTERPRETATION] Final creative taxonomy when requiring interpretation")
    final_taxonomy_evidence: str = Field(default="[AGENT_INTERPRETATION: Awaiting creative interpretation]")

    # 6. TEMPORAL EVENTS & ACTIVE REGION
    active_region_str: str = Field(default="unavailable (unmeasured)")
    temporal_events: List[Dict[str, Any]] = Field(default_factory=list)

    # 7. MUSIC & TONAL INTELLIGENCE
    is_tonal: Optional[bool] = Field(default=None)
    is_tonal_str: str = Field(default="unavailable (unmeasured)")
    detected_pitch_hz: Optional[float] = Field(default=None)
    tuning_hz: Optional[float] = Field(default=None)
    bpm_str: str = Field(default="unavailable (unmeasured)")
    key_tonality_str: str = Field(default="unavailable (unmeasured)")
    time_signature_str: str = Field(default="unavailable (unmeasured)")

    # 8. AGENT CREATIVE INTERPRETATION (First-class Container)
    agent_interpretation: Optional[AgentInterpretation] = Field(
        default=None,
        description="Downstream agent creative interpretation (None if asset is in unassigned catalog storage)"
    )

    # 9. QUALITY & COMPLETENESS
    metadata_completeness_pct: int = Field(default=50, ge=0, le=100)
    analysis_status: str = Field(default="partial")

    # 10. PROVENANCE
    provenance_summary: Dict[str, str] = Field(default_factory=dict)

    # 11. AVAILABILITY
    is_local_cached: bool = Field(default=False)
    is_virtual_jit_ready: bool = Field(default=True)
    file_path: Optional[str] = None

    # 12. RETRIEVAL EVIDENCE & EXPLANATION
    retrieval_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    why_matched: List[str] = Field(default_factory=list)

    def attach_interpretation(self, interpretation: AgentInterpretation) -> AgentSoundCard:
        """
        Attaches downstream agent creative interpretation to the card without mutating
        underlying raw measurements or classifier inferences.
        """
        self.agent_interpretation = interpretation
        agent_name = interpretation.evaluator_agent

        if interpretation.assigned_dramatic_role:
            self.dramatic_role = interpretation.assigned_dramatic_role
            self.dramatic_role_evidence = f"[AGENT INTERPRETATION: {agent_name}]"

        if interpretation.scene_purpose:
            self.scene_purpose = interpretation.scene_purpose
            self.scene_purpose_evidence = f"[AGENT INTERPRETATION: {agent_name}]"

        eff_mood = interpretation.emotional_suitability or interpretation.assigned_mood
        if eff_mood:
            self.mood = eff_mood
            self.emotional_suitability = eff_mood
            self.mood_evidence = f"[AGENT INTERPRETATION: {agent_name}]"
            self.emotional_suitability_evidence = f"[AGENT INTERPRETATION: {agent_name}]"

        eff_mask = interpretation.voice_masking_judgment or interpretation.voice_masking_assessment
        if eff_mask:
            self.voice_masking_risk = eff_mask
            self.voice_masking_judgment = eff_mask
            self.voice_masking_evidence = f"[AGENT INTERPRETATION: {agent_name}]"

        eff_duck = interpretation.dialogue_ducking_amount_db if interpretation.dialogue_ducking_amount_db is not None else interpretation.contextual_ducking_db
        if eff_duck is not None:
            self.recommended_ducking_db = eff_duck
            self.dialogue_ducking_amount_db = eff_duck
            self.recommended_ducking_evidence = f"[AGENT INTERPRETATION: {agent_name}]"

        if interpretation.placement_usage:
            self.placement_usage = interpretation.placement_usage
            self.placement_usage_evidence = f"[AGENT INTERPRETATION: {agent_name}]"

        if interpretation.final_taxonomy:
            self.final_taxonomy = interpretation.final_taxonomy
            self.final_taxonomy_evidence = f"[AGENT INTERPRETATION: {agent_name}]"

        return self

    def to_agent_markdown(self) -> str:
        """
        Formats an honest, high-density Markdown representation for AI reasoning.
        Strictly conveys evidence hierarchy:
        MEASURED > CLASSIFIER > EMBEDDING > SOURCE METADATA > AGENT INTERPRETATION
        """
        status_str = "LOCAL (Cached)" if self.is_local_cached else "VIRTUAL (JIT Ready)"
        lufs_str = f"{self.integrated_lufs:.1f} LUFS" if self.integrated_lufs is not None else "Unmeasured"
        peak_str = f"{self.true_peak_dbtp:.1f} dBTP" if self.true_peak_dbtp is not None else "Unmeasured"
        centroid_str = f"{self.spectral_centroid_hz:.0f} Hz ({self.spectral_brightness})" if self.spectral_centroid_hz else "Unmeasured"

        # Classifier breakdown with evidence
        class_lines = []
        for cl in self.top_classifier_labels[:3]:
            lbl = cl.get("normalized_label") or cl.get("raw_label", "unknown")
            conf = cl.get("raw_score", 0.0)
            rank = cl.get("rank", 1)
            class_lines.append(f"`{lbl}` (conf: {conf:.2f}, rank #{rank})")
        classifier_summary = ", ".join(class_lines) if class_lines else "None (Unclassified)"

        # CLAP representation
        clap_str = f"{self.clap_similarity:.3f} [CLAP SIMILARITY]" if self.clap_similarity is not None else "None"

        # Why matched
        why_section = ""
        if self.why_matched:
            bullets = "\n  - " + "\n  - ".join(self.why_matched)
            why_section = f"\n- **Retrieval Evidence**:{bullets}"

        # Temporal events summary (deduplicated by window & type)
        temporal_lines = []
        if self.active_region_str and self.active_region_str != "unavailable (unmeasured)":
            temporal_lines.append(f"Active Region: {self.active_region_str}")

        if self.temporal_events:
            # Group classifier observation windows by window
            obs_windows: Dict[Tuple[float, float], List[str]] = {}
            transient_count = 0
            for ev in self.temporal_events:
                ev_type = ev.get("event_type")
                st = round(float(ev.get("start_sec") or 0.0), 2)
                et = round(float(ev.get("end_sec") or 0.0), 2)
                if ev_type in ("classifier_observation_window", "classifier_event"):
                    meta = ev.get("metadata") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    lbl = meta.get("normalized_label") or meta.get("raw_label") or "observed_class"
                    conf = ev.get("confidence") or 0.0
                    obs_windows.setdefault((st, et), []).append(f"{lbl} ({conf:.2f})")
                elif ev_type == "transient_onset":
                    transient_count += 1

            if obs_windows:
                # Show top 2 distinct observation windows
                for (w_st, w_et), w_lbls in list(obs_windows.items())[:2]:
                    temporal_lines.append(f"Window [{w_st:.2f}s - {w_et:.2f}s] [OBSERVATION WINDOW]: {', '.join(w_lbls[:2])} [CLASSIFIER INFERENCE]")
                if len(obs_windows) > 2:
                    temporal_lines.append(f"... and {len(obs_windows) - 2} more classifier observation windows")

            if transient_count > 0:
                temporal_lines.append(f"{transient_count} transient onsets detected [MEASURED DSP]")

        if not temporal_lines:
            temporal_summary = "None (Unmeasured)"
        else:
            temporal_summary = " | ".join(temporal_lines)

        # Mix safety and directorial badges
        if self.agent_interpretation and self.agent_interpretation.assigned_dramatic_role:
            role_badge = f"{self.dramatic_role} [AGENT_INTERPRETATION: {self.agent_interpretation.evaluator_agent}]"
        else:
            role_badge = f"{self.dramatic_role} {self.dramatic_role_evidence}"

        if self.agent_interpretation and self.agent_interpretation.scene_purpose:
            purpose_badge = f"{self.scene_purpose} [AGENT_INTERPRETATION: {self.agent_interpretation.evaluator_agent}]"
        else:
            purpose_badge = f"{self.scene_purpose} {self.scene_purpose_evidence}"

        eff_mood = (
            self.agent_interpretation.emotional_suitability or self.agent_interpretation.assigned_mood
            if self.agent_interpretation else None
        )
        if eff_mood:
            mood_badge = f"{eff_mood} [AGENT_INTERPRETATION: {self.agent_interpretation.evaluator_agent}]"
        else:
            mood_badge = f"{self.mood} {self.mood_evidence}"

        dens_str = f"{self.speech_corridor_density:.2f}" if self.speech_corridor_density is not None else "Unmeasured"
        v_prob_str = f"{self.vocal_speech_probability:.2f}" if self.vocal_speech_probability is not None else "0.00"

        eff_mask = (
            self.agent_interpretation.voice_masking_judgment or self.agent_interpretation.voice_masking_assessment
            if self.agent_interpretation else None
        )
        if eff_mask:
            v_risk_badge = f"{eff_mask} [AGENT_INTERPRETATION: {self.agent_interpretation.evaluator_agent}]"
        elif self.voice_masking_risk and self.voice_masking_risk != "UNASSESSED":
            v_risk_badge = f"{self.voice_masking_risk} {self.voice_masking_evidence}"
        else:
            v_risk_badge = f"UNASSESSED (Speech Density: {dens_str} [MEASURED], Vocal Presence: {v_prob_str} [CLASSIFIER]) [AWAITING MIX AGENT]"

        eff_duck = (
            self.agent_interpretation.dialogue_ducking_amount_db
            if (self.agent_interpretation and self.agent_interpretation.dialogue_ducking_amount_db is not None)
            else (self.agent_interpretation.contextual_ducking_db if self.agent_interpretation else None)
        )
        if eff_duck is not None:
            duck_badge = f"{eff_duck:.0f} dB [AGENT_INTERPRETATION: {self.agent_interpretation.evaluator_agent}]"
        elif self.recommended_ducking_db is not None:
            duck_badge = f"{self.recommended_ducking_db:.0f} dB {self.recommended_ducking_evidence}"
        else:
            duck_badge = "SCENE_DEPENDENT (Deferred to Track 11 Mix Director)"

        if self.agent_interpretation and self.agent_interpretation.placement_usage:
            placement_badge = f"{self.placement_usage} [AGENT_INTERPRETATION: {self.agent_interpretation.evaluator_agent}]"
        else:
            placement_badge = f"{self.placement_usage} {self.placement_usage_evidence}"

        if self.agent_interpretation and self.agent_interpretation.final_taxonomy:
            taxonomy_badge = f"{self.final_taxonomy} [AGENT_INTERPRETATION: {self.agent_interpretation.evaluator_agent}]"
        else:
            taxonomy_badge = f"{self.final_taxonomy} {self.final_taxonomy_evidence}"

        w_compat_badge = f"{self.whisper_compatibility:.2f}" if self.whisper_compatibility is not None else "NOT_CALIBRATED"

        # Agent creative interpretation section
        if self.agent_interpretation:
            interp = self.agent_interpretation
            conf_str = f"{interp.creative_confidence:.2f}" if interp.creative_confidence is not None else "Unspecified"
            duck_val_str = f"{eff_duck:.1f} dB" if eff_duck is not None else "None"
            agent_section = (
                f"\n- **Agent Creative Interpretation**: [AGENT_INTERPRETATION]\n"
                f"  - Evaluator: `{interp.evaluator_agent}` (Scene: `{interp.scene_context or 'Global'}` | Conf: `{conf_str}`)\n"
                f"  - Assigned Role: `{interp.assigned_dramatic_role or 'Unassigned'}` | Scene Purpose: `{interp.scene_purpose or 'Unassigned'}`\n"
                f"  - Emotional Suitability: `{eff_mood or 'Unassigned'}` | Placement / Usage: `{interp.placement_usage or 'Unassigned'}`\n"
                f"  - Final Taxonomy: `{interp.final_taxonomy or 'Unassigned'}`\n"
                f"  - Mix Decision: Masking=`{eff_mask or 'Unspecified'}`, Ducking=`{duck_val_str}`"
            )
            if interp.mix_notes:
                agent_section += f"\n  - Mix Notes: {interp.mix_notes}"
            if interp.conflict_notes:
                agent_section += f"\n  - Conflict Resolution: {interp.conflict_notes}"
        else:
            agent_section = (
                f"\n- **Agent Creative Interpretation**: None [AGENT_INTERPRETATION: Asset unassigned in catalog; dramatic role, scene purpose, emotional suitability, and dialogue ducking evaluated per scene by SoundDirector / Mix Director]"
            )

        card = (
            f"### 🎵 Sound Card [ID: {self.asset_id}] {self.title}\n"
            f"- **File / Status [SOURCE_METADATA]**: `{self.filename}` | {status_str} | **Duration [MEASURED]**: {self.duration_sec:.2f}s\n"
            f"- **Source [SOURCE_METADATA]**: {self.source_collection} ({self.license})\n"
            f"- **Taxonomy [SOURCE METADATA]**:\n"
            f"  - Category [SOURCE_METADATA]: `{self.category}` / `{self.subcategory}`\n"
            f"  - Physical [SOURCE_METADATA]: Exciter: `{self.exciter}` | Resonator: `{self.resonator}` | Action: `{self.physical_action}` | Surface: `{self.surface}`\n"
            f"  - Source Pack Mood [SOURCE_METADATA]: `{self.source_mood or 'unspecified'}`\n"
            f"- **Acoustics [MEASURED DSP]**:\n"
            f"  - Loudness [MEASURED]: {lufs_str} | True Peak [MEASURED]: {peak_str}\n"
            f"  - Spectral [MEASURED]: Centroid {centroid_str} | Dynamics [MEASURED]: `{self.energy_profile}` ({self.transient_character})\n"
            f"  - Speech Corridor Density (1kHz–4kHz) [MEASURED]: {dens_str}\n"
            f"- **Classifier Inferences [CLASSIFIER]**:\n"
            f"  - AudioSet [CLASSIFIER]: {classifier_summary}\n"
            f"  - Vocal Speech Probability [CLASSIFIER]: {v_prob_str}\n"
            f"  - Classifier Mood Evidence [CLASSIFIER]: {self.classifier_mood or 'None'}\n"
            f"- **Semantic Embedding [CLAP]**:\n"
            f"  - Query Similarity [CLASSIFIER]: {clap_str}\n"
            f"- **Directorial Decisions & Mix Safety [AGENT_INTERPRETATION]**:\n"
            f"  - Dramatic Role [AGENT_INTERPRETATION]: `{role_badge}`\n"
            f"  - Scene Purpose [AGENT_INTERPRETATION]: `{purpose_badge}`\n"
            f"  - Emotional Suitability [AGENT_INTERPRETATION]: `{mood_badge}`\n"
            f"  - Voice-Masking Judgment [AGENT_INTERPRETATION]: `{v_risk_badge}` (Whisper Compatibility: `{w_compat_badge}`)\n"
            f"  - Dialogue Ducking Amount [AGENT_INTERPRETATION]: `{duck_badge}`\n"
            f"  - Placement / Recommended Usage [AGENT_INTERPRETATION]: `{placement_badge}`\n"
            f"  - Final Taxonomy [AGENT_INTERPRETATION]: `{taxonomy_badge}`\n"
            f"- **Temporal Structure**: {temporal_summary}\n"
            f"- **Music & Tonal [MEASURED / SOURCE METADATA]**:\n"
            f"  - Tonal [MEASURED]: {self.is_tonal_str} | BPM [SOURCE_METADATA / MEASURED]: {self.bpm_str} | Key [SOURCE_METADATA]: {self.key_tonality_str} | Time Signature [SOURCE_METADATA]: {self.time_signature_str}\n"
            f"{agent_section}\n"
            f"- **Provenance & Quality**:\n"
            f"  - Metadata Completeness: {self.metadata_completeness_pct}% | Status: `{self.analysis_status}`\n"
            f"  - Provenance: DSP=`{self.provenance_summary.get('dsp', 'v1.0')}`, AST=`{self.provenance_summary.get('classifier', 'AudioSet-527')}`, CLAP=`{self.provenance_summary.get('clap', 'HTS-AT')}`"
            f"{why_section}"
        )
        return card

    def to_dict(self) -> Dict[str, Any]:
        """Serializes sound card to dictionary representation."""
        return self.model_dump(mode="json")


# -----------------------------------------------------------------------------
# Epistemic Resolution Helpers (Strictly Evidence-Bound, Zero Creative Invention)
# -----------------------------------------------------------------------------
def _resolve_mood_and_evidence(
    raw_mood: Optional[str],
    classifier_tags: Optional[List[Dict[str, Any]]],
) -> Tuple[str, str, Optional[str], Optional[str]]:
    """
    Exposes source mood and classifier mood predictions without making a creative judgment.
    Preserves any tension/conflict between catalog and classifier evidence.
    Returns: (mood_display_str, mood_evidence_badge, source_mood, classifier_mood)
    """
    clean_src = (
        raw_mood.lower().strip()
        if raw_mood and raw_mood.lower().strip() not in ("default", "unspecified", "none", "")
        else None
    )

    best_cls_mood = None
    best_cls_score = 0.0
    if classifier_tags:
        for t in classifier_tags:
            lbl = (t.get("normalized_label") or t.get("raw_label") or "").lower()
            raw_lbl = (t.get("raw_label") or "").lower()
            score = float(t.get("raw_score") or 0.0)
            if score >= 0.05 and ("mood." in lbl or "scary" in lbl or "scary" in raw_lbl or "horror" in lbl):
                c_lbl = lbl.replace("music.mood.", "").replace("music.", "").strip()
                if score > best_cls_score:
                    best_cls_score = score
                    best_cls_mood = c_lbl

    if clean_src and best_cls_mood:
        if clean_src == best_cls_mood:
            return clean_src, f"[AGREED: Source & AudioSet conf: {best_cls_score:.3f}]", clean_src, best_cls_mood
        else:
            display = f"Catalog: '{clean_src}' vs Classifier: '{best_cls_mood}' ({best_cls_score:.3f})"
            return display, "[CONFLICT / REQUIRES AGENT EVALUATION]", clean_src, best_cls_mood

    if clean_src:
        return clean_src, "[SOURCE METADATA]", clean_src, None

    if best_cls_mood:
        return f"{best_cls_mood} (conf: {best_cls_score:.3f})", f"[CLASSIFIER INFERENCE, AudioSet conf: {best_cls_score:.3f}]", None, best_cls_mood

    return "UNINTERPRETED", "[AWAITING_AGENT_EVALUATION]", None, None


def _resolve_dramatic_role(role_val: Optional[str]) -> Tuple[str, str]:
    """Exposes dramatic role from source metadata, or marks as UNASSIGNED for agent direction."""
    if role_val and role_val.lower().strip() not in ("general", "default", "unspecified", "none", ""):
        return role_val, "[SOURCE METADATA]"
    return "UNASSIGNED", "[AWAITING_AGENT_EVALUATION]"


def _extract_vocal_presence(classifier_tags: Optional[List[Dict[str, Any]]]) -> Optional[float]:
    """Extracts maximum classifier probability for human vocal, speech, or chatter classes."""
    if not classifier_tags:
        return None
    scores = []
    for t in classifier_tags:
        lbl = (t.get("normalized_label") or t.get("raw_label") or "").lower()
        score = float(t.get("raw_score") or 0.0)
        if any(k in lbl for k in ("vocal.speech", "speech", "chatter", "walla", "singing", "vocal")):
            scores.append(score)
    return round(max(scores), 4) if scores else None


def _resolve_active_region(
    duration_sec: float,
    temporal_events: Optional[List[Dict[str, Any]]] = None,
    sonic_genome: Optional[Any] = None,
) -> str:
    """
    Honest active sound region reporting.
    Distinguishes complete file measurements from truncated analysis windows.
    """
    active_start = None
    active_end = None
    if sonic_genome and hasattr(sonic_genome, "measured_facts") and sonic_genome.measured_facts:
        t = sonic_genome.measured_facts.temporal
        active_start = t.active_start_sec
        active_end = t.active_end_sec

    if active_start is None and temporal_events:
        for ev in temporal_events:
            if ev.get("event_type") == "active_region":
                active_start = ev.get("start_sec")
                active_end = ev.get("end_sec")
                break

    if active_start is not None and active_end is not None:
        if duration_sec > 60.0 and abs(float(active_end) - 60.0) < 0.5:
            return f"0.00s - 60.00s [ANALYSIS WINDOW: First 60.0s analyzed of {duration_sec:.2f}s total]"
        else:
            return f"{float(active_start):.2f}s - {float(active_end):.2f}s (Duration: {duration_sec:.2f}s) [MEASURED DSP]"

    if duration_sec > 0.0:
        if duration_sec > 60.0:
            return f"0.00s - 60.00s [ANALYSIS WINDOW: First 60.0s analyzed of {duration_sec:.2f}s total]"
        return f"0.00s - {duration_sec:.2f}s [MEASURED DSP]"

    return "unavailable (unmeasured)"


def _resolve_tonal_attributes(
    sonic_genome: Optional[Any],
    row_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extracts verified tonal properties and guards against default hallucinations.
    """
    tonal_facts = None
    if sonic_genome and hasattr(sonic_genome, "measured_facts") and sonic_genome.measured_facts:
        tonal_facts = sonic_genome.measured_facts.tonal

    is_tonal = tonal_facts.is_tonal if tonal_facts else None
    pitch = tonal_facts.detected_pitch_hz if tonal_facts else None
    tuning = tonal_facts.tuning_hz if tonal_facts else None
    detected_bpm = tonal_facts.detected_bpm if tonal_facts else None

    if is_tonal is True and pitch:
        is_tonal_str = f"True (Pitch: {pitch:.1f} Hz) [MEASURED DSP, autocorrelation peak > 0.55]"
    elif is_tonal is False:
        is_tonal_str = "False [MEASURED DSP]"
    else:
        is_tonal_str = "unavailable (unmeasured)"

    cat_bpm = float(row_dict.get("tempo_bpm") or 0.0)
    if detected_bpm and detected_bpm > 0:
        bpm_str = f"{detected_bpm:.1f} BPM [ESTIMATED DSP]"
    elif cat_bpm > 0:
        bpm_str = f"{cat_bpm:.1f} BPM [SOURCE METADATA]"
    else:
        bpm_str = "unavailable (unmeasured)"

    key = row_dict.get("key_tonality")
    if key and key.lower() not in ("unspecified", "none", ""):
        key_str = f"{key} [SOURCE METADATA]"
    else:
        key_str = "unavailable (unmeasured)"

    time_sig = row_dict.get("time_signature")
    if time_sig and time_sig not in ("4/4", ""):
        time_sig_str = f"{time_sig} [SOURCE METADATA]"
    else:
        time_sig_str = "unavailable (unmeasured)"

    return {
        "is_tonal": is_tonal,
        "is_tonal_str": is_tonal_str,
        "detected_pitch_hz": pitch,
        "tuning_hz": tuning,
        "bpm_str": bpm_str,
        "key_tonality_str": key_str,
        "time_signature_str": time_sig_str,
    }


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

        # Epistemic Context & Source Metadata
        cls_tags = cand.evidence.classifier_matches
        mood_val, mood_ev, src_mood, cls_mood = _resolve_mood_and_evidence(
            cand.mood or meta.get("mood"), cls_tags
        )
        role_val, role_ev = _resolve_dramatic_role(meta.get("dramatic_role"))

        # Measured Mix Signals (Scripts expose measurable facts; agents make decisions)
        sp_density = meta.get("speech_corridor_density")
        v_prob = _extract_vocal_presence(cls_tags)

        # Temporal active region
        temp_events = cand.evidence.temporal_event_matches
        active_region_str = _resolve_active_region(cand.duration_sec, temporal_events=temp_events)

        # Tonal attributes
        tonal_data = _resolve_tonal_attributes(None, meta)

        # Completeness & Analysis status
        completeness_pct = int(cand.evidence.metadata_completeness * 100)
        has_dsp = meta.get("integrated_lufs") is not None
        has_class = bool(cls_tags)
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

        # Build card (unassigned catalog state: zero hardcoded creative/mix conclusions)
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
            speech_corridor_density=sp_density,
            tags=cand.tags.split() if cand.tags else [],
            top_classifier_labels=cls_tags,
            vocal_speech_probability=v_prob,
            clap_similarity=cand.evidence.clap_similarity,
            source_mood=src_mood,
            classifier_mood=cls_mood,
            mood=mood_val,
            mood_evidence=mood_ev,
            dramatic_role=role_val,
            dramatic_role_evidence=role_ev,
            voice_masking_risk="UNASSESSED",
            voice_masking_evidence="[UNASSESSED: Requires Mix Agent evaluation based on measured speech corridor density]",
            whisper_compatibility=None,
            whisper_compatibility_evidence="[NOT_CALIBRATED]",
            recommended_ducking_db=None,
            recommended_ducking_evidence="[SCENE_DEPENDENT / DEFERRED_TO_MIX_AGENT]",
            active_region_str=active_region_str,
            temporal_events=temp_events,
            is_tonal=tonal_data["is_tonal"],
            is_tonal_str=tonal_data["is_tonal_str"],
            detected_pitch_hz=tonal_data["detected_pitch_hz"],
            tuning_hz=tonal_data["tuning_hz"],
            bpm_str=tonal_data["bpm_str"],
            key_tonality_str=tonal_data["key_tonality_str"],
            time_signature_str=tonal_data["time_signature_str"],
            agent_interpretation=None,
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
    def from_database_row(
        cls,
        row_dict: Dict[str, Any],
        classifier_tags: Optional[List[Dict[str, Any]]] = None,
        temporal_events: Optional[List[Dict[str, Any]]] = None,
        sonic_genome: Optional[Any] = None,
    ) -> AgentSoundCard:
        """Constructs an AgentSoundCard directly from database catalog row."""
        centroid = row_dict.get("spectral_centroid_hz")
        if centroid is not None:
            c_val = float(centroid)
            brightness = "bright" if c_val >= 2500 else ("warm" if c_val <= 1200 else "neutral")
        else:
            brightness = row_dict.get("wave_style") or "neutral"

        # Epistemic Context & Source Metadata
        cls_tags = classifier_tags or []
        mood_val, mood_ev, src_mood, cls_mood = _resolve_mood_and_evidence(
            row_dict.get("mood"), cls_tags
        )
        role_val, role_ev = _resolve_dramatic_role(row_dict.get("dramatic_role"))

        # Measured Mix Signals
        sp_density = None
        if sonic_genome and hasattr(sonic_genome, "acoustic") and sonic_genome.acoustic:
            sp_density = sonic_genome.acoustic.speech_corridor_density
        if sp_density is None:
            sp_density = row_dict.get("speech_corridor_density")

        v_prob = _extract_vocal_presence(cls_tags)

        # Temporal active region
        dur_sec = float(row_dict.get("duration_sec") or 0.0)
        active_region_str = _resolve_active_region(dur_sec, temporal_events=temporal_events, sonic_genome=sonic_genome)

        # Tonal attributes
        tonal_data = _resolve_tonal_attributes(sonic_genome, row_dict)

        tags_str = row_dict.get("tags") or ""

        # Build card (unassigned catalog state: zero hardcoded creative/mix conclusions)
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
            duration_sec=dur_sec,
            integrated_lufs=row_dict.get("integrated_lufs"),
            true_peak_dbtp=row_dict.get("true_peak_db"),
            spectral_centroid_hz=row_dict.get("spectral_centroid_hz"),
            spectral_brightness=brightness,
            transient_character=row_dict.get("temporal_character") or "transient",
            energy_profile=row_dict.get("energy_profile") or "medium",
            speech_corridor_density=sp_density,
            tags=tags_str.split() if tags_str else [],
            top_classifier_labels=cls_tags,
            vocal_speech_probability=v_prob,
            clap_similarity=None,
            source_mood=src_mood,
            classifier_mood=cls_mood,
            mood=mood_val,
            mood_evidence=mood_ev,
            dramatic_role=role_val,
            dramatic_role_evidence=role_ev,
            voice_masking_risk="UNASSESSED",
            voice_masking_evidence="[UNASSESSED: Requires Mix Agent evaluation based on measured speech corridor density]",
            whisper_compatibility=None,
            whisper_compatibility_evidence="[NOT_CALIBRATED]",
            recommended_ducking_db=None,
            recommended_ducking_evidence="[SCENE_DEPENDENT / DEFERRED_TO_MIX_AGENT]",
            active_region_str=active_region_str,
            temporal_events=temporal_events or [],
            is_tonal=tonal_data["is_tonal"],
            is_tonal_str=tonal_data["is_tonal_str"],
            detected_pitch_hz=tonal_data["detected_pitch_hz"],
            tuning_hz=tonal_data["tuning_hz"],
            bpm_str=tonal_data["bpm_str"],
            key_tonality_str=tonal_data["key_tonality_str"],
            time_signature_str=tonal_data["time_signature_str"],
            agent_interpretation=None,
            metadata_completeness_pct=int(_compute_metadata_completeness(row_dict) * 100),
            analysis_status="database_record",
            provenance_summary={"dsp": row_dict.get("analysis_version") or "v1.0"},
            is_local_cached=bool(row_dict.get("is_downloaded")),
            is_virtual_jit_ready=not bool(row_dict.get("is_downloaded")),
            file_path=row_dict.get("filepath"),
            retrieval_score=None,
            why_matched=["Direct asset lookup"],
        )
