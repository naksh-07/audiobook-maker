#!/usr/bin/env python3
"""
Non-Destructive Chapter 9 Hardening Benchmark.
Runs the upgraded SourceSemanticMap, TargetSemanticMap, SemanticAligner,
IntensityEvaluator (Gate T8), and TranslationCertifier (T0 to T11) on Chapter 9 scenes.
Saves all artifacts in an isolated directory: audiobooks/standards/chapter_009_hardened_benchmark/
DOES NOT overwrite any canonical files.
"""

import sys
import json
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.translation.book_bible import BookBible
from audiobook_factory.translation.source_semantic_map import (
    build_source_semantic_map,
    build_target_semantic_map,
    SemanticAligner,
    SourceSemanticMap,
    SEMANTIC_MAP_VERSION,
)
from audiobook_factory.translation.intensity_model import IntensityEvaluator
from audiobook_factory.translation.certification import TranslationCertifier
from audiobook_factory.translation.scene_planner import ScenePlan
from audiobook_factory.translation.provenance import TranslationProvenanceTracker


def reconstruct_source_text(semantic_map_path: Path) -> str:
    with open(semantic_map_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    propositions = data.get("propositions", [])
    paras: dict[int, list[str]] = {}
    for p in propositions:
        p_idx = p.get("paragraph_idx", 0)
        sentence = p.get("source_sentence", "")
        paras.setdefault(p_idx, []).append(sentence)

    para_strings = []
    for p_idx in sorted(paras.keys()):
        para_strings.append(" ".join(paras[p_idx]))
    return "\n\n".join(para_strings)


def run_benchmark():
    standards_dir = WORKSPACE_DIR / "audiobooks" / "standards"
    ch9_orig_dir = standards_dir / "chapter_009"
    bench_dir = standards_dir / "chapter_009_hardened_benchmark"
    bench_dir.mkdir(parents=True, exist_ok=True)

    with open(standards_dir / "book_bible.json", "r", encoding="utf-8") as f:
        bible = BookBible.model_validate(json.load(f))

    scenes = ["scene_001", "scene_002"]
    metrics_summary = {}

    for scene_id in scenes:
        orig_scene_dir = ch9_orig_dir / scene_id
        target_scene_dir = bench_dir / scene_id
        target_scene_dir.mkdir(parents=True, exist_ok=True)

        orig_sem_path = orig_scene_dir / "semantic_map.json"
        with open(orig_sem_path, "r", encoding="utf-8") as f:
            old_sem_data = json.load(f)
        old_props = old_sem_data.get("propositions", [])

        # Old metrics
        old_total_beats = len(old_props)
        old_actors_pop = sum(1 for p in old_props if p.get("actors"))
        old_action_pop = sum(1 for p in old_props if p.get("action"))
        old_has_neg = sum(1 for p in old_props if p.get("has_negation"))
        old_diag = sum(1 for p in old_props if p.get("is_dialogue"))

        # Reconstruct source text
        source_text = reconstruct_source_text(orig_sem_path)
        with open(orig_scene_dir / "translation.md", "r", encoding="utf-8") as f:
            target_text = f.read()

        known_chars = list(bible.characters.keys()) if isinstance(bible.characters, dict) else [c.canonical_name for c in bible.characters]

        # 1. Run upgraded SourceSemanticMap
        new_source_map = build_source_semantic_map(
            scene_text=source_text,
            scene_id=scene_id,
            known_entities=known_chars,
        )

        new_total_beats = len(new_source_map.propositions)
        new_actors_pop = sum(1 for p in new_source_map.propositions if p.actors)
        new_action_pop = sum(1 for p in new_source_map.propositions if p.action)
        new_has_neg = sum(1 for p in new_source_map.propositions if p.has_negation)
        new_diag = sum(1 for p in new_source_map.propositions if p.is_dialogue)
        new_time_pop = sum(1 for p in new_source_map.propositions if p.time_marker)
        new_loc_pop = sum(1 for p in new_source_map.propositions if p.location_marker)

        # 2. Run upgraded TargetSemanticMap and SemanticAligner
        new_target_map = build_target_semantic_map(
            target_text=target_text,
            scene_id=scene_id,
            book_bible=bible,
        )

        align_res = SemanticAligner.align(
            source_map=new_source_map,
            target_map=new_target_map,
            book_bible=bible,
        )

        # 3. Run calibrated IntensityEvaluator
        src_intensity = IntensityEvaluator.estimate_source_intensity(source_text, semantic_map=new_source_map)
        tgt_intensity = IntensityEvaluator.estimate_target_intensity(target_text, target_map=new_target_map, source_vector=src_intensity)
        int_res = IntensityEvaluator.compare_vectors(src_intensity, tgt_intensity)

        # 4. Run upgraded TranslationCertifier
        scene_plan = ScenePlan(
            scene_id=scene_id,
            scene_title=f"Chapter 9 - {scene_id}",
            start_paragraph_idx=0,
            end_paragraph_idx=len(source_text.split('\n\n')) - 1,
            text_block=source_text,
            active_characters=known_chars[:3],
            intensity_vector=src_intensity,
        )

        audit_res = TranslationCertifier.certify_scene(
            source_text=source_text,
            target_text=target_text,
            source_map=new_source_map,
            scene_plan=scene_plan,
            book_bible=bible,
            chapter_num=9,
            source_intensity=src_intensity,
            target_intensity=tgt_intensity,
            target_map=new_target_map,
        )

        # 5. Save benchmark artifacts
        bible_hash = bible.get_version_hash()
        comp_key = TranslationProvenanceTracker.generate_composite_key(
            source_text=source_text,
            bible_version_hash=bible_hash,
            prompt_version="2.0.0",
            translator_version="2.0",
            evaluator_version="2.0",
            semantic_map_version=SEMANTIC_MAP_VERSION,
            repair_version="2.0",
        )

        prov_dict = {
            "source_hash": new_source_map.source_hash,
            "bible_version_hash": bible_hash,
            "policy_version": "2.0.0",
            "prompt_version": "2.0.0",
            "translator_version": "2.0",
            "evaluator_version": "2.0",
            "semantic_map_version": SEMANTIC_MAP_VERSION,
            "repair_version": "2.0",
            "composite_cache_key": comp_key,
            "certified": audit_res.certified,
            "certification_status": audit_res.overall_status,
        }

        TranslationCertifier.save_artifact_bundle(
            output_dir=target_scene_dir,
            source_text=source_text,
            target_text=target_text,
            source_map=new_source_map,
            scene_plan=scene_plan,
            audit_result=audit_res,
            provenance_dict=prov_dict,
            target_map=new_target_map,
        )

        metrics_summary[scene_id] = {
            "old": {
                "beats": old_total_beats,
                "actors_populated": f"{old_actors_pop}/{old_total_beats} ({old_actors_pop/max(1, old_total_beats)*100:.1f}%)",
                "action_populated": f"{old_action_pop}/{old_total_beats} ({old_action_pop/max(1, old_total_beats)*100:.1f}%)",
                "dialogue_beats": old_diag,
                "negation_beats": old_has_neg,
            },
            "new": {
                "beats": new_total_beats,
                "actors_populated": f"{new_actors_pop}/{new_total_beats} ({new_actors_pop/max(1, new_total_beats)*100:.1f}%)",
                "action_populated": f"{new_action_pop}/{new_total_beats} ({new_action_pop/max(1, new_total_beats)*100:.1f}%)",
                "dialogue_beats": new_diag,
                "negation_beats": new_has_neg,
                "time_markers_extracted": new_time_pop,
                "location_markers_extracted": new_loc_pop,
            },
            "alignment": {
                "total_source_paragraphs": align_res.total_source_paragraphs,
                "total_target_paragraphs": align_res.total_target_paragraphs,
                "overall_negation_parity": align_res.overall_negation_parity,
                "average_coverage": align_res.overall_coverage_ratio,
                "affected_paragraphs": align_res.affected_paragraphs,
            },
            "intensity": {
                "source_profanity": src_intensity.profanity,
                "source_violence": src_intensity.violence,
                "source_emotional": src_intensity.emotional_intensity,
                "target_profanity": tgt_intensity.profanity,
                "target_violence": tgt_intensity.violence,
                "target_emotional": tgt_intensity.emotional_intensity,
                "max_delta": int_res.max_delta,
                "status": int_res.status,
            },
            "certification": {
                "overall_status": audit_res.overall_status,
                "certified": audit_res.certified,
                "gates": {k: g.status.value for k, g in audit_res.gates.items()},
                "affected_paragraphs": audit_res.affected_paragraphs,
            },
        }

    # Write comparative benchmark report
    report_md = f"""# Chapter 9 Hardening Verification Benchmark Report

## 1. Executive Summary
The Chapter 9 standard benchmark was executed non-destructively against `scene_001` and `scene_002`.
All artifacts were saved to `audiobooks/standards/chapter_009_hardened_benchmark/`.
Canonical standard files (`chapter_009_hi_old_canonical.md`, `chapter_009_hi_standard.md`, `chapter_009_hi.md`) remain 100% untouched.

## 2. Before vs. After Semantic Extraction Metrics

| Metric | scene_001 (Old) | scene_001 (Hardened) | scene_002 (Old) | scene_002 (Hardened) |
| :--- | :--- | :--- | :--- | :--- |
| **Total Propositions (Beats)** | {metrics_summary['scene_001']['old']['beats']} | {metrics_summary['scene_001']['new']['beats']} | {metrics_summary['scene_002']['old']['beats']} | {metrics_summary['scene_002']['new']['beats']} |
| **Action Extraction Rate** | {metrics_summary['scene_001']['old']['action_populated']} | **{metrics_summary['scene_001']['new']['action_populated']}** | {metrics_summary['scene_002']['old']['action_populated']} | **{metrics_summary['scene_002']['new']['action_populated']}** |
| **Actor Population Rate** | {metrics_summary['scene_001']['old']['actors_populated']} | **{metrics_summary['scene_001']['new']['actors_populated']}** | {metrics_summary['scene_002']['old']['actors_populated']} | **{metrics_summary['scene_002']['new']['actors_populated']}** |
| **Dialogue Beats Tracked** | {metrics_summary['scene_001']['old']['dialogue_beats']} | {metrics_summary['scene_001']['new']['dialogue_beats']} | {metrics_summary['scene_002']['old']['dialogue_beats']} | {metrics_summary['scene_002']['new']['dialogue_beats']} |
| **Time Markers Extracted** | 0 (Field missing) | **{metrics_summary['scene_001']['new']['time_markers_extracted']}** | 0 (Field missing) | **{metrics_summary['scene_002']['new']['time_markers_extracted']}** |
| **Location Markers Extracted** | 0 (Field missing) | **{metrics_summary['scene_001']['new']['location_markers_extracted']}** | 0 (Field missing) | **{metrics_summary['scene_002']['new']['location_markers_extracted']}** |

## 3. Target Semantic Map & Alignment Verification

### Scene 1 Alignment
- **Paragraphs**: {metrics_summary['scene_001']['alignment']['total_source_paragraphs']} Source $\\leftrightarrow$ {metrics_summary['scene_001']['alignment']['total_target_paragraphs']} Target
- **Negation Parity**: {metrics_summary['scene_001']['alignment']['overall_negation_parity']}
- **Average Beat Coverage**: {metrics_summary['scene_001']['alignment']['average_coverage']}
- **Affected Paragraphs**: {metrics_summary['scene_001']['alignment']['affected_paragraphs']}

### Scene 2 Alignment
- **Paragraphs**: {metrics_summary['scene_002']['alignment']['total_source_paragraphs']} Source $\\leftrightarrow$ {metrics_summary['scene_002']['alignment']['total_target_paragraphs']} Target
- **Negation Parity**: {metrics_summary['scene_002']['alignment']['overall_negation_parity']}
- **Average Beat Coverage**: {metrics_summary['scene_002']['alignment']['average_coverage']}
- **Affected Paragraphs**: {metrics_summary['scene_002']['alignment']['affected_paragraphs']}

## 4. Literary Intensity Calibration (Gate T8)

| Dimension / Metric | scene_001 Source | scene_001 Target | scene_002 Source | scene_002 Target |
| :--- | :--- | :--- | :--- | :--- |
| **Profanity** | {metrics_summary['scene_001']['intensity']['source_profanity']:.1f} | {metrics_summary['scene_001']['intensity']['target_profanity']:.1f} | {metrics_summary['scene_002']['intensity']['source_profanity']:.1f} | {metrics_summary['scene_002']['intensity']['target_profanity']:.1f} |
| **Violence** | {metrics_summary['scene_001']['intensity']['source_violence']:.1f} | {metrics_summary['scene_001']['intensity']['target_violence']:.1f} | {metrics_summary['scene_002']['intensity']['source_violence']:.1f} | {metrics_summary['scene_002']['intensity']['target_violence']:.1f} |
| **Emotional Intensity** | {metrics_summary['scene_001']['intensity']['source_emotional']:.1f} | {metrics_summary['scene_001']['intensity']['target_emotional']:.1f} | {metrics_summary['scene_002']['intensity']['source_emotional']:.1f} | {metrics_summary['scene_002']['intensity']['target_emotional']:.1f} |
| **Max Delta** | **{metrics_summary['scene_001']['intensity']['max_delta']}** | - | **{metrics_summary['scene_002']['intensity']['max_delta']}** | - |
| **Gate T8 Status** | **{metrics_summary['scene_001']['intensity']['status']}** | - | **{metrics_summary['scene_002']['intensity']['status']}** | - |

## 5. Certification Gate Status Summary

- **Scene 1 Status**: `{metrics_summary['scene_001']['certification']['overall_status']}` (Certified: {metrics_summary['scene_001']['certification']['certified']})
- **Scene 2 Status**: `{metrics_summary['scene_002']['certification']['overall_status']}` (Certified: {metrics_summary['scene_002']['certification']['certified']})

```json
{json.dumps(metrics_summary, indent=2, ensure_ascii=False)}
```
"""

    report_path = bench_dir / "comparison_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"\n[+] Chapter 9 Benchmark Completed Successfully!")
    print(f"[+] Comparison Report saved -> {report_path}")
    print(f"[+] Scene 1 Action Extraction: {metrics_summary['scene_001']['old']['action_populated']} -> {metrics_summary['scene_001']['new']['action_populated']}")
    print(f"[+] Scene 2 Action Extraction: {metrics_summary['scene_002']['old']['action_populated']} -> {metrics_summary['scene_002']['new']['action_populated']}")
    print(f"[+] Scene 1 Gate T8 Status: {metrics_summary['scene_001']['intensity']['status']} (Calibrated)")
    print(f"[+] Scene 2 Gate T8 Status: {metrics_summary['scene_002']['intensity']['status']} (Calibrated)")
    print(f"[+] Scene 1 Overall Certification: {metrics_summary['scene_001']['certification']['overall_status']}")
    print(f"[+] Scene 2 Overall Certification: {metrics_summary['scene_002']['certification']['overall_status']}")


if __name__ == "__main__":
    run_benchmark()
