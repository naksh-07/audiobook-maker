from __future__ import annotations
import os
import re
import json
import time
from pathlib import Path

from audiobook_factory.cli.context import get_projects_dir, get_workspace_dir
from audiobook_factory.extractor import process_book_file
from audiobook_factory.translator import translate_book_project
from audiobook_factory.script_builder import generate_project_scripts
from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.orchestrator import PipelineOrchestrator

def cmd_extract(args):
    input_file = Path(args.file)
    force_gate = getattr(args, "force_gate", False)
    meta = process_book_file(input_file, get_projects_dir(), force_gate=force_gate)
    print(f"\n[OK] Project created: '{meta['book_id']}' at {get_projects_dir() / meta['book_id']}")



def cmd_translate(args):
    project_dir = get_projects_dir() / args.book
    trans_dir = translate_book_project(project_dir, model=args.model)
    print(f"\n[OK] Hindi translation complete at: {trans_dir}")



def cmd_script(args):
    project_dir = get_projects_dir() / args.book
    scripts_dir = generate_project_scripts(
        project_dir,
        use_hindi=args.hindi,
        dramatized=args.dramatized,
    )
    print(f"\n[OK] Scripts ready at: {scripts_dir}")



def cmd_synthesize(args):
    project_dir = get_projects_dir() / args.book
    scripts_dir = project_dir / "scripts"
    if not scripts_dir.exists():
        raise FileNotFoundError(f"Scripts directory missing. Run 'script' command first.")

    dispatcher = TTSDispatcher(
        project_dir=project_dir,
        default_backend=args.backend,
        default_voice=args.voice,
    )

    script_files = sorted(scripts_dir.glob("chapter_*_script.json"))
    if not script_files:
        raise FileNotFoundError(f"No script files found in {scripts_dir}")

    for sf in script_files:
        m = re.search(r"chapter_(\d+)", sf.stem)
        ch_num = int(m.group(1)) if m else 1
        dispatcher.synthesize_chapter_script(sf, ch_num)

    print(f"\n[OK] Synthesis complete for {len(script_files)} chapters!")



def cmd_master(args):
    project_dir = get_projects_dir() / args.book
    audio_dir = project_dir / "audio_chunks"
    mastered_dir = project_dir / "mastered"
    mastered_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = project_dir / "scripts"
    script_files = sorted(scripts_dir.glob("chapter_*_script.json"))

    for sf in script_files:
        chap_stem = sf.stem.replace("_script", "")
        m = re.search(r"chapter_(\d+)", sf.stem)
        ch_num = int(m.group(1)) if m else 1
        # Find audio segments for this chapter, deduplicating multiple takes per segment
        raw_segments = sorted(audio_dir.glob(f"c{ch_num:03d}_*.wav"))
        if not raw_segments:
            print(f"[!] Warning: No audio segments found for chapter {ch_num}, skipping.")
            continue

        seg_dict = {}
        for p in raw_segments:
            m_s = re.search(r"_s(\d{4})_", p.name)
            if m_s:
                s_idx = int(m_s.group(1))
                if s_idx not in seg_dict or p.stat().st_mtime > seg_dict[s_idx].stat().st_mtime:
                    seg_dict[s_idx] = p
        segments = [seg_dict[k] for k in sorted(seg_dict.keys())] if seg_dict else raw_segments

        out_file = mastered_dir / f"{chap_stem}_mastered.m4a"
        concatenate_and_master_chapter(segments, out_file)

    print(f"\n[OK] All chapters mastered at: {mastered_dir}")



def cmd_produce(args):
    """Single-command cinematic chapter or full-book production using 5-track standard."""
    project_dir = get_projects_dir() / args.book
    orchestrator = PipelineOrchestrator(get_projects_dir())
    force_rebuild = getattr(args, "force_rebuild", False)
    stage_start = getattr(args, "stage_start", None)

    if args.chapter:
        print(f"[*] Producing Cinematic Chapter {args.chapter} for '{args.book}'...")
        res = orchestrator.produce_chapter(
            project_dir=project_dir,
            chapter_num=args.chapter,
            voice=args.voice,
            workers=args.workers,
            duck_db=args.duck_db,
            force_rebuild=force_rebuild,
            stage_start=stage_start,
        )
        print(f"\n[OK] Chapter {args.chapter} produced successfully!")
        print(f"     Master File : {res['master_file']}")
        print(f"     Ledger File : {res['ledger_file']}")
        print(f"     Duration    : {res['duration_min']} minutes ({res['total_segments']} segments)")
    elif args.all:
        scripts_dir = project_dir / "scripts"
        scripts = sorted(scripts_dir.glob("chapter_*_script.json"))
        print(f"[*] Producing all {len(scripts)} chapters for '{args.book}'...")
        for s_file in scripts:
            m = re.search(r"chapter_(\d+)", s_file.stem, re.IGNORECASE)
            ch_num = int(m.group(1)) if m else 1
            orchestrator.produce_chapter(
                project_dir=project_dir,
                chapter_num=ch_num,
                voice=args.voice,
                workers=args.workers,
                duck_db=args.duck_db,
                force_rebuild=force_rebuild,
                stage_start=stage_start,
            )
        print(f"\n[OK] All {len(scripts)} chapters produced successfully!")
    else:
        print("[!] Please specify --chapter <num> or --all.")



def cmd_auto(args):
    """End-to-end 1-command autonomous run using PipelineOrchestrator."""
    input_file = Path(args.file)
    cover = Path(args.cover) if args.cover else None
    workers = getattr(args, "workers", 3)
    force_gate = getattr(args, "force_gate", False)
    force_rebuild = getattr(args, "force_rebuild", False)
    stage_start = getattr(args, "stage_start", None)

    orchestrator = PipelineOrchestrator(get_projects_dir())
    orchestrator.run_autonomous_pipeline(
        input_file=input_file,
        hindi=args.hindi,
        dramatized=args.dramatized,
        voice=args.voice,
        cover_image=cover,
        workers=workers,
        force_gate=force_gate,
        force_rebuild=force_rebuild,
        stage_start=stage_start,
    )


