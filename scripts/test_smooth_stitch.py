import wave
import json
from pathlib import Path
import numpy as np

def stitch_dialogue_track_smooth(
    ledger_path: Path,
    chunks_dir: Path,
    output_wav_path: Path,
    sample_rate: int = 48000,
    fade_in_ms: float = 10.0,
    fade_out_ms: float = 15.0,
) -> Path:
    """
    Stitches speech chunks into a sample-accurate vocal master track (chapter_xxx_dialogue.wav)
    applying raised-cosine (Hann) micro-fades at every chunk boundary to ELIMINATE:
    1. Digital step discontinuities (clicks/pops / 'htt ftt').
    2. DC bias offset pops.
    3. Abrupt noise-floor gating ('hiss' cutting in/out violently).
    """
    import subprocess
    import shutil

    with open(ledger_path, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    segments = ledger.get("segments", [])
    output_wav_path = Path(output_wav_path).resolve()
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = output_wav_path.with_suffix(".tmp_smooth.wav")

    # Number of samples for micro fades at target sample rate
    fade_in_samples = int(sample_rate * (fade_in_ms / 1000.0))
    fade_out_samples = int(sample_rate * (fade_out_ms / 1000.0))

    # Pre-calculate Hann fade curves (raised cosine for organic acoustic taper)
    fade_in_curve = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_in_samples)))
    fade_out_curve = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, fade_out_samples)))

    all_frames = []

    for i, seg in enumerate(segments):
        audio_file = seg.get("audio_file", "")
        chunk_path = chunks_dir / audio_file
        if not chunk_path.exists():
            parts = audio_file.split("_")
            if len(parts) >= 2:
                matches = list(chunks_dir.glob(f"{parts[0]}_{parts[1]}_*.wav"))
                if matches:
                    chunk_path = matches[0]
                else:
                    raise FileNotFoundError(f"Chunk not found: {chunk_path}")
            else:
                raise FileNotFoundError(f"Chunk not found: {chunk_path}")

        # Read and resample to 48000Hz mono 16-bit PCM via FFmpeg
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(chunk_path),
            "-ar", str(sample_rate),
            "-ac", "1",
            "-f", "s16le",
            "-"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        raw_pcm = proc.stdout

        # Convert to numpy float32 for high-precision DSP
        samples = np.frombuffer(raw_pcm, dtype=np.int16).astype(np.float32)

        # 1. Remove DC bias offset
        dc_bias = np.mean(samples)
        samples = samples - dc_bias

        # 2. Apply micro-fade in
        if len(samples) > fade_in_samples:
            samples[:fade_in_samples] *= fade_in_curve
        else:
            n = len(samples)
            samples *= (0.5 * (1.0 - np.cos(np.linspace(0, np.pi, n))))

        # 3. Apply micro-fade out
        if len(samples) > fade_out_samples:
            samples[-fade_out_samples:] *= fade_out_curve
        else:
            n = len(samples)
            samples *= (0.5 * (1.0 + np.cos(np.linspace(0, np.pi, n))))

        # Force exact zero at boundary endpoints
        samples[0] = 0.0
        samples[-1] = 0.0

        # Convert back to int16
        processed_int16 = np.clip(np.round(samples), -32768, 32767).astype(np.int16)
        all_frames.append(processed_int16.tobytes())

        # 4. Add silence padding if not last segment
        pause_after_ms = int(seg.get("pause_after_ms", 400))
        if i < len(segments) - 1 and pause_after_ms > 0:
            silence_samples = int(sample_rate * (pause_after_ms / 1000.0))
            # Clean digital zero silence (endpoints are already at 0.0, so 0 step discontinuity!)
            silence_bytes = b"\x00\x00" * silence_samples
            all_frames.append(silence_bytes)

    with wave.open(str(tmp_out), "wb") as out_wf:
        out_wf.setnchannels(1)
        out_wf.setsampwidth(2)
        out_wf.setframerate(sample_rate)
        out_wf.writeframes(b"".join(all_frames))

    shutil.move(str(tmp_out), str(output_wav_path))
    print(f"[OK] Stitched smooth vocal track: {output_wav_path.name}")
    return output_wav_path

if __name__ == "__main__":
    ledger_path = Path("audiobooks/projects/witcher1/scripts/chapter_011_timeline_ledger.json")
    chunks_dir = Path("audiobooks/projects/witcher1/audio_chunks")
    out_wav = Path("audiobooks/projects/witcher1/mastered/chapter_011_dialogue_smooth.wav")
    stitch_dialogue_track_smooth(ledger_path, chunks_dir, out_wav)

    # Measure discontinuity on the smooth file
    with wave.open(str(out_wav), "rb") as wf:
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        print(f"Smooth Master: {framerate}Hz, {nframes} frames, {nframes/framerate:.2f}s")
        # Check first segment boundary
        with open(ledger_path, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        seg1 = ledger["segments"][0]
        # Calculate seg1 samples at 48000
        p1 = list(chunks_dir.glob(f"c011_s0001_*.wav"))[0]
        with wave.open(str(p1), "rb") as wf1:
            seg1_samples = int(wf1.getnframes() * (framerate / wf1.getframerate()))

        wf.setpos(max(0, seg1_samples - 10))
        data = np.frombuffer(wf.readframes(20), dtype=np.int16)
        print("Last 10 samples of Seg 1:", data[:10])
        print("First 10 samples of Silence:", data[10:20])
        step = abs(int(data[10]) - int(data[9]))
        print(f"New Discontinuity step size: {step} samples ({step/32768*100:.4f}%) - TARGET: 0.0000%!")
