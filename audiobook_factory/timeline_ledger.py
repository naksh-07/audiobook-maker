#!/usr/bin/env python3
"""
Audiobook Factory - Millisecond-Precision Master Timeline Ledger & Transcript Engine.
Tracks every millisecond of speech, sound effects, ambience, and music
ducking across all 5 tracks of the cinematic audio drama container.
"""

import os
import wave
import uuid
import shutil
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from audiobook_factory.contracts import TimelineSegment, TimelineLedger, ScreenplayScript, ScreenplaySegment
from audiobook_factory.soundscape import get_audio_duration

logger = logging.getLogger("audiobook_factory.timeline_ledger")


def get_wav_duration_ms(wav_path: Path) -> int:
    """Accurately computes duration of a WAV file in milliseconds."""
    try:
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return int(round((frames / float(rate)) * 1000.0))
    except Exception:
        pass
    dur_sec = get_audio_duration(wav_path)
    return int(round(dur_sec * 1000.0))


def build_audio_transcript_ledger(
    project_dir: Path | str,
    chapter_num: int,
    script_file: Optional[Path | str] = None,
    audio_dir: Optional[Path | str] = None,
    output_ledger_file: Optional[Path | str] = None,
    default_pause_ms: int = 400,
) -> TimelineLedger:
    """
    Gate 4.5: Builds the master sample-accurate audio transcript & millisecond timeline ledger.
    Extracts every synthesized speech chunk, measures its sample duration,
    chronologically maps start_ms and end_ms, preserves 100% of the Hindi text without truncation,
    and returns a strictly-typed TimelineLedger contract.
    """
    project_dir = Path(project_dir).resolve()
    ch_str = f"chapter_{chapter_num:03d}"

    # 1. Resolve screenplay script
    if script_file is None:
        cands = [
            project_dir / "scripts" / f"{ch_str}_hi_script.json",
            project_dir / "scripts" / f"{ch_str}_script.json",
        ]
        for c in cands:
            if c.exists():
                script_file = c
                break
        if script_file is None:
            raise FileNotFoundError(f"Screenplay script not found for chapter {chapter_num} in {project_dir / 'scripts'}")
    script_file = Path(script_file).resolve()

    # 2. Load screenplay script
    script = ScreenplayScript.from_file(script_file)
    if not script.segments:
        raise ValueError(f"Screenplay script has 0 segments: {script_file}")

    # 3. Resolve audio chunks directory
    if audio_dir is None:
        audio_dir = project_dir / "audio_chunks"
    audio_dir = Path(audio_dir).resolve()

    timeline_segments: List[TimelineSegment] = []
    curr_t_ms = 0
    total_speech_ms = 0

    for seg in script.segments:
        idx = seg.index
        # Match audio chunk pattern: c{chapter:03d}_s{idx:04d}_*.wav
        pattern = f"c{chapter_num:03d}_s{idx:04d}_*.wav"
        matches = sorted(list(audio_dir.glob(pattern)))
        if not matches:
            raise FileNotFoundError(
                f"Audio chunk missing for chapter {chapter_num}, segment {idx} (pattern: {pattern}) in {audio_dir}"
            )
        audio_chunk = matches[0]
        if audio_chunk.stat().st_size <= 1000:
            raise ValueError(
                f"Audio chunk {audio_chunk.name} is corrupt or too small ({audio_chunk.stat().st_size} bytes)"
            )

        dur_ms = get_wav_duration_ms(audio_chunk)
        start_ms = curr_t_ms
        end_ms = start_ms + dur_ms
        total_speech_ms += dur_ms

        pause_after = seg.pause_after_ms if seg.pause_after_ms is not None else default_pause_ms

        t_seg = TimelineSegment(
            segment_index=idx,
            speaker=seg.speaker,
            text=seg.text,  # Full unabridged text preserved!
            audio_file=audio_chunk.name,
            duration_ms=dur_ms,
            start_ms=start_ms,
            end_ms=end_ms,
            pause_after_ms=pause_after,
            emotion=seg.emotion,
            delivery_style=seg.acting.delivery_style if seg.acting else "neutral",
            spatial_pan=seg.spatial.pan if seg.spatial else 0.0,
            acoustic_env=seg.acoustic_env,
            sfx_cues=list(seg.sfx_cues),
            music_mood=seg.music.mood if seg.music else "neutral",
        )
        timeline_segments.append(t_seg)

        # Advance timeline by segment duration + silence padding
        curr_t_ms = end_ms + pause_after

    # Compute total durations
    total_timeline_ms = curr_t_ms - (timeline_segments[-1].pause_after_ms if timeline_segments else 0)
    total_silence_ms = max(0, total_timeline_ms - total_speech_ms)
    silence_pct = round((total_silence_ms / float(total_timeline_ms) * 100.0), 2) if total_timeline_ms > 0 else 0.0

    ledger = TimelineLedger(
        ledger_version="2.0",
        project_id=project_dir.name,
        chapter_id=ch_str,
        total_segments=len(timeline_segments),
        total_dialogue_duration_ms=total_speech_ms,
        total_timeline_duration_ms=total_timeline_ms,
        total_silence_duration_ms=total_silence_ms,
        silence_percentage=silence_pct,
        segments=timeline_segments,
    )

    # Resolve output file
    if output_ledger_file is None:
        output_ledger_file = project_dir / "scripts" / f"{ch_str}_timeline_ledger.json"
    output_ledger_file = Path(output_ledger_file).resolve()
    output_ledger_file.parent.mkdir(parents=True, exist_ok=True)

    # Atomic write
    tmp_path = output_ledger_file.with_suffix(f".tmp_{os.getpid()}_{uuid.uuid4().hex[:6]}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(ledger.to_json(indent=2))
        os.replace(tmp_path, output_ledger_file)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    logger.info(
        f"[+] Gate 4.5 Timeline Ledger generated: {output_ledger_file.name} "
        f"({ledger.total_segments} segments, {ledger.total_timeline_duration_ms / 1000.0:.1f}s, "
        f"speech: {ledger.total_dialogue_duration_ms / 1000.0:.1f}s, silence: {ledger.silence_percentage}%)"
    )
    return ledger


def stitch_dialogue_track_from_ledger(
    ledger: TimelineLedger,
    audio_dir: Path | str,
    output_wav_path: Path | str,
    sample_rate: int = 24000,
) -> Path:
    """
    Stitches speech chunks into a sample-accurate vocal master track (chapter_xxx_dialogue.wav)
    inserting precise PCM silence intervals defined by pause_after_ms in the timeline ledger.
    Guarantees 100.00% sample synchronization with the timeline ledger!
    """
    audio_dir = Path(audio_dir).resolve()
    output_wav_path = Path(output_wav_path).resolve()
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_out = output_wav_path.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}.wav")

    with wave.open(str(tmp_out), "wb") as out_wf:
        out_wf.setnchannels(1)
        out_wf.setsampwidth(2)
        out_wf.setframerate(sample_rate)

        for i, seg in enumerate(ledger.segments):
            chunk_path = audio_dir / seg.audio_file
            if not chunk_path.exists():
                # Fallback search by prefix
                parts = seg.audio_file.split("_")
                if len(parts) >= 2:
                    matches = list(audio_dir.glob(f"{parts[0]}_{parts[1]}_*.wav"))
                    if matches:
                        chunk_path = matches[0]
                    else:
                        raise FileNotFoundError(f"Audio chunk not found: {chunk_path}")
                else:
                    raise FileNotFoundError(f"Audio chunk not found: {chunk_path}")

            with wave.open(str(chunk_path), "rb") as in_wf:
                in_frames = in_wf.readframes(in_wf.getnframes())
                out_wf.writeframes(in_frames)

            # Add silence padding if not the last segment
            if i < len(ledger.segments) - 1 and seg.pause_after_ms > 0:
                silence_samples = int(sample_rate * (seg.pause_after_ms / 1000.0))
                silence_bytes = b"\x00\x00" * silence_samples
                out_wf.writeframes(silence_bytes)

    os.replace(tmp_out, output_wav_path)
    logger.info(f"[+] Dialogue track stitched from ledger: {output_wav_path.name}")
    return output_wav_path


