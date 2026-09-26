#!/usr/bin/env python3
"""
Test Suite for Sonic Intelligence Catalog & Virtual JIT Sound Bank.
===================================================================
Rigorous verification of:
1. Schema migration, FTS5 sync triggers, and asset relationship indexing.
2. Sonic Genome v2 Pydantic schema validation & measured/inferred knowledge separation.
3. Bounded LRU cache management and active-render eviction protection.
4. Virtual source adapters (Incompetech, BBC SFX, Sonniss GDC, Kenney OGA).
5. Seed compression and offline catalog hydration.
6. Hybrid semantic virtual catalog search with explainable match breakdowns.
7. Compact LLM Agent Sound Card generation.
8. JIT atomic streaming download, mirror fallback, and payload validation.
9. SoundAssetRetriever integration with virtual resolution and render protection.
10. Asset relationship linking (variations, layers, transitions).
"""

import gzip
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audiobook_factory.contracts import (
    SonicGenome,
    PhysicalGenome,
    TemporalWaveGenome,
    SpatialGenome,
    EnvironmentalGenome,
    DramaticGenome,
    MixCompatibilityGenome,
    MusicIntelligence,
    FoleyIntelligence,
    RemoteAssetMetadata,
    AcousticMetrics,
)
from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.sound_bank_cache import SoundBankCacheManager
from audiobook_factory.sound_design.asset_retriever import SoundAssetRetriever
from audiobook_factory.virtual_catalog.incompetech_adapter import IncompetechAdapter
from audiobook_factory.virtual_catalog.bbc_sfx_adapter import BBCSoundEffectsAdapter
from audiobook_factory.virtual_catalog.sonniss_gdc_adapter import SonnissGDCAdapter
from audiobook_factory.virtual_catalog.kenney_oga_adapter import KenneyOGAAdapter
from audiobook_factory.virtual_catalog.seed_generator import generate_seed_file, hydrate_from_seed


# =============================================================================
# 1. Schema Migration & Relational / FTS5 Invariants
# =============================================================================

