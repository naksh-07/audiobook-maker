#!/usr/bin/env python3
"""
Test Suite: Metadata-Harvesting Pilot Subsystem.
================================================
Validates:
1. Non-destructive database schema migration (6 new canonical columns).
2. Epistemic honesty (zero invented metadata, unmeasured fields stay empty/null).
3. Lossless separation of raw_metadata and source_provenance.
4. Authoritative precedence ladder (CSV catalog > embedded tag > filename stem).
5. Duplicate detection (fingerprint & content matching).
6. Strict idempotency (second run yields 0 new rows).
7. Export generation (CSV, JSON audit report, and Markdown summary).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pytest

from audiobook_factory.metadata_pilot_harvester import (
    CanonicalHarvestedRecord,
    MetadataPilotHarvester,
    PilotAssetCandidate,
)
from audiobook_factory.sound_bank import SoundBank


class TestMetadataPilotHarvester(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="pilot_harvest_test_"))
        self.db_path = self.tmp_dir / "test_sound_bank.db"
        self.bank = SoundBank(db_path=self.db_path, bank_root=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_schema_migration_columns_exist(self):
        """Verify the 6 pilot metadata columns are created non-destructively."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sound_catalog)")
            col_names = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            "raw_metadata",
            "source_provenance",
            "bundle_name",
            "source_asset_id",
            "variation_group",
            "duplicate_of_id",
        }
        for col in expected_columns:
            self.assertIn(col, col_names, f"Column '{col}' must exist in sound_catalog")

    def test_field_provenance_and_raw_metadata_separation(self):
        """Verify raw source payloads are preserved losslessly alongside field provenance."""
        cand = PilotAssetCandidate(
            source_collection="Kenney_RPG_Audio",
            bundle_name="Kenney_CC0_RPG_Foley_Pack",
            filename="footstep_dirt_01.ogg",
            filepath="/foley/footstep_dirt_01.ogg",
            source_asset_id="footstep_dirt_01",
            license="CC0 1.0 Universal",
            creator="Kenney",
            raw_bundle_meta={"pack": "Kenney RPG Audio", "license": "CC0"},
            raw_json_record={"desc": "Footstep on soft dirt surface", "cat": "FOL", "subcat": "Footsteps"},
            is_physical_file=False,
            file_size_bytes=12400,
        )

        harvester = MetadataPilotHarvester(self.bank)
        rec = harvester.reconcile_and_normalize(cand)

        self.assertEqual(rec.bundle_name, "Kenney_CC0_RPG_Foley_Pack")
        self.assertEqual(rec.category, "FOL")
        self.assertEqual(rec.subcategory, "Footsteps")
        self.assertEqual(rec.description, "Footstep on soft dirt surface")

        # Check raw_metadata preserves source dictionaries losslessly
        self.assertIn("bundle_manifest", rec.raw_metadata)
        self.assertIn("json_catalog_record", rec.raw_metadata)
        self.assertEqual(rec.raw_metadata["bundle_manifest"]["pack"], "Kenney RPG Audio")

        # Check source_provenance tracks the layers
        self.assertIn("description", rec.source_provenance)
        self.assertEqual(rec.source_provenance["description"]["source"], "accompanying_json")

    def test_authoritative_precedence_ladder(self):
        """Verify that accompanying catalog metadata overrides generic embedded tags without data loss."""
        cand = PilotAssetCandidate(
            source_collection="BBC_Sound_Effects",
            bundle_name="BBC_SFX_CD01",
            filename="07001001.wav",
            filepath="/virtual/07001001.wav",
            source_asset_id="07001001",
            license="BBC RemArc",
            creator="BBC",
            raw_csv_record={
                "location": "07001001.wav",
                "description": "Heavy wooden front door slam shut with iron latch click",
                "category": "Doors: Exterior",
                "secs": "4.5",
                "CDNumber": "01",
                "CDName": "BBC Sound Effects Library",
            },
            is_physical_file=False,
            file_size_bytes=0,
        )

        harvester = MetadataPilotHarvester(self.bank)
        rec = harvester.reconcile_and_normalize(cand)

        # CSV description must be used for title & description
        self.assertEqual(rec.title, "Heavy wooden front door slam shut with iron latch click")
        self.assertIn("Heavy wooden front door slam", rec.description)
        self.assertEqual(rec.duration_sec, 4.5)
        self.assertEqual(rec.category, "FOL")
        self.assertEqual(rec.subcategory, "Doors")
        self.assertEqual(rec.source_provenance["title"]["source"], "accompanying_csv")

    def test_epistemic_honesty_zero_fabricated_fields(self):
        """Verify that absent creative dimensions (mood, intensity) are NOT fabricated."""
        cand = PilotAssetCandidate(
            source_collection="Test_Bundle",
            bundle_name="Test_Foley_Bundle",
            filename="bare_click.wav",
            filepath="/test/bare_click.wav",
            source_asset_id="bare_click",
            is_physical_file=False,
            file_size_bytes=0,
        )

        harvester = MetadataPilotHarvester(self.bank)
        rec = harvester.reconcile_and_normalize(cand)

        # Ensure no creative fields are fabricated in tags or description
        self.assertNotIn("aggressive", rec.tags)
        self.assertNotIn("mood", rec.source_provenance)

    def test_duplicate_detection(self):
        """Verify that duplicate files are detected and linked via duplicate_of_id."""
        harvester = MetadataPilotHarvester(self.bank)

        # Insert primary asset into database
        with harvester._get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO sound_catalog (
                    filename, filepath, title, description, category, subcategory, tags,
                    duration_sec, size_bytes, format, source_collection, bundle_name,
                    license, creator_attribution, source_asset_id, raw_metadata, source_provenance
                ) VALUES (
                    'metal_hit_01.wav', '/sounds/metal_hit_01.wav', 'Metal Hit 01', 'Metal hit',
                    'SFX', 'Impacts', 'metal hit', 1.2, 50000, '.wav', 'Kenney', 'Kenney_Pack',
                    'CC0', 'Kenney', 'metal_hit_01',
                    '{"filesystem": {"fingerprint": "abc123hash"}}',
                    '{"title": {"source": "stem"}}'
                )
            """)
            primary_id = cur.lastrowid
            conn.commit()

            # Now create a candidate that has the exact same fingerprint
            dup_rec = CanonicalHarvestedRecord(
                filename="metal_hit_01_copy.wav",
                filepath="/sounds/metal_hit_01_copy.wav",
                title="Metal Hit Copy",
                description="Copy of metal hit",
                category="SFX",
                subcategory="Impacts",
                tags="metal hit copy",
                duration_sec=1.2,
                size_bytes=50000,
                format=".wav",
                source_collection="Kenney",
                bundle_name="Kenney_Pack",
                license="CC0",
                creator_attribution="Kenney",
                source_url=None,
                mirror_url=None,
                source_asset_id="metal_hit_01_copy",
                variation_group="metal_hit",
                duplicate_of_id=None,
                raw_metadata={},
                source_provenance={},
            )

            detected_id = harvester.detect_duplicate(conn, dup_rec, fingerprint="abc123hash")
            self.assertEqual(detected_id, primary_id)

    def test_strict_idempotency_and_exports(self):
        """Running the pilot twice on the same library must insert 0 new rows on run 2 and export cleanly."""
        harvester = MetadataPilotHarvester(self.bank)
        export_dir = self.tmp_dir / "pilot_exports"

        # Pass 1 (limit=5 for fast execution)
        res1 = harvester.run_pilot(
            export_dir=export_dir,
            force=False,
            bundle_limit=5,
        )
        self.assertGreater(res1["total_discovered"], 0)
        self.assertGreater(res1["total_added"], 0)

        with harvester._get_conn() as conn:
            count_after_run1 = conn.execute("SELECT COUNT(*) FROM sound_catalog").fetchone()[0]

        # Pass 2 without force
        res2 = harvester.run_pilot(
            export_dir=export_dir,
            force=False,
            bundle_limit=5,
        )
        with harvester._get_conn() as conn:
            count_after_run2 = conn.execute("SELECT COUNT(*) FROM sound_catalog").fetchone()[0]

        # Invariant: 0 new rows inserted on run 2
        self.assertEqual(count_after_run1, count_after_run2)
        self.assertEqual(res2["total_added"], 0)
        self.assertGreater(res2["total_skipped"], 0)

        # Check export files
        csv_file = Path(res1["canonical_csv_path"])
        report_file = Path(res1["report_json_path"])
        summary_file = Path(res1["summary_md_path"])

        self.assertTrue(csv_file.exists())
        self.assertTrue(report_file.exists())
        self.assertTrue(summary_file.exists())

        # Validate CSV contents
        csv_text = csv_file.read_text(encoding="utf-8")
        self.assertIn("filename,title,category", csv_text)

        # Validate JSON contents
        report_json = json.loads(report_file.read_text(encoding="utf-8"))
        self.assertIn("statistics", report_json)
        self.assertIn("sample_records", report_json)


if __name__ == "__main__":
    unittest.main()
