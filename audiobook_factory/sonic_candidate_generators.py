#!/usr/bin/env python3
"""
Multi-Source Candidate Generation & Evidence Preservation (Phase 3).
===================================================================
Produces bounded candidate pools from multiple evidence generators:
- FTS5 Keyword Matcher (BM25 lexical relevance)
- Structured Metadata Filter (Sonic Genome relational taxonomy)
- Classifier & Temporal Event Matcher (AudioSet 527 tags & detected onsets)
- CLAP Semantic Searcher (512-d dual vector similarity with query cache)
- Acoustic Filter (Deterministic DSP physical boundaries)

Preserves granular, multi-signal retrieval evidence for every candidate
before passing to the downstream hybrid reranker.
"""

from __future__ import annotations

import abc
import json
import re
import sqlite3
from typing import Any, Dict, List, Literal, Optional, Set, Tuple
from pathlib import Path
import numpy as np

from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.sonic_query_planner import SoundQueryPlan
from audiobook_factory.query_embedding_cache import QueryEmbeddingCache, get_query_embedding_cache


class CandidateEvidence(BaseModel):
    """Granular evidence explaining why an asset was retrieved by candidate generators."""
    model_config = ConfigDict(extra="ignore")

    asset_id: int
    sources: List[str] = Field(default_factory=list, description="List of generators that nominated this asset")
    fts_score: Optional[float] = None
    fts_matched_terms: List[str] = Field(default_factory=list)
    structured_matches: Dict[str, Any] = Field(default_factory=dict)
    classifier_matches: List[Dict[str, Any]] = Field(default_factory=list)
    temporal_event_matches: List[Dict[str, Any]] = Field(default_factory=list)
    clap_similarity: Optional[float] = None
    clap_relative_score: Optional[float] = None
    clap_query_matched: Optional[str] = None
    acoustic_matches: Dict[str, Any] = Field(default_factory=dict)
    negative_signals: Dict[str, Any] = Field(default_factory=dict)
    metadata_completeness: float = Field(default=0.0, ge=0.0, le=1.0)


class CandidateRecord(BaseModel):
    """Candidate asset container preserving database metadata and retrieval evidence."""
    model_config = ConfigDict(extra="ignore")

    asset_id: int
    filename: str
    filepath: Optional[str] = None
    title: str = ""
    description: str = ""
    category: str = "SFX"
    subcategory: str = "General"
    mood: str = "default"
    duration_sec: float = 0.0
    is_downloaded: bool = False
    source_collection: str = ""
    license: str = "Royalty-Free"
    tags: str = ""
    evidence: CandidateEvidence
    raw_metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseCandidateGenerator(abc.ABC):
    """Abstract interface for all Phase 3 candidate generators."""

    @abc.abstractmethod
    def generate(self, plan: SoundQueryPlan, limit: int = 50) -> List[CandidateRecord]:
        """Generates candidates matching the query plan with explicit evidence."""
        pass


class FTSCandidateGenerator(BaseCandidateGenerator):
    """Candidate generator leveraging SQLite FTS5 Full-Text Search."""

    def __init__(self, db_conn_factory):
        self._get_conn = db_conn_factory

    def generate(self, plan: SoundQueryPlan, limit: int = 50) -> List[CandidateRecord]:
        if not plan.keyword_terms:
            return []

        sanitized_tokens = []
        for w in plan.keyword_terms:
            clean_w = re.sub(r'["\'\*\^\:\(\)\{\}\[\]\~\+\-\?]', '', w).strip()
            if clean_w:
                sanitized_tokens.append(f'"{clean_w}"*')

        if not sanitized_tokens:
            return []

        fts_and = " AND ".join(sanitized_tokens)
        fts_or = " OR ".join(sanitized_tokens)

        candidates: List[CandidateRecord] = []
        try:
            with self._get_conn() as conn:
                # 1. High precision AND search
                sql = """
                    SELECT c.*, f.rank as bm25_rank
                    FROM sound_catalog_fts f
                    JOIN sound_catalog c ON f.rowid = c.id
                    WHERE sound_catalog_fts MATCH ?
                    ORDER BY f.rank ASC LIMIT ?
                """
                rows = conn.execute(sql, (fts_and, limit)).fetchall()
                if not rows and len(search_tokens) > 1:
                    # 2. Broad recall OR fallback
                    rows = conn.execute(sql, (fts_or, limit)).fetchall()

                for r in rows:
                    row_d = dict(r)
                    bm25 = float(row_d.get("bm25_rank") or 0.0)
                    # Convert negative BM25 rank to normalized 0.0-1.0 relevance
                    # FTS5 bm25 produces negative numbers where more negative = better match
                    fts_score = round(1.0 / (1.0 + abs(bm25) * 0.1), 3) if bm25 != 0 else 0.5

                    # Check matched tokens against tags/title/desc
                    matched = []
                    text_blob = f"{row_d.get('title', '')} {row_d.get('description', '')} {row_d.get('tags', '')}".lower()
                    for t in plan.keyword_terms:
                        if t.lower() in text_blob or t.lower() in row_d.get("filename", "").lower():
                            matched.append(t)

                    cand = _build_candidate_record(
                        row_d,
                        source="fts",
                        fts_score=fts_score,
                        fts_matched_terms=matched or plan.keyword_terms[:2],
                    )
                    candidates.append(cand)
        except Exception as e:
            logger.debug(f"FTSCandidateGenerator encountered warning: {e}")

        return candidates


