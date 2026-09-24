#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 12 Hindi Translation Runner (SOTA New Level Standards).
Strict Unfiltered Literary Hindustani Translation of Andrzej Sapkowski's 'The Last Wish' (आखिरी इच्छा).
Adheres strictly to:
- ADR-023: Dynamic Literary Advisory Lexicon DB & Register Quality Guard
- ADR-015: Unfiltered Desi Tavern Grit & Wasseypur/Manto Texture
- ADR-016: HBO/Netflix Grade Sensual & Intimate Scene Production Framework
- ADR-019: Somatic Realism & Gemini TTS Safety Filter Unlock (BLOCK_NONE)
- ADR-021: Character Voice Consistency & Zero English Parenthetical Leakage
"""

import os
import sys
import re
import json
import time
import shutil
import sqlite3
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


def reset_key_backoffs():
    """Unstick any temporary backoffs from previous runs."""
    db_file = ROOT_DIR / "audiobooks" / "key_pool_state.db"
    if db_file.exists():
        try:
            with sqlite3.connect(str(db_file)) as conn:
                c = conn.execute("UPDATE key_quota_ledger SET status = 'ACTIVE', backoff_until = NULL WHERE status = 'TEMP_BACKOFF';")
                conn.commit()
                if c.rowcount > 0:
                    print(f"[+] Restored {c.rowcount} temporarily backed-off API keys to ACTIVE.")
        except Exception as e:
            print(f"[!] Key ledger reset note: {e}")


def call_gemini_resilient(
    prompt: str,
    system_instruction: str = "",
    model: str = "gemini-3.5-flash-lite",
    max_retries: int = 300,
) -> str:
    candidate_models = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3-flash-preview"]

    last_error = None

    for curr_model in candidate_models:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 4096,
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
                    pool.mark_temporary_backoff(api_key, 20.0, f"HTTP {e.code}")
                    sleep_time = 15.0 if e.code == 429 else 6.0
                    print(f"    [PACING] HTTP {e.code} received. Cooling off {sleep_time:.1f}s for rate limit window...", flush=True)
                    time.sleep(sleep_time)
                    continue
                break
            except Exception as e:
                last_error = str(e)
                time.sleep(2.0)
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
   - Proper Nouns: 'गेराल्ट' (Geralt), 'डैंडेलियन' (Dandelion/Jaskier), 'येनेफ़र' (Yennefer), 'चिरेडन' (Chireadan), 'क्रेप' (Krepp), 
     'नेविल' (Neville), 'रिंडे' (Rinde), 'जिन्न' (Djinn / Genie).
   - Yennefer's Signature Scent: 'लिलाक और आंवले की खुशबू' (Lilac and gooseberries).
3. ZERO ENGLISH PARENTHETICAL LEAKAGE (CRITICAL FOR TTS): NEVER append English words in parentheses like '(djinn)', '(amphora)', 
   '(seal)', or '(portal)'. In an audiobook script, bracketed English ruins the speech synthesis. Use pure, evocative Hindustani.
4. PERIOD TAVERN GRIT & RAW PROFANITY (NEW LEVEL STANDARD):
   - Catfish banter: "You screwed up, my friend. You make as good a fisherman as a goat's arse makes a trumpet." -> 
     "तुमने सब गुड़-गोबर कर दिया, मेरे दोस्त। तुम उतने ही अच्छे मछुआरे हो जितनी अच्छी शहनाई एक बकरी की गांड बजा सकती है!"
   - Dandelion cursing: "Bloody hell! So much grub escaped! I hope you die, you son-of-a-catfish." -> 
     "सत्यानाश! इतना सारा खाना हाथ से निकल गया! तू डूब मरे, ओ मछली के पिल्ले!"
   - Tavern & Street: 'हरामज़ादे', 'सत्यानाश', 'लानत है', 'बकवास', 'भोसड़ीके', 'दल्ले', 'रांड'.
5. SOMATIC INTIMACY & EROTIC REALISM (ADR-016 & ADR-019):
   - When Geralt meets Yennefer in Mayor Neville's house during her bath, render the adult tension with palpable sensory friction: 
     warm water, soapsuds clinging to pale curves, coal-black violet eyes, the intoxicating scent of lilac and gooseberries, and dangerous seductive banter.
   - Absolutely NO clinical anatomy terms ('योनि', 'लिंग'). Use somatic descriptions (कमर, जांघें, गर्माहट, सांसें, लिलाक की महक).
6. CHARACTER VOICES:
   - Geralt: Calm, gravelly, cynical, weary, speaking without artificial drawl.
   - Dandelion: Theatrical, dramatic, terrified when choked by the Djinn, flamboyant poet.
   - Yennefer: Arrogant, razor-sharp, hypnotic, magnetic, aristocratic sorceress.
   - Chireadan: Dignified, intellectual, melancholy elf.
   - Priest Krepp: Dogmatic, scholarly cleric lecturing on elemental planes.
7. URDU KA TARKA ('Aate me Namak'): Infuse a calibrated 10-15% of atmospheric, noir, and poetic Urdu 
   ('गुफ़ा', 'जिस्म', 'हवस', 'अकीक', 'सन्नाटा', 'ज़ख़्म', 'इल्हाम', 'विरासत', 'फ़ना', 'क़यामत', 'तावीज़', 'फ़रमान') to give dark-fantasy philosophical weight.
8. SPOKEN DRAMATIC DIALOGUE: Punctuate for voice actors using ellipses ('...'), em-dashes ('—'), and expressive phrasing.
9. OUTPUT FORMAT: Output ONLY the translated chapter in Devanagari Markdown. NO preamble, NO translator notes, NO conversational intro/outro.
"""


