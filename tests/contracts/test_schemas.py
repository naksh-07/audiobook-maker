#!/usr/bin/env python3
"""
Unit tests for v6.0-ENTERPRISE-DAG Pydantic v2 Contracts & Schemas.
Tests strict typing, fail-closed validation, and deterministic SHA-256 serialization.
"""

import pytest
from pydantic import ValidationError

from audiobook_factory.contracts.base import ContractBaseModel
from audiobook_factory.contracts.ingestion import (
    RawBookManifest,
    RawChapterRecord,
    RawSentenceRecord,
)
from audiobook_factory.contracts.lore import (
    BookBible,
    CastLock,
    CharacterDossier,
)
from audiobook_factory.contracts.translation import (
    TranslatedSentenceRecord,
    TranslationBeatRecord,
    TranslationManifest,
)
from audiobook_factory.contracts.screenplay import (
    ScreenplayScript,
    ScreenplaySegment,
    SegmentProvenance,
)
from audiobook_factory.contracts.editorial import (
    ChapterDialogueManifest,
    SegmentTakeMetadata,
    TimelineCueRecord,
    TimelineLedger,
)
from audiobook_factory.contracts.mastering import (
    ChapterMarker,
    ContainerM4BManifest,
    LoudnessComplianceReport,
    MasterArtifact,
)
from audiobook_factory.contracts.ledger import (
    ChapterStageRecord,
    GateAuditRecord,
    ProjectMetadataRecord,
    SegmentTakeCacheRecord,
    StageArtifactRecord,
)


class TestBaseContractModel:
    def test_deterministic_sha256_hashing(self):
        class DummyModel(ContractBaseModel):
            name: str
            count: int
            ratio: float

        m1 = DummyModel(name="test", count=42, ratio=3.14159)
        m2 = DummyModel(name="test", count=42, ratio=3.14159)
        assert m1.compute_sha256_hash() == m2.compute_sha256_hash()
        assert len(m1.compute_sha256_hash()) == 64

    def test_hash_changes_on_data_mutation(self):
        class DummyModel(ContractBaseModel):
            text: str

        m1 = DummyModel(text="Hello world")
        m2 = DummyModel(text="Hello world!")
        assert m1.compute_sha256_hash() != m2.compute_sha256_hash()

    def test_extra_fields_forbidden(self):
        class StrictModel(ContractBaseModel):
            title: str

        with pytest.raises(ValidationError):
            StrictModel(title="Valid", unexpected_key="Not allowed")  # type: ignore


class TestIngestionContracts:
    def test_raw_book_manifest_hierarchy(self):
        sentence = RawSentenceRecord(
            sentence_id="ch01_s01",
            text="The man had no sword, only a leather purse.",
            source_char_offset=0,
            page_number=1,
        )
        chapter = RawChapterRecord(
            chapter_id=1,
            title="The Voice of Reason",
            source_hash="abcd1234efgh5678",
            sentences=[sentence],
        )
        manifest = RawBookManifest(
            book_id="the-last-wish",
            title="The Last Wish",
            author="Andrzej Sapkowski",
            source_file_path="/books/the_last_wish.epub",
            total_chapters=1,
            chapters=[chapter],
        )

        assert manifest.book_id == "the-last-wish"
        assert len(manifest.chapters) == 1
        assert manifest.chapters[0].sentences[0].sentence_id == "ch01_s01"
        assert len(manifest.compute_sha256_hash()) == 64


class TestLoreContracts:
    def test_character_dossier_and_cast_lock(self):
        geralt = CharacterDossier(
            character_name="Geralt",
            canonical_hindi_name="गेराल्ट",
            gender="MALE",
            vocal_weight="GRUFF",
            social_register="ROGUE",
            suggested_voice_id="Charon",
            pitch_offset=-4.0,
            tempo_multiplier=0.95,
            eq_profile_name="LOW_MIDS_WARMTH",
        )
        cast_lock = CastLock(
            project_id="sword-of-destiny",
            narrator_voice_id="Aoede",
            narrator_temperature=0.32,
            cast_assignments={"Geralt": geralt},
        )
        assert cast_lock.cast_assignments["Geralt"].canonical_hindi_name == "गेराल्ट"
        assert cast_lock.cast_assignments["Geralt"].pitch_offset == -4.0

    def test_invalid_gender_rejected(self):
        with pytest.raises(ValidationError):
            CharacterDossier(
                character_name="Monster",
                canonical_hindi_name="राक्षस",
                gender="ALIEN",  # type: ignore
                suggested_voice_id="Puck",
            )


