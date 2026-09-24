#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 13 Hindi Translation Runner (SOTA New Level Standards).
Strict Unfiltered Literary Hindustani Translation of Andrzej Sapkowski's 'The Voice of Reason 7' (तर्क की आवाज़ 7).
Adheres strictly to:
- ADR-023: Dynamic Literary Advisory Lexicon DB & Register Quality Guard
- ADR-015: Unfiltered Desi Tavern Grit & Wasseypur/Manto Texture
- ADR-016: HBO/Netflix Grade Dramatic & Somatic Realism
- ADR-019: Unlocked Safety Thresholds (BLOCK_NONE)
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
    model: str = "gemini-3.5-flash",
    max_retries: int = 50,
) -> str:
    candidate_models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]

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
                    pool.mark_temporary_backoff(api_key, 20.0, f"HTTP {e.code}")
                    sleep_time = 10.0 if e.code == 429 else 4.0
                    print(f"    [PACING] HTTP {e.code} on {curr_model}. Cooling off {sleep_time:.1f}s...", flush=True)
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
and adult literature of Andrzej Sapkowski into cinematic, spoken Hindustani (Hindi in Devanagari script) for a premier audio drama.

{advisory_guidance}

STRICT TRANSLATION INVARIANTS & PRODUCTION STANDARDS:
1. LITERARY ANTI-BOWDLERIZATION MANDATE: NEVER sanitize, soften, or bowdlerize raw dialogue, tavern grit, rough soldier humor, 
   or visceral horror descriptions. The original European text is gritty adult literature—NOT a censored children's cartoon.
2. THE 70/30 ANTI-PARODY INVARIANT: Maintain a strict 70% Canon Sacredness / 30% Sensory Desi Amplification ratio. 
   Never replace European dark-fantasy lore, proper nouns, or titles with Indian mythology or tapori spoofs.
   - Proper Nouns: 'गेराल्ट' (Geralt), 'डैंडेलियन' (Dandelion), 'फ़ाल्विक' (Count Falwick), 'डेनिस क्रैनमर' (Dennis Cranmer), 
     'तैलिस' (Sir Tailles of Dorndal), 'मदर नेनेके' (Mother Nenneke), 'इओला' (Iola), 'राजकुमार हियरवर्ड' (Prince Hereward), 
     'एलांडर' (Ellander), 'ऑर्डर ऑफ द व्हाइट रोज़' (Order of the White Rose / व्हाइट रोज़ का संप्रदाय), 'मेलीतेले का मंदिर' (Temple of Melitele).
3. ZERO ENGLISH PARENTHETICAL LEAKAGE (CRITICAL FOR TTS): NEVER append English words in parentheses like '(medallion)', '(order)', 
   '(witcher)', or '(duel)'. In an audiobook script, bracketed English ruins the speech synthesis. Use pure, evocative Hindustani.
4. PERIOD TAVERN & GUARD GRIT:
   - Dennis Cranmer's rough dwarf tongue:
     "A knight without a scar is a prick, not a knight." -> 
     "बिना ज़ख़्म के नाइट... नाइट नहीं, बस एक चूहा होता है! काउंट साहब, उससे पूछिए, आप देखेंगे कि वह खुश है।"
     "I'd prefer not to bring my mother, a woman with whom I'm not very well acquainted, into this." -> 
     "मैं अपनी माँ को इसमें नहीं घसीटना चाहता, जिनसे मेरी वैसे भी कोई खास जान-पहचान नहीं रही।"
   - Geralt's cold warning to Falwick:
     "I'll find you and, not caring about any code, will bleed you like a pig." -> 
     "मैं तुम्हें पाताल से भी ढूँढ निकालूँगा और तुम्हारे किसी नियम-कायदे की परवाह किए बिना, तुम्हें किसी सूअर की तरह हलाल कर दूँगा।"
   - Tailles' arrogant howling and cursing: 'हरामज़ादे', 'सत्यानाश', 'लानत है', 'बकवास'.
