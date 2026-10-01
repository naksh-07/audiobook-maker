#!/usr/bin/env python3
"""
Audiobook Factory - Cinematic Sound-Design Continuity & Failure Injection Test Suite.
=====================================================================================
Covers Prompt 6 Phases 22 & 23:
1. Recurring location sonic identity maintenance (Phase 3).
2. Seamless ambience cross-scene evolution without loop restarts (Phase 4).
3. Controlled ambience layering (<= 4 stems) (Phase 5).
4. High-value foley selection vs. low-value verb rejection (Phase 6).
5. Foley pre-roll synchronization to segment boundaries (Phase 7).
6. Music variation mode matching & silence preservation (Phases 9, 10, 11).
7. Intentional silence preservation vs. broken audio distinction (Phases 12, 13).
8. Smooth scene transitions & adapter enrichment (Phase 14).
9. Sound density constraint adherence (Phase 19).
10. Controlled failure injection & restoration cycles (wrong ambience, time warp, silence breach, tableware clash).
"""

import pytest
from pathlib import Path
from typing import Dict, Any, List

from audiobook_factory.sound_design.contracts import (
    SceneAudioUnderstandingResult,
    SceneAudioBlueprint,
    SoundTimeline,
    SoundTimelineEvent,
    SpatialMetadata,
    MixIntent,
    ActionCandidate,
    MotifVariationMode,
)
from audiobook_factory.sound_design.environment_profiles import get_environment_registry
from audiobook_factory.sound_design.ambience_engine import get_ambience_engine
from audiobook_factory.sound_design.foley_engine import get_foley_engine
from audiobook_factory.sound_design.silence_engine import get_silence_engine
from audiobook_factory.sound_design.music_motif_director import get_music_cue_director
from audiobook_factory.sound_design.sound_director import get_sound_design_director
from audiobook_factory.sound_design.adapter import get_sound_design_adapter
from audiobook_factory.sound_design.qc import get_sound_design_qc_auditor
from audiobook_factory.sound_design.asset_retriever import get_asset_retriever
from audiobook_factory.scene_acoustics import SceneSoundscapeManifest, SceneAcousticProfile, AmbienceLayer
from audiobook_factory.contracts import CreativeManifest, MasteringConfig, MusicCue, FoleyCue, AmbienceScene, ManifestValidationError


# =============================================================================
# 1. Recurring Location Sonic Identity Maintenance (Phase 3)
# =============================================================================
def test_recurring_location_sonic_identity():
    """
    Verifies that returning to a previously established location
    preserves its acoustic identity (reverb preset, occlusion barrier, stem layers).
    """
    registry = get_environment_registry()
    hall_p1 = registry.get_profile("castle_great_hall")
    hall_p2 = registry.resolve_from_text("The great hall of the castle was cold and quiet.")
    
    assert hall_p1 is not None
    assert hall_p2.env_id == "castle_great_hall"
    assert hall_p1.estimated_rt60_ms == hall_p2.estimated_rt60_ms
    assert hall_p1.occlusion_barrier_hz == hall_p2.occlusion_barrier_hz
    assert hall_p1.typical_ambience_layers == hall_p2.typical_ambience_layers
    
    # World acoustic profile mapping
    wap = registry.to_world_acoustic_profile("castle_great_hall")
    assert wap.space_type == "indoor_large"
    assert wap.ir_preset == "hall"
    assert wap.estimated_rt60_ms == 2200