class StructuredFilterCandidateGenerator(BaseCandidateGenerator):
    """Candidate generator querying relational Sonic Genome schema columns."""

    def __init__(self, db_conn_factory):
        self._get_conn = db_conn_factory

    def generate(self, plan: SoundQueryPlan, limit: int = 50) -> List[CandidateRecord]:
        if not plan.structured_filters:
            return []

        clauses = []
        params = []
        matches_found = {}

        sf = plan.structured_filters
        if "category" in sf:
            cat = sf["category"].upper()
            if cat in ("FOLEY", "FOL", "SFX"):
                clauses.append("category IN ('FOL', 'SFX')")
            elif cat in ("AMB", "AMBIENCE"):
                clauses.append("category IN ('AMB', 'CHAPTER_BED')")
            elif cat in ("MUS", "MUSIC"):
                clauses.append("category IN ('MUS', 'LEITMOTIF', 'CHAPTER_BED', 'DYNAMIC_STEM')")
            else:
                clauses.append("category = ?")
                params.append(cat)
            matches_found["category"] = cat

        if "subcategory" in sf:
            clauses.append("LOWER(subcategory) = LOWER(?)")
            params.append(sf["subcategory"])
            matches_found["subcategory"] = sf["subcategory"]

        if "mood" in sf:
            clauses.append("LOWER(mood) = LOWER(?)")
            params.append(sf["mood"])
            matches_found["mood"] = sf["mood"]

        if "exciter" in sf:
            clauses.append("(LOWER(exciter) LIKE ? OR LOWER(tags) LIKE ?)")
            params.extend([f"%{sf['exciter'].lower()}%", f"%{sf['exciter'].lower()}%"])
            matches_found["exciter"] = sf["exciter"]

        if "resonator" in sf:
            clauses.append("(LOWER(resonator) LIKE ? OR LOWER(tags) LIKE ?)")
            params.extend([f"%{sf['resonator'].lower()}%", f"%{sf['resonator'].lower()}%"])
            matches_found["resonator"] = sf["resonator"]

        if "action_type" in sf:
            clauses.append("(LOWER(action_type) LIKE ? OR LOWER(tags) LIKE ?)")
            params.extend([f"%{sf['action_type'].lower()}%", f"%{sf['action_type'].lower()}%"])
            matches_found["action_type"] = sf["action_type"]

        if not clauses:
            return []

        sql = f"SELECT * FROM sound_catalog WHERE {' AND '.join(clauses)} LIMIT ?"
        params.append(limit)

        candidates: List[CandidateRecord] = []
        try:
            with self._get_conn() as conn:
                rows = conn.execute(sql, params).fetchall()
                for r in rows:
                    cand = _build_candidate_record(
                        dict(r),
                        source="structured",
                        structured_matches=matches_found,
                    )
                    candidates.append(cand)
        except Exception as e:
            logger.debug(f"StructuredFilterCandidateGenerator warning: {e}")

        return candidates


