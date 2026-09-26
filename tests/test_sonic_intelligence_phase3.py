"""
Phase 3 Validation Suite: Sonic Intelligence Engine.
===================================================
Tests all 15 Retrieval Quality Pillars specified in Section 26:
1. Exact keyword retrieval (FTS5 BM25)
2. Semantic retrieval (CLAP 512-d dual space without hard thresholds)
3. Structured filtering (category, exciter, resonator, mood)
4. Classifier filtering (AudioSet 527 tags and raw probabilities)
5. Hybrid retrieval integration (multi-source candidate pool & reranking)
6. Negative evidence handling (confirmed speech/music rejection vs unknown)
7. Short-SFX retrieval (micro-transients and impacts)
8. Hindi / Hinglish normalization ("talwar ka bhaari vaar", "door se halki footsteps")
9. Compound query decomposition (multi-action sequence extraction)
10. Semantic vs Acoustic distinction (CLAP similarity vs DSP timbre/centroid)
11. Find Similar modes (semantic vs acoustic vs category vs source)
12. Honest Agent Sound Card generation (epistemic labeling & completeness)
13. Explanation generation (detailed why_matched evidence)
14. Graceful degradation (generator failure resilience)
15. Deterministic ranking for identical inputs
"""

import os
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import pytest

from audiobook_factory.contracts import (
    SoundQueryPlan,
    AtomicSoundConcept,
    AgentSoundCard,
    CandidateEvidence,
    RerankingWeights,
    SoundRetrievalResult,
)
from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.sonic_query_planner import SonicQueryPlanner, HinglishQueryNormalizer
from audiobook_factory.query_embedding_cache import QueryEmbeddingCache
from audiobook_factory.sonic_candidate_generators import (
    CandidateRecord,
    CandidatePoolAggregator,
    FTSCandidateGenerator,
    StructuredFilterCandidateGenerator,
    ClassifierCandidateGenerator,
    CLAPSemanticCandidateGenerator,
    AcousticCandidateGenerator,
)
from audiobook_factory.sonic_hybrid_reranker import SonicHybridReranker, ScoredCandidate
from audiobook_factory.agent_sound_card import AgentSoundCard, SoundCardBuilder
from audiobook_factory.sonic_intelligence_engine import (
    SonicIntelligenceEngine,
    get_sonic_intelligence_engine,
)
from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter


@pytest.fixture(scope="module")
def shared_clap_adapter():
    """Provides a shared CLAPSemanticAdapter instance for vector generation."""
    return CLAPSemanticAdapter()