class TestTranslationContracts:
    def test_translation_manifest(self):
        sent = TranslatedSentenceRecord(
            sentence_id="ch03_s01",
            source_text="Geralt turned slowly.",
            translated_text="गेराल्ट धीरे से मुड़ा।",
            terminology_hash="hash123",
            confidence_score=0.98,
        )
        beat = TranslationBeatRecord(
            beat_uid="ch03_beat001",
            narrative_function="VISCERAL_COMBAT",
            sentences=[sent],
        )
        manifest = TranslationManifest(
            chapter_id=3,
            source_hash="source_hash_999",
            translation_mode="RAW_UNRATED",
            beats=[beat],
        )
        assert manifest.chapter_id == 3
        assert manifest.beats[0].sentences[0].translated_text == "गेराल्ट धीरे से मुड़ा।"


class TestScreenplayContracts:
    def test_screenplay_segment_with_4d_formants(self):
        prov = SegmentProvenance(
            origin="DIRECTOR_LOCK",
            user_locked=True,
            content_hash="segment_hash_456",
        )
        seg = ScreenplaySegment(
            segment_uid="ch03_seg045",
            beat_ref="ch03_beat001",
            speaker="Geralt",
            voice_id="Charon",
            text="यहाँ से चले जाओ, इससे पहले कि देर हो जाए।",
            pitch_shift=-6.0,
            speed_multiplier=0.92,
            temperature=0.38,
            acting_instruction="understated natural dialogue (never theatrical)",
            provenance=prov,
        )
        script = ScreenplayScript(
            chapter_id=3,
            translation_hash="trans_hash_777",
            segments=[seg],
        )
        assert script.segments[0].provenance.user_locked is True
        assert script.segments[0].pitch_shift == -6.0

    def test_temperature_boundary_constraints(self):
        with pytest.raises(ValidationError):
            ScreenplaySegment(
                segment_uid="ch01_s01",
                beat_ref="b01",
                speaker="Narrator",
                voice_id="Aoede",
                text="Test",
                temperature=0.85,  # Exceeds max 0.52
            )


class TestEditorialAndMasteringContracts:
    def test_timeline_ledger_and_dialogue_manifest(self):
        cue = TimelineCueRecord(
            segment_uid="ch03_seg001",
            speaker="Narrator",
            start_time_sec=0.0,
            end_time_sec=4.5,
            fade_in_ms=12.0,
            fade_out_ms=18.0,
            pause_after_sec=0.4,
        )
        ledger = TimelineLedger(
            chapter_id=3,
            total_duration_sec=4.9,
            cues=[cue],
        )
        take = SegmentTakeMetadata(
            segment_uid="ch03_seg001",
            take_content_hash="take_hash_111",
            take_wav_path="/takes/take_hash_111.wav",
            duration_sec=4.5,
            measured_lufs=-19.2,
            was_cache_hit=True,
        )
        manifest = ChapterDialogueManifest(
            chapter_id=3,
            script_hash="script_hash_222",
            lossless_dialogue_wav_path="/mastered/ch03_dialogue.wav",
            timeline_ledger=ledger,
            takes=[take],
        )
        assert manifest.takes[0].was_cache_hit is True
        assert manifest.timeline_ledger.cues[0].fade_in_ms == 12.0

    def test_master_artifact_and_loudness_compliance(self):
        compliance = LoudnessComplianceReport(
            integrated_lufs=-19.1,
            true_peak_dbfs=-2.8,
            loudness_range_lu=5.4,
            threshold_lufs=-70.0,
            is_compliant=True,
        )
        artifact = MasterArtifact(
            chapter_id=3,
            mastered_audio_path="/mastered/ch03_mastered.m4a",
            duration_sec=1124.5,
            compliance=compliance,
        )
        assert artifact.compliance.is_compliant is True
        assert artifact.compliance.integrated_lufs == -19.1


class TestLedgerAndGateContracts:
    def test_stage_record_and_gate_audit(self):
        stage = ChapterStageRecord(
            chapter_stage_uid="ch003_room3_screenplay",
            project_id="sword-of-destiny",
            chapter_id=3,
            room_name="ROOM3_SCREENPLAY",
            input_contract_hash="in_hash_123",
            output_contract_hash="out_hash_456",
            status="COMPLETED",
        )
        gate = GateAuditRecord(
            audit_uid="audit_gate2_ch03",
            chapter_stage_uid="ch003_room3_screenplay",
            gate_name="GATE_2_0_SCREENPLAY",
            decision="PASSED",
            metrics={"speaker_turn_inversions": 0, "quote_leakage_count": 0},
            failure_reasons=[],
        )
        assert stage.status == "COMPLETED"
        assert gate.decision == "PASSED"
        assert gate.metrics["speaker_turn_inversions"] == 0
