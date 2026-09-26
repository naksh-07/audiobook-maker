#!/usr/bin/env python3
"""
Sonic Asset Inspection & Export Module (Sonic Intelligence Engine Hardened).
============================================================================
Provides deterministic, non-invasive inspection and complete canonical
export of an asset's Sonic Genome, Agent Sound Card, classifier inferences,
SED intervals, CLAP embedding metadata, and provenance ledger.

Strict Epistemic Transparency Hierarchy:
MEASURED > CLASSIFIER > EMBEDDING > DERIVED > HEURISTIC > DEFAULT/FALLBACK

Exposes only already-computed, stored, or canonical data.
Does NOT compute new features or mutate system state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from audiobook_factory.logger import logger
from audiobook_factory.sound_bank import SoundBank, get_sound_bank
from audiobook_factory.sonic_intelligence_engine import (
    SonicIntelligenceEngine,
    get_sonic_intelligence_engine,
)
from audiobook_factory.contracts import SonicGenome
from audiobook_factory.agent_sound_card import AgentSoundCard


class SonicAssetInspector:
    """
    Non-destructive inspector that aggregates all existing telemetry,
    DSP measurements, AI inferences, and provenance for a given sound asset.
    """

    def __init__(
        self,
        bank: Optional[SoundBank] = None,
        engine: Optional[SonicIntelligenceEngine] = None,
    ) -> None:
        self.bank = bank or get_sound_bank()
        self.engine = engine or get_sonic_intelligence_engine(sound_bank=self.bank)

    def inspect_asset(self, sound_id: int) -> Dict[str, Any]:
        """
        Collects all existing data for track `sound_id` across:
        - Catalog and source metadata
        - Technical audio format
        - Measured DSP & Sonic Genome (loudness, spectral, temporal)
        - Temporal events & SED intervals
        - AudioSet / classifier predictions
        - CLAP embedding metadata
        - Provenance ledger & analysis runs
        - Agent Sound Card v3.0 (with strict epistemic badges)
        """
        # 1. Fetch raw catalog record
        with self.bank._get_conn() as conn:
            row = conn.execute("SELECT * FROM sound_catalog WHERE id = ?", (sound_id,)).fetchone()
            if not row:
                raise ValueError(f"Asset ID #{sound_id} not found in sound_catalog database.")
            cat_row = dict(row)

            # Fetch related runs
            run_rows = conn.execute("""
                SELECT id, track_id, analyzer_id, analyzer_version, analysis_stage,
                       execution_status, error_message, provenance_data, created_at
                FROM sound_analysis_runs
                WHERE track_id = ?
                ORDER BY created_at ASC
            """, (sound_id,)).fetchall()
            runs = []
            for r in run_rows:
                rd = dict(r)
                if rd.get("provenance_data"):
                    try:
                        rd["provenance_data"] = json.loads(rd["provenance_data"])
                    except Exception:
                        pass
                runs.append(rd)

            # Fetch classifier tags
            tag_rows = conn.execute("""
                SELECT id, model_id, model_version, ontology_id, raw_label, normalized_label,
                       raw_score, calibrated_score, rank, start_sec, end_sec, source_method, created_at
                FROM sound_classifier_tags
                WHERE track_id = ?
                ORDER BY rank ASC
            """, (sound_id,)).fetchall()
            tags = [dict(r) for r in tag_rows]

            # Fetch temporal events
            event_rows = conn.execute("""
                SELECT id, track_id, event_type, start_sec, end_sec, confidence,
                       source_method, detector_id, metadata, created_at
                FROM sound_temporal_events
                WHERE track_id = ?
                ORDER BY start_sec ASC
            """, (sound_id,)).fetchall()
            events = []
            for ev in event_rows:
                ev_d = dict(ev)
                if ev_d.get("metadata"):
                    try:
                        ev_d["metadata"] = json.loads(ev_d["metadata"])
                    except Exception:
                        pass
                events.append(ev_d)

            # Fetch embedding metadata
            emb_row = conn.execute("""
                SELECT id, model_id, model_version, embedding_dim, embedding_bytes,
                       preprocessing_version, source_method, created_at
                FROM sound_embeddings
                WHERE track_id = ?
                ORDER BY id DESC LIMIT 1
            """, (sound_id,)).fetchone()

            embedding_meta = None
            if emb_row:
                b = emb_row["embedding_bytes"]
                vec = np.frombuffer(b, dtype=np.float32) if b else None
                norm_val = float(np.linalg.norm(vec)) if vec is not None and len(vec) > 0 else None
                preview = [round(float(x), 5) for x in vec[:5]] if vec is not None and len(vec) >= 5 else None

                embedding_meta = {
                    "embedding_id": emb_row["id"],
                    "model_id": emb_row["model_id"],
                    "model_version": emb_row["model_version"],
                    "embedding_dim": emb_row["embedding_dim"],
                    "byte_size": len(b) if b else 0,
                    "l2_norm": round(norm_val, 5) if norm_val is not None else None,
                    "unit_norm_verified": abs(norm_val - 1.0) < 1e-3 if norm_val is not None else False,
                    "preprocessing_version": emb_row["preprocessing_version"],
                    "source_method": emb_row["source_method"],
                    "created_at": emb_row["created_at"],
                    "vector_sample_head": preview,
                }

            # Fetch asset relationships if present
            rel_rows = conn.execute("""
                SELECT target_asset_id, relationship_type, confidence, created_at
                FROM sound_asset_relationships
                WHERE source_asset_id = ?
            """, (sound_id,)).fetchall()
            relationships = [dict(r) for r in rel_rows]

        # 2. Retrieve Canonical Sonic Genome model
        genome = self.bank.get_sonic_genome(sound_id)
        genome_dict = genome.model_dump(mode="json") if genome else None

        # 3. Retrieve Agent Sound Card v3.0 (with epistemic badges)
        sound_card = self.engine.get_sound_card(sound_id)
        sound_card_dict = sound_card.to_dict() if sound_card else None
        sound_card_md = sound_card.to_agent_markdown() if sound_card else ""

        # 4. Synthesize complete canonical data payload
        measured = genome.measured_facts if genome else None

        inspection_payload: Dict[str, Any] = {
            "schema_version": "1.0-export-hardened",
            "asset_id": sound_id,
            "filename": cat_row.get("filename"),
            "filepath": cat_row.get("filepath"),
            "source_and_catalog_metadata": {
                "title": cat_row.get("title") or cat_row.get("filename"),
                "description": cat_row.get("description"),
                "category": cat_row.get("category"),
                "subcategory": cat_row.get("subcategory"),
                "source_collection": cat_row.get("source_collection"),
                "license": cat_row.get("license"),
                "creator_attribution": cat_row.get("creator_attribution"),
                "source_url": cat_row.get("source_url"),
                "source_page_url": cat_row.get("source_page_url"),
                "mirror_url": cat_row.get("mirror_url"),
                "is_downloaded": bool(cat_row.get("is_downloaded")),
                "raw_tags": [t for t in (cat_row.get("tags") or "").split() if t],
                "created_at": cat_row.get("created_at"),
                "last_accessed_at": cat_row.get("last_accessed_at"),
                "last_analyzed_at": cat_row.get("last_analyzed_at"),
                "analysis_version": cat_row.get("analysis_version"),
            },
            "technical_audio_format": {
                "duration_sec": (measured.format.duration_sec if measured else None) or cat_row.get("duration_sec"),
                "container_format": (measured.format.container if measured else None) or cat_row.get("format"),
                "codec": measured.format.codec if measured else None,
                "sample_rate_hz": (measured.format.sample_rate if measured else None) or cat_row.get("sample_rate"),
                "channels": (measured.format.channels if measured else None) or cat_row.get("channels"),
                "bit_depth": (measured.format.bit_depth if measured else None) or cat_row.get("bit_depth"),
                "bitrate_bps": measured.format.bit_rate if measured else None,
                "file_size_bytes": (measured.format.file_size_bytes if measured else None) or cat_row.get("size_bytes"),
            },
            "loudness_and_dynamics": {
                "integrated_lufs": (measured.loudness.integrated_lufs if measured else None) or cat_row.get("integrated_lufs"),
                "true_peak_dbtp": (measured.loudness.true_peak_dbtp if measured else None) or cat_row.get("true_peak_db"),
                "loudness_range_lu": (measured.loudness.loudness_range_lu if measured else None) or cat_row.get("loudness_range_lu"),
                "rms_level_db": (measured.loudness.rms_level_db if measured else None) or cat_row.get("rms_level_db"),
                "peak_level_db": measured.loudness.peak_level_db if measured else None,
                "dynamic_range_db": measured.loudness.dynamic_range_db if measured else None,
            },
            "spectral_and_acoustic": {
                "spectral_centroid_hz": (measured.spectral.spectral_centroid_hz if measured else None) or cat_row.get("spectral_centroid_hz"),
                "spectral_bandwidth_hz": (measured.spectral.spectral_bandwidth_hz if measured else None) or cat_row.get("spectral_bandwidth_hz"),
                "spectral_rolloff_hz": (measured.spectral.spectral_rolloff_hz if measured else None) or cat_row.get("spectral_rolloff_hz"),
                "spectral_flatness": (measured.spectral.spectral_flatness if measured else None) or cat_row.get("spectral_flatness"),
                "zero_crossing_rate": (measured.spectral.zero_crossing_rate if measured else None) or cat_row.get("zero_crossing_rate"),
                "spectral_brightness": sound_card.spectral_brightness if sound_card else cat_row.get("wave_style"),
                "speech_corridor_density": genome.acoustic.speech_corridor_density if genome else None,
                "vocal_clash_risk": genome.acoustic.vocal_clash_risk if genome else cat_row.get("voice_masking_risk"),
            },
            "temporal_and_events": {
                "active_region_str": sound_card.active_region_str if sound_card else "unavailable (unmeasured)",
                "silence_ratio": (measured.temporal.silence_ratio if measured else None) or cat_row.get("silence_ratio"),
                "active_duration_sec": measured.temporal.active_duration_sec if measured else None,
                "active_start_sec": measured.temporal.active_start_sec if measured else None,
                "active_end_sec": measured.temporal.active_end_sec if measured else None,
                "transient_count": measured.temporal.transient_count if measured else None,
                "energy_envelope": measured.temporal.energy_envelope if measured else cat_row.get("temporal_character"),
                "major_transients_sec": measured.temporal.major_transients_sec if measured else [],
                "temporal_events_count": len(events),
                "temporal_events": events,
            },
            "music_metadata": {
                "bpm_str": sound_card.bpm_str if sound_card else "unavailable (unmeasured)",
                "tempo_bpm": (measured.tonal.detected_bpm if measured else None) or cat_row.get("tempo_bpm") or (genome.acoustic.bpm if genome else None),
                "is_tonal": sound_card.is_tonal if sound_card else (measured.tonal.is_tonal if measured else None),
                "is_tonal_str": sound_card.is_tonal_str if sound_card else "unavailable (unmeasured)",
                "detected_pitch_hz": (measured.tonal.detected_pitch_hz if measured else None),
                "tuning_hz": (measured.tonal.tuning_hz if measured else None),
                "key_tonality_str": sound_card.key_tonality_str if sound_card else "unavailable (unmeasured)",
                "time_signature_str": sound_card.time_signature_str if sound_card else "unavailable (unmeasured)",
                "musical_sections": genome.music.structure_sections if genome else [],
            },
            "psychoacoustics_and_mix_safety": {
                "dramatic_role": sound_card.dramatic_role if sound_card else "UNASSIGNED",
                "dramatic_role_evidence": sound_card.dramatic_role_evidence if sound_card else "[AWAITING_AGENT_EVALUATION]",
                "scene_purpose": sound_card.scene_purpose if sound_card else "UNASSIGNED",
                "scene_purpose_evidence": sound_card.scene_purpose_evidence if sound_card else "[AGENT_INTERPRETATION: Awaiting SoundDirector]",
                "mood": sound_card.mood if sound_card else "UNINTERPRETED",
                "mood_evidence": sound_card.mood_evidence if sound_card else "[AWAITING_AGENT_EVALUATION]",
                "emotional_suitability": sound_card.emotional_suitability if sound_card else "UNINTERPRETED",
                "emotional_suitability_evidence": sound_card.emotional_suitability_evidence if sound_card else "[AWAITING_AGENT_EVALUATION]",
                "source_mood": sound_card.source_mood if sound_card else None,
                "classifier_mood": sound_card.classifier_mood if sound_card else None,
                "speech_corridor_density": sound_card.speech_corridor_density if sound_card else None,
                "vocal_speech_probability": sound_card.vocal_speech_probability if sound_card else None,
                "voice_masking_judgment": sound_card.voice_masking_judgment if sound_card else "UNASSESSED",
                "voice_masking_risk": sound_card.voice_masking_risk if sound_card else "UNASSESSED",
                "voice_masking_evidence": sound_card.voice_masking_evidence if sound_card else "[AWAITING_MIX_AGENT_EVALUATION]",
                "whisper_compatibility": sound_card.whisper_compatibility if sound_card else None,
                "whisper_compatibility_evidence": sound_card.whisper_compatibility_evidence if sound_card else "[NOT_CALIBRATED]",
                "dialogue_ducking_amount_db": sound_card.dialogue_ducking_amount_db if sound_card else None,
                "recommended_ducking_db": sound_card.recommended_ducking_db if sound_card else None,
                "recommended_ducking_evidence": sound_card.recommended_ducking_evidence if sound_card else "[SCENE_DEPENDENT / DEFERRED_TO_MIX_AGENT]",
                "placement_usage": sound_card.placement_usage if sound_card else "UNASSIGNED",
                "placement_usage_evidence": sound_card.placement_usage_evidence if sound_card else "[AGENT_INTERPRETATION: Awaiting SoundDirector]",
                "final_taxonomy": sound_card.final_taxonomy if sound_card else "UNASSIGNED",
                "final_taxonomy_evidence": sound_card.final_taxonomy_evidence if sound_card else "[AGENT_INTERPRETATION: Awaiting creative interpretation]",
                "physical_action": cat_row.get("action_type") or "unspecified",
                "exciter": cat_row.get("exciter") or "unspecified",
                "resonator": cat_row.get("resonator") or "unspecified",
                "surface": cat_row.get("surface") or "unspecified",
                "acoustic_space": cat_row.get("acoustic_space") or "unspecified",
                "reverb_character": cat_row.get("reverb_character") or "unspecified",
                "agent_interpretation": sound_card.agent_interpretation.model_dump(mode="json") if (sound_card and sound_card.agent_interpretation) else None,
            },
            "classifier_inferences": {
                "model_id": tags[0]["model_id"] if tags else "MIT/ast-finetuned-audioset-10-10-0.4593",
                "model_version": tags[0]["model_version"] if tags else "audioset_527",
                "predictions_count": len(tags),
                "top_predictions": tags,
            },
            "clap_semantic_embedding": embedding_meta,
            "provenance_and_audit_runs": {
                "total_runs": len(runs),
                "runs": runs,
            },
            "relationships": relationships,
            "agent_sound_card": {
                "card_dict": sound_card_dict,
                "rendered_markdown": sound_card_md,
            },
            "canonical_sonic_genome_raw": genome_dict,
        }

        return inspection_payload

    def export_asset(
        self,
        sound_id: int,
        output_dir: Union[str, Path] = "exports/sonic_inspections",
    ) -> Tuple[Path, Path]:
        """
        Inspects an asset and writes out:
        1. `<output_dir>/sound_asset_<id>.json` (Full Canonical JSON)
        2. `<output_dir>/sound_asset_<id>.md` (Human/AI Readable Markdown View)
        """
        payload = self.inspect_asset(sound_id)
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        json_file = out_path / f"sound_asset_{sound_id}.json"
        md_file = out_path / f"sound_asset_{sound_id}.md"

        # 1. Write structured JSON
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        # 2. Write Markdown view
        md_content = self.render_markdown_view(payload)
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"Successfully exported asset #{sound_id} -> JSON: {json_file}, MD: {md_file}")
        return json_file, md_file

    def render_markdown_view(self, payload: Dict[str, Any]) -> str:
        """Renders an intuitive, high-density Markdown representation of the complete inspection."""
        sid = payload["asset_id"]
        fn = payload["filename"]
        cat_meta = payload["source_and_catalog_metadata"]
        fmt = payload["technical_audio_format"]
        loud = payload["loudness_and_dynamics"]
        spec = payload["spectral_and_acoustic"]
        temp = payload["temporal_and_events"]
        music = payload["music_metadata"]
        mix = payload["psychoacoustics_and_mix_safety"]
        cls_inf = payload["classifier_inferences"]
        clap = payload["clap_semantic_embedding"]
        prov = payload["provenance_and_audit_runs"]
        card = payload.get("agent_sound_card", {})

        # Classifier table
        cls_table_lines = [
            "| Rank | Normalized Label | Raw AudioSet Label | Confidence | Time Window |",
            "|:---:|---|---|:---:|:---:|",
        ]
        top_tags = cls_inf.get("top_predictions", [])[:10]
        if top_tags:
            for t in top_tags:
                norm_lbl = t.get("normalized_label") or "—"
                raw_lbl = t.get("raw_label") or "—"
                score = f"{t.get('raw_score', 0.0):.3f}"
                win = f"{t.get('start_sec', 0.0):.1f}s - {t.get('end_sec', 0.0):.1f}s" if t.get("start_sec") is not None else "Global"
                cls_table_lines.append(f"| #{t.get('rank', 1)} | `{norm_lbl}` | {raw_lbl} | **{score}** | {win} |")
        else:
            cls_table_lines.append("| — | *(No classifier tags stored)* | — | — | — |")
        cls_table = "\n".join(cls_table_lines)

        # Deduplicate and group temporal events by window with informative label names
        events = temp.get("temporal_events", [])
        event_lines = []
        if events:
            # Group classifier events by window
            cls_by_window: Dict[Tuple[float, float], List[str]] = {}
            active_spans = []
            transient_spans = []

            for ev in events:
                ev_type = ev.get("event_type")
                st = round(float(ev.get("start_sec") or 0.0), 2)
                et = round(float(ev.get("end_sec") or 0.0), 2)
                det = ev.get("detector_id", "unknown")

                if ev_type in ("classifier_observation_window", "classifier_event"):
                    meta = ev.get("metadata") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    lbl = meta.get("normalized_label") or meta.get("raw_label") or "event"
                    conf = ev.get("confidence") or 0.0
                    cls_by_window.setdefault((st, et), []).append(f"`{lbl}` ({conf:.2f})")
                elif ev_type == "active_region":
                    active_spans.append(f"- `[{st:.2f}s - {et:.2f}s]` **Active Audio Region** [MEASURED DSP, Detector: `{det}`]")
                elif ev_type == "transient_onset":
                    transient_spans.append(f"`{st:.2f}s`")

            # Output active region first
            for a in active_spans:
                event_lines.append(a)

            # Output aggregated classifier observation windows
            for (w_st, w_et), lbls in list(cls_by_window.items())[:6]:
                event_lines.append(f"- `[{w_st:.2f}s - {w_et:.2f}s]` **Classifier Observation Window**: {', '.join(lbls[:3])} [CLASSIFIER INFERENCE]")

            if len(cls_by_window) > 6:
                event_lines.append(f"- *(... and {len(cls_by_window) - 6} more classifier observation windows in JSON)*")

            # Output transient summary
            if transient_spans:
                onsets_str = ", ".join(transient_spans[:8])
                if len(transient_spans) > 8:
                    onsets_str += f", ... ({len(transient_spans)} total)"
                event_lines.append(f"- **Transient Onsets [MEASURED DSP]**: [{onsets_str}]")

        if not event_lines:
            event_lines.append("- *(No discrete temporal events detected)*")
        event_block = "\n".join(event_lines)

        # Runs ledger
        run_lines = []
        for r in prov.get("runs", []):
            st = r.get("execution_status", "UNKNOWN")
            run_lines.append(f"- **{r.get('analyzer_id')}** (`v{r.get('analyzer_version')}`) | Stage: `{r.get('analysis_stage')}` | Status: `{st}` | Date: `{r.get('created_at')}`")
        runs_block = "\n".join(run_lines) if run_lines else "- *(No analysis runs logged)*"

        # CLAP summary
        if clap:
            clap_summary = (
                f"- **Model**: `{clap.get('model_id')}` (Version: `{clap.get('model_version')}`)\n"
                f"- **Vector Dimensions**: {clap.get('embedding_dim')}-d ({clap.get('byte_size')} bytes IEEE-754)\n"
                f"- **L2 Norm**: {clap.get('l2_norm')} (Unit norm verified: `{clap.get('unit_norm_verified')}`)\n"
                f"- **Vector Sample (Head)**: `{clap.get('vector_sample_head')}`"
            )
        else:
            clap_summary = "- *(No CLAP embedding generated or indexed)*"

        md = f"""# Sonic Intelligence Canonical Inspection Report: Asset #{sid}

