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
from typing import Dict, Any, List, Optional


DEFAULT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3-flash-preview")


from audiobook_factory.tts_dispatcher import global_key_pool


def get_api_key() -> str:
    return global_key_pool.get_key()


def call_gemini(prompt: str, system_instruction: str = "", model: str = DEFAULT_MODEL, json_mode: bool = False, max_retries: int = 4) -> str:
    """Send request to Gemini API with automatic key rotation, retry and model fallback."""
    candidate_models = [model]
    for m in ("gemini-3-flash-preview", "gemini-3.1-flash-lite-preview", "gemini-flash-latest"):
        if m not in candidate_models:
            candidate_models.append(m)

    last_error = None

    for curr_model in candidate_models:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        data = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries):
            api_key = get_api_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{curr_model}:generateContent?key={api_key}"

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": api_key,
                    "User-Agent": "AudiobookFactory/1.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    candidates = res_data.get("candidates", [])
                    if not candidates:
                        prompt_fb = res_data.get("promptFeedback", {})
                        raise RuntimeError(f"Gemini API returned no candidates: {prompt_fb}")
                    candidate = candidates[0]
                    if candidate.get("finishReason") == "MAX_TOKENS":
                        raise RuntimeError("Gemini API output truncated: finishReason is MAX_TOKENS.")
                    parts = candidate.get("content", {}).get("parts", [])
                    if not parts or "text" not in parts[0]:
                        raise RuntimeError(f"Candidate has no text parts (finishReason: {candidate.get('finishReason')})")
                    return parts[0]["text"]
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {e.code}: {err_msg}"
                if e.code in (503, 500, 429) and attempt < max_retries - 1:
                    wait_sec = 4.0 * (attempt + 1)
                    print(f"    [WAIT] Gemini API HTTP {e.code}. Cooling off {wait_sec:.1f}s before retry...", flush=True)
                    time.sleep(wait_sec)
                    continue
                break
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    wait_sec = 5.0 * (attempt + 1)
                    print(f"    [WAIT] Network hiccup ({e}). Retrying in {wait_sec:.1f}s (Attempt {attempt+1}/{max_retries})...", flush=True)
                    time.sleep(wait_sec)
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


