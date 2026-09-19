#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 2: Literary English-to-Hindi Translation Engine.
Translates English novels into dramatic, spoken Hindustani suitable for audiobooks.
Features Two-Pass Glossary Memory for character names, tone, and honorific consistency (Aap/Tum/Tu).
"""

import os
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List


DEFAULT_MODEL = "gemini-2.5-flash"


def get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")
    return key


def call_gemini(prompt: str, system_instruction: str = "", model: str = DEFAULT_MODEL, json_mode: bool = False, max_retries: int = 3) -> str:
    """Send request to Gemini API with automatic retry and model fallback."""
    api_key = get_api_key()
    candidate_models = [model]
    if model != "gemini-2.5-flash":
        candidate_models.append("gemini-2.5-flash")

    last_error = None

    for curr_model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{curr_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        data = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries):
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "AudiobookFactory/1.0"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    return res_data["candidates"][0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {e.code}: {err_msg}"
                if e.code in (503, 500, 429) and attempt < max_retries - 1:
                    time.sleep(3.0 * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    time.sleep(2.0)
                    continue
                break

    raise RuntimeError(f"Gemini API request failed on {candidate_models}: {last_error}")


def generate_book_glossary(sample_chapter_text: str, book_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Pass 1: Extract character names, Hindi spellings, honorific relationships, and terms."""
    system_prompt = (
        "You are an expert literary translation director for audiobooks. "
        "Analyze this opening book passage and output a comprehensive JSON glossary for English-to-Hindi translation."
    )

    prompt = f"""Book Title: {book_metadata.get('title', 'Unknown')}
Author: {book_metadata.get('author', 'Unknown')}

Sample Chapter Text:
\"\"\"
{sample_chapter_text[:6000]}
\"\"\"

Produce a JSON object with:
1. "characters": List of objects with:
   - "english_name": string
   - "hindi_name": Devanagari spelling (e.g. "हैरी पॉटर")
   - "gender": "male" | "female" | "other"
   - "voice_style": brief description of speech tone (e.g. "gruff, calm, authoritative")
   - "recommended_pronoun_level": default how others address them ("aap", "tum", or "tu")
2. "relationships": List of pairs describing who addresses whom as "aap", "tum", or "tu".
3. "locations_and_terms": Map of English terms to their consistent Hindi Devanagari or translated equivalent.
4. "general_tone": Description of narrative tone (e.g. "dark fantasy, dramatic, contemporary Hindustani").
"""

    response_text = call_gemini(prompt, system_instruction=system_prompt, json_mode=True)
    try:
        glossary = json.loads(response_text)
    except Exception:
        glossary = {
            "characters": [],
            "relationships": [],
            "locations_and_terms": {},
            "general_tone": "Cinematic Hindustani",
        }
    return glossary


def translate_chapter(
    chapter_text: str,
    glossary: Dict[str, Any],
    chapter_title: str = "",
    preceding_context: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    """Pass 2: Sense-for-sense literary translation of a single chapter into spoken Hindustani."""
    system_prompt = (
        "You are a master literary translator and audiobook director. "
        "Translate the following English novel chapter into high-quality, dramatic, natural spoken Hindustani (Hindi in Devanagari script). "
        "Strict Translation Invariants:\n"
        "1. Never do literal word-for-word translation. Translate sense-for-sense, preserving drama, subtext, humor, and emotional depth.\n"
        "2. The text will be read aloud by professional voice actors. Use flowing, cinematic Hindustani rather than overly stiff, textbook Sanskritized Hindi.\n"
        "3. Strictly adhere to the provided Character Glossary for proper noun spellings and honorific dynamics ('Aap' vs 'Tum' vs 'Tu').\n"
        "4. Preserve Markdown formatting: Keep '# Chapter ...' header intact, use dialogue quotation marks properly.\n"
        "5. Output ONLY the translated chapter in Devanagari Markdown without any meta-commentary, notes, or introductions."
    )

    glossary_str = json.dumps(glossary, ensure_ascii=False, indent=2)

    prompt = f"""### PERSISTENT TRANSLATION GLOSSARY:
{glossary_str}

### PRECEDING STORY CONTEXT:
{preceding_context if preceding_context else "Beginning of novel."}

### ENGLISH CHAPTER TO TRANSLATE ({chapter_title}):
\"\"\"
{chapter_text}
\"\"\"
"""

    return call_gemini(prompt, system_instruction=system_prompt, model=model, json_mode=False).strip()


def translate_book_project(project_dir: Path, model: str = DEFAULT_MODEL) -> Path:
    """Batch translates all extracted chapters in a project into Hindi."""
    project_dir = Path(project_dir).resolve()
    extracted_dir = project_dir / "extracted"
    meta_file = project_dir / "metadata.json"

    if not extracted_dir.exists() or not meta_file.exists():
        raise FileNotFoundError(f"Project not found or unextracted: {project_dir}")

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    trans_dir = project_dir / "translation"
    trans_dir.mkdir(parents=True, exist_ok=True)
    glossary_file = trans_dir / "glossary.json"

    # Step 1: Load or generate glossary
    if glossary_file.exists():
        print(f"[*] Loading existing translation glossary: {glossary_file}")
        with open(glossary_file, "r", encoding="utf-8") as f:
            glossary = json.load(f)
    else:
        first_chap_file = extracted_dir / "chapter_001.md"
        if not first_chap_file.exists():
            chap_files = sorted(extracted_dir.glob("*.md"))
            if not chap_files:
                raise FileNotFoundError("No chapter markdown files found in extracted directory.")
            first_chap_file = chap_files[0]

        with open(first_chap_file, "r", encoding="utf-8") as f:
            first_chap_text = f.read()

        print("[*] Generating Pass-1 Character & Honorifics Glossary via Gemini...")
        glossary = generate_book_glossary(first_chap_text, meta)
        with open(glossary_file, "w", encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        print(f"[+] Saved glossary with {len(glossary.get('characters', []))} characters -> {glossary_file}")

    # Step 2: Translate chapters in order
    chapter_files = sorted(extracted_dir.glob("chapter_*.md"))
    total = len(chapter_files)
    print(f"[*] Starting literary translation of {total} chapters using {model}...")

    preceding_summary = f"Novel title: {meta.get('title')}. Setting out on journey."

    for idx, chap_file in enumerate(chapter_files, 1):
        target_file = trans_dir / f"{chap_file.stem}_hi.md"
        if target_file.exists() and target_file.stat().st_size > 100:
            print(f"[-] Chapter {idx}/{total} already translated: {target_file.name} (Skipping)")
            continue

        print(f"[*] Translating Chapter {idx}/{total}: {chap_file.name}...")
        with open(chap_file, "r", encoding="utf-8") as f:
            content = f.read()

        trans_content = translate_chapter(
            chapter_text=content,
            glossary=glossary,
            chapter_title=chap_file.stem,
            preceding_context=preceding_summary,
            model=model,
        )

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(trans_content + "\n")

        print(f"[+] Translated Chapter {idx}/{total} -> {target_file.name}")
        # Gentle pacing to respect rate limits (15 RPM)
        time.sleep(4.5)

    print(f"[DONE] All chapters translated into Hindi successfully -> {trans_dir}")
    return trans_dir