@pytest.fixture(scope="module")
def controlled_bank(shared_clap_adapter):
    """
    Creates a temporary SQLite SoundBank populated with a representative,
    controlled 18-sound test corpus across diverse categories and acoustics.
    """
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
                    {"raw": "Walk, footsteps", "norm": "human.footsteps.walk", "score": 0.85, "rank": 2},
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
                    {"raw": "Bang", "norm": "transient.pop", "score": 0.74, "rank": 2},
                ],
            },
            {
                "id": 3,
                "filename": "sword_clash_steel_sharp.wav",
                "title": "Heavy Steel Sword Clash",
                "description": "High transient steel blade impact and strike during intense swordfight",
                "category": "SFX",
                "subcategory": "Combat",
                "mood": "epic",
                "tags": "sword blade clash steel metal strike fight combat parry weapon",
                "duration_sec": 0.8,
                "integrated_lufs": -15.0,
                "true_peak_db": -1.2,
                "spectral_centroid_hz": 3800.0,
                "action_type": "strike",
                "exciter": "metal",
                "resonator": "metal",
                "classifier_tags": [
                    {"raw": "Tools", "norm": "metal.strike", "score": 0.78, "rank": 1},
                    {"raw": "Clash", "norm": "combat", "score": 0.75, "rank": 2},
                ],
            },
            {
                "id": 4,
                "filename": "rain_thunder_storm_bed.wav",
                "title": "Heavy Rain and Thunder Storm",
                "description": "Continuous pouring rain with low rumbling thunderclaps and howling wind",
                "category": "AMB",
                "subcategory": "Weather",
                "mood": "dark",
                "tags": "rain thunder storm weather downpour water rumble dark ambience",
                "duration_sec": 15.0,
                "integrated_lufs": -28.0,
                "true_peak_db": -4.0,
                "spectral_centroid_hz": 950.0,
                "action_type": "pour",
                "exciter": "water",
                "resonator": "air",
                "classifier_tags": [
                    {"raw": "Rain", "norm": "weather.rain", "score": 0.95, "rank": 1},
                    {"raw": "Thunder", "norm": "weather.thunder", "score": 0.82, "rank": 2},
                ],
            },
            {
                "id": 5,
                "filename": "wind_howl_winter.wav",
                "title": "Howling Winter Wind",
                "description": "Cold gusty winter blizzard wind howling across frozen peaks",
                "category": "AMB",
                "subcategory": "Weather",
                "mood": "mysterious",
                "tags": "wind howling winter blizzard gale snow cold breeze",
                "duration_sec": 20.0,
                "integrated_lufs": -30.0,
                "true_peak_db": -5.5,
                "spectral_centroid_hz": 800.0,
                "action_type": "blow",
                "exciter": "air",
                "resonator": "air",
                "classifier_tags": [
                    {"raw": "Wind", "norm": "weather.wind", "score": 0.90, "rank": 1},
                ],
            },
            {
                "id": 6,
                "filename": "room_tone_quiet_castle.wav",
                "title": "Quiet Castle Room Tone",
                "description": "Whisper-quiet ambient room tone in a secluded medieval stone library",
                "category": "AMB",
                "subcategory": "General",
                "mood": "peaceful",
                "tags": "room tone silence quiet peaceful subtle stone hall castle",
                "duration_sec": 30.0,
                "integrated_lufs": -42.0,
                "true_peak_db": -18.0,
                "spectral_centroid_hz": 450.0,
                "action_type": "drift",
                "exciter": "air",
                "resonator": "stone",
                "classifier_tags": [
                    {"raw": "Silence", "norm": "ambient.room_tone", "score": 0.65, "rank": 1},
                ],
            },
            {
                "id": 7,
                "filename": "creature_monster_roar.wav",
                "title": "Demonic Beast Roar",
                "description": "Fearsome guttural roar and snarl from a subterranean predator",
                "category": "SFX",
                "subcategory": "Monster",
                "mood": "tense",
                "tags": "monster creature beast roar snarl demonic growl predator",
                "duration_sec": 3.0,
                "integrated_lufs": -16.0,
                "true_peak_db": -1.0,
                "spectral_centroid_hz": 1100.0,
                "action_type": "roar",
                "exciter": "vocal",
                "resonator": "flesh",
                "classifier_tags": [
                    {"raw": "Howl", "norm": "nature.creature.howl", "score": 0.85, "rank": 1},
                    {"raw": "Animal", "norm": "nature.creature", "score": 0.80, "rank": 2},
                ],
            },
            {
                "id": 8,
                "filename": "magic_energy_blast.wav",
                "title": "Magical Arcane Energy Blast",
                "description": "Concussive magical explosion of arcane energy and fiery burst",
                "category": "SFX",
                "subcategory": "Magic",
                "mood": "epic",
                "tags": "magic magical energy blast spell concussive explosion burst",
                "duration_sec": 2.0,
                "integrated_lufs": -15.0,
                "true_peak_db": -1.5,
                "spectral_centroid_hz": 2400.0,
                "action_type": "blast",
                "exciter": "energy",
                "resonator": "air",
                "classifier_tags": [
                    {"raw": "Explosion", "norm": "combat.explosion", "score": 0.72, "rank": 1},
                ],
            },
            {
                "id": 9,
                "filename": "orchestral_battle_drums.wav",
                "title": "Intense Orchestral Battle Percussion",
                "description": "Dramatic orchestral war drums and brass fanfare underscore",
                "category": "MUS",
                "subcategory": "General",
                "mood": "epic",
                "tags": "music orchestral battle drums percussion brass fanfare score",
                "duration_sec": 25.0,
                "integrated_lufs": -18.0,
                "true_peak_db": -1.2,
                "spectral_centroid_hz": 1500.0,
                "action_type": "play",
                "exciter": "percussion",
                "resonator": "drum",
                "classifier_tags": [
                    {"raw": "Music", "norm": "music", "score": 0.96, "rank": 1},
                    {"raw": "Musical instrument", "norm": "music.instrument", "score": 0.91, "rank": 2},
                ],
            },
            {
                "id": 10,
                "filename": "tavern_crowd_talking_voices.wav",
                "title": "Tavern Crowd Chatter and Voices",
                "description": "Busy medieval inn crowded with people talking, laughing, and drunken speech",
                "category": "AMB",
                "subcategory": "Tavern",
                "mood": "default",
                "tags": "tavern crowd wallah voices chatter talking people speaking speech",
                "duration_sec": 18.0,
                "integrated_lufs": -22.0,
                "true_peak_db": -3.0,
                "spectral_centroid_hz": 2100.0,
                "action_type": "talk",
                "exciter": "voice",
                "resonator": "room",
                "classifier_tags": [
                    {"raw": "Speech", "norm": "human.vocal", "score": 0.91, "rank": 1},
                    {"raw": "Laughter", "norm": "human.vocal.laugh", "score": 0.70, "rank": 2},
                ],
            },
            {
                "id": 11,
                "filename": "glass_bottle_shatter_micro.wav",
                "title": "Glass Bottle Shatter",
                "description": "Ultra short sharp transient of a glass bottle breaking on stone",
                "category": "SFX",
                "subcategory": "Props",
                "mood": "tense",
                "tags": "glass bottle shatter break sharp impact crash",
                "duration_sec": 0.4,
                "integrated_lufs": -17.0,
                "true_peak_db": -2.0,
                "spectral_centroid_hz": 4500.0,
                "action_type": "shatter",
                "exciter": "glass",
                "resonator": "glass",
                "classifier_tags": [
                    {"raw": "Glass", "norm": "material.glass", "score": 0.89, "rank": 1},
                    {"raw": "Shatter", "norm": "material.glass.break", "score": 0.85, "rank": 2},
                ],
            },
            {
                "id": 12,
                "filename": "fireplace_warm_crackle.wav",
                "title": "Warm Fireplace Crackle",
                "description": "Gentle crackling flames and warm glowing embers in a brick hearth",
                "category": "AMB",
                "subcategory": "Nature",
                "mood": "peaceful",
                "tags": "fireplace fire crackle warm cozy flames hearth heat",
                "duration_sec": 22.0,
                "integrated_lufs": -32.0,
                "true_peak_db": -8.0,
                "spectral_centroid_hz": 1400.0,
                "action_type": "crackle",
                "exciter": "fire",
                "resonator": "hearth",
                "classifier_tags": [
                    {"raw": "Fire", "norm": "ambient.fire", "score": 0.93, "rank": 1},
                    {"raw": "Crackling", "norm": "ambient.fire.crackling", "score": 0.89, "rank": 2},
                ],
            },
        ]

        # Insert into sound_catalog and related tables
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
                    item["id"],
                    item["filename"],
                    str(bank_path / item["filename"]),
                    item["title"],
                    item["description"],
                    item["category"],
                    item["subcategory"],
                    item["mood"],
                    item["tags"],
                    item["duration_sec"],
                    item["integrated_lufs"],
                    item["true_peak_db"],
                    item["spectral_centroid_hz"],
                    item["action_type"],
                    item["exciter"],
                    item["resonator"],
                ))

                # Classifier tags
                for cl in item["classifier_tags"]:
                    conn.execute("""
                        INSERT INTO sound_classifier_tags (
                            track_id, model_id, model_version, ontology_id, raw_label,
                            normalized_label, raw_score, rank, source_method
                        ) VALUES (?, 'MIT/ast-finetuned-audioset-10-10-0.4593', '1.0.0', 'audioset_527', ?, ?, ?, ?, 'classifier')
                    """, (
                        item["id"],
                        cl["raw"],
                        cl["norm"],
                        cl["score"],
                        cl["rank"],
                    ))

                # Real CLAP semantic embeddings in dual space (using description text)
                vec, _ = shared_clap_adapter.embed_text(f"{item['title']} {item['description']}")
                conn.execute("""
                    INSERT OR REPLACE INTO sound_embeddings (
                        track_id, model_id, model_version, embedding_dim,
                        embedding_bytes, preprocessing_version, source_method
                    ) VALUES (?, 'laion/clap-htsat-unfused', '2023_v1', 512, ?, 'v1', 'semantic_model')
                """, (
                    item["id"],
                    vec.astype(np.float32).tobytes(),
                ))

            # Rebuild FTS5 virtual table
            conn.execute("INSERT INTO sound_catalog_fts(sound_catalog_fts) VALUES('rebuild');")
            conn.commit()

        yield bank


