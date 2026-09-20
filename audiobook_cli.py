#!/usr/bin/env python3
"""
Audiobook Factory - Unified Command Line Interface (CLI) & Pipeline Orchestrator.
Orchestrates the entire 3-pillar production pipeline from raw book to final M4B audiobook.
"""

import sys
import argparse
from pathlib import Path

# Configure UTF-8 streams for cross-platform Devanagari/Hindi logging
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Paths
WORKSPACE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = WORKSPACE_DIR / "audiobooks" / "projects"

# Add package to sys.path
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.extractor import process_book_file
from audiobook_factory.translator import translate_book_project
from audiobook_factory.script_builder import generate_project_scripts
from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.soundscape import (
    detect_chapter_mood,
    generate_procedural_ambient_bed,
    resolve_ambient_score,
    generate_chapter_soundscape_plan,
    render_chapter_soundscape,
    generate_project_soundscapes,
    fetch_musicgen,
    apply_dynamic_sidechain_ducking,
    get_audio_duration,
)
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.packager import package_m4b_audiobook
from audiobook_factory.orchestrator import PipelineOrchestrator


def cmd_extract(args):
    input_file = Path(args.file)
    meta = process_book_file(input_file, PROJECTS_DIR)
    print(f"\n[OK] Project created: '{meta['book_id']}' at {PROJECTS_DIR / meta['book_id']}")


def cmd_translate(args):
    project_dir = PROJECTS_DIR / args.book
    trans_dir = translate_book_project(project_dir, model=args.model)
    print(f"\n[OK] Hindi translation complete at: {trans_dir}")


def cmd_script(args):
    project_dir = PROJECTS_DIR / args.book
    scripts_dir = generate_project_scripts(
        project_dir,
        use_hindi=args.hindi,
        dramatized=args.dramatized,
    )
    print(f"\n[OK] Scripts ready at: {scripts_dir}")


def cmd_synthesize(args):
    project_dir = PROJECTS_DIR / args.book
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

    for idx, sf in enumerate(script_files, 1):
        dispatcher.synthesize_chapter_script(sf, idx)

    print(f"\n[OK] Synthesis complete for {len(script_files)} chapters!")


def cmd_master(args):
    project_dir = PROJECTS_DIR / args.book
    audio_dir = project_dir / "audio_chunks"
    mastered_dir = project_dir / "mastered"
    mastered_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = project_dir / "scripts"
    script_files = sorted(scripts_dir.glob("chapter_*_script.json"))

    for idx, sf in enumerate(script_files, 1):
        chap_stem = sf.stem.replace("_script", "")
        # Find audio segments for this chapter
        segments = sorted(audio_dir.glob(f"c{idx:03d}_*.wav"))
        if not segments:
            print(f"[!] Warning: No audio segments found for chapter {idx}, skipping.")
            continue

        out_file = mastered_dir / f"{chap_stem}_mastered.m4a"
        concatenate_and_master_chapter(segments, out_file)

    print(f"\n[OK] All chapters mastered at: {mastered_dir}")


def cmd_soundscape(args):
    """Generate Director Soundscape JSON Plans for all chapters."""
    project_dir = PROJECTS_DIR / args.book
    soundscapes_dir = generate_project_soundscapes(project_dir)
    print(f"\n[OK] Soundscape JSON plans ready at: {soundscapes_dir}")