**File Name**: `{fn}`  
**Title**: {cat_meta.get('title')}  
**Category**: `{cat_meta.get('category')}` / `{cat_meta.get('subcategory')}`  
**License / Source**: {cat_meta.get('source_collection')} ({cat_meta.get('license')})  
**Local Disk Status**: `{'LOCAL_DOWNLOADED' if cat_meta.get('is_downloaded') else 'VIRTUAL_REMOTE'}`  

---

## 1. Agent Sound Card v3.0 (Active Production View)

{card.get('rendered_markdown', '*Sound card rendering unavailable*')}

---

## 2. Technical Audio Format & File Metadata

| Property | Value | Evidence / Method |
|---|---|---|
| **Duration** | `{fmt.get('duration_sec'):.3f}s` | [MEASURED] Container Header Probing |
| **Container & Codec** | `{fmt.get('container_format')}` / `{fmt.get('codec') or 'native'}` | [MEASURED] Audio Stream Probing |
| **Sample Rate** | `{fmt.get('sample_rate_hz')} Hz` | [MEASURED] Exact Sample Clock |
| **Channels** | `{fmt.get('channels')} ch` ({'Stereo' if fmt.get('channels') == 2 else 'Mono'}) | [MEASURED] Channel Map |
| **Bit Depth** | `{fmt.get('bit_depth') or 'N/A (Lossy Codec)'}` | [MEASURED] Bit Resolution |
| **Bitrate** | `{fmt.get('bitrate_bps') or 'N/A'} bps` | [MEASURED] Stream Average |
| **File Size** | `{fmt.get('file_size_bytes')} bytes` | [MEASURED] Disk File Size |