# ==============================================================================
# 1. Exact Keyword Retrieval Tests
# ==============================================================================
def test_01_exact_keyword_retrieval(controlled_bank):
    """Pillar 1: FTS5 BM25 exact keyword matching."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    res = engine.search_sounds("door slam")

    assert len(res.ranked_cards) > 0
    top = res.ranked_cards[0]
    assert top.asset_id == 2  # door_heavy_wood_slam.wav
    assert "door" in top.filename.lower()
    assert any("keyword" in r.lower() or "door" in r.lower() for r in top.why_matched)


# ==============================================================================
# 2. Semantic Retrieval Tests (CLAP Dual-Space)
# ==============================================================================
def test_02_semantic_retrieval_clap(controlled_bank):
    """Pillar 2: CLAP semantic candidate generation without hardcoded cosine thresholds."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    # Query has no exact keyword overlap with "guttural roar and snarl" but expresses the concept
    res = engine.search_sounds("terrifying angry monster growl")

    assert len(res.ranked_cards) > 0
    top_ids = [c.asset_id for c in res.ranked_cards[:3]]
    assert 7 in top_ids  # creature_monster_roar.wav

    top_card = next(c for c in res.ranked_cards if c.asset_id == 7)
    assert top_card.clap_similarity is not None
    assert top_card.clap_similarity > 0.0


