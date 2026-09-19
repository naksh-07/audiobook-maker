#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.1: Screenplay Script Builder & Speech Normalizer.
Converts raw novel prose (English or Hindi) into an annotated Screenplay Script JSON.
Handles dialogue vs. narration segmentation, text normalization, and pause timing.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any


def normalize_speech_text(text: str, is_hindi: bool = False) -> str:
    """Normalize symbols, abbreviations, and numbers for natural TTS reading."""
    if not text:
        return ""

    text = text.strip()

    # Universal symbol replacements
    symbols = {
        "&": " and " if not is_hindi else " और ",
        "%": " percent" if not is_hindi else " प्रतिशत",
        "$": " dollars " if not is_hindi else " डॉलर ",
        "₹": " rupees " if not is_hindi else " रुपये ",
        "@": " at ",
        "#": " number " if not is_hindi else " नंबर ",
        "+": " plus " if not is_hindi else " प्लस ",
        "=": " equals " if not is_hindi else " बराबर ",
    }
    for sym, word in symbols.items():
        text = text.replace(sym, word)

    if not is_hindi:
        # Common English honorifics and abbreviations
        abbrevs = {
            r"\bMr\.\s*": "Mister ",
            r"\bMrs\.\s*": "Missus ",
            r"\bMs\.\s*": "Miss ",
            r"\bDr\.\s*": "Doctor ",
            r"\bProf\.\s*": "Professor ",
            r"\bSt\.\s*": "Saint ",
            r"\bvs\.\s*": "versus ",
            r"\betc\.\s*": "et cetera ",
            r"\bi\.e\.\s*": "that is ",
            r"\be\.g\.\s*": "for example ",
        }
        for pat, repl in abbrevs.items():
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # Strip formatting artifacts
    text = re.sub(r"[\*\_~`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_narrator_script(chapter_text: str, is_hindi: bool = False) -> List[Dict[str, Any]]:
    """
    Standard Audiobook Mode: Groups text into optimal speech chunks (200 - 500 words).
    Maintains dramatic pauses at paragraph boundaries and scene breaks.
    """
    paragraphs = chapter_text.split("\n\n")
    script = []
    chunk_index = 1

    current_chunk = []
    current_words = 0

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        # Skip chapter headers like "# Chapter 1"
        if p.startswith("#"):
            header_text = p.lstrip("#").strip()
            script.append({
                "index": chunk_index,
                "type": "chapter_header",
                "speaker": "Narrator",
                "text": normalize_speech_text(header_text, is_hindi),
                "pause_after_ms": 1200,
            })
            chunk_index += 1
            continue

        # Scene breaks
        if p in ("---", "* * *", "***", "— — —"):
            if current_chunk:
                script.append({
                    "index": chunk_index,
                    "type": "narration",
                    "speaker": "Narrator",
                    "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
                    "pause_after_ms": 800,
                })
                chunk_index += 1
                current_chunk = []
                current_words = 0
            continue

        words = len(p.split())

        # If adding this paragraph exceeds ~350 words, flush the chunk
        if current_words + words > 350 and current_chunk:
            script.append({
                "index": chunk_index,
                "type": "narration",
                "speaker": "Narrator",
                "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
                "pause_after_ms": 600,
            })
            chunk_index += 1
            current_chunk = [p]
            current_words = words
        else:
            current_chunk.append(p)
            current_words += words

    if current_chunk:
        script.append({
            "index": chunk_index,
            "type": "narration",
            "speaker": "Narrator",
            "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
            "pause_after_ms": 1000,
        })

    return script


def build_dramatized_script_llm(chapter_text: str, is_hindi: bool = False) -> List[Dict[str, Any]]:
    """
    Dramatized Screenplay Mode: Uses Gemini JSON mode to extract dialogues and narration.
    """
    import os
    import urllib.request

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # Fallback to standard narrator mode if no API key
        return build_narrator_script(chapter_text, is_hindi)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"

    sys_prompt = (
        "You are an expert audio drama director. Convert this book chapter into an annotated screenplay JSON script. "
        "Split into narration segments and character dialogue segments. Attribute each dialogue to the correct character."
    )

    prompt = f"""Language: {"Hindi (Devanagari)" if is_hindi else "English"}
Text:
\"\"\"
{chapter_text[:8000]}
\"\"\"

Output JSON: A list of objects where each object has:
- "index": int
- "type": "narration" | "dialogue"
- "speaker": character name or "Narrator"
- "text": speech text (cleaned of redundant 'he said' dialogue tags when spoken by the character)
- "emotion": "neutral" | "angry" | "whispering" | "sad" | "excited"
- "pause_after_ms": int (300 to 800)
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": sys_prompt}]},
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
            script = json.loads(raw_json)
            for item in script:
                item["text"] = normalize_speech_text(item.get("text", ""), is_hindi)
            return script
    except Exception:
        # Graceful fallback to narrator script on any error
        return build_narrator_script(chapter_text, is_hindi)


def generate_project_scripts(
    project_dir: Path,
    use_hindi: bool = False,
    dramatized: bool = False,
) -> Path:
    """Generates JSON screenplay scripts for all chapters in project."""
    project_dir = Path(project_dir).resolve()
    input_dir = project_dir / ("translation" if use_hindi else "extracted")
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    target_files = sorted(input_dir.glob("*.md"))
    if not target_files:
        raise FileNotFoundError(f"No markdown chapters found in {input_dir}")

    print(f"[*] Building audiobook scripts for {len(target_files)} chapters (Mode: {'Dramatized' if dramatized else 'Narrator'})...")

    for chap_file in target_files:
        script_file = scripts_dir / f"{chap_file.stem}_script.json"
        if script_file.exists() and script_file.stat().st_size > 50:
            print(f"[-] Script already exists: {script_file.name} (Skipping)")
            continue

        with open(chap_file, "r", encoding="utf-8") as f:
            content = f.read()

        if dramatized:
            script = build_dramatized_script_llm(content, is_hindi=use_hindi)
        else:
            script = build_narrator_script(content, is_hindi=use_hindi)

        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)

        print(f"[+] Built script for {chap_file.name} -> {len(script)} audio segments")

    print(f"[DONE] All chapter scripts built -> {scripts_dir}")
    return scripts_dir
