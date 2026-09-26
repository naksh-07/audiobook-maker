#!/usr/bin/env python3
"""
Audiobook Factory - Sound Design Quality Upgrade Comprehensive Test Suite.
===========================================================================
Validates the complete Sound Design Quality Upgrade:
1. Dramatic-beat-aware music cue intelligence & authentic no-music decisions.
2. 5-tier layered Ambience Engine with DramaticNarrativePhase modulation.
3. Cross-system choreography policies (12 canonical patterns).
4. Scene context understanding with manner-of-action Foley scoring.
5. Creature and Magic persistent sonic identity registries.
6. Asset pipeline integrity (zero fake paths, clean unresolved handling).
7. Independent QC Auditor with explainable QCViolationRecords and continuity checks.
"""

from __future__ import annotations
import pytest
from pathlib import Path
from typing import Dict, Any, List

from audiobook_factory.sound_design.contracts import (
    SceneAudioBlueprint,
    SoundTimeline,
    SoundTimelineEvent,
    SpatialMetadata,
    MixIntent,
    MusicCueSpec,
    QCViolationRecord,
    DramaticNarrativePhase,
)
from audiobook_factory.sound_design.sound_director import get_sound_design_director
from audiobook_factory.sound_design.music_motif_director import get_music_cue_director
from audiobook_factory.sound_design.ambience_engine import get_ambience_engine
from audiobook_factory.sound_design.scene_state import get_scene_state_manager, CrossSystemPolicy
from audiobook_factory.sound_design.scene_understanding import get_scene_understanding_engine
from audiobook_factory.sound_design.foley_engine import get_foley_engine
from audiobook_factory.sound_design.narrative_sfx import get_creature_identity_registry
from audiobook_factory.sound_design.magical_sound import get_magical_identity_registry
from audiobook_factory.sound_design.adapter import get_sound_design_adapter
from audiobook_factory.sound_design.qc import get_sound_design_qc_auditor
from audiobook_factory.contracts import CreativeManifest


# -----------------------------------------------------------------------------
# 1. Music Cue Intelligence & Beat-Aware Lifecycle
# -----------------------------------------------------------------------------

def test_music_cue_beat_aware_lifecycle():
    music_director = get_music_cue_director()
    
    # Scene with an explicit revelation turning beat
    dramatic_beats = [
        {
            "beat_id": "beat_rev_01",
            "start_ms": 12000,
            "dramatic_function": "revelation",
            "tension": 0.85,
            "description": "Truth about the lost heir revealed",
        }
    ]
    
    cues = music_director.direct_scene_cues(
        scene_id="scene_music_beat_test",
        start_ms=0,
        end_ms=30000,
        tension_level=0.85,
        dominant_emotion="revelation",
        characters_present=["Scholar", "Prince"],
        dramatic_beats=dramatic_beats,
        restraint_target="moderate",
    )
    
    assert len(cues) >= 1
    rev_cue = cues[0]
    # Verify beat-aware timing fields
    assert rev_cue.trigger_beat == "beat_rev_01" or rev_cue.start_ms <= 12000
    assert rev_cue.pre_roll_ms >= 500
    assert rev_cue.entry_type in ("fade_in", "pre_roll_swell", "sudden_hit", "subtle_drift")
    assert rev_cue.development_arc in ("tension_riser", "emotional_swell", "driving_rhythm", "steady_bed")
    assert rev_cue.release_type in ("fade_out", "sharp_cutoff", "reverb_spill", "ringout")
    assert len(rev_cue.narrative_rationale) > 10


def test_music_cue_restraint_no_music_in_quiet_scene():
    music_director = get_music_cue_director()
    
    # Intimate quiet grief scene with high restraint and no turning beats
    cues = music_director.direct_scene_cues(
        scene_id="scene_quiet_restraint",
        start_ms=0,
        end_ms=25000,
        tension_level=0.20,
        dominant_emotion="grief",
        characters_present=["Mourner"],
        dramatic_beats=[],
        restraint_target="high",
    )
    
    # Crucial studio invariant: NO MUSIC decision to preserve acoustic space
    assert len(cues) == 0, f"Expected 0 music cues in quiet restrained scene, got {len(cues)}"


# -----------------------------------------------------------------------------
# 2. 5-Tier Ambience Engine Architecture & Phase Modulation
# -----------------------------------------------------------------------------

