#!/usr/bin/env python3
"""
Unit tests for Room 2 Translation Collective Engine.
Standard: v6.0-ENTERPRISE-DAG
"""

from pathlib import Path
import pytest

from audiobook_factory.contracts.ingestion import RawChapterRecord, RawSentenceRecord
from audiobook_factory.contracts.lore import BookBible, CharacterDossier
from audiobook_factory.contracts.ledger import ProjectMetadataRecord
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.rooms.room2_translate.collective import TranslationCollective


class TestRoom2Translate:
    def test_translation_collective_end_to_end(self, tmp_path: Path):
        ledger = PipelineLedger(db_path=tmp_path / "test_ledger.db")
        proj_dir = tmp_path / "project"
        
        # Register project in ledger
        ledger.upsert_project(ProjectMetadataRecord(
            project_id="test_book",
            source_file_path=str(tmp_path / "source.txt"),
            title="Test Book",
            author="Author",
            book_bible_path=str(proj_dir / "book_bible.json"),
            cast_lock_path=str(proj_dir / "cast_lock.json"),
        ))

        collective = TranslationCollective(project_dir=proj_dir, ledger=ledger)

        # Setup chapter sentences
        chapter = RawChapterRecord(
            chapter_id=1,
            title="Chapter 1",
            source_hash="sha256_dummy_hash",
            sentences=[
                RawSentenceRecord(sentence_id="ch01_s001", text="Geralt drew his silver sword.", source_char_offset=0),
                RawSentenceRecord(sentence_id="ch01_s002", text="Yennefer looked at him with cold eyes.", source_char_offset=30),
                RawSentenceRecord(sentence_id="ch01_s003", text="'We have work to do,' she said.", source_char_offset=68),
                RawSentenceRecord(sentence_id="ch01_s004", text="The night was dark and full of shadows.", source_char_offset=100),
            ]
        )

        bible = BookBible(
            book_id="test_book",
            literary_tradition="DARK_FANTASY",
            fidelity_tier="RAW_UNRATED",
            terminology_map={
                "Geralt": "गेराल्ट",
                "Yennefer": "येनेफर",
            },
            characters={
                "Geralt": CharacterDossier(
                    character_name="Geralt",
                    canonical_hindi_name="गेराल्ट",
                    gender="MALE",
                    suggested_voice_id="Charon"
                ),
            }
        )

        manifest, gate_audit = collective.translate_chapter(
            chapter=chapter,
            bible=bible,
            mode="RAW_UNRATED",
            project_id="test_book",
        )

        assert manifest.chapter_id == 1
        assert len(manifest.beats) == 1
        assert len(manifest.beats[0].sentences) == 4
        assert gate_audit.decision == "PASSED"
        assert gate_audit.gate_name == "GATE_1_0_TRANSLATION"

        # Verify terminology substitution
        s1 = manifest.beats[0].sentences[0]
        assert "गेराल्ट" in s1.translated_text

        # Verify SQLite ledger state
        stage = ledger.get_stage("ch001_room2_translate")
        assert stage is not None
        assert stage.status == "COMPLETED"

        # Verify surgical beat patching
        beat_uid = manifest.beats[0].beat_uid
        patched_manifest = collective.patch_beat(
            chapter_id=1,
            beat_uid=beat_uid,
            patched_sentences=[
                {"translated_text": "गेराल्ट ने अपनी चांदी की तलवार निकाली।"},
                {"translated_text": "येनेफर ने उसकी तरफ ठंडी नज़रों से देखा।"},
                {"translated_text": "'हमें काम पूरा करना है,' उसने कहा।"},
                {"translated_text": "रात घनी और सायों से भरी थी।"},
            ],
            project_id="test_book",
        )

        assert patched_manifest.beats[0].sentences[0].translated_text == "गेराल्ट ने अपनी चांदी की तलवार निकाली।"
        assert patched_manifest.beats[0].sentences[0].user_override is True
