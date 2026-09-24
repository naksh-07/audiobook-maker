#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 11 Hindi Translation Runner (New Updated Standards).
Strict Unfiltered Literary Hindustani Translation of Andrzej Sapkowski's 'The Voice of Reason 6'.
Adheres strictly to:
- ADR-023: Dynamic Literary Advisory Lexicon DB & Register Quality Guard
- ADR-015: Unfiltered Desi Tavern Grit & Wasseypur/Manto Texture
- ADR-019: Somatic Realism & 19-to-21 Amplification
- ADR-021: Character Voice Consistency & Zero English Parenthetical Leakage
"""

import os
import sys
import re
import json
import time
import shutil
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

# Ensure UTF-8 I/O for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import urllib.request
import urllib.error

from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers
from audiobook_factory.translator import (
    normalize_translated_lexicon,
    GeminiPayloadError,
)
from audiobook_factory.sanitizer import (
    validate_and_sanitize_translation,
    audit_literary_register,
)
from audiobook_factory.advisory_lexicon import get_advisory_db

pool = get_persistent_key_pool()


def call_gemini_resilient(
    prompt: str,
    system_instruction: str = "",
    model: str = "gemini-3.8-flash",
    max_retries: int = 4,
) -> str:
    candidate_models = [model, "gemini-3.7-flash", "gemini-flash-latest", "gemini-3.1-flash-lite"]
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
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        data = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries):
            api_key = pool.get_key(service="text")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{curr_model}:generateContent?key={api_key}"
            headers = get_stealth_sdk_headers(api_key)
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    candidates = res_data.get("candidates", [])
                    if not candidates:
                        raise GeminiPayloadError(f"No candidates returned: {res_data.get('promptFeedback', {})}")
                    candidate = candidates[0]
                    parts = candidate.get("content", {}).get("parts", [])
                    if not parts or "text" not in parts[0]:
                        raise GeminiPayloadError("Candidate missing text parts")
                    return parts[0]["text"]
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8", errors="ignore")
                last_error = f"HTTP {e.code}: {err_msg}"
                if e.code in (429, 503, 500):
                    pool.mark_temporary_backoff(api_key, 10.0, f"HTTP {e.code}")
                    if e.code == 503 and attempt >= 1:
                        print(f"    [MODEL OVERLOAD] {curr_model} overloaded (503). Trying fallback candidate...", flush=True)
                        break
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_error = str(e)
                time.sleep(1.5)
                continue

    raise RuntimeError(f"Gemini API request failed on all candidate models: {last_error}")


def build_system_prompt() -> str:
    advisory_guidance = get_advisory_db().get_formatted_prompt_guidelines()

    return f"""You are a master literary translator and audio drama director adapting the mature, grimdark fantasy 
and adult literature (in the unapologetic tradition of Andrzej Sapkowski, George R.R. Martin, Anurag Kashyap, and Saadat Hasan Manto) 
into cinematic, spoken Hindustani (Hindi in Devanagari script) for a premier audio drama.

{advisory_guidance}

STRICT TRANSLATION INVARIANTS & PRODUCTION STANDARDS:
1. LITERARY ANTI-BOWDLERIZATION MANDATE: NEVER sanitize, soften, or bowdlerize raw dialogue, sexual humor, intimate 
   bodily descriptions, crude tavern banter, or gritty curses. The original European text is gritty adult literature—NOT a censored 
   children's cartoon.
2. THE 70/30 ANTI-PARODY INVARIANT: Maintain a strict 70% Canon Sacredness / 30% Sensory Desi Amplification ratio. 
   Never replace European dark-fantasy lore, proper nouns, or monster classifications with Indian mythology or tapori spoofs.
   - Temple of Melitele: 'मेलिटेले का मंदिर', 'माँ नेनेके' (Mother Nenneke).
   - Currency & Geography: 'तेमेरियन ओरेन' (Temerian orens), 'विज़िमा' (Wyzim), 'नोविग्राड के क्राउन' (Novigrad crowns), 
     'महाकाम की खदानें' (Mahakam mines), 'बौने' (dwarves).
   - Flora & Herbs: Translate exotic herbal names into vivid, grounded medieval fantasy descriptions without Latin bracketed junk.
     - Melilote -> 'तारों जैसी पत्तियों वाली मेलिलोट'
     - Arenaria -> 'सुर्ख लाल बेरियों वाली एरेनेरिया'
     - Scarix -> 'स्कारिक्स की जड़'
     - Crystal roof -> 'बिल्लौर (स्फटिक) की पारदर्शी छत' (DO NOT write English '(crystal)').
     - Agate -> 'अकीक', Nephrite -> 'नेफ्राइट (यशब)', Ruby -> 'माणिक / लाल', Diamond -> 'हीरा'.
