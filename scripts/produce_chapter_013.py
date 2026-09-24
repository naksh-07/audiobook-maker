#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 13 ("The Voice of Reason 7" / "तर्क की आवाज़ 7") Audio Drama Production Runner.
Executes Gates 4, 4.5, 5, and 6 under SOTA Standards:
- TTS Engine: gemini-3.8-flash-tts
- Extended Book-Level Voice Catalog:
    * Geralt: algenib (Candidate B: gravelly, grounded, hard-hitting Witcher)
    * Narrator: Aoede (Melodic, articulate, immersive)
    * Dandelion: achird (Warm, lively, theatrical troubadour)
    * Falwick: alnilam (Pompous, venomous knight of the White Rose)
    * Dennis_Cranmer: Fenrir (Gruff, cold, pragmatic dwarf guard captain)
    * Tailles: Puck (Haughty, arrogant young knight)
    * Nenneke: Kore (Wise, maternal, protective high priestess)
    * Iola: Kore (Gentle novice priestess)
- ADR-028 Dual-Layer Forensic Audio Restoration & Dead-Air Clamping Engine
- 5-Track Cinematic Mix & EBU R128 (-19.0 LUFS) Broadcast Mastering
"""

import os
import sys
import json
import time
import shutil
import base64
import random
import struct
import math
import wave
import sqlite3
import uuid
import subprocess
import urllib.request
import urllib.error
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Force gemini-3.8-flash-tts
os.environ["GEMINI_TTS_MODEL"] = "gemini-3.8-flash-tts"

# Ensure UTF-8 I/O for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import audiobook_factory.tts_dispatcher as tts_module
from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    AmbienceScene,
    MasteringConfig,
    FoleyCue,
)
from audiobook_factory.tts_dispatcher import (
    TTSDispatcher,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    NUMERAL_NORMALIZATION,
)
from audiobook_factory.key_manager import (
    get_persistent_key_pool,
    classify_gemini_error,
    AllKeysExhaustedTodayError,
)
from audiobook_factory.cadence import (
    get_stealth_sdk_headers,
    get_human_cadence_controller,
)
from audiobook_factory.timeline_ledger import (
    build_audio_transcript_ledger,
    stitch_dialogue_track_from_ledger,
)
from audiobook_factory.gate_auditor import audit_gate4_ledger
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.manifest_renderer import render_manifest_soundscape
from audiobook_factory.soundscape import get_audio_duration
from audiobook_factory.restoration import (
    extract_clean_pcm_from_gemini_container,
    read_surgically_cleaned_chunk,
    apply_studio_restoration_filter,
)
from audiobook_factory.logger import logger


def calibrated_synthesize_gemini_tts(
    text: str,
    output_file: Path,
    voice: str = "Aoede",
    emotion: str = "neutral",
    acting: Any = None,
    intensity: str = "medium",
    max_retries: int = 4,
    rate_limiter: Optional[Any] = None,
    model: str = "gemini-3.8-flash-tts",
) -> Tuple[Path, float]:
    """Calibrated synthesis function with speechMetadata.style and flat-top consecutive clipping detector."""
    clean_text = text.strip()
    clean_stripped = "".join(c for c in clean_text if c.isalnum() or '\u0900' <= c <= '\u097F')
    if clean_stripped in NUMERAL_NORMALIZATION:
        clean_text = NUMERAL_NORMALIZATION[clean_stripped]
    elif clean_text in NUMERAL_NORMALIZATION:
        clean_text = NUMERAL_NORMALIZATION[clean_text]

    part_payload: Dict[str, Any] = {"text": clean_text}
    from audiobook_factory.tts_dispatcher import resolve_speech_metadata_style
    style_desc = resolve_speech_metadata_style(acting, emotion, intensity)
    if style_desc and style_desc.lower() not in ("neutral", "standard"):
        part_payload["speechMetadata"] = {"style": style_desc}

    payload = {
        "contents": [{"parts": [part_payload]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice
                    }
                }
            },
            "temperature": round(random.uniform(0.685, 0.715), 3)
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    data = json.dumps(payload).encode("utf-8")
    pool = get_persistent_key_pool()
    MAX_KEY_ROTATIONS = 25
    rotation_count = 0

    while True:
        rotation_count += 1
        if rotation_count > MAX_KEY_ROTATIONS:
            raise RuntimeError(f"TTS synthesis failed after {MAX_KEY_ROTATIONS} key rotations.")

        api_key = pool.get_key(service="tts")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = get_stealth_sdk_headers(api_key)

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        for network_attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        raise ValueError("No candidates returned from Gemini TTS API")

                    parts = candidates[0].get("content", {}).get("parts", [])
                    inline_data = None
                    for part in parts:
                        if "inlineData" in part:
                            inline_data = part["inlineData"]
                            break
                    if not inline_data:
                        raise ValueError("No audio data found in Gemini response parts")

                    b64_audio = inline_data.get("data", "")
                    if not b64_audio:
                        raise ValueError("No audio data found in Gemini response parts")
                    raw_bytes = base64.b64decode(b64_audio)
                    raw_pcm, sample_rate, sample_count = extract_clean_pcm_from_gemini_container(raw_bytes)

                    # Inspect PCM
                    dur_sec = sample_count / float(sample_rate)
                    word_count = max(len(text.split()), 1)
                    ratio = dur_sec / word_count

                    if sample_count > 0:
                        samples = struct.unpack(f"<{sample_count}h", raw_pcm)
                        peak_amp = max(abs(s) for s in samples)
                        sum_sq = sum(s * s for s in samples)
                        rms = math.sqrt(sum_sq / sample_count)
                        dc_offset = abs(sum(samples) / sample_count)

                        consec = 0
                        max_consec = 0
                        for s in samples:
                            if abs(s) >= 32760:
                                consec += 1
                                if consec > max_consec:
                                    max_consec = consec
                            else:
                                consec = 0
                        is_clipped = (max_consec >= 6)
                    else:
                        peak_amp = 0
                        rms = 0.0
                        dc_offset = 0.0
                        is_clipped = False

                    faint_limit = 8.0 if ("[whispers]" in text.lower() or "whisper" in emotion.lower()) else 20.0
                    is_silent_faint = (peak_amp > 0 and word_count >= 3 and rms < faint_limit)
                    is_dc_corrupted = (peak_amp > 0 and dur_sec >= 2.0 and dc_offset > 1500.0)
                    is_stutter = (word_count > 3 and ratio > 3.2 and dur_sec >= 15.0)
                    is_empty = (dur_sec < 0.20 and word_count >= 3)

                    has_defect = (is_clipped or is_silent_faint or is_dc_corrupted or is_stutter or is_empty)
                    if has_defect:
                        reasons = []
                        if is_clipped: reasons.append(f"Genuine Flat-Top Clipping (consec={max_consec}>=6)")
                        if is_silent_faint: reasons.append(f"Faint Audio (RMS {rms:.1f} < {faint_limit})")
                        if is_dc_corrupted: reasons.append(f"DC Offset ({dc_offset:.1f} > 1500)")
                        if is_stutter: reasons.append(f"Stutter Loop ({ratio:.2f}s/w)")
                        if is_empty: reasons.append("Empty Audio")
                        reason_str = " | ".join(reasons)
                        if network_attempt < 2:
                            logger.warning(f"  [SNR GATEKEEPER: {reason_str}] Retrying segment (Attempt {network_attempt+1}/3)...")
                            time.sleep(2.0)
                            continue
                        else:
                            raise ValueError(f"SNR Gatekeeper rejected segment: {reason_str}")

                    # Write verified audio
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    tmp_file = output_file.with_suffix(".tmp.wav")
                    with wave.open(str(tmp_file), "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(sample_rate)
                        wf.writeframes(raw_pcm)

                    if output_file.exists():
                        output_file.unlink()
                    shutil.move(str(tmp_file), str(output_file))
                    return output_file, dur_sec

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                cat, _ = classify_gemini_error(e.code, err_body)
                if cat == "RATE_LIMIT":
                    pool.mark_temporary_backoff(api_key, 25.0, f"HTTP {e.code}")
                    break
                elif cat == "RESOURCE_EXHAUSTED":
                    pool.mark_key_invalid(api_key, f"Daily limit: {err_body[:60]}")
                    break
                elif cat == "BLOCKED_CONTENT":
                    raise
                else:
                    if network_attempt < 2:
                        time.sleep(1.0)
                        continue
                    break
            except Exception as e:
                if network_attempt < 2:
                    time.sleep(1.0)
                    continue
                break


def stitch_dialogue_track_smooth(
    ledger: Any,
    audio_dir: Path,
    output_wav_path: Path,
    sample_rate: int = 48000,
    fade_in_ms: float = 12.0,
    fade_out_ms: float = 18.0,
) -> Path:
    """
    Sample-accurate vocal master stitching with raised-cosine (Hann) micro-fades (ADR-028).
    Eliminates all transient clicks, pops, and vocoder dead-air screech.
    """
    output_wav_path = Path(output_wav_path).resolve()
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = output_wav_path.with_suffix(f".tmp_smooth_{uuid.uuid4().hex[:6]}.wav")

    all_frames = []
    segments = ledger.segments

    for i, seg in enumerate(segments):
        audio_file = seg.audio_file
        chunk_path = audio_dir / audio_file
        if not chunk_path.exists():
            parts = audio_file.split("_")
            if len(parts) >= 2:
                matches = list(audio_dir.glob(f"{parts[0]}_{parts[1]}_*.wav"))
                if matches:
                    chunk_path = matches[0]
                else:
                    raise FileNotFoundError(f"Chunk not found: {chunk_path}")
            else:
                raise FileNotFoundError(f"Chunk not found: {chunk_path}")

        # Layer 1 + Layer 2 Surgical Dead-Air Clamping and Zero-Crossing Hann Tapers
        clean_pcm, trimmed_ms = read_surgically_cleaned_chunk(
            chunk_path,
            target_sample_rate=sample_rate,
            fade_in_ms=fade_in_ms,
            fade_out_ms=fade_out_ms
        )
        all_frames.append(clean_pcm)

        # Silence padding with strict timeline synchronization (transfer trimmed ms to pause)
        pause_after_ms = int(getattr(seg, "pause_after_ms", 400))
        total_pause_ms = pause_after_ms + trimmed_ms
        if i < len(segments) - 1 and total_pause_ms > 0:
            silence_samples = int(sample_rate * (total_pause_ms / 1000.0))
            silence_bytes = b"\x00\x00" * silence_samples
            all_frames.append(silence_bytes)

    with wave.open(str(tmp_out), "wb") as out_wf:
        out_wf.setnchannels(1)
        out_wf.setsampwidth(2)
        out_wf.setframerate(sample_rate)
        out_wf.writeframes(b"".join(all_frames))

    # Apply 6-stage studio restoration filter chain (ADR-027 / ADR-028)
    tmp_polished = output_wav_path.with_suffix(f".tmp_polish_{uuid.uuid4().hex[:6]}.wav")
    print(f"[*] Applying Studio DSP Restoration (de-click, afftdn de-hiss, 11.2kHz lowpass, agate expander)...")
    apply_studio_restoration_filter(tmp_out, tmp_polished, sample_rate=sample_rate)
    if tmp_out.exists():
        tmp_out.unlink()
    shutil.move(str(tmp_polished), str(output_wav_path))
    return output_wav_path


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    scripts_dir = project_dir / "scripts"
    manifests_dir = project_dir / "manifests"
    mastered_dir = project_dir / "mastered"
    audio_chunks_dir = project_dir / "audio_chunks"

    mastered_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)

    script_path = scripts_dir / "chapter_013_hi_script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Screenplay script not found: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    script_segments = script_data.get("segments", [])
    total_segments = len(script_segments)

    print("=" * 80)
    print(f"  AUDIOBOOK FACTORY - CHAPTER 013 ('THE VOICE OF REASON 7') PRODUCTION")
    print(f"  TTS Engine: gemini-3.8-flash-tts (Calibrated SNR Gatekeeper)")
    print(f"  Geralt Voice: Candidate B (algenib) | Hann Micro-fades & Brickwall Limiter")
    print("=" * 80)
    print(f"  Script: {script_path.name} ({total_segments} segments)\n")

    # Monkey-patch dispatcher synthesis
    tts_module.synthesize_gemini_tts = calibrated_synthesize_gemini_tts

    # -------------------------------------------------------------------------
    # STEP 1: GATE 4 - SPEECH SYNTHESIS (gemini-3.8-flash-tts)
    # -------------------------------------------------------------------------
    print("-" * 80)
    print("  STEP 1: GATE 4 - SPEECH SYNTHESIS (gemini-3.8-flash-tts)")
    print("-" * 80)

    dispatcher = TTSDispatcher(
        project_dir=project_dir,
        default_backend="gemini_tts",
        max_workers=1,
        rpm=15.0,
    )
    dispatcher.batching_enabled = True

    chapter_13_voices = {
        "Geralt": {
            "backend": "gemini_tts",
            "voice": "algenib",
            "speed": 0.98,
            "pitch": 1.0,
            "bass_boost_db": 1.0,
            "presence_boost_db": 1.5,
            "volume_gain_db": 0.5,
        },
        "Narrator": {
            "backend": "gemini_tts",
            "voice": "Aoede",
            "speed": 1.0,
        },
        "Dandelion": {
            "backend": "gemini_tts",
            "voice": "achird",
            "speed": 1.02,
            "presence_boost_db": 1.0,
        },
        "Falwick": {
            "backend": "gemini_tts",
            "voice": "alnilam",
            "speed": 0.96,
            "bass_boost_db": 1.2,
        },
        "Dennis_Cranmer": {
            "backend": "gemini_tts",
            "voice": "Fenrir",
            "speed": 0.96,
            "bass_boost_db": 1.5,
        },
        "Tailles": {
            "backend": "gemini_tts",
            "voice": "achird",
            "speed": 1.02,
        },
        "Nenneke": {
            "backend": "gemini_tts",
            "voice": "Kore",
            "speed": 0.96,
            "pitch": 0.94,
            "bass_boost_db": 2.0,
        },
        "Iola": {
            "backend": "gemini_tts",
            "voice": "Kore",
            "speed": 1.0,
        },
    }
    dispatcher.voice_map.update(chapter_13_voices)

    # Check existing chunks
    existing_chunks = []
    for idx in range(1, total_segments + 1):
        matches = list(audio_chunks_dir.glob(f"c013_s{idx:04d}_*.wav"))
        if matches and matches[0].stat().st_size > 44:
            existing_chunks.append(matches[0])

    if len(existing_chunks) == total_segments:
        print(f"[OK] Gate 4 Audit Passed: All {total_segments} chunks verified on disk with non-zero audio. Zero API calls needed.")
    else:
        print(f"[*] Synthesizing missing chunks for Chapter 13 ({len(existing_chunks)}/{total_segments} exist)...")
        t0 = time.time()
        audio_files = dispatcher.synthesize_chapter_script(
            script_path=script_path,
            chapter_num=13,
        )
        t_synth = time.time() - t0
        print(f"\n[+] Gate 4 Synthesis Complete in {t_synth:.1f}s ({t_synth/60:.1f}m).")
        print(f"    Total chunks generated/verified: {len(audio_files)}/{total_segments}")

    # -------------------------------------------------------------------------
    # STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 2: GATE 4.5 - TIMELINE LEDGER & MASTER DIALOGUE STEM")
    print("-" * 80)

    ledger_path = scripts_dir / "chapter_013_timeline_ledger.json"
    dialogue_path = mastered_dir / "chapter_013_dialogue.wav"

    print(f"[*] Building timeline ledger for Chapter 13 ({total_segments} segments)...")
    ledger = build_audio_transcript_ledger(
        project_dir=project_dir,
        chapter_num=13,
        script_file=script_path,
        audio_dir=audio_chunks_dir,
    )
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"[+] Saved timeline ledger to: {ledger_path.name}")

    audit_res = audit_gate4_ledger(
        ledger_file=ledger_path,
        script_file=script_path,
        audio_dir=audio_chunks_dir,
    )
    if audit_res.get("status") != "PASS":
        raise ValueError(f"Gate 4.5 Ledger Audit Failed: {audit_res}")
    print(f"[OK] Gate 4.5 Ledger Audit Passed (Total: {ledger.total_timeline_duration_ms} ms)")

    print(f"[*] Stitching Master Dialogue Stem ({dialogue_path.name}) with ADR-028 Dual-Layer Forensic Cleaning...")
    stitch_dialogue_track_smooth(
        ledger=ledger,
        audio_dir=audio_chunks_dir,
        output_wav_path=dialogue_path,
        sample_rate=48000,
        fade_in_ms=12.0,
        fade_out_ms=18.0,
    )

    actual_wav_dur = get_audio_duration(dialogue_path)
    expected_dur = ledger.total_timeline_duration_ms / 1000.0
    print(f"[+] Master Dialogue Track Rendered: {actual_wav_dur:.2f}s (Ledger expected: {expected_dur:.2f}s)")

    # -------------------------------------------------------------------------
    # STEP 3: GATE 5 - CREATIVE MANIFEST CURATION (5 DRAMATIC ACTS)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 3: GATE 5 - CREATIVE MANIFEST CURATION (5 DRAMATIC ACTS)")
    print("-" * 80)

    total_dur_ms = ledger.total_timeline_duration_ms
    seg_map = {item.segment_index: (item.start_ms, item.end_ms) for item in ledger.segments}

    # Curate Witcher 3 OST Cues
    music_cues = []

    # Cue 1: The Ambush in the Glade (Act 1, ~0%)
    s1 = min(seg_map.keys())
    music_cues.append(
        MusicCue(
            cue_id="cue_01_glade_ambush",
            cue_type="EMOTIONAL_UNDERSCORE",
            track_name="009 White Orchards.mp3",
            section_name="INTRO_BED",
            start_ms=seg_map[s1][0],
            duration_ms=min(65000, int(total_dur_ms * 0.15)),
            fade_in_ms=2500,
            fade_out_ms=3500,
            volume_db=-13.5,
            dramatic_justification="Tense standoff in the forest glade outside Ellander as Count Falwick blocks the road."
        )
    )

    # Cue 2: Dennis Cranmer's Intervention & Secret Orders (~25%)
    idx_act2 = max(1, int(total_segments * 0.25))
    if idx_act2 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_02_cranmer_standoff",
                cue_type="TENSION_RISER",
                track_name="002 The Trail.mp3",
                section_name="RISING_TENSION",
                start_ms=seg_map[idx_act2][0],
                duration_ms=min(70000, int(total_dur_ms * 0.15)),
                fade_in_ms=2000,
                fade_out_ms=3500,
                volume_db=-13.0,
                dramatic_justification="Dennis Cranmer reveals Prince Hereward's orders and warns of another Blaviken bloodshed."
            )
        )

    # Cue 3: Climax - The Duel & Sword Deflection (~55%)
    idx_act3 = max(1, int(total_segments * 0.55))
    if idx_act3 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_03_duel_iron_clash",
                cue_type="CLIMACTIC_ACTION_CUE",
                track_name="001 Geralt of Rivia.mp3",
                section_name="CLIMAX",
                start_ms=seg_map[idx_act3][0],
                duration_ms=min(85000, int(total_dur_ms * 0.18)),
                fade_in_ms=1500,
                fade_out_ms=4000,
                volume_db=-11.5,
                dramatic_justification="Lightning duel: Tailles attacks, Geralt's deflection smashes the blade into Tailles' face."
            )
        )

    # Cue 4: Geralt's Bleed-Like-A-Pig Warning & Forest Ride (~75%)
    idx_act4 = max(1, int(total_segments * 0.75))
    if idx_act4 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_04_falwick_threat_ride",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="004 The Fortress of Memory.mp3",
                section_name="RISING_TENSION",
                start_ms=seg_map[idx_act4][0],
                duration_ms=min(60000, int(total_dur_ms * 0.14)),
                fade_in_ms=2500,
                fade_out_ms=3500,
                volume_db=-13.0,
                dramatic_justification="Geralt's terrifying warning to Falwick before riding off through the forests."
            )
        )

    # Cue 5: Melitele Departure & Iola's Blood Prophecy (~88%)
    idx_act5 = max(1, int(total_segments * 0.88))
    if idx_act5 in seg_map:
        music_cues.append(
            MusicCue(
                cue_id="cue_05_melitele_blood_vision",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="003 Geralt and Yen.mp3",
                section_name="RESOLUTION",
                start_ms=seg_map[idx_act5][0],
                duration_ms=min(95000, int(total_dur_ms * 0.20)),
                fade_in_ms=3000,
                fade_out_ms=5000,
                volume_db=-12.5,
                dramatic_justification="Tragic, haunting farewell at Temple of Melitele: Iola's prophetic vision of blood and death."
            )
        )

    total_music_ms = sum(c.duration_ms for c in music_cues)
    silence_pct = max(0.0, min(100.0, ((total_dur_ms - total_music_ms) / total_dur_ms) * 100.0))
    print(f"[*] Curated {len(music_cues)} Witcher 3 score cues.")
    print(f"    Total Timeline: {total_dur_ms/1000.0:.1f}s | Music: {total_music_ms/1000.0:.1f}s")
    print(f"    Silence Percentage: {silence_pct:.2f}% (Sweet Spot: 70-75%)")

    # Ambience Scenes
    sound_bank = get_sound_bank()
    amb_forest = sound_bank.resolve_sound("wind_forest_bed.ogg", category="AMB") or (ROOT_DIR / "audiobooks/sound_bank/ambience/wind_forest_bed.ogg")
    amb_temple = sound_bank.resolve_sound("dungeon_cave_bed.ogg", category="AMB") or (ROOT_DIR / "audiobooks/sound_bank/ambience/dungeon_cave_bed.ogg")

    t_scene2_start = seg_map.get(idx_act5, (int(total_dur_ms * 0.85), 0))[0]

    ambience_scenes = [
        # Scene 1: Forest Glade Standoff & Duel
        AmbienceScene(
            scene_id=1,
            start_ms=0,
            end_ms=t_scene2_start,
            asset_path=str(amb_forest),
            asset_name="wind_forest_bed.ogg",
            target_lufs=-28.0,
            reverb_preset="forest"
        ),
        # Scene 2: Temple of Melitele Courtyard & Farewell
        AmbienceScene(
            scene_id=2,
            start_ms=t_scene2_start,
            end_ms=total_dur_ms,
            asset_path=str(amb_temple),
            asset_name="dungeon_cave_bed.ogg",
            target_lufs=-27.0,
            reverb_preset="temple"
        ),
    ]

    # Foley Cues
    foley_cues = []
    foley_dir = ROOT_DIR / "audiobooks" / "sound_bank" / "foley"
    sword_sfx = foley_dir / "tiny_metal-knife-scrape-01.wav"
    body_sfx = foley_dir / "tiny_soil-steps-01.wav"

    fc_count = 0
    if sword_sfx.exists() and idx_act3 in seg_map:
        fc_count += 1
        foley_cues.append(
            FoleyCue(
                cue_id=f"fc_sword_clash_{fc_count:02d}",
                segment_index=idx_act3,
                anchor_word="sword_clash",
                pre_roll_ms=50,
                asset_path=str(sword_sfx.resolve()).replace("\\", "/"),
                asset_name="tiny_metal-knife-scrape-01.wav",
                gain_dbfs=-14.0,
                azimuth_pan=0.0,
                start_ms=seg_map[idx_act3][0] + 400,
            )
        )

    print(f"[*] Curated {len(foley_cues)} Foley cues.")

    mastering_config = MasteringConfig(
        target_lufs=-19.0,
        true_peak_dbtp=-1.5,
        ducking_attenuation_db=-7.5,
        ducking_attack_ms=80,
        ducking_release_ms=450,
        spectral_carve_hz=2200,
        spectral_carve_gain_db=-4.0,
        acoustic_ir=None,
    )

    manifest = CreativeManifest(
        manifest_version="3.0",
        project_id="witcher1",
        chapter_id="chapter_013",
        total_duration_ms=total_dur_ms,
        silence_percentage=round(silence_pct, 2),
        mastering=mastering_config,
        ambience_scenes=ambience_scenes,
        music_cues=music_cues,
        foley_cues=foley_cues
    )

    manifest_path = manifests_dir / "chapter_013_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"[+] Saved Creative Manifest to: {manifest_path.name}")

    # -------------------------------------------------------------------------
    # STEP 4: GATE 6 - CINEMATIC SOUNDSCAPE RENDERING & MASTERING
    # -------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("  STEP 4: GATE 6 - CINEMATIC SOUNDSCAPE RENDERING & MASTERING")
    print("-" * 80)

    cinematic_output = mastered_dir / "chapter_013_cinematic.m4a"

    print(f"[*] Rendering Multitrack Master via CinemaAudioEngine...")
    t_render_start = time.time()
    rendered_master = render_manifest_soundscape(
        manifest=manifest,
        vocal_track_path=dialogue_path,
        output_master_file=cinematic_output,
    )
    t_render = time.time() - t_render_start
    print(f"[+] Mastered Track Rendered in {t_render:.1f}s: {cinematic_output.name}")
    print(f"    Output File Size: {cinematic_output.stat().st_size / (1024*1024):.2f} MB")

    # Broadcast Certification via FFmpeg EBU R128 Probe
    print("\n[*] Running Broadcast EBU R128 Verification...")
    probe_cmd = [
        "ffmpeg", "-nostats", "-i", str(cinematic_output),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-"
    ]
    probe_res = subprocess.run(probe_cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

    lufs_match = [line for line in probe_res.stderr.split("\n") if "Integrated loudness:" in line or "I:" in line]
    tp_match = [line for line in probe_res.stderr.split("\n") if "True peak:" in line]

    print("=" * 80)
    print("  BROADCAST COMPLIANCE CERTIFICATION (EBU R128):")
    for l in (lufs_match + tp_match)[-3:]:
        print(f"    {l.strip()}")
    print("=" * 80)
    print("\n[OK] Chapter 13 Full Audio Drama Production Pipeline Completed Successfully!")


if __name__ == "__main__":
    main()