def build_chapter_timeline_ledger(
    chapter_id: int,
    script_segments: List[Dict[str, Any]],
    audio_chunk_paths: List[Path],
    cue_sheet: Optional[Dict[str, Any]] = None,
    soundscape_plan: Optional[Dict[str, Any]] = None,
    pause_ms: int = 450,
    output_ledger_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper for legacy orchestrator.
    Builds a granular, millisecond-accurate timeline ledger of the entire audio drama chapter.
    """
    foley_cues = cue_sheet.get("foley_cues", []) if cue_sheet else []
    cues_by_seg = {}
    for c in foley_cues:
        s_idx = c.get("segment_index", 1)
        cues_by_seg.setdefault(s_idx, []).append(c)

    primary_env = cue_sheet.get("primary_environment", "dense_forest_night") if cue_sheet else "dense_forest_night"
    primary_mood = soundscape_plan.get("primary_mood", "tense") if soundscape_plan else "tense"
    duck_gain = soundscape_plan.get("ducking_attenuation_db", -16.0) if soundscape_plan else -16.0

    pause_sec = float(pause_ms) / 1000.0
    timeline_items = []
    curr_t_sec = 0.0

    for idx, (seg, chunk_path) in enumerate(zip(script_segments, audio_chunk_paths), 1):
        dur_sec = get_audio_duration(chunk_path)
        end_t_sec = curr_t_sec + dur_sec

        t_start_ms = int(round(curr_t_sec * 1000))
        t_end_ms = int(round(end_t_sec * 1000))
        dur_ms = t_end_ms - t_start_ms

        speaker = seg.get("speaker", "Narrator")
        seg_cues = cues_by_seg.get(idx, [])
        foley_events = []
        for fc in seg_cues:
            offset = int(fc.get("offset_ms", 0))
            trigger_ms = min(t_end_ms, max(0, t_start_ms + offset))
            foley_events.append({
                "trigger_t_ms": trigger_ms,
                "foley_tag": fc.get("foley_tag", ""),
                "volume": float(fc.get("volume", 0.30)),
                "stereo_pan": float(fc.get("spatial_pan", 0.0)),
                "description": fc.get("description", ""),
            })

        # Extract metadata from Master Director Schema if present
        acting_info = seg.get("acting", {})
        delivery_style = acting_info.get("delivery_style", seg.get("emotion", "neutral")) if isinstance(acting_info, dict) else seg.get("emotion", "neutral")
        seg_env = seg.get("acoustic_env", primary_env)
        music_info = seg.get("music", {})
        seg_mood = music_info.get("mood", primary_mood) if isinstance(music_info, dict) else primary_mood
        seg_duck_db = float(music_info.get("ducking_db", duck_gain)) if isinstance(music_info, dict) and "ducking_db" in music_info else duck_gain
        seg_spatial = seg.get("spatial", {})
        seg_pan = float(seg_spatial.get("pan", 0.0)) if isinstance(seg_spatial, dict) and "pan" in seg_spatial else 0.0

        timeline_items.append({
            "segment_index": idx,
            "t_start_ms": t_start_ms,
            "t_end_ms": t_end_ms,
            "duration_ms": dur_ms,
            "speaker": speaker,
            "role": seg.get("type", "narration"),
            "emotion": seg.get("emotion", "neutral"),
            "delivery_style": delivery_style,
            "spatial_pan": seg_pan,
            "audio_chunk": chunk_path.name,
            "text": seg.get("text", ""),
            "foley_events": foley_events,
            "ambience": {
                "environment": seg_env,
                "volume": 0.14,
            },
            "music_ducking": {
                "score_mood": seg_mood,
                "is_ducked": True,
                "attenuation_db": seg_duck_db,
            },
        })

        curr_t_sec = end_t_sec + pause_sec

    total_duration_sec = curr_t_sec - pause_sec if curr_t_sec > pause_sec else curr_t_sec
    total_duration_ms = int(round(total_duration_sec * 1000))

    scene_items = []
    seg_times = {item["segment_index"]: (item["t_start_ms"], item["t_end_ms"]) for item in timeline_items}
    if soundscape_plan and "scenes" in soundscape_plan:
        for sc in soundscape_plan.get("scenes", []):
            s_start = sc.get("segment_start", 1)
            s_end = sc.get("segment_end", len(timeline_items))
            t_s = seg_times.get(s_start, (0, 0))[0]
            t_e = seg_times.get(s_end, (0, total_duration_ms))[1]
            sc_entry = dict(sc)
            sc_entry["t_start_ms"] = t_s
            sc_entry["t_end_ms"] = t_e
            sc_entry["duration_ms"] = max(0, t_e - t_s)
            if "cue_slice" in sc:
                cs = sc["cue_slice"]
                sc_entry["cue_slice"] = {
                    "section_name": cs.get("section_name"),
                    "source_track": cs.get("track_name"),
                    "start_sec": cs.get("start_sec"),
                    "end_sec": cs.get("end_sec"),
                    "energy_level": cs.get("energy_level"),
                }
            scene_items.append(sc_entry)

    leitmotif_events = []
    if soundscape_plan and "level1_leitmotifs" in soundscape_plan:
        for lm in soundscape_plan.get("level1_leitmotifs", []):
            trig_seg = int(lm.get("trigger_segment", 1))
            t_s = seg_times.get(trig_seg, (0, 0))[0]
            lm_entry = {
                "theme": lm.get("theme", ""),
                "trigger_segment": trig_seg,
                "t_start_ms": t_s,
                "timing": lm.get("timing", "under"),
                "volume": float(lm.get("volume", 0.22)),
            }
            if "cue_slice" in lm:
                cs = lm["cue_slice"]
                lm_entry["cue_slice"] = {
                    "section_name": cs.get("section_name"),
                    "source_track": cs.get("track_name"),
                    "start_sec": cs.get("start_sec"),
                    "end_sec": cs.get("end_sec"),
                    "energy_level": cs.get("energy_level"),
                }
            leitmotif_events.append(lm_entry)

    chapter_bed = soundscape_plan.get("level2_chapter_bed", {}) if soundscape_plan else {}

    ledger = {
        "chapter_id": chapter_id,
        "total_duration_ms": total_duration_ms,
        "total_duration_sec": round(total_duration_ms / 1000.0, 2),
        "total_duration_min": round(total_duration_ms / 60000.0, 2),
        "total_scenes": len(scene_items),
        "scenes": scene_items,
        "total_segments": len(timeline_items),
        "total_foley_events": sum(len(item["foley_events"]) for item in timeline_items),
        "hierarchical_score": {
            "standard": "3-Level Dynamic BGM with Acoustic Cue-Slicing (Leitmotif + Chapter Bed + Scene Stems)",
            "level1_leitmotifs": leitmotif_events,
            "level2_chapter_bed": chapter_bed,
            "level3_dynamic_scenes": len(scene_items),
            "energy_zones_engine": "Non-Destructive FFmpeg Micro-Slicing (Intro/Tension/Climax/Aftermath)",
        },
        "timeline": timeline_items,
    }

    if output_ledger_file:
        output_ledger_file = Path(output_ledger_file).resolve()
        output_ledger_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_ledger_file, "w", encoding="utf-8") as f:
            json.dump(ledger, f, ensure_ascii=False, indent=2)

    return ledger
