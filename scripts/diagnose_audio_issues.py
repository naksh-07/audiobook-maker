import json
import wave
from pathlib import Path
import numpy as np

def analyze_audio():
    ledger_path = Path("audiobooks/projects/witcher1/scripts/chapter_011_timeline_ledger.json")
    dialogue_wav = Path("audiobooks/projects/witcher1/mastered/chapter_011_dialogue.wav")
    chunks_dir = Path("audiobooks/projects/witcher1/audio_chunks")

    with open(ledger_path, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    print("=== 1. RAW TTS CHUNKS BOUNDARY ANALYSIS ===")
    for i in range(1, 6):
        pattern = f"c011_s{i:04d}_*.wav"
        matches = list(chunks_dir.glob(pattern))
        if not matches:
            continue
        p = matches[0]
        with wave.open(str(p), "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            data = wf.readframes(nframes)
            samples = np.frombuffer(data, dtype=np.int16)

        # Check first and last 50ms
        sample_50ms = int(framerate * 0.05)
        start_samples = samples[:sample_50ms]
        end_samples = samples[-sample_50ms:]

        first_sample = samples[0]
        last_sample = samples[-1]
        start_max = np.max(np.abs(start_samples))
        end_max = np.max(np.abs(end_samples))
        overall_max = np.max(np.abs(samples))
        dc_mean = np.mean(samples)

        print(f"Chunk {i:02d} ({p.name}, {framerate}Hz, {nframes/framerate:.2f}s):")
        print(f"   First sample: {first_sample} | Last sample: {last_sample}")
        print(f"   Start 50ms Peak: {start_max} ({20*np.log10(max(1, start_max)/32768):.1f} dBFS)")
        print(f"   End 50ms Peak: {end_max} ({20*np.log10(max(1, end_max)/32768):.1f} dBFS)")
        print(f"   DC Offset Mean: {dc_mean:.2f}")

    print("\n=== 2. MASTER DIALOGUE WAV ANALYSIS ===")
    if dialogue_wav.exists():
        with wave.open(str(dialogue_wav), "rb") as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            dur = nframes / framerate
            print(f"Master Dialogue: {framerate}Hz, {nframes} frames, {dur:.2f}s")

            # Check boundary between segment 1 and 2 in dialogue.wav
            # From ledger:
            seg1 = ledger["segments"][0]
            seg2 = ledger["segments"][1]

            # In stitch_dialogue_track_from_ledger, segment 1 frames are written, then silence_samples
            # Let's inspect around the transition from seg 1 to silence, and silence to seg 2
            # Let's find seg 1 duration in frames
            p1 = list(chunks_dir.glob(f"c011_s0001_*.wav"))[0]
            with wave.open(str(p1), "rb") as wf1:
                seg1_frames = int(wf1.getnframes() * (framerate / wf1.getframerate()))
            pause1_samples = int(framerate * (seg1["pause_after_ms"] / 1000.0))

            # Read around the cut
            cut_pos = seg1_frames
            wf.setpos(max(0, cut_pos - 100))
            boundary_data = np.frombuffer(wf.readframes(200), dtype=np.int16)
            print(f"Transition Seg1 -> Silence (last 5 samples of Seg1 vs first 5 of silence):")
            print(f"   Before cut: {boundary_data[95:100]}")
            print(f"   After cut:  {boundary_data[100:105]}")
            step_size = abs(int(boundary_data[100]) - int(boundary_data[99]))
            print(f"   Discontinuity Step size: {step_size} samples ({step_size/32768*100:.2f}%)")

            # Transition from silence -> Seg2
            cut_pos2 = seg1_frames + pause1_samples
            wf.setpos(max(0, cut_pos2 - 100))
            boundary_data2 = np.frombuffer(wf.readframes(200), dtype=np.int16)
            print(f"Transition Silence -> Seg2 (last 5 samples of silence vs first 5 of Seg2):")
            print(f"   Before cut (silence): {boundary_data2[95:100]}")
            print(f"   After cut (Seg2):     {boundary_data2[100:105]}")
            step_size2 = abs(int(boundary_data2[100]) - int(boundary_data2[99]))
            print(f"   Discontinuity Step size: {step_size2} samples ({step_size2/32768*100:.2f}%)")

if __name__ == "__main__":
    analyze_audio()
