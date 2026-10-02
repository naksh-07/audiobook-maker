#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.storage import (
    IStorageBackend,
    LocalStorageBackend,
    get_default_storage,
)


class TestStorageBackend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backend = LocalStorageBackend(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_protocol_conformance(self):
        self.assertIsInstance(self.backend, IStorageBackend)

    def test_write_and_read_bytes(self):
        content = b"Studio Master Audio Stem Header"
        saved_path = self.backend.write_bytes("chapters/c01.wav", content)
        self.assertTrue(Path(saved_path).exists())
        self.assertTrue(self.backend.exists("chapters/c01.wav"))

        retrieved = self.backend.read_bytes("chapters/c01.wav")
        self.assertEqual(retrieved, content)

    def test_path_traversal_protection(self):
        with self.assertRaises(ValueError):
            self.backend.write_bytes("../../../evil.exe", b"bad")

    def test_list_and_delete(self):
        self.backend.write_bytes("c01/foley.wav", b"click")
        self.backend.write_bytes("c01/music.wav", b"melody")
        self.backend.write_bytes("c02/foley.wav", b"footstep")

        c01_keys = self.backend.list_keys(prefix="c01")
        self.assertEqual(len(c01_keys), 2)
        self.assertIn("c01/foley.wav", c01_keys)

        deleted = self.backend.delete("c01/foley.wav")
        self.assertTrue(deleted)
        self.assertFalse(self.backend.exists("c01/foley.wav"))


if __name__ == "__main__":
    unittest.main()
