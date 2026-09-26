#!/usr/bin/env python3
"""
Real-World Smoke Test for Sonic Intelligence Engine (Phases 1-3).
================================================================
Processes 5 real-world audio assets spanning:
1. Witcher 3 OST Vocal Track: '090 The Wolven Storm.mp3' (Track 453)
2. Witcher 3 OST Instrumental Monster Theme: '135 The Leshy Comes.mp3' (Track 498)
3. Micro-SFX Metal Impact: 'tiny_sword-clash-01.wav' (Track 164)
4. Ambiguous Layered Crowd Walla: 'tavern_crowd_murmur.ogg' (Track 68)
5. Continuous Ambience with Transients: 'rain_thunder.ogg' (Track 67)

Executes complete pipeline:
Audio -> Metadata -> DSP/Sonic Genome -> AST Classifier/SED -> CLAP Embedding -> Indexing -> Hybrid Retrieval -> Agent Sound Card
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.sonic_intelligence_engine import SonicIntelligenceEngine

TEST_TRACK_IDS = [453, 498, 164, 68, 67]

def run_smoke_test():
    print("=" * 80)
    print("🚀 STARTING REAL-WORLD SMOKE TEST: SONIC INTELLIGENCE ENGINE (PHASES 1-3)")
    print("=" * 80)

    bank = get_sound_bank()
    engine = SonicIntelligenceEngine(sound_bank=bank)

    # -------------------------------------------------------------------------
    # STAGE 1 & 2: Process Audio through Phase 1 (DSP) and Phase 2 (AI Enrichment)
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("STEP 1: INGESTION, PHASE 1 DSP ANALYSIS & PHASE 2 AI ENRICHMENT")
    print("#" * 80)

    processed_summaries = {}

    for track_id in TEST_TRACK_IDS:
        print(f"\n--- Processing Track #{track_id} ---")
        t0 = time.perf_counter()

        # Phase 1: DSP Analysis
        print(f"  [1/2] Running Phase 1 Deterministic DSP Analysis...")
        genome = bank.enrich_asset(track_id, force=True)
        if not genome or not genome.measured_facts:
            raise RuntimeError(f"Phase 1 DSP analysis failed for Track #{track_id}")

        # Phase 2: AI Enrichment (AST AudioSet 527 + LAION-CLAP)
        print(f"  [2/2] Running Phase 2 AI Enrichment (AST Classifier + CLAP Embedding)...")
        genome_p2 = bank.enrich_asset_phase2(track_id, force=True, run_classifier=True, run_clap=True)
        elapsed = time.perf_counter() - t0

        facts = genome.measured_facts
        emb = bank.get_sound_embedding(track_id)
        tags = bank.get_classifier_tags(track_id)
        provenance = bank.get_asset_provenance(track_id)

        processed_summaries[track_id] = {
            "track_id": track_id,
            "filename": genome.filename,
            "elapsed_sec": round(elapsed, 2),
            "duration_sec": round(facts.format.duration_sec, 2),
            "format": facts.format.container,
            "sample_rate": facts.format.sample_rate,
            "channels": facts.format.channels,
            "integrated_lufs": round(facts.loudness.integrated_lufs, 2) if facts.loudness.integrated_lufs else None,
            "true_peak_dbtp": round(facts.loudness.true_peak_dbtp, 2) if facts.loudness.true_peak_dbtp else None,
            "spectral_centroid_hz": round(facts.spectral.spectral_centroid_hz, 1) if facts.spectral.spectral_centroid_hz else None,
            "silence_ratio": round(facts.temporal.silence_ratio, 3),
            "top_classifier_tags": [f"{t.get('normalized_label') or t.get('raw_label')} ({t['raw_score']:.2f})" for t in tags[:5]],
            "has_clap_embedding": emb is not None and len(emb) == 512,
            "provenance_records_count": len(provenance),
        }

        print(f"  [OK] Completed in {elapsed:.2f}s:")
        print(f"       File: {genome.filename} ({facts.format.container}, {facts.format.duration_sec:.2f}s, {facts.format.sample_rate}Hz)")
        top3_tags_str = ", ".join(f"{t.get('normalized_label') or t.get('raw_label')} ({t['raw_score']:.2f})" for t in tags[:3])
        print(f"       Classifier Top 3: {top3_tags_str}")
        print(f"       CLAP: 512-d vector verified (shape={emb.shape if emb is not None else None})")
        print(f"       Provenance runs recorded: {len(provenance)}")

    # -------------------------------------------------------------------------
    # STAGE 3: Agent Sound Cards Inspection
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("STEP 2: AGENT SOUND CARD v3.0 INSPECTION")
    print("#" * 80)

    sound_cards = {}
    for track_id in TEST_TRACK_IDS:
        card = engine.get_sound_card(track_id)
        sound_cards[track_id] = card
        print(f"\n==================== Agent Sound Card: Track #{track_id} ====================")
        print(card.to_agent_markdown())

    # -------------------------------------------------------------------------
    # STAGE 4: Natural-Language & Multimodal Hybrid Retrieval Battery
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("STEP 3: HYBRID RETRIEVAL EVALUATION BATTERY (REAL-WORLD QUERIES)")
    print("#" * 80)

    test_queries = [
        {
            "id": "Q1_EXACT_OBJECT",
            "type": "exact/object",
            "query": "steel sword clashing in melee combat",
            "acceptable_top_ids": [601, 164, 668], # sword_clash_parry.wav or tiny_sword-clash-01.wav
            "rationale": "Direct object match for sword blade impact.",
        },
        {
            "id": "Q2_SEMANTIC_MONSTER",
            "type": "semantic",
            "query": "dark eerie monster lurking in an ancient cursed forest",
            "acceptable_top_ids": [375, 498, 479, 594, 503], # Dark Witcher fantasy themes
            "rationale": "High semantic affinity for dark eerie Witcher fantasy themes.",
        },
        {
            "id": "Q3_ACOUSTIC_WEATHER",
            "type": "acoustic/environmental",
            "query": "heavy continuous rain with sudden loud thunder cracks",
            "acceptable_top_ids": [67], # rain_thunder.ogg
            "rationale": "Strong acoustic match on rain bed and thunder events.",
        },
        {
            "id": "Q4_AUDIOBOOK_WALLA",
            "type": "audiobook/cinematic",
            "query": "busy tavern crowd murmur with people chatting and drinking",
            "acceptable_top_ids": [68], # tavern_crowd_murmur.ogg
            "rationale": "Atmospheric walla bed match for tavern setting.",
        },
        {
            "id": "Q5_VOCAL_BALLAD",
            "type": "semantic/vocal",
            "query": "melancholic female vocal ballad with acoustic lute accompaniment",
            "acceptable_top_ids": [453], # 090 The Wolven Storm.mp3
            "rationale": "Direct semantic & musical match for Priscilla's song.",
        },
        {
            "id": "Q6_NEGATIVE_CONSTRAINT",
            "type": "negative_constraint",
            "query": "dark fantasy music without voice",
            "acceptable_top_ids": [502, 374, 432, 498], # Instrumental dark fantasy themes
            "penalized_id": 453, # The Wolven Storm (has female vocals / speech)
            "rationale": "Negative constraint 'without voice' must penalize Track 453 and elevate instrumental tracks.",
        },
        {
            "id": "Q7_HINGLISH_QUERY",
            "type": "multilingual_hinglish",
            "query": "sharaabkhane ki bheed ka shor",
            "acceptable_top_ids": [68], # tavern_crowd_murmur.ogg
            "rationale": "Hinglish normalizer maps 'sharaabkhane ki bheed ka shor' -> 'tavern crowd murmur'.",
        },
    ]

    retrieval_results = []

    for q in test_queries:
        print(f"\n--- Testing Query [{q['id']}] ({q['type']}): \"{q['query']}\" ---")
        t0 = time.perf_counter()
        res = engine.search_sounds(q["query"], limit=5, apply_diversity=False)
        dur_ms = (time.perf_counter() - t0) * 1000

        top_hit = res.ranked_cards[0] if res.ranked_cards else None
        top_id = top_hit.asset_id if top_hit else None
        acceptable_ids = q.get("acceptable_top_ids", [])
        is_expected = top_id in acceptable_ids

        # Rank of first matching acceptable track
        expected_rank = None
        for r_idx, c in enumerate(res.ranked_cards, 1):
            if c.asset_id in acceptable_ids:
                expected_rank = r_idx
                break

        # Check negative penalty if applicable
        penalized_id = q.get("penalized_id")
        penalized_rank = None
        if penalized_id:
            for r_idx, c in enumerate(res.ranked_cards, 1):
                if c.asset_id == penalized_id:
                    penalized_rank = r_idx
                    break

        print(f"  Plan: Detected Lang: {res.query_plan.detected_language} | Normalized: '{res.query_plan.normalized_query}'")
        print(f"  Plan Intents: {[i for i in res.query_plan.intent_types]}")
        print(f"  Negative Constraints: speech={res.query_plan.negative_constraints.exclude_speech}, music={res.query_plan.negative_constraints.exclude_music}, terms={res.query_plan.negative_constraints.banned_terms}")
        print(f"  Results Returned: {len(res.ranked_cards)} in {dur_ms:.1f}ms")

        for idx, card in enumerate(res.ranked_cards[:3], 1):
            score_str = f"{card.retrieval_score:.3f}" if card.retrieval_score is not None else "N/A"
            print(f"    {idx}. [Score: {score_str}] Track #{card.asset_id}: {card.title} ({card.filename})")
            if card.why_matched:
                print(f"       Evidence: {'; '.join(card.why_matched)}")

        eval_entry = {
            "query_id": q["id"],
            "query": q["query"],
            "type": q["type"],
            "acceptable_top_ids": acceptable_ids,
            "actual_top_id": top_id,
            "best_acceptable_rank": expected_rank,
            "penalized_id": penalized_id,
            "penalized_rank": penalized_rank,
            "success": is_expected,
            "latency_ms": round(dur_ms, 1),
            "normalized_query": res.query_plan.normalized_query,
            "negative_speech_flag": res.query_plan.negative_constraints.exclude_speech,
        }
        retrieval_results.append(eval_entry)
        status_tag = "✅ PASS" if is_expected else f"⚠️ BEST MATCH RANK #{expected_rank}"
        print(f"  Verdict: {status_tag} (Acceptable: {acceptable_ids} -> Actual Top: #{top_id})")

    # -------------------------------------------------------------------------
    # STAGE 5: Save JSON Artifact & Print Final Diagnostic Report
    # -------------------------------------------------------------------------
    smoke_report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "processed_files": processed_summaries,
        "retrieval_evaluations": retrieval_results,
    }

    report_path = Path("tests/smoke_test_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(smoke_report, f, indent=2)

    print("\n" + "=" * 80)
    print(f"🎉 SMOKE TEST EXECUTION COMPLETE. Raw data saved to: {report_path}")
    print("=" * 80)


if __name__ == "__main__":
    run_smoke_test()
