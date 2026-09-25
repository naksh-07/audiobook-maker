#!/usr/bin/env python3
"""
Audiobook Factory - Dramaturgy Data Contracts & Strictly Typed Schemas (Pydantic v2).
Defines contracts for Scene-Level Dramatic Understanding, Beat-Level Character Objectives,
Actioning, Subtext, Emotional Trajectories, Tension Curves, Performance Bibles,
and Dramatic Validation Results.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


# -----------------------------------------------------------------------------
# Fundamental Dramaturgy Types
# -----------------------------------------------------------------------------

DramaticFunction = Literal[
    "setup",
    "approach",
    "question",
    "resistance",
    "escalation",
    "reaction",
    "reveal",
    "realization",
    "reversal",
    "threat",
    "decision",
    "emotional_turn",
    "climax",
    "aftermath",
    "transition",
]

SceneType = Literal[
    "dialogue",
    "investigation",
    "romance",
    "confrontation",
    "combat",
    "horror",
    "comedy",
    "travel",
    "revelation",
    "exposition",
    "introspection",
    "flashback",
    "transition",
]

DramaticComplexity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

SubtextClassification = Literal[
    "SOURCE_SUPPORTED",
    "CONTEXTUAL_INFERENCE",
    "CREATIVE_INTERPRETATION",
    "UNSUPPORTED",
]

PerformancePriority = Literal["background", "standard", "high_focus", "climactic"]

CausalLinkType = Literal["therefore", "but", "meanwhile", "catalyst"]
RelationshipDimension = Literal["trust", "hostility", "cooperation", "intimacy", "fear", "dominance", "respect", "estrangement"]
RelationshipDirection = Literal["increased", "decreased", "inverted", "severed", "cemented"]

NarrativeMode = Literal[
    "direct_dialogue",
    "narrator_exposition",
    "internal_monologue",
    "reported_speech",
    "quoted_speech",
    "stream_of_consciousness",
    "choral_or_aside",
]

NarrativeDistance = Literal["objective_detached", "close_third_person", "first_person_intimate", "omniscient_editorial"]


# -----------------------------------------------------------------------------
# Enriched Dramatic Models
# -----------------------------------------------------------------------------

class RelationshipShift(BaseModel):
    """
    Relational movement between two characters triggered by a dramatic beat.
    """
    model_config = ConfigDict(extra="ignore")

    source_character: str = Field(..., description="Character whose relational stance has transformed")
    target_character: str = Field(..., description="Target character of the relational stance")
    dimension: RelationshipDimension = Field(default="trust", description="Relational axis being shifted")
    direction: RelationshipDirection = Field(default="increased", description="Directional movement")
    description: str = Field(default="", description="Narrative rationale for the shift")


class PhysicalBlocking(BaseModel):
    """
    Dramatically meaningful physical action materially altering leverage, proximity, or posture.
    Filters out trivial fidgets; focuses on physical moments with dramatic weight.
    """
    model_config = ConfigDict(extra="ignore")

    character: str = Field(..., description="Character executing physical action")
    action_description: str = Field(..., description="Material physical action affecting dramatic situation")
    dramatic_significance: Literal[
        "power_assertion",
        "barrier_creation",
        "intimacy_seeking",
        "concealment",
        "territorial_control",
        "threat_display",
        "submission",
        "revelation_trigger",
    ] = Field(default="power_assertion")
    spatial_intent: Optional[str] = Field(default=None, description="Resulting spatial or acoustic staging change")


class StoryConnectionRecord(BaseModel):
    """
    Long-range narrative connection referencing setup, foreshadowing, callbacks, or motifs.
    Reuses existing narrative context without building a separate redundant database.
    """
    model_config = ConfigDict(extra="ignore")

    connection_type: Literal["setup", "foreshadowing", "callback", "motif_echo", "payoff", "thematic_anchor"] = Field(default="setup")
    reference_target: str = Field(..., description="Target chapter, scene, or narrative element ID")
    description: str = Field(..., description="Dramatic nature of the connection")
    motif_name: Optional[str] = Field(default=None, description="Optional motif tag")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class ConversationalDynamic(BaseModel):
    """
    Rhetorical turn-taking dynamic capturing interruptions, hesitation, avoidance, and tactical shifts.
    """
    model_config = ConfigDict(extra="ignore")

    dynamic_type: Literal[
        "interruption",
        "hesitation",
        "escalation",
        "deflection_avoidance",
        "miscommunication",
        "cross_talk",
        "tactical_silence",
        "strategy_shift",
        "steady_exchange",
    ] = Field(default="steady_exchange")
    initiator: str = Field(..., description="Character driving the dynamic")
    target: Optional[str] = Field(default=None, description="Recipient of the dynamic")
    description: str = Field(default="", description="Conversational tactic in play")
    strategy_before: Optional[str] = Field(default=None, description="Strategy prior to shift")
    strategy_after: Optional[str] = Field(default=None, description="Strategy following shift")


class DramaticSilenceIntent(BaseModel):
    """
    Dramatic layer identification of the narrative purpose of silence or pause.
    NOTE: Stage 3 models narrative intent only; Stage 10 executes DSP audio timing.
    """
    model_config = ConfigDict(extra="ignore")

    purpose: Literal[
        "anticipation",
        "shock",
        "realization",
        "grief",
        "emotional_absorption",
        "intimidation",
        "hesitation",
        "suspense",
    ] = Field(..., description="Narrative purpose of silence")
    affected_character: Optional[str] = Field(default=None, description="Character experiencing silence")
    dramatic_rationale: str = Field(..., description="Why dramatic silence is narratively required")
    listening_focus: Literal["character_reaction", "acoustic_space", "subtext_digestion"] = Field(
        default="character_reaction",
        description="Where listener attention should focus during silence",
    )


class DramaticStateDelta(BaseModel):
    """
    Net dramatic transformation between scene entry and scene exit.
    Quantifies meaningful changes in knowledge, relationships, objectives, power, danger, and emotion.
    """
    model_config = ConfigDict(extra="ignore")

    knowledge_delta: List[str] = Field(default_factory=list, description="New facts learned, disclosed, or disproven")
    relationship_shifts: List[str] = Field(default_factory=list, description="Interpersonal movements across scene")
    power_shift: Optional[str] = Field(default=None, description="Net directional shift in leverage/authority across scene")
    danger_level_delta: Optional[Literal["escalated", "reduced", "latent", "unchanged"]] = Field(default="unchanged")
    decisions_made: List[str] = Field(default_factory=list, description="Irreversible or binding choices made by characters")
    emotional_trajectory: Optional[str] = Field(default=None, description="Entry-to-exit emotional movement")


class AdaptationFidelityPolicy(BaseModel):
    """
    Rules of engagement defining what dramatic adaptation may enhance vs what must remain immutable.
    Guarantees zero silent fabrication of plot events, character motivations, or false lore.
    """
    model_config = ConfigDict(extra="ignore")

    preserve_plot_events: bool = Field(default=True, description="No added, deleted, or reordered plot events")
    preserve_character_identities: bool = Field(default=True, description="No hallucinated characters or merged identities")
    preserve_epistemic_facts: bool = Field(default=True, description="Strict adherence to character knowledge boundaries")
    preserve_core_dialogue_intent: bool = Field(default=True, description="Spoken dialogue retains exact semantic intent")
    preserve_narrative_pov: bool = Field(default=True, description="No unauthorized switches between 1st/3rd person")
    allow_subtext_inference: bool = Field(default=True, description="Inference permitted with confidence score")
    allow_conversational_turn_dynamics: bool = Field(default=True, description="Tagging hesitations/interruptions allowed")
    disallow_fabricated_reveals: bool = Field(default=True, description="Forbids reveals not substantiated by source")
    disallow_invented_conflicts: bool = Field(default=True, description="Forbids manufacturing ungrounded disputes")


# -----------------------------------------------------------------------------
# Beat-Level Contracts
# -----------------------------------------------------------------------------

class CharacterDramaticObjective(BaseModel):
    """
    Immediate tactical objective of a character during a dramatic beat.
    Answers: 'What does this character want right now, and what prevents them?'
    """
    model_config = ConfigDict(extra="ignore")

    immediate_goal: str = Field(..., description="Tactical objective within this beat")
    obstacle: str = Field(default="", description="Immediate counter-force or resistance")
    underlying_desire: str = Field(default="", description="Deep psychological motivation")
    core_fear: str = Field(default="", description="What the character is trying to avoid or hide")
    strategy: str = Field(default="", description="Behavioral approach chosen to achieve goal")
    actioning: str = Field(default="", description="Transitive acting verb (e.g. 'threaten', 'deflect', 'reassure')")


class DramaticBeat(BaseModel):
    """
    Atomic dramatic unit representing a meaningful change in state, leverage, or emotion.
    Forms a continuous causal chain with preceding and succeeding beats.
    """
    model_config = ConfigDict(extra="ignore")

    beat_id: str = Field(..., description="Unique beat identifier, e.g. 'beat_001'")
    scene_id: str = Field(..., description="Enclosing scene identifier, e.g. 'scene_001'")
    index: int = Field(..., ge=1, description="1-indexed sequence number within scene")
    dramatic_function: str = Field(default="setup", description="Dramatic function of this beat")
    summary: str = Field(default="", description="Concise synopsis of beat action")
    active_characters: List[str] = Field(default_factory=list, description="Canonical names of present characters")
    primary_speaker: Optional[str] = Field(default=None, description="Initiating or dominant speaker")
    target_character: Optional[str] = Field(default=None, description="Target of action or dialogue")
    objective: Optional[CharacterDramaticObjective] = Field(default=None, description="Objective of primary speaker")
    surface_emotion: str = Field(default="neutral", description="Outwardly exhibited emotional delivery")
    underlying_emotion: Optional[str] = Field(default=None, description="Concealed internal emotional state")
    subtext: Optional[str] = Field(default=None, description="Unspoken meaning behind dialogue if justified")
    subtext_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in subtext inference")
    subtext_classification: SubtextClassification = Field(default="SOURCE_SUPPORTED")
    tension_before: float = Field(default=0.5, ge=0.0, le=1.0, description="Tension index entering beat (0.0 to 1.0)")
    tension_after: float = Field(default=0.5, ge=0.0, le=1.0, description="Tension index exiting beat (0.0 to 1.0)")
    intensity: str = Field(default="medium", description="Acoustic dynamic headroom: low, medium, high, explosive")
    power_shift: Optional[str] = Field(default=None, description="Shift in leverage or relational authority")
    information_revealed: List[str] = Field(default_factory=list, description="Facts disclosed in this beat")
    information_withheld: List[str] = Field(default_factory=list, description="Secrets deliberately concealed")
    performance_priority: PerformancePriority = Field(default="standard", description="Performance focus weighting")

    # Capability 1: Beat Causality
    causal_trigger: Optional[str] = Field(default=None, description="What event or action triggered this beat ('Because of...')")
    character_response: Optional[str] = Field(default=None, description="How the reacting character responds to the trigger")
    consequence: Optional[str] = Field(default=None, description="Direct dramatic consequence leading into the next beat ('Therefore...')")
    causal_link_type: CausalLinkType = Field(default="therefore", description="Connective relationship from preceding beat")

    # Capability 3: Relationship Evolution
    relationship_shift: Optional[RelationshipShift] = Field(default=None, description="Relational movement occurring during this beat")

    # Capability 4: Power + Information Dynamics
    leverage_holder: Optional[str] = Field(default=None, description="Character holding tactical leverage in this beat")
    vulnerable_character: Optional[str] = Field(default=None, description="Character in exposed or vulnerable position")
    dramatic_irony: Optional[str] = Field(default=None, description="Specific irony where listener knows truth hidden from character")

    # Capability 5: Meaningful Physical Blocking
    blocking: Optional[PhysicalBlocking] = Field(default=None, description="Meaningful physical blocking action")

    # Capability 7: Provenance Mode (Fidelity)
    provenance_mode: Literal["SOURCE_DIRECT", "INFERRED_PERFORMANCE", "DRAMATIC_INTERPRETATION"] = Field(default="SOURCE_DIRECT")

    # Capability 8: Long-Range Story Connections
    story_connection: Optional[StoryConnectionRecord] = Field(default=None, description="Beat echoing or paying off long-range setup")

    # Capability 9: Conversational Dynamics
    conversational_dynamic: Optional[ConversationalDynamic] = Field(default=None, description="Turn-taking or rhetorical dynamic")

    # Capability 10: Dramatic Silence Intent
    silence_intent: Optional[DramaticSilenceIntent] = Field(default=None, description="Narrative purpose of pause or silence")


# -----------------------------------------------------------------------------
# Scene-Level Contracts
# -----------------------------------------------------------------------------

class SceneDramaticPlan(BaseModel):
    """
    Comprehensive dramatic architecture of an individual scene.
    Answers: What is happening, why it matters, stakes, and knowledge state.
    """
    model_config = ConfigDict(extra="ignore")

    scene_id: str = Field(..., description="Scene identifier, e.g. 'scene_001'")
    chapter_num: int = Field(default=1, ge=1, description="1-indexed chapter number")
    scene_title: str = Field(default="", description="Descriptive title of the scene")
    scene_type: str = Field(default="dialogue", description="Genre or structural type of scene")
    location: str = Field(default="Unspecified", description="Physical or acoustic environment")
    time_context: str = Field(default="Unspecified", description="Time of day or temporal context")
    dramatic_purpose: str = Field(default="", description="Why this scene exists in the narrative")
    scene_question: str = Field(default="", description="Core dramatic question driving scene tension")
    stakes: str = Field(default="", description="What is won, lost, or risked")
    opening_state: str = Field(default="", description="Emotional and dramatic state entering scene")
    closing_state: str = Field(default="", description="Emotional and dramatic state exiting scene")
    primary_conflict: str = Field(default="", description="Central conflict (character vs character, self, environment)")
    secondary_conflicts: List[str] = Field(default_factory=list, description="Subordinate dramatic tensions")
    participants: List[str] = Field(default_factory=list, description="Canonical character names active in scene")
    dramatic_complexity: str = Field(default="MEDIUM", description="Reasoning complexity rating (LOW/MEDIUM/HIGH/CRITICAL)")
    listener_knowledge_state: str = Field(default="", description="Epistemic context of the audience (e.g. dramatic irony)")
    character_knowledge_states: Dict[str, List[str]] = Field(default_factory=dict, description="Facts known by each character")
    major_reveals: List[str] = Field(default_factory=list, description="Major narrative disclosures in this scene")
    reversals: List[str] = Field(default_factory=list, description="Dramatic or fortune reversals")
    tension_curve: List[float] = Field(default_factory=list, description="Sampled tension trajectory across beats")
    beats: List[DramaticBeat] = Field(default_factory=list, description="Sequential dramatic beats")
    source_hash: str = Field(default="", description="SHA-256 hash of underlying source text")

    # Capability 2: Dramatic State Delta
    state_delta: Optional[DramaticStateDelta] = Field(default_factory=DramaticStateDelta, description="Net transformation between scene entry and exit")

    # Capability 4: Power + Information Dynamics
    epistemic_asymmetry: List[str] = Field(default_factory=list, description="Contrasts between listener knowledge and character ignorance")

    # Capability 6: Narrative Mode & Perspective
    narrative_pov: str = Field(default="third_person_limited", description="Dominant narrative point of view")
    narrative_distance: NarrativeDistance = Field(default="close_third_person", description="Psychological distance of narration")
    pov_character: Optional[str] = Field(default=None, description="Focalizing character for scene perspective")

    # Capability 8: Long-Range Story Connections
    story_connections: List[StoryConnectionRecord] = Field(default_factory=list, description="Long-range narrative connections linked to this scene")


class DramaticPlan(BaseModel):
    """
    Complete Chapter Dramatic Plan (Durable Artifact: dramatic_plan.json).
    Encodes the holistic dramaturgical blueprint across all scenes in a chapter.
    """
    model_config = ConfigDict(extra="ignore")

    chapter_id: str = Field(..., description="Chapter identifier, e.g. 'chapter_001'")
    chapter_num: int = Field(default=1, ge=1, description="1-indexed chapter number")
    scenes: List[SceneDramaticPlan] = Field(default_factory=list, description="Constituent scene plans")
    overall_arc_summary: str = Field(default="", description="High-level narrative progression summary")
    total_beats: int = Field(default=0, ge=0, description="Total planned dramatic beats in chapter")
    version: str = Field(default="1.1", description="Dramaturgy schema version")
    source_hash: str = Field(default="", description="SHA-256 hash of full chapter source text")

    # Capability 7: Explicit Adaptation & Fidelity Policy
    adaptation_policy: AdaptationFidelityPolicy = Field(default_factory=AdaptationFidelityPolicy, description="Fidelity constraints governing adaptation")

    def get_scene(self, scene_id: str) -> Optional[SceneDramaticPlan]:
        """Lookup scene by identifier."""
        for s in self.scenes:
            if s.scene_id == scene_id:
                return s
        return None

    def get_beat(self, beat_id: str) -> Optional[DramaticBeat]:
        """Lookup beat by identifier across all scenes."""
        for s in self.scenes:
            for b in s.beats:
                if b.beat_id == beat_id:
                    return b
        return None

    def save_to_file(self, path: Path | str) -> None:
        """Persist dramatic plan as JSON atomically."""
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(f".tmp_{p.stat().st_mtime if p.exists() else 'new'}")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(self.model_dump_json(indent=2))
            tmp.replace(p)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    @classmethod
    def load_from_file(cls, path: Path | str) -> DramaticPlan:
        """Load dramatic plan from disk."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)