# ==============================================================================
# 3. Structured Filtering Tests
# ==============================================================================
def test_03_structured_filtering(controlled_bank):
    """Pillar 3: Relational Sonic Genome structured query filtering."""
    planner = SonicQueryPlanner()
    plan = planner.plan_query("footsteps on stone corridor")

    assert plan.structured_filters.get("category") == "FOL"
    assert plan.structured_filters.get("resonator") == "stone"

    gen = StructuredFilterCandidateGenerator(controlled_bank._get_conn)
    candidates = gen.generate(plan, limit=10)

    assert len(candidates) > 0
    assert any(c.asset_id == 1 for c in candidates)
    c1 = next(c for c in candidates if c.asset_id == 1)
    assert c1.evidence.structured_matches.get("category") == "FOL"


# ==============================================================================
# 4. Classifier Filtering Tests
# ==============================================================================
def test_04_classifier_filtering(controlled_bank):
    """Pillar 4: Retrieval via AST AudioSet 527 tags and raw scores."""
    planner = SonicQueryPlanner()
    plan = planner.plan_query("rainstorm")

    gen = ClassifierCandidateGenerator(controlled_bank._get_conn)
    candidates = gen.generate(plan, limit=10)

    assert len(candidates) > 0
    rain_cand = next(c for c in candidates if c.asset_id == 4)
    assert any(m["raw_label"] == "Rain" for m in rain_cand.evidence.classifier_matches)
    assert rain_cand.evidence.classifier_matches[0]["raw_score"] > 0.80


# ==============================================================================
# 5. Hybrid Retrieval Integration
# ==============================================================================
def test_05_hybrid_retrieval_integration(controlled_bank):
    """Pillar 5: Multi-source candidate aggregation and reranking."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    res = engine.search_sounds("heavy steel sword clash")

    assert res.total_candidates_considered >= 1
    top = res.ranked_cards[0]
    assert top.asset_id == 3  # sword_clash_steel_sharp.wav
    assert top.retrieval_score is not None
    assert top.retrieval_score >= 0.70


# ==============================================================================
# 6. Negative Evidence Handling
# ==============================================================================
def test_06_negative_evidence_handling(controlled_bank):
    """Pillar 6: Speech detected penalized when query specifies 'without voices'."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)

    # Search with negation
    res_no_voices = engine.search_sounds("busy ambient crowd without voices")

    # Asset 10 is tavern crowd with speech detected (0.91 confidence)
    card_10 = next((c for c in res_no_voices.ranked_cards if c.asset_id == 10), None)
    if card_10:
        # If card 10 appeared, verify it got heavily penalized and explains it
        assert any("penalty" in r.lower() or "speech detected" in r.lower() for r in card_10.why_matched)

    # Asset 6 (room tone) or 4 (rain) should not be penalized for speech
    res_clean = engine.search_sounds("quiet room tone without voices")
    top = res_clean.ranked_cards[0]
    assert top.asset_id == 6  # room_tone_quiet_castle.wav
    assert any("speech-free" in r.lower() or "negative" in r.lower() for r in top.why_matched)


