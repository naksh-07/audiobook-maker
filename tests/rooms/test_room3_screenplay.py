#!/usr/bin/env python3
"""
Unit tests for Room 3 Screenplay & Anti-Swap Dramaturgy Engine.
Standard: v6.0-ENTERPRISE-DAG
"""

from pathlib import Path
import pytest

from audiobook_factory.contracts.lore import CastLock, CharacterDossier
from audiobook_factory.contracts.screenplay import ScreenplayScript, ScreenplaySegment, SegmentProvenance
from audiobook_factory.contracts.translation import TranslatedSentenceRecord, TranslationBeatRecord, TranslationManifest
from audiobook_factory.contracts.ledger import ProjectMetadataRecord
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.rooms.room3_screenplay.dramaturge import ScreenplayDramaturge


class TestRoom3Screenplay:
    def test_screenplay_dramaturge_end_to_end(self, tmp_path: Path):
        ledger = PipelineLedger(db_path=tmp_path / "test_ledger.db")
        proj_dir = tmp_path / "project"

        ledger.upsert_project(ProjectMetadataRecord(
            project_id="test_book",
            source_file_path=str(tmp_path / "source.txt"),
            title="Test Book",
            author="Author",
            book_bible_path=str(proj_dir / "book_bible.json"),
            cast_lock_path=str(proj_dir / "cast_lock.json"),
        ))

        dramaturge = ScreenplayDramaturge(project_dir=proj_dir, ledger=ledger)

        # Setup translation manifest
        manifest = TranslationManifest(
            chapter_id=1,
            source_hash="sha256_src_dummy",
            translation_mode="RAW_UNRATED",
            beats=[
                TranslationBeatRecord(
                    beat_uid="ch01_beat001",
                    narrative_function="DIALOGUE_INTERACTION",
                    sentences=[
                        TranslatedSentenceRecord(
                            sentence_id="ch01_s001",
                            source_text="Geralt: 'I know who you are.'",
                            translated_text="गेराल्ट: 'मैं जानता हूँ तुम कौन हो।'"
                        ),
                        TranslatedSentenceRecord(
                            sentence_id="ch01_s002",
                            source_text="The fireplace crackled loudly.",
                            translated_text="अंगीठी में आग ज़ोर से जल रही थी।"
                        ),
                    ]
                )
            ]
        )

        cast_lock = CastLock(
            project_id="test_book",
            narrator_voice_id="Aoede",
            narrator_temperature=0.32,
            cast_assignments={
                "गेराल्ट": CharacterDossier(
                    character_name="Geralt",
                    canonical_hindi_name="गेराल्ट",
                    gender="MALE",
                    suggested_voice_id="Charon",
                    pitch_offset=-4.0,
                    tempo_multiplier=0.95
                )
            }
        )

        script, gate_audit = dramaturge.build_screenplay(
            manifest=manifest,
            cast_lock=cast_lock,
            project_id="test_book",
        )

        assert script.chapter_id == 1
        assert len(script.segments) == 2
        assert gate_audit.decision == "PASSED"
        assert gate_audit.gate_name == "GATE_2_0_SCREENPLAY"

        # Check dialogue attribution & formants
        seg0 = script.segments[0]
        assert seg0.speaker == "गेराल्ट"
        assert seg0.voice_id == "Charon"
        assert seg0.pitch_shift == -4.0
        assert seg0.temperature == 0.38
        assert "मैं जानता हूँ तुम कौन हो।" in seg0.text

        # Check narrator segment
        seg1 = script.segments[1]
        assert seg1.speaker == "Narrator"
        assert seg1.voice_id == "Aoede"
        assert seg1.temperature == 0.32
        assert seg1.acting_instruction == "calm, steady, articulate, measured audiobook delivery"

        # Verify reconciliation and user lock preservation
        locked_seg = seg0.model_copy(
            update={
                "text": "मैनें तुम्हें पहले भी देखा है।",
                "provenance": seg0.provenance.model_copy(update={"user_locked": True}),
            }
        )
        script.segments[0] = locked_seg

        reconciled = dramaturge.reconcile_screenplay(
            existing_script=script,
            new_manifest=manifest,
            cast_lock=cast_lock,
        )

        assert reconciled.segments[0].text == "मैनें तुम्हें पहले भी देखा है।"
        assert reconciled.segments[0].provenance.user_locked is True