# -----------------------------------------------------------------------------
# Performance Bible Contracts
# -----------------------------------------------------------------------------

class CharacterPerformanceProfile(BaseModel):
    """
    Performance-oriented character projection (How this character behaves when performed).
    Completely decoupled from canonical lore/memory storage; focuses on delivery mechanics.
    """
    model_config = ConfigDict(extra="ignore")

    character_name: str = Field(..., description="Canonical character display name")
    baseline_pace: float = Field(default=1.0, ge=0.5, le=2.0, description="Pacing multiplier relative to neutral")
    baseline_energy: float = Field(default=0.8, ge=0.0, le=1.0, description="Vocal energy/projection level")
    articulation: str = Field(default="natural", description="Speech clarity: crisp, colloquial, sluggish, slurred, sharp")
    emotional_behaviors: Dict[str, str] = Field(
        default_factory=dict,
        description="Delivery style mappings for specific emotions (e.g. {'anger': 'cold_quiet_menace'})"
    )
    restraint_level: float = Field(default=0.5, ge=0.0, le=1.0, description="Emotional suppression vs expression (0=raw, 1=iron restraint)")
    speech_quirks: List[str] = Field(default_factory=list, description="Organic performance quirks (e.g. 'cynical grunt', 'ragged pause')")
    performance_rules: List[str] = Field(default_factory=list, description="Guiding rules for line delivery")