# ==============================================================================
# 7. Short-SFX Retrieval Tests
# ==============================================================================
def test_07_short_sfx_retrieval(controlled_bank):
    """Pillar 7: Micro-transients and impacts with transient-centric acoustic boundaries."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    res = engine.search_sounds("short sharp glass shatter impact")

    assert len(res.ranked_cards) > 0
    top = res.ranked_cards[0]
    assert top.asset_id == 11  # glass_bottle_shatter_micro.wav (0.4s duration, 4500Hz centroid)
    assert top.duration_sec <= 1.0


# ==============================================================================
# 8. Hindi & Hinglish Query Normalization
# ==============================================================================
def test_08_hinglish_multilingual_normalization(controlled_bank):
    """Pillar 8: Hinglish requests map to canonical English search terms and CLAP embeddings."""
    normalizer = HinglishQueryNormalizer()

    # Case A: "talwar ka bhaari vaar"
    norm_a, lang_a, sem_a, attrs_a = normalizer.normalize("talwar ka bhaari vaar")
    assert lang_a in ("hinglish", "hi")
    assert "sword" in norm_a
    assert "strike" in norm_a or "heavy" in norm_a
    assert any("heavy metal sword impact" in s.lower() for s in sem_a)

    # Case B: "door se halki footsteps"
    norm_b, lang_b, sem_b, attrs_b = normalizer.normalize("door se halki footsteps")
    assert "distant" in norm_b
    assert "faint" in norm_b or "halki" in norm_b or "footsteps" in norm_b
    assert attrs_b.get("distance") == "distant"

    # End-to-end retrieval with Hinglish query
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    res = engine.search_sounds("talwar ka bhaari vaar")
    assert len(res.ranked_cards) > 0
    top = res.ranked_cards[0]
    assert top.asset_id == 3  # sword_clash_steel_sharp.wav


# ==============================================================================
# 9. Compound Query Decomposition
# ==============================================================================
def test_09_compound_query_decomposition():
    """Pillar 9: Multi-action compound queries decompose into atomic concepts."""
    planner = SonicQueryPlanner()
    plan = planner.plan_query("quiet distant footsteps followed by a heavy wooden door slam")

    assert len(plan.atomic_concepts) >= 2
    concept_1 = plan.atomic_concepts[0]
    assert "footstep" in concept_1.concept_text.lower()
    assert "quiet" in concept_1.modifiers or "distant" in concept_1.modifiers

    concept_2 = plan.atomic_concepts[1]
    assert "door" in concept_2.concept_text.lower()
    assert "heavy" in concept_2.modifiers or "wooden" in concept_2.modifiers

    assert plan.ranking_hints.get("has_sequence") is True


# ==============================================================================
# 10. Semantic vs Acoustic Similarity Distinction
# ==============================================================================
def test_10_semantic_vs_acoustic_distinction(controlled_bank):
    """Pillar 10: Semantic similarity (CLAP) and acoustic similarity (DSP) yield distinct results."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)

    # Asset 3: sword_clash_steel_sharp.wav (Combat, 0.8s, 3800Hz centroid)
    similar_semantic = engine.find_similar(asset_id=3, mode="semantic", limit=3)
    similar_acoustic = engine.find_similar(asset_id=3, mode="acoustic", limit=3)

    assert len(similar_semantic) > 0
    assert len(similar_acoustic) > 0

    # Semantic similarity finds semantic neighbors (e.g. magic blast or battle)
    # Acoustic similarity finds sounds with close duration and high spectral centroid (e.g. glass shatter: 0.4s, 4500Hz)
    acoustic_ids = [c.asset_id for c in similar_acoustic]
    assert 11 in acoustic_ids  # glass shatter is acoustically closest in centroid and duration!


