#!/usr/bin/env python3
"""
Custom Dialogue Processor:
Reads user-provided dialogues from audiobooks/inputs/lets try.txt,
formats for TTS using the persistent key pool & Gemini text model,
synthesizes speech with BLOCK_NONE safetySettings via Gemini 3.1 Flash TTS,
and masters the final cinematic audio into audiobooks/output/.
"""

import os
import sys
import json
import wave
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.script_builder import build_dramatized_script_llm, build_narrator_script
from audiobook_factory.tts_dispatcher import synthesize_gemini_tts
from audiobook_factory.mastering import concatenate_and_master_chapter


def process_custom_dialogues():
    input_file = REPO_ROOT / "audiobooks" / "inputs" / "lets try.txt"
    output_dir = REPO_ROOT / "audiobooks" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_audio_dir = output_dir / "lets_try_chunks"
    temp_audio_dir.mkdir(parents=True, exist_ok=True)

    if not input_file.exists():
        logger.error(f"[!] Input file not found: {input_file}")
        return False

    print(f"[*] Reading user dialogues from: {input_file}")
    text_content = input_file.read_text(encoding="utf-8").strip()
    if not text_content:
        logger.error("[!] Input file is empty.")
        return False

    print(f"[*] Total input characters: {len(text_content)}")

    # 1. Format text into Screenplay Segments via Gemini Text Model
    print("[*] Formatting dialogues into TTS screenplay segments using persistent key pool...")
    os.environ["GEMINI_TEXT_MODEL"] = "gemini-flash-latest"
    
    script_segments = build_dramatized_script_llm(
        chapter_text=text_content,
        is_hindi=True,
    )

    if not script_segments:
        print("[!] LLM script formatting fallback to structured narrator chunks.")
        script_segments = build_narrator_script(text_content, is_hindi=True)

    script_path = output_dir / "lets_try_script.json"
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script_segments, f, ensure_ascii=False, indent=2)
    print(f"[+] Screenplay saved to: {script_path} ({len(script_segments)} segments)")

    # 2. Synthesize each segment via Gemini 3.1 Flash TTS
    print(f"[*] Synthesizing {len(script_segments)} speech segments with Gemini 3.1 Flash TTS (BLOCK_NONE)...")
    audio_paths = []
    
    # Speaker voice map
    voice_map = {
        "Narrator": "Aoede",
        "Male": "Charon",
        "He": "Charon",
        "Female": "Kore",
        "She": "Kore",
    }

    for idx, seg in enumerate(script_segments, 1):
        seg_text = seg.get("text", "").strip()
        speaker = seg.get("speaker", "Narrator")
        emotion = seg.get("emotion", "intimate")

        # Pick appropriate voice
        voice = voice_map.get(speaker)
        if not voice:
            # Check gender or fallback
            voice = "Kore" if any(w in speaker.lower() for w in ["she", "female", "woman", "girl", "ladki"]) else "Charon" if speaker != "Narrator" else "Aoede"

        out_wav = temp_audio_dir / f"seg_{idx:03d}_{voice}.wav"
        print(f"    [{idx}/{len(script_segments)}] Speaker: {speaker} | Voice: {voice} | Emotion: {emotion}")
        
        try:
            out_file, dur = synthesize_gemini_tts(
                text=seg_text,
                output_file=out_wav,
                voice=voice,
                emotion=emotion,
            )
            audio_paths.append(out_file)
            print(f"         [OK] Generated {dur:.2f}s -> {out_file.name}")
        except Exception as e:
            print(f"         [!] Synthesis error on segment {idx}: {e}")
            # If segment had tags that failed, try without bracket tags
            import re
            cleaned_text = re.sub(r"\[.*?\]", "", seg_text).strip()
            if cleaned_text and cleaned_text != seg_text:
                print(f"         [*] Retrying without inline tags...")
                out_file, dur = synthesize_gemini_tts(
                    text=cleaned_text,
                    output_file=out_wav,
                    voice=voice,
                    emotion=emotion,
                )
                audio_paths.append(out_file)
                print(f"         [OK] Retry generated {dur:.2f}s -> {out_file.name}")
            else:
                raise

    if not audio_paths:
        logger.error("[!] No audio segments generated.")
        return False

    # 3. Concatenate and Master Final Audio
    print(f"[*] Concatenating and mastering {len(audio_paths)} segments into final audio...")
    master_wav = output_dir / "lets_try_master.wav"
    master_m4a = output_dir / "lets_try_master.m4a"

    concatenate_and_master_chapter(
        audio_segments=audio_paths,
        output_chapter_file=master_wav,
        script_segments=script_segments,
        loudnorm=True,
        target_lufs=-19.0,
        true_peak_db=-1.5,
    )
    print(f"[+] Master WAV compiled: {master_wav} ({master_wav.stat().st_size:,} bytes)")

    concatenate_and_master_chapter(
        audio_segments=audio_paths,
        output_chapter_file=master_m4a,
        script_segments=script_segments,
        loudnorm=True,
        target_lufs=-19.0,
        true_peak_db=-1.5,
    )
    print(f"[+] Master M4A compiled: {master_m4a} ({master_m4a.stat().st_size:,} bytes)")

    print("\n[SUCCESS] Custom dialogue processing complete!")
    print(f"Script : {script_path}")
    print(f"Master : {master_m4a}")
    return True


if __name__ == "__main__":
    process_custom_dialogues()