---

## 3. Measured DSP & Acoustic Facts (Sonic Genome Layer 1)

### Loudness & Dynamic Profiles [MEASURED DSP]
- **Integrated Loudness**: `{loud.get('integrated_lufs')} LUFS` (EBU R128)
- **True Peak**: `{loud.get('true_peak_dbtp')} dBTP`
- **Loudness Range (LRA)**: `{loud.get('loudness_range_lu')} LU`
- **RMS Level**: `{loud.get('rms_level_db')} dBFS`
- **Peak Level**: `{loud.get('peak_level_db')} dBFS`
- **Dynamic Range**: `{loud.get('dynamic_range_db')} dB`

### Spectral & Acoustic Fingerprint [MEASURED DSP]
- **Spectral Centroid**: `{spec.get('spectral_centroid_hz')} Hz` (**Brightness**: `{spec.get('spectral_brightness')}`)
- **Spectral Bandwidth**: `{spec.get('spectral_bandwidth_hz')} Hz`
- **Spectral Rolloff (85%)**: `{spec.get('spectral_rolloff_hz')} Hz`
- **Spectral Flatness**: `{spec.get('spectral_flatness')}`
- **Zero Crossing Rate**: `{spec.get('zero_crossing_rate')}`
- **Speech Corridor Density (1kHz - 4kHz)**: `{spec.get('speech_corridor_density')}`
- **Vocal Clash Risk**: `{spec.get('vocal_clash_risk')}`

