#!/usr/bin/env python3
"""
Tests for AudioRealityAuditor (Pillar 4: Millisecond Audio Reality Engine).
========================================================================
Validates:
- Foley duration physics capping (<= 3.5s with trim flag).
- Anti-repetition cooldown (180-second quenching).
- Category isolation (rejection of rogue music files on foley bus).
- Historical/fantasy era filtering (rejection of modern machinery / banned substrings).
- Audit ledger JSON emission and reporting.
"""

import json
import tempfile
from pathlib import Path
import pytest

from audiobook_factory.contracts import CreativeManifest, FoleyCue, AmbienceScene, MusicCue
from audiobook_factory.audio_reality_auditor import AudioRealityAuditor, AudioRealityReport


def test_foley_duration_capping_and_trimming():
    """Verifies that foley cues with duration > 3.5s are clamped to 3.5s."""
    auditor = AudioRealityAuditor()

    manifest = CreativeManifest(
        chapter_id="chap_test_01",
        foley_cues=[
            FoleyCue(
                cue_id="fc_001",
                segment_index=1,
                anchor_word="तलवार",
                asset_path="sfx/sword_clash.wav",
                start_ms=1000,
                duration_ms=6000,  # 6.0 seconds - exceeds 3.5s cap
            )
        ],
        ambience_scenes=[],
        music_cues=[],
    )

    with tempfile.TemporaryDirectory() as td:
        sanitized_manifest, report = auditor.audit_and_remediate(
            manifest,
            output_dir=Path(td),
            era="MEDIEVAL_FANTASY",
        )

        assert report.total_cues_inspected == 1
        assert report.remediated_count == 1
        assert report.rejected_count == 0
        assert report.passed_count == 0

        # Clamped to 3500ms
        assert len(sanitized_manifest.foley_cues) == 1
        assert sanitized_manifest.foley_cues[0].duration_ms == 3500
        assert report.cues[0].was_trimmed is True
        assert report.cues[0].effective_duration_sec == 3.5


def test_anti_repetition_cooldown():
    """Verifies that identical foley assets within 180s (180000ms) cooldown are purged."""
    auditor = AudioRealityAuditor()

    manifest = CreativeManifest(
        chapter_id="chap_test_02",
        foley_cues=[
            FoleyCue(cue_id="fc_01", segment_index=1, anchor_word="दरवाजा", asset_path="sfx/tavern_door.wav", start_ms=10000, duration_ms=2000),
            # Repeat at 40s (within 180s cooldown) -> should be rejected
            FoleyCue(cue_id="fc_02", segment_index=3, anchor_word="दरवाजा", asset_path="sfx/tavern_door.wav", start_ms=40000, duration_ms=2000),
            # Repeat at 210s (> 180s after first occurrence) -> should be allowed
            FoleyCue(cue_id="fc_03", segment_index=15, anchor_word="दरवाजा", asset_path="sfx/tavern_door.wav", start_ms=210000, duration_ms=2000),
        ],
        ambience_scenes=[],
        music_cues=[],
    )

    with tempfile.TemporaryDirectory() as td:
        sanitized, report = auditor.audit_and_remediate(
            manifest,
            output_dir=Path(td),
            era="MEDIEVAL_FANTASY",
        )

        assert report.total_cues_inspected == 3
        assert report.rejected_count == 1  # fc_02 rejected
        assert len(sanitized.foley_cues) == 2
        assert [c.cue_id for c in sanitized.foley_cues] == ["fc_01", "fc_03"]


def test_category_isolation_rejects_rogue_music_on_foley_bus():
    """Verifies that music tracks accidentally assigned to foley bus are blocked."""
    auditor = AudioRealityAuditor()

    manifest = CreativeManifest(
        chapter_id="chap_test_03",
        foley_cues=[
            # Rogue music path
            FoleyCue(cue_id="fc_bad_01", segment_index=1, anchor_word="संगीत", asset_path="audiobooks/sound_bank/music/004 The Fortress of Memory.mp3", start_ms=5000, duration_ms=2000),
            # Normal sound effect
            FoleyCue(cue_id="fc_good_01", segment_index=2, anchor_word="म्यान", asset_path="audiobooks/sound_bank/sfx/cs202_holster_sword.wav", start_ms=8000, duration_ms=1500),
        ],
        ambience_scenes=[],
        music_cues=[],
    )

    with tempfile.TemporaryDirectory() as td:
        sanitized, report = auditor.audit_and_remediate(
            manifest,
            output_dir=Path(td),
            era="MEDIEVAL_FANTASY",
        )

        assert report.rejected_count == 1
        assert len(sanitized.foley_cues) == 1
        assert sanitized.foley_cues[0].cue_id == "fc_good_01"


def test_era_negative_keyword_rejection():
    """Verifies that modern/anachronistic assets are banned in medieval fantasy stories."""
    auditor = AudioRealityAuditor()

    manifest = CreativeManifest(
        chapter_id="chap_test_04",
        foley_cues=[
            FoleyCue(cue_id="fc_modern_01", segment_index=1, anchor_word="कदम", asset_path="sfx/07018159_soldiers_shambling_on_gravel.mp3", start_ms=2000, duration_ms=2500),
            FoleyCue(cue_id="fc_modern_02", segment_index=2, anchor_word="पत्थर", asset_path="sfx/stone_grader_machine.wav", start_ms=10000, duration_ms=3000),
            FoleyCue(cue_id="fc_valid_01", segment_index=3, anchor_word="कवच", asset_path="sfx/leather_armor_movement.wav", start_ms=15000, duration_ms=1200),
        ],
        ambience_scenes=[],
        music_cues=[],
    )

    with tempfile.TemporaryDirectory() as td:
        sanitized, report = auditor.audit_and_remediate(
            manifest,
            output_dir=Path(td),
            era="MEDIEVAL_FANTASY",
        )

        assert report.rejected_count == 2
        assert len(sanitized.foley_cues) == 1
        assert sanitized.foley_cues[0].cue_id == "fc_valid_01"


def test_audit_ledger_json_written():
    """Verifies that chapter_XXX_audio_reality_ledger.json is persisted to output_dir."""
    auditor = AudioRealityAuditor()

    manifest = CreativeManifest(
        chapter_id="chapter_002",
        foley_cues=[
            FoleyCue(cue_id="fc_01", segment_index=1, anchor_word="वार", asset_path="sfx/sword_swing.wav", start_ms=3000, duration_ms=1500)
        ],
        ambience_scenes=[],
        music_cues=[],
    )

    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td)
        _, report = auditor.audit_and_remediate(
            manifest,
            output_dir=out_path,
            era="MEDIEVAL_FANTASY",
        )

        ledger_file = out_path / "chapter_002_audio_reality_ledger.json"
        assert ledger_file.exists()

        data = json.loads(ledger_file.read_text(encoding="utf-8"))
        assert data["chapter_id"] == "chapter_002"
        assert data["total_cues_inspected"] == 1
        assert data["passed_count"] == 1
