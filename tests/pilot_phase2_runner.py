"""
Controlled AI Pilot Runner for Phase 2 (100 Representative Assets).
Validates model inference, VRAM stability, error isolation, embedding storage,
and classification telemetry on real local audio assets.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# Suppress HF symlinks warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.sonic_model_manager import SonicModelManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase2_pilot")


def run_pilot(max_assets: int = 100) -> Dict[str, Any]:
    bank = get_sound_bank()
    model_manager = SonicModelManager()

    logger.info(f"Starting Phase 2 AI Pilot on up to {max_assets} representative assets...")
    logger.info(f"Target Hardware Device: {model_manager.device}")

    # Fetch balanced set of downloaded assets across categories
    with bank._get_conn() as conn:
        rows = conn.execute("""
            SELECT id, filename, filepath, category, subcategory, duration_sec
            FROM sound_catalog
            WHERE is_downloaded = 1 AND filepath IS NOT NULL
            ORDER BY category ASC, id ASC
            LIMIT ?
        """, (max_assets * 2,)).fetchall()

    candidate_records = [dict(r) for r in rows if Path(r["filepath"]).exists()][:max_assets]
    logger.info(f"Selected {len(candidate_records)} verified local assets for pilot execution.")

    if not candidate_records:
        logger.warning("No local audio files found. Generating representative fixture set...")
        # Create small test fixtures if none exist
        import soundfile as sf
        fixtures_dir = Path("tests/fixtures/pilot_audio")
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        sr = 48000
        for i in range(10):
            p = fixtures_dir / f"pilot_sample_{i:02d}.wav"
            t = np.linspace(0, 1.0 + i * 0.5, int((1.0 + i * 0.5) * sr), dtype=np.float32)
            wf = 0.3 * np.sin(2 * np.pi * (200 + i * 50) * t)
            sf.write(str(p), wf, sr)
        bank.scan_and_index(extra_dirs=[fixtures_dir])
        with bank._get_conn() as conn:
            candidate_records = [dict(r) for r in conn.execute("SELECT id, filename, filepath, category, subcategory, duration_sec FROM sound_catalog LIMIT ?", (max_assets,)).fetchall()]

    # VRAM check
    vram_start_mb = 0.0
    try:
        import torch
        if torch.cuda.is_available():
            vram_start_mb = torch.cuda.memory_allocated() / (1024 * 1024)
    except Exception:
        pass

    results = {
        "total_attempted": len(candidate_records),
        "successful": 0,
        "partial": 0,
        "failed": 0,
        "durations_ms": [],
        "categories_processed": {},
        "top_detected_labels": {},
        "embeddings_verified": 0,
        "vram_start_mb": round(vram_start_mb, 2),
        "vram_peak_mb": 0.0,
        "vram_end_mb": 0.0,
    }

    t0_all = time.perf_counter()

    for idx, item in enumerate(candidate_records, start=1):
        sound_id = item["id"]
        fname = item["filename"]
        cat = item.get("category", "SFX")
        results["categories_processed"][cat] = results["categories_processed"].get(cat, 0) + 1

        t0 = time.perf_counter()
        try:
            genome = bank.enrich_asset_phase2(sound_id=sound_id, force=True)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            results["durations_ms"].append(elapsed_ms)

            # Verification of outputs
            embed = bank.get_sound_embedding(sound_id)
            if embed is not None and embed.shape == (512,):
                results["embeddings_verified"] += 1

            tags = bank.get_classifier_tags(sound_id)
            if tags:
                top_label = tags[0]["raw_label"]
                results["top_detected_labels"][top_label] = results["top_detected_labels"].get(top_label, 0) + 1

            results["successful"] += 1
            if idx % 10 == 0 or idx == len(candidate_records):
                logger.info(f"[{idx}/{len(candidate_records)}] Processed {fname} in {elapsed_ms:.1f}ms | Top tag: {tags[0]['raw_label'] if tags else 'None'}")

        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error(f"[{idx}/{len(candidate_records)}] Failed {fname}: {e}")
            results["failed"] += 1

        # Check peak VRAM
        try:
            import torch
            if torch.cuda.is_available():
                cur_vram = torch.cuda.memory_allocated() / (1024 * 1024)
                if cur_vram > results["vram_peak_mb"]:
                    results["vram_peak_mb"] = round(cur_vram, 2)
        except Exception:
            pass

    total_time_sec = time.perf_counter() - t0_all

    # Clean up and release VRAM
    model_manager.release_models()

    try:
        import torch
        if torch.cuda.is_available():
            results["vram_end_mb"] = round(torch.cuda.memory_allocated() / (1024 * 1024), 2)
    except Exception:
        pass

    avg_ms = np.mean(results["durations_ms"]) if results["durations_ms"] else 0.0
    median_ms = np.median(results["durations_ms"]) if results["durations_ms"] else 0.0

    summary = {
        "status": "COMPLETED",
        "total_assets": results["total_attempted"],
        "successful": results["successful"],
        "failed": results["failed"],
        "success_rate_pct": round(results["successful"] / max(1, results["total_attempted"]) * 100, 2),
        "total_runtime_sec": round(total_time_sec, 2),
        "avg_latency_ms": round(float(avg_ms), 1),
        "median_latency_ms": round(float(median_ms), 1),
        "embeddings_verified": results["embeddings_verified"],
        "categories_breakdown": results["categories_processed"],
        "top_labels_sample": dict(sorted(results["top_detected_labels"].items(), key=lambda x: x[1], reverse=True)[:10]),
        "vram_metrics": {
            "start_mb": results["vram_start_mb"],
            "peak_mb": results["vram_peak_mb"],
            "end_mb": results["vram_end_mb"],
        },
    }

    report_path = Path("tests/pilot_phase2_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    logger.info("================ PHASE 2 PILOT SUMMARY ================")
    logger.info(f"Total Processed: {summary['total_assets']} assets")
    logger.info(f"Success Rate:    {summary['success_rate_pct']}% ({summary['successful']}/{summary['total_assets']})")
    logger.info(f"Avg Latency:     {summary['avg_latency_ms']} ms/asset")
    logger.info(f"Total Runtime:   {summary['total_runtime_sec']} sec")
    logger.info(f"Embeddings:      {summary['embeddings_verified']} stored in SQLite (512-d float32)")
    logger.info(f"Peak VRAM:       {summary['vram_metrics']['peak_mb']} MB (cleared to {summary['vram_metrics']['end_mb']} MB)")
    logger.info(f"Report saved to: {report_path.resolve()}")
    logger.info("========================================================")

    return summary


if __name__ == "__main__":
    n = 100
    if len(sys.argv) > 1:
        try:
            n = int(sys.argv[1])
        except ValueError:
            pass
    run_pilot(max_assets=n)
