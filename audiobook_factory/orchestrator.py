#!/usr/bin/env python3
"""
Audiobook Factory - High-Level Production Pipeline Orchestrator.
Orchestrates end-to-end processing from raw EPUB/PDF to studio-mastered M4B audiobook.
Provides single-command autonomous execution with transaction-safe state management.
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

from audiobook_factory.logger import logger
from audiobook_factory.state import ProjectStateLedger
from audiobook_factory.extractor import process_book_file
from audiobook_factory.translator import translate_book_project
from audiobook_factory.script_builder import generate_project_scripts
from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.soundscape import (
    generate_chapter_soundscape_plan,
    render_chapter_soundscape,
    apply_dynamic_sidechain_ducking,
    get_audio_duration,
)
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.packager import package_m4b_audiobook


class PipelineOrchestrator:
    """End-to-end production manager for full novels and books."""

    def __init__(self, projects_dir: Path):
        self.projects_dir = Path(projects_dir).resolve()
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def run_autonomous_pipeline(
        self,
        input_file: Path,
        hindi: bool = True,
        dramatized: bool = True,
        voice: str = "Aoede",
        cover_image: Optional[Path] = None,
        workers: int = 3,
        duck_db: float = -16.0,
    ) -> Path:
        """
        Executes the complete 6-stage autonomous novel pipeline:
        1. Ingestion & Extraction (EPUB / PDF)
        2. Literary Hindi Translation & Glossary (Optional)
        3. Sliding-Window Screenplay Attribution (No truncation)
        4. Concurrent Speech Synthesis (Gemini 3.1 Flash TTS + Token Bucket)
        5. FTS5 Sound Bank Ambience & Sidechain Ducking
        6. Broadcast EBU R128 Mastering & Single-Pass M4B Packaging
        """
        start_time = time.time()
        input_file = Path(input_file).resolve()
        if not input_file.exists():
            raise FileNotFoundError(f"Input novel file not found: {input_file}")

        logger.info("=======================================================")
        logger.info("   AUTONOMOUS STUDIO AUDIOBOOK PRODUCTION PIPELINE   ")
        logger.info(f"   Target Book: {input_file.name}")
        logger.info(f"   Mode       : {'Literary Hindi' if hindi else 'Original Language'}")
        logger.info(f"   Style      : {'Full-Cast Dramatized' if dramatized else 'Single Narrator'}")
        logger.info(f"   Voice Lead : {voice}")
        logger.info("=======================================================\n")

        # -------------------------------------------------------------
        # Stage 1: Document Extraction
        # -------------------------------------------------------------
        logger.info("[Stage 1/6] Ingesting document and extracting chapters...")
        meta = process_book_file(input_file, self.projects_dir)
        book_slug = meta["book_id"]
        project_dir = self.projects_dir / book_slug
        ledger = ProjectStateLedger(project_dir)
        ledger.set_meta("title", meta.get("title", book_slug))
        ledger.set_meta("author", meta.get("author", "Unknown Author"))
        ledger.set_meta("source_file", str(input_file))

        # -------------------------------------------------------------
        # Stage 2: Literary Translation (Sense-for-Sense Hindustani)
        # -------------------------------------------------------------
        if hindi:
            logger.info("\n[Stage 2/6] Literary Hindi translation with honorific glossary...")
            translate_book_project(project_dir)
        else:
            logger.info("\n[Stage 2/6] Translation skipped (English/Native language selected).")

        # -------------------------------------------------------------
        # Stage 3: Screenplay Attribution (Sliding Window, No Truncation)
        # -------------------------------------------------------------
        logger.info("\n[Stage 3/6] Generating screenplay scripts with dialogue attribution...")
        scripts_dir = generate_project_scripts(
            project_dir=project_dir,
            use_hindi=hindi,
            dramatized=dramatized,
        )

        script_files = sorted(scripts_dir.glob("chapter_*_script.json"))
        if not script_files:
            raise RuntimeError(f"No script files generated in {scripts_dir}")

        # -------------------------------------------------------------
        # Stage 4: Concurrent Speech Synthesis (Gemini 3.1 Flash TTS)
        # -------------------------------------------------------------
        logger.info(f"\n[Stage 4/6] Concurrent TTS synthesis across {len(script_files)} chapters (Workers: {workers})...")
        dispatcher = TTSDispatcher(
            project_dir=project_dir,
            default_voice=voice,
            max_workers=workers,
        )

        for idx, sf in enumerate(script_files, 1):
            logger.info(f"--- Synthesizing Chapter {idx}/{len(script_files)}: {sf.name} ---")
            dispatcher.synthesize_chapter_script(sf, idx)

        # -------------------------------------------------------------
        # Stage 5: Mastering, Ambience & Sidechain Ducking
        # -------------------------------------------------------------
        logger.info("\n[Stage 5/6] Mastering chapter audio, scoring ambience & sidechain ducking...")
        mastered_dir = project_dir / "mastered"
        audio_dir = project_dir / "audio_chunks"
        bgm_dir = project_dir / "soundscapes"
        mastered_dir.mkdir(parents=True, exist_ok=True)
        bgm_dir.mkdir(parents=True, exist_ok=True)

        for idx, sf in enumerate(script_files, 1):
            chap_stem = sf.stem.replace("_script", "")
            segments = sorted(audio_dir.glob(f"c{idx:03d}_*.wav"))
            if not segments:
                logger.warning(f"[!] Warning: No audio segments found for chapter {idx}, skipping.")
                continue

            # 5a. Master dialogue vocals with 5-stage DSP
            vocal_m4a = mastered_dir / f"{chap_stem}_mastered.m4a"
            concatenate_and_master_chapter(segments, vocal_m4a)

            # 5b. Soundscape Scoring & Ducking
            soundscape_plan_file = bgm_dir / f"{chap_stem}_soundscape.json"
            with open(sf, "r", encoding="utf-8") as f:
                script_data = json.load(f)
            text_sample = " ".join([seg.get("text", "") for seg in script_data[:10]])

            if soundscape_plan_file.exists():
                with open(soundscape_plan_file, "r", encoding="utf-8") as f:
                    plan = json.load(f)
            else:
                plan = generate_chapter_soundscape_plan(text_sample, script_data)
                with open(soundscape_plan_file, "w", encoding="utf-8") as f:
                    json.dump(plan, f, ensure_ascii=False, indent=2)

            dur = get_audio_duration(vocal_m4a)
            bgm_raw = bgm_dir / f"{chap_stem}_bgm.wav"

            # Segment durations mapping for soundscape cues
            seg_durations = {}
            for seg in script_data:
                s_idx = seg.get("index", 1)
                seg_matches = sorted(audio_dir.glob(f"c{idx:03d}_s{s_idx:04d}_*.wav"))
                if seg_matches:
                    seg_durations[s_idx] = get_audio_duration(seg_matches[0])

            render_chapter_soundscape(plan, dur, bgm_raw, segment_durations=seg_durations)

            # Sidechain ducking
            cinematic_out = mastered_dir / f"{chap_stem}_cinematic.m4a"
            apply_dynamic_sidechain_ducking(vocal_m4a, bgm_raw, cinematic_out, duck_attenuation_db=duck_db)

        # -------------------------------------------------------------
        # Stage 6: Final M4B Containerization with Chapter Markers
        # -------------------------------------------------------------
        logger.info("\n[Stage 6/6] Packaging final M4B container with chapter navigation & cover art...")
        final_m4b = package_m4b_audiobook(project_dir, cover_image=cover_image)

        elapsed_min = round((time.time() - start_time) / 60.0, 1)
        progress = ledger.get_progress()

        logger.info("\n=======================================================")
        logger.info("   [SUCCESS] NOVEL AUDIOBOOK PRODUCTION COMPLETED!    ")
        logger.info(f"   Deliverable   : {final_m4b}")
        logger.info(f"   Total Segments: {progress['completed']}/{progress['total_segments']}")
        logger.info(f"   Audio Duration: {progress['total_duration_min']} minutes")
        logger.info(f"   Total Elapsed : {elapsed_min} minutes")
        logger.info("=======================================================\n")

        return final_m4b
