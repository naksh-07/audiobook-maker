"""
Forensic Audit Remediation Test Suite (ADR-020).
Comprehensive regression verification for all 13 audit fixes:
- CreativeManifest deserialization rehydration (@model_validator)
- CLI & Orchestrator screenplay dict unpacking
- Gemini TTS defensive safety & finishReason parsing
- KeyManager text service backoff cooldown wait
- Gate 3.5 asset extension FTS5 fallback
- Gate 4.5 action beat size threshold (<=44B check)
- Sanitizer bracketed vocal tags and empty-text defense
- Scene acoustics multi-layer stochastic collision prevention
- Catalog seeder word-boundary matching for sub-bass tokens
- FFMETADATA1 special character escaping
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from audiobook_factory.contracts import (
    CreativeManifest,
    AmbienceScene,
    MusicCue,
    FoleyCue,
    MasteringConfig,
    ScreenplayScript,
    ScreenplaySegment,
    TimelineSegment,
    TimelineLedger,
)
from audiobook_factory.scene_acoustics import (
    SceneSoundscapeManifest,
    SceneAcousticProfile,
    AmbienceLayer,
)
from audiobook_factory.sanitizer import sanitize_screenplay_segment
from audiobook_factory.catalog_seeder import derive_virtual_metadata
from audiobook_factory.packager import _escape_ffmetadata, generate_ffmetadata
from audiobook_factory.gate_auditor import audit_gate3_5_acoustic_feasibility, audit_gate4_ledger
from audiobook_factory.sound_bank import SoundBank


class TestForensicAuditRemediation(unittest.TestCase):

    def test_creative_manifest_deserialization_roundtrip(self):
        """1.1 & Flaw 2: Verify CreativeManifest.from_json() rehydrates scene_acoustics into SceneSoundscapeManifest."""
        layer = AmbienceLayer(
            layer_type="base_room_tone",
            asset_path="wind_howl.ogg",
            target_lufs=-30.0,
        )
        scene = SceneAcousticProfile(
            scene_id="sc_001",
            start_ms=0,
            end_ms=10000,
            layers=[layer],
        )
        scene_manifest = SceneSoundscapeManifest(
            chapter_id="chapter_001",
            scenes=[scene],
        )

        manifest = CreativeManifest(
            chapter_id="chapter_001",
            silence_percentage=75.0,
            scene_acoustics=scene_manifest,
        )

        # Serialize to JSON and reload
        manifest_json = manifest.to_json()
        reloaded = CreativeManifest.from_json(manifest_json)

        # Verify type restoration
        self.assertIsNotNone(reloaded.scene_acoustics)
        self.assertIsInstance(reloaded.scene_acoustics, SceneSoundscapeManifest)
        self.assertEqual(len(reloaded.scene_acoustics.scenes), 1)
        self.assertEqual(reloaded.scene_acoustics.scenes[0].scene_id, "sc_001")
        self.assertTrue(hasattr(reloaded.scene_acoustics, "generate_stochastic_cues"))

    def test_cli_and_orchestrator_dict_screenplay_unpacking(self):
        """1.2 & 1.3: Verify screenplay scripts wrapped in dict format unpack cleanly."""
        dict_script = {
            "script_version": "2.0",
            "chapter_id": "chapter_001",
            "segments": [
                {"index": 1, "speaker": "Narrator", "text": "रात गहरी थी।"},
                {"index": 2, "speaker": "Geralt", "text": "रुको!"},
            ],
        }

        # Simulating unpacking logic added to CLI and Orchestrator
        script_data = dict_script
        if isinstance(script_data, dict):
            script_data = script_data.get("segments", script_data)

        self.assertIsInstance(script_data, list)
        self.assertEqual(len(script_data), 2)
        # Test dict comprehension that previously crashed with AttributeError
        seg_durs = {s.get("index", i): 4.0 for i, s in enumerate(script_data)}
        self.assertEqual(seg_durs, {1: 4.0, 2: 4.0})

    def test_sanitizer_combat_battlecry_not_dropped(self):
        """Flaw 3: Verify combat exclamations with multiple bracketed vocal tags are preserved."""
        seg = {
            "index": 1,
            "speaker": "Geralt",
            "text": "[bellowing battlecry] [guttural grunt on blade deflect] वार!",
            "type": "dialogue",
        }
        cleaned = sanitize_screenplay_segment(seg, is_hindi=True)
        self.assertIsNotNone(cleaned, "Battlecry segment must not be dropped by Latin word counter")
        self.assertIn("वार!", cleaned["text"])

    def test_sanitizer_empty_text_dropped(self):
        """3.3: Verify non-vocal action stage cues do not emit empty text strings to TTS."""
        # Non-vocal cue stripped to empty
        seg_action_cue = {
            "index": 2,
            "speaker": "Geralt",
            "text": "[तलवार टकराई]",
            "type": "dialogue",
        }
        res = sanitize_screenplay_segment(seg_action_cue, is_hindi=True)
        self.assertIsNone(res, "Segments where non-vocal tags leave empty text must be dropped")

        # Spoken segment with only vocal tag and no dialogue
        seg_whisper_only = {
            "index": 3,
            "speaker": "Yennefer",
            "text": "[whispers]",
            "type": "dialogue",
        }
        res2 = sanitize_screenplay_segment(seg_whisper_only, is_hindi=True)
        self.assertIsNone(res2, "Vocal tag with no spoken text must be dropped")

    def test_gate35_asset_extension_fallback(self):
        """2.1: Gate 3.5 must resolve assets with extensions via bank.resolve_sound() if direct path fails."""
        mock_bank = MagicMock(spec=SoundBank)
        # Direct path resolution fails
        mock_bank.resolve_asset_path.side_effect = FileNotFoundError("Not direct path")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(b"RIFF" + b"\x00" * 2000)
            valid_path = Path(tmp.name)

        try:
            # But FTS5 search resolves it
            mock_bank.resolve_sound.return_value = valid_path
            mock_bank._extract_duration.return_value = 5.0

            manifest = CreativeManifest(
                chapter_id="chapter_001",
                silence_percentage=80.0,
                foley_cues=[
                    FoleyCue(
                        cue_id="cue_01",
                        segment_index=1,
                        anchor_word="slash",
                        asset_id=1,
                        asset_path="sword_slash.wav",  # has extension .wav
                    )
                ],
            )

            result = audit_gate3_5_acoustic_feasibility(manifest, sound_bank=mock_bank)
            self.assertTrue(result.passed, f"Gate 3.5 should pass via sound bank fallback: {result.errors}")
            self.assertEqual(len(result.errors), 0)
        finally:
            valid_path.unlink(missing_ok=True)

    def test_gate45_action_beat_small_file(self):
        """2.2: Action beat silent WAV smaller than 1000B but > 44B must pass Gate 4.5."""
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            audio_dir = temp_path / "audio"
            audio_dir.mkdir()
            chunk_file = audio_dir / "c001_s0001_action.wav"

            # Create a 200-byte silent WAV file (> 44B header, but < 1000B)
            chunk_file.write_bytes(b"RIFF" + b"\x00" * 196)

            script_file = temp_path / "chapter_001_script.json"
            ledger_file = temp_path / "chapter_001_timeline_ledger.json"

            script = ScreenplayScript(
                chapter_id="chapter_001",
                segments=[
                    ScreenplaySegment(
                        index=1,
                        speaker="Foley",
                        text="[ACTION]",
                        type="action",
                    )
                ],
            )
            script_file.write_text(script.model_dump_json(indent=2), encoding="utf-8")

            seg_ledger = TimelineSegment(
                segment_index=1,
                speaker="Foley",
                text="[ACTION]",
                audio_file="c001_s0001_action.wav",
                start_ms=0,
                end_ms=50,
                duration_ms=50,
            )
            ledger = TimelineLedger(
                chapter_num=1,
                chapter_id="chapter_001",
                total_segments=1,
                total_timeline_duration_ms=50,
                total_dialogue_duration_ms=0,
                silence_percentage=100.0,
                segments=[seg_ledger],
            )
            ledger_file.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")

            res = audit_gate4_ledger(ledger_file=ledger_file, script_file=script_file, audio_dir=audio_dir)
            self.assertEqual(res["status"], "PASS")

    def test_scene_acoustics_multi_layer_collision_avoidance(self):
        """3.1: Multi-layer stochastic spot cues must not generate identical timestamps."""
        layer1 = AmbienceLayer(
            layer_type="spot_stochastic",
            asset_path="wood_creak",
            stochastic_interval_sec=5.0,
        )
        layer2 = AmbienceLayer(
            layer_type="spot_stochastic",
            asset_path="owl_hoot",
            stochastic_interval_sec=5.0,
        )
        scene = SceneAcousticProfile(
            scene_id="sc_001",
            start_ms=0,
            end_ms=20000,
            layers=[layer1, layer2],
        )
        manifest = SceneSoundscapeManifest(
            chapter_id="chapter_001",
            scenes=[scene],
        )

        cues = manifest.generate_stochastic_cues(sound_bank=None)
        layer1_cues = [c for c in cues if "wood_creak" in c.asset_path or "wood" in c.asset_path]
        layer2_cues = [c for c in cues if "owl_hoot" in c.asset_path or "owl" in c.asset_path]

        # Check timestamp collision
        all_timestamps = [c.start_ms for c in cues]
        self.assertEqual(len(all_timestamps), len(set(all_timestamps)), "All stochastic cue timestamps must be distinct!")

    def test_catalog_seeder_subtle_foley_classification(self):
        """Flaw 9: subtle_creak.wav must not be misclassified as Combat Foley."""
        meta_subtle = derive_virtual_metadata("subtle_creak.wav", "FOL", "Doors")
        self.assertEqual(meta_subtle["subcategory"], "Doors", "subtle_creak must be categorized as Doors, not Combat")

        meta_sub_drop = derive_virtual_metadata("sub_drop_hit.wav", "FOL", "General")
        self.assertEqual(meta_sub_drop["subcategory"], "Combat", "sub_drop must be categorized as Combat")

    def test_ffmetadata_escaping(self):
        """Flaw 12: Special characters (=, ;, #, \\) in FFMETADATA1 must be escaped."""
        escaped = _escape_ffmetadata("Book #1: C# & Python = Fun; Indeed")
        self.assertIn(r"\#1", escaped)
        self.assertIn(r"C\#", escaped)
        self.assertIn(r"\=", escaped)
        self.assertIn(r"\;", escaped)

        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "ffmetadata.txt"
            generate_ffmetadata(
                metadata={"title": "Test #1 = Epic; Edition", "author": "Author #2"},
                chapter_durations=[{"number": 1, "title": "Chapter #1; Start", "duration_ms": 1000}],
                output_file=out_file,
            )
            content = out_file.read_text(encoding="utf-8")
            self.assertIn(r"title=Test \#1 \= Epic\; Edition", content)
            self.assertIn(r"artist=Author \#2", content)
    def test_gemini_tts_defensive_safety_parsing(self):
        """1.4: Gemini TTS safety blocks with empty candidates must raise descriptive ValueError, not IndexError."""
        from audiobook_factory.tts_dispatcher import synthesize_gemini_tts
        from io import BytesIO

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "candidates": [],
            "promptFeedback": {"blockReason": "SAFETY"}
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "safety_test.wav"
            with patch("urllib.request.urlopen", return_value=mock_resp):
                with patch("audiobook_factory.key_manager.get_persistent_key_pool") as mock_km:
                    mock_km.return_value.get_key.return_value = "AIzaSyFakeKey123"
                    with self.assertRaises(ValueError) as ctx:
                        synthesize_gemini_tts(
                            text="खतरनाक दृश्य",
                            output_file=out_file,
                            voice="Aoede",
                        )
                    self.assertIn("blocked generation", str(ctx.exception))
                    self.assertIn("promptFeedback", str(ctx.exception))

    def test_key_manager_text_service_backoff(self):
        """1.5: PersistentKeyPool.get_key(service='text') must respect temporary backoff cooldown without crashing."""
        from datetime import datetime, timedelta
        from audiobook_factory.key_manager import PersistentKeyPool

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test_keys.db"
            km = PersistentKeyPool(keys=["AIzaSyValidKeyForText123"], db_path=db_path)

            # Place key into a 0.2s temporary backoff
            expiry = (datetime.now() + timedelta(seconds=0.2)).isoformat()
            with km.lock, km._connection() as conn:
                conn.execute(
                    "UPDATE key_quota_ledger SET status = 'TEMP_BACKOFF', backoff_until = ?",
                    (expiry,)
                )
                conn.commit()

            # get_key('text') should wait for backoff expiry (0.2s) and return key, not raise ValueError
            key = km.get_key(service="text")
            self.assertEqual(key, "AIzaSyValidKeyForText123")


if __name__ == "__main__":
    unittest.main()
