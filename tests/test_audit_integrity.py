#!/usr/bin/env python3
"""
Comprehensive Audit & System Integrity Test Suite for Audiobook Factory.
Verifies all modules, imports, database schemas, and CLI subcommands.
"""

import sys
import unittest
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

import audiobook_factory
from audiobook_factory import (
    process_book_file,
    translate_book_project,
    generate_project_scripts,
    TTSDispatcher,
    detect_chapter_mood,
    generate_procedural_ambient_bed,
    resolve_ambient_score,
    generate_chapter_soundscape_plan,
    render_chapter_soundscape,
    generate_project_soundscapes,
    concatenate_and_master_chapter,
    package_m4b_audiobook,
    SoundBank,
)


class TestAudiobookAudit(unittest.TestCase):

    def test_01_core_exports(self):
        """Verify all core factory APIs are present and callable."""
        for fn in [
            process_book_file,
            translate_book_project,
            generate_project_scripts,
            detect_chapter_mood,
            generate_procedural_ambient_bed,
            resolve_ambient_score,
            generate_chapter_soundscape_plan,
            render_chapter_soundscape,
            generate_project_soundscapes,
            concatenate_and_master_chapter,
            package_m4b_audiobook,
        ]:
            self.assertTrue(callable(fn), f"{fn} is not callable")

    def test_02_sound_bank_fts5(self):
        """Verify SoundBank SQLite FTS5 database operations, indexing, and search."""
        bank = SoundBank()
        stats = bank.stats()
        self.assertGreaterEqual(stats["total_sounds"], 6)
        self.assertIn("database_path", stats)

        # Keyword search test
        results = bank.search("mysterious", limit=3)
        self.assertGreater(len(results), 0)
        first = results[0]
        self.assertIn("filepath", first)
        self.assertIn("filename", first)

    def test_03_sfx_resolution(self):
        """Verify procedural SFX synthesis fallback."""
        from audiobook_factory.soundscape import resolve_sfx_cue
        test_out = WORKSPACE_DIR / "audiobooks" / "soundscapes" / "sfx" / "test_heartbeat.wav"
        resolved = resolve_sfx_cue("heartbeat", test_out, duration_sec=1.0)
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.exists())
        if test_out.exists():
            test_out.unlink()

    def test_04_soundscape_plan_schema(self):
        """Verify fallback soundscape plan schema has valid keys."""
        plan = generate_chapter_soundscape_plan("", [])
        self.assertIn("primary_mood", plan)
        self.assertIn("ducking_attenuation_db", plan)
        self.assertIn("scenes", plan)
        self.assertIn("sfx_cues", plan)


if __name__ == "__main__":
    unittest.main(verbosity=2)