5. VISCERAL SOMATIC REALISM & PROPHETIC HORROR (IOLA'S VISION):
   - When Iola touches Geralt's hand, the prophetic seizure must hit like an acoustic and psychological lightning strike:
     "खून। खून। लाल गर्म खून। टूटी हुई सफेद तीलियों जैसी चटकती हड्डियाँ। काँटोंदार विशाल पंजों और आरी जैसे नुकीले दाँतों से फटी खाल के नीचे से उधड़ते सफेद स्नायु। गोश्त के चीथड़े उड़ने की वीभत्स आवाज़... और चीखें—मौत की निर्लज्ज, रूह कँपा देने वाली चीखें! खून और चीखें..."
6. CHARACTER VOICES:
   - Geralt: Cold, gravelly, cynical, weary, speaking with deadly calm authority.
   - Dandelion: Flamboyant, theatrical, mockingly poetic, observant.
   - Dennis Cranmer: Sturdy, gravelly, stubborn, strictly honorable dwarf captain who loves a good joke and loathes pompous knights.
   - Falwick: Pompous, venomous, cowardly underneath his noble armor.
   - Tailles: Haughty, spoiled young noble who learns a brutal lesson.
   - Nenneke: Protective, deeply maternal, terrified by the prophetic omen yet commanding.
7. URDU KA TARKA ('Aate me Namak'): Infuse a calibrated 10-15% of atmospheric Urdu ('ज़ख़्म', 'कयामत', 'फ़रमान', 'दस्तूर', 'सन्नाटा', 'हलाल', 'तावीज़', 'विरासत') 
   to give dark-fantasy philosophical weight.
8. SPOKEN DRAMATIC DIALOGUE: Punctuate for voice actors using ellipses ('...'), em-dashes ('—'), and natural cadence.
9. OUTPUT FORMAT: Output ONLY the translated chapter in Devanagari Markdown. NO preamble, NO translator notes, NO conversational intro/outro.
"""


def split_chapter_13_text(source_text: str) -> List[Tuple[str, str, str]]:
    """
    Split Chapter 13 into 4 complete, scene-bound dramatic chunks on narrative boundaries.
    """
    text = source_text.strip()
    if text.startswith("# 7: THE VOICE OF REASON"):
        text = text[len("# 7: THE VOICE OF REASON"):].strip()
    if text.startswith("THE VOICE OF REASON"):
        text = text[len("THE VOICE OF REASON"):].strip()

    m1_marker = "Allow me, Geralt sir."
    m2_marker = "The soldiers surrounded the glade"
    m3_marker = "\nII\n"

    p1 = text.find(m1_marker)
    p2 = text.find(m2_marker)
    p3 = text.find(m3_marker)

    if p1 == -1 or p2 == -1 or p3 == -1:
        raise ValueError(f"Could not locate narrative scene markers: p1={p1}, p2={p2}, p3={p3}")

    c1 = text[:p1].strip()
    c2 = text[p1:p2].strip()
    c3 = text[p2:p3].strip()
    c4 = text[p3 + len("\nII\n"):].strip()

    chunks = [
        ("तर्क की आवाज़ 7 - भाग 1: जंगल में घेराबंदी व नाइट की चुनौती", "I", c1),
        ("तर्क की आवाज़ 7 - भाग 1: कप्तान डेनिस क्रैनमर व द्वंद्व का फैसला", "I", c2),
        ("तर्क की आवाज़ 7 - भाग 1: द्वंद्व, तैलिस का मुंहतोड़ जवाब व विदाई चेतावनी", "I", c3),
        ("तर्क की आवाज़ 7 - भाग 2: मेलीतेले मंदिर से विदाई व इओला की खौफनाक भविष्यवाणी", "II", c4),
    ]
    return chunks


def main():
    reset_key_backoffs()

    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    extracted_file = project_dir / "extracted" / "chapter_013.md"
    translation_dir = project_dir / "translation"
    translation_file = translation_dir / "chapter_013_hi.md"
    backup_file = translation_dir / "chapter_013_hi.old.md"
    glossary_file = translation_dir / "glossary.json"

    glossary = {}
    if glossary_file.exists():
        with open(glossary_file, "r", encoding="utf-8") as gf:
            glossary = json.load(gf)
        print(f"[*] Loaded translation glossary: {glossary_file.name}")

    if not extracted_file.exists():
        raise FileNotFoundError(f"Source extracted file not found: {extracted_file}")

    # Backup legacy translation
    if translation_file.exists() and not backup_file.exists():
        shutil.copy2(translation_file, backup_file)
        print(f"[+] Backed up legacy translation to: {backup_file.name}")

    with open(extracted_file, "r", encoding="utf-8") as f:
        source_text = f.read()

    print(f"[*] Loaded source text: {extracted_file.name} ({len(source_text.split())} words)")

    chunks = split_chapter_13_text(source_text)
    print(f"[*] Sliced Chapter 13 into {len(chunks)} scene-bound chunks:")
    for i, (title, num, txt) in enumerate(chunks, 1):
        print(f"    - Chunk {i}: {title} ({len(txt.split())} words)")

    system_prompt = build_system_prompt()
    translated_sections = []

    print("\n" + "=" * 80)
    print("  STAGE 1: CHAPTER 13 SOTA HIGH-FIDELITY LITERARY TRANSLATION (gemini-3.5-flash)")
    print("=" * 80)

    cache_dir = translation_dir / ".cache" / "chapter_013_new"
    # Ensure fresh translation of all chunks
    shutil.rmtree(cache_dir, ignore_errors=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    prev_context = ""
    for idx, (title, numeral, chunk_txt) in enumerate(chunks, 1):
        cache_file = cache_dir / f"chunk_{idx:02d}.txt"

        print(f"\n[*] Translating [{idx}/{len(chunks)}] {title} ({len(chunk_txt.split())} words)...")
        prompt = f"""Translate the following section from Andrzej Sapkowski's 'The Witcher: The Last Wish' (Story: 'The Voice of Reason 7' / 'तर्क की आवाज़ 7') into rich, cinematic spoken Hindustani in Devanagari script.

STRICT INVARIANTS:
- No English words in parentheses (eliminate '(medallion)', '(order)', '(witcher)', '(duel)', etc.).
- Maintain raw, gritty tavern/soldier dialogue without censorship ('हरामज़ादे', 'सत्यानाश', 'लानत है', 'चूहा/लौंडियाबाज़').
- In Dennis Cranmer's dialogues, preserve his sturdy, ironic dwarf cadence.
- In Iola's prophetic vision, render the somatic horror with terrifying visceral power (splintered white bones, monster fangs, tearing flesh, shameless horror of death).
- Character fidelity: Geralt (calm, gravelly, cynical, deadly), Dandelion (theatrical poet), Falwick (pompous, venomous knight), Dennis Cranmer (dwarf captain), Nenneke (protective high priestess).
- Translate every single dialogue line and narrative paragraph completely. Do NOT summarize or omit anything.

ENGLISH SOURCE TEXT TO TRANSLATE:
{chunk_txt}
"""
        t0 = time.time()
        translated_chunk = call_gemini_resilient(
            prompt=prompt,
            system_instruction=system_prompt,
            model="gemini-3.5-flash",
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
        time.sleep(3.0)

    # Assemble complete Chapter 13 translation
    full_translation = "# तर्क की आवाज़ 7\n\n"
    current_sec = None
    for (title, numeral, _), trans in zip(chunks, translated_sections):
        if numeral != current_sec:
            full_translation += f"## {numeral}\n\n"
            current_sec = numeral
        full_translation += trans.strip() + "\n\n"

    with open(translation_file, "w", encoding="utf-8") as f:
        f.write(full_translation.strip() + "\n")

    print("\n" + "=" * 80)
    print(f"🎉 CHAPTER 13 SOTA TRANSLATION COMPLETE & ASSEMBLED!")
    print(f"Output File: {translation_file.resolve()}")
    print(f"Total Words: {len(full_translation.split())} Devanagari words across {len(chunks)} chunks.")
    print("=" * 80)


if __name__ == "__main__":
    main()