def main():
    reset_key_backoffs()

    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    extracted_file = project_dir / "extracted" / "chapter_012.md"
    translation_dir = project_dir / "translation"
    translation_file = translation_dir / "chapter_012_hi.md"
    backup_file = translation_dir / "chapter_012_hi.old.md"
    glossary_file = translation_dir / "glossary.json"

    glossary = {}
    if glossary_file.exists():
        with open(glossary_file, "r", encoding="utf-8") as gf:
            glossary = json.load(gf)
        print(f"[*] Loaded translation glossary: {glossary_file.name}")

    if not extracted_file.exists():
        raise FileNotFoundError(f"Source extracted file not found: {extracted_file}")

    # Backup legacy translation if not already backed up
    if translation_file.exists() and not backup_file.exists():
        shutil.copy2(translation_file, backup_file)
        print(f"[+] Backed up legacy translation to: {backup_file.name}")

    with open(extracted_file, "r", encoding="utf-8") as f:
        source_text = f.read()

    print(f"[*] Loaded source text: {extracted_file.name} ({len(source_text.split())} words)")

    # Parse sections based on Roman numerals at start of lines
    # Split by \n(?=[I|V|X]+\n)
    raw_sections = re.split(r'\n(?=[I|V|X]+\n)', source_text)
    
    # We assemble into 10 structured chunks
    # raw_sections[0] is '# THE LAST WISH\n'
    # raw_sections[1] is 'I\n...'
    # raw_sections[2] is 'II\n...'
    # ...
    # raw_sections[8] is 'VIII\n...'
    # raw_sections[9..13] is 'IX'..'XIII'
    # raw_sections[14..17] is 'XIV'..'XVII'

    # Balance sections into granular 600-800 word chunks on paragraph boundaries
    chunks = []
    for s in raw_sections[1:]:
        lines = s.strip().split('\n')
        numeral = lines[0].strip()
        body = '\n'.join(lines[1:]).strip()

        paras = [p.strip() for p in body.split('\n\n') if p.strip()]
        curr_chunk = []
        curr_words = 0
        part_idx = 1
        total_sec_words = len(body.split())
        remaining_words = total_sec_words

        for p in paras:
            w_cnt = len(p.split())
            if curr_words >= 650 and (remaining_words - w_cnt) >= 350:
                chunks.append((f"Section {numeral} (Part {part_idx})", numeral, "\n\n".join(curr_chunk)))
                curr_chunk = [p]
                curr_words = w_cnt
                part_idx += 1
            else:
                curr_chunk.append(p)
                curr_words += w_cnt
            remaining_words -= w_cnt

        if curr_chunk:
            p_label = f" (Part {part_idx})" if part_idx > 1 else ""
            chunks.append((f"Section {numeral}{p_label}", numeral, "\n\n".join(curr_chunk)))

    system_prompt = build_system_prompt()
    translated_sections = []

    print("\n" + "=" * 80)
    print("  STAGE 1: CHAPTER 12 SOTA HIGH-FIDELITY LITERARY TRANSLATION (gemini-3.8-flash)")
    print("=" * 80)

    cache_dir = translation_dir / ".cache" / "chapter_012"
    cache_dir.mkdir(parents=True, exist_ok=True)

    prev_context = ""
    for idx, (title, numeral, chunk_txt) in enumerate(chunks, 1):
        cache_file = cache_dir / f"chunk_{idx:02d}.txt"
        if cache_file.exists():
            print(f"[*] Restoring [{idx}/{len(chunks)}] {title} from cache...")
            with open(cache_file, "r", encoding="utf-8") as f:
                clean_chunk = f.read()
            translated_sections.append(clean_chunk)
            prev_context = clean_chunk
            continue

        print(f"\n[*] Translating [{idx}/{len(chunks)}] {title} ({len(chunk_txt.split())} words)...")
        prompt = f"""Translate the following section from Andrzej Sapkowski's 'The Witcher: The Last Wish' (Story: 'The Last Wish' / 'आखिरी इच्छा') into rich, cinematic spoken Hindustani in Devanagari script.

STRICT INVARIANTS:
- No English words in parentheses (eliminate '(djinn)', '(amphora)', '(seal)', etc.).
- Maintain raw, gritty tavern/street dialogue without censorship ('हरामज़ादे', 'सत्यानाश', 'लानत है', 'बकरी की गांड').
- In sensual and intimate scenes with Yennefer, use visceral somatic realism (lilac and gooseberry perfume, touch, friction, dark passion) with zero clinical anatomy words.
- Character fidelity: Geralt (calm, gravelly, cynical, protective), Dandelion (flamboyant troubadour), Yennefer (hypnotic, aristocratic, dangerous, seductive), Chireadan (intellectual, melancholy elf), Priest Krepp (scholarly cleric).

{f'PREVIOUS CONTEXT:\n{prev_context[-800:]}\n\n' if prev_context else ''}
ENGLISH SOURCE TEXT TO TRANSLATE:
{chunk_txt}
"""
        t0 = time.time()
        translated_chunk = call_gemini_resilient(
            prompt=prompt,
            system_instruction=system_prompt,
            model="gemini-3.5-flash-lite",
        )
        t_el = time.time() - t0
        print(f"[+] Translated in {t_el:.1f}s ({len(translated_chunk.split())} Devanagari words).")

        clean_chunk = translated_chunk.strip()
        if clean_chunk.startswith("```markdown"):
            clean_chunk = clean_chunk[len("```markdown"):].strip()
        elif clean_chunk.startswith("```"):
            clean_chunk = clean_chunk[len("```"):].strip()
        if clean_chunk.endswith("```"):
            clean_chunk = clean_chunk[:-3].strip()

        # Remove redundant leading Roman numeral headers emitted by LLM
        clean_chunk = re.sub(r"^(?:#+\s*(?:Section\s*)?[IVXLCDM]+\b[^\n]*\n+)+", "", clean_chunk, flags=re.IGNORECASE).strip()

        # Sanitize translation and audit literary register
        is_valid, sanitized_chunk, err = validate_and_sanitize_translation(clean_chunk)
        if not is_valid:
            print(f"    [!] Warning: Sanitize flagged chunk {idx}: {err}")
            if sanitized_chunk:
                clean_chunk = sanitized_chunk
        else:
            clean_chunk = sanitized_chunk

        _, audited_chunk, warnings = audit_literary_register(clean_chunk)
        for w in warnings:
            print(f"    [*] Advisory: {w}")
        clean_chunk = normalize_translated_lexicon(audited_chunk, glossary)

        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(clean_chunk)

        translated_sections.append(clean_chunk)
        prev_context = clean_chunk
        time.sleep(4.0)

    # Assemble complete Chapter 12 translation
    full_translation = "# आखिरी इच्छा\n\n"
    current_sec = None
    for (title, numeral, _), trans in zip(chunks, translated_sections):
        if numeral != current_sec:
            full_translation += f"## {numeral}\n\n"
            current_sec = numeral
        full_translation += trans.strip() + "\n\n"

    with open(translation_file, "w", encoding="utf-8") as f:
        f.write(full_translation.strip() + "\n")

    print("\n" + "=" * 80)
    print(f"🎉 CHAPTER 12 SOTA TRANSLATION COMPLETE & ASSEMBLED!")
    print(f"Output File: {translation_file.resolve()}")
    print(f"Total Words: {len(full_translation.split())} Devanagari words across {len(chunks)} chunks.")
    print("=" * 80)

if __name__ == "__main__":
    main()
