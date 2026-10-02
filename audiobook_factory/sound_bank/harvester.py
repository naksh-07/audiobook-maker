#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Semantic Harvester & Vector Operations.
Manages vector embeddings, CLAP text encoding, multi-stage library harvesting,
and streaming ingestion pipelines.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
import numpy as np


class HarvesterMixin:
    """Semantic vector operations and autonomous library harvesting mixin."""

    bank_root: Path
    db_path: Path

    def get_sound_embedding(self, sound_id: int, model_id: Optional[str] = None) -> Optional[np.ndarray]:
        """Retrieves stored 512-d CLAP embedding vector as a float32 numpy array."""
        with self._get_conn() as conn:
            if model_id:
                row = conn.execute("""
                    SELECT embedding_bytes FROM sound_embeddings
                    WHERE track_id = ? AND model_id = ?
                    ORDER BY id DESC LIMIT 1
                """, (sound_id, model_id)).fetchone()
            else:
                row = conn.execute("""
                    SELECT embedding_bytes FROM sound_embeddings
                    WHERE track_id = ?
                    ORDER BY id DESC LIMIT 1
                """, (sound_id,)).fetchone()

            if not row or not row["embedding_bytes"]:
                return None

            return np.frombuffer(row["embedding_bytes"], dtype=np.float32)

    def embed_text_query(self, query: str) -> np.ndarray:
        """Encodes a natural language text query into a 512-d normalized CLAP vector."""
        from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter
        adapter = CLAPSemanticAdapter()
        vector, _ = adapter.embed_text(query)
        return vector

    def get_classifier_tags(self, sound_id: int) -> List[Dict[str, Any]]:
        """Retrieves all classifier tags and raw scores for a sound asset ordered by rank."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT raw_label, normalized_label, raw_score, calibrated_score, rank, ontology_id, start_sec, end_sec
                FROM sound_classifier_tags
                WHERE track_id = ?
                ORDER BY rank ASC
            """, (sound_id,)).fetchall()
            return [dict(r) for r in rows]

    def search_intelligence(
        self,
        intent: str,
        limit: int = 10,
        weights: Optional[Any] = None,
        apply_diversity: bool = True,
        diversity_threshold: Optional[float] = None,
    ) -> Any:
        """
        Phase 3 Hybrid Sonic Intelligence Retrieval delegate method.
        """
        from audiobook_factory.sonic_intelligence_engine import SonicIntelligenceEngine
        engine = SonicIntelligenceEngine(sound_bank=self)
        return engine.search_sounds(
            intent=intent,
            limit=limit,
            weights=weights,
            apply_diversity=apply_diversity,
            diversity_threshold=diversity_threshold,
        )

    def get_agent_sound_card_v3(self, sound_id: int) -> Any:
        """Retrieves the typed Phase 3 AgentSoundCard with full epistemic transparency."""
        from audiobook_factory.sonic_intelligence_engine import SonicIntelligenceEngine
        engine = SonicIntelligenceEngine(sound_bank=self)
        return engine.get_sound_card(sound_id)

    def harvest_library(
        self,
        directory: Union[Path, str],
        recursive: bool = True,
        stage: str = "all",
        max_workers: int = 4,
        batch_size: int = 25,
        force: bool = False,
        retry_failed: bool = False,
        progress_callback: Optional[Callable[[int, int, str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the autonomous 11-stage Sonic Intelligence harvesting pipeline.
        """
        from audiobook_factory.sonic_harvester import SonicLibraryHarvester
        harvester = SonicLibraryHarvester(
            db_path=self.db_path,
            conn_factory=self._get_conn,
        )
        return harvester.harvest_directory(
            directory=directory,
            recursive=recursive,
            stage=stage,
            max_workers=max_workers,
            batch_size=batch_size,
            force=force,
            retry_failed=retry_failed,
            progress_callback=progress_callback,
        )

    def get_harvest_status(self) -> Dict[str, Any]:
        """Aggregates catalog-wide harvest intelligence and coverage telemetry."""
        with self._get_conn() as conn:
            total_sounds = conn.execute("SELECT COUNT(*) FROM sound_catalog").fetchone()[0]
            local_sounds = conn.execute("SELECT COUNT(*) FROM sound_catalog WHERE is_downloaded = 1 OR filepath IS NOT NULL").fetchone()[0]
            dsp_analyzed = conn.execute("SELECT COUNT(*) FROM sound_catalog WHERE integrated_lufs IS NOT NULL").fetchone()[0]
            clap_embedded = conn.execute("SELECT COUNT(DISTINCT track_id) FROM sound_embeddings").fetchone()[0]
            classifier_tagged = conn.execute("SELECT COUNT(DISTINCT track_id) FROM sound_classifier_tags").fetchone()[0]
            failed_runs = conn.execute("SELECT COUNT(*) FROM sound_analysis_runs WHERE execution_status = 'FAILED'").fetchone()[0]

            formats = conn.execute("SELECT format, COUNT(*) FROM sound_catalog WHERE format != '' GROUP BY format").fetchall()
            format_breakdown = {r[0]: r[1] for r in formats}

            categories = conn.execute("SELECT category, COUNT(*) FROM sound_catalog GROUP BY category").fetchall()
            category_breakdown = {r[0]: r[1] for r in categories}

            return {
                "total_sounds": total_sounds,
                "local_sounds": local_sounds,
                "dsp_analyzed": dsp_analyzed,
                "dsp_coverage_pct": round((dsp_analyzed / max(1, local_sounds)) * 100, 1),
                "clap_embedded": clap_embedded,
                "clap_coverage_pct": round((clap_embedded / max(1, local_sounds)) * 100, 1),
                "classifier_tagged": classifier_tagged,
                "classifier_coverage_pct": round((classifier_tagged / max(1, local_sounds)) * 100, 1),
                "failed_runs": failed_runs,
                "format_breakdown": format_breakdown,
                "category_breakdown": category_breakdown,
                "database_path": str(self.db_path),
            }

    def run_metadata_pilot(
        self,
        export_dir: Optional[Any] = None,
        force: bool = False,
        bbc_csv_limit: int = 150,
        limit_per_bundle: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Executes the non-destructive metadata-harvesting pilot."""
        from audiobook_factory.metadata_pilot_harvester import MetadataPilotHarvester
        harvester = MetadataPilotHarvester(sound_bank=self)
        return harvester.run_pilot(
            export_dir=export_dir,
            force=force,
            bbc_csv_limit=bbc_csv_limit,
            bundle_limit=limit_per_bundle,
        )

    def stream_harvest(
        self,
        source: str = "bbc",
        batch_size_gb: float = 10.0,
        batch_limit_items: int = 500,
        max_batches: Optional[int] = None,
        workers: int = 4,
        ai_mode: str = "full",
        scratch_dir: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Executes sliding-window ephemeral batch streaming ingestion."""
        from audiobook_factory.streaming_harvester import (
            StreamingBatchConfig,
            StreamingLibraryHarvester,
        )
        cfg = StreamingBatchConfig(
            source=source,
            batch_size_bytes=int(batch_size_gb * 1024 * 1024 * 1024),
            max_items_per_batch=batch_limit_items,
            max_batches=max_batches,
            workers=workers,
            ai_mode=ai_mode,
            scratch_dir=Path(scratch_dir) if scratch_dir else (self.bank_root / "temp_scratch"),
        )
        harvester = StreamingLibraryHarvester(sound_bank=self, config=cfg)
        return harvester.run_streaming_pipeline()
