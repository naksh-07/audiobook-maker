#!/usr/bin/env python3
"""
End-to-End Automated Test Suite for Audiobook Studio Modular CLI.
Standard: v6.0-ENTERPRISE-DAG
"""

import json
from pathlib import Path
import pytest

from audiobook_factory.cli.main import main


class TestCLICommands:
    def test_cli_help_and_version(self, capsys):
        # Test --help
        code = main(["--help"])
        assert code == 0
        captured = capsys.readouterr()
        assert "audiobook-studio" in captured.out
        assert "ingest" in captured.out
        assert "doctor" in captured.out

        # Test no args
        code = main([])
        assert code == 0

    def test_doctor_cli(self, capsys):
        # Text format
        code = main(["doctor"])
        assert code == 0
        out = capsys.readouterr().out
        assert "Audiobook Studio System Diagnostic Doctor" in out
        assert "FFmpeg" in out

        # JSON format
        code = main(["doctor", "--json"])
        assert code == 0
        out_json = capsys.readouterr().out
        data = json.loads(out_json)
        assert "ffmpeg" in data
        assert "keypool" in data
        assert "ledger" in data

    def test_full_pipeline_cli_lifecycle(self, tmp_path: Path, capsys):
        proj_dir = tmp_path / "cli_test_book"
        source_file = tmp_path / "sample_source.txt"
        source_file.write_text(
            "# Chapter 1: The Gathering\n\n"
            "Geralt walked through the dense woods.\n"
            "Yennefer cast a spell into the dark night sky.\n"
            "'We must hasten,' whispered the sorceress.\n"
            "The wind howled through the ancient trees.\n",
            encoding="utf-8"
        )

        # 1. Ingest CLI
        code_ingest = main([
            "ingest",
            str(source_file),
            "--project-id", "cli_test_book",
            "--title", "CLI Test Book",
            "--author", "Sapkowski",
            "--fidelity", "RAW_UNRATED",
            "--project-dir", str(proj_dir),
        ])
        assert code_ingest == 0
        assert (proj_dir / "raw_book_manifest.json").exists()
        assert (proj_dir / "book_bible.json").exists()
        assert (proj_dir / "cast_lock.json").exists()
        assert (proj_dir / "pipeline_ledger.db").exists()

        # 2. Translate CLI
        code_trans = main([
            "translate",
            str(proj_dir),
            "--chapter", "1",
            "--mode", "RAW_UNRATED",
        ])
        assert code_trans == 0
        assert (proj_dir / "chapter_001_translation.json").exists()

        # 2b. Translate CLI Beat Patching
        patch_json = json.dumps([
            {"translated_text": "गेराल्ट घने जंगलों से होकर आगे बढ़ा।"},
            {"translated_text": "येनेफर ने अंधेरी रात के आसमान में जादू फूंका।"},
            {"translated_text": "'हमें जल्दी करनी होगी,' जादूगरनी ने फुसफुसाया।"},
            {"translated_text": "प्राचीन पेड़ों के बीच से तेज़ हवाएं सनसना रही थीं।"},
        ])
        code_patch = main([
            "translate",
            str(proj_dir),
            "--chapter", "1",
            "--patch-beat", "ch01_beat001",
            "--patch-json", patch_json,
        ])
        assert code_patch == 0

        # 3. Screenplay CLI
        code_screenplay = main([
            "screenplay",
            str(proj_dir),
            "--chapter", "1",
        ])
        assert code_screenplay == 0
        assert (proj_dir / "chapter_001_screenplay.json").exists()

        # 3b. Screenplay CLI Reconcile
        code_reconcile = main([
            "screenplay",
            str(proj_dir),
            "--chapter", "1",
            "--reconcile",
        ])
        assert code_reconcile == 0

        # 4. Synth CLI
        code_synth = main([
            "synth",
            str(proj_dir),
            "--chapter", "1",
            "--workers", "2",
        ])
        assert code_synth == 0
        assert (proj_dir / "chapter_001_dialogue.wav").exists()

        # 5. Master CLI
        code_master = main([
            "master",
            str(proj_dir),
            "--chapter", "1",
            "--target-lufs", "-19.0",
        ])
        assert code_master == 0
        assert (proj_dir / "chapter_001_mastered.m4a").exists()

        # 6. Package CLI
        code_package = main([
            "package",
            str(proj_dir),
            "--title", "Final CLI Masterpiece",
            "--author", "Sapkowski",
        ])
        assert code_package == 0
        assert (proj_dir / "cli_test_book.m4b").exists()
