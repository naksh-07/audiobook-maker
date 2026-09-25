#!/usr/bin/env python3
"""
Unit tests for Pronunciation & Spoken Language Domain Contracts.
"""

import unittest
from audiobook_factory.pronunciation.contracts import (
    PronunciationStatus,
    PronunciationSource,
    SpokenLanguage,
    PronunciationPolicy,
    PronunciationEntry,
    PronunciationResolutionResult,
    SpokenTextResult,
    PronunciationAudioQAResult,
    CrossChapterPronunciationDrift,
    PronunciationProvenanceRecord,
)
from audiobook_factory.contracts import ScreenplaySegment


class TestPronunciationContracts(unittest.TestCase):

    def test_01_pronunciation_entry_auto_canonical_id_and_defaults(self):
        entry = PronunciationEntry(
            canonical_text="Sherlock Holmes",
            expected_language=SpokenLanguage.ENGLISH,
            pronunciation_hint="शरलॉक होम्स",
        )
        self.assertEqual(entry.canonical_id, "sherlock_holmes")
        self.assertEqual(entry.spoken_form, "शरलॉक होम्स")
        self.assertEqual(entry.status, PronunciationStatus.LIKELY)
        self.assertEqual(entry.source, PronunciationSource.CANONICAL_LEXICON)
        self.assertEqual(entry.policy, PronunciationPolicy.STRICT_CANONICAL)

    def test_02_pronunciation_resolution_result(self):
        res = PronunciationResolutionResult(
            original_token="Sherlock",
            canonical_id="sherlock_holmes",
            resolved_spoken="शरलॉक",
            status=PronunciationStatus.VERIFIED,
            source=PronunciationSource.BOOK_BIBLE,
            language=SpokenLanguage.ENGLISH,
            transformation_applied=True,
            requires_review=False,
            explanation="Resolved via BookBible hint",
        )
        self.assertEqual(res.resolved_spoken, "शरलॉक")
        self.assertTrue(res.transformation_applied)
        self.assertFalse(res.requires_review)

    def test_03_spoken_text_result_immutability(self):
        lit_text = "उसने कहा, “Sherlock यहाँ आया था।”"
        disp_text = "उसने कहा, “Sherlock यहाँ आया था।”"
        spk_text = "उसने कहा, “शरलॉक यहाँ आया था।”"

        result = SpokenTextResult(
            literary_text=lit_text,
            display_text=disp_text,
            spoken_text=spk_text,
            resolutions=[
                PronunciationResolutionResult(
                    original_token="Sherlock",
                    resolved_spoken="शरलॉक",
                    status=PronunciationStatus.VERIFIED,
                    source=PronunciationSource.CANONICAL_LEXICON,
                    transformation_applied=True,
                )
            ],
            has_unresolved_critical=False,
            requires_review=False,
        )
        # Verify literary text remains identical to original prose
        self.assertEqual(result.literary_text, lit_text)
        self.assertNotEqual(result.literary_text, result.spoken_text)
        self.assertEqual(result.spoken_text, spk_text)

    def test_04_screenplay_segment_backward_compatibility(self):
        seg = ScreenplaySegment(
            index=1,
            type="dialogue",
            speaker="Geralt",
            text="यह रास्ता बंद है।",
        )
        self.assertIsNone(seg.spoken_text)
        self.assertIsNone(seg.pronunciation_metadata)

        # Setting spoken_text does not mutate literary text
        seg.spoken_text = "यह रास्ता बंद है।"
        seg.pronunciation_metadata = [{"token": "रास्ता", "status": "VERIFIED"}]
        self.assertEqual(seg.text, "यह रास्ता बंद है।")
        self.assertEqual(seg.spoken_text, "यह रास्ता बंद है।")

    def test_05_audio_qa_result_contract(self):
        qa = PronunciationAudioQAResult(
            take_id="take_s0001_standard",
            segment_uid="s0001",
            passed=True,
            status=PronunciationStatus.VERIFIED,
            token_alignments=[{"token": "शरलॉक", "start_ms": 300, "end_ms": 750, "duration_ms": 450}],
            omissions=[],
            repetitions=[],
            timing_anomalies=[],
            review_reasons=[],
        )
        self.assertTrue(qa.passed)
        self.assertEqual(qa.status, PronunciationStatus.VERIFIED)
        self.assertEqual(len(qa.token_alignments), 1)

    def test_06_cross_chapter_drift_contract(self):
        drift = CrossChapterPronunciationDrift(
            canonical_id="ostrit",
            canonical_text="Ostrit",
            occurrences=[
                {"chapter": 1, "spoken_form": "ओस्ट्रिट", "status": "VERIFIED"},
                {"chapter": 3, "spoken_form": "ऑस्ट्रिट", "status": "LIKELY"},
            ],
            drift_detected=True,
            drift_details=["Spoken form drifted from 'ओस्ट्रिट' (ch 1) to 'ऑस्ट्रिट' (ch 3)"],
        )
        self.assertTrue(drift.drift_detected)
        self.assertEqual(len(drift.drift_details), 1)


if __name__ == "__main__":
    unittest.main()