def test_schema_migration_and_fts5_triggers():
    """Verifies that all 29 fields, FTS5 virtual table, and triggers are created idempotently."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bank_p = Path(tmp_dir)
        bank = SoundBank(bank_root=bank_p)

        # Inspect sound_catalog columns
        with bank._get_conn() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(sound_catalog)").fetchall()}
            expected_cols = {
                "id", "filename", "filepath", "category", "subcategory", "mood", "tags",
                "duration_sec", "size_bytes", "format", "source_url", "is_downloaded",
                "created_at", "title", "description", "source_collection", "license",
                "creator_attribution", "mirror_url", "source_page_url", "url_status",
                "last_verified_at", "tempo_bpm", "key_tonality", "time_signature",
                "wave_style", "temporal_character", "energy_profile", "texture_profile",
                "exciter", "resonator", "action_type", "surface", "perspective",
                "acoustic_space", "reverb_character", "dramatic_role", "foreground_strength",
                "voice_masking_risk", "whisper_compatibility", "last_accessed_at",
                "cache_pin_status", "sonic_genome",
            }
            assert expected_cols.issubset(cols), f"Missing columns: {expected_cols - cols}"

            # Inspect sound_asset_relationships table
            rel_cols = {r[1] for r in conn.execute("PRAGMA table_info(sound_asset_relationships)").fetchall()}
            assert {"id", "source_asset_id", "target_asset_id", "relationship_type"}.issubset(rel_cols)

            # Test FTS5 insertion and sync
            conn.execute("""
                INSERT INTO sound_catalog (filename, filepath, category, title, description, tags, exciter, resonator, action_type, dramatic_role)
                VALUES ('test_foley_clash.ogg', 'path/test_foley_clash.ogg', 'FOL', 'Epic Iron Sword Clash', 'Two swords collide with ringing overtone', 'metal weapon combat', 'iron', 'steel', 'strike', 'combat')
            """)
            row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Verify FTS5 match
            fts_match = conn.execute(
                "SELECT rowid FROM sound_catalog_fts WHERE sound_catalog_fts MATCH 'swords collide'"
            ).fetchone()
            assert fts_match is not None
            assert fts_match[0] == row_id


# =============================================================================
# 2. Sonic Genome v2 Pydantic Validation & Knowledge Classes
# =============================================================================

def test_sonic_genome_v2_pydantic_schema():
    """Verifies that Sonic Genome v2 accurately captures measured DSP, inferred semantic, and curated metadata."""
    genome = SonicGenome(
        version="2.0",
        physical=PhysicalGenome(
            source_object="sword",
            source_material="steel",
            surface_material="hollow_iron",
            action_type="strike",
            confidence=0.88,
        ),
        temporal=TemporalWaveGenome(
            wave_style="transient_percussive",
            attack_ms=4.2,
            decay_ms=380.0,
        ),
        spatial=SpatialGenome(
            room_size="dungeon",
            stereo_width=1.0,
        ),
        environmental=EnvironmentalGenome(
            weather="none",
            environmental_density="sparse",
        ),
        dramatic=DramaticGenome(
            dramatic_role="action_confirmation",
            foreground_strength=0.85,
        ),
        mix=MixCompatibilityGenome(
            voice_masking_risk="LOW",
            whisper_compatibility=0.90,
            recommended_ducking_db=-6.0,
        ),
        remote=RemoteAssetMetadata(
            source_collection="Sonniss_GDC",
            source_url="https://archive.org/download/test/clash.wav",
            mirror_url="https://gamesounds.xyz/test/clash.wav",
            url_status="available",
        ),
    )

    data = genome.model_dump()
    assert data["version"] == "2.0"
    assert data["physical"]["source_material"] == "steel"
    assert data["mix"]["voice_masking_risk"] == "LOW"
    assert data["remote"]["source_collection"] == "Sonniss_GDC"

    # Verify backward compatibility with AcousticMetrics
    assert isinstance(genome.acoustic, AcousticMetrics)
    assert genome.acoustic.true_peak_dbtp == -1.5


# =============================================================================
# 3. Bounded LRU Cache Manager & Active Render Protection
# =============================================================================

def test_cache_manager_lru_and_active_render_protection():
    """Verifies that LRU eviction respects pinned and active-render files, freeing bytes without touching metadata."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        db_path = tmp_p / "test_bank.db"
        cache_dir = tmp_p / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize test database
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE sound_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                filepath TEXT,
                size_bytes INTEGER,
                duration_sec REAL,
                is_downloaded INTEGER,
                last_accessed_at TIMESTAMP,
                cache_pin_status TEXT DEFAULT 'normal'
            );
        """)

        # Create 3 dummy audio files (100KB each)
        file_paths = []
        for i in range(1, 4):
            fp = cache_dir / f"sound_{i}.ogg"
            fp.write_bytes(b"\x00" * (100 * 1024))
            file_paths.append(fp)
            conn.execute(
                "INSERT INTO sound_catalog (id, filename, filepath, size_bytes, duration_sec, is_downloaded, last_accessed_at, cache_pin_status) "
                "VALUES (?, ?, ?, ?, ?, 1, datetime('now', ?), 'normal')",
                (i, fp.name, str(fp).replace("\\", "/"), len(fp.read_bytes()), 2.0, f"-{10 - i} hours")
            )
        conn.commit()
        conn.close()

        # Create cache manager with 0.15 MB budget (enough for ~1.5 files, forcing eviction)
        mgr = SoundBankCacheManager(db_path=db_path, cache_dir=cache_dir, max_cache_mb=0.15)
        stats = mgr.get_cache_stats()
        assert stats["downloaded_files_count"] == 3

        # Protect sound 1 (oldest accessed, but protected via active render)
        with mgr.protect_active_render([1]):
            # Verify sound 1 status changed to active_render
            conn = sqlite3.connect(db_path)
            status_1 = conn.execute("SELECT cache_pin_status FROM sound_catalog WHERE id = 1").fetchone()[0]
            conn.close()
            assert status_1 == "active_render"

            # Prune cache to budget (should evict sound 2 instead of protected sound 1)
            pruned_bytes, pruned_count = mgr.prune_to_budget(target_mb=0.15)
            assert pruned_count >= 1

            # Sound 1 must still exist on disk
            assert file_paths[0].exists()

        # After exiting context manager, sound 1 reverts to normal
        conn = sqlite3.connect(db_path)
        status_1_after = conn.execute("SELECT cache_pin_status FROM sound_catalog WHERE id = 1").fetchone()[0]
        # Sound 2 record in DB should have is_downloaded=0 and filepath=NULL
        row_2 = conn.execute("SELECT is_downloaded, filepath FROM sound_catalog WHERE id = 2").fetchone()
        conn.close()

        assert status_1_after == "normal"
        assert row_2[0] == 0
        assert row_2[1] is None
        assert not file_paths[1].exists()  # Evicted from disk


# =============================================================================
# 4. Virtual Source Adapters & Normalization
# =============================================================================

def test_incompetech_adapter_normalization():
    """Verifies that Incompetech adapter maps pieces into complete Sonic Genome records."""
    adapter = IncompetechAdapter()
    raw_piece = {
        "title": "Prelude and Action",
        "filename": "Prelude and Action.mp3",
        "tempo": "130",
        "feels": ["Epic", "Driving", "Action"],
        "instruments": ["Brass", "Strings", "Percussion"],
        "description": "Driving orchestral adventure soundtrack cue",
        "length": "03:15",
    }

    norm = adapter.normalize_item(raw_piece)
    assert norm is not None
    assert norm["title"] == "Prelude and Action"
    assert norm["category"] == "MUS"
    assert norm["tempo_bpm"] == 130.0
    assert norm["duration_sec"] == 195.0
    assert "https://incompetech.com" in norm["source_url"]
    assert "Incompetech" in norm["source_collection"]
    assert norm["is_downloaded"] == 0

    genome = norm["sonic_genome"] if isinstance(norm["sonic_genome"], dict) else json.loads(norm["sonic_genome"])
    assert genome["music"]["bpm"] == 130.0
    assert "Brass" in genome["music"]["lead_instruments"]


def test_bbc_sfx_adapter_normalization():
    """Verifies that BBC SFX adapter maps categories, exciters, resonators, and stream URLs."""
    adapter = BBCSoundEffectsAdapter()
    raw_row = {
        "CDNumber": "EC01",
        "TrackNumber": "42",
        "CDTitle": "Exterior Atmospheres",
        "TrackTitle": "Heavy rain falling on stone courtyard with distant thunder",
        "Category": "Atmospheres / Weather",
        "Description": "Continuous rainfall on granite paving stones with low rumbles",
        "Duration": "01:45",
        "location": "07042001",
    }

    norm = adapter.normalize_item(raw_row)
    assert norm is not None
    assert norm["category"] == "AMB"
    assert norm["duration_sec"] == 105.0
    assert "BBC" in norm["source_collection"]
    assert norm["exciter"] == "water"
    assert norm["surface"] == "stone"
    assert "bbcrewind.co.uk" in norm["source_url"]


def test_sonniss_and_kenney_adapters_normalization():
    """Verifies Sonniss GDC and Kenney OGA adapters produce clean metadata records."""
    sonniss = SonnissGDCAdapter()
    raw_s = {
        "filename": "Impact_Sword_Armor_Heavy_01.wav",
        "category": "FOL",
        "subcategory": "Combat",
        "exciter": "steel",
        "surface": "metal",
        "action": "strike",
        "duration_sec": 1.2,
        "archive_id": "SonnissGameAudioGDCPack1",
    }
    norm_s = sonniss.normalize_item(raw_s)
    assert norm_s["category"] == "FOL"
    assert "Sonniss" in norm_s["license"]
    assert "archive.org" in norm_s["source_url"]

    kenney = KenneyOGAAdapter()
    raw_k = {
        "filename": "creature_growl_04.ogg",
        "category": "SFX",
        "subcategory": "Creatures",
        "tags": "creature beast roar growl monster",
        "duration_sec": 2.5,
    }
    norm_k = kenney.normalize_item(raw_k)
    assert norm_k["category"] == "SFX"
    assert "CC0" in norm_k["license"]
    assert "Kenney" in norm_k["source_collection"]


# =============================================================================
# 5. Seed Generation & Instant Hydration
# =============================================================================

def test_seed_generation_and_hydration():
    """Verifies that seed generator creates compressed file and hydration populates database."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        seed_path = tmp_p / "test_seed.json.gz"
        bank = SoundBank(bank_root=tmp_p / "bank")

        # Generate small seed with limit
        out = generate_seed_file(
            output_path=seed_path,
            limits_per_adapter={
                "Sonniss_GDC": 2,
                "Kenney_OpenGameArt": 2,
                "Incompetech": 2,
                "BBC_Sound_Effects": 2,
            },
        )
        assert out.exists()
        assert out.stat().st_size > 50

        # Hydrate bank from seed
        res = hydrate_from_seed(bank, seed_path=seed_path)
        inserted_count = res.get("added", 0) if isinstance(res, dict) else res
        assert inserted_count > 0

        # Check DB
        with bank._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM sound_catalog WHERE is_downloaded = 0").fetchone()[0]
            assert total == inserted_count