def cmd_bgm(args):
    """Generate ambient score / background music and apply dynamic sidechain ducking."""
    import json
    project_dir = PROJECTS_DIR / args.book
    mastered_dir = project_dir / "mastered"
    bgm_dir = project_dir / "soundscapes"
    bgm_dir.mkdir(parents=True, exist_ok=True)

    mastered_chapters = sorted(mastered_dir.glob("chapter_*_mastered.m4a"))
    if not mastered_chapters:
        print(f"[!] No mastered chapters found in {mastered_dir}. Run 'master' first.")
        return

    print(f"[*] Applying cinematic background score & sidechain ducking ({len(mastered_chapters)} chapters)...")
    for ch in mastered_chapters:
        chap_stem = ch.stem.replace("_mastered", "")
        script_file = project_dir / "scripts" / f"{chap_stem}_script.json"
        soundscape_plan_file = bgm_dir / f"{chap_stem}_soundscape.json"
        text_sample = ""
        script_data = []

        if script_file.exists():
            with open(script_file, "r", encoding="utf-8") as f:
                script_data = json.load(f)
                text_sample = " ".join([seg.get("text", "") for seg in script_data[:10]])

        # 1. Resolve or generate Soundscape JSON Plan
        if soundscape_plan_file.exists():
            with open(soundscape_plan_file, "r", encoding="utf-8") as f:
                plan = json.load(f)
        else:
            print(f"  [+] Generating Soundscape Plan JSON for {chap_stem}...")
            plan = generate_chapter_soundscape_plan(text_sample, script_data)
            with open(soundscape_plan_file, "w", encoding="utf-8") as f:
                json.dump(plan, f, ensure_ascii=False, indent=2)

        primary_mood = plan.get("primary_mood", "default")
        duck_db = plan.get("ducking_attenuation_db", args.duck_db)
        scenes = plan.get("scenes", [])
        print(f"  Chapter {chap_stem}: Mood = '{primary_mood}' ({len(scenes)} scenes), Ducking = {duck_db} dB")

        dur = get_audio_duration(ch)
        bgm_raw = bgm_dir / f"{chap_stem}_bgm.wav"

        # Calculate segment durations if segments exist
        segment_durations = {}
        for seg in script_data:
            s_idx = seg.get("index", 1)
            seg_matches = sorted((project_dir / "audio_chunks").glob(f"c*s{s_idx:04d}_*.wav"))
            if seg_matches:
                segment_durations[s_idx] = get_audio_duration(seg_matches[0])

        if args.engine == "musicgen":
            prompt = plan.get("musicgen_prompt", MOOD_PRESETS.get(primary_mood, {}).get("musicgen_prompt", ""))
            fetch_musicgen(prompt, dur, bgm_raw)
        else:
            render_chapter_soundscape(plan, dur, bgm_raw, segment_durations=segment_durations)

        # Apply ducking
        cinematic_out = mastered_dir / f"{chap_stem}_cinematic.m4a"
        apply_dynamic_sidechain_ducking(ch, bgm_raw, cinematic_out, duck_attenuation_db=duck_db)

    print(f"\n[OK] Cinematic scoring and sidechain ducking complete at: {mastered_dir}")


def cmd_package(args):
    project_dir = PROJECTS_DIR / args.book
    cover = Path(args.cover) if args.cover else None
    final_m4b = package_m4b_audiobook(project_dir, cover_image=cover)
    print(f"\n[DONE] Finished Audiobook Package: {final_m4b}")


def cmd_bank(args):
    """Manage and inspect local Sound Bank (SQLite FTS5 index)."""
    from audiobook_factory.sound_bank import SoundBank
    bank = SoundBank()

    action = getattr(args, "action", "stats") or "stats"

    if action == "scan":
        print("[*] Scanning and indexing audio assets into Sound Bank...")
        stats = bank.scan_and_index(extra_dirs=[
            WORKSPACE_DIR / "audiobooks" / "soundscapes" / "stems",
            WORKSPACE_DIR / "audiobooks" / "soundscapes" / "sfx",
        ])
        print(f"[+] Scan complete: {stats}")
    elif action == "search":
        results = bank.search(args.query, limit=args.limit)
        print(f"\n[*] Found {len(results)} matches for '{args.query}':")
        for r in results:
            print(f"  [{r['category']}] {r['filename']} (Mood: {r['mood']}, Dur: {r['duration_sec']:.1f}s)")
            print(f"      Path: {r['filepath']}")
    elif action == "stats":
        s = bank.stats()
        print("\n=======================================================")
        print("   SOUND BANK STATUS SUMMARY                          ")
        print("=======================================================")
        print(f"  Total Sounds Indexed: {s['total_sounds']}")
        print(f"  Total Duration      : {s['total_duration_min']} minutes")
        print(f"  Total Storage Size  : {s['total_size_mb']} MB")
        print(f"  Categories Breakdown: {s['categories']}")
        print(f"  Moods Breakdown     : {s['moods']}")
        print(f"  SQLite FTS5 DB      : {s['database_path']}")
        print("=======================================================\n")


def cmd_auto(args):
    """End-to-end 1-command autonomous run using PipelineOrchestrator."""
    input_file = Path(args.file)
    cover = Path(args.cover) if args.cover else None
    workers = getattr(args, "workers", 3)

    orchestrator = PipelineOrchestrator(PROJECTS_DIR)
    orchestrator.run_autonomous_pipeline(
        input_file=input_file,
        hindi=args.hindi,
        dramatized=args.dramatized,
        voice=args.voice,
        cover_image=cover,
        workers=workers,
    )


