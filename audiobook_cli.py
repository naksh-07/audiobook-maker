#!/usr/bin/env python3
"""
Audiobook Factory - Unified Command Line Interface (CLI) & Pipeline Orchestrator.
Orchestrates the entire 3-pillar production pipeline from raw book to final M4B audiobook.
"""

import sys
import argparse
from pathlib import Path

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
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.packager import package_m4b_audiobook


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


def cmd_package(args):
    project_dir = PROJECTS_DIR / args.book
    cover = Path(args.cover) if args.cover else None
    final_m4b = package_m4b_audiobook(project_dir, cover_image=cover)
    print(f"\n[DONE] Finished Audiobook Package: {final_m4b}")


def cmd_auto(args):
    """End-to-end 1-command autonomous run."""
    input_file = Path(args.file)
    print(f"\n=======================================================")
    print(f"   STARTING AUTONOMOUS AUDIOBOOK PRODUCTION PIPELINE   ")
    print(f"=======================================================")

    # 1. Extract
    meta = process_book_file(input_file, PROJECTS_DIR)
    book_slug = meta["book_id"]
    project_dir = PROJECTS_DIR / book_slug

    # 2. Translate (optional)
    if args.hindi:
        translate_book_project(project_dir)

    # 3. Script
    generate_project_scripts(project_dir, use_hindi=args.hindi, dramatized=args.dramatized)

    # 4. Synthesize
    dispatcher = TTSDispatcher(
        project_dir=project_dir,
        default_backend=args.backend,
        default_voice=args.voice,
    )
    script_files = sorted((project_dir / "scripts").glob("chapter_*_script.json"))
    for idx, sf in enumerate(script_files, 1):
        dispatcher.synthesize_chapter_script(sf, idx)

    # 5. Master
    mastered_dir = project_dir / "mastered"
    audio_dir = project_dir / "audio_chunks"
    for idx, sf in enumerate(script_files, 1):
        chap_stem = sf.stem.replace("_script", "")
        segments = sorted(audio_dir.glob(f"c{idx:03d}_*.wav"))
        if segments:
            out_file = mastered_dir / f"{chap_stem}_mastered.m4a"
            concatenate_and_master_chapter(segments, out_file)

    # 6. Package
    cover = Path(args.cover) if args.cover else None
    final_m4b = package_m4b_audiobook(project_dir, cover_image=cover)

    print(f"\n=======================================================")
    print(f"   [SUCCESS] AUDIOBOOK PRODUCTION COMPLETED!          ")
    print(f"   Deliverable: {final_m4b}")
    print(f"=======================================================\n")


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
    p_translate.add_argument("--model", default="gemini-2.5-flash", help="Gemini translation model")

    # script
    p_script = subparsers.add_parser("script", help="Generate screenplay script JSON with speaker tags")
    p_script.add_argument("book", help="Project book slug")
    p_script.add_argument("--hindi", action="store_true", help="Use translated Hindi chapters")
    p_script.add_argument("--dramatized", action="store_true", help="Multi-voice character attribution mode")

    # synthesize
    p_synth = subparsers.add_parser("synthesize", help="Synthesize audio segments via Gemini or Kokoro TTS")
    p_synth.add_argument("book", help="Project book slug")
    p_synth.add_argument("--backend", default="gemini_tts", choices=["gemini_tts", "kokoro"], help="TTS engine")
    p_synth.add_argument("--voice", default="Aoede", help="Default voice persona")

    # master
    p_master = subparsers.add_parser("master", help="Concatenate segments and master audio with EBU R128")
    p_master.add_argument("book", help="Project book slug")

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

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "extract": cmd_extract,
        "translate": cmd_translate,
        "script": cmd_script,
        "synthesize": cmd_synthesize,
        "master": cmd_master,
        "package": cmd_package,
        "auto": cmd_auto,
    }
    cmds[args.subcommand](args)


if __name__ == "__main__":
    main()
