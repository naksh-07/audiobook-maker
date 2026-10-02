#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank DSP Audio Metrics & Sonic Genome Enrichment.
Integrates deterministic audio analysis (LUFS, true peak, spectral centroids),
provenance auditing, AST classifier tagging, and CLAP semantic embeddings.
"""

from __future__ import annotations
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from audiobook_factory.logger import logger
from audiobook_factory.contracts import (
    SonicGenome,
    MeasuredAudioFacts,
    SourceMetadata,
    NormalizedSourceFields,
    ProvenanceRecord,
    AudioEventRecord,
    ClassifierInferences,
    ClassifierPrediction,
    SemanticEmbeddingFacts,
)
from audiobook_factory.deterministic_audio_analyzer import (
    DeterministicAudioAnalyzer,
    ANALYZER_VERSION,
    ANALYZER_ID,
    ONTOLOGY_VERSION,
)


class DSPMetricsMixin:
    """DSP measurement and Sonic Genome enrichment mixin for SoundBank."""

    audio_analyzer: DeterministicAudioAnalyzer

    def analyze_local_audio(self, filepath: Union[Path, str]) -> Tuple[MeasuredAudioFacts, List[AudioEventRecord]]:
        """
        Runs deterministic audio analysis on a local audio file.
        Returns measured physical facts and detected audio events with full provenance.
        """
        return self.audio_analyzer.analyze_file(Path(filepath).resolve())

    def enrich_asset(self, sound_id: int, force: bool = False) -> SonicGenome:
        """
        Enriches an asset in sound_catalog with deterministic audio analysis.
        Extracts format, EBU R128 loudness, spectral features, temporal boundaries,
        and conservative tonal facts.
        """
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            if not row:
                raise ValueError(f"Sound asset ID {sound_id} not found in sound_catalog.")

        row_dict = dict(row)
        filepath_str = row_dict.get("filepath")
        local_path = Path(filepath_str).resolve() if filepath_str else None

        raw_genome_str = row_dict.get("sonic_genome") or "{}"
        try:
            genome_dict = json.loads(raw_genome_str) if isinstance(raw_genome_str, str) else raw_genome_str
            if not isinstance(genome_dict, dict):
                genome_dict = {}
        except Exception:
            genome_dict = {}

        current_version = row_dict.get("analysis_version") or ""
        if not force and current_version == ANALYZER_VERSION and row_dict.get("last_analyzed_at"):
            try:
                genome_dict["track_id"] = sound_id
                genome_dict["filename"] = row_dict.get("filename", "")
                return SonicGenome.model_validate(genome_dict)
            except Exception:
                pass

        if not local_path or not local_path.exists() or local_path.stat().st_size == 0:
            genome_dict["track_id"] = sound_id
            genome_dict["filename"] = row_dict.get("filename", "")
            genome_dict["version"] = "2.1"
            return SonicGenome.model_validate(genome_dict)

        facts, events = self.audio_analyzer.analyze_file(local_path)

        try:
            genome = SonicGenome.model_validate(genome_dict)
            genome.version = "2.1"
        except Exception:
            genome = SonicGenome(
                version="2.1",
                track_id=sound_id,
                filename=row_dict.get("filename", local_path.name),
            )

        genome.track_id = sound_id
        genome.filename = row_dict.get("filename", local_path.name)
        genome.measured_facts = facts
        genome.events = events
        genome.sync_measured_to_acoustic()

        genome.provenance_ledger.append(facts.provenance)
        genome.provenance_log.append({
            "source_method": facts.provenance.source_method,
            "analyzer_id": facts.provenance.analyzer_id,
            "analyzer_version": facts.provenance.analyzer_version,
            "timestamp": facts.provenance.generated_at,
            "confidence": None,
        })

        if row_dict.get("source_collection") or row_dict.get("source_url"):
            genome.source_metadata.provider_name = row_dict.get("source_collection") or "local"
            genome.source_metadata.normalized.title = row_dict.get("title") or ""
            genome.source_metadata.normalized.description = row_dict.get("description") or ""
            genome.source_metadata.normalized.category = row_dict.get("category") or "SFX"
            genome.source_metadata.normalized.subcategory = row_dict.get("subcategory") or "General"
            genome.source_metadata.normalized.mood = row_dict.get("mood") or "default"
            genome.source_metadata.normalized.source_url = row_dict.get("source_url")
            genome.source_metadata.normalized.license = row_dict.get("license") or "Royalty-Free"

        genome.inferred.category = row_dict.get("category") or "SFX"
        genome.inferred.action_type = row_dict.get("action_type") or ""
        genome.inferred.exciter = row_dict.get("exciter") or ""
        genome.inferred.resonator = row_dict.get("resonator") or ""

        genome_json = genome.model_dump_json()

        with self._get_conn() as conn:
            conn.execute("""
                UPDATE sound_catalog
                SET size_bytes = ?, duration_sec = ?, format = ?,
                    sample_rate = ?, channels = ?, bit_depth = ?,
                    integrated_lufs = ?, true_peak_db = ?, loudness_range_lu = ?, rms_level_db = ?,
                    spectral_centroid_hz = ?, spectral_bandwidth_hz = ?, spectral_rolloff_hz = ?,
                    spectral_flatness = ?, zero_crossing_rate = ?, silence_ratio = ?,
                    analysis_version = ?, last_analyzed_at = CURRENT_TIMESTAMP,
                    sonic_genome = ?
                WHERE id = ?
            """, (
                facts.format.file_size_bytes,
                facts.format.duration_sec,
                facts.format.container,
                facts.format.sample_rate,
                facts.format.channels,
                facts.format.bit_depth,
                facts.loudness.integrated_lufs,
                facts.loudness.true_peak_dbtp,
                facts.loudness.loudness_range_lu,
                facts.loudness.rms_level_db,
                facts.spectral.spectral_centroid_hz,
                facts.spectral.spectral_bandwidth_hz,
                facts.spectral.spectral_rolloff_hz,
                facts.spectral.spectral_flatness,
                facts.spectral.zero_crossing_rate,
                facts.temporal.silence_ratio,
                ANALYZER_VERSION,
                genome_json,
                sound_id,
            ))

            conn.execute("""
                INSERT INTO sound_analysis_runs (
                    track_id, analyzer_id, analyzer_version, analysis_stage,
                    execution_status, error_message, measured_facts, provenance_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sound_id,
                ANALYZER_ID,
                ANALYZER_VERSION,
                "MEASURED_AUDIO_FACTS",
                "SUCCESS",
                None,
                facts.model_dump_json(),
                facts.provenance.model_dump_json(),
            ))

            conn.execute("""
                DELETE FROM sound_temporal_events
                WHERE track_id = ? AND detector_id IN ('frame_energy_gate_v1', 'energy_flux_detector_v1')
            """, (sound_id,))

            for ev in events:
                conn.execute("""
                    INSERT INTO sound_temporal_events (
                        track_id, event_type, start_sec, end_sec, confidence,
                        source_method, detector_id, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sound_id,
                    ev.event_type,
                    ev.start_sec,
                    ev.end_sec,
                    ev.confidence,
                    ev.source_method,
                    ev.detector_id,
                    json.dumps(ev.metadata),
                ))

        return genome

    def get_sonic_genome(self, sound_id: int) -> Optional[SonicGenome]:
        """Retrieves the typed SonicGenome v2.1 for a sound catalog record."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            if not row:
                return None
            row_dict = dict(row)

        g_str = row_dict.get("sonic_genome") or "{}"
        try:
            g_dict = json.loads(g_str) if isinstance(g_str, str) else g_str
            if not isinstance(g_dict, dict):
                g_dict = {}
        except Exception:
            g_dict = {}

        g_dict["track_id"] = sound_id
        g_dict["filename"] = row_dict.get("filename", "")
        if "version" not in g_dict:
            g_dict["version"] = "2.1"

        try:
            return SonicGenome.model_validate(g_dict)
        except Exception as e:
            logger.debug(f"Failed to parse SonicGenome for track {sound_id}: {e}")
            return SonicGenome(track_id=sound_id, filename=row_dict.get("filename", ""))

    def get_asset_provenance(self, sound_id: int) -> List[Dict[str, Any]]:
        """Retrieves complete audit-trail provenance records for an asset across all analysis runs."""
        records: List[Dict[str, Any]] = []
        with self._get_conn() as conn:
            cur = conn.execute("""
                SELECT id, track_id, analyzer_id, analyzer_version, analysis_stage,
                       execution_status, error_message, provenance_data, created_at
                FROM sound_analysis_runs
                WHERE track_id = ?
                ORDER BY created_at DESC
            """, (sound_id,))
            for r in cur.fetchall():
                row_d = dict(r)
                if row_d.get("provenance_data"):
                    try:
                        row_d["provenance_data"] = json.loads(row_d["provenance_data"])
                    except Exception:
                        pass
                records.append(row_d)
        return records

    def rerun_analysis(self, sound_id: int, force: bool = True) -> SonicGenome:
        """Safely recomputes deterministic audio analysis without duplicating records."""
        return self.enrich_asset(sound_id=sound_id, force=force)

    def ingest_source_metadata(self, item: Dict[str, Any], source_name: str) -> int:
        """
        Ingests source metadata for an asset into sound_catalog, preserving raw fields
        and recording the run in sound_analysis_runs.
        """
        fname = item.get("filename")
        if not fname:
            raise ValueError("Item must contain a 'filename'")

        title = item.get("title", "")
        desc = item.get("description", "")
        cat = item.get("category", "SFX")
        subcat = item.get("subcategory", "General")
        mood = item.get("mood", "default")
        tags = item.get("tags", "")
        dur = float(item.get("duration_sec") or 0.0)
        source_url = item.get("source_url")
        mirror_url = item.get("mirror_url")
        source_page = item.get("source_page_url")
        license_str = item.get("license", "Royalty-Free")
        creator = item.get("creator_attribution", "")
        tempo = float(item.get("tempo_bpm") or 0.0)

        src_meta = SourceMetadata(
            provider_name=source_name,
            raw_metadata=item.get("raw_metadata") or item,
            normalized=NormalizedSourceFields(
                title=title,
                description=desc,
                tags=tags.split() if isinstance(tags, str) else list(tags),
                category=cat,
                subcategory=subcat,
                creator=creator,
                collection=source_name,
                mood=mood,
                tempo_bpm=tempo if tempo > 0 else None,
                duration_sec=dur,
                source_url=source_url,
                license=license_str,
                provider_id=str(item.get("id") or item.get("isrc") or fname),
            ),
            provenance=ProvenanceRecord(
                source_method="source_metadata",
                analyzer_id=f"{source_name.lower()}_adapter",
                analyzer_version="1.0.0",
                confidence=None,
            )
        )

        genome = SonicGenome(
            version="2.1",
            filename=fname,
            source_metadata=src_meta,
        )
        genome.provenance_ledger.append(src_meta.provenance)
        genome_json = genome.model_dump_json()

        with self._get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO sound_catalog (
                    filename, filepath, title, description, category, subcategory,
                    mood, tags, duration_sec, source_collection, license, creator_attribution,
                    source_url, mirror_url, source_page_url, url_status, is_downloaded,
                    tempo_bpm, sonic_genome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unverified', 0, ?, ?)
                RETURNING id;
            """, (
                fname, f"virtual/{source_name.lower()}/{fname}", title, desc, cat, subcat,
                mood, tags, dur, source_name, license_str, creator,
                source_url, mirror_url, source_page, tempo, genome_json
            ))
            track_id = cur.fetchone()[0]

            conn.execute("""
                INSERT INTO sound_analysis_runs (
                    track_id, analyzer_id, analyzer_version, analysis_stage,
                    execution_status, measured_facts, provenance_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                track_id,
                f"{source_name.lower()}_adapter",
                "1.0.0",
                "SOURCE_METADATA",
                "SUCCESS",
                "{}",
                src_meta.provenance.model_dump_json(),
            ))

        return track_id

    def enrich_asset_phase2(
        self,
        sound_id: int,
        force: bool = False,
        run_classifier: bool = True,
        run_clap: bool = True,
    ) -> Optional[SonicGenome]:
        """
        Phase 2 AI Enrichment: Runs dedicated audio classifiers (AST AudioSet 527)
        and CLAP semantic embeddings (512-d).
        """
        import numpy as np

        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            if not row:
                raise ValueError(f"Sound track ID {sound_id} not found in sound_catalog")
            row_dict = dict(row)

        if not force:
            with self._get_conn() as conn:
                existing_run = conn.execute("""
                    SELECT execution_status FROM sound_analysis_runs
                    WHERE track_id = ? AND analysis_stage = 'PHASE2_AI_ENRICHMENT' AND execution_status = 'SUCCESS'
                """, (sound_id,)) .fetchone()
                if existing_run:
                    return self.get_sonic_genome(sound_id)

        file_path_str = row_dict.get("filepath")
        resolved_path: Optional[Path] = None
        if file_path_str:
            p = Path(file_path_str)
            if p.exists() and p.stat().st_size > 0:
                resolved_path = p

        if resolved_path is None and row_dict.get("source_url"):
            resolved_path = self.download_virtual_asset(sound_id)

        if resolved_path is None or not resolved_path.exists():
            error_msg = f"Audio file not accessible on disk for track {sound_id} ({file_path_str})"
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO sound_analysis_runs (
                        track_id, analyzer_id, analyzer_version, analysis_stage,
                        execution_status, error_message, measured_facts, provenance_data
                    ) VALUES (?, 'phase2_orchestrator', '1.0.0', 'PHASE2_AI_ENRICHMENT', 'FAILED', ?, '{}', '{}')
                """, (sound_id, error_msg))
            raise FileNotFoundError(error_msg)

        import soundfile as sf
        waveform = None
        sr = 48000
        duration_sec = 0.0

        try:
            waveform, sr = sf.read(str(resolved_path), dtype="float32", always_2d=False)
            if waveform.ndim > 1:
                waveform = np.mean(waveform, axis=0 if waveform.shape[0] < waveform.shape[1] else 1)
            duration_sec = float(len(waveform) / sr)
        except Exception:
            try:
                import librosa
                waveform, sr = librosa.load(str(resolved_path), sr=None, mono=True)
                duration_sec = float(len(waveform) / sr)
            except Exception:
                ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
                try:
                    cmd = [
                        ffmpeg, "-v", "error", "-i", str(resolved_path),
                        "-f", "f32le", "-ac", "1", "-ar", "48000", "-"
                    ]
                    res = subprocess.run(cmd, capture_output=True, timeout=25.0)
                    if res.returncode == 0 and res.stdout:
                        waveform = np.frombuffer(res.stdout, dtype=np.float32)
                        sr = 48000
                        duration_sec = float(len(waveform) / sr)
                    else:
                        raise RuntimeError(res.stderr.decode("utf-8", errors="ignore"))
                except Exception as e3:
                    error_msg = f"Failed to decode audio for track {sound_id}: {e3}"
                    with self._get_conn() as conn:
                        conn.execute("""
                            INSERT INTO sound_analysis_runs (
                                track_id, analyzer_id, analyzer_version, analysis_stage,
                                execution_status, error_message, measured_facts, provenance_data
                            ) VALUES (?, 'phase2_orchestrator', '1.0.0', 'PHASE2_AI_ENRICHMENT', 'FAILED', ?, '{}', '{}')
                        """, (sound_id, error_msg))
                    raise RuntimeError(error_msg)

        from audiobook_factory.audio_classifier_adapters import ASTClassifierAdapter
        from audiobook_factory.clap_semantic_adapter import CLAPSemanticAdapter

        classifier_inferences: Optional[ClassifierInferences] = None
        temporal_events: List[AudioEventRecord] = []
        classifier_err: Optional[str] = None

        if run_classifier:
            try:
                adapter = ASTClassifierAdapter()
                classifier_inferences = adapter.classify(waveform, sr, duration_sec)
                temporal_events = adapter.detect_temporal_events(waveform, sr, duration_sec)
            except Exception as e:
                logger.warning(f"Phase 2 Classifier encountered error for track {sound_id}: {e}")
                classifier_err = str(e)

        clap_vector: Optional[np.ndarray] = None
        clap_facts: Optional[SemanticEmbeddingFacts] = None
        clap_err: Optional[str] = None

        if run_clap:
            try:
                clap_adapter = CLAPSemanticAdapter()
                clap_vector, clap_facts = clap_adapter.embed_audio(waveform, sr, duration_sec)
            except Exception as e:
                logger.warning(f"Phase 2 CLAP embedding encountered error for track {sound_id}: {e}")
                clap_err = str(e)

        if classifier_err and clap_err:
            overall_status = "FAILED"
            error_message = f"Classifier: {classifier_err} | CLAP: {clap_err}"
        elif classifier_err or clap_err:
            overall_status = "PARTIAL"
            error_message = f"Classifier: {classifier_err}" if classifier_err else f"CLAP: {clap_err}"
        else:
            overall_status = "SUCCESS"
            error_message = None

        genome = self.get_sonic_genome(sound_id) or SonicGenome(track_id=sound_id, filename=row_dict.get("filename", ""))
        genome.record_ai_inference(
            classifier=classifier_inferences,
            semantic=clap_facts,
            events=temporal_events,
        )
        genome_json = genome.model_dump_json()

        with self._get_conn() as conn:
            conn.execute("UPDATE sound_catalog SET sonic_genome = ? WHERE id = ?", (genome_json, sound_id))

            if classifier_inferences:
                conn.execute("DELETE FROM sound_classifier_tags WHERE track_id = ?", (sound_id,))
                for pred in classifier_inferences.predictions:
                    conn.execute("""
                        INSERT INTO sound_classifier_tags (
                            track_id, model_id, model_version, ontology_id,
                            raw_label, normalized_label, raw_score, calibrated_score,
                            rank, start_sec, end_sec, source_method
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sound_id,
                        classifier_inferences.model_id,
                        classifier_inferences.model_version,
                        classifier_inferences.ontology_id,
                        pred.raw_label,
                        pred.normalized_label,
                        pred.raw_score,
                        pred.calibrated_score,
                        pred.rank,
                        pred.start_sec,
                        pred.end_sec,
                        "classifier",
                    ))

                conn.execute("""
                    DELETE FROM sound_temporal_events
                    WHERE track_id = ? AND source_method = 'classifier'
                """, (sound_id,))
                for ev in temporal_events:
                    conn.execute("""
                        INSERT INTO sound_temporal_events (
                            track_id, event_type, start_sec, end_sec,
                            confidence, source_method, detector_id, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        sound_id,
                        ev.event_type,
                        ev.start_sec,
                        ev.end_sec,
                        ev.confidence,
                        ev.source_method,
                        ev.detector_id,
                        json.dumps(ev.metadata),
                    ))

            if clap_vector is not None and clap_facts is not None:
                embedding_bytes = clap_vector.tobytes()
                conn.execute("""
                    INSERT OR REPLACE INTO sound_embeddings (
                        track_id, model_id, model_version, embedding_dim,
                        embedding_bytes, preprocessing_version, source_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    sound_id,
                    clap_facts.model_id,
                    clap_facts.model_version,
                    clap_facts.embedding_dim,
                    embedding_bytes,
                    clap_facts.preprocessing_version,
                    "semantic_model",
                ))

            conn.execute("""
                INSERT INTO sound_analysis_runs (
                    track_id, analyzer_id, analyzer_version, analysis_stage,
                    execution_status, error_message, measured_facts, provenance_data
                ) VALUES (?, 'phase2_ai_orchestrator', '1.0.0', 'PHASE2_AI_ENRICHMENT', ?, ?, ?, ?)
            """, (
                sound_id,
                overall_status,
                error_message,
                json.dumps({
                    "has_classifier": classifier_inferences is not None,
                    "has_clap": clap_vector is not None,
                    "top_classifier_label": classifier_inferences.top_labels[0] if classifier_inferences and classifier_inferences.top_labels else None,
                }),
                json.dumps([p.model_dump(mode="json") for p in genome.provenance_ledger[-2:]]),
            ))

        return genome
