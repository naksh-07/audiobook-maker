#!/usr/bin/env python3
"""
Sonic Intelligence Engine (Phase 3 Facade & Domain Interface).
=============================================================
Top-level agent-facing intelligence layer for audio drama sound retrieval.
Provides:
- search_sounds(intent): Multi-signal hybrid retrieval returning ranked AgentSoundCards
- find_similar(asset_id, mode): Strict separation of Semantic vs Acoustic vs Category similarity
- explain_match(asset_id): Transparent match diagnostics and provenance breakdown
- get_sound_card(asset_id): Honest v3.0 Agent Sound Card representation

Gracefully degrades when individual generators (CLAP, FTS, Classifier) are unavailable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
import numpy as np
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.sonic_query_planner import SonicQueryPlanner, SoundQueryPlan
from audiobook_factory.query_embedding_cache import QueryEmbeddingCache, get_query_embedding_cache
from audiobook_factory.sonic_candidate_generators import (
    CandidateRecord,
    CandidatePoolAggregator,
    FTSCandidateGenerator,
    StructuredFilterCandidateGenerator,
    ClassifierCandidateGenerator,
    CLAPSemanticCandidateGenerator,
    AcousticCandidateGenerator,
)
from audiobook_factory.sonic_hybrid_reranker import (
    SonicHybridReranker,
    RerankingWeights,
    ScoredCandidate,
)
from audiobook_factory.agent_sound_card import AgentSoundCard, SoundCardBuilder


class SoundRetrievalResult(BaseModel):
    """Container holding ranked sound cards, query plan, and execution telemetry."""
    model_config = ConfigDict(extra="ignore")

    original_query: str
    normalized_query: str
    query_plan: SoundQueryPlan
    ranked_cards: List[AgentSoundCard] = Field(default_factory=list)
    total_candidates_considered: int = 0
    execution_telemetry: Dict[str, Any] = Field(default_factory=dict)

    def summary(self) -> str:
        """Returns brief human-readable retrieval summary."""
        lines = [
            f"=== Sonic Retrieval Result: '{self.original_query}' ===",
            f"Normalized Plan: '{self.normalized_query}' (Language: {self.query_plan.detected_language})",
            f"Candidates Considered: {self.total_candidates_considered} | Returned: {len(self.ranked_cards)}",
            f"Latency: {self.execution_telemetry.get('total_latency_ms', 0):.1f} ms\n",
        ]
        for idx, card in enumerate(self.ranked_cards, start=1):
            score_str = f"Score: {card.retrieval_score:.2f}" if card.retrieval_score is not None else ""
            lines.append(f"{idx}. [{card.category}] {card.title} (ID: {card.asset_id}) {score_str}")
            if card.why_matched:
                lines.append(f"   Why: {'; '.join(card.why_matched[:2])}")
        return "\n".join(lines)


class SonicIntelligenceEngine:
    """
    High-level domain service providing agent-facing sound retrieval and intelligence.
    """

    def __init__(
        self,
        sound_bank: Optional[SoundBank] = None,
        query_cache: Optional[QueryEmbeddingCache] = None,
        reranker: Optional[SonicHybridReranker] = None,
    ):
        self.bank = sound_bank or get_sound_bank()
        self.planner = SonicQueryPlanner()
        self.query_cache = query_cache or get_query_embedding_cache(db_path=self.bank.db_path)
        self.reranker = reranker or SonicHybridReranker()

        # Wire up candidate generators
        self.fts_generator = FTSCandidateGenerator(self.bank._get_conn)
        self.struct_generator = StructuredFilterCandidateGenerator(self.bank._get_conn)
        self.classifier_generator = ClassifierCandidateGenerator(self.bank._get_conn)
        self.clap_generator = CLAPSemanticCandidateGenerator(
            db_conn_factory=self.bank._get_conn,
            embedding_cache=self.query_cache,
        )
        self.acoustic_generator = AcousticCandidateGenerator(self.bank._get_conn)

        self.pool_aggregator = CandidatePoolAggregator(
            generators=[
                self.fts_generator,
                self.struct_generator,
                self.classifier_generator,
                self.clap_generator,
                self.acoustic_generator,
            ],
            pool_limit=100,
        )

    def search_sounds(
        self,
        intent: str,
        limit: int = 10,
        weights: Optional[RerankingWeights] = None,
        apply_diversity: bool = True,
        diversity_threshold: Optional[float] = None,
    ) -> SoundRetrievalResult:
        """
        Primary agent-facing search method.
        Accepts natural language intent in English, Hindi, or Hinglish.
        Deconstructs intent, generates multi-source candidates, transparently reranks,
        and returns honest AgentSoundCards with explainable evidence.
        """
        start_time = time.perf_counter()

        # 1. Query Planning & Normalization
        plan = self.planner.plan_query(intent)

        # 2. Candidate Generation Pool (with multi-signal evidence)
        candidate_pool = self.pool_aggregator.assemble_pool(plan)
        pool_size = len(candidate_pool)

        # 3. Transparent Hybrid Reranking
        scored_candidates = self.reranker.rerank(
            candidates=candidate_pool,
            plan=plan,
            weights=weights,
            apply_diversity=apply_diversity,
            top_k=limit,
            diversity_threshold=diversity_threshold,
        )

        # 4. Agent Sound Card Construction
        ranked_cards: List[AgentSoundCard] = [
            SoundCardBuilder.from_scored_candidate(sc) for sc in scored_candidates
        ]

        total_latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return SoundRetrievalResult(
            original_query=intent,
            normalized_query=plan.normalized_query,
            query_plan=plan,
            ranked_cards=ranked_cards,
            total_candidates_considered=pool_size,
            execution_telemetry={
                "total_latency_ms": total_latency_ms,
                "generators_executed": 5,
                "candidate_pool_size": pool_size,
                "diversity_applied": apply_diversity,
            },
        )

    def find_similar(
        self,
        asset_id: int,
        mode: Literal["semantic", "acoustic", "category", "source"] = "semantic",
        limit: int = 5,
    ) -> List[AgentSoundCard]:
        """
        Retrieves sounds similar to a reference asset, maintaining strict separation:
        - 'semantic': 512-d CLAP vector cosine similarity
        - 'acoustic': Deterministic DSP distance (centroid, flatness, duration, LUFS)
        - 'category': Sonic Genome physical taxonomy alignment
        - 'source': Common sound designer / collection
        """
        # Fetch reference asset
        with self.bank._get_conn() as conn:
            ref_row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (asset_id,)).fetchone()
            if not ref_row:
                raise ValueError(f"Reference asset ID {asset_id} not found in sound catalog.")
            ref_dict = dict(ref_row)

        if mode == "semantic":
            return self._find_similar_semantic(asset_id, limit=limit)
        elif mode == "acoustic":
            return self._find_similar_acoustic(ref_dict, limit=limit)
        elif mode == "category":
            return self._find_similar_category(ref_dict, limit=limit)
        elif mode == "source":
            return self._find_similar_source(ref_dict, limit=limit)
        else:
            raise ValueError(f"Unsupported similarity mode '{mode}'. Choose 'semantic', 'acoustic', 'category', or 'source'.")

    def _find_similar_semantic(self, ref_id: int, limit: int = 5) -> List[AgentSoundCard]:
        """Finds semantic nearest neighbors using 512-d CLAP embeddings."""
        ref_vec = self.bank.get_sound_embedding(ref_id)
        if ref_vec is None:
            # If reference asset has no embedding, return empty
            logger.warning(f"Reference asset {ref_id} has no CLAP embedding.")
            return []

        with self.bank._get_conn() as conn:
            rows = conn.execute("""
                SELECT e.track_id, e.embedding_bytes, c.*
                FROM sound_embeddings e
                JOIN sound_catalog c ON c.id = e.track_id
                WHERE e.track_id != ?
            """, (ref_id,)).fetchall()

        if not rows:
            return []

        track_ids = []
        vectors = []
        catalog_rows = []
        for r in rows:
            b = r["embedding_bytes"]
            if b and len(b) == 512 * 4:
                track_ids.append(r["track_id"])
                vectors.append(np.frombuffer(b, dtype=np.float32))
                catalog_rows.append(dict(r))

        if not vectors:
            return []

        matrix = np.vstack(vectors)
        sims = np.dot(matrix, ref_vec)
        top_indices = np.argsort(sims)[::-1][:limit]

        cards = []
        for idx in top_indices:
            row_d = catalog_rows[idx]
            card = SoundCardBuilder.from_database_row(row_d)
            card.clap_similarity = round(float(sims[idx]), 4)
            card.why_matched = [f"Semantic similarity {sims[idx]:.3f} to asset #{ref_id}"]
            cards.append(card)

        return cards

    def _find_similar_acoustic(self, ref_dict: Dict[str, Any], limit: int = 5) -> List[AgentSoundCard]:
        """Finds acoustically similar sounds using measured DSP facts."""
        ref_id = ref_dict["id"]
        ref_dur = float(ref_dict.get("duration_sec") or 1.0)
        ref_centroid = float(ref_dict.get("spectral_centroid_hz") or 2000.0)
        ref_lufs = float(ref_dict.get("integrated_lufs") or -23.0)

        with self.bank._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM sound_catalog
                WHERE id != ? AND spectral_centroid_hz IS NOT NULL
                LIMIT 200
            """, (ref_id,)).fetchall()

        if not rows:
            return []

        scored = []
        for r in rows:
            row_d = dict(r)
            dur = float(row_d.get("duration_sec") or 1.0)
            centroid = float(row_d.get("spectral_centroid_hz") or 2000.0)
            lufs = float(row_d.get("integrated_lufs") or -23.0)

            # Normalized acoustic distance (Euclidean on z-scaled features)
            dur_diff = abs(dur - ref_dur) / max(1.0, ref_dur)
            centroid_diff = abs(centroid - ref_centroid) / 3000.0
            lufs_diff = abs(lufs - ref_lufs) / 20.0

            dist = np.sqrt(dur_diff**2 + centroid_diff**2 + (lufs_diff * 0.5)**2)
            similarity = round(1.0 / (1.0 + float(dist)), 3)
            scored.append((similarity, row_d))

        scored.sort(key=lambda x: x[0], reverse=True)

        cards = []
        for sim, row_d in scored[:limit]:
            card = SoundCardBuilder.from_database_row(row_d)
            card.retrieval_score = sim
            card.why_matched = [
                f"Acoustic DSP similarity {sim:.2f} (duration ~{row_d.get('duration_sec'):.1f}s, centroid ~{row_d.get('spectral_centroid_hz'):.0f}Hz)"
            ]
            cards.append(card)

        return cards

    def _find_similar_category(self, ref_dict: Dict[str, Any], limit: int = 5) -> List[AgentSoundCard]:
        """Finds sounds in the same category, subcategory, or physical action."""
        ref_id = ref_dict["id"]
        cat = ref_dict.get("category", "SFX")
        subcat = ref_dict.get("subcategory", "General")
        act = ref_dict.get("action_type", "")

        with self.bank._get_conn() as conn:
            sql = """
                SELECT * FROM sound_catalog
                WHERE id != ? AND category = ?
                ORDER BY (CASE WHEN subcategory = ? THEN 2 ELSE 0 END +
                          CASE WHEN action_type = ? THEN 2 ELSE 0 END) DESC,
                         id ASC
                LIMIT ?
            """
            rows = conn.execute(sql, (ref_id, cat, subcat, act, limit)).fetchall()

        cards = []
        for r in rows:
            row_d = dict(r)
            card = SoundCardBuilder.from_database_row(row_d)
            card.why_matched = [f"Shared category '{cat}' / subcategory '{subcat}'"]
            cards.append(card)
        return cards

    def _find_similar_source(self, ref_dict: Dict[str, Any], limit: int = 5) -> List[AgentSoundCard]:
        """Finds sounds from the same collection or sound designer."""
        ref_id = ref_dict["id"]
        col = ref_dict.get("source_collection", "SoundBank")

        with self.bank._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM sound_catalog
                WHERE id != ? AND source_collection = ?
                LIMIT ?
            """, (ref_id, col, limit)).fetchall()

        cards = []
        for r in rows:
            row_d = dict(r)
            card = SoundCardBuilder.from_database_row(row_d)
            card.why_matched = [f"Same source collection: '{col}'"]
            cards.append(card)
        return cards

    def explain_match(self, asset_id_or_card: Union[int, AgentSoundCard]) -> str:
        """Returns diagnostic explanation for why a sound matched or its acoustic profile."""
        if isinstance(asset_id_or_card, AgentSoundCard):
            card = asset_id_or_card
        else:
            card = self.get_sound_card(asset_id_or_card)

        if not card:
            return f"Asset ID {asset_id_or_card} not found."

        reasons = card.why_matched or ["Direct lookup"]
        lines = [
            f"Explanation for [{card.category}] {card.title} (ID: {card.asset_id}):",
            f"- Retrieval Score: {card.retrieval_score if card.retrieval_score is not None else 'N/A'}",
            "- Matched Signals:",
        ]
        for r in reasons:
            lines.append(f"  • {r}")
        lines.append(f"- Status: {'Cached on disk' if card.is_local_cached else 'Virtual (JIT Ready)'}")
        return "\n".join(lines)

    def get_sound_card(self, asset_id: int) -> Optional[AgentSoundCard]:
        """Retrieves honest AgentSoundCard directly for any asset ID in the catalog."""
        with self.bank._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (asset_id,)).fetchone()
            if not row:
                return None
            row_d = dict(row)

            # Retrieve temporal events
            ev_rows = conn.execute("""
                SELECT id, track_id, event_type, start_sec, end_sec, confidence,
                       source_method, detector_id, metadata, created_at
                FROM sound_temporal_events
                WHERE track_id = ?
                ORDER BY start_sec ASC
            """, (asset_id,)).fetchall()
            temporal_events = []
            for ev in ev_rows:
                ev_d = dict(ev)
                if ev_d.get("metadata") and isinstance(ev_d["metadata"], str):
                    try:
                        ev_d["metadata"] = json.loads(ev_d["metadata"])
                    except Exception:
                        pass
                temporal_events.append(ev_d)

        classifier_tags = self.bank.get_classifier_tags(asset_id)
        sonic_genome = self.bank.get_sonic_genome(asset_id)

        card = SoundCardBuilder.from_database_row(
            row_d,
            classifier_tags=classifier_tags,
            temporal_events=temporal_events,
            sonic_genome=sonic_genome,
        )

        # Retrieve CLAP embedding presence
        clap_vec = self.bank.get_sound_embedding(asset_id)
        if clap_vec is not None:
            card.analysis_status = "full_phase2"

        return card

    def get_candidate_cards_for_beat(
        self,
        intent: str,
        era: Optional[str] = None,
        franchise_affinity: Optional[str] = None,
        category: str = "FOL",
        max_duration_sec: float = 4.0,
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top lightweight, token-efficient sound candidate cards
        specifically formatted for LLM Director prompt injection.
        Guarantees strict duration limits and franchise prioritization.
        """
        matches = self.bank.search(
            query=intent,
            category=category,
            era=era,
            franchise_affinity=franchise_affinity,
            limit=limit * 2,
        )
        cards = []
        for m in matches:
            dur = float(m.get("duration_sec", 0.0) or 0.0)
            if max_duration_sec > 0 and dur > max_duration_sec:
                continue
            cards.append({
                "asset_id": m.get("id"),
                "filename": m.get("filename"),
                "filepath": m.get("filepath"),
                "category": m.get("category"),
                "duration_sec": round(dur, 2),
                "franchise_affinity": m.get("franchise_affinity"),
                "description": m.get("description", "") or m.get("tags", ""),
            })
            if len(cards) >= limit:
                break
        return cards


_GLOBAL_SONIC_ENGINE: Optional[SonicIntelligenceEngine] = None


def get_sonic_intelligence_engine(sound_bank: Optional[SoundBank] = None) -> SonicIntelligenceEngine:
    """Returns singleton instance of the SonicIntelligenceEngine."""
    global _GLOBAL_SONIC_ENGINE
    if _GLOBAL_SONIC_ENGINE is None:
        _GLOBAL_SONIC_ENGINE = SonicIntelligenceEngine(sound_bank=sound_bank)
    return _GLOBAL_SONIC_ENGINE