3. ZERO ENGLISH PARENTHETICAL LEAKAGE (CRITICAL FOR TTS): NEVER append English words in parentheses like '(crystal)', '(agate)', 
   '(nephrite)', '(striga)', or '(infertility)'. In an audiobook script, bracketed English ruins the speech synthesis. Use pure, evocative Hindustani.
4. PERIOD TAVERN GRIT & RAW PROFANITY (NEW LEVEL STANDARD):
   - Nenneke cuts through Geralt's bullshit: "I don't give a shit how she treated you" -> "मुझे रत्ती भर फ़र्क नहीं पड़ता कि उसने तुम्हारे साथ कैसा सुलूक किया, और इसकी तो मुझे ज़रा भी परवाह नहीं कि तुमने उसके साथ क्या किया!"
   - "Stop crying on my shoulder. I'm not your mother..." -> "मेरे कंधे पर सिर रखकर ये रोना-धोना बंद करो! मैं तुम्हारी माँ नहीं हूँ, और न ही तुम्हारी राज़दार बनने बैठी हूँ!"
   - "You're more of an idiot than I thought" -> "तुम मेरी सोच से भी बड़े बेवकूफ़ हो!"
   - "Bloody little" -> "खाक समझते हो तुम!"
5. CHARACTER DYNAMICS & INTIMACY FIDELITY:
   - Geralt and Nenneke: Nenneke speaks to Geralt with maternal authority, exasperated affection, blunt cynicism, and clinical precision ('तुम' / 'तू' with deep warmth and sharp tongue). Geralt speaks with defensive respect, vulnerable sincerity, and quiet raspy cynicism ('आप' or warm 'नेनेके').
   - Yennefer's Infertility: Treat the discussion of atrophied ovaries, futile treatments, and Geralt's guilt with raw emotional realism and adult biological frankness.
   - The Trance / Future: Geralt's fatalistic refusal to glimpse prophecy ("भविष्य जानकर मैं वो कैसे कर पाऊँगा जो मैं करता हूँ?").
   - The Crystal Roof Metaphor: The ecological tragedy of the dying sun and lethal rays, concluding with Nenneke's bone-chilling final line: "बहुत देर हो चुकी है।"
6. URDU KA TARKA ('Aate me Namak'): Infuse a calibrated 10-15% of atmospheric, noir, and poetic Urdu 
   ('गुफ़ा', 'उमस', 'जिस्म', 'हवस', 'अकीक', 'बिल्लौर', 'हसरत', 'सन्नाटा', 'ज़ख़्म', 'इल्हाम', 'विरासत', 'फ़ना', 'क़यामत', 'तावीज़') to give dark-fantasy philosophical weight.
7. SPOKEN DRAMATIC DIALOGUE: Punctuate for voice actors using ellipses ('...'), em-dashes ('—'), and expressive phrasing.
8. OUTPUT FORMAT: Output ONLY the translated chapter in Devanagari Markdown. NO preamble, NO translator notes, NO conversational intro/outro.
"""


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    extracted_file = project_dir / "extracted" / "chapter_011.md"
    translation_dir = project_dir / "translation"
    translation_file = translation_dir / "chapter_011_hi.md"
    backup_file = translation_dir / "chapter_011_hi.old.md"

    if not extracted_file.exists():
        raise FileNotFoundError(f"Source extracted file not found: {extracted_file}")

    # Backup legacy translation
    if translation_file.exists() and not backup_file.exists():
        shutil.copy2(translation_file, backup_file)
        print(f"[+] Backed up legacy translation to: {backup_file.name}")

    with open(extracted_file, "r", encoding="utf-8") as f:
        source_text = f.read()

    print(f"[*] Loaded source text: {extracted_file.name} ({len(source_text.split())} words)")

    # Split into 2 dramatic parts for high-fidelity translation
    paras = [p.strip() for p in source_text.split("\n\n") if p.strip()]
    header_lines = [p for p in paras if p.startswith("#")]
    body_paras = [p for p in paras if not p.startswith("#")]

    # Split body paras approximately at mid-point (around Geralt showing the jewels)
    mid_idx = len(body_paras) // 2
    # Find natural break near "Come here a minute, Nenneke"
    for idx, p in enumerate(body_paras):
        if "Come here a minute" in p or "unknotted a secret pocket" in p:
            mid_idx = idx
            break

    part1_text = "\n\n".join(body_paras[:mid_idx])
    part2_text = "\n\n".join(body_paras[mid_idx:])

    parts = [
        ("Part 1: The Grotto, Herbs & Yennefer's Quarrel", part1_text),
        ("Part 2: The Jewels, Infertility, The Trance & The Crystal Roof", part2_text),
    ]

    system_prompt = build_system_prompt()
    translated_sections = []

    print("\n" + "=" * 80)
    print("  STAGE 1: HIGH-FIDELITY LITERARY TRANSLATION (gemini-3.8-flash)")
    print("=" * 80)

    glossary_path = translation_dir / "glossary.json"
    glossary = {}
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)

    cache_dir = translation_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    prev_context = ""
    for idx, (title, chunk_txt) in enumerate(parts, 1):
        cache_file = cache_dir / f"chapter_011_part_{idx:02d}.txt"
        if cache_file.exists():
            print(f"[*] Restoring [{idx}/{len(parts)}] {title} from cache...")
            with open(cache_file, "r", encoding="utf-8") as f:
                clean_chunk = f.read()
            translated_sections.append(clean_chunk)
            prev_context = clean_chunk
            continue

        print(f"\n[*] Translating [{idx}/{len(parts)}] {title} ({len(chunk_txt.split())} words)...")
        prompt = f"""Translate the following section from Andrzej Sapkowski's 'The Witcher: The Last Wish' (Chapter 11: 'The Voice of Reason 6') into rich, cinematic spoken Hindustani in Devanagari script.