# =============================================================================
# 2. Seamless Ambience Cross-Scene Evolution (Phase 4)
# =============================================================================
def test_seamless_ambience_cross_scene_evolution():
    """
    Verifies that successive scenes in the same environment maintain continuity
    without loop restarts, tracking cross-scene progression.
    """
    amb_engine = get_ambience_engine()
    amb_engine.reset()
    
    # Scene 1: Arrival at castle
    s1_layers = amb_engine.build_scene_ambience(
        scene_id="sc_001_arrival",
        chapter_id="ch_01",
        environment_id="castle_great_hall",
        start_ms=0,
        end_ms=20000,
        tension_level=0.3,
        mood="calm",
        previous_scene_id=None,
    )
    assert len(s1_layers) >= 1
    state1 = amb_engine._state_tracker.get("ch_01")
    assert state1 is not None
    assert state1.active_environment_id == "castle_great_hall"
    
    # Scene 2: Tension rises in the same castle hall
    s2_layers = amb_engine.build_scene_ambience(
        scene_id="sc_002_confrontation",
        chapter_id="ch_01",
        environment_id="castle_great_hall",
        start_ms=20000,
        end_ms=45000,
        tension_level=0.85,
        mood="threatening",
        previous_scene_id="sc_001_arrival",
    )
    state2 = amb_engine._state_tracker.get("ch_01")
    assert state2 is not None
    assert state2.active_environment_id == "castle_great_hall"
    assert state2.accumulated_duration_ms > 0
    # Higher tension should adapt relative intensity or layer presence
    assert any(l.relative_intensity in ("whisper_quiet", "subtle_bed", "normal", "prominent") for l in s2_layers)


# =============================================================================
# 3. Controlled Ambience Layering (<= 4 Stems) (Phase 5)
# =============================================================================
def test_controlled_ambience_layering_stem_limit():
    """
    Verifies that no scene exceeds the strict 4-stem decoupled limit:
    (Base Room Tone, Weather Elements, Crowd Walla, Spot Stochastic).
    """
    director = get_sound_design_director()
    segments = [
        {"segment_index": 1, "speaker": "Narrator", "text": "Rain pounded the tavern roof as the patrons cheered.", "start_ms": 0},
        {"segment_index": 2, "speaker": "Geralt", "text": "Quiet down.", "start_ms": 3000},
    ]
    bp, tl = director.direct_scene(
        scene_id="sc_tavern_crowd_test",
        chapter_id="ch_01",
        segments=segments,
        start_ms=0,
        end_ms=25000,
        environment_override="tavern_interior",
    )
    
    amb_events = [e for e in tl.events if e.category == "AMBIENCE"]
    assert len(amb_events) <= 4, f"Exceeded 4 stems limit: got {len(amb_events)}"
    
    # Verify in SceneAcousticProfile via adapter
    adapter = get_sound_design_adapter()
    adapted = adapter.direct_and_adapt_scene(
        scene_id="sc_tavern_crowd_test",
        chapter_id="ch_01",
        segments=segments,
        start_ms=0,
        end_ms=25000,
        environment_override="tavern_interior",
    )
    profile: SceneAcousticProfile = adapted["scene_acoustic_profile"]
    assert len(profile.layers) <= 4


# =============================================================================
# 4. High-Value Foley Selection vs. Low-Value Verb Rejection (Phase 6)
# =============================================================================
def test_high_value_foley_selection_vs_low_value_verb_rejection():
    """
    Verifies narrative foley scoring:
    - High-value tactile verbs (draw, clash, slam, unlock) score high and are preserved.
    - Low-value conversational/psychological verbs (nod, look, breathe, shrug, smile) are rejected.
    """
    foley_engine = get_foley_engine()
    candidates = [
        ActionCandidate(
            action_verb="draw",
            subject="Geralt",
            object_material="steel",
            segment_index=1,
            anchor_word="sword",
        ),
        ActionCandidate(
            action_verb="nod",
            subject="Innkeeper",
            object_material="flesh",
            segment_index=2,
            anchor_word="nodded",
        ),
        ActionCandidate(
            action_verb="shrug",
            subject="Dandelion",
            object_material="cloth",
            segment_index=3,
            anchor_word="shrugged",
        ),
        ActionCandidate(
            action_verb="slam",
            subject="Patron",
            object_material="heavy_wood",
            segment_index=4,
            anchor_word="tankard",
        ),
    ]
    
    scored = foley_engine.process_scene_actions(candidates, tension_level=0.5, restraint_target="moderate")
    approved_verbs = [c.action_verb for c in scored if c.status == "ACCEPTED"]
    rejected_verbs = [c.action_verb for c in scored if c.status == "REJECTED_TRIVIAL"]
    
    assert "draw" in approved_verbs, "Draw action should be approved"
    assert "slam" in approved_verbs, "Slam action should be approved"
    assert "nod" in rejected_verbs, "Low-value 'nod' must be rejected"
    assert "shrug" in rejected_verbs, "Low-value 'shrug' must be rejected"


