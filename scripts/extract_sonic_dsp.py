#!/usr/bin/env python3
"""
Offline High-Performance DSP Scanner for Sound Bank BGM Tracks.
Extracts physical acoustic invariants (LUFS, True Peak, Speech Corridor Density,
Transient Drop Seconds, Intro Bed Boundaries, and ID3 Tags) with 0 network bandwidth.
Saves intermediate acoustic profiles to scratch/bgm_dsp_profiles.json.
"""

import io
import json
import logging
import os
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
from scipy.io import wavfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("extract_sonic_dsp")

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "audiobooks" / "sound_bank" / "sound_bank.db"
SCRATCH_DIR = ROOT_DIR / "scratch"
OUTPUT_JSON = SCRATCH_DIR / "bgm_dsp_profiles.json"


def extract_id3_tags(filepath: Path) -> Dict[str, Any]:
    """Extract ID3 tags using ffprobe in JSON format."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format_tags:format=duration",
        "-of", "json", str(filepath)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            data = json.loads(res.stdout).get("format", {})
            tags = data.get("tags", {})
            dur = float(data.get("duration", 0.0) or 0.0)
            return {
                "title": tags.get("title") or tags.get("TITLE") or filepath.stem,
                "artist": tags.get("artist") or tags.get("ARTIST") or "Unknown Artist",
                "album": tags.get("album") or tags.get("ALBUM") or "Cinematic Soundtrack",
                "track": tags.get("track") or tags.get("TRACK") or "",
                "date": tags.get("date") or tags.get("DATE") or "",
                "genre": tags.get("genre") or tags.get("GENRE") or "Soundtrack",
                "duration_sec": dur,
            }
    except Exception as e:
        logger.debug(f"ID3 extraction failed for {filepath}: {e}")
    return {
        "title": filepath.stem,
        "artist": "Unknown Artist",
        "album": "Cinematic Soundtrack",
        "duration_sec": 0.0,
    }


def analyze_audio_dsp(filepath: Path, duration_sec: float) -> Dict[str, Any]:
    """
    Decodes audio via FFmpeg pipe and computes:
    - EBU R128 Integrated LUFS & True Peak
    - RMS Energy Envelope (250ms windows)
    - Intro Bed End Offset & Climax Drop Peak Offsets
    - 300Hz-3.5kHz Vocal Corridor Energy Ratio (Speech Masking Risk)
    """
    # 1. EBU R128 Loudness measurement
    cmd_lufs = [
        "ffmpeg", "-nostats", "-i", str(filepath),
        "-filter_complex", "ebur128=peak=true",
        "-f", "null", "-"
    ]
    lufs = -18.0
    true_peak = -1.0
    try:
        res = subprocess.run(cmd_lufs, capture_output=True, text=True, timeout=10)
        import re
        m_lufs = re.search(r"I:\s+(-?\d+\.\d+)\s+LUFS", res.stderr)
        if m_lufs:
            lufs = float(m_lufs.group(1))
        m_tp = re.search(r"Peak:\s+(-?\d+\.\d+)\s+dBFS", res.stderr)
        if m_tp:
            true_peak = float(m_tp.group(1))
    except Exception as e:
        logger.debug(f"EBUR128 failed for {filepath}: {e}")

    # 2. Decode up to 90 seconds mono 16kHz WAV for waveform analysis
    scan_dur = min(90.0, duration_sec) if duration_sec > 5.0 else 60.0
    cmd_wav = [
        "ffmpeg", "-nostats", "-i", str(filepath),
        "-t", str(scan_dur),
        "-ac", "1", "-ar", "16000",
        "-f", "wav", "-"
    ]
    
    intro_bed_end_sec = 0.0
    transient_drops = []
    vocal_corridor_density = 0.25
    vocal_clash_risk = "LOW"
    bpm_est = 90.0

    try:
        proc = subprocess.run(cmd_wav, capture_output=True, timeout=10)
        if proc.returncode == 0 and len(proc.stdout) > 44:
            sr, data = wavfile.read(io.BytesIO(proc.stdout))
            data_float = data.astype(float)

            # RMS Envelope (250ms window, 125ms step)
            win_size = int(sr * 0.25)
            step_size = int(sr * 0.125)
            rms = []
            times = []
            for i in range(0, len(data_float) - win_size, step_size):
                frame = data_float[i:i+win_size]
                r = np.sqrt(np.mean(frame**2))
                rms.append(r)
                times.append(i / sr)

            if len(rms) > 8:
                rms_arr = np.array(rms)
                max_rms = np.max(rms_arr) or 1.0
                norm_rms = rms_arr / max_rms

                # Find major peaks (peaks > 0.6 of max)
                peak_indices = [
                    i for i in range(1, len(norm_rms) - 1)
                    if norm_rms[i] > norm_rms[i-1] and norm_rms[i] > norm_rms[i+1] and norm_rms[i] >= 0.65
                ]
                transient_drops = [round(times[idx], 2) for idx in peak_indices[:5]]
                if not transient_drops:
                    transient_drops = [round(times[int(np.argmax(norm_rms))], 2)]

                # Intro bed end: when normalized RMS first exceeds 0.35
                surges = [times[i] for i, r in enumerate(norm_rms) if r >= 0.35]
                intro_bed_end_sec = round(surges[0], 2) if surges else round(times[0], 2)

            # 3. Speech Corridor Density: FFT ratio in 300Hz - 3500Hz
            if len(data_float) > 2048:
                fft_vals = np.abs(np.fft.rfft(data_float[:sr * 10]))  # analyze first 10s
                freqs = np.fft.rfftfreq(len(data_float[:sr * 10]), d=1.0/sr)
                total_energy = np.sum(fft_vals**2) or 1.0
                corridor_mask = (freqs >= 300) & (freqs <= 3500)
                corridor_energy = np.sum(fft_vals[corridor_mask]**2)
                vocal_corridor_density = round(float(corridor_energy / total_energy), 3)

                if vocal_corridor_density > 0.45:
                    vocal_clash_risk = "SEVERE"
                elif vocal_corridor_density >= 0.28:
                    vocal_clash_risk = "MODERATE"
                else:
                    vocal_clash_risk = "LOW"

            # 4. Tempo Estimation via envelope autocorrelation
            if len(rms) > 16:
                env_diff = np.diff(rms_arr)
                env_diff = np.maximum(0, env_diff)
                corr = np.correlate(env_diff - np.mean(env_diff), env_diff - np.mean(env_diff), mode='full')
                corr = corr[len(env_diff)-1:]
                # 60 BPM to 180 BPM lags at 8Hz (125ms step)
                # 60 BPM = 1.0s = 8 frames; 180 BPM = 0.33s = ~2.6 frames
                min_lag, max_lag = 2, min(len(corr)-1, 12)
                if max_lag > min_lag:
                    sub_corr = corr[min_lag:max_lag]
                    best_lag = min_lag + np.argmax(sub_corr)
                    bpm_est = round(60.0 / (best_lag * 0.125), 1)
                    if bpm_est < 60:
                        bpm_est *= 2
                    elif bpm_est > 180:
                        bpm_est /= 2
    except Exception as e:
        logger.debug(f"Waveform DSP failed for {filepath}: {e}")

    return {
        "integrated_lufs": round(lufs, 1),
        "true_peak_dbtp": round(true_peak, 1),
        "intro_bed_end_sec": intro_bed_end_sec,
        "transient_drops_sec": transient_drops,
        "speech_corridor_density": vocal_corridor_density,
        "vocal_clash_risk": vocal_clash_risk,
        "bpm": round(bpm_est, 1),
    }


def process_single_track(row: tuple) -> Dict[str, Any]:
    """Worker to extract ID3 and DSP metrics for one database row."""
    tid, filename, filepath, dur = row
    p = Path(filepath)
    if not p.exists():
        logger.warning(f"Track ID {tid} not found on disk: {filepath}")
        return {}

    id3 = extract_id3_tags(p)
    actual_dur = id3.get("duration_sec") or dur
    dsp = analyze_audio_dsp(p, actual_dur)

    return {
        "track_id": tid,
        "filename": filename,
        "filepath": str(p),
        "id3_metadata": id3,
        "acoustic": {
            "true_peak_dbtp": dsp["true_peak_dbtp"],
            "integrated_lufs": dsp["integrated_lufs"],
            "speech_corridor_density": dsp["speech_corridor_density"],
            "transient_drops_sec": dsp["transient_drops_sec"],
            "bpm": dsp["bpm"],
            "intro_bed_end_sec": dsp["intro_bed_end_sec"],
            "vocal_clash_risk": dsp["vocal_clash_risk"],
        }
    }


def main():
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    rows = c.execute("""
        SELECT id, filename, filepath, duration_sec 
        FROM sound_catalog 
        WHERE category = 'BGM' 
        ORDER BY id
    """).fetchall()
    conn.close()

    total = len(rows)
    logger.info(f"Starting Offline DSP Extraction across {total} BGM soundtrack tracks...")
    start_time = time.time()

    profiles: Dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {executor.submit(process_single_track, r): r[0] for r in rows}
        done_count = 0
        for future in as_completed(future_map):
            done_count += 1
            res = future.result()
            if res and "track_id" in res:
                profiles[str(res["track_id"])] = res
            if done_count % 25 == 0 or done_count == total:
                logger.info(f"Progress: {done_count}/{total} tracks processed ({time.time() - start_time:.1f}s)")

    elapsed = time.time() - start_time
    logger.info(f"Completed DSP extraction for {len(profiles)} tracks in {elapsed:.2f}s!")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)
    logger.info(f"Saved profiles to {OUTPUT_JSON} ({os.path.getsize(OUTPUT_JSON)} bytes)")


if __name__ == "__main__":
    main()