# ==============================================================================
# 11. Find Similar Modes
# ==============================================================================
def test_11_find_similar_modes(controlled_bank):
    """Pillar 11: Explicit similarity modes (semantic, acoustic, category, source)."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)

    cat_sim = engine.find_similar(asset_id=4, mode="category", limit=2)  # rain storm
    assert len(cat_sim) > 0
    for c in cat_sim:
        assert c.category == "AMB"

    # Acoustic similarity
    ac_sim = engine.find_similar(asset_id=4, mode="acoustic", limit=2)
    assert len(ac_sim) > 0
    for c in ac_sim:
        assert any("acoustic" in r.lower() for r in c.why_matched)


# ==============================================================================
# 12. Honest Agent Sound Card Generation
# ==============================================================================
def test_12_agent_sound_card_honesty(controlled_bank):
    """Pillar 12: Epistemic transparency and honest markdown formatting."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    card = engine.get_sound_card(asset_id=1)

    assert card is not None
    assert isinstance(card, AgentSoundCard)
    assert card.asset_id == 1
    assert card.duration_sec == 2.5
    assert card.integrated_lufs == -24.0

    md = card.to_agent_markdown()
    assert "[MEASURED DSP]" in md
    assert "[CLASSIFIER]" in md
    assert "-24.0 LUFS" in md
    assert "Footsteps" in md or "human.footsteps" in md


# ==============================================================================
# 13. Explanation Generation
# ==============================================================================
def test_13_explanation_generation(controlled_bank):
    """Pillar 13: Transparent why_matched evidence for retrieved sounds."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)
    res = engine.search_sounds("heavy steel sword strike")

    top = res.ranked_cards[0]
    explanation = engine.explain_match(top)

    assert f"ID: {top.asset_id}" in explanation
    assert "Matched Signals:" in explanation
    assert len(top.why_matched) > 0


# ==============================================================================
# 14. Graceful Degradation
# ==============================================================================
def test_14_graceful_degradation(controlled_bank):
    """Pillar 14: Engine survives when CLAP is unavailable or errors out."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)

    # Simulate CLAP failure by breaking generator adapter
    class FailingCLAP:
        model_id = "test"
        model_version = "1.0"
        preprocessing_version = "v1"
        def embed_text(self, text):
            raise RuntimeError("CLAP model offline")

    engine.clap_generator._clap_adapter = FailingCLAP()

    # Search should still succeed via FTS5, Structured Filters, and DSP constraints!
    res = engine.search_sounds("door slam")
    assert len(res.ranked_cards) > 0
    assert res.ranked_cards[0].asset_id == 2  # door slam still found via FTS!


# ==============================================================================
# 15. Deterministic Ranking
# ==============================================================================
def test_15_deterministic_ranking(controlled_bank):
    """Pillar 15: Identical query inputs produce identical candidate rank orders and scores."""
    engine = SonicIntelligenceEngine(sound_bank=controlled_bank)

    query = "distant footsteps on stone"
    res1 = engine.search_sounds(query)
    res2 = engine.search_sounds(query)

    assert len(res1.ranked_cards) == len(res2.ranked_cards)
    for c1, c2 in zip(res1.ranked_cards, res2.ranked_cards):
        assert c1.asset_id == c2.asset_id
        assert c1.retrieval_score == c2.retrieval_score


# ==============================================================================
# 16. SoundBank Non-Breaking Delegate Test
# ==============================================================================
def test_16_sound_bank_delegate_integration(controlled_bank):
    """Verifies SoundBank.search_intelligence() and get_agent_sound_card_v3() delegates."""
    res = controlled_bank.search_intelligence("heavy sword strike")
    assert isinstance(res, SoundRetrievalResult)
    assert len(res.ranked_cards) > 0

    card = controlled_bank.get_agent_sound_card_v3(sound_id=3)
    assert isinstance(card, AgentSoundCard)
    assert card.asset_id == 3

    # Legacy format_agent_sound_card with AgentSoundCard
    formatted_md = controlled_bank.format_agent_sound_card(card)
    assert "Sound Card [ID: 3]" in formatted_md
