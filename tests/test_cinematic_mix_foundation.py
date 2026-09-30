#!/usr/bin/env python3
"""
Unit Tests for Stage 11 Cinematic Mix v2: Foundation + Scene Intent + Attention Architecture.
=============================================================================================
Tests:
1. SceneMixIntent:
   - Valid values and presets accepted.
   - Invalid normalized values rejected (< 0.0 or > 1.0).
   - Invalid focus rejected (unrecognized values).
   - Deterministic serialization and fingerprinting.
   - Compatibility adapters for existing Stage 10 scene data.

2. AttentionMap & AttentionEvent:
   - Valid events and aliases accepted.
   - Invalid timestamps rejected (start < 0, end <= start).
   - Invalid priority values rejected (< 0.0 or > 1.0).
   - Deterministic ordering of events regardless of insertion sequence.
   - Overlapping cues permitted and resolved via deterministic priority dominance.
   - Attention != Dialogue: listener attention focused on music, fx, or silence over dialogue.
   - Serialization and deserialization roundtrip.
   - Adaptation from Stage 10 SoundTimeline.

3. Integration & Output Semantics:
   - StemMetadata and StemLedger support CINEMATIC_MIX_PREMASTER with FULL_MASTER backward compatibility.
   - CinemaAudioManifest accepts SceneMixIntent and AttentionMap.
"""

import json
import pytest
from pydantic import ValidationError

from audiobook_factory.cinematic_mix import (
    SceneMixIntent,
    AttentionEvent,
    AttentionMap,
    ALLOWED_FOCUS_TARGETS,
    DYNAMIC_RANGE_PRESETS,
    SPATIAL_DEPTH_PRESETS,
    SILENCE_INTENT_PRESETS,
    IMPACT_INTENT_PRESETS,
)
from audiobook_factory.cinema_audio_engine import (
    StemMetadata,
    StemLedger,
    CinemaAudioManifest,
)