class ClassifierCandidateGenerator(BaseCandidateGenerator):
    """Candidate generator querying AST AudioSet 527 tags and temporal events."""

    def __init__(self, db_conn_factory):
        self._get_conn = db_conn_factory

    def generate(self, plan: SoundQueryPlan, limit: int = 50) -> List[CandidateRecord]:
        if not plan.target_classifier_labels:
            return []

        candidates: List[CandidateRecord] = []
        try:
            with self._get_conn() as conn:
                placeholders = ",".join("?" for _ in plan.target_classifier_labels)
                params: List[Any] = list(plan.target_classifier_labels)

                # Query sound_classifier_tags for matching raw or normalized labels
                sql = f"""
                    SELECT t.track_id, t.raw_label, t.normalized_label, t.raw_score, t.rank,
                           c.*
                    FROM sound_classifier_tags t
                    JOIN sound_catalog c ON c.id = t.track_id
                    WHERE t.raw_label IN ({placeholders})
                       OR t.normalized_label IN ({placeholders})
                    ORDER BY t.raw_score DESC
                    LIMIT ?
                """
                params_full = params + params + [limit]
                rows = conn.execute(sql, params_full).fetchall()

                for r in rows:
                    row_d = dict(r)
                    class_match = {
                        "raw_label": row_d.get("raw_label"),
                        "normalized_label": row_d.get("normalized_label"),
                        "raw_score": float(row_d.get("raw_score") or 0.0),
                        "rank": int(row_d.get("rank") or 1),
                    }

                    # Fetch temporal events if available
                    events_rows = conn.execute(
                        "SELECT event_type, start_sec, end_sec, confidence FROM sound_temporal_events WHERE track_id = ? LIMIT 5",
                        (row_d["track_id"],)
                    ).fetchall()
                    ev_list = [dict(ev) for ev in events_rows]

                    cand = _build_candidate_record(
                        row_d,
                        source="classifier",
                        classifier_matches=[class_match],
                        temporal_events=ev_list,
                    )
                    candidates.append(cand)
        except Exception as e:
            logger.debug(f"ClassifierCandidateGenerator warning: {e}")

        return candidates


class CLAPSemanticCandidateGenerator(BaseCandidateGenerator):
    """
    Candidate generator using Phase 2 CLAP semantic text embeddings and vector dot-products.
    Top-K retrieval without arbitrary universal cosine thresholds.
    """

    def __init__(
        self,
        db_conn_factory,
        embedding_cache: Optional[QueryEmbeddingCache] = None,
        clap_adapter=None,
    ):
        self._get_conn = db_conn_factory
        self.embedding_cache = embedding_cache or get_query_embedding_cache()
        self._clap_adapter = clap_adapter

    def _get_adapter(self):
        if self._clap_adapter is None:
            from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter
            self._clap_adapter = CLAPSemanticAdapter()
        return self._clap_adapter

    def generate(self, plan: SoundQueryPlan, limit: int = 50) -> List[CandidateRecord]:
        if not plan.semantic_queries:
            return []

        candidates_map: Dict[int, CandidateRecord] = {}

        for sem_query in plan.semantic_queries[:3]:
            try:
                # 1. Fetch or compute query text embedding
                adapter = self._get_adapter()
                cached_vec = self.embedding_cache.get(
                    normalized_query=sem_query,
                    model_id=adapter.model_id,
                    model_version=adapter.model_version,
                    preprocessing_version=adapter.preprocessing_version,
                )

                if cached_vec is not None:
                    query_vec = cached_vec
                else:
                    query_vec, _ = adapter.embed_text(sem_query)
                    self.embedding_cache.put(
                        normalized_query=sem_query,
                        model_id=adapter.model_id,
                        model_version=adapter.model_version,
                        vector=query_vec,
                        preprocessing_version=adapter.preprocessing_version,
                    )

                # 2. Retrieve all stored embeddings from SQLite
                with self._get_conn() as conn:
                    emb_rows = conn.execute("""
                        SELECT e.track_id, e.embedding_bytes, c.*
                        FROM sound_embeddings e
                        JOIN sound_catalog c ON c.id = e.track_id
                    """).fetchall()

                if not emb_rows:
                    continue

                track_ids = []
                vectors_list = []
                catalog_rows = []

                expected_bytes = len(query_vec) * 4
                for r in emb_rows:
                    b = r["embedding_bytes"]
                    if b and len(b) == expected_bytes:
                        track_ids.append(r["track_id"])
                        vectors_list.append(np.frombuffer(b, dtype=np.float32))
                        catalog_rows.append(dict(r))

                if not vectors_list:
                    continue

                # 3. Vectorized matrix dot-product (cosine similarity for L2-normalized vectors)
                corpus_matrix = np.vstack(vectors_list)
                sims = np.dot(corpus_matrix, query_vec)

                # 4. Top-K relative ranking without absolute cutoff
                top_indices = np.argsort(sims)[::-1][:limit]
                min_sim = float(np.min(sims[top_indices])) if len(top_indices) > 0 else 0.0
                max_sim = float(np.max(sims[top_indices])) if len(top_indices) > 0 else 1.0
                sim_range = max_sim - min_sim

                for idx in top_indices:
                    tid = track_ids[idx]
                    raw_sim = float(sims[idx])
                    # Per-query relative normalization [0.0, 1.0]
                    if sim_range < 1e-5:
                        rel_score = max(0.0, min(1.0, raw_sim)) if raw_sim > 0 else 1.0
                    else:
                        rel_score = float((raw_sim - min_sim) / sim_range)

                    row_d = catalog_rows[idx]
                    if tid not in candidates_map:
                        candidates_map[tid] = _build_candidate_record(
                            row_d,
                            source="clap",
                            clap_sim=round(raw_sim, 4),
                            clap_rel=round(rel_score, 4),
                            clap_query=sem_query,
                        )
                    else:
                        # Keep maximum similarity across compound query variations
                        cand = candidates_map[tid]
                        if cand.evidence.clap_similarity is None or raw_sim > cand.evidence.clap_similarity:
                            cand.evidence.clap_similarity = round(raw_sim, 4)
                            cand.evidence.clap_relative_score = round(rel_score, 4)
                            cand.evidence.clap_query_matched = sem_query
                        if "clap" not in cand.evidence.sources:
                            cand.evidence.sources.append("clap")
            except Exception as e:
                logger.warning(f"CLAPSemanticCandidateGenerator query '{sem_query}' warning: {e}")

        return list(candidates_map.values())