---

## 4. Temporal Structure & SED Active Intervals

- **Active Sound Region**: `{temp.get('active_region_str')}`
- **Silence Ratio**: `{temp.get('silence_ratio')} [MEASURED DSP]`
- **Transient Pulse Count**: `{temp.get('transient_count')} detected peaks [MEASURED DSP]`
- **Energy Envelope Character**: `{temp.get('energy_envelope')} [DERIVED DSP]`
- **Major Transient Onsets**: `{temp.get('major_transients_sec')}`

### Detected Temporal Intervals & Active Windows ({temp.get('temporal_events_count')} total)
{event_block}

---

## 5. Music & Tonal Intelligence [MEASURED / SOURCE METADATA]

- **Is Tonal**: {music.get('is_tonal_str')}
- **BPM / Tempo**: {music.get('bpm_str')}
- **Key / Tonality**: {music.get('key_tonality_str')}
- **Time Signature**: {music.get('time_signature_str')}

---

## 6. AI Classifier Predictions (AST AudioSet 527) [CLASSIFIER INFERENCE]

{cls_table}

---

## 7. CLAP Semantic Vector Embedding (512-d Open-Vocabulary) [EMBEDDING]

{clap_summary}

---

## 8. Psychoacoustics, Mix Evidence & Agent Directorial Guidelines