# =============================================================================
# 6. Hybrid Virtual Search & Explainable Scoring Breakdown
# =============================================================================

def test_hybrid_virtual_search_explainable_scoring():
    """Verifies search_virtual_catalog returns ranked results with why_matched explainability."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bank = SoundBank(bank_root=Path(tmp_dir))
        with bank._get_conn() as conn:
            conn.execute("""
                INSERT INTO sound_catalog (
                    filename, category, title, description, tags, exciter, surface,
                    action_type, dramatic_role, tempo_bpm, voice_masking_risk,
                    is_downloaded, source_collection, source_url
                ) VALUES
                ('battle_sword_hit.wav', 'FOL', 'Clashing Steel Blade', 'Two heavy medieval swords clash in fury', 'sword blade metal clash combat', 'steel', 'metal', 'strike', 'combat', 0.0, 'LOW', 0, 'Sonniss GDC', 'http://example.com/sword.wav'),
                ('peaceful_meadow_flute.mp3', 'MUS', 'Quiet Afternoon Stream', 'Gentle acoustic flute underscore', 'flute peaceful calm pastoral gentle', 'air', 'wood', 'play', 'underscore', 80.0, 'LOW', 0, 'Incompetech', 'http://example.com/stream.mp3')
            """)

        # Search for sword combat
        results = bank.search_virtual_catalog(
            query="medieval sword",
            category="foley",
            exciter="steel",
            limit=5,
        )

        assert len(results) >= 1
        top_match = results[0]
        assert top_match["filename"] == "battle_sword_hit.wav"
        assert "why_matched" in top_match
        reasons = " ".join(top_match["why_matched"]).lower()
        assert "exciter" in reasons or "category" in reasons or "matched" in reasons


# =============================================================================
# 7. Agent Sound Card Formatting
# =============================================================================

def test_agent_sound_card_generation():
    """Verifies that get_agent_sound_card formats a rich, LLM-digestible card."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bank = SoundBank(bank_root=Path(tmp_dir))
        with bank._get_conn() as conn:
            conn.execute("""
                INSERT INTO sound_catalog (
                    id, filename, category, subcategory, title, description, tags,
                    exciter, resonator, action_type, surface, duration_sec,
                    wave_style, voice_masking_risk, whisper_compatibility,
                    foreground_strength, dramatic_role, source_collection, license, is_downloaded
                ) VALUES (
                    99, 'tavern_tankard_slam.ogg', 'FOL', 'Props', 'Ceramic Mug Slam',
                    'A heavy ale mug strikes a rough oak tavern table', 'mug tankard slam table tavern',
                    'ceramic', 'wood', 'impact', 'wood', 1.4,
                    'transient', 'LOW', 0.85, 0.7, 'action_accent', 'BBC Sound Effects', 'CC0', 0
                )
            """)

        card = bank.get_agent_sound_card(99)
        assert card is not None
        assert "[ID: 99]" in card
        assert "Ceramic Mug Slam" in card
        assert "FOL / Props" in card
        assert "exciter: ceramic" in card
        assert "resonator: wood" in card
        assert "voice_masking: LOW" in card
        assert "BBC Sound Effects" in card


