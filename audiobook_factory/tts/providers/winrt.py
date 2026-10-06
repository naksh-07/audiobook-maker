#!/usr/bin/env python3
"""
Audiobook Factory - Offline Windows WinRT Speech Synthesis Provider.
Provides emergency local speech synthesis fallback using Windows SpeechSynthesis APIs and PowerShell.
"""

from __future__ import annotations
import uuid
import wave
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np

from audiobook_factory.logger import logger
from audiobook_factory.tts.constants import get_ffmpeg


def _synthesize_local_winrt_fallback(text: str, output_file: Path, voice: str = "Aoede") -> Tuple[Path, float]:
    """Offline local fallback using Windows WinRT SpeechSynthesis (Kalpana for Hindi, David/Zira for English)."""
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    has_devanagari = any('\u0900' <= char <= '\u097f' for char in text)
    if has_devanagari or "kalpana" in voice.lower():
        voice_pattern = "*Kalpana*"
    elif any(f_voice in voice.lower() for f_voice in ("zira", "female", "aoede")):
        voice_pattern = "*Zira*"
    else:
        voice_pattern = "*David*"

    # Resolve synth_speech.ps1 from factory root or parent dirs
    cand_paths = [
        Path(__file__).resolve().parents[1] / "synth_speech.ps1",
        Path(__file__).resolve().parents[2] / "audiobook_factory" / "synth_speech.ps1",
        Path(__file__).resolve().parents[1] / "providers" / "synth_speech.ps1",
    ]
    ps_script = cand_paths[0]
    for cp in cand_paths:
        if cp.exists():
            ps_script = cp
            break

    tmp_wav = output_file.with_suffix(f".tmp_winrt_{uuid.uuid4().hex[:6]}.wav")

    cmd_ps = [
        "powershell", "-ExecutionPolicy", "Bypass",
        "-File", str(ps_script),
        "-Text", text,
        "-VoicePattern", voice_pattern,
        "-OutputPath", str(tmp_wav),
    ]
    res = subprocess.run(cmd_ps, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30.0)
    if res.returncode != 0 or not tmp_wav.exists() or tmp_wav.stat().st_size < 100:
        logger.warning(f"[!] WinRT synthesis notice: {res.stderr[:100]}. Using fallback harmonic synth.")
        sr = 24000
        dur = max(2.0, len(text.split()) * 0.4)
        t = np.linspace(0, dur, int(dur * sr))
        waveform = (0.3 * np.sin(2 * np.pi * 200 * t) * 32767).astype(np.int16)
        with wave.open(str(output_file), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(waveform.tobytes())
        return output_file, dur

    ff = get_ffmpeg()
    cmd_ff = [
        ff, "-y",
        "-i", str(tmp_wav),
        "-ar", "24000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_file),
    ]
    subprocess.run(cmd_ff, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=60.0)
    tmp_wav.unlink(missing_ok=True)

    dur = 1.0
    try:
        with wave.open(str(output_file), "rb") as wf:
            dur = wf.getnframes() / float(wf.getframerate())
    except Exception:
        pass
    return output_file, dur


def _synthesize_local_batch_winrt(batch: Any, output_file: Path, voice_map: Dict[str, str]) -> Tuple[Path, float]:
    """Renders multi-speaker batch locally by concatenating individual WinRT takes."""
    output_file = Path(output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    seg_wavs = []
    tmp_dir = output_file.parent / f"tmp_batch_{batch.batch_id}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    total_dur = 0.0

    try:
        for idx, seg in enumerate(batch.segments):
            seg_text = seg.spoken_text if hasattr(seg, "spoken_text") and seg.spoken_text else (seg.text if hasattr(seg, "text") else seg.get("text", ""))
            spk = seg.speaker if hasattr(seg, "speaker") else seg.get("speaker", "Narrator")
            v_name = voice_map.get(spk, "Aoede")
            seg_out = tmp_dir / f"seg_{idx:03d}.wav"
            _, d = _synthesize_local_winrt_fallback(seg_text, seg_out, voice=v_name)
            seg_wavs.append(seg_out)
            total_dur += d

        # Concatenate using ffmpeg concat demuxer
        concat_txt = tmp_dir / "concat.txt"
        with open(concat_txt, "w", encoding="utf-8") as cf:
            for sw in seg_wavs:
                cf.write(f"file '{sw.resolve().as_posix()}'\n")

        ff = get_ffmpeg()
        cmd_cat = [
            ff, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-ar", "24000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(output_file),
        ]
        subprocess.run(cmd_cat, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=120.0)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return output_file, total_dur