### Measurable Mix Evidence [MEASURED DSP & CLASSIFIER]
- **Speech Corridor Density (1kHz–4kHz)**: `{mix.get('speech_corridor_density') or 'Unmeasured'}` [MEASURED DSP]
- **Classifier Vocal / Speech Presence**: `{mix.get('vocal_speech_probability') or '0.00'}` [CLASSIFIER INFERENCE]

### Contextual Directorial Status [AGENT_INTERPRETATION]
- **Dramatic Role**: `{mix.get('dramatic_role')}` {mix.get('dramatic_role_evidence')}
- **Scene Purpose**: `{mix.get('scene_purpose')}` {mix.get('scene_purpose_evidence')}
- **Emotional Suitability**: `{mix.get('emotional_suitability')}` {mix.get('emotional_suitability_evidence')}
- **Voice Masking Judgment**: **`{mix.get('voice_masking_judgment') or mix.get('voice_masking_risk')}`** {mix.get('voice_masking_evidence')}
- **Whisper Compatibility**: `{mix.get('whisper_compatibility') if mix.get('whisper_compatibility') is not None else 'NOT_CALIBRATED'}` {mix.get('whisper_compatibility_evidence')}
- **Recommended Dialogue Ducking**: **`{f"{mix.get('dialogue_ducking_amount_db') or mix.get('recommended_ducking_db')} dB" if (mix.get('dialogue_ducking_amount_db') is not None or mix.get('recommended_ducking_db') is not None) else 'SCENE_DEPENDENT'}`** {mix.get('recommended_ducking_evidence')}
- **Placement & Usage**: `{mix.get('placement_usage')}` {mix.get('placement_usage_evidence')}
- **Final Taxonomy**: `{mix.get('final_taxonomy')}` {mix.get('final_taxonomy_evidence')}

### Physical Taxonomy & Acoustic Environment [SOURCE_METADATA]
- **Physical Taxonomy**: Action=`{mix.get('physical_action')}`, Exciter=`{mix.get('exciter')}`, Resonator=`{mix.get('resonator')}`, Surface=`{mix.get('surface')}`
- **Acoustic Environment**: `{mix.get('acoustic_space')}` (Reverb: `{mix.get('reverb_character')}`)

---

## 9. Provenance, Audit Trails & Analysis Runs ({prov.get('total_runs')} runs)

{runs_block}
"""
        return md


def main() -> None:
    parser = argparse.ArgumentParser(description="Sonic Asset Inspection & Export Tool")
    parser.add_argument("track_id", type=int, help="Catalog track ID to inspect and export")
    parser.add_argument("--output-dir", type=str, default="exports/sonic_inspections", help="Directory for exported JSON and MD files")
    args = parser.parse_args()

    inspector = SonicAssetInspector()
    json_path, md_path = inspector.export_asset(args.track_id, output_dir=args.output_dir)
    print(f"Asset #{args.track_id} exported successfully:\n  JSON: {json_path}\n  Markdown: {md_path}")


if __name__ == "__main__":
    main()