def test_ambience_5_tier_architecture():
    amb_engine = get_ambience_engine()
    
    calm_layers = amb_engine.build_scene_ambience(
        scene_id="scene_amb_calm",
        chapter_id="chap_01",
        environment_id="castle_great_hall",
        start_ms=0,
        end_ms=30000,
        tension_level=0.20,
        mood="calm",
    )
    
    threat_layers = amb_engine.build_scene_ambience(
        scene_id="scene_amb_threat",
        chapter_id="chap_01",
        environment_id="castle_great_hall",
        start_ms=0,
        end_ms=30000,
        tension_level=0.88,
        mood="terror",
    )
    
    assert len(calm_layers) >= 1
    assert len(threat_layers) >= 1
    # Verify presence of BASE tier
    tiers = [layer.layer_tier for layer in calm_layers]
    assert "BASE" in tiers
    
    # Threat phase modulates base intensity to whisper_quiet to elevate dramatic tension
    calm_base = [l for l in calm_layers if l.layer_tier == "BASE"][0]
    threat_base = [l for l in threat_layers if l.layer_tier == "BASE"][0]
    assert calm_base.relative_intensity == "subtle_bed"
    assert threat_base.relative_intensity == "whisper_quiet"


# -----------------------------------------------------------------------------
# 3. Cross-System Choreography Policies
# -----------------------------------------------------------------------------

def test_cross_system_choreography_policies():
    from audiobook_factory.sound_design.contracts import SceneAudioUnderstandingResult
    state_mgr = get_scene_state_manager()
    
    state = state_mgr.initialize_state(
        scene_id="scene_cross_test",
        understanding=SceneAudioUnderstandingResult(
            scene_id="scene_cross_test",
            chapter_id="chap_01",
            environment_type="castle_great_hall",
            tension_level=0.75,
            dominant_emotion="shock",
        ),
        staged_positions={},
    )
    
    reactions = state_mgr.evaluate_cross_system_reactions(
        state=state,
        has_magic=True,
        has_creature=True,
        has_hard_sfx=True,
        is_stealth=False,
    )
    
    assert len(reactions) >= 3
    targets = [r.target_system for r in reactions]
    assert "WALLA" in targets or "AMBIENCE" in targets
    assert "MUSIC" in targets


# -----------------------------------------------------------------------------
# 4. Scene Context Understanding & Foley Manner of Action
# -----------------------------------------------------------------------------

def test_scene_context_manner_of_action():
    analyzer = get_scene_understanding_engine()
    foley_engine = get_foley_engine()
    
    # Stealth infiltration segments
    segments = [
        {
            "segment_index": 1,
            "speaker": "Rogue",
            "text": "She stepped quietly in hushed stealth across the cold flagstones.",
            "sfx_cues": [],
        }
    ]
    
    understanding = analyzer.analyze_scene(
        scene_id="scene_stealth_test",
        chapter_id="chap_01",
        segments=segments,
        dramatic_plan={"location": "crypt_subterranean", "tension": 0.75},
    )
    
    assert len(understanding.action_candidates) >= 1
    stealth_candidate = understanding.action_candidates[0]
    assert stealth_candidate.manner_of_action == "stealth"
    
    # Process through FoleyEngine
    scored = foley_engine.process_scene_actions(
        candidates=understanding.action_candidates,
        tension_level=0.75,
        restraint_target="high",
    )
    
    accepted = [f for f in scored if f.status == "ACCEPTED"]
    assert len(accepted) >= 1
    foley_cue = accepted[0]
    assert foley_cue.manner_of_action == "stealth"
    assert foley_cue.intensity_modifier == "whisper_quiet"


# -----------------------------------------------------------------------------
# 5. Creature & Magic Persistent Sonic Identities
# -----------------------------------------------------------------------------

def test_creature_and_magic_sonic_identity():
    creature_reg = get_creature_identity_registry()
    magic_reg = get_magical_identity_registry()
    
    # Verify striga identity
    striga = creature_reg.get_identity("striga")
    assert striga is not None
    assert striga.creature_type == "striga"
    assert "shriek" in striga.vocal_timbre
    assert striga.locomotion_weight == "fast_heavy_bipedal"
    
    # Verify magic sign/spell identity
    aard = magic_reg.get_identity("aard")
    assert aard is not None
    assert aard.spell_or_artifact_name == "Aard"
    assert aard.family == "kinetic_telekinetic"
    assert len(aard.charge_timbre) > 0
    assert len(aard.release_timbre) > 0


# -----------------------------------------------------------------------------
# 6. Asset Pipeline Integrity & Adapter
# -----------------------------------------------------------------------------

