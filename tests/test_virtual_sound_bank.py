#!/usr/bin/env python3
"""
Unit tests for Virtual Sound Catalog, Cloud Seeder, and JIT Downloader.
All network requests are mocked for instant 100% offline test execution.
"""

import json
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.catalog_seeder import seed_virtual_sound_catalog


class TestVirtualSoundBank(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.bank_root = Path(self.temp_dir)
        self.db_path = self.bank_root / "test_sound_bank.db"
        self.bank = SoundBank(db_path=self.db_path, bank_root=self.bank_root)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_virtual_columns_exist(self):
        with self.bank._get_conn() as conn:
            cols = [c[1] for c in conn.execute("PRAGMA table_info(sound_catalog)").fetchall()]
            self.assertIn("source_url", cols)
            self.assertIn("is_downloaded", cols)

    @patch("urllib.request.urlopen")
    def test_virtual_seeding_mocked(self, mock_urlopen):
        # Mock GitHub API response for Kenney assets
        mock_github_items = [
            {"name": "test_sword_draw.ogg", "type": "file", "size": 12000, "download_url": "https://example.com/test_sword.ogg"},
            {"name": "test_spell_zap.ogg", "type": "file", "size": 18000, "download_url": "https://example.com/test_spell.ogg"},
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_github_items).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # Seed into temporary bank
        stats = seed_virtual_sound_catalog(self.bank)
        self.assertGreater(stats["total_virtual"], 0)

        # Verify FTS search finds virtual assets
        results = self.bank.search("thunder rain", limit=3)
        self.assertGreater(len(results), 0)
        self.assertIn("source_url", results[0])
        self.assertEqual(results[0]["is_downloaded"], 0)

    @patch("urllib.request.urlopen")
    def test_jit_download(self, mock_urlopen):
        # Mock HTTP response for audio download (must return b"" on second call for copyfileobj)
        mock_resp = MagicMock()
        mock_resp.read.side_effect = [b"MOCK_OGG_AUDIO_BYTES_TEST", b""]
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # Insert a dummy virtual sound
        with self.bank._get_conn() as conn:
            conn.execute("""
                INSERT INTO sound_catalog
                (filename, filepath, category, subcategory, mood, tags, duration_sec, size_bytes, format, source_url, is_downloaded)
                VALUES ('virtual_dagger.ogg', 'virtual/test/virtual_dagger.ogg', 'FOL', 'Combat', 'tense', 'dagger blade test', 1.5, 0, '.ogg', 'https://example.com/virtual_dagger.ogg', 0)
            """)

        # Call resolve_sound which should trigger JIT download
        resolved = self.bank.resolve_sound("virtual_dagger")
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.exists())

        # Verify database was updated to is_downloaded = 1
        with self.bank._get_conn() as conn:
            row = conn.execute("SELECT is_downloaded, filepath FROM sound_catalog WHERE filename = 'virtual_dagger.ogg'").fetchone()
            self.assertEqual(row["is_downloaded"], 1)
            self.assertIn("cache", row["filepath"])


if __name__ == "__main__":
    unittest.main()
