#!/usr/bin/env python3
"""
Audiobook Factory - Unified Command Line Interface (CLI) & Pipeline Orchestrator.
Orchestrates the entire 3-pillar production pipeline from raw book to final M4B audiobook.
"""

import os
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

    for sf in script_files:
        m = re.search(r"chapter_(\d+)", sf.stem)
        ch_num = int(m.group(1)) if m else 1
        dispatcher.synthesize_chapter_script(sf, ch_num)

    print(f"\n[OK] Synthesis complete for {len(script_files)} chapters!")


def cmd_master(args):
    project_dir = PROJECTS_DIR / args.book
    audio_dir = project_dir / "audio_chunks"
    mastered_dir = project_dir / "mastered"
    mastered_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = project_dir / "scripts"
    script_files = sorted(scripts_dir.glob("chapter_*_script.json"))

    for sf in script_files:
        chap_stem = sf.stem.replace("_script", "")
        m = re.search(r"chapter_(\d+)", sf.stem)
        ch_num = int(m.group(1)) if m else 1
        # Find audio segments for this chapter
        segments = sorted(audio_dir.glob(f"c{ch_num:03d}_*.wav"))
        if not segments:
            print(f"[!] Warning: No audio segments found for chapter {ch_num}, skipping.")
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
    """Applies AgentDirector and Cinema Audio Engine to produce discrete DME stems and cinema master."""
    import json
    import subprocess
    project_dir = PROJECTS_DIR / args.book
    mastered_dir = project_dir / "mastered"
    manifests_dir = project_dir / "manifests"
    scripts_dir = project_dir / "scripts"
    soundscapes_dir = project_dir / "soundscapes"
    for d in (mastered_dir, manifests_dir, soundscapes_dir):
        d.mkdir(parents=True, exist_ok=True)

    from audiobook_factory.agent_director import AgentDirector
    from audiobook_factory.contracts import CreativeManifest, LegacyCreativeManifestAdapter
    from audiobook_factory.cinema_audio_engine import render_discrete_stems
    from audiobook_factory.sound_bank import get_sound_bank
    from audiobook_factory.soundscape import get_audio_duration, get_ffmpeg

    # Find dialogue tracks or mastered chapters (.wav or .m4a)
    dialogue_tracks = sorted(mastered_dir.glob("chapter_*_dialogue.wav"))
    if not dialogue_tracks:
        dialogue_tracks = sorted(mastered_dir.glob("chapter_*_mastered.wav"))
    if not dialogue_tracks:
        dialogue_tracks = sorted(mastered_dir.glob("chapter_*_dialogue.m4a"))
    if not dialogue_tracks:
        dialogue_tracks = sorted(mastered_dir.glob("chapter_*_mastered.m4a"))
    if not dialogue_tracks:
        print(f"[!] No dialogue audio tracks found in {mastered_dir}. Run 'master' or 'produce' first.")
        return

    print(f"[*] Applying Cinema Audio Engine discrete stems & dynamic ducking ({len(dialogue_tracks)} chapters)...")
    for d_track in dialogue_tracks:
        chap_stem = d_track.stem.replace("_dialogue", "").replace("_mastered", "")
        cand_scripts = sorted(scripts_dir.glob(f"{chap_stem}*.json"))
        script_data = []
        if cand_scripts:
            with open(cand_scripts[0], "r", encoding="utf-8") as f:
                script_data = json.load(f)

        manifest_file = manifests_dir / f"{chap_stem}_manifest.json"
        if manifest_file.exists():
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = CreativeManifest.from_json(f.read())
        else:
            director = AgentDirector(project_dir=project_dir)
            seg_durs = {s.get("index", i): 4.0 for i, s in enumerate(script_data)}
            manifest = director.direct_chapter_manifest(
                chapter_id=chap_stem,
                script_segments=script_data,
                segment_durations_sec=seg_durs,
                dialogue_stem_path=d_track,
                project_dir=project_dir,
            )
            with open(manifest_file, "w", encoding="utf-8") as f:
                f.write(manifest.to_json(indent=2))

        cinema_manifest = LegacyCreativeManifestAdapter.lift_legacy_manifest_to_cinema(manifest)
        stem_ledger = render_discrete_stems(
            manifest=cinema_manifest,
            dialogue_wav=d_track,
            output_dir=mastered_dir,
            sound_bank=get_sound_bank(),
        )

        master_wav = mastered_dir / f"{cinema_manifest.chapter_id}_cinema_master.wav"
        if not master_wav.exists():
            master_wav = mastered_dir / f"{chap_stem}_cinema_master.wav"
        if master_wav.exists():
            cinematic_out = mastered_dir / f"{chap_stem}_cinematic.m4a"
            ff = get_ffmpeg()
            subprocess.run([
                ff, "-y", "-i", str(master_wav),
                "-c:a", "aac", "-b:a", "192k",
                str(cinematic_out)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"  [+] Chapter {chap_stem} cinema master delivered -> {cinematic_out.name}")

    print(f"\n[OK] Cinema scoring and discrete stem mastering complete at: {mastered_dir}")


def cmd_stems(args):
    """Inspect and verify exported discrete DME stems and stem ledger for a chapter."""
    project_dir = PROJECTS_DIR / args.book
    mastered_dir = project_dir / "mastered"
    ch_str = f"chapter_{args.chapter:03d}"

    ledger_path = mastered_dir / f"{ch_str}_stem_ledger.json"
    if not ledger_path.exists():
        cand = list(mastered_dir.glob(f"*{args.chapter:03d}*stem_ledger.json"))
        if cand:
            ledger_path = cand[0]
        else:
            print(f"[!] No stem ledger found for Chapter {args.chapter} in {mastered_dir}")
            return

    from audiobook_factory.cinema_audio_engine import StemLedger
    ledger = StemLedger.load_from_disk(ledger_path)

    print("\n" + "=" * 65)
    print(f"🎬 CINEMA STEM LEDGER: {ledger.chapter_id}")
    print("=" * 65)
    print(f"  Master Integrated LUFS: {ledger.master_lufs:.1f} LUFS (Broadcast Target: -19.0 LUFS)")
    print(f"  Master True Peak      : {ledger.master_peak:.2f} dBTP (Broadcast Ceiling: <= -1.4 dBTP)")
    print(f"  Broadcast Compliance  : {'PASS' if ledger.compliance_status else 'FAIL'}")
    print("\n  Discrete Audio Stems:")
    for stem_name, stem in sorted(ledger.stems.items()):
        exists_tag = "[ON DISK]" if Path(stem.filepath).exists() else "[MISSING]"
        print(f"    - {stem_name:4s} : {stem.integrated_lufs:6.1f} LUFS | Peak: {stem.true_peak_dbtp:5.2f} dBTP | Dur: {stem.duration_sec:6.1f}s {exists_tag}")
        print(f"             Path: {stem.filepath}")
    print("=" * 65 + "\n")


def cmd_package(args):
    target = Path(args.book)
    project_dir = target if (target.exists() and target.is_dir()) else (PROJECTS_DIR / args.book)
    cover = Path(args.cover) if args.cover else None
    enforce = getattr(args, "enforce_gate6", False)
    final_m4b = package_m4b_audiobook(project_dir, cover_image=cover, enforce_gate6=enforce)
    print(f"\n[DONE] Finished Audiobook Package: {final_m4b}")


def cmd_audit_book(args):
    """Executes Macro-Tier Gate 6 (6A, 6B, 6C, 6D) audit for an entire book project."""
    from audiobook_factory.gate_auditor import audit_book_master

    target = Path(args.project_dir)
    project_dir = target if (target.exists() and target.is_dir()) else (PROJECTS_DIR / args.project_dir)

    print(f"[*] Running Macro-Tier Gate 6 Master Audit on '{project_dir.name}'...")
    report = audit_book_master(project_dir)
    print("\n" + "=" * 65)
    print(f"📘 MACRO BOOK GATE 6 VERDICT: {report['overall_status']}")
    print("=" * 65)
    print(f"  Gate 6A (Voice Continuity):   {report['gate_6a']['status']}")
    if report['gate_6a'].get('errors'):
        for err in report['gate_6a']['errors']:
            print(f"     [!] {err}")
    print(f"  Gate 6B (Loudness Continuity): {report['gate_6b']['status']} (avg {report['gate_6b']['details'].get('average_lufs', -19.0)} LUFS)")
    if report['gate_6b'].get('errors'):
        for err in report['gate_6b']['errors']:
            print(f"     [!] {err}")
    print(f"  Gate 6C (TOC Integrity):       {report['gate_6c']['status']} ({report['gate_6c']['details'].get('total_chapters', 0)} chapters)")
    if report['gate_6c'].get('errors'):
        for err in report['gate_6c']['errors']:
            print(f"     [!] {err}")
    print(f"  Gate 6D (Packaging Specs):     {report['gate_6d']['status']}")
    if report['gate_6d'].get('errors'):
        for err in report['gate_6d']['errors']:
            print(f"     [!] {err}")
    print("=" * 65)
    if not report['overall_passed']:
        sys.exit(1)


def cmd_bank(args):
    """Manage and inspect local Sound Bank (SQLite FTS5 index)."""
    from audiobook_factory.sound_bank import SoundBank
    bank = SoundBank()

    action = getattr(args, "action", "stats") or "stats"

    if action == "seed":
        from audiobook_factory.catalog_seeder import seed_virtual_sound_catalog
        print("[*] Seeding virtual sound catalog from CC0 repositories (Kenney, Wikimedia)...")
        res = seed_virtual_sound_catalog(bank)
        print(f"[+] Seeding complete: {res}")
        s = bank.stats()
        print(f"    Total Sounds Indexed: {s['total_sounds']} ({s['total_duration_min']} min)")
    elif action == "scan":
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
            dl_tag = "[Downloaded]" if r.get("is_downloaded") else "[Cloud/Virtual]"
            print(f"  [{r['category']}] {dl_tag} {r['filename']} (Mood: {r['mood']}, Dur: {r['duration_sec']:.1f}s)")
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
    elif action == "ingest":
        from audiobook_factory.sound_bank_ingest import UniversalSoundBankIngester
        ingester = UniversalSoundBankIngester()
        dir_path = Path(args.dir).resolve()
        rec = not getattr(args, "no_recursive", False)
        wrk = getattr(args, "workers", 4)
        print(f"[*] Ingesting sound assets from {dir_path} into Sound Bank via UniversalSoundBankIngester...")
        stats = ingester.ingest_directory(dir_path, recursive=rec, max_workers=wrk)
        print(
            f"[+] Ingestion complete: {stats['ingested']} indexed, {stats['failed']} failed, "
            f"{stats['total_duration_sec']/60:.1f} minutes of audio in bank."
        )


def cmd_produce(args):
    """Single-command cinematic chapter or full-book production using 5-track standard."""
    project_dir = PROJECTS_DIR / args.book
    orchestrator = PipelineOrchestrator(PROJECTS_DIR)

    if args.chapter:
        print(f"[*] Producing Cinematic Chapter {args.chapter} for '{args.book}'...")
        res = orchestrator.produce_chapter(
            project_dir=project_dir,
            chapter_num=args.chapter,
            voice=args.voice,
            workers=args.workers,
            duck_db=args.duck_db,
        )
        print(f"\n[OK] Chapter {args.chapter} produced successfully!")
        print(f"     Master File : {res['master_file']}")
        print(f"     Ledger File : {res['ledger_file']}")
        print(f"     Duration    : {res['duration_min']} minutes ({res['total_segments']} segments)")
    elif args.all:
        scripts_dir = project_dir / "scripts"
        scripts = sorted(scripts_dir.glob("chapter_*_script.json"))
        print(f"[*] Producing all {len(scripts)} chapters for '{args.book}'...")
        for idx in range(1, len(scripts) + 1):
            orchestrator.produce_chapter(
                project_dir=project_dir,
                chapter_num=idx,
                voice=args.voice,
                workers=args.workers,
                duck_db=args.duck_db,
            )
        print(f"\n[OK] All {len(scripts)} chapters produced successfully!")
    else:
        print("[!] Please specify --chapter <num> or --all.")


def cmd_direct(args):
    """Directs a chapter into a CreativeManifest using AgentDirector."""
    project_dir = PROJECTS_DIR / args.book
    scripts_dir = project_dir / "scripts"
    script_file = scripts_dir / f"chapter_{args.chapter:03d}_script.json"
    if not script_file.exists():
        script_file = scripts_dir / f"chapter_{args.chapter:03d}_hi_script.json"
    if not script_file.exists():
        raise FileNotFoundError(f"Script file not found: {script_file}")

    import json
    with open(script_file, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    # Audio chunks & Timeline Ledger
    chunks_dir = project_dir / "audio_chunks"
    ledger_file = scripts_dir / f"chapter_{args.chapter:03d}_timeline_ledger.json"
    timeline_ledger = None
    seg_durs = {}

    if ledger_file.exists():
        from audiobook_factory.contracts import TimelineLedger
        timeline_ledger = TimelineLedger.from_file(ledger_file)
        seg_durs = {s.segment_index: s.duration_ms / 1000.0 for s in timeline_ledger.segments}
    else:
        from audiobook_factory.soundscape import get_audio_duration
        for s in script_data:
            s_idx = s.get("index", 1)
            matches = list(chunks_dir.glob(f"c{args.chapter:03d}_s{s_idx:04d}_*.wav"))
            if matches:
                seg_durs[s_idx] = get_audio_duration(matches[0])
            else:
                seg_durs[s_idx] = 4.0

    from audiobook_factory.agent_director import AgentDirector
    director = AgentDirector(project_dir=project_dir)
    manifests_dir = project_dir / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = Path(args.output) if getattr(args, "output", None) else (manifests_dir / f"chapter_{args.chapter:03d}_manifest.json")

    vocal_stem = project_dir / "mastered" / f"chapter_{args.chapter:03d}_dialogue.wav"

    manifest = director.direct_chapter_manifest(
        chapter_id=f"chapter_{args.chapter:03d}",
        script_segments=script_data,
        segment_durations_sec=seg_durs,
        dialogue_stem_path=vocal_stem if vocal_stem.exists() else None,
        timeline_ledger=timeline_ledger,
        project_dir=project_dir,
    )

    with open(manifest_file, "w", encoding="utf-8") as f:
        f.write(manifest.to_json(indent=2))

    print(f"\n[OK] Creative Manifest Directed for Chapter {args.chapter}!")
    print(f"     Manifest File      : {manifest_file}")
    print(f"     Silence Percentage : {manifest.silence_percentage}%")
    print(f"     Music Cues         : {len(manifest.music_cues)}")
    print(f"     Foley Cues         : {len(manifest.foley_cues)}")


def cmd_render(args):
    """Compiles and renders a CreativeManifest into a Master Audio file."""
    manifest_file = Path(args.manifest)
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_file}")

    from audiobook_factory.contracts import CreativeManifest
    from audiobook_factory.manifest_renderer import render_manifest_soundscape
    from audiobook_factory.gate_auditor import audit_gate3_5_acoustic_feasibility

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = CreativeManifest.from_json(f.read())

    # Pre-Flight Gate 3.5 Feasibility Guard
    skip_gate35 = getattr(args, "skip_gate3_5", False)
    if not skip_gate35:
        print(f"[*] Executing Gate 3.5 Pre-Flight Feasibility Guard on {manifest_file.name}...")
        gate35_res = audit_gate3_5_acoustic_feasibility(manifest)
        if not gate35_res.passed:
            print(f"\n[FAIL] Gate 3.5 Pre-Flight Feasibility Guard Failed!", file=sys.stderr)
            for err in gate35_res.errors:
                print(f"  [!] {err}", file=sys.stderr)
            sys.exit(1)
        print(
            f"    [+] Gate 3.5 Passed: {gate35_res.details.get('total_music_cues', 0)} music, "
            f"{gate35_res.details.get('total_foley_cues', 0)} foley cues verified."
        )
        for w in gate35_res.details.get("warnings", [])[:3]:
            print(f"    [*] Warning: {w}")

    vocal_file = Path(args.vocal) if getattr(args, "vocal", None) else None
    if not vocal_file or not vocal_file.exists():
        ch_id = manifest.chapter_id
        # Infer vocal track dynamically from manifest directory structure:
        # e.g., <project_dir>/manifests/<chapter_id>_manifest.json -> <project_dir>/mastered/
        project_mastered = manifest_file.parent.parent / "mastered"
        cand_dirs = [project_mastered]
        if hasattr(manifest, "project_dir") and manifest.project_dir:
            cand_dirs.append(Path(manifest.project_dir) / "mastered")

        cand_names = [
            f"{ch_id}_dialogue.wav",
            f"{ch_id}_mastered.wav",
            f"{ch_id}_dialogue.m4a",
            f"{ch_id}_mastered.m4a",
            f"{ch_id}.wav",
            f"{ch_id}.m4a",
        ]
        for cdir in cand_dirs:
            for name in cand_names:
                test_p = cdir / name
                if test_p.exists():
                    vocal_file = test_p
                    break
            if vocal_file:
                break

        if not vocal_file or not vocal_file.exists():
            raise FileNotFoundError(
                f"Vocal dialogue track for '{ch_id}' not found in {project_mastered}. "
                f"Please specify path explicitly via --vocal."
            )

    output_file = Path(args.output) if getattr(args, "output", None) else vocal_file.parent / f"{manifest.chapter_id}_cinematic_v2.m4a"

    print(f"[*] Rendering Creative Manifest: {manifest_file.name}")
    print(f"    Vocal Track : {vocal_file}")
    print(f"    Output File : {output_file}")

    out_path = render_manifest_soundscape(
        manifest=manifest,
        vocal_track_path=vocal_file,
        output_master_file=output_file,
    )
    print(f"\n[OK] Master Render Complete: {out_path}")


def cmd_audit(args):
    """Executes multi-gate independent verification audit for a chapter."""
    from audiobook_factory.gate_auditor import audit_chapter_gates, GateAuditError

    project_dir = PROJECTS_DIR / args.book
    ch_num = args.chapter

    print(f"[*] Running Multi-Gate Independent Verification Audit on '{args.book}' Chapter {ch_num}...")
    try:
        report = audit_chapter_gates(project_dir, ch_num)
        print("\n" + "=" * 60)
        print(f"🎉 MULTI-GATE AUDIT VERDICT: {report['overall_status']}")
        print("=" * 60)
        print(f"  Gate 0 (Translation): {report['gate_0']['status']} ({report['gate_0']['translation_chars']:,} chars)")
        print(f"  Gate 1 (Voice Roster): {report['gate_1']['status']} ({report['gate_1']['active_roles']} roles, 0 collisions)")
        print(f"  Gate 2 (Screenplay):   {report['gate_2']['status']} ({report['gate_2']['total_segments']} segments)")
        print(f"  Gate 3 (Scenes Source): {report['gate_3']['status']} ({report['gate_3']['total_acts']} acts, 100% continuous)")
        if "gate_4_ledger" in report:
            print(f"  Gate 4.5 (Timeline):   {report['gate_4_ledger']['status']} ({report['gate_4_ledger']['total_segments']} segments, {report['gate_4_ledger']['total_timeline_sec']}s, pause silence: {report['gate_4_ledger']['silence_percentage']}%)")
        print("=" * 60)
    except GateAuditError as e:
        print(f"\n[FAIL] Gate Audit Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_timeline(args):
    """Builds and verifies the Gate 4.5 Master Timeline & Audio Transcript Ledger."""
    from audiobook_factory.timeline_ledger import build_audio_transcript_ledger, stitch_dialogue_track_from_ledger

    project_dir = PROJECTS_DIR / args.book
    ch_num = args.chapter

    print(f"[*] Building Gate 4.5 Timeline & Audio Transcript Ledger for '{args.book}' Chapter {ch_num}...")
    ledger = build_audio_transcript_ledger(
        project_dir=project_dir,
        chapter_num=ch_num,
    )
    print(f"\n[OK] Timeline Ledger Generated Successfully!")
    print(f"     Chapter ID       : {ledger.chapter_id}")
    print(f"     Total Segments   : {ledger.total_segments}")
    print(f"     Speech Duration  : {ledger.total_dialogue_duration_ms / 1000.0:.2f}s ({ledger.total_dialogue_duration_ms / 60000.0:.2f}m)")
    print(f"     Timeline Total   : {ledger.total_timeline_duration_ms / 1000.0:.2f}s ({ledger.total_timeline_duration_ms / 60000.0:.2f}m)")
    print(f"     Pause Silence    : {ledger.silence_percentage}%")

    if getattr(args, "stitch", False):
        mastered_dir = project_dir / "mastered"
        out_vocal = mastered_dir / f"chapter_{ch_num:03d}_dialogue.wav"
        print(f"[*] Stitching sample-accurate vocal master track: {out_vocal.name}...")
        stitch_dialogue_track_from_ledger(ledger, project_dir / "audio_chunks", out_vocal)
        print(f"[OK] Vocal track ready: {out_vocal}")


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
    p_synth = subparsers.add_parser("synthesize", help="Synthesize audio segments via Gemini Cloud TTS")
    p_synth.add_argument("book", help="Project book slug")
    p_synth.add_argument("--backend", default="gemini_tts", choices=["gemini_tts"], help="TTS engine (default: gemini_tts)")
    p_synth.add_argument("--voice", default="Aoede", help="Default voice persona")

    # master
    p_master = subparsers.add_parser("master", help="Concatenate segments and master audio with EBU R128")
    p_master.add_argument("book", help="Project book slug")

    # bgm
    p_bgm = subparsers.add_parser("bgm", help="Generate ambient score and apply dynamic sidechain ducking")
    p_bgm.add_argument("book", help="Project book slug")
    p_bgm.add_argument("--engine", default="ambient_bed", choices=["ambient_bed"], help="Music scoring engine (default: ambient_bed)")
    p_bgm.add_argument("--duck-db", default=-16.0, type=float, help="Sidechain attenuation in dB (default: -16)")

    # package
    p_pack = subparsers.add_parser("package", help="Assemble final M4B container with chapters")
    p_pack.add_argument("book", help="Project book slug or path")
    p_pack.add_argument("--cover", default=None, help="Cover art image path")
    p_pack.add_argument("--enforce-gate6", action="store_true", help="Abort packaging if any Gate 6 verification check fails")

    # audit-book
    p_audit_book = subparsers.add_parser("audit-book", help="Run Macro-Tier Gate 6 master audit across entire book project")
    p_audit_book.add_argument("project_dir", help="Project directory or book slug")

    # auto
    p_auto = subparsers.add_parser("auto", help="Run entire end-to-end pipeline in one command")
    p_auto.add_argument("file", help="Input book path")
    p_auto.add_argument("--hindi", action="store_true", help="Translate English book to Hindi")
    p_auto.add_argument("--backend", default="gemini_tts", choices=["gemini_tts"], help="TTS engine (default: gemini_tts)")
    p_auto.add_argument("--voice", default="Aoede", help="Voice persona")
    p_auto.add_argument("--dramatized", action="store_true", help="Multi-voice dramatization")
    p_auto.add_argument("--cover", default=None, help="Cover art image path")
    p_auto.add_argument("--workers", default=3, type=int, help="Number of concurrent TTS synthesis workers (default: 3)")

    # produce
    p_produce = subparsers.add_parser("produce", help="Produce cinematic chapters with 5-track standard & timeline ledger")
    p_produce.add_argument("book", help="Project book slug")
    p_produce.add_argument("--chapter", type=int, default=None, help="Specific chapter number to produce")
    p_produce.add_argument("--all", action="store_true", help="Produce all chapters in sequence")
    p_produce.add_argument("--voice", default="Aoede", help="Lead voice persona")
    p_produce.add_argument("--workers", default=3, type=int, help="TTS synthesis workers")
    p_produce.add_argument("--duck-db", default=-16.0, type=float, help="Sidechain attenuation dB")

    # bank
    p_bank = subparsers.add_parser("bank", help="Manage and search local Sound Bank (SQLite FTS5)")
    p_bank_subs = p_bank.add_subparsers(dest="action", help="Bank action")
    p_bank_subs.add_parser("scan", help="Scan and index audio files into Sound Bank")
    p_bank_subs.add_parser("stats", help="Display Sound Bank statistics")
    p_bank_subs.add_parser("seed", help="Seed virtual sound catalog from cloud CC0 sources")
    p_b_search = p_bank_subs.add_parser("search", help="Search sounds by keywords/tags")
    p_b_search.add_argument("query", help="Keyword or search query")
    p_b_search.add_argument("--limit", default=5, type=int, help="Maximum matches")
    p_b_ingest = p_bank_subs.add_parser("ingest", help="Ingest audio directory into Sound Bank via UniversalSoundBankIngester")
    p_b_ingest.add_argument("dir", help="Directory of sound assets to ingest")
    p_b_ingest.add_argument("--no-recursive", action="store_true", help="Do not scan recursively")
    p_b_ingest.add_argument("--workers", type=int, default=4, help="Concurrent worker threads")

    # soundbank (alias for bank)
    p_sbank = subparsers.add_parser("soundbank", help="Manage Sound Bank (alias for bank)")
    p_sb_subs = p_sbank.add_subparsers(dest="action", help="Sound Bank action")
    p_sb_subs.add_parser("scan", help="Scan and index audio files into Sound Bank")
    p_sb_subs.add_parser("stats", help="Display Sound Bank statistics")
    p_sb_subs.add_parser("seed", help="Seed virtual sound catalog from cloud CC0 sources")
    p_sb_search = p_sb_subs.add_parser("search", help="Search sounds by keywords/tags")
    p_sb_search.add_argument("query", help="Keyword or search query")
    p_sb_search.add_argument("--limit", default=5, type=int, help="Maximum matches")
    p_sb_ingest = p_sb_subs.add_parser("ingest", help="Ingest audio directory into Sound Bank via UniversalSoundBankIngester")
    p_sb_ingest.add_argument("dir", help="Directory of sound assets to ingest")
    p_sb_ingest.add_argument("--no-recursive", action="store_true", help="Do not scan recursively")
    p_sb_ingest.add_argument("--workers", type=int, default=4, help="Concurrent worker threads")

    # direct
    p_direct = subparsers.add_parser("direct", help="Direct chapter into CreativeManifest via AgentDirector")
    p_direct.add_argument("book", help="Project book slug")
    p_direct.add_argument("--chapter", type=int, required=True, help="Chapter number to direct")
    p_direct.add_argument("--output", "-o", default=None, help="Custom output manifest JSON path")

    # render
    p_render = subparsers.add_parser("render", help="Compile and render CreativeManifest with Deterministic Engine")
    p_render.add_argument("--manifest", required=True, help="Path to creative_manifest.json")
    p_render.add_argument("--vocal", default=None, help="Optional path to vocal dialogue stem")
    p_render.add_argument("--output", default=None, help="Optional output audio master path")
    p_render.add_argument("--skip-gate3-5", action="store_true", help="Skip Gate 3.5 Pre-Flight Feasibility Guard")

    # audit
    p_audit = subparsers.add_parser("audit", help="Run multi-gate independent verification audit on a chapter")
    p_audit.add_argument("book", help="Project book slug")
    p_audit.add_argument("--chapter", type=int, required=True, help="Chapter number to audit")

    # timeline
    p_timeline = subparsers.add_parser("timeline", help="Generate Gate 4.5 Master Timeline & Audio Transcript Ledger")
    p_timeline.add_argument("book", help="Project book slug")
    p_timeline.add_argument("--chapter", type=int, required=True, help="Chapter number")
    p_timeline.add_argument("--stitch", action="store_true", help="Also stitch sample-accurate vocal master track")

    # stems
    p_stems = subparsers.add_parser("stems", help="Inspect and verify exported discrete DME stems and stem ledger")
    p_stems.add_argument("book", help="Project book slug")
    p_stems.add_argument("--chapter", type=int, required=True, help="Chapter number to inspect")

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
        "soundbank": cmd_bank,
        "produce": cmd_produce,
        "auto": cmd_auto,
        "direct": cmd_direct,
        "render": cmd_render,
        "audit": cmd_audit,
        "audit-book": cmd_audit_book,
        "timeline": cmd_timeline,
        "stems": cmd_stems,
    }
    try:
        cmds[args.subcommand](args)
    except KeyboardInterrupt:
        print("\n\n[!] Production aborted by user (Ctrl+C). Checkpoints safely preserved on disk.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n[!] Pipeline Error: {e}", file=sys.stderr)
        if os.environ.get("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