class PerformanceBible(BaseModel):
    """
    Project-level Performance Bible (Durable Artifact: performance_bible.json).
    Directs how every character sounds and behaves across all emotional beats.
    """
    model_config = ConfigDict(extra="ignore")

    characters: Dict[str, CharacterPerformanceProfile] = Field(default_factory=dict)
    narrator_style: Dict[str, Any] = Field(
        default_factory=lambda: {
            "baseline_pace": 1.0,
            "tone": "objective_cinematic_observer",
            "pause_multiplier": 1.0,
        }
    )
    version: str = Field(default="1.0")

    def get_profile(self, name: str) -> Optional[CharacterPerformanceProfile]:
        """Lookup character performance profile case-insensitively."""
        clean = name.strip().lower()
        for k, v in self.characters.items():
            if k.strip().lower() == clean:
                return v
        return None

    def save_to_file(self, path: Path | str) -> None:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp_pb")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(self.model_dump_json(indent=2))
            tmp.replace(p)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    @classmethod
    def load_from_file(cls, path: Path | str) -> PerformanceBible:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)


# -----------------------------------------------------------------------------
# Dramatic Validation Contracts
# -----------------------------------------------------------------------------

class DramaticValidationIssue(BaseModel):
    """Specific dramatic or structural flaw detected by DramaticValidator."""
    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Machine-readable issue code, e.g. 'EMOTIONAL_TELEPORTATION'")
    severity: Literal["INFO", "WARNING", "ERROR"] = Field(default="WARNING")
    message: str = Field(..., description="Human-readable explanation of the issue")
    scene_id: Optional[str] = Field(default=None)
    beat_id: Optional[str] = Field(default=None)
    segment_uid: Optional[str] = Field(default=None)


class DramaticValidationResult(BaseModel):
    """
    Comprehensive result of dramatic plan & screenplay validation (dramatic_validation.json).
    """
    model_config = ConfigDict(extra="ignore")

    status: Literal["PASS", "WARNING", "FAIL"] = Field(default="PASS")
    passed: bool = Field(default=True)
    total_issues: int = Field(default=0)
    issues: List[DramaticValidationIssue] = Field(default_factory=list)
    summary: str = Field(default="")
    checked_at: str = Field(default="")

    def save_to_file(self, path: Path | str) -> None:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp_val")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(self.model_dump_json(indent=2))
            tmp.replace(p)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass

    @classmethod
    def load_from_file(cls, path: Path | str) -> DramaticValidationResult:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)