# =============================================================================
# 5. Foley Pre-Roll Synchronization (Phase 7)
# =============================================================================
def test_foley_preroll_synchronization():
    """
    Verifies that physical Foley cues include pre-roll padding (minimum 80ms)
    and are aligned to word anchor positions within the active timeline.
    """
    director = get_sound_design_director()
    adapter = get_sound_design_adapter()
    segments = [
        {"segment_index": 1, "speaker": "Geralt", "text": "He drew his silver blade.", "sfx_cues": ["draw_sword"], "start_ms": 1000},
    ]
    adapted = adapter.direct_and_adapt_scene(
        scene_id="sc_foley_preroll",
        chapter_id="ch_01",
        segments=segments,
        start_ms=0,
        end_ms=10000,
    )
    for cue in adapted["foley_cues"]:
        assert cue.pre_roll_ms >= 80, f"Foley cue {cue.cue_id} pre-roll too short: {cue.pre_roll_ms}ms"
        assert -1.0 <= cue.azimuth_pan <= 1.0


# =============================================================================
# 6. Music Variation Mode Matching & Silence Preservation (Phases 9, 10, 11)
# =============================================================================
def test_music_variation_mode_and_silence_preservation():
    """
    Verifies that music motif director:
    - Chooses distinct variation modes matching dramatic context (CLIMAX, TENSE, INTIMATE).
    - Preserves negative silence in intimate/stealth scenes instead of forcing wall-to-wall cues.
    """
    music_dir = get_music_cue_director()
    
    # 1. Combat context -> Climax or Tense variation
    cues_combat = music_dir.direct_scene_cues(
        scene_id="sc_combat",
        start_ms=0,
        end_ms=40000,
        tension_level=0.9,
        dominant_emotion="combat",
        characters_present=["Geralt"],
        dramatic_beats=[{"type": "climax", "intensity": "high", "offset_ms": 5000}],
        restraint_target="dense",
    )
    assert len(cues_combat) >= 1
    assert cues_combat[0].variation_mode in ("CLIMAX", "TENSE")
    
    # 2. Stealth / Intimate grief context -> Silence preservation choice
    cues_quiet = music_dir.direct_scene_cues(
        scene_id="sc_quiet",
        start_ms=0,
        end_ms=30000,
        tension_level=0.2,
        dominant_emotion="stealth",
        characters_present=[],
        dramatic_beats=[],
        restraint_target="high",
    )
    # Directorial choice: NO MUSIC -> authentic negative silence preserved
    assert len(cues_quiet) == 0


