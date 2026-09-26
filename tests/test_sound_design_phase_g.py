#!/usr/bin/env python3
"""
Unit and Integration Tests for Sound Design Phase G:
Sound Director, QC Auditor & Adapter (Capability 20).
"""

import pytest
from audiobook_factory.sound_design.sound_director import SoundDesignDirector, get_sound_design_director
from audiobook_factory.sound_design.qc import SoundDesignQCAuditor, get_sound_design_qc_auditor
from audiobook_factory.sound_design.adapter import SoundDesignAdapter, get_sound_design_adapter
from audiobook_factory.contracts import CreativeManifest


def test_sound_director_and_qc_auditor_full_scene():
    director = get_sound_design_director()
    qc = get_sound_design_qc_auditor()

    segments = [
        {
            "segment_index": 1,
            "speaker": "Geralt",
            "text": "The beast is near. Draw your blade.",
            "sfx_cues": ["draws sword"],
            "start_ms": 0,
        },
        {
            "segment_index": 2,
            "speaker": "Narrator",
            "text": "A sudden explosion detonated in the courtyard, shattering the heavy oak doors.",
            "sfx_cues": ["explosion", "doors shattered"],
            "start_ms": 5000,
        },
    ]

    blueprint, timeline = director.direct_scene(
        scene_id="sc_test_director_01",
        chapter_id="chap_01",
        segments=segments,
        start_ms=0,
        end_ms=25000,
        environment_override="castle_stone_corridor",
    )

    assert blueprint.scene_id == "sc_test_director_01"
    assert timeline.total_duration_ms == 25000
    assert len(timeline.events) >= 4  # Ambience + Foley + SFX + Music + Silence

    # Run QC Audit
    report = qc.audit_scene_sound_design(blueprint, timeline)
    assert report.status in ("PASS", "WARN")
    assert report.restraint_score >= 0.70
    assert report.ambience_continuity_verified is True
    assert report.spatial_stage_valid is True
    assert len(report.errors) == 0


def test_sound_design_adapter_integration():
    adapter = get_sound_design_adapter()

    segments = [
        {
            "segment_index": 1,
            "speaker": "Harry",
            "text": "Alohomora!",
            "sfx_cues": ["spell cast"],
            "start_ms": 0,
        }
    ]

    res = adapter.direct_and_adapt_scene(
        scene_id="sc_adapt_01",
        chapter_id="chap_01",
        segments=segments,
        start_ms=0,
        end_ms=15000,
        environment_override="ancient_library",
    )

    assert "blueprint" in res
    assert "timeline" in res
    assert "scene_acoustic_profile" in res
    assert "qc_report" in res

    # Verify enrichment of CreativeManifest
    manifest = CreativeManifest(
        chapter_id="chap_01",
        silence_percentage=85.0,
    )

    enriched = adapter.enrich_creative_manifest(
        manifest=manifest,
        blueprints=[res["blueprint"]],
        timelines=[res["timeline"]],
    )

    assert enriched.chapter_id == "chap_01"
    assert enriched.metadata["sound_design_blueprints"] == 1
    assert enriched.metadata["sound_design_timeline_events"] >= 1