class TestSceneMixIntent:
    """Test suite for Stage 11 SceneMixIntent model."""

    def test_valid_default_construction(self):
        """Verify default SceneMixIntent initializes with valid acoustic bounds."""
        intent = SceneMixIntent()
        assert intent.focus == "dialogue"
        assert intent.emotional_intensity == 0.50
        assert intent.dialogue_priority == 0.80
        assert intent.music_priority == 0.50
        assert intent.fx_priority == 0.50
        assert intent.ambience_priority == 0.30
        assert intent.normalized_dynamic_range == 0.50
        assert intent.normalized_spatial_depth == 0.30
        assert intent.normalized_silence_intent == 0.00
        assert intent.normalized_impact_intent == 0.00

    def test_all_focus_targets_accepted(self):
        """Verify all constrained focus targets are accepted case-insensitively."""
        for target in ["dialogue", "music", "fx", "ambience", "silence", "environment"]:
            intent = SceneMixIntent(focus=target)
            assert intent.focus == target
            # Case-insensitivity check
            intent_upper = SceneMixIntent(focus=target.upper())
            assert intent_upper.focus == target

    def test_invalid_focus_rejected(self):
        """Verify arbitrary free text or invalid focus targets are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SceneMixIntent(focus="screaming_banshee")
        assert "Invalid focus" in str(exc_info.value)

        with pytest.raises(ValidationError):
            SceneMixIntent(focus="")

    def test_normalized_priority_bounds(self):
        """Verify priorities outside [0.0, 1.0] are rejected."""
        # dialogue_priority
        with pytest.raises(ValidationError):
            SceneMixIntent(dialogue_priority=-0.1)
        with pytest.raises(ValidationError):
            SceneMixIntent(dialogue_priority=1.05)

        # music_priority
        with pytest.raises(ValidationError):
            SceneMixIntent(music_priority=-0.01)
        with pytest.raises(ValidationError):
            SceneMixIntent(music_priority=1.5)

        # fx_priority
        with pytest.raises(ValidationError):
            SceneMixIntent(fx_priority=-1.0)
        with pytest.raises(ValidationError):
            SceneMixIntent(fx_priority=2.0)

        # ambience_priority
        with pytest.raises(ValidationError):
            SceneMixIntent(ambience_priority=-0.5)
        with pytest.raises(ValidationError):
            SceneMixIntent(ambience_priority=1.1)

    def test_emotional_intensity_bounds(self):
        """Verify emotional intensity outside [0.0, 1.0] is rejected."""
        with pytest.raises(ValidationError):
            SceneMixIntent(emotional_intensity=-0.1)
        with pytest.raises(ValidationError):
            SceneMixIntent(emotional_intensity=1.1)

        # Boundary values are valid
        i0 = SceneMixIntent(emotional_intensity=0.0)
        assert i0.emotional_intensity == 0.0
        i1 = SceneMixIntent(emotional_intensity=1.0)
        assert i1.emotional_intensity == 1.0

    def test_dynamic_range_intent_float_and_presets(self):
        """Verify dynamic_range_intent accepts bounded floats and valid presets."""
        i_float = SceneMixIntent(dynamic_range_intent=0.75)
        assert i_float.dynamic_range_intent == 0.75
        assert i_float.normalized_dynamic_range == 0.75

        i_preset = SceneMixIntent(dynamic_range_intent="cinematic_wide")
        assert i_preset.dynamic_range_intent == "cinematic_wide"
        assert i_preset.normalized_dynamic_range == 0.80

        # Invalid float rejected
        with pytest.raises(ValidationError):
            SceneMixIntent(dynamic_range_intent=1.5)
        with pytest.raises(ValidationError):
            SceneMixIntent(dynamic_range_intent=-0.2)

        # Invalid preset rejected
        with pytest.raises(ValidationError):
            SceneMixIntent(dynamic_range_intent="ultra_loud_wall")

    def test_spatial_depth_float_and_presets(self):
        """Verify spatial_depth accepts bounded floats and valid presets."""
        i_float = SceneMixIntent(spatial_depth=0.85)
        assert i_float.normalized_spatial_depth == 0.85

        i_preset = SceneMixIntent(spatial_depth="deep_cavernous")
        assert i_preset.normalized_spatial_depth == 0.85

        with pytest.raises(ValidationError):
            SceneMixIntent(spatial_depth=-0.1)
        with pytest.raises(ValidationError):
            SceneMixIntent(spatial_depth="outer_space_nowhere")

    def test_silence_and_impact_presets(self):
        """Verify silence_intent and impact_intent accept floats and presets."""
        i_silence = SceneMixIntent(silence_intent="profound_stillness")
        assert i_silence.normalized_silence_intent == 1.0

        i_impact = SceneMixIntent(impact_intent="heavy_strike")
        assert i_impact.normalized_impact_intent == 0.70

        with pytest.raises(ValidationError):
            SceneMixIntent(silence_intent=1.2)
        with pytest.raises(ValidationError):
            SceneMixIntent(impact_intent=-0.05)

    def test_deterministic_serialization(self):
        """Verify identical inputs serialize deterministically with identical fingerprints."""
        intent1 = SceneMixIntent(
            focus="music",
            emotional_intensity=0.85,
            dialogue_priority=0.70,
            music_priority=0.95,
            fx_priority=0.40,
            ambience_priority=0.20,
            dynamic_range_intent="cinematic_wide",
            spatial_depth="hall_medium",
            silence_intent="subtle_pause",
            impact_intent="light_accent",
            scene_id="scene_001",
        )
        intent2 = SceneMixIntent(
            focus="music",
            emotional_intensity=0.85,
            dialogue_priority=0.70,
            music_priority=0.95,
            fx_priority=0.40,
            ambience_priority=0.20,
            dynamic_range_intent="cinematic_wide",
            spatial_depth="hall_medium",
            silence_intent="subtle_pause",
            impact_intent="light_accent",
            scene_id="scene_001",
        )
        assert intent1.to_dict() == intent2.to_dict()
        assert intent1.to_json() == intent2.to_json()
        assert intent1.fingerprint() == intent2.fingerprint()

        # Roundtrip JSON deserialization
        reconstructed = SceneMixIntent.from_json(intent1.to_json())
        assert reconstructed.focus == intent1.focus
        assert reconstructed.emotional_intensity == intent1.emotional_intensity
        assert reconstructed.fingerprint() == intent1.fingerprint()

    def test_compatibility_with_stage10_scene_data(self):
        """Verify SceneMixIntent can be constructed from Stage 10 data structures."""
        # 1. Adapt from SceneAudioUnderstandingResult dictionary
        understanding_data = {
            "scene_id": "sc_forest_night",
            "chapter_id": "c001",
            "tension_level": 0.88,
            "dominant_emotion": "terror_pursuit",
            "music_required": True,
            "silence_opportunities": [],
        }
        intent_from_u = SceneMixIntent.from_scene_understanding(understanding_data)
        assert intent_from_u.scene_id == "sc_forest_night"
        assert intent_from_u.focus == "fx"
        assert intent_from_u.emotional_intensity == 0.88
        assert intent_from_u.impact_intent > 0.50

        # 2. Adapt from SceneAudioBlueprint dictionary
        blueprint_data = {
            "scene_id": "sc_crypt_tomb",
            "chapter_id": "c001",
            "restraint_target": "high",
            "silence_events_planned": [{"silence_id": "sil_01"}],
            "hard_sfx_planned": [],
            "music_cues_planned": [],
            "acoustic_profile_id": "hall_deep",
        }
        intent_from_bp = SceneMixIntent.from_scene_blueprint(blueprint_data)
        assert intent_from_bp.focus == "silence"
        assert intent_from_bp.normalized_silence_intent >= 0.70


class TestAttentionMapAndEvents:
    """Test suite for Stage 11 AttentionEvent and AttentionMap models."""

    def test_valid_attention_event(self):
        """Verify construction of valid AttentionEvent with computed properties."""
        event = AttentionEvent(
            start=1.5,
            end=4.5,
            focus_target="whisper",
            priority=0.95,
            reason="intimate disclosure of secret",
        )
        assert event.start == 1.5
        assert event.end == 4.5
        assert event.duration_sec == 3.0
        assert event.start_ms == 1500
        assert event.end_ms == 4500
        assert event.duration_ms == 3000
        assert event.priority == 0.95
        assert event.category == "dialogue"
        assert event.contains(2.0)
        assert not event.contains(5.0)

    def test_invalid_timestamps_rejected(self):
        """Verify negative start and end <= start are rejected."""
        # Negative start
        with pytest.raises(ValidationError):
            AttentionEvent(start=-0.5, end=2.0, focus_target="door", priority=0.8)

        # end == start (zero duration)
        with pytest.raises(ValidationError):
            AttentionEvent(start=2.0, end=2.0, focus_target="door", priority=0.8)

        # end < start
        with pytest.raises(ValidationError):
            AttentionEvent(start=3.0, end=1.0, focus_target="door", priority=0.8)

    def test_invalid_priority_rejected(self):
        """Verify priority outside [0.0, 1.0] is rejected."""
        with pytest.raises(ValidationError):
            AttentionEvent(start=0.0, end=2.0, focus_target="sword", priority=-0.1)
        with pytest.raises(ValidationError):
            AttentionEvent(start=0.0, end=2.0, focus_target="sword", priority=1.01)

    def test_empty_focus_target_rejected(self):
        """Verify empty string focus target is rejected."""
        with pytest.raises(ValidationError):
            AttentionEvent(start=0.0, end=1.0, focus_target="", priority=0.5)
        with pytest.raises(ValidationError):
            AttentionEvent(start=0.0, end=1.0, focus_target="   ", priority=0.5)

    def test_deterministic_ordering(self):
        """Verify AttentionMap orders events deterministically regardless of insertion sequence."""
        e1 = AttentionEvent(start=0.0, end=4.0, focus_target="narrator", priority=0.80)
        e2 = AttentionEvent(start=4.0, end=5.0, focus_target="door_slam", priority=0.95)
        e3 = AttentionEvent(start=4.0, end=7.0, focus_target="music_swell", priority=0.60)
        e4 = AttentionEvent(start=7.0, end=9.0, focus_target="silence", priority=1.00)

        # Construct in shuffled order
        map_shuffled = AttentionMap(events=[e3, e1, e4, e2])
        # Construct in reverse order
        map_reverse = AttentionMap(events=[e4, e3, e2, e1])

        # Both must produce identical ordered list: e1 (start 0.0), e2 (start 4.0, end 5.0), e3 (start 4.0, end 7.0), e4 (start 7.0)
        assert [e.focus_target for e in map_shuffled.events] == ["narrator", "door_slam", "music_swell", "silence"]
        assert [e.focus_target for e in map_reverse.events] == ["narrator", "door_slam", "music_swell", "silence"]
        assert map_shuffled.fingerprint() == map_reverse.fingerprint()

    def test_overlapping_events_and_priority_dominance(self):
        """
        Verify that overlapping cues are valid and deterministic priority resolution works.
        Music bed (0.0 to 10.0, priority 0.50)
        collides with sudden door kick (4.0 to 4.5, priority 0.95).
        """
        music_bed = AttentionEvent(
            start=0.0, end=10.0, focus_target="music_theme", priority=0.50, reason="mood bed"
        )
        door_kick = AttentionEvent(
            start=4.0, end=4.5, focus_target="door_kick", priority=0.95, reason="burst into room"
        )
        dialogue = AttentionEvent(
            start=4.5, end=8.0, focus_target="yell", priority=0.85, reason="battle cry"
        )

        att_map = AttentionMap(events=[music_bed, door_kick, dialogue])

        # At t = 2.0s: only music_bed is active
        assert att_map.get_dominant_target_at(2.0) == "music_theme"

        # At t = 4.2s: both music_bed (0.50) and door_kick (0.95) are active -> door_kick dominates!
        active_at_4_2 = att_map.get_active_events(4.2)
        assert len(active_at_4_2) == 2
        assert att_map.get_dominant_target_at(4.2) == "door_kick"

        # At t = 6.0s: both music_bed (0.50) and dialogue (0.85) are active -> dialogue dominates!
        assert att_map.get_dominant_target_at(6.0) == "yell"

        # At t = 9.0s: only music_bed remains active
        assert att_map.get_dominant_target_at(9.0) == "music_theme"

    def test_attention_is_not_dialogue(self):
        """
        STEP 6 VERIFICATION:
        Explicitly verify that dialogue is NOT always highest priority.
        Music, FX, and silence can each dominate over dialogue when narrative priority demands it.
        """
        # Scenario A: Whisper dialogue (0.70) overpowered by climactic musical revelation (0.95)
        quiet_speech = AttentionEvent(start=10.0, end=15.0, focus_target="speech", priority=0.70)
        musical_revelation = AttentionEvent(start=11.0, end=14.0, focus_target="orchestral_reveal", priority=0.95)

        map_music = AttentionMap(events=[quiet_speech, musical_revelation])
        assert map_music.get_dominant_target_at(12.0) == "orchestral_reveal"

        # Scenario B: Ambient dialogue (0.60) dropped for profound dramatic silence (0.98)
        background_talk = AttentionEvent(start=20.0, end=25.0, focus_target="dialogue", priority=0.60)
        dramatic_silence = AttentionEvent(start=21.5, end=23.0, focus_target="silence", priority=0.98, reason="smother cut")

        map_silence = AttentionMap(events=[background_talk, dramatic_silence])
        assert map_silence.get_dominant_target_at(22.0) == "silence"

        # Scenario C: Ordinary narration (0.75) interrupted by lethal blade clash (0.99)
        narration = AttentionEvent(start=30.0, end=35.0, focus_target="narrator", priority=0.75)
        blade_clash = AttentionEvent(start=31.0, end=31.8, focus_target="sword_clash", priority=0.99)

        map_fx = AttentionMap(events=[narration, blade_clash])
        assert map_fx.get_dominant_target_at(31.4) == "sword_clash"

    def test_resolve_windows_segmentation(self):
        """Verify resolve_windows segments timeline into discrete dominant attention windows."""
        e1 = AttentionEvent(start=0.0, end=4.0, focus_target="narrator", priority=0.80)
        e2 = AttentionEvent(start=4.0, end=5.0, focus_target="door", priority=0.95)
        e3 = AttentionEvent(start=5.0, end=8.0, focus_target="whisper", priority=1.00)
        e4 = AttentionEvent(start=8.0, end=8.5, focus_target="silence", priority=0.98)

        att_map = AttentionMap(events=[e1, e2, e3, e4])
        windows = att_map.resolve_windows()

        assert len(windows) == 4
        assert windows[0][2].focus_target == "narrator"
        assert windows[1][2].focus_target == "door"
        assert windows[2][2].focus_target == "whisper"
        assert windows[3][2].focus_target == "silence"

    def test_roundtrip_serialization(self):
        """Verify serialization and deserialization roundtrip preserves all event data."""
        att_map = AttentionMap.from_events(
            events=[
                {"start": 0.0, "end": 4.2, "focus_target": "narrator", "priority": 0.80, "reason": "narrative exposition"},
                {"start": 4.2, "end": 5.1, "focus_target": "door", "priority": 0.95, "reason": "environmental event"},
                {"start": 5.1, "end": 8.0, "focus_target": "whisper", "priority": 1.00, "reason": "intimate dialogue"},
                {"start": 8.0, "end": 8.35, "focus_target": "silence", "priority": 0.98, "reason": "dramatic pause"},
            ],
            scene_id="scene_001",
            chapter_id="c001",
        )

        serialized_json = att_map.to_json()
        reconstructed = AttentionMap.from_json(serialized_json)

        assert len(reconstructed.events) == 4
        assert reconstructed.events[0].focus_target == "narrator"
        assert reconstructed.events[3].focus_target == "silence"
        assert reconstructed.fingerprint() == att_map.fingerprint()


class TestCinemaAudioEngineIntegration:
    """Test suite for Stage 11 Cinema Audio Engine integration and semantics."""

    def test_stem_metadata_accepts_cinematic_mix_premaster(self):
        """Verify StemMetadata accepts CINEMATIC_MIX_PREMASTER and FULL_MASTER."""
        stem_premaster = StemMetadata(
            stem_type="CINEMATIC_MIX_PREMASTER",
            filepath="/tmp/c001_cinema_master.wav",
            duration_sec=60.0,
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
        )
        assert stem_premaster.stem_type == "CINEMATIC_MIX_PREMASTER"

        stem_legacy = StemMetadata(
            stem_type="FULL_MASTER",
            filepath="/tmp/c001_cinema_master.wav",
            duration_sec=60.0,
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
        )
        assert stem_legacy.stem_type == "FULL_MASTER"

    def test_stem_ledger_premaster_property(self):
        """Verify StemLedger.premaster returns CINEMATIC_MIX_PREMASTER or falls back to FULL_MASTER."""
        stem_pm = StemMetadata(
            stem_type="CINEMATIC_MIX_PREMASTER",
            filepath="/tmp/pm.wav",
            duration_sec=30.0,
        )
        ledger = StemLedger(
            chapter_id="c001",
            stems={"CINEMATIC_MIX_PREMASTER": stem_pm},
        )
        assert ledger.premaster is not None
        assert ledger.premaster.stem_type == "CINEMATIC_MIX_PREMASTER"

        # Fallback to legacy FULL_MASTER if only that is present
        stem_legacy = StemMetadata(
            stem_type="FULL_MASTER",
            filepath="/tmp/legacy.wav",
            duration_sec=30.0,
        )
        ledger_legacy = StemLedger(
            chapter_id="c002",
            stems={"FULL_MASTER": stem_legacy},
        )
        assert ledger_legacy.premaster is not None
        assert ledger_legacy.premaster.stem_type == "FULL_MASTER"

    def test_cinema_manifest_accepts_intent_and_attention(self):
        """Verify CinemaAudioManifest accepts scene_intent and attention_map without breaking."""
        intent = SceneMixIntent(focus="music", emotional_intensity=0.80)
        att_map = AttentionMap.from_events([
            {"start": 0.0, "end": 5.0, "focus_target": "theme", "priority": 0.90}
        ])

        manifest = CinemaAudioManifest(
            chapter_id="c001",
            scene_intent=intent,
            attention_map=att_map,
        )
        assert manifest.scene_intent is not None
        assert manifest.scene_intent.focus == "music"
        assert manifest.attention_map is not None
        assert len(manifest.attention_map.events) == 1
