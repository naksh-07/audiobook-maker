import os
import sqlite3
import tempfile
import threading
from pathlib import Path
import numpy as np
import pytest

from audiobook_factory.contracts import (
    SoundRetrievalResult,
    AgentSoundCard
)
from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.sonic_intelligence_engine import SonicIntelligenceEngine
from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter
from audiobook_factory.query_embedding_cache import QueryEmbeddingCache

@pytest.fixture(scope="module")
def shared_clap_adapter():
    return CLAPSemanticAdapter()

@pytest.fixture(scope="module")
def controlled_bank(shared_clap_adapter):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        bank_path = Path(tmp_dir)
        bank = SoundBank(bank_root=bank_path)

        corpus_data = [
            {
                "id": 1,
                "filename": "footsteps_stone_hall.wav",
                "title": "Footsteps on Stone Corridor",
                "description": "Quiet footsteps echoing down an empty ancient stone corridor",
                "category": "FOL",
                "subcategory": "Footsteps",
                "mood": "tense",
                "tags": "footsteps stone walk corridor quiet echoing footsteps",
                "duration_sec": 2.5,
                "integrated_lufs": -24.0,
                "true_peak_db": -6.0,
                "spectral_centroid_hz": 1800.0,
                "action_type": "walk",
                "exciter": "leather",
                "resonator": "stone",
                "classifier_tags": [
                    {"raw": "Footsteps", "norm": "human.footsteps", "score": 0.88, "rank": 1},
                ],
            },
            {
                "id": 2,
                "filename": "door_heavy_wood_slam.wav",
                "title": "Heavy Wooden Door Slam",
                "description": "Loud, violent slam of a heavy oak wooden dungeon door",
                "category": "SFX",
                "subcategory": "Doors",
                "mood": "tense",
                "tags": "door wooden slam heavy impact oak shut dungeon door",
                "duration_sec": 1.2,
                "integrated_lufs": -14.0,
                "true_peak_db": -0.8,
                "spectral_centroid_hz": 1200.0,
                "action_type": "slam",
                "exciter": "wood",
                "resonator": "wood",
                "classifier_tags": [
                    {"raw": "Door", "norm": "architectural.door", "score": 0.92, "rank": 1},
                ],
            }
        ]

        with bank._get_conn() as conn:
            for item in corpus_data:
                conn.execute("""
                    INSERT OR REPLACE INTO sound_catalog (
                        id, filename, filepath, title, description, category, subcategory,
                        mood, tags, duration_sec, integrated_lufs, true_peak_db,
                        spectral_centroid_hz, action_type, exciter, resonator, is_downloaded,
                        analysis_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'deterministic_v1.0')
                """, (
                    item["id"], item["filename"], str(bank_path / item["filename"]), item["title"],
                    item["description"], item["category"], item["subcategory"], item["mood"],
                    item["tags"], item["duration_sec"], item["integrated_lufs"], item["true_peak_db"],
                    item["spectral_centroid_hz"], item["action_type"], item["exciter"], item["resonator"],
                ))

                for cl in item["classifier_tags"]:
                    conn.execute("""
                        INSERT INTO sound_classifier_tags (
                            track_id, model_id, model_version, ontology_id, raw_label,
                            normalized_label, raw_score, rank, source_method
                        ) VALUES (?, 'MIT/ast-finetuned-audioset-10-10-0.4593', '1.0.0', 'audioset_527', ?, ?, ?, ?, 'classifier')
                    """, (item["id"], cl["raw"], cl["norm"], cl["score"], cl["rank"]))

                vec, _ = shared_clap_adapter.embed_text(f"{item['title']} {item['description']}")
                conn.execute("""
                    INSERT OR REPLACE INTO sound_embeddings (
                        track_id, model_id, model_version, embedding_dim,
                        embedding_bytes, preprocessing_version, source_method
                    ) VALUES (?, 'laion/clap-htsat-unfused', '2023_v1', 512, ?, 'v1', 'semantic_model')
                """, (item["id"], vec.astype(np.float32).tobytes()))
            
            # Asset without embedding or DSP
            conn.execute("""
                INSERT OR REPLACE INTO sound_catalog (
                    id, filename, filepath, title, description, is_downloaded
                ) VALUES (999, 'corrupt.wav', 'corrupt.wav', 'Corrupt Asset', 'No DSP or embeddings', 1)
            """)

            conn.execute("INSERT INTO sound_catalog_fts(sound_catalog_fts) VALUES('rebuild');")
            conn.commit()

        yield bank

def test_audit_empty_and_whitespace_queries(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    for q in ["", "   ", "\t\n"]:
        res = engine.search_sounds(q)
        assert isinstance(res, SoundRetrievalResult)

def test_audit_single_character_query(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    res = engine.search_sounds("a")
    assert isinstance(res, SoundRetrievalResult)

def test_audit_ultra_long_query(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    long_query = "door " * 2000
    res = engine.search_sounds(long_query)
    assert isinstance(res, SoundRetrievalResult)

def test_audit_fts5_special_operators(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    queries = [
        '"door',
        'footsteps *',
        'door AND OR NOT NEAR slam',
        'slam ^ OR *'
    ]
    for q in queries:
        res = engine.search_sounds(q)
        assert isinstance(res, SoundRetrievalResult)

def test_audit_multilingual_unicode_emojis(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    queries = [
        'दरवाजा खटखटाना',
        '💥⚔️',
        'door!!!???&&&slam...'
    ]
    for q in queries:
        res = engine.search_sounds(q)
        assert isinstance(res, SoundRetrievalResult)

def test_audit_exactly_one_candidate(controlled_bank):
    # Tests min-max scaling division by zero if min_score == max_score
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    # The string "footsteps_stone_hall" should precisely match asset 1
    res = engine.search_sounds("id:1 exactly one specific test")
    assert isinstance(res, SoundRetrievalResult)

def test_audit_zero_matches(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    res = engine.search_sounds("asdfghjklqwertyuiopzxcvbnm1234567890")
    assert len(res.ranked_cards) == 0

def test_audit_negative_only_queries(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    res = engine.search_sounds("without voices without music")
    assert isinstance(res, SoundRetrievalResult)

def test_audit_embedding_cache_concurrency(controlled_bank):
    cache = QueryEmbeddingCache(controlled_bank._get_conn)
    def worker(idx):
        cache.get_or_compute(f"concurrent query {idx}", lambda t: (np.random.rand(512), "lang"))
    
    threads = []
    for i in range(20):
        t = threading.Thread(target=worker, args=(i % 5,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()

def test_audit_find_similar_missing_or_corrupt_asset(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    
    # Missing asset
    with pytest.raises(Exception):
         engine.find_similar(asset_id=9999, mode="semantic")

    # Corrupt asset (id 999 has no DSP or embeddings)
    res = engine.find_similar(asset_id=999, mode="acoustic")
    assert isinstance(res, list)

def test_audit_diversity_filtering_edge_cases(controlled_bank):
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    # limit > available
    res1 = engine.search_sounds("door", limit=100, diversity_threshold=0.5)
    
    # diversity threshold 0.0 vs 1.0
    res2 = engine.search_sounds("door", limit=2, diversity_threshold=0.0)
    res3 = engine.search_sounds("door", limit=2, diversity_threshold=1.0)
    
    assert isinstance(res1, SoundRetrievalResult)
    assert isinstance(res2, SoundRetrievalResult)
    assert isinstance(res3, SoundRetrievalResult)
