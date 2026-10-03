from __future__ import annotations
import os
import sys
import re
import json
import time
import subprocess
from pathlib import Path

from audiobook_factory.cli.context import get_projects_dir, get_workspace_dir
from audiobook_factory.soundscape import generate_project_soundscapes, get_audio_duration, get_ffmpeg
from audiobook_factory.packager import package_m4b_audiobook
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.contracts import CreativeManifest, LegacyCreativeManifestAdapter
from audiobook_factory.cinema_audio_engine import render_discrete_stems
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.manifest_renderer import render_manifest_soundscape

def cmd_soundscape(args):
    """Generate Director Soundscape JSON Plans for all chapters."""
    project_dir = get_projects_dir() / args.book
    soundscapes_dir = generate_project_soundscapes(project_dir)
    print(f"\n[OK] Soundscape JSON plans ready at: {soundscapes_dir}")



def cmd_bgm(args):
    """Applies AgentDirector and Cinema Audio Engine to produce discrete DME stems and cinema master."""
    import json
    import subprocess
    project_dir = get_projects_dir() / args.book
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
        if isinstance(script_data, dict):
            script_data = script_data.get("segments", script_data)

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
    project_dir = get_projects_dir() / args.book
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
    project_dir = target if (target.exists() and target.is_dir()) else (get_projects_dir() / args.book)
    cover = Path(args.cover) if args.cover else None
    enforce = getattr(args, "enforce_gate6", False)
    final_m4b = package_m4b_audiobook(project_dir, cover_image=cover, enforce_gate6=enforce)
    print(f"\n[DONE] Finished Audiobook Package: {final_m4b}")



def cmd_direct(args):
    """Directs a chapter into a CreativeManifest using AgentDirector."""
    project_dir = get_projects_dir() / args.book
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



def cmd_timeline(args):
    """Builds and verifies the Gate 4.5 Master Timeline & Audio Transcript Ledger."""
    from audiobook_factory.timeline_ledger import build_audio_transcript_ledger, stitch_dialogue_track_from_ledger

    project_dir = get_projects_dir() / args.book
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


