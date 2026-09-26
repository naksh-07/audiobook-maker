#!/usr/bin/env python3
"""
Test Suite & Validation for SonicAssetInspector.
Tests complete inspection and export across the 5 real-world smoke test tracks:
453, 498, 164, 68, 67.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from audiobook_factory.sonic_asset_inspector import SonicAssetInspector


SMOKE_TRACK_IDS = [453, 498, 164, 68, 67]
EXPORT_DIR = Path("exports/sonic_inspections")


@pytest.fixture(scope="module")
def inspector() -> SonicAssetInspector:
    return SonicAssetInspector()


def test_export_five_smoke_tracks(inspector: SonicAssetInspector):
    """Verifies that all 5 tracks export valid JSON and Markdown files with full telemetry."""
    for tid in SMOKE_TRACK_IDS:
        json_path, md_path = inspector.export_asset(tid, output_dir=EXPORT_DIR)

        assert json_path.exists(), f"JSON export missing for #{tid}"
        assert md_path.exists(), f"Markdown export missing for #{tid}"
        assert json_path.stat().st_size > 500, f"JSON export too small for #{tid}"
        assert md_path.stat().st_size > 500, f"Markdown export too small for #{tid}"

        # Parse JSON
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["asset_id"] == tid
        assert "filename" in data and data["filename"]

        # 1. Source / file metadata
        src = data["source_and_catalog_metadata"]
        assert "title" in src
        assert "category" in src
        assert "source_collection" in src
        assert "license" in src

        # 2. Technical audio format
        fmt = data["technical_audio_format"]
        assert fmt["duration_sec"] is not None and fmt["duration_sec"] > 0
        assert fmt["container_format"] is not None
        assert fmt["sample_rate_hz"] in [44100, 48000]
        assert fmt["channels"] in [1, 2]

        # 3. Loudness and dynamics
        loud = data["loudness_and_dynamics"]
        assert loud["integrated_lufs"] is not None
        assert loud["true_peak_dbtp"] is not None

        # 4. Spectral / acoustic
        spec = data["spectral_and_acoustic"]
        assert spec["spectral_centroid_hz"] is not None
        assert spec["spectral_brightness"] is not None

        # 5. Temporal / events
        temp = data["temporal_and_events"]
        assert "silence_ratio" in temp
        assert "temporal_events" in temp
        assert len(temp["temporal_events"]) >= 1

        # 6. Music metadata
        music = data["music_metadata"]
        assert "tempo_bpm" in music

        # 7. Classifier predictions
        cls_inf = data["classifier_inferences"]
        assert cls_inf["predictions_count"] >= 1
        top_pred = cls_inf["top_predictions"][0]
        assert "raw_label" in top_pred
        assert "raw_score" in top_pred
        assert "rank" in top_pred
        assert cls_inf["model_id"] is not None

        # 8. CLAP embedding metadata
        clap = data["clap_semantic_embedding"]
        assert clap is not None
        assert clap["embedding_dim"] == 512
        assert clap["byte_size"] == 2048
        assert clap["unit_norm_verified"] is True
        assert clap["model_id"] is not None

        # 9. Provenance records
        prov = data["provenance_and_audit_runs"]
        assert prov["total_runs"] >= 1
        assert len(prov["runs"]) >= 1

        # 10. Agent Sound Card
        card = data["agent_sound_card"]
        assert card["card_dict"] is not None
        assert card["rendered_markdown"]
        assert "### 🎵 Sound Card" in card["rendered_markdown"]

        # Verify Markdown file content
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()
        assert f"Asset #{tid}" in md_text
        assert "Agent Sound Card v3.0" in md_text
        assert "Measured DSP & Acoustic Facts" in md_text
        assert "AI Classifier Predictions" in md_text
        assert "CLAP Semantic Vector Embedding" in md_text


def test_invalid_track_id_raises_value_error(inspector: SonicAssetInspector):
    """Verifies that non-existent track IDs fail closed with clear error message."""
    with pytest.raises(ValueError, match="not found"):
        inspector.inspect_asset(99999999)
