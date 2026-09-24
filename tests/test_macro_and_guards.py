#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3 Macro-Tier & Meso-Tier Verification Guards Test Suite.
Tests:
1. Pydantic contracts backward compatibility (100% non-destructive default values).
2. 12,000-word chapter auto-splitter on semantic boundaries (extractor.py).
3. Canonical Devanagari lexicon normalizer (translator.py).
4. Pre-flight API key health probe (cadence.py / tts_dispatcher.py).
5. Dynamic Foley-whisper collision attenuator (soundscape.py).
6. Gate 6A, 6B, 6C, 6D verification suite and master book auditor (gate_auditor.py).
"""

import os
import json
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.contracts import (
    CharacterProfile,
    CharacterRoster,
    ScreenplaySegment,
    ScreenplayScript,
    AmbienceScene,
    MasteringConfig,
    BookPackagingSpecs,
    BookChapterMarker,
    BookTableOfContents,
    BookVoiceRoster,
    GlobalLoreBible,
    BookMasterManifest,
)
from audiobook_factory.extractor import (
    split_large_chapter_on_semantic_boundary,
    extract_chapters,
)
from audiobook_factory.translator import normalize_translated_lexicon
from audiobook_factory.cadence import probe_key_health
from audiobook_factory.soundscape import attenuate_foley_whisper_collisions
from audiobook_factory.gate_auditor import (
    AuditResult,
    audit_gate6a_voice_continuity,
    audit_gate6b_loudness_continuity,
    audit_gate6c_toc_integrity,
    audit_gate6d_packaging_specs,
    audit_book_master,
)


class TestContractsAndBackwardCompatibility(unittest.TestCase):
    """Verifies that all new schema fields maintain 100% backward compatibility with legacy JSON."""

    def test_legacy_character_roster_deserialization(self):
        legacy_roster_json = {
            "project_id": "demo_project",
            "characters": [
                {
                    "character_uuid": "c-001",
                    "display_name": "Protagonist",
                    "gender": "male",
                    "assigned_voice_id": "Fenrir",
                }
            ],
        }
        roster = CharacterRoster.model_validate(legacy_roster_json)
        self.assertEqual(roster.project_id, "demo_project")
        self.assertEqual(len(roster.characters), 1)
        self.assertEqual(roster.characters[0].display_name, "Protagonist")
        self.assertEqual(roster.pronunciation_overrides, {})

    def test_character_roster_with_pronunciation_overrides(self):
        roster_data = {
            "project_id": "demo_project",
            "characters": [],
            "pronunciation_overrides": {
                "Protagonist": "नायक",
                "CapitalCity": "राजधानी",
            },
        }
        roster = CharacterRoster.model_validate(roster_data)
        self.assertEqual(roster.pronunciation_overrides["Protagonist"], "नायक")
        self.assertEqual(roster.pronunciation_overrides["CapitalCity"], "राजधानी")
        serialized = roster.model_dump()
        self.assertIn("pronunciation_overrides", serialized)

    def test_legacy_screenplay_segment_deserialization(self):
        legacy_segment = {
            "index": 1,
            "type": "dialogue",
            "speaker": "Geralt",
            "text": "Evil is evil, Stregobor.",
            "emotion": "neutral",
            "pause_after_ms": 400,
        }
        seg = ScreenplaySegment.model_validate(legacy_segment)
        self.assertEqual(seg.speaker, "Geralt")
        self.assertEqual(seg.intensity_level, "medium")
        self.assertEqual(seg.pre_roll_breath_ms, 0)

    def test_screenplay_segment_with_intensity_and_breath(self):
        segment_data = {
            "index": 2,
            "type": "dialogue",
            "speaker": "Renfri",
            "text": "[whispers] Remember me.",
            "emotion": "whispering",
            "pause_after_ms": 500,
            "intensity_level": "low",
            "pre_roll_breath_ms": 200,
        }
        seg = ScreenplaySegment.model_validate(segment_data)
        self.assertEqual(seg.intensity_level, "low")
        self.assertEqual(seg.pre_roll_breath_ms, 200)

    def test_screenplay_script_pronunciation_overrides(self):
        script_data = {
            "segments": [
                {
                    "index": 1,
                    "type": "narration",
                    "speaker": "Narrator",
                    "text": "The Hero arrived in the City.",
                }
            ],
            "pronunciation_overrides": {"Hero": "नायक"},
        }
        script = ScreenplayScript.model_validate(script_data)
        self.assertEqual(script.pronunciation_overrides.get("Hero"), "नायक")

    def test_ambience_and_mastering_acoustic_ir(self):
        legacy_ambience = {
            "scene_id": 1,
            "start_ms": 0,
            "end_ms": 5000,
            "asset_path": "wind.ogg",
        }
        amb = AmbienceScene.model_validate(legacy_ambience)
        self.assertIsNone(amb.acoustic_ir)

        amb_with_ir = AmbienceScene.model_validate({
            **legacy_ambience,
            "acoustic_ir": {"room_type": "stone_crypt", "rt60": 1.4},
        })
        self.assertIsNotNone(amb_with_ir.acoustic_ir)
        self.assertEqual(amb_with_ir.acoustic_ir["rt60"], 1.4)

        legacy_mastering = {
            "target_lufs": -19.0,
        }
        mc = MasteringConfig.model_validate(legacy_mastering)
        self.assertIsNone(mc.acoustic_ir)

        mc_with_ir = MasteringConfig.model_validate({
            **legacy_mastering,
            "acoustic_ir": {"convolution_preset": "cathedral"},
        })
        self.assertEqual(mc_with_ir.acoustic_ir["convolution_preset"], "cathedral")

    def test_macro_tier_book_master_manifest_roundtrip(self):
        manifest = BookMasterManifest(
            title="The Chronicles of Eldoria",
            author="Author Person",
            narrator="Charon",
            series_title="Eldoria Chronicles",
            book_number=1,
            total_duration_ms=3600000,
            voice_roster=BookVoiceRoster(
                character_voices={"Protagonist": "Fenrir", "Sorceress": "Aoede"},
                narrator_voice="Charon",
            ),
            lore_bible=GlobalLoreBible(
                lexicon={"Protagonist": "नायक", "CapitalCity": "राजधानी"},
                series_title="Eldoria Chronicles",
                book_number=1,
            ),
            toc=BookTableOfContents(
                chapters=[
                    BookChapterMarker(
                        chapter_index=1,
                        title="Chapter 1: The Beginning",
                        start_ms=0,
                        end_ms=1800000,
                        duration_ms=1800000,
                        integrated_lufs=-19.1,
                        true_peak_dbfs=-1.5,
                    ),
                    BookChapterMarker(
                        chapter_index=2,
                        title="Chapter 2: The Journey",
                        start_ms=1800000,
                        end_ms=3600000,
                        duration_ms=1800000,
                        integrated_lufs=-18.9,
                        true_peak_dbfs=-1.5,
                    ),
                ],
                total_duration_ms=3600000,
            ),
            packaging_specs=BookPackagingSpecs(
                codec="aac",
                bitrate="192k",
                sample_rate=44100,
                faststart=True,
            ),
        )

        json_str = manifest.to_json()
        deserialized = BookMasterManifest.from_json(json_str)
        self.assertEqual(deserialized.title, "The Chronicles of Eldoria")
        self.assertEqual(deserialized.voice_roster.character_voices["Protagonist"], "Fenrir")
        self.assertEqual(deserialized.lore_bible.lexicon["CapitalCity"], "राजधानी")
        self.assertEqual(len(deserialized.toc.chapters), 2)
        self.assertEqual(deserialized.packaging_specs.codec, "aac")


class TestExtractorSemanticSplitter(unittest.TestCase):
    """Verifies the 12,000 word ceiling auto-splitter on semantic boundaries."""

    def test_under_12k_words_untouched(self):
        short_content = "This is a short chapter text. " * 50
        parts = split_large_chapter_on_semantic_boundary("Chapter 1", short_content, max_words=12000)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["title"], "Chapter 1")

    def test_over_12k_words_splits_on_scene_break(self):
        # Generate 7,000 words, then scene break, then 7,000 words (total 14,000 words)
        part_a = "Geralt rode Roach through the dense forest. " * 1000  # ~7,000 words
        divider = "\n\n* * *\n\n"
        part_b = "At dawn he arrived at the tavern of Blaviken. " * 1000  # ~8,000 words
        long_content = part_a + divider + part_b

        parts = split_large_chapter_on_semantic_boundary("Chapter 01: The Lesser Evil", long_content, max_words=12000)
        self.assertEqual(len(parts), 2)
        self.assertIn("Part 1", parts[0]["title"])
        self.assertIn("Part 2", parts[1]["title"])
        self.assertLessEqual(parts[0]["words"], 12000)
        self.assertLessEqual(parts[1]["words"], 12000)

    def test_extract_chapters_applies_12k_guard(self):
        part_a = "Word " * 7000
        divider = "\n\n---\n\n"
        part_b = "Another " * 7000
        raw_text = f"# Chapter 1: Epic Prologue\n\n{part_a}{divider}{part_b}"

        chapters = extract_chapters(raw_text)
        self.assertEqual(len(chapters), 2)
        self.assertIn("Part 1", chapters[0]["title"])
        self.assertIn("Part 2", chapters[1]["title"])


class TestDevanagariLexiconNormalizer(unittest.TestCase):
    """Verifies deterministic regex substitution for canonical Devanagari spellings."""

    def test_basic_word_replacement(self):
        glossary = {"Geralt": "गेराल्ट", "Blaviken": "ब्लावीकेन"}
        raw_text = "Geralt entered the gates of Blaviken at dusk."
        normalized = normalize_translated_lexicon(raw_text, glossary)
        self.assertEqual(normalized, "गेराल्ट entered the gates of ब्लावीकेन at dusk.")

    def test_devanagari_variant_normalization(self):
        glossary = {"गेराल्ड": "गेराल्ट", "ब्लावीकन": "ब्लावीकेन"}
        raw_text = "गेराल्ड ने तलवार निकाली और ब्लावीकन की ओर देखा।"
        normalized = normalize_translated_lexicon(raw_text, glossary)
        self.assertEqual(normalized, "गेराल्ट ने तलवार निकाली और ब्लावीकेन की ओर देखा।")

    def test_nested_glossary_support(self):
        nested_glossary = {
            "characters": [
                {"english_name": "Elena", "hindi_name": "एलेना"},
                {"english_name": "Aria", "hindi_name": "आरिया"},
            ],
            "locations_and_terms": {
                "Sorcerer": "जादूगर",
            },
        }
        text = "Elena trained Aria to become a Sorcerer."
        normalized = normalize_translated_lexicon(text, nested_glossary)
        self.assertEqual(normalized, "एलेना trained आरिया to become a जादूगर.")

    def test_preserves_word_boundaries(self):
        glossary = {"Cat": "बिल्ली"}
        text = "The Catastrophe occurred today with a Cat."
        normalized = normalize_translated_lexicon(text, glossary)
        # "Catastrophe" should NOT have "Cat" replaced
        self.assertEqual(normalized, "The Catastrophe occurred today with a बिल्ली.")


class TestKeyHealthProbe(unittest.TestCase):
    """Verifies pre-flight API key health check and eviction."""

    def test_probe_evicts_invalid_keys(self):
        keys = ["GOOD_KEY_AAA", "BAD_KEY_BBB", "GOOD_KEY_CCC"]

        def mock_ping(key: str) -> bool:
            return "GOOD" in key

        healthy = probe_key_health(keys, ping_fn=mock_ping)
        self.assertEqual(healthy, ["GOOD_KEY_AAA", "GOOD_KEY_CCC"])

    def test_probe_handles_exceptions_gracefully(self):
        keys = ["KEY_OK", "KEY_CRASH", "KEY_FAIL"]

        def mock_ping(key: str) -> bool:
            if key == "KEY_CRASH":
                raise ConnectionResetError("Connection reset by peer")
            return key == "KEY_OK"

        healthy = probe_key_health(keys, ping_fn=mock_ping)
        self.assertEqual(healthy, ["KEY_OK"])


class TestFoleyWhisperCollisionAttenuator(unittest.TestCase):
    """Verifies -6 dBFS attenuation of Foley overlapping whispered / low-intensity lines."""

    def test_attenuates_foley_on_whisper_segment(self):
        segments = [
            ScreenplaySegment(
                index=1,
                type="dialogue",
                speaker="Renfri",
                text="[whispers] मत जाओ, गेराल्ट...",
                emotion="whispering",
                intensity_level="low",
            ),
            ScreenplaySegment(
                index=2,
                type="dialogue",
                speaker="Geralt",
                text="मुझे जाना ही होगा।",
                emotion="neutral",
                intensity_level="medium",
            ),
        ]

        foley_cues = [
            {"cue_id": "fc_001", "segment_index": 1, "gain_dbfs": -15.0, "pre_roll_ms": 100},
            {"cue_id": "fc_002", "segment_index": 2, "gain_dbfs": -15.0, "pre_roll_ms": 100},
        ]

        attenuated = attenuate_foley_whisper_collisions(foley_cues, segments, attenuation_db=-6.0)

        # Segment 1 cue should be attenuated by -6.0 dBFS (-15.0 -> -21.0)
        self.assertEqual(attenuated[0]["gain_dbfs"], -21.0)
        self.assertEqual(attenuated[0]["pre_roll_ms"], 250)

        # Segment 2 cue should remain unaffected (-15.0 dBFS)
        self.assertEqual(attenuated[1]["gain_dbfs"], -15.0)
        self.assertEqual(attenuated[1]["pre_roll_ms"], 100)


class TestGate6Suite(unittest.TestCase):
    """Verifies Gate 6A, 6B, 6C, 6D audit functions and composite audit_book_master."""

    def test_gate6a_voice_continuity_pass(self):
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            scripts_dir = pdir / "scripts"
            scripts_dir.mkdir()

            # Write 2 chapter scripts with consistent speaker 'Geralt'
            s1 = ScreenplayScript(segments=[
                ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="Line 1"),
            ])
            s2 = ScreenplayScript(segments=[
                ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="Line 2"),
            ])
            with open(scripts_dir / "chapter_001_script.json", "w", encoding="utf-8") as f:
                f.write(s1.model_dump_json())
            with open(scripts_dir / "chapter_002_script.json", "w", encoding="utf-8") as f:
                f.write(s2.model_dump_json())

            # Provide voice registry
            with open(pdir / "voice_registry.json", "w", encoding="utf-8") as f:
                json.dump({"Geralt": {"voice": "Fenrir"}}, f)

            res = audit_gate6a_voice_continuity(pdir)
            self.assertTrue(res.passed)
            self.assertEqual(res.status, "PASS")

    def test_gate6a_voice_continuity_fail_on_missing_voice(self):
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            scripts_dir = pdir / "scripts"
            scripts_dir.mkdir()

            # Geralt speaks in 2 chapters but is not in voice registry
            s1 = ScreenplayScript(segments=[
                ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="Line 1"),
            ])
            s2 = ScreenplayScript(segments=[
                ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="Line 2"),
            ])
            with open(scripts_dir / "chapter_001_script.json", "w", encoding="utf-8") as f:
                f.write(s1.model_dump_json())
            with open(scripts_dir / "chapter_002_script.json", "w", encoding="utf-8") as f:
                f.write(s2.model_dump_json())

            res = audit_gate6a_voice_continuity(pdir)
            self.assertFalse(res.passed)
            self.assertEqual(res.status, "FAIL")
            self.assertTrue(any("Geralt" in err for err in res.errors))

    def test_gate6b_loudness_continuity(self):
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            f1 = pdir / "ch1.wav"
            f2 = pdir / "ch2.wav"
            # Create mock wav files > 1000 bytes
            f1.write_bytes(b"RIFF" + b"\x00" * 2000)
            f2.write_bytes(b"RIFF" + b"\x00" * 2000)

            # In test environment where ffprobe/ebur128 defaults to target_lufs
            res = audit_gate6b_loudness_continuity([f1, f2], target_lufs=-19.0, max_variance=1.0)
            self.assertTrue(res.passed)
            self.assertEqual(res.status, "PASS")

    def test_gate6c_toc_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            f1 = pdir / "ch1.m4a"
            f2 = pdir / "ch2.m4a"
            f1.write_bytes(b"M4A " + b"\x00" * 2000)
            f2.write_bytes(b"M4A " + b"\x00" * 2000)

            valid_toc = BookTableOfContents(
                chapters=[
                    BookChapterMarker(
                        chapter_index=1,
                        title="Chapter 1",
                        start_ms=0,
                        end_ms=10000,
                        duration_ms=10000,
                    ),
                    BookChapterMarker(
                        chapter_index=2,
                        title="Chapter 2",
                        start_ms=10000,
                        end_ms=25000,
                        duration_ms=15000,
                    ),
                ],
                total_duration_ms=25000,
            )

            res = audit_gate6c_toc_integrity([f1, f2], toc=valid_toc)
            self.assertTrue(res.passed)
            self.assertEqual(res.status, "PASS")

            # Test overlapping / non-monotonic failure
            invalid_toc = BookTableOfContents(
                chapters=[
                    BookChapterMarker(
                        chapter_index=1,
                        title="Chapter 1",
                        start_ms=0,
                        end_ms=10000,
                        duration_ms=10000,
                    ),
                    BookChapterMarker(
                        chapter_index=2,
                        title="Chapter 2",
                        start_ms=8000,  # Overlap!
                        end_ms=25000,
                        duration_ms=17000,
                    ),
                ],
                total_duration_ms=25000,
            )
            res_invalid = audit_gate6c_toc_integrity([f1, f2], toc=invalid_toc)
            self.assertFalse(res_invalid.passed)
            self.assertEqual(res_invalid.status, "FAIL")

    def test_gate6d_packaging_specs(self):
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            cover = pdir / "cover.jpg"
            cover.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 5000)

            valid_specs = BookPackagingSpecs(codec="aac", bitrate="192k", faststart=True)
            res = audit_gate6d_packaging_specs(cover_image=cover, specs=valid_specs)
            self.assertTrue(res.passed)
            self.assertEqual(res.status, "PASS")

            invalid_specs = BookPackagingSpecs(codec="ogg", bitrate="192k", faststart=False)
            res_inv = audit_gate6d_packaging_specs(cover_image=cover, specs=invalid_specs)
            self.assertFalse(res_inv.passed)
            self.assertEqual(res_inv.status, "FAIL")

    def test_audit_book_master_composite(self):
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td)
            mastered_dir = pdir / "mastered"
            scripts_dir = pdir / "scripts"
            mastered_dir.mkdir()
            scripts_dir.mkdir()

            ch1_audio = mastered_dir / "chapter_001_cinematic.m4a"
            ch1_audio.write_bytes(b"M4A " + b"\x00" * 2000)

            ch1_script = ScreenplayScript(segments=[
                ScreenplaySegment(index=1, type="dialogue", speaker="Geralt", text="I am ready."),
            ])
            with open(scripts_dir / "chapter_001_script.json", "w", encoding="utf-8") as f:
                f.write(ch1_script.model_dump_json())

            with open(pdir / "voice_registry.json", "w", encoding="utf-8") as f:
                json.dump({"Geralt": {"voice": "Fenrir"}}, f)

            cover = pdir / "cover.jpg"
            cover.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 2000)

            report = audit_book_master(pdir)
            self.assertEqual(report["overall_status"], "PASS")
            self.assertTrue(report["overall_passed"])
            self.assertEqual(report["gate_6a"]["status"], "PASS")
            self.assertEqual(report["gate_6b"]["status"], "PASS")
            self.assertEqual(report["gate_6c"]["status"], "PASS")
            self.assertEqual(report["gate_6d"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
