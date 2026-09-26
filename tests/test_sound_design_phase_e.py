#!/usr/bin/env python3
"""
Unit and Integration Tests for Sound Design Phase E:
Score Dramaturgy & Leitmotif Intelligence (Capabilities 13, 14, 15).
"""

import pytest
from audiobook_factory.sonic_bible import LeitmotifDefinition, SonicBible
from audiobook_factory.sound_design.music_motif_director import (
    MotifVariationEngine,
    MusicCueDirector,
    get_music_cue_director,
)
from audiobook_factory.contracts import MusicCue


def test_motif_variation_engine():
    engine = MotifVariationEngine()

    # 1. Test derivation
    assert engine.derive_variation_mode(tension_level=0.9, dominant_emotion="neutral") == "CLIMAX"
    assert engine.derive_variation_mode(tension_level=0.4, dominant_emotion="grief") == "TRAGIC"
    assert engine.derive_variation_mode(tension_level=0.3, dominant_emotion="intimate") == "INTIMATE"
    assert engine.derive_variation_mode(tension_level=0.7, dominant_emotion="suspense") == "TENSE"
    assert engine.derive_variation_mode(tension_level=0.2, dominant_emotion="peace") == "AFTERMATH"

    # 2. Test variation application
    base_motif = LeitmotifDefinition(
        motif_id="lm_geralt",
        entity_type="character",
        associated_entity="Geralt",
        track_id=42,
        track_name="White Wolf Theme",
        primary_instrument="Solo Cello & Hurdy-Gurdy",
        canonical_tempo_bpm=100,
        dramatic_intent="Heroic yet weary witcher destiny",
        priority_level=10,
    )

    climax_var = engine.apply_variation(base_motif, "CLIMAX")
    assert climax_var["variation_mode"] == "CLIMAX"
    assert climax_var["effective_tempo_bpm"] > 100  # Accelerated tempo
    assert climax_var["priority"] == "CRITICAL"

    intimate_var = engine.apply_variation(base_motif, "INTIMATE")
    assert intimate_var["variation_mode"] == "INTIMATE"
    assert intimate_var["effective_tempo_bpm"] < 100  # Slower tempo
    assert intimate_var["relative_intensity"] == "whisper_quiet"


def test_music_cue_director_adaptive_restraint_and_conversion():
    bible = SonicBible(book_title="Test Book")
    custom_motif = LeitmotifDefinition(
        motif_id="lm_yennefer",
        entity_type="character",
        associated_entity="Yennefer",
        track_id=101,
        track_name="Lilac and Gooseberries",
        primary_instrument="Solo Viola & High Chimes",
        canonical_tempo_bpm=80,
        dramatic_intent="Enigmatic sorceress presence",
        priority_level=9,
    )
    bible.register_leitmotif(custom_motif)

    director = MusicCueDirector(sonic_bible=bible)

    # 1. High restraint scene: sparse single cue
    cues_high = director.direct_scene_cues(
        scene_id="sc_restraint_test",
        start_ms=0,
        end_ms=30000,
        tension_level=0.3,
        dominant_emotion="intimate",
        characters_present=["Yennefer"],
        restraint_target="high",
    )
    assert len(cues_high) == 1
    assert cues_high[0].motif_id == "lm_yennefer"
    assert cues_high[0].variation_mode == "INTIMATE"
    assert cues_high[0].relative_intensity == "whisper_quiet"

    # 2. Climax scene: full driving score
    cues_climax = director.direct_scene_cues(
        scene_id="sc_climax_test",
        start_ms=0,
        end_ms=45000,
        tension_level=0.95,
        dominant_emotion="terror",
        characters_present=["Yennefer"],
        restraint_target="dense",
    )
    assert len(cues_climax) == 1
    assert cues_climax[0].variation_mode == "CLIMAX"
    assert cues_climax[0].priority == "CRITICAL"

    # 3. Downstream legacy conversion
    legacy_cues = director.to_legacy_music_cues(cues_high)
    assert len(legacy_cues) == 1
    assert isinstance(legacy_cues[0], MusicCue)
    assert legacy_cues[0].track_id == 101
    assert legacy_cues[0].fade_in_ms == 2500