def _translate_single_block(
    text_block: str,
    glossary: Dict[str, Any],
    block_title: str = "",
    preceding_context: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    system_prompt = (
        "You are a master literary translator and audiobook director. "
        "Translate the following English novel passage into high-quality, dramatic, natural spoken Hindustani (Hindi in Devanagari script). "
        "Strict Translation Invariants:\n"
        "1. Never do literal word-for-word translation. Translate sense-for-sense, preserving drama, subtext, humor, and emotional depth.\n"
        "2. The text will be read aloud by professional voice actors. Use flowing, cinematic Hindustani rather than overly stiff, textbook Sanskritized Hindi.\n"
        "3. Strictly adhere to the provided Character Glossary for proper noun spellings and honorific dynamics ('Aap' vs 'Tum' vs 'Tu').\n"
        "4. Preserve Markdown formatting: Keep headings and dialogue quotation marks intact.\n"
        "5. Output ONLY the translated passage in Devanagari Markdown without any meta-commentary, notes, or introductions."
    )

    glossary_str = json.dumps(glossary, ensure_ascii=False, indent=2)

    prompt = f"""### PERSISTENT TRANSLATION GLOSSARY:
{glossary_str}

### PRECEDING STORY CONTEXT:
{preceding_context if preceding_context else "Beginning of novel."}

### ENGLISH TEXT TO TRANSLATE ({block_title}):
\"\"\"
{text_block}
\"\"\"
"""
    raw = call_gemini(prompt, system_instruction=system_prompt, model=model, json_mode=False).strip()
    from audiobook_factory.sanitizer import validate_and_sanitize_translation
    is_valid, cleaned, reason = validate_and_sanitize_translation(raw, is_hindi=True)
    if not is_valid:
        raise RuntimeError(f"Translation guardrail triggered for {block_title}: {reason}")
    return cleaned


def translate_chapter(
    chapter_text: str,
    glossary: Dict[str, Any],
    chapter_title: str = "",
    preceding_context: str = "",
    model: str = DEFAULT_MODEL,
    project_dir: Optional[Path] = None,
) -> str:
    """Pass 2: Sense-for-sense literary translation of a single chapter into spoken Hindustani."""
    from audiobook_factory.sanitizer import validate_and_sanitize_translation
    cache_dir = None
    if project_dir:
        cache_dir = Path(project_dir) / "translation" / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

    words = chapter_text.split()
    # Chapters under 2,200 words fit comfortably within the 8,192 token limit
    if len(words) <= 2200:
        cache_file = (cache_dir / f"{chapter_title}_full.txt") if cache_dir and chapter_title else None
        if cache_file and cache_file.exists() and cache_file.stat().st_size > 10:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_text = f.read().strip()
            is_valid, cleaned_cached, err = validate_and_sanitize_translation(cached_text, is_hindi=True)
            if is_valid:
                print(f"    [CACHED] Chapter loaded from cache ({len(cleaned_cached)} chars).", flush=True)
                return cleaned_cached
            else:
                print(f"    [INVALID CACHE] Cache failed guardrail ({err}). Re-translating...", flush=True)

        res = _translate_single_block(chapter_text, glossary, chapter_title, preceding_context, model)
        if cache_file:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(res)
        return res

    # For long chapters, split across paragraph boundaries to avoid hitting MAX_TOKENS
    paragraphs = chapter_text.split("\n\n")
    chunks: List[str] = []
    curr_chunk: List[str] = []
    curr_words = 0

    for p in paragraphs:
        p_words = len(p.split())
        if curr_words + p_words > 1800 and curr_chunk:
            chunks.append("\n\n".join(curr_chunk))
            curr_chunk = [p]
            curr_words = p_words
        else:
            curr_chunk.append(p)
            curr_words += p_words
    if curr_chunk:
        chunks.append("\n\n".join(curr_chunk))

    translated_pieces: List[str] = []
    rolling_ctx = preceding_context
    for i, chunk in enumerate(chunks, 1):
        chunk_words = len(chunk.split())
        cache_file = (cache_dir / f"{chapter_title}_part_{i}.txt") if cache_dir and chapter_title else None
        if cache_file and cache_file.exists() and cache_file.stat().st_size > 10:
            with open(cache_file, "r", encoding="utf-8") as f:
                trans_part = f.read().strip()
            is_valid, cleaned_part, err = validate_and_sanitize_translation(trans_part, is_hindi=True)
            if is_valid:
                translated_pieces.append(cleaned_part)
                rolling_ctx = cleaned_part[-500:]
                print(f"    [CACHED] [Part {i}/{len(chunks)}] Loaded from cache ({len(cleaned_part)} chars).", flush=True)
                continue
            else:
                print(f"    [INVALID CACHE] [Part {i}/{len(chunks)}] Cache failed guardrail ({err}). Re-translating...", flush=True)

        print(f"    -> [Part {i}/{len(chunks)}] Translating {chunk_words} words...", flush=True)
        chunk_title = f"{chapter_title} (Part {i}/{len(chunks)})" if chapter_title else f"Part {i}/{len(chunks)}"
        trans_part = _translate_single_block(chunk, glossary, chunk_title, rolling_ctx, model)
        if cache_file:
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(trans_part)
        translated_pieces.append(trans_part)
        rolling_ctx = trans_part[-500:]
        print(f"    [OK] [Part {i}/{len(chunks)}] Done ({len(trans_part)} chars).", flush=True)

    return "\n\n".join(translated_pieces)


def translate_book_project(project_dir: Path, model: str = DEFAULT_MODEL) -> Path:
    """Batch translates all extracted chapters in a project into Hindi."""
    extracted_dir = project_dir / "extracted"
    if not extracted_dir.exists() and (project_dir / "chapters").exists():
        extracted_dir = project_dir / "chapters"
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
        print(f"[*] Loading existing translation glossary: {glossary_file}", flush=True)
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

        print("[*] Generating Pass-1 Character & Honorifics Glossary via Gemini...", flush=True)
        glossary = generate_book_glossary(first_chap_text, meta)
        with open(glossary_file, "w", encoding="utf-8") as f:
            json.dump(glossary, f, ensure_ascii=False, indent=2)
        print(f"[+] Saved glossary with {len(glossary.get('characters', []))} characters -> {glossary_file}", flush=True)

    # Step 2: Translate chapters in order
    chapter_files = sorted(extracted_dir.glob("chapter_*.md"))
    total = len(chapter_files)
    print(f"[*] Starting literary translation of {total} chapters using {model}...", flush=True)

    preceding_summary = f"Novel title: {meta.get('title')}. Setting out on journey."

    for idx, chap_file in enumerate(chapter_files, 1):
        target_file = trans_dir / f"{chap_file.stem}_hi.md"
        if target_file.exists() and target_file.stat().st_size > 100:
            print(f"[-] Chapter {idx}/{total} already translated: {target_file.name} (Skipping)", flush=True)
            continue

        with open(chap_file, "r", encoding="utf-8") as f:
            content = f.read()
        word_count = len(content.split())

        print(f"[*] [{idx}/{total}] Translating {chap_file.name} ({word_count} words)...", flush=True)

        trans_content = translate_chapter(
            chapter_text=content,
            glossary=glossary,
            chapter_title=chap_file.stem,
            preceding_context=preceding_summary,
            model=model,
            project_dir=project_dir,
        )

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(trans_content + "\n")

        print(f"[+] [{idx}/{total}] Successfully translated -> {target_file.name}", flush=True)
        time.sleep(2.0)

    print(f"[DONE] All chapters translated into Hindi successfully -> {trans_dir}")
    return trans_dir