def main():
    parser = argparse.ArgumentParser(
        prog="audiobook-factory",
        description="Production Audiobook Factory CLI (Extraction, Translation, TTS & M4B Packaging)",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Pipeline step to execute")

    # extract
    p_extract = subparsers.add_parser("extract", help="Extract and segment book file into clean Markdown chapters")
    p_extract.add_argument("file", help="Input book path (.epub, .pdf, .txt, .md)")

    # translate
    p_translate = subparsers.add_parser("translate", help="Translate extracted chapters into literary Hindi")
    p_translate.add_argument("book", help="Project book slug (folder name)")
    p_translate.add_argument("--model", default="gemini-flash-latest", help="Gemini translation model")

    # script
    p_script = subparsers.add_parser("script", help="Generate screenplay script JSON with speaker tags")
    p_script.add_argument("book", help="Project book slug")
    p_script.add_argument("--hindi", action="store_true", help="Use translated Hindi chapters")
    p_script.add_argument("--dramatized", action="store_true", help="Multi-voice character attribution mode")

    # soundscape
    p_sc = subparsers.add_parser("soundscape", help="Generate Director Soundscape JSON Plans with moods and SFX")
    p_sc.add_argument("book", help="Project book slug")

    # synthesize
    p_synth = subparsers.add_parser("synthesize", help="Synthesize audio segments via Gemini or Kokoro TTS")
    p_synth.add_argument("book", help="Project book slug")
    p_synth.add_argument("--backend", default="gemini_tts", choices=["gemini_tts", "kokoro"], help="TTS engine")
    p_synth.add_argument("--voice", default="Aoede", help="Default voice persona")

    # master
    p_master = subparsers.add_parser("master", help="Concatenate segments and master audio with EBU R128")
    p_master.add_argument("book", help="Project book slug")

    # bgm
    p_bgm = subparsers.add_parser("bgm", help="Generate ambient score and apply dynamic sidechain ducking")
    p_bgm.add_argument("book", help="Project book slug")
    p_bgm.add_argument("--engine", default="ambient_bed", choices=["ambient_bed", "musicgen"], help="Music generation engine")
    p_bgm.add_argument("--duck-db", default=-16.0, type=float, help="Sidechain attenuation in dB (default: -16)")

    # package
    p_pack = subparsers.add_parser("package", help="Assemble final M4B container with chapters")
    p_pack.add_argument("book", help="Project book slug")
    p_pack.add_argument("--cover", default=None, help="Cover art image path")

    # auto
    p_auto = subparsers.add_parser("auto", help="Run entire end-to-end pipeline in one command")
    p_auto.add_argument("file", help="Input book path")
    p_auto.add_argument("--hindi", action="store_true", help="Translate English book to Hindi")
    p_auto.add_argument("--backend", default="gemini_tts", choices=["gemini_tts", "kokoro"], help="TTS engine")
    p_auto.add_argument("--voice", default="Aoede", help="Voice persona")
    p_auto.add_argument("--dramatized", action="store_true", help="Multi-voice dramatization")
    p_auto.add_argument("--cover", default=None, help="Cover art image path")
    p_auto.add_argument("--workers", default=3, type=int, help="Number of concurrent TTS synthesis workers (default: 3)")

    # bank
    p_bank = subparsers.add_parser("bank", help="Manage and search local Sound Bank (SQLite FTS5)")
    p_bank_subs = p_bank.add_subparsers(dest="action", help="Bank action")
    p_bank_subs.add_parser("scan", help="Scan and index audio files into Sound Bank")
    p_bank_subs.add_parser("stats", help="Display Sound Bank statistics")
    p_b_search = p_bank_subs.add_parser("search", help="Search sounds by keywords/tags")
    p_b_search.add_argument("query", help="Keyword or search query")
    p_b_search.add_argument("--limit", default=5, type=int, help="Maximum matches")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "extract": cmd_extract,
        "translate": cmd_translate,
        "script": cmd_script,
        "soundscape": cmd_soundscape,
        "synthesize": cmd_synthesize,
        "master": cmd_master,
        "bgm": cmd_bgm,
        "package": cmd_package,
        "bank": cmd_bank,
        "auto": cmd_auto,
    }
    cmds[args.subcommand](args)


if __name__ == "__main__":
    main()
