#!/usr/bin/env python3
"""
Test Suite: Director Fallback Gate Verification (Empty Cue Sheet Safety).
"""

from unittest.mock import patch
from pathlib import Path
from audiobook_factory.director.director import AgentDirector


def test_director_fallback_gate_on_empty_cues():
    pdir = Path("audiobooks/projects/sword_of_destiny")
    director = AgentDirector(project_dir=pdir)

    script_segments = [
        {"index": 1, "speaker": "Narrator", "type": "narration", "text": "खंडहरों के बीच लोग खड़े थे।", "pause_after_ms": 600},
        {"index": 2, "speaker": "Geralt", "type": "dialogue", "text": "बैसिलिस्क मर चुका है।", "pause_after_ms": 600},
    ]
    seg_durations = {1: 5.0, 2: 4.0}

    # Mock SoundSpotter returning empty cue sheet (empty dict)
    with patch("audiobook_factory.sound_spotter.SoundSpotter.spot_chapter") as mock_spot:
        mock_spot.return_value = {
            "chapter_id": "chapter_002",
            "era": "MEDIEVAL_FANTASY",
            "foley_cues": [],
            "ambience_scenes": [],
            "music_cues": [],
        }

        # Mock Pass 1 so test runs instantly without network latency
        with patch.object(director, "_pass1_dramaturgy_and_silence_carving") as mock_pass1:
            mock_pass1.return_value = {
                "dramatic_theme": "Dark Slavic Witcher Fantasy",
                "ambience": [{"name": "stone_ruins_exterior", "target_lufs": -32.0}],
                "music_cues": [{
                    "cue_id": "cue_01",
                    "cue_type": "EMOTIONAL_UNDERSCORE",
                    "trigger_segment": 1,
                    "search_query": "wolf",
                    "duration_sec": 8.0,
                    "volume_db": -7.5,
                }],
                "foley_events": [{
                    "segment_index": 2,
                    "action_verb": "sword_draw",
                    "object_material": "metal",
                    "anchor_word": "बैसिलिस्क",
                    "gain_dbfs": -16.0,
                }],
            }

            manifest = director.direct_chapter_manifest(
                chapter_id="chapter_002",
                script_segments=script_segments,
                segment_durations_sec=seg_durations,
                total_duration_sec=9.0,
                project_dir=pdir,
            )

            # Fallback gate must engage and NOT leave manifest 100% silent
            assert manifest is not None
            mock_pass1.assert_called_once()
            assert len(manifest.ambience_scenes) > 0 or len(manifest.scene_acoustics.scenes) > 0
            assert len(manifest.music_cues) > 0