def test_adapter_zero_fake_paths():
    adapter = get_sound_design_adapter()
    
    segments = [
        {
            "segment_index": 1,
            "speaker": "Traveler",
            "text": "He poured the ale and stepped into the room.",
            "sfx_cues": [],
        }
    ]
    
    adapted = adapter.direct_and_adapt_scene(
        scene_id="scene_adapter_test",
        chapter_id="chap_01",
        segments=segments,
        start_ms=0,
        end_ms=15000,
    )
    
    foley_cues = adapted["foley_cues"]
    for fc in foley_cues:
        # Crucial Invariant: asset_path must NOT be fake 'foley.wav'
        assert fc.asset_path != "foley.wav"
        if fc.asset_path:
            assert Path(fc.asset_path).exists()


# -----------------------------------------------------------------------------
# 7. QC Auditor Forensic Hardening & Explainable Violations
# -----------------------------------------------------------------------------

def test_qc_deep_tableware_weapon_context_check():
    qc_auditor = get_sound_design_qc_auditor()
    
    blueprint = SceneAudioBlueprint(
        scene_id="scene_qc_dining_fail",
        chapter_id="chap_01",
        location_id="castle_great_hall",
        foley_planned=[],
    )
    
    # Dining action mistakenly assigned a weapon sword clash asset
    timeline = SoundTimeline(
        timeline_id="tl_dining_fail",
        chapter_id="chap_01",
        scene_id="scene_qc_dining_fail",
        total_duration_ms=10000,
        events=[
            SoundTimelineEvent(
                event_id="evt_amb",
                category="AMBIENCE",
                start_ms=0,
                duration_ms=10000,
                is_resolved=True,
                asset_path="valid_amb.wav",
            ),
            SoundTimelineEvent(
                event_id="evt_dining_clash",
                category="FOLEY",
                start_ms=2000,
                duration_ms=500,
                source_segment_index=1,
                asset_name="sword_blade_clash.wav",
                decision_reason="Guest cutting dinner roast at feast table",
                is_resolved=True,
                asset_path="sword_blade_clash.wav",
            ),
        ],
    )
    
    report = qc_auditor.audit_scene_sound_design(blueprint, timeline)
    assert report.status == "FAIL"
    assert any("Tableware vs Weapon collision" in err for err in report.errors)
    
    # Verify structured QCViolationRecord
    assert len(report.violations) >= 1
    viol = [v for v in report.violations if v.rule_id == "TABLEWARE_WEAPON_COLLISION"][0]
    assert viol.severity == "ERROR"
    assert viol.category == "FOLEY"
    assert "dining" in viol.reason.lower()
    assert len(viol.expected_behavior) > 5
    assert len(viol.actual_behavior) > 5


def test_qc_chapter_continuity_audit():
    qc_auditor = get_sound_design_qc_auditor()
    
    bp1 = SceneAudioBlueprint(
        scene_id="scene_1",
        chapter_id="chap_01",
        location_id="dark_forest",
        acoustic_profile_id="outdoor_forest_dense",
        foley_planned=[],
    )
    tl1 = SoundTimeline(
        timeline_id="tl_1",
        chapter_id="chap_01",
        scene_id="scene_1",
        total_duration_ms=10000,
        events=[
            SoundTimelineEvent(
                event_id="evt_amb_1",
                category="AMBIENCE",
                start_ms=0,
                duration_ms=10000,
                is_resolved=True,
                asset_path="forest_amb.wav",
            )
        ],
    )
    
    # Scene 2 is in same location but has an acoustic profile mismatch without transition
    bp2 = SceneAudioBlueprint(
        scene_id="scene_2",
        chapter_id="chap_01",
        location_id="dark_forest",
        acoustic_profile_id="indoor_stone_catacomb",  # Discontinuity!
        foley_planned=[],
    )
    tl2 = SoundTimeline(
        timeline_id="tl_2",
        chapter_id="chap_01",
        scene_id="scene_2",
        total_duration_ms=10000,
        events=[
            SoundTimelineEvent(
                event_id="evt_amb_2",
                category="AMBIENCE",
                start_ms=0,
                duration_ms=10000,
                is_resolved=True,
                asset_path="forest_amb.wav",
            )
        ],
    )
    
    reports = qc_auditor.audit_chapter_sound_design([bp1, bp2], [tl1, tl2])
    assert len(reports) == 2
    rep2 = reports[1]
    assert any("Acoustic profile discontinuity" in w for w in rep2.warnings)
    continuity_viols = [v for v in rep2.violations if v.rule_id == "AMBIENCE_CONTINUITY_MISMATCH"]
    assert len(continuity_viols) >= 1