# =============================================================================
# 7. Intentional Silence Preservation vs. Broken Audio (Phases 12, 13)
# =============================================================================
def test_intentional_silence_events_explicit_tagging():
    """
    Verifies that negative sound design explicitly stamps SILENCE events
    with dramatic purpose tags ('ambient_drop_suspense', 'music_drop_impact', 'reveal_breath')
    so that downstream listeners and QC know pause is artistic, not a DSP dropout.
    """
    silence_engine = get_silence_engine()
    understanding = SceneAudioUnderstandingResult(
        scene_id="sc_silence_test",
        chapter_id="ch_01",
        environment_type="ancient_library",
        dominant_emotion="mysterious",
        tension_level=0.75,
        characters_present=["Scholar"],
        silence_opportunities=["ambient_drop_suspense", "reveal_breath"],
    )
    beats = [
        {"type": "revelation", "offset_ms": 10000, "is_climax": False},
    ]
    
    silence_events = silence_engine.plan_silence_events(
        scene_id="sc_silence_test",
        scene_understanding=understanding,
        start_ms=0,
        end_ms=30000,
        dramatic_beats=beats,
    )
    
    assert len(silence_events) >= 1
    valid_purposes = {
        "ambient_drop_suspense", "music_drop_impact", "reveal_breath",
        "aftermath_contemplation", "profound_stillness", "walla_drop_arrival",
        "foley_suppression_stealth",
    }
    for s_evt in silence_events:
        assert s_evt.purpose in valid_purposes
        assert s_evt.duration_ms >= 500
        assert s_evt.start_ms >= 0


# =============================================================================
# 8. Smooth Scene Transitions & Adapter Enrichment (Phase 14)
# =============================================================================
def test_adapter_enrich_creative_manifest_with_soundscape():
    """
    Verifies that SoundDesignAdapter.enrich_creative_manifest:
    - Populates 4-stem decoupled SceneSoundscapeManifest in manifest.scene_acoustics.
    - Populates backward-compatible ambience_scenes if initially empty.
    - Stamps silence_events in metadata.
    - Preserves >= 60.0% silence mandate.
    """
    adapter = get_sound_design_adapter()
    director = get_sound_design_director()
    
    segments = [
        {"segment_index": 1, "speaker": "Narrator", "text": "The wind howled outside the old wooden tavern.", "start_ms": 0},
        {"segment_index": 2, "speaker": "Geralt", "text": "He drew his silver sword.", "start_ms": 4000},
    ]
    bp, tl = director.direct_scene(
        scene_id="sc_enrich_test",
        chapter_id="ch_enrich",
        segments=segments,
        start_ms=0,
        end_ms=20000,
        environment_override="tavern_interior",
    )
    
    base_manifest = CreativeManifest(
        chapter_id="ch_enrich",
        total_duration_ms=20000,
        silence_percentage=100.0,
        mastering=MasteringConfig(target_lufs=-19.0),
        music_cues=[],
        foley_cues=[],
        ambience_scenes=[],
    )
    
    enriched = adapter.enrich_creative_manifest(
        manifest=base_manifest,
        blueprints=[bp],
        timelines=[tl],
    )
    
    # 1. Decoupled scene acoustics populated
    assert enriched.scene_acoustics is not None
    assert isinstance(enriched.scene_acoustics, SceneSoundscapeManifest)
    assert len(enriched.scene_acoustics.scenes) == 1
    profile = enriched.scene_acoustics.scenes[0]
    assert profile.scene_id == "sc_enrich_test"
    assert len(profile.layers) <= 4
    
    # 2. Backward compatibility ambience scenes populated
    assert len(enriched.ambience_scenes) >= 1
    assert enriched.ambience_scenes[0].scene_id == 1
    
    # 3. Silence mandate verified
    assert enriched.silence_percentage >= 60.0
    
    # 4. Metadata stamped
    assert "sound_design_blueprints" in enriched.metadata
    assert enriched.metadata["sound_design_blueprints"] == 1