STRICT INVARIANTS:
- No English words in parentheses (eliminate '(crystal)', '(agate)', etc.).
- Maintain raw, gritty tavern/temple dialogue without censorship.
- Geralt (raspy, cynical, weary, addresses Nenneke with deep respect/vulnerability).
- Nenneke (sharp-tongued, matronly, scolding, clinical, warm under the surface).

{f'PREVIOUS CONTEXT:\n{prev_context[-800:]}\n\n' if prev_context else ''}
ENGLISH SOURCE TEXT TO TRANSLATE:
{chunk_txt}
"""
        t0 = time.time()
        translated_chunk = call_gemini_resilient(
            prompt=prompt,
            system_instruction=system_prompt,
            model="gemini-3.8-flash",
        )
        t_el = time.time() - t0
        print(f"[+] Translated in {t_el:.1f}s ({len(translated_chunk.split())} Devanagari words).")

        # Clean markdown code blocks if wrapped
        clean_chunk = translated_chunk.strip()
        if clean_chunk.startswith("```"):
            clean_chunk = re.sub(r"^```(?:markdown|md)?\n", "", clean_chunk)
            clean_chunk = re.sub(r"\n```$", "", clean_chunk)

        # Sanitize and normalize lexicon
        if glossary:
            clean_chunk = normalize_translated_lexicon(clean_chunk, glossary)
        is_valid, clean_chunk, reason = validate_and_sanitize_translation(clean_chunk, is_hindi=True)
        reg_valid, reg_cleaned, rep = audit_literary_register(clean_chunk)
        if rep:
            clean_chunk = reg_cleaned
        clean_chunk = re.sub(r"\s*\([A-Za-z\s]{2,25}\)", "", clean_chunk)

        # Save to cache
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(clean_chunk)

        translated_sections.append(clean_chunk)
        prev_context = clean_chunk

    full_translated_body = "\n\n".join(translated_sections)

    # Format chapter header
    final_output = f"# ६: तर्क की आवाज़\n\nतर्क की आवाज़\n\n{full_translated_body}\n"

    # Final register audit & parenthetical leak check
    print("\n[*] Running Quality & Register Audit...")
    is_clean, cleaned_text, warnings = audit_literary_register(final_output)
    if warnings:
        print(f"    [*] Auto-normalized {len(warnings)} register tokens: {warnings[:5]}")
    final_output = cleaned_text
    print(f"    Total words: {len(final_output.split())}")

    # Check for English parenthetical leaks
    english_leaks = re.findall(r'\([a-zA-Z\s]{2,}\)', final_output)
    if english_leaks:
        print(f"[!] Warning: English parenthetical leaks detected: {set(english_leaks)}")
        for leak in set(english_leaks):
            final_output = final_output.replace(leak, "")
        print("[+] Eradicated English parenthetical leaks.")
    else:
        print("[OK] Zero English parenthetical leaks detected!")

    with open(translation_file, "w", encoding="utf-8") as f:
        f.write(final_output)

    print(f"\n[OK] SOTA Hindustani Translation saved successfully: {translation_file.name}")


if __name__ == "__main__":
    main()