# =============================================================================
# 8. JIT Stream Download, Mirror Fallback & Validation
# =============================================================================

def test_jit_download_with_mirror_fallback_and_validation():
    """Verifies download_virtual_asset handles retries, mirror fallback, and validates audio payload."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bank_p = Path(tmp_dir)
        bank = SoundBank(bank_root=bank_p)

        with bank._get_conn() as conn:
            conn.execute("""
                INSERT INTO sound_catalog (
                    id, filename, filepath, is_downloaded, source_url, mirror_url, url_status
                ) VALUES (
                    501, 'virtual_cue.mp3', NULL, 0, 'https://primary.example.com/broken.mp3', 'https://mirror.example.com/valid.mp3', 'unverified'
                )
            """)

        # Mock urllib request: primary fails with 404 HTML, mirror succeeds with valid audio bytes
        import io
        def mock_urlopen(req, timeout=30):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "broken" in url:
                bio = io.BytesIO(b"<!DOCTYPE html><html>404 Not Found</html>")
                bio.status = 404
                return bio
            else:
                bio = io.BytesIO(b"ID3" + b"\x00" * 600)
                bio.status = 200
                return bio

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            dl_path = bank.download_virtual_asset(501)
            assert dl_path is not None
            assert dl_path.exists()
            assert dl_path.name == "virtual_cue.mp3"

            # Check DB state
            with bank._get_conn() as conn:
                row = conn.execute("SELECT is_downloaded, filepath, url_status FROM sound_catalog WHERE id = 501").fetchone()
                assert row[0] == 1
                assert row[1] is not None
                assert row[2] == "available"


# =============================================================================
# 9. SoundAssetRetriever Integration & JIT Triggering
# =============================================================================

def test_sound_asset_retriever_virtual_fallback():
    """Verifies SoundAssetRetriever falls back to virtual catalog and triggers JIT download."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bank_p = Path(tmp_dir)
        bank = SoundBank(bank_root=bank_p)

        # Seed a virtual foley asset that is NOT downloaded
        with bank._get_conn() as conn:
            conn.execute("""
                INSERT INTO sound_catalog (
                    id, filename, filepath, category, title, description, tags,
                    exciter, resonator, action_type, surface, is_downloaded, source_url
                ) VALUES (
                    777, 'remote_metal_axe.ogg', NULL, 'FOL', 'Axe Strike on Pine Tree',
                    'Heavy iron axe bites into pine timber', 'axe wood chop tree strike',
                    'iron', 'pine', 'strike', 'wood', 0, 'https://mirror.example.com/axe.ogg'
                )
            """)

        retriever = SoundAssetRetriever(sound_bank=bank)

        # Mock download_virtual_asset to write a valid synthetic audio file
        def mock_download(sound_id, *args, **kwargs):
            out_file = bank.cache_manager.cache_dir / "remote_metal_axe.ogg"
            out_file.write_bytes(b"OggS" + b"\x00" * 600)
            with bank._get_conn() as conn:
                conn.execute(
                    "UPDATE sound_catalog SET is_downloaded = 1, filepath = ? WHERE id = ?",
                    (str(out_file).replace("\\", "/"), sound_id)
                )
            return out_file

        with patch.object(bank, "download_virtual_asset", side_effect=mock_download):
            descriptor = retriever.resolve_foley_asset(
                action_verb="strike",
                exciter_material="iron",
                surface_material="wood",
            )
            assert descriptor is not None
            assert descriptor.filename == "remote_metal_axe.ogg"
            assert descriptor.category == "FOL"
            assert descriptor.exciter_material == "iron"
            assert Path(descriptor.filepath).exists()

        # Test sound card retrieval
        card = retriever.get_sound_card(777)
        assert card is not None
        assert "Axe Strike on Pine Tree" in card or "remote_metal_axe.ogg" in card


# =============================================================================
# 10. Sound Asset Relationships (Variations & Transitions)
# =============================================================================

def test_sound_asset_relationships():
    """Verifies asset relationships (variations, layers, transitions) can be linked and queried."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        bank = SoundBank(bank_root=Path(tmp_dir))
        with bank._get_conn() as conn:
            conn.execute("""
                INSERT INTO sound_catalog (id, filename, category, is_downloaded)
                VALUES (101, 'footstep_gravel_01.ogg', 'FOL', 1),
                       (102, 'footstep_gravel_02.ogg', 'FOL', 1),
                       (103, 'footstep_gravel_03.ogg', 'FOL', 1)
            """)

        bank.link_assets(101, 102, "variation")
        bank.link_assets(101, 103, "variation")

        related = bank.get_related_assets(101, "variation")
        assert len(related) == 2
        related_ids = {r["id"] for r in related}
        assert related_ids == {102, 103}