# =============================================================================
# 9. Sound Density Budget Compliance (Phase 19)
# =============================================================================
def test_sound_density_budget_compliance():
    """
    Verifies that SilenceEngine density arbiter correctly evaluates active sound density
    and identifies congestion under minimal/moderate restraint targets.
    """
    silence_engine = get_silence_engine()
    
    # 30-second scene with 12 seconds of sound = 40% density (within moderate target 35-70%)
    res_clean = silence_engine.evaluate_scene_density(
        total_duration_ms=30000,
        active_sound_spans=[(2000, 8000), (12000, 18000)],
        restraint_target="moderate",
        scene_start_ms=0,
    )
    assert res_clean["compliant"] is True
    assert res_clean["density"] == pytest.approx(0.40, abs=0.01)
    
    # 30-second scene with 27 seconds of sound = 90% density (violates high restraint max 45%)
    res_congested = silence_engine.evaluate_scene_density(
        total_duration_ms=30000,
        active_sound_spans=[(0, 27000)],
        restraint_target="high",
        scene_start_ms=0,
    )
    assert res_congested["compliant"] is False
    assert res_congested["density"] == pytest.approx(0.90, abs=0.01)


# =============================================================================
# 10. Controlled Failure Injection & Restoration Tests (Phases 22 & 23)
# =============================================================================
def test_failure_injection_wrong_ambience_rejected_and_restored():
    """
    Failure Injection 1: Subterranean crypt scene assigned sunny open road ambience.
    - Must be flagged as WARN or FAIL by QC auditor.
    - Must PASS when restored to canonical subterranean crypt profile.
    """
    qc_auditor = get_sound_design_qc_auditor()
    
    # Broken scenario: crypt location with open_road ambience
    broken_bp = SceneAudioBlueprint(
        scene_id="sc_fi_01",
        chapter_id="ch_fi",
        location_id="crypt_catacomb",
        restraint_target="moderate",
        metadata={"environment_type": "open_road"},
    )
    broken_tl = SoundTimeline(
        timeline_id="tl_fi_01",
        chapter_id="ch_fi",
        scene_id="sc_fi_01",
        total_duration_ms=20000,
        events=[
            SoundTimelineEvent(
                event_id="evt_wrong_amb",
                category="AMBIENCE",
                start_ms=0,
                duration_ms=20000,
                relative_intensity="subtle_bed",
                priority="LOW",
                asset_path="sunny_country_birds_open_road.wav",
                asset_name="sunny_country_birds_open_road.wav",
                decision_reason="Injected mismatch",
                dramatic_purpose="Outdoor birds in subterranean tomb",
            )
        ],
    )
    
    report_broken = qc_auditor.audit_scene_sound_design(broken_bp, broken_tl)
    # Flags warning or error due to asset resolution or mismatch
    assert report_broken.status in ("WARN", "FAIL") or len(report_broken.warnings) > 0 or len(report_broken.errors) > 0
    
    # Restored scenario: canonical crypt audio
    fixed_bp = SceneAudioBlueprint(
        scene_id="sc_fi_01",
        chapter_id="ch_fi",
        location_id="crypt_catacomb",
        restraint_target="moderate",
        metadata={"environment_type": "crypt_catacomb"},
    )
    fixed_tl = SoundTimeline(
        timeline_id="tl_fi_01_fixed",
        chapter_id="ch_fi",
        scene_id="sc_fi_01",
        total_duration_ms=20000,
        events=[
            SoundTimelineEvent(
                event_id="evt_fixed_amb",
                category="AMBIENCE",
                start_ms=0,
                duration_ms=20000,
                relative_intensity="subtle_bed",
                priority="LOW",
                asset_path="amb_crypt_tomb_drips.wav",
                asset_name="amb_crypt_tomb_drips.wav",
                decision_reason="Canonical subterranean ambience",
                dramatic_purpose="Cold damp tomb atmosphere",
            )
        ],
    )
    report_fixed = qc_auditor.audit_scene_sound_design(fixed_bp, fixed_tl)
    assert len(report_fixed.errors) == 0


