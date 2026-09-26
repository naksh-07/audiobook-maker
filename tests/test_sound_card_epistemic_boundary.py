#!/usr/bin/env python3
"""
Test Suite: Sound Card Epistemic Boundary & Truthful Presentation.
==================================================================
Verifies the strict separation between:
1. Deterministic audio analysis & measured DSP facts.
2. AI classifier & semantic model predictions.
3. Original source pack metadata.
4. Autonomous agent creative / mix interpretation.

Enforces zero script-level creative invention:
- Zero fake defaults ('general', '0.50', '-6 dB', manufactured 'LOW' risk).
- Honest conflict surfacing between source tags and model predictions.
- Proper temporal semantic typing (observation windows vs true events).
- First-class AgentInterpretation container with creative_confidence defaulting to None.
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone

from audiobook_factory.agent_sound_card import (
    AgentSoundCard,
    AgentInterpretation,
    SoundCardBuilder,
    _resolve_mood_and_evidence,
    _resolve_dramatic_role,
    _extract_vocal_presence,
)
from audiobook_factory.audio_classifier_adapters import (
    AudioEventRecord,
    ClassifierPrediction,
)
from audiobook_factory.sonic_candidate_generators import CandidateRecord, CandidateEvidence
from audiobook_factory.sonic_hybrid_reranker import ScoredCandidate
from audiobook_factory.sound_design.asset_retriever import SoundAssetRetriever


def test_01_zero_fake_defaults_in_unassigned_sound_card():
    """Rule A & B: Unassigned sound card must NOT contain fake defaults (general, 0.50, -6 dB, LOW)."""
    card = SoundCardBuilder.from_database_row({
        "id": 999,
        "filename": "test_unassigned.wav",
        "title": "Unassigned Test Sound",
        "category": "SFX",
        "subcategory": "Impact",
        "duration_sec": 3.5,
        "integrated_lufs": -20.0,
        "true_peak_db": -1.0,
        "spectral_centroid_hz": 1500.0,
    })

    # Dramatic role must be UNASSIGNED, not 'general'
    assert card.dramatic_role == "UNASSIGNED"
    assert card.dramatic_role_evidence == "[AWAITING_AGENT_EVALUATION]"

    # Mood must be UNINTERPRETED
    assert card.mood == "UNINTERPRETED"
    assert card.mood_evidence == "[AWAITING_AGENT_EVALUATION]"

    # Voice masking risk must be UNASSESSED, not 'LOW'
    assert card.voice_masking_risk == "UNASSESSED"
    assert "[UNASSESSED" in card.voice_masking_evidence

    # Whisper compatibility must be None and NOT_CALIBRATED, not 0.50
    assert card.whisper_compatibility is None
    assert card.whisper_compatibility_evidence == "[NOT_CALIBRATED]"

    # Recommended dialogue ducking must be None, not -6 dB
    assert card.recommended_ducking_db is None
    assert "DEFERRED_TO_MIX_AGENT" in card.recommended_ducking_evidence


def test_02_source_taxonomy_labeled_as_source_metadata_not_inferred():
    """Rule C: Source/catalog metadata must be labeled [SOURCE METADATA], never [INFERRED]."""
    card = SoundCardBuilder.from_database_row({
        "id": 100,
        "filename": "wood_door_creak.wav",
        "title": "Door Creak",
        "category": "FOL",
        "subcategory": "Door",
        "action_type": "creak",
        "exciter": "wood",
        "resonator": "door_frame",
        "surface": "wood",
        "acoustic_space": "room",
        "duration_sec": 2.0,
        "integrated_lufs": -22.0,
    })

    md = card.to_agent_markdown()
    assert "- **Taxonomy [SOURCE METADATA]**:" in md
    assert "[SOURCE / INFERRED]" not in md
    assert "[INFERRED]" not in md


def test_03_transparent_mood_conflict_surfacing():
    """Rule A & F: Conflicts between catalog metadata and classifier predictions must be explicitly surfaced."""
    # Example: Asset #498 scenario (catalog: 'peaceful', classifier: 'scary' conf: 0.134)
    cls_tags = [
        {"raw_label": "music.instrumental", "normalized_label": "music.instrumental", "raw_score": 0.70, "rank": 1},
        {"raw_label": "music.mood.scary", "normalized_label": "music.mood.scary", "raw_score": 0.134, "rank": 2},
    ]
    card = SoundCardBuilder.from_database_row(
        {"id": 498, "filename": "the_leshy_comes.mp3", "mood": "peaceful", "duration_sec": 37.0},
        classifier_tags=cls_tags,
    )

    # Must expose both facts and flag conflict for agent evaluation
    assert card.source_mood == "peaceful"
    assert card.classifier_mood == "scary"
    assert "Catalog: 'peaceful'" in card.mood
    assert "Classifier: 'scary'" in card.mood
    assert card.mood_evidence == "[CONFLICT / REQUIRES AGENT EVALUATION]"

    md = card.to_agent_markdown()
    assert "[CONFLICT / REQUIRES AGENT EVALUATION]" in md
    assert "Catalog: 'peaceful'" in md
    assert "Classifier: 'scary'" in md


def test_04_temporal_observation_window_semantics():
    """Rule D: AST 10-second sliding windows must be typed as classifier_observation_window."""
    events = [
        {
            "event_type": "classifier_observation_window",
            "start_sec": 0.0,
            "end_sec": 10.0,
            "confidence": 0.71,
            "metadata": {"raw_label": "music.instrumental", "normalized_label": "music.instrumental"},
        },
        {
            "event_type": "transient_onset",
            "start_sec": 1.25,
            "end_sec": 1.25,
            "confidence": None,
        }
    ]
    card = SoundCardBuilder.from_database_row(
        {"id": 50, "filename": "test_ambience.wav", "duration_sec": 15.0},
        temporal_events=events,
    )

    md = card.to_agent_markdown()
    # Must use [OBSERVATION WINDOW], not [CLASSIFIER SED]
    assert "[OBSERVATION WINDOW]" in md
    assert "[CLASSIFIER SED]" not in md
    assert "[MEASURED DSP]" in md  # for transient onset


def test_05_agent_creative_confidence_defaults_to_none():
    """Instruction 3: creative_confidence must default to None, NOT 1.0."""
    interp = AgentInterpretation(
        evaluator_agent="SoundDesignDirector",
        evaluated_at="2026-09-27T03:00:00Z",
        assigned_dramatic_role="suspense_builder",
    )
    assert interp.creative_confidence is None


def test_06_downstream_agent_interpretation_attachment():
    """Rule F & G: Downstream agents can attach creative decisions without altering raw evidence."""
    card = SoundCardBuilder.from_database_row({
        "id": 101,
        "filename": "creepy_drone.wav",
        "title": "Creepy Drone",
        "duration_sec": 10.0,
        "integrated_lufs": -18.0,
        "true_peak_db": -0.5,
        "spectral_centroid_hz": 250.0,
    })

    # Initially unassigned
    assert card.agent_interpretation is None
    assert card.dramatic_role == "UNASSIGNED"
    assert card.recommended_ducking_db is None

    # Downstream agent evaluates the asset for Scene 4
    interp = AgentInterpretation(
        evaluator_agent="SoundDesignDirector",
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        scene_context="scene_ch04_sc02",
        assigned_dramatic_role="threat_foreshadowing",
        assigned_mood="dread",
        voice_masking_assessment="MODERATE",
        contextual_ducking_db=-14.0,
        mix_notes="Heavy low-end presence requires -14dB ducking under Geralt's dialogue",
        creative_confidence=0.92,
    )
    card.attach_interpretation(interp)

    # Verification: Agent decisions are populated
    assert card.agent_interpretation is not None
    assert card.dramatic_role == "threat_foreshadowing"
    assert card.dramatic_role_evidence == "[AGENT INTERPRETATION: SoundDesignDirector]"
    assert card.mood == "dread"
    assert card.voice_masking_risk == "MODERATE"
    assert card.recommended_ducking_db == -14.0

    # Verification: Raw measured facts remain completely intact
    assert card.integrated_lufs == -18.0
    assert card.true_peak_dbtp == -0.5
    assert card.spectral_centroid_hz == 250.0

    # Verification: Markdown view renders the active agent interpretation
    md = card.to_agent_markdown()
    assert "- **Agent Creative Interpretation**:" in md
    assert "Evaluator: `SoundDesignDirector`" in md
    assert "Assigned Role: `threat_foreshadowing`" in md
    assert "Ducking=`-14.0 dB`" in md
    assert "Conf: `0.92`" in md


def test_07_asset_retriever_helper_method():
    """Verifies that SoundAssetRetriever.attach_agent_interpretation works ergonomically."""
    retriever = SoundAssetRetriever()
    card = SoundCardBuilder.from_database_row({
        "id": 202,
        "filename": "tavern_chatter.wav",
        "duration_sec": 30.0,
    })

    card = retriever.attach_agent_interpretation(
        card=card,
        evaluator_agent="WallaEngine",
        scene_context="scene_ch01_sc01",
        assigned_dramatic_role="ambient_grounding",
        assigned_mood="boisterous",
        voice_masking_assessment="SEVERE",
        contextual_ducking_db=-18.0,
        mix_notes="Walla background stem; aggressive ducking required",
    )

    assert card.agent_interpretation is not None
    assert card.agent_interpretation.evaluator_agent == "WallaEngine"
    assert card.dramatic_role == "ambient_grounding"
    assert card.recommended_ducking_db == -18.0
    assert card.voice_masking_risk == "SEVERE"


def test_08_measurable_mix_evidence_exposed_without_script_decisions():
    """Instruction 1: Scripts calculate & expose measurable evidence (speech probability, density) without conclusions."""
    cls_tags = [
        {"raw_label": "vocal.speech", "normalized_label": "vocal.speech", "raw_score": 0.45, "rank": 1},
    ]
    card = SoundCardBuilder.from_database_row(
        {
            "id": 303,
            "filename": "narrator_sample.wav",
            "duration_sec": 5.0,
            "speech_corridor_density": 0.65,
        },
        classifier_tags=cls_tags,
    )

    # Factual measured & classified evidence is exposed
    assert card.speech_corridor_density == 0.65
    assert card.vocal_speech_probability == 0.45

    # But script does NOT declare a hardcoded risk or ducking
    assert card.voice_masking_risk == "UNASSESSED"
    assert card.recommended_ducking_db is None


def test_09_all_seven_creative_dimensions_remain_unassigned_at_baseline():
    """Verifies that none of the 7 creative/directorial dimensions are prematurely inferred."""
    card = SoundCardBuilder.from_database_row({
        "id": 404,
        "filename": "ambient_forest.wav",
        "duration_sec": 12.0,
        "integrated_lufs": -24.0,
        "true_peak_db": -2.0,
        "spectral_centroid_hz": 1200.0,
        "speech_corridor_density": 0.15,
    })

    # All 7 creative dimensions must be unassigned / unassessed
    assert card.dramatic_role == "UNASSIGNED"
    assert card.scene_purpose == "UNASSIGNED"
    assert card.emotional_suitability == "UNINTERPRETED"
    assert card.voice_masking_judgment == "UNASSESSED"
    assert card.dialogue_ducking_amount_db is None
    assert card.placement_usage == "UNASSIGNED"
    assert card.final_taxonomy == "UNASSIGNED"

    # Evidence strings must explicitly flag awaiting specialist agent
    assert "Awaiting" in card.scene_purpose_evidence
    assert "Awaiting" in card.placement_usage_evidence
    assert "Awaiting" in card.final_taxonomy_evidence


def test_10_specialist_agents_evaluate_contextual_scene_decisions():
    """Verifies SoundDirector and MixDirector evaluate contextual decisions at scene time."""
    retriever = SoundAssetRetriever()
    card = SoundCardBuilder.from_database_row({
        "id": 505,
        "filename": "battle_drums.wav",
        "duration_sec": 8.0,
        "integrated_lufs": -14.0,
        "true_peak_db": -0.1,
        "spectral_centroid_hz": 800.0,
        "speech_corridor_density": 0.42,
    })

    # SoundDirector evaluates dramatic role, scene purpose, placement, and taxonomy
    card = retriever.evaluate_sound_director_decision(
        card=card,
        scene_id="scene_03_climax",
        dramatic_role="combat_urgency",
        scene_purpose="Geralt faces the striga in the crypt",
        placement_usage="under_action_stems",
        final_taxonomy="Percussive Combat SFX",
        emotional_suitability="adrenaline",
    )
    assert card.agent_interpretation is not None
    assert card.agent_interpretation.assigned_dramatic_role == "combat_urgency"
    assert card.agent_interpretation.scene_purpose == "Geralt faces the striga in the crypt"
    assert card.agent_interpretation.placement_usage == "under_action_stems"
    assert card.agent_interpretation.final_taxonomy == "Percussive Combat SFX"

    # MixDirector evaluates voice masking and ducking based on dialogue presence
    card = retriever.evaluate_mix_director_decision(
        card=card,
        scene_id="scene_03_climax",
        dialogue_present=True,
        dialogue_style="whisper",
    )
    assert card.agent_interpretation.voice_masking_judgment == "SEVERE"
    assert card.agent_interpretation.dialogue_ducking_amount_db == -18.0

    # Unified scene decision attachment
    card = retriever.evaluate_contextual_scene_decision(
        card=card,
        scene_id="scene_03_climax",
        dramatic_role="combat_urgency",
        scene_purpose="Geralt faces the striga in the crypt",
        emotional_suitability="adrenaline",
        placement_usage="under_action_stems",
        final_taxonomy="Percussive Combat SFX",
        dialogue_present=True,
        dialogue_style="normal",
        creative_confidence=0.95,
    )
    assert card.dramatic_role == "combat_urgency"
    assert card.scene_purpose == "Geralt faces the striga in the crypt"
    assert card.emotional_suitability == "adrenaline"
    assert card.placement_usage == "under_action_stems"
    assert card.final_taxonomy == "Percussive Combat SFX"
    assert card.dialogue_ducking_amount_db == -12.0
    assert card.agent_interpretation.creative_confidence == 0.95


def test_11_four_epistemic_categories_explicitly_labeled_in_sound_card_markdown():
    """Verifies that all 4 categories (MEASURED, CLASSIFIER, SOURCE_METADATA, AGENT_INTERPRETATION) are labeled."""
    card = SoundCardBuilder.from_database_row({
        "id": 606,
        "filename": "creak_01.wav",
        "title": "Floorboard Creak",
        "category": "SFX",
        "subcategory": "Foley",
        "duration_sec": 1.5,
        "integrated_lufs": -26.0,
        "true_peak_db": -3.0,
        "spectral_centroid_hz": 950.0,
    })

    md = card.to_agent_markdown()

    # 1. MEASURED
    assert "[MEASURED]" in md or "[MEASURED DSP]" in md
    assert "**Duration [MEASURED]**:" in md
    assert "- **Acoustics [MEASURED DSP]**:" in md

    # 2. CLASSIFIER
    assert "[CLASSIFIER]" in md
    assert "- **Classifier Inferences [CLASSIFIER]**:" in md

    # 3. SOURCE_METADATA
    assert "[SOURCE_METADATA]" in md or "[SOURCE METADATA]" in md
    assert "- **File / Status [SOURCE_METADATA]**:" in md
    assert "- **Taxonomy [SOURCE METADATA]**:" in md

    # 4. AGENT_INTERPRETATION
    assert "[AGENT_INTERPRETATION]" in md
    assert "- **Directorial Decisions & Mix Safety [AGENT_INTERPRETATION]**:" in md
    assert "Dramatic Role [AGENT_INTERPRETATION]:" in md
    assert "Scene Purpose [AGENT_INTERPRETATION]:" in md
    assert "Emotional Suitability [AGENT_INTERPRETATION]:" in md
    assert "Voice-Masking Judgment [AGENT_INTERPRETATION]:" in md
    assert "Dialogue Ducking Amount [AGENT_INTERPRETATION]:" in md
    assert "Placement / Recommended Usage [AGENT_INTERPRETATION]:" in md
    assert "Final Taxonomy [AGENT_INTERPRETATION]:" in md

