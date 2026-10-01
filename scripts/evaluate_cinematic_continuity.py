#!/usr/bin/env python3
"""
Audiobook Factory - Representative Audio Sequence Evaluator.
============================================================
Runs a representative 3-scene dramatic sequence:
- Scene 1: Castle Great Hall Banquet (Festive, Walla, Fireplace, Tableware/Goblet clatter)
- Scene 2: Solitary Stone Corridor (Stealth, Stone footsteps, Negative Silence Drop)
- Scene 3: Crypt Confrontation (Tension Riser Motif, Steel sword draw, Subterranean Reverb)

Evaluates:
- Ambience continuity & spatial profiles
- Foley relevance & tableware isolation
- Music variation mode & silence preservation
- Stems rendering (DX, MX, FX, AMB, FULL_MASTER)
"""

import sys
import json
import subprocess
from pathlib import Path
from audiobook_factory.sound_design.sound_director import get_sound_design_director
from audiobook_factory.sound_design.adapter import get_sound_design_adapter
from audiobook_factory.sound_design.qc import get_sound_design_qc_auditor
from audiobook_factory.contracts import CreativeManifest, MasteringConfig
from audiobook_factory.cinema_audio_engine import render_discrete_stems, measure_audio_metrics

def main():
    print("[*] Initializing Cinematic Audio Sequence Evaluation...")
    director = get_sound_design_director()
    adapter = get_sound_design_adapter()
    qc_auditor = get_sound_design_qc_auditor()

    # Define 3 contiguous scenes
    scenes_data = [
        {
            "scene_id": "sc_001_castle_banquet",
            "environment_id": "castle_great_hall",
            "start_ms": 0,
            "end_ms": 20000,
            "tension": 0.35,
            "emotion": "festive",
            "characters": ["King", "Knight", "Cupbearer"],
            "segments": [
                {"segment_index": 1, "speaker": "King", "text": "Raise your goblets to victory!", "sfx_cues": ["goblet clatter"], "start_ms": 0},
                {"segment_index": 2, "speaker": "Narrator", "text": "Servants hurried across the hall, setting heavy wooden platters.", "start_ms": 4000},
            ]
        },
        {
            "scene_id": "sc_002_corridor_stealth",
            "environment_id": "castle_stone_corridor",
            "start_ms": 20000,
            "end_ms": 40000,
            "tension": 0.65,
            "emotion": "stealth",
            "characters": ["Rogue"],
            "segments": [
                {"segment_index": 3, "speaker": "Narrator", "text": "She stepped into the shadowed hallway, holding her breath.", "start_ms": 21000},
                {"segment_index": 4, "speaker": "Rogue", "text": "The guards have changed posts.", "start_ms": 26000},
            ]
        },
        {
            "scene_id": "sc_003_crypt_confrontation",
            "environment_id": "crypt_catacomb",
            "start_ms": 40000,
            "end_ms": 65000,
            "tension": 0.90,
            "emotion": "combat",
            "characters": ["Geralt", "Beast"],
            "segments": [
                {"segment_index": 5, "speaker": "Geralt", "text": "Step into the light.", "start_ms": 42000},
                {"segment_index": 6, "speaker": "Narrator", "text": "He drew his silver sword as claws scraped against stone.", "sfx_cues": ["draw_sword", "claws_stone"], "start_ms": 47000},
            ]
        }
    ]

    blueprints = []
    timelines = []
    qc_reports = []

    prev_sc = None
    for sc in scenes_data:
        bp, tl = director.direct_scene(
            scene_id=sc["scene_id"],
            chapter_id="eval_ch_01",
            segments=sc["segments"],
            start_ms=sc["start_ms"],
            end_ms=sc["end_ms"],
            environment_override=sc["environment_id"],
            characters_override=sc["characters"],
            tension_override=sc["tension"],
            emotion_override=sc["emotion"],
            previous_scene_id=prev_sc,
        )
        blueprints.append(bp)
        timelines.append(tl)
        qc = qc_auditor.audit_scene_sound_design(bp, tl)
        qc_reports.append(qc)
        prev_sc = sc["scene_id"]

    print(f"[+] Directed {len(blueprints)} scenes. QC Statuses: {[r.status for r in qc_reports]}")

    # Build Creative Manifest
    base_manifest = CreativeManifest(
        chapter_id="eval_ch_01",
        total_duration_ms=65000,
        silence_percentage=100.0,
        mastering=MasteringConfig(target_lufs=-19.0),
        music_cues=[],
        foley_cues=[],
        ambience_scenes=[],
    )

    enriched_manifest = adapter.enrich_creative_manifest(
        manifest=base_manifest,
        blueprints=blueprints,
        timelines=timelines,
    )

    print(f"[+] Manifest Enriched:")
    print(f"    - Silence Percentage: {enriched_manifest.silence_percentage}%")
    print(f"    - Foley Cues: {len(enriched_manifest.foley_cues)}")
    print(f"    - Music Cues: {len(enriched_manifest.music_cues)}")
    print(f"    - Acoustic Scenes: {len(enriched_manifest.scene_acoustics.scenes) if enriched_manifest.scene_acoustics else 0}")
    print(f"    - Silence Events in Metadata: {len(enriched_manifest.metadata.get('silence_events', []))}")

    # Create dummy vocal WAV for stem rendering
    out_dir = Path("build/eval_stems")
    out_dir.mkdir(parents=True, exist_ok=True)
    vocal_wav = out_dir / "eval_vocal.wav"
    
    cmd_tone = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=65",
        "-af", "volume=-24dB",
        "-c:a", "pcm_s16le",
        str(vocal_wav)
    ]
    subprocess.run(cmd_tone, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Render discrete stems
    print("[*] Rendering discrete cinema stems (DX, MX, FX, AMB, FULL_MASTER)...")
    ledger = render_discrete_stems(
        manifest=enriched_manifest,
        dialogue_wav=vocal_wav,
        output_dir=out_dir,
    )

    print(f"[+] Stems Rendered Successfully!")
    for s_type, s_meta in ledger.stems.items():
        print(f"    [{s_type}] Path: {Path(s_meta.filepath).name} | Duration: {s_meta.duration_sec:.1f}s | LUFS: {s_meta.integrated_lufs} | Peak: {s_meta.true_peak_dbtp} dBTP")

    # Output JSON summary
    summary = {
        "chapter_id": enriched_manifest.chapter_id,
        "silence_percentage": enriched_manifest.silence_percentage,
        "foley_cues_count": len(enriched_manifest.foley_cues),
        "music_cues_count": len(enriched_manifest.music_cues),
        "scenes_count": len(enriched_manifest.scene_acoustics.scenes) if enriched_manifest.scene_acoustics else 0,
        "silence_events_count": len(enriched_manifest.metadata.get("silence_events", [])),
        "stems": {k: {"lufs": v.integrated_lufs, "peak": v.true_peak_dbtp, "duration_sec": v.duration_sec} for k, v in ledger.stems.items()},
    }
    with open(out_dir / "eval_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[+] Saved evaluation summary to: {out_dir / 'eval_summary.json'}")

if __name__ == "__main__":
    main()
