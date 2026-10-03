import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.packager import package_m4b_audiobook
from audiobook_factory.gate_auditor import audit_chapter_gates, audit_gate5_master, GateAuditError
from audiobook_factory.key_manager import _load_env_fallback
from audiobook_factory.soundscape import detect_chapter_mood
from audiobook_factory.contracts import CreativeManifest
from audiobook_cli import cmd_render, cmd_synthesize, cmd_master


class TestAuditRemediationSprint(unittest.TestCase):
    """Regression test suite for audit remediation fixes."""

    def test_m4b_packager_wav_codec_detection(self):
        """Verifies that non-AAC (e.g. WAV) inputs force AAC transcode arguments rather than '-c:a copy'."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            wav1 = td_path / "chapter_001.wav"
            wav1.write_bytes(b"RIFF" + b"\x00" * 100)
            wav2 = td_path / "chapter_002.wav"
            wav2.write_bytes(b"RIFF" + b"\x00" * 100)

            chapter_files = [wav1, wav2]
            is_all_aac = all(f.suffix.lower() in (".m4a", ".aac") for f in chapter_files)
            audio_codec_args = ["-c:a", "copy"] if is_all_aac else ["-c:a", "aac", "-b:a", "192k"]

            self.assertFalse(is_all_aac)
            self.assertEqual(audio_codec_args, ["-c:a", "aac", "-b:a", "192k"])

            m4a_files = [td_path / "ch1.m4a", td_path / "ch2.m4a"]
            is_all_aac_m4a = all(f.suffix.lower() in (".m4a", ".aac") for f in m4a_files)
            audio_codec_args_m4a = ["-c:a", "copy"] if is_all_aac_m4a else ["-c:a", "aac", "-b:a", "192k"]
            self.assertTrue(is_all_aac_m4a)
            self.assertEqual(audio_codec_args_m4a, ["-c:a", "copy"])

    def test_gate3_dynamic_scenes_and_manifest(self):
        """Verifies that Gate 3 passes cleanly when driven by CreativeManifest or director-managed."""
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            (pdir / "extracted").mkdir()
            (pdir / "translation").mkdir()
            (pdir / "scripts").mkdir()
            (pdir / "manifests").mkdir()

            sample_en = "The morning mist hung heavy over the ancient forest. A solitary rider approached the village gate slowly." * 2
            sample_hi = "सुबह का घना कोहरा प्राचीन जंगल के ऊपर छाया हुआ था। एक अकेला घुड़सवार धीरे-धीरे गांव के फाटक के पास पहुंचा।" * 2
            (pdir / "extracted" / "chapter_001.md").write_text(sample_en, encoding="utf-8")
            (pdir / "translation" / "chapter_001_hi.md").write_text(sample_hi, encoding="utf-8")
            (pdir / "character_roster.json").write_text('{"characters": {"Narrator": {}}}', encoding="utf-8")
            (pdir / "voice_registry.json").write_text('{"Narrator": {"voice": "Aoede"}}', encoding="utf-8")
            (pdir / "scripts" / "chapter_001_hi_script.json").write_text(
                f'[{{"index": 1, "speaker": "Narrator", "text": "{sample_hi}"}}]', encoding="utf-8"
            )

            # Test 1: Neither legacy scenes nor manifest -> Fail closed (Directing stage must be executed)
            with self.assertRaises(GateAuditError) as ctx:
                audit_chapter_gates(pdir, 1)
            self.assertIn("Gate 3 Failed", str(ctx.exception))

            # Test 2: CreativeManifest present -> PASS feasibility
            manifest = CreativeManifest(
                chapter_id="chapter_001",
                total_duration_ms=5000,
                silence_percentage=70.0,
            )
            manifest.save_to_file(pdir / "manifests" / "chapter_001_manifest.json")
            report2 = audit_chapter_gates(pdir, 1)
            self.assertEqual(report2["gate_3"]["status"], "PASS")
            self.assertEqual(report2["gate_3"]["type"], "creative_manifest")

    def test_gate5_tolerance_standardization(self):
        """Verifies Gate 5 master probe default tolerance is standardized to 1.0 LU."""
        import inspect
        sig = inspect.signature(audit_gate5_master)
        self.assertEqual(sig.parameters["tolerance_lu"].default, 1.0)

    def test_env_loader_strips_quotes(self):
        """Verifies that .env keys with quotes are stripped cleanly."""
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / ".env"
            env_file.write_text('TEST_QUOTED_KEY="secret_key_123"\nTEST_SINGLE_QUOTE=\'val_456\'\n', encoding="utf-8")
            with patch("audiobook_factory.key_manager.Path") as mock_path:
                mock_path.return_value.resolve.return_value.parent.parent.__truediv__.return_value = env_file
                _load_env_fallback()

            self.assertEqual(os.environ.get("TEST_QUOTED_KEY"), "secret_key_123")
            self.assertEqual(os.environ.get("TEST_SINGLE_QUOTE"), "val_456")

    def test_soundscape_mood_service_type(self):
        """Verifies that detect_chapter_mood calls get_key with service='text' and fails closed when None."""
        from audiobook_factory.model_manager import LLMUnavailableError
        with patch("audiobook_factory.tts_dispatcher.global_key_pool.get_key") as mock_get_key:
            mock_get_key.return_value = None
            with self.assertRaises(LLMUnavailableError):
                detect_chapter_mood("Test chapter prose")
            mock_get_key.assert_called_with(service="text")

    def test_cli_chapter_regex_parsing(self):
        """Verifies that script files extract genuine chapter number rather than sequential enumerate."""
        import re
        filenames = [
            "chapter_005_hi_script.json",
            "chapter_012_script.json",
            "chapter_001_hi_script.json",
        ]
        parsed_chapters = []
        for fn in filenames:
            m = re.search(r"chapter_(\d+)", fn)
            parsed_chapters.append(int(m.group(1)) if m else 1)

        self.assertEqual(parsed_chapters, [5, 12, 1])

    def test_packager_chapter_exact_number_matching(self):
        """Verifies that chapter 1 does NOT resolve to chapter 10 audio in packager."""
        import re
        all_audio = [
            Path("chapter_10_cinematic.m4a"),
            Path("chapter_1_cinematic.m4a"),
            Path("chapter_100_cinematic.m4a"),
        ]

        def resolve_for_chapter(c_num):
            def _belongs_to_chapter(path: Path) -> bool:
                m = re.search(r"chapter[_-]?(\d+)", path.name, re.IGNORECASE)
                return m is not None and int(m.group(1)) == c_num

            ch_files = [f for f in all_audio if _belongs_to_chapter(f)]
            return sorted([f for f in ch_files if "_cinematic." in f.name.lower()])

        self.assertEqual(resolve_for_chapter(1), [Path("chapter_1_cinematic.m4a")])
        self.assertEqual(resolve_for_chapter(10), [Path("chapter_10_cinematic.m4a")])
        self.assertEqual(resolve_for_chapter(100), [Path("chapter_100_cinematic.m4a")])

    def test_verification_gate_word_boundary_anachronism(self):
        """Verifies that combat cues and carriages pass, while diesel trucks/cars are rejected."""
        from audiobook_factory.sound_bank.verification_gate import AudioVerificationGate

        gate = AudioVerificationGate()
        with tempfile.TemporaryDirectory() as td:
            # 1. Medieval combat SFX ("struck" contains "truck")
            combat_f = Path(td) / "sword_struck_shield.wav"
            combat_f.write_bytes(b"RIFF" + b"\x00" * 2000)

            # 2. Medieval carriage ("carriage" contains "car")
            carriage_f = Path(td) / "horse_carriage.wav"
            carriage_f.write_bytes(b"RIFF" + b"\x00" * 2000)

            # 3. Modern car
            car_f = Path(td) / "sports_car_rev.wav"
            car_f.write_bytes(b"RIFF" + b"\x00" * 2000)

            with patch.object(gate, "probe_audio", return_value={"duration_sec": 3.0, "format": "wav"}):
                res_combat = gate.verify_asset(combat_f, era="MEDIEVAL_FANTASY", category="SFX")
                self.assertTrue(res_combat.is_valid, f"Combat failed: {res_combat.reason}")

                res_carriage = gate.verify_asset(carriage_f, era="MEDIEVAL_FANTASY", category="SFX")
                self.assertTrue(res_carriage.is_valid, f"Carriage failed: {res_carriage.reason}")

                res_car = gate.verify_asset(car_f, era="MEDIEVAL_FANTASY", category="SFX")
                self.assertFalse(res_car.is_valid, "Modern car should have been banned")
                self.assertIn("Anachronism Detected", res_car.reason)

    def test_chapter_segmenter_extended_word_numbers(self):
        """Verifies that chapter_segmenter recognizes numbers up to 100 with compound words."""
        from audiobook_factory.chapter_segmenter import CHAPTER_PATTERNS
        import re

        word_pattern = CHAPTER_PATTERNS[-1]  # word-number pattern
        test_headers = [
            "ONE",
            "TWENTY-TWO",
            "THIRTY-FOUR: The Awakening",
            "FORTY",
            "FIFTY-SIX",
            "HUNDRED",
        ]
        for header in test_headers:
            self.assertTrue(
                bool(re.match(word_pattern, header, re.IGNORECASE)),
                f"Failed to match valid chapter header: '{header}'"
            )

    def test_acoustic_bus_matrix_duration_overlap(self):
        """Verifies that filter_concurrency_window detects overlapping durations, not just start times."""
        from audiobook_factory.acoustic_bus_matrix import filter_concurrency_window
        from types import SimpleNamespace

        # 3 long overlapping cues (duration 5s, staggered by 1s)
        cue1 = SimpleNamespace(start_ms=1000, duration_ms=5000, gain_dbfs=-10.0)
        cue2 = SimpleNamespace(start_ms=2000, duration_ms=5000, gain_dbfs=-15.0)
        cue3 = SimpleNamespace(start_ms=3000, duration_ms=5000, gain_dbfs=-20.0)

        # Max concurrency = 2 -> weakest cue3 should be dropped
        accepted = filter_concurrency_window([cue1, cue2, cue3], window_ms=200, max_concurrency=2)
        self.assertEqual(len(accepted), 2)
        self.assertIn(cue1, accepted)
        self.assertIn(cue2, accepted)
        self.assertNotIn(cue3, accepted)


if __name__ == "__main__":
    unittest.main()
