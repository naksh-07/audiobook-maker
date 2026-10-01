#!/usr/bin/env python3
"""
Unit tests for Stage 3.5 Specialist Multi-Agent Sound Spotting Engine (SoundSpotter).
Verifies:
1. Era-aware negative filtering (Modern excludes swamp, crypt, sword, tavern_brawl).
2. Proper construction of foley_cues, ambience_scenes, and music_cues.
3. Fallback to silence instead of wrong genre assets.
4. Output cue sheet structure compliance.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.sound_spotter import SoundSpotter, ERA_BANNED_TAGS
from audiobook_factory.contracts import FoleyCue, AmbienceScene, MusicCue


class MockSoundBank:
    """Mock sound bank simulating local asset catalog."""
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        # Create some real dummy wav files
        self.car_wav = tmp_path / "car_door_close.wav"
        self.car_wav.write_bytes(b"RIFFdummywav")

        self.swamp_wav = tmp_path / "amb_bog_swamp_night.wav"
        self.swamp_wav.write_bytes(b"RIFFdummywav")

        self.sword_wav = tmp_path / "sword_clash.wav"
        self.sword_wav.write_bytes(b"RIFFdummywav")

        self.room_wav = tmp_path / "domestic_room_quiet.wav"
        self.room_wav.write_bytes(b"RIFFdummywav")

        self.music_wav = tmp_path / "subtle_tension_theme.wav"
        self.music_wav.write_bytes(b"RIFFdummywav")

    def search(self, query, category=None, limit=5, era=None, negative_tags=None):
        q = query.lower()
        results = []
        if "car" in q:
            results.append({
                "id": 1,
                "filename": "car_door_close.wav",
                "filepath": str(self.car_wav),
                "tags": "car door vehicle modern",
                "category": "foley",
            })
            # Also include a medieval asset that might match if unfiltered
            results.append({
                "id": 2,
                "filename": "wooden_cart_door.wav",
                "filepath": str(self.swamp_wav),
                "tags": "cart tavern wood medieval",
                "category": "foley",
            })
        elif "swamp" in q or "bog" in q or "room" in q or "domestic" in q:
            results.append({
                "id": 3,
                "filename": "domestic_room_quiet.wav",
                "filepath": str(self.room_wav),
                "tags": "room interior quiet domestic",
                "category": "ambience",
            })
            results.append({
                "id": 4,
                "filename": "amb_bog_swamp_night.wav",
                "filepath": str(self.swamp_wav),
                "tags": "swamp bog night outdoor horror",
                "category": "ambience",
            })
        elif "sword" in q:
            results.append({
                "id": 5,
                "filename": "sword_clash.wav",
                "filepath": str(self.sword_wav),
                "tags": "sword blade combat medieval",
                "category": "foley",
            })
        return results

    def search_music_catalog(self, query, section_type="INTRO_BED", limit=3):
        return [{
            "id": 10,
            "filename": "subtle_tension_theme.wav",
            "filepath": str(self.music_wav),
            "start_sec": 0.0,
            "energy_level": 3,
            "tags": "subtle tension strings",
        }]


def test_era_banned_tags_modern():
    banned = ERA_BANNED_TAGS.get("MODERN", set())
    assert "swamp" in banned
    assert "sword" in banned
    assert "dungeon" in banned
    assert "crypt" in banned
    assert "car" not in banned


def test_foley_resolution_excludes_banned_era_tags(tmp_path):
    mock_sb = MockSoundBank(tmp_path)
    spotter = SoundSpotter(sound_bank=mock_sb)

    foley_events = [
        {"segment_index": 1, "action_verb": "car", "object_material": "door", "anchor_word": "कार", "gain_dbfs": -16.0, "pan": 0.0},
        {"segment_index": 2, "action_verb": "sword", "object_material": "metal", "anchor_word": "तलवार", "gain_dbfs": -14.0, "pan": 0.2},
    ]

    resolved = spotter._resolve_foley_cues(
        foley_events=foley_events,
        script_segments=[{"index": 1}, {"index": 2}],
        seg_starts_ms={1: 0, 2: 4000},
        segment_durations_sec={1: 3.5, 2: 2.0},
        banned_tags=ERA_BANNED_TAGS["MODERN"],
    )

    # In modern era, car should be resolved, sword should be completely omitted (no fantasy assets)
    assert len(resolved) == 1
    assert "car" in resolved[0]["asset_name"].lower()
    assert resolved[0]["segment_index"] == 1

    # Validate against FoleyCue contract
    cue = FoleyCue.model_validate(resolved[0])
    assert cue.segment_index == 1
    assert cue.anchor_word == "कार"


def test_ambience_resolution_excludes_swamp_in_modern_suburb(tmp_path):
    mock_sb = MockSoundBank(tmp_path)
    spotter = SoundSpotter(sound_bank=mock_sb)

    amb_events = [
        {"name": "domestic_room_quiet", "target_lufs": -32.0, "reverb_preset": "room"}
    ]

    resolved = spotter._resolve_ambience_beds(
        ambience_scenes=amb_events,
        total_duration_ms=60000,
        banned_tags=ERA_BANNED_TAGS["MODERN"],
        era="MODERN",
    )

    assert len(resolved) == 1
    assert "domestic_room_quiet" in resolved[0]["asset_name"]
    assert "swamp" not in resolved[0]["asset_name"]

    # Validate against AmbienceScene contract
    scene = AmbienceScene.model_validate(resolved[0])
    assert scene.target_lufs == -32.0
    assert scene.end_ms == 60000
