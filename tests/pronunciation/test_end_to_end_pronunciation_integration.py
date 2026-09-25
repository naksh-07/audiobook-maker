#!/usr/bin/env python3
"""
End-to-End Integration Test for Pronunciation & Spoken Language QA Subsystem.
Verifies the complete lifecycle:
BookBible -> PronunciationLexicon -> PronunciationResolver -> SpokenTextEngine ->
TTSDispatcher -> TakeBank -> PronunciationAudioQA -> Repair -> Certification (T0-T15) -> Provenance -> Book Master Gate 6E.
"""

import unittest
import tempfile
import json
import wave
from pathlib import Path

from audiobook_factory.translation.book_bible import BookBible, BookEntity
from audiobook_factory.translation.source_semantic_map import build_source_semantic_map
from audiobook_factory.translation.scene_planner import ScenePlan
from audiobook_factory.translation.certification import TranslationCertifier, GateStatus
from audiobook_factory.translation.provenance import TranslationProvenanceTracker
from audiobook_factory.contracts import ScreenplaySegment, ActingInstructions
from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.gate_auditor import audit_book_master
from audiobook_factory.pronunciation import (
    PronunciationLexicon,
    PronunciationResolver,
    SpokenTextEngine,
    PronunciationAudioQA,
    PronunciationRepairEngine,
    PronunciationStatus,
)


def create_mock_pcm_wav(path: Path, duration_sec: float = 2.0, sample_rate: int = 24000):
    """Creates a mock valid 24kHz mono PCM WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(sample_rate * duration_sec)
    import struct
    samples = [int(1500 * (i % 30 - 15)) for i in range(num_frames)]
    pcm = struct.pack(f"<{num_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


class TestEndToEndPronunciationIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

        # 1. Setup BookBible
        self.bible = BookBible(book_title="The Grand Case", author="A. Conan Doyle")
        self.bible.characters["Sherlock Holmes"] = BookEntity(
            canonical_id="sherlock_holmes",
            english_name="Sherlock Holmes",
            hindi_name="शरलॉक होम्स",
            pronunciation_hint="शरलॉक होम्स",
        )
        self.bible.terminology["Scotland Yard"] = "स्कॉटलैंड यार्ड"
        self.bible.save(self.project_dir)

        # Setup voice registry and roster for TTSDispatcher
        registry_file = self.project_dir / "voice_registry.json"
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump({"Sherlock Holmes": {"backend": "gemini_tts", "voice": "Charon"}}, f)

        roster_file = self.project_dir / "character_roster.json"
        with open(roster_file, "w", encoding="utf-8") as f:
            json.dump({
                "characters": {
                    "Sherlock Holmes": {"english_name": "Sherlock Holmes", "gender": "male"}
                }
            }, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_full_pronunciation_lifecycle(self):
        # Step A: Pronunciation Lexicon & Synchronization
        lexicon = PronunciationLexicon.load_or_create(self.project_dir, book_bible=self.bible)
        self.assertIn("sherlock_holmes", lexicon.entries)
        self.assertEqual(lexicon.entries["sherlock_holmes"].spoken_form, "शरलॉक होम्स")

        # Step B: Pronunciation Resolver & 7-tier hierarchy
        resolver = PronunciationResolver(lexicon, book_bible=self.bible)
        res_entity = resolver.resolve_token("Sherlock Holmes")
        self.assertEqual(res_entity.resolved_spoken, "शरलॉक होम्स")
        self.assertEqual(res_entity.status, PronunciationStatus.VERIFIED)

        # Step C: Spoken Text Engine & Immutability Verification
        spoken_engine = SpokenTextEngine(resolver)
        literary_line = "[whispers] Sherlock Holmes ने ₹500 दिए और कहा, “यह काफी है।”"
        seg = ScreenplaySegment(
            index=1,
            type="dialogue",
            speaker="Sherlock Holmes",
            text=literary_line,
        )

        spoken_res = spoken_engine.resolve_screenplay_segment(seg)

        # Invariant 1: Literary text MUST remain completely immutable
        self.assertEqual(seg.text, literary_line)
        self.assertEqual(spoken_res.literary_text, literary_line)

        # Invariant 2: Spoken text has proper phonetic expansions and acting tags
        self.assertTrue(spoken_res.spoken_text.startswith("[whispers]"))
        self.assertIn("शरलॉक होम्स", spoken_res.spoken_text)
        self.assertIn("पाँच सौ रुपये", spoken_res.spoken_text)

        # Step D: TTSDispatcher with Pronunciation Subsystem
        dispatcher = TTSDispatcher(project_dir=self.project_dir, max_workers=1)
        self.assertIsNotNone(dispatcher.spoken_text_engine)
        self.assertIsNotNone(dispatcher.pronunciation_auditor)

        # Step E: Audio QA and Verification Report
        mock_take_audio = self.project_dir / "audio_chunks" / "test_take.wav"
        create_mock_pcm_wav(mock_take_audio, duration_sec=3.5)

        qa_result = dispatcher.pronunciation_auditor.audit_take(
            take_audio_path=mock_take_audio,
            spoken_result=spoken_res,
            take_id="take_s0001_standard",
            segment_uid="s0001",
        )
        self.assertTrue(qa_result.passed)
        self.assertEqual(qa_result.status, PronunciationStatus.VERIFIED)

        # Step F: Translation Certification Gates T0 through T15
        source_text = "Sherlock Holmes gave 500 rupees and said that is enough."
        target_text = "शरलॉक होम्स ने पाँच सौ रुपये दिए और कहा कि यह काफी है।"

        source_map = build_source_semantic_map(source_text, scene_id="scene_001", known_entities=["Sherlock Holmes"])
        scene_plan = ScenePlan(
            scene_id="scene_001",
            scene_title="Scene 1",
            start_paragraph_idx=0,
            end_paragraph_idx=0,
            text_block=source_text,
            active_characters=["Sherlock Holmes"],
        )

        cert_res = TranslationCertifier.certify_scene(
            source_text=source_text,
            target_text=target_text,
            source_map=source_map,
            scene_plan=scene_plan,
            book_bible=self.bible,
            chapter_num=1,
            call_llm_fn=None,
            project_dir=self.project_dir,
        )

        self.assertTrue(cert_res.certified)
        self.assertIn("T12_spoken_language", cert_res.gates)
        self.assertIn("T13_pronunciation_plan", cert_res.gates)
        self.assertIn("T14_pronunciation_audio", cert_res.gates)
        self.assertIn("T15_pronunciation_consistency", cert_res.gates)
        self.assertEqual(cert_res.gates["T13_pronunciation_plan"].status, GateStatus.PASS)

        # Step G: Provenance Tracking with Pronunciation Hash
        comp_key = TranslationProvenanceTracker.generate_composite_key(
            source_text=source_text,
            bible_version_hash=self.bible.get_version_hash(),
            pronunciation_version="1.0",
            pronunciation_hash=dispatcher.pronunciation_lexicon.get_entry("sherlock_holmes").canonical_id,
        )
        self.assertIsNotNone(comp_key)
        self.assertGreater(len(comp_key), 10)

        # Step H: Book Master Gate 6E Pronunciation Consistency Check
        master_rep = audit_book_master(self.project_dir)
        self.assertIn("gate_6e_pronunciation_consistency", master_rep)
        self.assertTrue(master_rep["gate_6e_pronunciation_consistency"]["passed"])


if __name__ == "__main__":
    unittest.main()