class AcousticCandidateGenerator(BaseCandidateGenerator):
    """Candidate generator applying deterministic DSP boundary filtering."""

    def __init__(self, db_conn_factory):
        self._get_conn = db_conn_factory

    def generate(self, plan: SoundQueryPlan, limit: int = 50) -> List[CandidateRecord]:
        ac = plan.acoustic_constraints
        has_constraints = (
            ac.duration_min_sec is not None or
            ac.duration_max_sec is not None or
            ac.spectral_character is not None or
            ac.whisper_safe_only or
            ac.target_lufs_max is not None
        )
        if not has_constraints:
            return []

        clauses = []
        params: List[Any] = []
        criteria = {}

        if ac.duration_min_sec is not None:
            clauses.append("duration_sec >= ?")
            params.append(ac.duration_min_sec)
            criteria["duration_min_sec"] = ac.duration_min_sec
        if ac.duration_max_sec is not None:
            clauses.append("duration_sec <= ?")
            params.append(ac.duration_max_sec)
            criteria["duration_max_sec"] = ac.duration_max_sec

        if ac.spectral_character == "bright":
            clauses.append("spectral_centroid_hz >= 2200.0")
            criteria["spectral_brightness"] = "bright (>=2200Hz)"
        elif ac.spectral_character == "dark":
            clauses.append("spectral_centroid_hz <= 1500.0")
            criteria["spectral_brightness"] = "dark (<=1500Hz)"

        if ac.whisper_safe_only:
            clauses.append("whisper_compatibility >= 0.4 AND voice_masking_risk != 'SEVERE'")
            criteria["whisper_safe"] = True

        if ac.target_lufs_max is not None:
            clauses.append("integrated_lufs <= ?")
            params.append(ac.target_lufs_max)
            criteria["target_lufs_max"] = ac.target_lufs_max

        if not clauses:
            return []

        sql = f"""
            SELECT * FROM sound_catalog
            WHERE {' AND '.join(clauses)}
            ORDER BY is_downloaded DESC LIMIT ?
        """
        params.append(limit)

        candidates: List[CandidateRecord] = []
        try:
            with self._get_conn() as conn:
                rows = conn.execute(sql, params).fetchall()
                for r in rows:
                    cand = _build_candidate_record(
                        dict(r),
                        source="acoustic",
                        acoustic_matches=criteria,
                    )
                    candidates.append(cand)
        except Exception as e:
            logger.debug(f"AcousticCandidateGenerator warning: {e}")

        return candidates


