#!/usr/bin/env python3
"""
Audiobook Factory - Soundscape Engine: Multitrack & Hierarchical Audio Mixer.
Handles rendering chapter soundscape scenes, 3-level hierarchical scores, and
broadcast-grade 5-track cinematic timeline assembly.
"""

from __future__ import annotations
import os
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

from audiobook_factory.logger import logger
from audiobook_factory.soundscape_engine.probe import (
    get_ffmpeg,
    get_audio_duration,
    resolve_timeline_start_offsets,
)
from audiobook_factory.soundscape_engine.sound_resolver import (
    get_sound_bank,
    resolve_ambient_score,
    resolve_environment_ambience,
)


def render_chapter_soundscape(
    soundscape_plan: Dict[str, Any],
    total_duration: float,
    output_audio_file: Path,
    segment_durations: Optional[Dict[int, float]] = None,
) -> Path:
    """
    Renders a complete, multi-scene background ambient bed with optional SFX cues
    based on the Soundscape JSON Plan.
    """
    output_audio_file = Path(output_audio_file).resolve()
    output_audio_file.parent.mkdir(parents=True, exist_ok=True)
    scenes = soundscape_plan.get("scenes", [])
    primary_mood = soundscape_plan.get("primary_mood", "default")

    # Simple path: single scene or fallback
    if len(scenes) <= 1 or not segment_durations:
        sc = scenes[0] if scenes else {}
        stem = sc.get("stem", primary_mood) if scenes else primary_mood
        bank = get_sound_bank()
        if bank:
            explicit_sec = sc.get("emotional_arc", {}).get("cue_section") if isinstance(sc.get("emotional_arc"), dict) else sc.get("cue_section")
            target_sec = str(explicit_sec).upper().strip() if explicit_sec and str(explicit_sec).upper().strip() in ("INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE") else "INTRO_BED"
            sec_info = bank.resolve_track_section(stem, section_type=target_sec)
            if sec_info and sec_info.get("track_path") and Path(sec_info["track_path"]).exists():
                try:
                    bank.slice_track_section(sec_info["track_path"], sec_info["start_sec"], total_duration, output_audio_file)
                    sc["cue_slice"] = sec_info
                    return output_audio_file
                except Exception:
                    pass
        return resolve_ambient_score(stem, total_duration, output_audio_file)

    # Multi-scene crossfading path
    ffmpeg = get_ffmpeg()
    temp_scene_files = []
    tmp_dir = output_audio_file.parent / f"tmp_scenes_{os.getpid()}_{uuid.uuid4().hex[:6]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        total_known_dur = sum(segment_durations.values()) if segment_durations else total_duration
        scale_factor = (total_duration / total_known_dur) if total_known_dur > 0 else 1.0

        for sc in scenes:
            sc_id = sc.get("scene_id", 1)
            start_seg = sc.get("segment_start", 1)
            end_seg = sc.get("segment_end", start_seg)
            stem = (
                sc.get("emotional_arc", {}).get("music_track")
                or sc.get("stem")
                or sc.get("emotional_arc", {}).get("music_mood")
                or sc.get("mood")
                or primary_mood
            ) if isinstance(sc.get("emotional_arc"), dict) else (sc.get("stem") or sc.get("mood") or primary_mood)

            # Calculate scene duration
            sc_dur = sum(segment_durations.get(s_idx, 4.0) for s_idx in range(start_seg, end_seg + 1)) * scale_factor
            sc_dur = max(sc_dur, 4.0)

            # Acoustic Energy Zone Mapping (Deterministic directive from manifest/script or pure INTRO_BED default)
            explicit_sec = sc.get("emotional_arc", {}).get("cue_section") if isinstance(sc.get("emotional_arc"), dict) else sc.get("cue_section")
            if explicit_sec and str(explicit_sec).upper().strip() in ("INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE"):
                target_sec = str(explicit_sec).upper().strip()
                if target_sec == "CLIMAX_DROP":
                    min_eng, max_eng = 7, 10
                elif target_sec == "RISING_TENSION":
                    min_eng, max_eng = 4, 7
                elif target_sec == "AFTERMATH_FADE":
                    min_eng, max_eng = 1, 4
                else:
                    min_eng, max_eng = 1, 5
            else:
                target_sec = "INTRO_BED"
                min_eng, max_eng = 1, 5

            sc_wav = tmp_dir / f"sc_{sc_id}_{stem}.wav"
            bank = get_sound_bank()
            sliced = False
            if bank:
                sec_info = bank.resolve_track_section(stem, section_type=target_sec, min_energy=min_eng, max_energy=max_eng)
                if sec_info and sec_info.get("track_path") and Path(sec_info["track_path"]).exists():
                    try:
                        bank.slice_track_section(
                            track_path=sec_info["track_path"],
                            start_sec=sec_info["start_sec"],
                            target_duration=sc_dur,
                            output_file=sc_wav,
                        )
                        sc["cue_slice"] = sec_info
                        sliced = True
                    except Exception as e:
                        logger.warning(f"  [!] Slicing section for scene {sc_id} fallback: {e}")

            if not sliced:
                resolve_ambient_score(stem, sc_dur, sc_wav)

            temp_scene_files.append((sc_wav, sc_dur))

        # Concatenate scene stems with smooth crossfade
        if len(temp_scene_files) == 1:
            shutil.copyfile(temp_scene_files[0][0], output_audio_file)
        else:
            # Build FFmpeg acrossfade filter complex
            filter_parts = []
            inputs = []
            for idx, (sw, _) in enumerate(temp_scene_files):
                inputs.extend(["-i", str(sw)])

            curr_tag = "0"
            for i in range(1, len(temp_scene_files)):
                next_tag = f"sc_{i}" if i < len(temp_scene_files) - 1 else "out"
                filter_parts.append(f"[{curr_tag}][{i}]acrossfade=d=2.0:c1=tri:c2=tri[{next_tag}]")
                curr_tag = next_tag

            filter_str = ";".join(filter_parts)
            cmd = [
                ffmpeg, "-y",
                *inputs,
                "-filter_complex", filter_str,
                "-map", "[out]",
                "-t", f"{total_duration:.2f}",
                "-c:a", "pcm_s16le",
                str(output_audio_file)
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        return output_audio_file
    except Exception as e:
        print(f"  [!] Multi-scene crossfade failed ({e}), falling back to single primary stem.")
        return resolve_ambient_score(primary_mood, total_duration, output_audio_file)
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def normalize_to_3level_soundscape(plan: Dict[str, Any], chapter_num: int = 1) -> Dict[str, Any]:
    """
    Ensures any soundscape plan conforms strictly to the 3-Level BGM schema
    with zero broken references.
    """
    out = dict(plan)
    scenes = out.get("scenes", [])
    if not scenes and "level3_scenes" in out:
        scenes = out.get("level3_scenes", [])
    out["scenes"] = scenes
    out["level3_scenes"] = scenes

    # Level 1: Leitmotifs
    if "level1_leitmotifs" not in out:
        out["level1_leitmotifs"] = []

    # Level 2: Chapter Bed
    if "level2_chapter_bed" not in out:
        env_counts: Dict[str, int] = {}
        for sc in scenes:
            env = sc.get("location", {}).get("environment_type", "open_road")
            env_counts[env] = env_counts.get(env, 0) + 1
        dominant_env = max(env_counts, key=env_counts.get) if env_counts else "open_road"
        out["level2_chapter_bed"] = {
            "setting": dominant_env,
            "stem": dominant_env,
            "base_volume": 0.16,
            "description": f"Continuous setting undercurrent for {dominant_env}",
        }

    # Level 3: Ensure each scene has dynamic_stems, stingers, and valid cue_section
    valid_cue_sections = {"INTRO_BED", "RISING_TENSION", "CLIMAX_DROP", "AFTERMATH_FADE", "AUTO"}
    valid_moods = {"tense", "mysterious", "peaceful", "emotional", "epic"}

    for sc in scenes:
        emo = sc.setdefault("emotional_arc", {})
        if "cue_section" in emo:
            c_sec = str(emo["cue_section"]).upper().strip()
            emo["cue_section"] = c_sec if c_sec in valid_cue_sections else "auto"
        mood = str(emo.get("music_mood", "tense")).lower().strip()
        emo["music_mood"] = mood if mood in valid_moods else "tense"

        if "dynamic_stems" not in emo:
            intensity = int(emo.get("intensity", 5))
            if intensity >= 8:
                emo["dynamic_stems"] = ["combat_drums"]
            elif intensity >= 6:
                emo["dynamic_stems"] = ["tension_pulse"]
            else:
                emo["dynamic_stems"] = []
        if "stingers" not in emo:
            emo["stingers"] = []

    out.setdefault("ducking_attenuation_db", -16.0)
    out.setdefault("primary_mood", "tense")
    out.setdefault("chapter_id", chapter_num)
    out["total_scenes"] = len(scenes)
    return out


def render_hierarchical_soundscape(
    soundscape_plan: Dict[str, Any],
    total_duration: float,
    output_audio_file: Path,
    segment_durations: Optional[Dict[int, float]] = None,
    pause_ms: int = 450,
) -> Path:
    """
    Renders a composite 3-Level Hierarchical Score (Hollywood standard):
    - Level 1: Global Leitmotifs (recurring character/destiny motifs time-aligned via adelay)
    - Level 2: Chapter World Bed (continuous setting undercurrent across full duration)
    - Level 3: Dynamic Multi-Act Scenes (crossfaded via acrossfade) + Action Stingers
    All 3 musical tiers are combined into output_audio_file ready for sidechain ducking.
    """
    plan = normalize_to_3level_soundscape(soundscape_plan)
    ffmpeg = get_ffmpeg()
    output_audio_file = Path(output_audio_file).resolve()
    output_audio_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_audio_file.parent / f"tmp_hierarchical_bgm_{os.getpid()}_{uuid.uuid4().hex[:6]}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    bank = get_sound_bank()

    try:
        active_layers = []  # List of (filepath, volume_float)

        # 1. Level 2: Chapter Setting Bed (Continuous Undercurrent)
        bed_info = plan.get("level2_chapter_bed", {})
        bed_name = bed_info.get("stem") or bed_info.get("setting") or "dark_forest"
        bed_vol = float(bed_info.get("base_volume", 0.16))
        bed_raw = tmp_dir / "l2_chapter_bed.wav"

        bed_sliced = False
        if bank:
            bed_sec = bank.resolve_track_section(bed_name, section_type="INTRO_BED", min_energy=1, max_energy=5)
            if bed_sec and bed_sec.get("track_path") and Path(bed_sec["track_path"]).exists():
                try:
                    bank.slice_track_section(
                        track_path=bed_sec["track_path"],
                        start_sec=bed_sec["start_sec"],
                        target_duration=total_duration,
                        output_file=bed_raw,
                    )
                    bed_info["cue_slice"] = bed_sec
                    bed_sliced = True
                except Exception:
                    bed_sliced = False

        if not bed_sliced:
            bed_resolved = bank.resolve_chapter_bed(bed_name) if bank else None
            if bed_resolved and bed_resolved.exists():
                resolve_ambient_score(bed_resolved.stem, total_duration, bed_raw)
            else:
                resolve_ambient_score(plan.get("primary_mood", "tense"), total_duration, bed_raw)

        if bed_raw.exists() and bed_raw.stat().st_size > 1000:
            active_layers.append((bed_raw, bed_vol))

        # 2. Level 3: Dynamic Multi-Act Scenes (Crossfaded Stems)
        scenes_raw = tmp_dir / "l3_dynamic_scenes.wav"
        render_chapter_soundscape(plan, total_duration, scenes_raw, segment_durations=segment_durations)
        if scenes_raw.exists() and scenes_raw.stat().st_size > 1000:
            active_layers.append((scenes_raw, 0.26))

        # 3. Level 1: Leitmotifs & Level 3 Accent Stingers (Time-Aligned Hits)
        time_aligned_events = []
        if segment_durations:
            seg_starts = resolve_timeline_start_offsets(
                segment_durations=segment_durations,
                timeline_ledger=plan.get("timeline_ledger") if isinstance(plan, dict) else getattr(plan, "timeline_ledger", None),
                default_pause_ms=pause_ms,
            )

            # Level 1 Leitmotifs
            for lm in plan.get("level1_leitmotifs", []):
                theme_name = lm.get("theme", "")
                trigger_seg = int(lm.get("trigger_segment", 1))
                t_sec = seg_starts.get(trigger_seg, 0.0)
                vol = float(lm.get("volume", 0.22))
                theme_file = None
                if bank:
                    theme_sec = bank.resolve_track_section(theme_name, section_type="INTRO_BED") or bank.resolve_track_section(theme_name, section_type="CLIMAX_DROP")
                    if theme_sec and theme_sec.get("track_path") and Path(theme_sec["track_path"]).exists():
                        theme_file = Path(theme_sec["track_path"])
                        lm["cue_slice"] = theme_sec
                    else:
                        theme_file = bank.resolve_leitmotif(theme_name)
                if theme_file and theme_file.exists() and t_sec < total_duration:
                    t_ms = max(0, int(t_sec * 1000))
                    time_aligned_events.append((theme_file, t_ms, vol, "leitmotif"))

            # Level 3 Stingers
            for sc in plan.get("scenes", []):
                emo = sc.get("emotional_arc", {})
                for st in emo.get("stingers", []):
                    st_cue = st.get("cue", "")
                    st_seg = int(st.get("segment", 1))
                    t_sec = seg_starts.get(st_seg, 0.0)
                    vol = float(st.get("volume", 0.32))
                    st_file = bank.resolve_stinger(st_cue) if bank else None
                    if st_file and st_file.exists() and t_sec < total_duration:
                        t_ms = max(0, int(t_sec * 1000))
                        time_aligned_events.append((st_file, t_ms, vol, "stinger"))

        # If time-aligned hits exist, render them via adelay bus
        if time_aligned_events:
            stinger_bus = tmp_dir / "l1_l3_stingers_bus.wav"
            events_slice = time_aligned_events[:25]
            s_inputs = []
            s_filters = []
            for idx, (s_path, t_ms, vol, _) in enumerate(events_slice):
                s_inputs.extend(["-i", str(s_path)])
                s_filters.append(f"[{idx}:a]adelay={t_ms}|{t_ms},volume={vol:.2f}[s_{idx}]")

            s_mix_ins = "".join(f"[s_{i}]" for i in range(len(events_slice)))
            s_filter_str = ";".join(s_filters) + f";{s_mix_ins}amix=inputs={len(events_slice)}:normalize=0[sout]"

            stinger_cmd = [
                ffmpeg, "-y",
                *s_inputs,
                "-filter_complex", s_filter_str,
                "-map", "[sout]",
                "-t", f"{total_duration:.2f}",
                "-c:a", "pcm_s16le",
                str(stinger_bus),
            ]
            try:
                subprocess.run(stinger_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if stinger_bus.exists() and stinger_bus.stat().st_size > 1000:
                    active_layers.append((stinger_bus, 1.0))
            except Exception as e:
                logger.warning(f"  [!] Stinger bus render notice: {e}")

        # 4. Final Mix of Active Layers into output_audio_file
        if not active_layers:
            return resolve_ambient_score(plan.get("primary_mood", "tense"), total_duration, output_audio_file)

        if len(active_layers) == 1:
            shutil.copyfile(active_layers[0][0], output_audio_file)
            return output_audio_file

        mix_inputs = []
        mix_filters = []
        for idx, (l_file, l_vol) in enumerate(active_layers):
            mix_inputs.extend(["-i", str(l_file)])
            mix_filters.append(f"[{idx}:a]volume={l_vol:.2f}[m_{idx}]")

        m_ins = "".join(f"[m_{i}]" for i in range(len(active_layers)))
        mix_filter_str = ";".join(mix_filters) + f";{m_ins}amix=inputs={len(active_layers)}:normalize=0[mout]"

        final_cmd = [
            ffmpeg, "-y",
            *mix_inputs,
            "-filter_complex", mix_filter_str,
            "-map", "[mout]",
            "-t", f"{total_duration:.2f}",
            "-c:a", "pcm_s16le",
            str(output_audio_file),
        ]
        subprocess.run(final_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return output_audio_file
    except Exception as e:
        logger.warning(f"  [!] Hierarchical BGM composition notice ({e}), falling back to 2-tier score.")
        return render_chapter_soundscape(soundscape_plan, total_duration, output_audio_file, segment_durations=segment_durations)
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def render_multitrack_chapter_audio(
    vocal_file: Path,
    output_master_file: Path,
    cue_sheet: Optional[Dict[str, Any]] = None,
    soundscape_plan: Optional[Dict[str, Any]] = None,
    segment_durations: Optional[Dict[int, float]] = None,
    pause_ms: int = 400,
) -> Path:
    """
    Next-Gen 5-Track Audio Drama Timeline Compositor (GraphicAudio / BBC Radio standard).
    Renders:
    - Track 1 (Voice Bus): Spatially enriched speech with matching room impulse reverberation.
    - Track 2 (Foley Bus): Physical object interactions and footsteps time-aligned via adelay.
    - Track 3 (Ambience Bus): Continuous environmental room tone (tavern, crypt, rain).
    - Track 4 (Music Bus): Cinematic score with 1.2kHz-3.2kHz spectral carving & sidechain ducking.
    - Master Bus: EBU R128 (-19 LUFS broadcast master) at 48kHz SOXR sinc.
    """
    ffmpeg = get_ffmpeg()
    vocal_file = Path(vocal_file).resolve()
    output_master_file = Path(output_master_file).resolve()
    output_master_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output_master_file.parent / "tmp_multitrack"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    vocal_dur = get_audio_duration(vocal_file)
    bank = get_sound_bank()

    # 1. Timeline Segmentation (Ledger-Authoritative Sync)
    seg_starts = {}
    if segment_durations:
        active_ledger = None
        ledger_candidates = [
            vocal_file.parent.parent / "scripts" / f"{vocal_file.stem.replace('_dialogue', '')}_timeline_ledger.json",
            vocal_file.parent / f"{vocal_file.stem.replace('_dialogue', '')}_timeline_ledger.json",
        ]
        for lc in ledger_candidates:
            if lc.exists():
                try:
                    with open(lc, "r", encoding="utf-8") as lf:
                        from audiobook_factory.contracts import TimelineLedger
                        active_ledger = TimelineLedger.model_validate_json(lf.read())
                        break
                except Exception:
                    pass

        seg_starts = resolve_timeline_start_offsets(
            segment_durations=segment_durations,
            timeline_ledger=active_ledger,
            default_pause_ms=pause_ms,
        )

    # 2. Resolve Foley Events
    foley_cues = cue_sheet.get("foley_cues", []) if cue_sheet else []
    valid_foley_events = []
    if bank and foley_cues:
        for c in foley_cues:
            s_idx = c.get("segment_index", 1)
            t_sec = seg_starts.get(s_idx, 0.0) + (c.get("offset_ms", 0) / 1000.0)
            t_ms = max(0, int(t_sec * 1000))
            tag = c.get("foley_tag", "") or c.get("tag", "")
            snd = bank.resolve_sound(tag)
            if snd and snd.exists() and t_sec < vocal_dur:
                # Moderate Foley cue level so it complements dialogue
                cue_vol = min(0.40, float(c.get("volume", 0.30)))
                valid_foley_events.append((snd, t_ms, cue_vol))

    # 3. Resolve Ambience & Music Stems (3-Level Hierarchical Score + Dynamic Acrossfade)
    bgm_raw = tmp_dir / "bgm_raw.wav"
    scenes = soundscape_plan.get("scenes", []) if soundscape_plan else []
    if soundscape_plan and ("level1_leitmotifs" in soundscape_plan or "level2_chapter_bed" in soundscape_plan or len(scenes) > 1):
        print("[*] Rendering 3-Level Hierarchical Score (Leitmotif + Chapter Bed + Dynamic Scenes)...")
        render_hierarchical_soundscape(
            soundscape_plan,
            vocal_dur,
            bgm_raw,
            segment_durations=segment_durations,
            pause_ms=pause_ms,
        )
    else:
        primary_mood = soundscape_plan.get("primary_mood", "tense") if soundscape_plan else "tense"
        resolve_ambient_score(primary_mood, vocal_dur, bgm_raw)

    amb_raw = tmp_dir / "amb_raw.wav"
    primary_env = cue_sheet.get("primary_environment", "dense_forest_night") if cue_sheet else "dense_forest_night"
    resolve_environment_ambience(primary_env, vocal_dur, amb_raw)

    # 4. Render Foley Bus (Chunked to prevent Win32 8191 CLI overflow)
    foley_bus_file = tmp_dir / "foley_bus.wav"
    has_foley = False
    if valid_foley_events:
        print(f"[*] Assembling Foley Bus with {len(valid_foley_events)} physical object cues (Chunked)...")
        chunk_size = 15
        sub_bus_files = []
        for c_idx in range(0, len(valid_foley_events), chunk_size):
            foley_slice = valid_foley_events[c_idx : c_idx + chunk_size]
            sub_bus_file = tmp_dir / f"foley_sub_{c_idx//chunk_size:03d}.wav"
            f_inputs = []
            f_filters = []
            for idx, (f_path, t_ms, vol) in enumerate(foley_slice):
                f_inputs.extend(["-i", str(f_path)])
                f_filters.append(f"[{idx}:a]adelay={t_ms}|{t_ms},volume={vol:.2f}[f_{idx}]")

            f_mix_ins = "".join(f"[f_{i}]" for i in range(len(foley_slice)))
            f_filter_str = ";".join(f_filters) + f";{f_mix_ins}amix=inputs={len(foley_slice)}:normalize=0[fout]"

            foley_cmd = [
                ffmpeg, "-y",
                *f_inputs,
                "-filter_complex", f_filter_str,
                "-map", "[fout]",
                "-t", f"{vocal_dur + 1.0:.2f}",
                "-ar", "48000",
                "-c:a", "pcm_s16le",
                str(sub_bus_file),
            ]
            try:
                subprocess.run(foley_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if sub_bus_file.exists() and sub_bus_file.stat().st_size > 1000:
                    sub_bus_files.append(sub_bus_file)
            except Exception as e:
                print(f"  [!] Sub-Foley chunk assembly notice ({c_idx}): {e}")

        if len(sub_bus_files) == 1:
            shutil.copy2(sub_bus_files[0], foley_bus_file)
            has_foley = foley_bus_file.exists() and foley_bus_file.stat().st_size > 5000
        elif len(sub_bus_files) > 1:
            merge_inputs = []
            for sf in sub_bus_files:
                merge_inputs.extend(["-i", str(sf)])
            merge_filter = f"amix=inputs={len(sub_bus_files)}:normalize=0[fout]"
            merge_cmd = [
                ffmpeg, "-y",
                *merge_inputs,
                "-filter_complex", merge_filter,
                "-map", "[fout]",
                "-t", f"{vocal_dur + 1.0:.2f}",
                "-ar", "48000",
                "-c:a", "pcm_s16le",
                str(foley_bus_file),
            ]
            try:
                subprocess.run(merge_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                has_foley = foley_bus_file.exists() and foley_bus_file.stat().st_size > 5000
            except Exception as e:
                print(f"  [!] Foley sub-bus merge notice: {e}")
                has_foley = False
        else:
            has_foley = False

    # 5. Master Multi-Bus Assembly
    print(f"[*] Mixing 5-Track Cinematic Audio Drama ({vocal_file.name})...")
    master_inputs = [
        "-i", str(vocal_file),   # Input 0: Vocal track
        "-i", str(bgm_raw),      # Input 1: Music score
        "-i", str(amb_raw),      # Input 2: Ambience bed
    ]
    if has_foley:
        master_inputs.extend(["-i", str(foley_bus_file)])  # Input 3: Foley bus

    from audiobook_factory.ffmpeg_agent import build_ffmpeg_filter_graph_via_agent
    master_filter_str = build_ffmpeg_filter_graph_via_agent(soundscape_plan, cue_sheet, vocal_dur, has_foley)

    if not master_filter_str:
        # Fallback if Agent fails
        filter_parts = [
            "[0:a]asplit=2[voc_dry][voc_sc]",
            f"[1:a]atrim=0:{vocal_dur+1.5:.2f},equalizer=f=2200:t=q:w=1.5:g=-5.5[bgm_carved]",
            "[bgm_carved][voc_sc]sidechaincompress=threshold=0.04:ratio=8.0:attack=120:release=750:knee=2.5[bgm_ducked]",
            f"[2:a]atrim=0:{vocal_dur+1.5:.2f},volume=0.14[amb_bed]",
        ]
        if has_foley:
            filter_parts.append("[3:a]volume=0.30[fol_bus]")
            mix_inputs = "[voc_dry][bgm_ducked][amb_bed][fol_bus]"
            num_mix = 4
        else:
            mix_inputs = "[voc_dry][bgm_ducked][amb_bed]"
            num_mix = 3

        filter_parts.append(f"{mix_inputs}amix=inputs={num_mix}:duration=first:dropout_transition=2:normalize=0[mixed]")
        filter_parts.append("[mixed]aresample=osr=48000,loudnorm=I=-19:TP=-1.5:LRA=11,alimiter=limit=0.89:attack=5:release=50[out]")
        master_filter_str = ";".join(filter_parts)

    ext = output_master_file.suffix.lower()
    codec = "aac" if ext in (".m4a", ".m4b") else "pcm_s16le"
    bitrate_args = ["-b:a", "192k"] if codec == "aac" else []

    cmd = [
        ffmpeg, "-y",
        *master_inputs,
        "-filter_complex", master_filter_str,
        "-map", "[out]",
        "-ac", "2",
        "-ar", "48000",
        "-c:a", codec,
        *bitrate_args,
        str(output_master_file)
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[+] Broadcast Mastered Audio Drama ready -> {output_master_file.name} ({output_master_file.stat().st_size / (1024*1024):.2f} MB)")
        return output_master_file
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Multitrack mastering failed: {err[:300]}")
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
