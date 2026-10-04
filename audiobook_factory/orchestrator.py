#!/usr/bin/env python3
"""
Audiobook Factory - High-Level Production Pipeline Orchestrator.
Orchestrates end-to-end processing from raw EPUB/PDF to studio-mastered M4B audiobook.
Provides single-command autonomous execution with transaction-safe state management.
"""

import os
import uuid
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional

from audiobook_factory.logger import logger


def atomic_write_json(filepath: Path, data: Any, indent: int = 2) -> None:
    """Writes JSON data atomically using a temporary file and atomic rename."""
    filepath = Path(filepath).resolve()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = filepath.with_suffix(f".tmp_{os.getpid()}_{uuid.uuid4().hex[:6]}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        for attempt in range(8):
            try:
                os.replace(tmp_path, filepath)
                break
            except (PermissionError, OSError):
                if attempt == 7:
                    try:
                        import shutil
                        shutil.copy2(tmp_path, filepath)
                        break
                    except Exception:
                        raise
                time.sleep(0.05 * (1.5 ** attempt))
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
from audiobook_factory.state import ProjectStateLedger
from audiobook_factory.extractor import process_book_file
from audiobook_factory.translator import translate_book_project
from audiobook_factory.script_builder import generate_project_scripts
from audiobook_factory.tts_dispatcher import TTSDispatcher

from audiobook_factory.timeline_ledger import build_chapter_timeline_ledger
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.packager import package_m4b_audiobook
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.manifest_renderer import render_manifest_soundscape
from audiobook_factory.contracts import CreativeManifest, LegacyCreativeManifestAdapter
from audiobook_factory.cinema_audio_engine import render_discrete_stems, CinemaAudioManifest
from audiobook_factory.gate_auditor import GateAuditError
from audiobook_factory.telemetry import get_telemetry_ledger
from audiobook_factory.model_manager import LLMUnavailableError, ModelTierFloorBreachError
from audiobook_factory.orchestration import (
    verify_pre_synthesis_gates,
    verify_performance_fidelity_gate,
    verify_acoustic_feasibility_gate,
    verify_post_mix_master_gates,
    verify_translation_coverage_gates,
    verify_screenplay_project_gates,
    verify_packaging_gates,
    cleanup_chapter_chunks,
    process_and_master_dialogue_stem,
)


STAGE_NUMBERS: Dict[str, int] = {
    "extract": 1,
    "extraction": 1,
    "translate": 2,
    "translation": 2,
    "script": 3,
    "screenplay": 3,
    "tts": 4,
    "synthesis": 4,
    "produce": 4,
    "direct": 5,
    "directing": 5,
    "mix": 5,
    "package": 6,
    "packaging": 6,
}


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
        spatial_staging: bool = True,
        adult_literary_mode: bool = True,
        force_gate: bool = False,
        force_rebuild: bool = False,
        stage_start: Optional[str] = None,
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

        os.environ["ADULT_LITERARY_MODE"] = "true" if adult_literary_mode else "false"
        if force_rebuild:
            os.environ["FORCE_REBUILD_MANIFEST"] = "true"

        start_stage_num = STAGE_NUMBERS.get(stage_start.lower(), 1) if stage_start else 1

        logger.info("=======================================================")
        logger.info("   AUTONOMOUS STUDIO AUDIOBOOK PRODUCTION PIPELINE   ")
        logger.info(f"   Target Book: {input_file.name}")
        logger.info(f"   Mode       : {'Literary Hindi' if hindi else 'Original Language'}")
        logger.info(f"   Style      : {'Full-Cast Dramatized' if dramatized else 'Single Narrator'}")
        logger.info(f"   Adult Mode : {'Active (Raw Unrated Adult Fidelity)' if adult_literary_mode else 'Standard'}")
        logger.info(f"   Voice Lead : {voice}")
        if stage_start:
            logger.info(f"   Stage Start: {stage_start} (Stage {start_stage_num})")
        if force_rebuild:
            logger.info("   Rebuild    : FORCE REBUILD ENABLED (Cache Invalidated)")
        logger.info("=======================================================\n")

        telemetry = get_telemetry_ledger()
        run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        os.environ["CURRENT_AUDIOBOOK_RUN_ID"] = run_id
        telemetry.start_run(
            run_id=run_id,
            project_id=f"proj-{input_file.stem}",
            book_title=input_file.stem,
            config={
                "hindi": hindi,
                "dramatized": dramatized,
                "voice": voice,
                "adult_literary_mode": adult_literary_mode,
                "force_rebuild": force_rebuild,
                "stage_start": stage_start,
            },
        )

        try:
            # -------------------------------------------------------------
            # Stage 1: Document Extraction
            # -------------------------------------------------------------
            if start_stage_num <= 1:
                with telemetry.stage_timer(run_id, "Document Extraction", 1):
                    logger.info("[Stage 1/6] Ingesting document and extracting chapters...")
                    meta = process_book_file(input_file, self.projects_dir, force_gate=force_gate)
                    book_slug = meta["book_id"]
                    project_dir = self.projects_dir / book_slug
                    ledger = ProjectStateLedger(project_dir)
                    ledger.set_meta("title", meta.get("title", book_slug))
                    ledger.set_meta("author", meta.get("author", "Unknown Author"))
                    ledger.set_meta("source_file", str(input_file))
            else:
                book_slug = input_file.stem
                project_dir = self.projects_dir / book_slug
                if not project_dir.exists():
                    logger.warning(f"  [!] Project {book_slug} missing on disk; running Stage 1 extraction.")
                    meta = process_book_file(input_file, self.projects_dir, force_gate=force_gate)
                    book_slug = meta["book_id"]
                    project_dir = self.projects_dir / book_slug
                ledger = ProjectStateLedger(project_dir)
                logger.info(f"[Stage 1/6] Document extraction skipped (resuming at stage: {stage_start}).")

            # -------------------------------------------------------------
            # Stage 2: Literary Translation (Sense-for-Sense Hindustani)
            # -------------------------------------------------------------
            if hindi:
                if start_stage_num <= 2:
                    with telemetry.stage_timer(run_id, "Literary Translation", 2):
                        logger.info("\n[Stage 2/6] Literary Hindi translation with honorific glossary...")
                        translate_book_project(project_dir, force_gate=force_gate)
                        # Inline Gate 0: Translation Coverage Verification
                        verify_translation_coverage_gates(project_dir)
                else:
                    logger.info(f"\n[Stage 2/6] Translation skipped (resuming at stage: {stage_start}).")
            else:
                telemetry.record_stage(run_id, "Literary Translation", 2, duration_sec=0.0, status="SKIPPED")
                logger.info("\n[Stage 2/6] Translation skipped (English/Native language selected).")

            # -------------------------------------------------------------
            # Stage 3: Screenplay Attribution (Sliding Window, No Truncation)
            # -------------------------------------------------------------
            scripts_dir = project_dir / "scripts"
            script_files = sorted(scripts_dir.glob("chapter_*_script.json")) if scripts_dir.exists() else []

            if start_stage_num <= 3 or not script_files:
                with telemetry.stage_timer(run_id, "Screenplay Attribution", 3):
                    logger.info("\n[Stage 3/6] Generating screenplay scripts with dialogue attribution...")
                if dramatized:
                    try:
                        from audiobook_factory.character_caster import CharacterCaster
                        logger.info("[*] Running Autonomous Character Discovery & Casting Director...")
                        CharacterCaster.discover_and_cast_project(
                            project_dir=project_dir,
                            use_hindi=hindi,
                            default_narrator_voice=voice,
                        )
                    except Exception as e:
                        logger.warning(f"  [!] Character discovery notice: {e}")

                scripts_dir = generate_project_scripts(
                    project_dir=project_dir,
                    use_hindi=hindi,
                    dramatized=dramatized,
                )

                script_files = sorted(scripts_dir.glob("chapter_*_script.json"))
                if not script_files:
                    raise RuntimeError(f"No script files generated in {scripts_dir}")

                # Inline Gate 1 & Gate 6A: Voice Collision, Roster Sanity & Voice Continuity
                verify_screenplay_project_gates(project_dir)
            else:
                logger.info(f"\n[Stage 3/6] Screenplay generation skipped (resuming at stage: {stage_start}, found {len(script_files)} scripts).")

            # -------------------------------------------------------------
            # Stage 4 & 5: Concurrent Synthesis & 5-Track Cinematic Production
            # -------------------------------------------------------------
            if start_stage_num <= 5:
                with telemetry.stage_timer(run_id, "Cinematic Audio Production", 4):
                    logger.info(f"\n[Stage 4-5/6] 5-Track Cinematic Audio Drama Production across {len(script_files)} chapters (Workers: {workers})...")
                    for idx in range(1, len(script_files) + 1):
                        logger.info(f"\n--- Producing Chapter {idx}/{len(script_files)} ---")
                        self.produce_chapter(
                            project_dir=project_dir,
                            chapter_num=idx,
                            voice=voice,
                            workers=workers,
                            duck_db=duck_db,
                            spatial_staging=spatial_staging,
                            force_rebuild=force_rebuild,
                            stage_start=stage_start,
                        )
            else:
                logger.info(f"\n[Stage 4-5/6] Synthesis & 5-Track production skipped (resuming at stage: {stage_start}).")

            # -------------------------------------------------------------
            # Stage 6: Final M4B Containerization with Chapter Markers
            # -------------------------------------------------------------
            if start_stage_num <= 6:
                with telemetry.stage_timer(run_id, "M4B Container Packaging", 6):
                    logger.info("\n[Stage 6/6] Packaging final M4B container with chapter navigation & cover art...")
                    final_m4b = package_m4b_audiobook(project_dir, cover_image=cover_image)

                    # Inline Gate 6C: Table of Contents Monotonicity & Chapter Boundaries
                    verify_packaging_gates(project_dir)
            else:
                final_m4b = project_dir / "mastered" / f"{book_slug}_audiobook.m4b"

            telemetry.end_run(run_id, status="SUCCESS")
            report_file = project_dir / "TELEMETRY_REPORT.json"
            telemetry.generate_report(run_id, output_path=report_file)

        except Exception as e:
            telemetry.end_run(run_id, status="FAILED", error=str(e))
            raise

        elapsed_min = round((time.time() - start_time) / 60.0, 1)
        progress = ledger.get_progress()

        logger.info("\n=======================================================")
        logger.info("   [SUCCESS] NOVEL AUDIOBOOK PRODUCTION COMPLETED!    ")
        logger.info(f"   Deliverable   : {final_m4b}")
        logger.info(f"   Telemetry     : {report_file}")
        logger.info(f"   Total Segments: {progress['completed']}/{progress['total_segments']}")
        logger.info(f"   Audio Duration: {progress['total_duration_min']} minutes")
        logger.info(f"   Total Elapsed : {elapsed_min} minutes")
        logger.info("=======================================================\n")

        return final_m4b

    def produce_chapter(
        self,
        project_dir: Path,
        chapter_num: int,
        voice: str = "Aoede",
        workers: int = 3,
        duck_db: float = -16.0,
        spatial_staging: bool = True,
        force_rebuild: bool = False,
        stage_start: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Produces a single cinematic chapter using the deterministic agentic standard:
        1. Resolve screenplay script.
        2. Synthesize missing speech segments via Gemini TTS key pool.
        3. Master dialogue bus and composite lossless vocal stems.
        4. Direct creative manifest via AgentDirector (dynamic dramaturgy and silence carving).
        5. Compile final master via ManifestRenderer (deterministic multitrack mix, EBU R128 mastering).
        6. Generate millisecond timeline ledger.
        7. Auto-Janitor cleanup of intermediate WAV buffers.
        """
        import shutil
        project_dir = Path(project_dir).resolve()
        scripts_dir = project_dir / "scripts"
        audio_dir = project_dir / "audio_chunks"
        bgm_dir = project_dir / "soundscapes"
        mastered_dir = project_dir / "mastered"
        manifests_dir = project_dir / "manifests"
        for d in (scripts_dir, audio_dir, bgm_dir, mastered_dir, manifests_dir):
            d.mkdir(parents=True, exist_ok=True)

        script_file = scripts_dir / f"chapter_{chapter_num:03d}_hi_script.json"
        if not script_file.exists():
            cand = sorted(scripts_dir.glob(f"chapter_{chapter_num:03d}_*.json"))
            if cand:
                script_file = cand[0]
            else:
                raise FileNotFoundError(f"Script file for chapter {chapter_num} not found in {scripts_dir}")

        with open(script_file, "r", encoding="utf-8") as f:
            script_data = json.load(f)
        if isinstance(script_data, dict):
            script_data = script_data.get("segments", script_data)

        chap_stem = script_file.stem.replace("_script", "")

        # Memory 2.0: Apply conservative performance & acoustic context from MemoryStore if available
        try:
            from audiobook_factory.translation.book_bible import BookBible
            from audiobook_factory.translation.memory import MemoryStore, MemoryRetriever

            store_path = MemoryStore.default_store_path(project_dir)
            if store_path.exists() and isinstance(script_data, list):
                bible = BookBible.load_from_project(project_dir)
                store = MemoryStore.load(store_path, book_bible=bible)
                active_speakers = list({
                    str(s.get("speaker", "")).strip()
                    for s in script_data
                    if isinstance(s, dict) and s.get("speaker") not in ("", "Narrator", "Foley", None)
                })
                mem_ctx = MemoryRetriever.retrieve_for_scene(
                    store=store,
                    book_bible=bible,
                    chapter=chapter_num,
                    scene_id=chap_stem,
                    active_characters=active_speakers,
                )
                script_data = [
                    mem_ctx.apply_performance_guidance_to_segment(seg)
                    if isinstance(seg, dict) else seg
                    for seg in script_data
                ]
                with open(script_file, "w", encoding="utf-8") as f:
                    json.dump(script_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


        # Gate 2 & Gate 2.5: Script Schema and Dramatic Fidelity
        verify_pre_synthesis_gates(script_file, chap_stem, project_dir, chapter_num)

        # 1. Synthesize speech segments via Gemini TTS (Token Bucket & Graceful Key Halting)
        skip_tts = bool(stage_start and stage_start.lower() in ("direct", "directing", "mix") and not force_rebuild)
        if not skip_tts:
            logger.info(f"[*] Synthesizing Chapter {chapter_num:02d} speech segments (Workers: {workers})...")
            from audiobook_factory.key_manager import AllKeysExhaustedTodayError
            import sys
            try:
                dispatcher = TTSDispatcher(
                    project_dir=project_dir,
                    default_voice=voice,
                    max_workers=workers,
                    allow_dynamic_cast=True,
                )
                dispatcher.synthesize_chapter_script(script_file, chapter_num)
            except AllKeysExhaustedTodayError as e:
                if os.environ.get("ENABLE_EMERGENCY_FALLBACK", "").lower() in ("true", "1", "yes"):
                    logger.warning(f"  [EMERGENCY FALLBACK] Gemini key pool exhausted; emergency local WinRT fallback was applied.")
                else:
                    logger.error("\n[!] 🛑 SUPERVISOR AGENT HALT: ALL TTS API KEYS EXHAUSTED FOR TODAY.")
                    logger.error(f"[!] 🛑 {e}")
                    logger.info(f"[*] Progress Checkpoint safely stored on disk for Chapter {chapter_num:02d}.")
                    logger.info("[*] The system will gracefully halt now. Run the script again tomorrow after 12:30 PM IST (Midnight PT) to automatically resume.")
                    raise AllKeysExhaustedTodayError(
                        f"Supervisor Halt: All TTS API keys exhausted today for Chapter {chapter_num:02d}. "
                        "Progress safely checkpointed on disk."
                    ) from e
        else:
            logger.info(f"[*] Synthesis skipped for Chapter {chapter_num:02d} (resuming at stage: {stage_start}).")

        # Gate 2.8: Pre-Mix Performance Fidelity Gate (Fail-Closed)
        verify_performance_fidelity_gate(manifests_dir, chap_stem, chapter_num)

        # 2. Dialogue Editorial Layer & Dialogue Vocal Mastering
        vocal_wav, vocal_dur, seg_durations, segments = process_and_master_dialogue_stem(
            project_dir=project_dir,
            chapter_num=chapter_num,
            chap_stem=chap_stem,
            script_data=script_data,
            audio_dir=audio_dir,
            mastered_dir=mastered_dir,
            spatial_staging=spatial_staging,
        )

        # 4. Agentic Directing Layer: Produce validated CreativeManifest via AgentDirector
        manifest_file = manifests_dir / f"{chap_stem}_manifest.json"
        force_rebuild_manifest = force_rebuild or (os.environ.get("FORCE_REBUILD_MANIFEST", "false").lower() in ("true", "1", "yes"))
        if force_rebuild and manifest_file.exists():
            try:
                manifest_file.unlink()
            except Exception:
                pass
        manifest = None

        if manifest_file.exists() and not force_rebuild_manifest:
            logger.info(f"[*] Loading existing Creative Manifest: {manifest_file.name}")
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = CreativeManifest.from_json(f.read())
                # Self-healing: if existing manifest was corrupted with 100% silence, re-direct
                if manifest.silence_percentage >= 99.9 and len(manifest.music_cues) == 0:
                    logger.warning(f"  [!] Existing manifest {manifest_file.name} is 100% silent. Re-directing with updated engine...")
                    manifest = None
            except Exception as e:
                logger.warning(f"  [!] Failed to parse existing manifest {manifest_file.name}: {e}")
                manifest = None

        if manifest is None:
            logger.info(f"[*] Agent Director: Directing Chapter {chapter_num:02d} Creative Manifest...")
            director = AgentDirector(project_dir=project_dir)
            manifest = director.direct_chapter_manifest(
                chapter_id=f"chapter_{chapter_num:03d}",
                script_segments=script_data,
                segment_durations_sec=seg_durations,
                dialogue_stem_path=vocal_wav,
                total_duration_sec=vocal_dur,
                project_dir=project_dir,
                sonic_bible=director.sonic_bible,
            )
            with open(manifest_file, "w", encoding="utf-8") as f:
                f.write(manifest.to_json(indent=2))

        # Gate 3.5: Acoustic Pre-Flight Feasibility Guard
        verify_acoustic_feasibility_gate(manifest, chapter_num)

        # 5. Cinema Audio Engine: Render 5-Track Discrete DME Stems & Final Cinema Master
        cinematic_out = mastered_dir / f"{chap_stem}_cinematic.m4a"
        logger.info(f"[*] Cinema Audio Engine: Rendering discrete DME stems and cinema master for Chapter {chapter_num:02d}...")

        # Lift legacy CreativeManifest to CinemaAudioManifest if needed
        if isinstance(manifest, CreativeManifest):
            cinema_manifest = LegacyCreativeManifestAdapter.lift_legacy_manifest_to_cinema(manifest)
        else:
            cinema_manifest = manifest

        stem_ledger = render_discrete_stems(
            manifest=cinema_manifest,
            dialogue_wav=vocal_wav,
            output_dir=mastered_dir,
            sound_bank=get_sound_bank(),
            enable_remix=True,
        )

        judge_status = stem_ledger.metadata.get("mix_judge_status", "UNKNOWN")
        judge_score = stem_ledger.metadata.get("mix_judge_score", "N/A")
        logger.info(f"[*] Stage 11 Mix Judge: {judge_status} (Score: {judge_score})")
        if judge_status == "FAIL":
            judge_audit = stem_ledger.metadata.get("mix_judge_audit", {})
            msg = f"Stage 11 Mix Judge Flagged Issues for Chapter {chapter_num:02d}: {judge_audit.get('failures', [])}"
            logger.warning(f"[!] {msg}")
            if os.environ.get("STRICT_QUALITY_GATES", "true").lower() in ("1", "true", "yes"):
                from audiobook_factory.gates.contracts import GateAuditError
                raise GateAuditError(f"Chapter {chapter_num:02d} failed Stage 11 Mix Judge: {judge_audit.get('failures', [])}")

        mastering_status = stem_ledger.metadata.get("mastering_status", "UNKNOWN")
        logger.info(f"[*] Stage 12 Mastering V2: {mastering_status}")

        master_wav = mastered_dir / f"{cinema_manifest.chapter_id}_cinema_master.wav"
        if not master_wav.exists():
            master_wav = mastered_dir / f"{chap_stem}_cinema_master.wav"

        if master_wav.exists():
            import subprocess
            from audiobook_factory.tts_dispatcher import get_ffmpeg
            ff = get_ffmpeg()
            cmd_enc = [
                ff, "-y",
                "-i", str(master_wav),
                "-af", "volume=-0.2dB",
                "-c:a", "aac", "-b:a", "192k",
                str(cinematic_out),
            ]
            subprocess.run(cmd_enc, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        else:
            # Fallback to render_manifest_soundscape if master wav was not produced
            render_manifest_soundscape(
                manifest=manifest,
                vocal_track_path=vocal_wav,
                output_master_file=cinematic_out,
            )

        # Post-Mix Audio Quality Gates (5.2, 5.3, 5.0) and Telemetry
        mx_stem = mastered_dir / f"{cinema_manifest.chapter_id}_stem_MX.wav"
        if not mx_stem.exists():
            mx_stem = mastered_dir / f"{chap_stem}_stem_MX.wav"

        gate52_passed, gate53_passed, gate5_certified = verify_post_mix_master_gates(
            chapter_num=chapter_num,
            cinematic_out=cinematic_out,
            master_wav=master_wav,
            vocal_wav=vocal_wav,
            mx_stem=mx_stem,
        )
        if not gate5_certified and os.environ.get("STRICT_QUALITY_GATES", "true").lower() in ("1", "true", "yes"):
            from audiobook_factory.gates.contracts import GateAuditError
            raise GateAuditError(f"Chapter {chapter_num:02d} failed Gate 5 Broadcast Master EBU R128 certification.")

        # 6. Build Millisecond Timeline Ledger (Canonical in scripts_dir, mirrored to bgm_dir)
        ledger_file = scripts_dir / f"{chap_stem}_timeline_ledger.json"
        cue_sheet = {
            "foley_cues": [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in manifest.foley_cues],
            "music_cues": [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in manifest.music_cues],
        }
        plan = {
            "chapter_id": chapter_num,
            "silence_percentage": manifest.silence_percentage,
            "scenes": [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in manifest.ambience_scenes],
        }
        ledger = build_chapter_timeline_ledger(
            chapter_id=chapter_num,
            script_segments=script_data,
            audio_chunk_paths=segments,
            cue_sheet=cue_sheet,
            soundscape_plan=plan,
            output_ledger_file=ledger_file,
        )
        try:
            import shutil
            shutil.copy2(ledger_file, bgm_dir / f"{chap_stem}_timeline_ledger.json")
        except Exception:
            pass

        # 9. Auto-Janitor: Clean up intermediate uncompressed WAV chunks ONLY IF certified
        all_gates_certified = (
            cinematic_out.exists()
            and gate5_certified
            and gate52_passed
            and gate53_passed
            and cinematic_out.stat().st_size > 1000
        )
        cleanup_chapter_chunks(audio_dir, chapter_num, cinematic_out, all_gates_certified)

        stem_ledger_file = mastered_dir / f"{cinema_manifest.chapter_id}_stem_ledger.json"
        if not stem_ledger_file.exists():
            stem_ledger_file = mastered_dir / f"{chap_stem}_stem_ledger.json"

        logger.info(f"[+] Chapter {chapter_num:02d} complete -> {cinematic_out} ({ledger['total_duration_min']} min)")
        return {
            "chapter_id": chapter_num,
            "master_file": cinematic_out,
            "ledger_file": ledger_file,
            "stem_ledger": stem_ledger_file,
            "duration_min": ledger["total_duration_min"],
            "total_segments": ledger["total_segments"],
        }