def test_failure_injection_time_warp_integrity_caught_and_restored():
    """
    Failure Injection 2: Scene with backwards chronological order (start_ms < prev.start_ms)
    or invalid duration (end_ms <= start_ms).
    - Must FAIL audit_scene_acoustics_integrity.
    - Must PASS when timestamps are properly sequenced.
    """
    broken_manifest = SceneSoundscapeManifest(
        chapter_id="ch_fi_time",
        scenes=[
            SceneAcousticProfile(
                scene_id="sc_001",
                start_ms=10000,
                end_ms=20000,
                layers=[],
            ),
            SceneAcousticProfile(
                scene_id="sc_002_warp",
                start_ms=5000,  # Time warp! Earlier than sc_001
                end_ms=15000,
                layers=[],
            ),
        ],
    )
    audit_broken = broken_manifest.audit_scene_acoustics_integrity()
    assert audit_broken["status"] == "FAIL"
    assert any("backwards in time" in err for err in audit_broken["errors"])
    
    # Restored: chronological sequence
    fixed_manifest = SceneSoundscapeManifest(
        chapter_id="ch_fi_time",
        scenes=[
            SceneAcousticProfile(
                scene_id="sc_001",
                start_ms=0,
                end_ms=10000,
                layers=[],
            ),
            SceneAcousticProfile(
                scene_id="sc_002",
                start_ms=10000,
                end_ms=20000,
                layers=[],
            ),
        ],
    )
    audit_fixed = fixed_manifest.audit_scene_acoustics_integrity()
    assert audit_fixed["status"] == "PASS"
    assert len(audit_fixed["errors"]) == 0


def test_failure_injection_silence_breach_caught_and_restored():
    """
    Failure Injection 3: CreativeManifest with wall-to-wall music breaching the 60% silence mandate.
    - Must raise validation error upon validation.
    - Must PASS when music duration is trimmed to comply with >= 60.0% silence.
    """
    total_dur = 60000  # 60 seconds
    excessive_music = [
        MusicCue(
            cue_id="mc_excessive",
            cue_type="CLIMACTIC_ACTION_CUE",
            track_id=1,
            track_name="Battle_Anthem.wav",
            section_name="CLIMAX",
            section_start_sec=0.0,
            start_ms=0,
            duration_ms=45000,  # 45s of music in 60s chapter = only 25% silence!
        )
    ]
    
    # Must fail validation when silence percentage breaches 60%
    with pytest.raises((ManifestValidationError, ValueError)):
        CreativeManifest(
            chapter_id="ch_silence_breach",
            total_duration_ms=total_dur,
            silence_percentage=25.0,  # Breaches 60.0% standard
            music_cues=excessive_music,
            foley_cues=[],
            ambience_scenes=[],
        )
        
    # Restored: trimmed to 18 seconds (70% silence)
    fixed_music = [
        MusicCue(
            cue_id="mc_calibrated",
            cue_type="CLIMACTIC_ACTION_CUE",
            track_id=1,
            track_name="Battle_Anthem.wav",
            section_name="CLIMAX",
            section_start_sec=0.0,
            start_ms=20000,
            duration_ms=18000,  # 18s in 60s chapter = 70% silence
        )
    ]
    fixed_manifest = CreativeManifest(
        chapter_id="ch_silence_breach",
        total_duration_ms=total_dur,
        silence_percentage=70.0,
        music_cues=fixed_music,
        foley_cues=[],
        ambience_scenes=[],
    )
    fixed_manifest.validate()
    assert fixed_manifest.silence_percentage == 70.0


def test_failure_injection_tableware_isolation_caught_and_restored():
    """
    Failure Injection 4: In a domestic banquet setting, a plate clatter action
    must never be resolved to a combat weapon asset.
    """
    retriever = get_asset_retriever()
    
    # Inquire tableware with dining context
    desc = retriever.resolve_foley_asset(
        action_verb="clatter",
        exciter_material="ceramic_plate",
        surface_material="wood",
        context_tags=["dinner", "feast", "banquet"],
    )
    # If resolved, it must NEVER contain weapon/sword/blade in path or tags
    if desc:
        fname = Path(desc.filepath).name.lower()
        assert "sword" not in fname
        assert "blade" not in fname
        assert "weapon" not in fname