class CandidatePoolAggregator:
    """
    Executes all candidate generators and merges them into a deduplicated candidate pool,
    preserving granular retrieval evidence across all generators.
    """

    def __init__(self, generators: List[BaseCandidateGenerator], pool_limit: int = 100):
        self.generators = generators
        self.pool_limit = pool_limit

    def assemble_pool(self, plan: SoundQueryPlan) -> List[CandidateRecord]:
        merged_pool: Dict[int, CandidateRecord] = {}

        for gen in self.generators:
            try:
                candidates = gen.generate(plan, limit=self.pool_limit)
                for cand in candidates:
                    aid = cand.asset_id
                    if aid not in merged_pool:
                        merged_pool[aid] = cand
                    else:
                        # Merge multi-source evidence
                        existing = merged_pool[aid]
                        for s in cand.evidence.sources:
                            if s not in existing.evidence.sources:
                                existing.evidence.sources.append(s)

                        if cand.evidence.fts_score is not None:
                            existing.evidence.fts_score = cand.evidence.fts_score
                        if cand.evidence.fts_matched_terms:
                            existing.evidence.fts_matched_terms = list(set(
                                existing.evidence.fts_matched_terms + cand.evidence.fts_matched_terms
                            ))
                        if cand.evidence.structured_matches:
                            existing.evidence.structured_matches.update(cand.evidence.structured_matches)
                        if cand.evidence.classifier_matches:
                            existing.evidence.classifier_matches.extend(cand.evidence.classifier_matches)
                        if cand.evidence.temporal_event_matches:
                            existing.evidence.temporal_event_matches.extend(cand.evidence.temporal_event_matches)
                        if cand.evidence.clap_similarity is not None:
                            existing.evidence.clap_similarity = cand.evidence.clap_similarity
                            existing.evidence.clap_relative_score = cand.evidence.clap_relative_score
                            existing.evidence.clap_query_matched = cand.evidence.clap_query_matched
                        if cand.evidence.acoustic_matches:
                            existing.evidence.acoustic_matches.update(cand.evidence.acoustic_matches)
            except Exception as e:
                logger.warning(f"Generator {gen.__class__.__name__} failed during pool assembly: {e}")

        # Compute metadata completeness for each candidate in the pool
        for cand in merged_pool.values():
            cand.evidence.metadata_completeness = _compute_metadata_completeness(cand.raw_metadata)

        return list(merged_pool.values())[:self.pool_limit]


def _build_candidate_record(
    row_d: Dict[str, Any],
    source: str,
    fts_score: Optional[float] = None,
    fts_matched_terms: Optional[List[str]] = None,
    structured_matches: Optional[Dict[str, Any]] = None,
    classifier_matches: Optional[List[Dict[str, Any]]] = None,
    temporal_events: Optional[List[Dict[str, Any]]] = None,
    clap_sim: Optional[float] = None,
    clap_rel: Optional[float] = None,
    clap_query: Optional[str] = None,
    acoustic_matches: Optional[Dict[str, Any]] = None,
) -> CandidateRecord:
    """Helper to instantiate CandidateRecord with strongly typed CandidateEvidence."""
    aid = int(row_d.get("id") or row_d.get("track_id") or 0)
    evidence = CandidateEvidence(
        asset_id=aid,
        sources=[source],
        fts_score=fts_score,
        fts_matched_terms=fts_matched_terms or [],
        structured_matches=structured_matches or {},
        classifier_matches=classifier_matches or [],
        temporal_event_matches=temporal_events or [],
        clap_similarity=clap_sim,
        clap_relative_score=clap_rel,
        clap_query_matched=clap_query,
        acoustic_matches=acoustic_matches or {},
    )

    return CandidateRecord(
        asset_id=aid,
        filename=row_d.get("filename", ""),
        filepath=row_d.get("filepath"),
        title=row_d.get("title") or row_d.get("filename", ""),
        description=row_d.get("description") or "",
        category=row_d.get("category") or "SFX",
        subcategory=row_d.get("subcategory") or "General",
        mood=row_d.get("mood") or "default",
        duration_sec=float(row_d.get("duration_sec") or 0.0),
        is_downloaded=bool(row_d.get("is_downloaded", False)),
        source_collection=row_d.get("source_collection") or "SoundBank",
        license=row_d.get("license") or "Royalty-Free",
        tags=row_d.get("tags") or "",
        evidence=evidence,
        raw_metadata=row_d,
    )


def _compute_metadata_completeness(meta: Dict[str, Any]) -> float:
    """Computes an honest metadata richness score between 0.0 and 1.0."""
    indicators = [
        bool(meta.get("duration_sec") and meta.get("duration_sec") > 0),
        bool(meta.get("category") and meta.get("category") != "SFX"),
        bool(meta.get("subcategory") and meta.get("subcategory") != "General"),
        bool(meta.get("description")),
        bool(meta.get("tags")),
        bool(meta.get("integrated_lufs") is not None),
        bool(meta.get("spectral_centroid_hz") is not None),
        bool(meta.get("exciter") or meta.get("resonator")),
        bool(meta.get("action_type")),
        bool(meta.get("sonic_genome") and meta.get("sonic_genome") != "{}"),
    ]
    return round(sum(1.0 for i in indicators if i) / len(indicators), 2)
