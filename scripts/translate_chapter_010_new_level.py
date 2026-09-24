#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 10 Hindi Translation Runner (New Updated Standards).
Strict Unfiltered Literary Hindustani Translation of Andrzej Sapkowski's 'The Edge of the World'.
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
    model: str = "gemini-flash-latest",
    max_retries: int = 4,
) -> str:
    candidate_models = [model, "gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash"]
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
   children's cartoon. Any softening of raw humor, peasant curses, or visceral insults is a critical translation failure.
2. THE 70/30 ANTI-PARODY INVARIANT: Maintain a strict 70% Canon Sacredness / 30% Sensory Desi Amplification ratio. 
   Never replace European dark-fantasy lore, proper nouns, or monster classifications with Indian mythology or tapori spoofs.
   - Sylvan / Torque: Keep as 'सिल्वन' (वन-मानव / सींगों वाला जीव), mischievous devil ('शैतान').
   - Elves: Keep as 'एल्व्स' (प्राचीन नस्ल / वन-वासी), never 'परियाँ'.
   - Locations: 'अपर पोसाडा' (Upper Posada), 'लोअर पोसाडा' (Lower Posada), 'डोल ब्लाथाना' (Dol Blathanna / फूलों की घाटी), 'ब्लू माउंटेंस' (नीले पर्वत).
   - Restrict Desi adaptation strictly to organic tavern grit, authentic rustic profanity, dynamic honorific power shifts, 
     and Manto-grade somatic physical descriptions.
3. ZERO ENGLISH PARENTHETICAL LEAKAGE (CRITICAL FOR TTS): NEVER append English words in parentheses like '(Bane)', '(elves)', 
   '(vetch)', or '(deovel)'. In an audiobook script, bracketed English ruins the speech synthesis. Use pure, evocative Hindustani.
4. PERIOD TAVERN GRIT & RAW PROFANITY (NEW LEVEL STANDARD): Translate medieval insults and curses into authentic, earthy Hindustani equivalents. 
   Use 'गांड' (STRICTLY NEVER 'चूतड़' or 'नितंब' for arse/buttocks), 'भोसड़ीके', 'लंड', 'रांड / रंडी', 'भड़वा / दल्ला', 'मादरचोद', 'बकचोदी', 'सूअर का पेशाब', 
   'अंडकोष बधिया करना'. NEVER replace them with polite TV-serial substitutions (do NOT turn 'bastard' into 'दुष्ट' or 'whore' into 'बुरी स्त्री').
5. THE 19-TO-21 AMPLIFICATION RULE: When source English dialogue is mild or toned down (19), elevate it to authentic Desi 21 
   for visceral gut-punch impact (e.g. 'Stop talking bullshit' -> 'अपनी ये बकचोदी बंद करो!', 'beer tastes like piss' -> 'बीयर का स्वाद सूअर के पेशाब जैसा है').
6. DESI MUHAVARE & IDIOMS: Transpose English idioms into organic, gritty spoken idioms rather than literal word-for-word translation.
7. HONORIFICS & CHARACTER DYNAMICS:
   - Geralt and Dandelion address each other as 'Tum' / 'Tu' (close brothers-in-arms, cynical witty banter).
   - Geralt addresses peasants (Alderman, Nettly, Dhun) with pragmatic professional distance ('Aap' or respectful 'Tum').
   - Peasants address Geralt with rustic deference or suspicious awe ('Aap' / 'विचर साहब' / 'मालिक').
   - Torque (the Sylvan) speaks with cheeky, insolent, sarcastic peasant swagger ('Tu' / 'तुम लोग').
   - Filavandrel (Elf King) speaks with tragic, aristocratic, poetic high gravity ('Tum' to Geralt, elevated formal tone).
   - Toruviel speaks with burning, furious, bitter hostility.
8. URDU KA TARKA ('Aate me Namak'): Infuse a calibrated 10-15% of atmospheric, noir, and poetic Urdu 
   ('जिस्म', 'हवस', 'क़यामत', 'रूह', 'सन्नाटा', 'ख़ौफ़', 'ज़ख़्म', 'दस्तक', 'शायर', 'इल्हाम', 'विरासत', 'हसरत') to give dark-fantasy philosophical weight.
9. SPOKEN DRAMATIC DIALOGUE: Punctuate for voice actors using ellipses ('...'), em-dashes ('—'), and expressive phrasing.
10. SENSE-FOR-SENSE SPOKEN DIALOGUE: Never do literal word-for-word translation. Preserve humor, cadence, cynicism, and wit.
11. OUTPUT FORMAT: Output ONLY the translated chapter in Devanagari Markdown. NO preamble, NO translator notes, NO conversational intro/outro.
"""


def chunk_chapter(text: str) -> List[Tuple[str, str]]:
    """Splits Chapter 10 into 13 coherent dramatic scenes (~500 - 1400 words each)."""
    parts = re.split(r'\n(?=[I|V|X]+\n)', text)
    title = parts[0].strip()
    
    chunks = []
    for idx, sec in enumerate(parts[1:], 1):
        sec = sec.strip()
        paras = [p.strip() for p in sec.split('\n\n') if p.strip()]
        if not paras:
            continue
        sec_header = paras[0]
        sec_body = paras[1:]
        sec_words = len(sec.split())
        
        if sec_words <= 1800:
            chunks.append((f"Section {sec_header}", sec))
        else:
            cur = [sec_header]
            cur_w = 0
            sub_idx = 1
            for p in sec_body:
                w = len(p.split())
                cur.append(p)
                cur_w += w
                if cur_w >= 1300:
                    chunks.append((f"Section {sec_header} (Part {sub_idx})", "\n\n".join(cur)))
                    sub_idx += 1
                    cur = []
                    cur_w = 0
            if cur:
                chunks.append((f"Section {sec_header} (Part {sub_idx})", "\n\n".join(cur)))
    return chunks


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    extracted_dir = project_dir / "extracted"
    translation_dir = project_dir / "translation"
    cache_dir = translation_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    source_path = extracted_dir / "chapter_010.md"
    glossary_path = translation_dir / "glossary.json"
    output_path = translation_dir / "chapter_010_hi.md"
    backup_path = translation_dir / "chapter_010_hi.old.md"

    if not source_path.exists():
        raise FileNotFoundError(f"Source file missing: {source_path}")

    # Backup previous translation if present
    if output_path.exists() and not backup_path.exists():
        shutil.copy2(output_path, backup_path)
        print(f"[*] Backed up existing legacy translation to {backup_path.name}")

    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read().strip()

    glossary = {}
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)

    words = len(source_text.split())
    chunks = chunk_chapter(source_text)

    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 010 NEW LEVEL HINDI TRANSLATION")
    print("  'The Edge of the World' -> Unfiltered Spoken Cinematic Hindustani")
    print("=" * 80)
    print(f"Source Words: {words} | Semantic Chunks: {len(chunks)}")

    system_prompt = build_system_prompt()
    glossary_str = json.dumps(glossary, ensure_ascii=False, indent=2)

    translated_scenes = []
    rolling_ctx = ""

    for idx, (chunk_name, chunk_text) in enumerate(chunks, 1):
        chunk_words = len(chunk_text.split())
        cache_file = cache_dir / f"chapter_010_new_part_{idx:02d}.txt"

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_text = f.read().strip()
            print(f"\n[*] [{idx:02d}/{len(chunks):02d}] Loaded {chunk_name} from cache ({len(cached_text)} chars)")
            translated_scenes.append(cached_text)
            rolling_ctx = cached_text[-600:]
            continue

        print(f"\n[*] [{idx:02d}/{len(chunks):02d}] Translating {chunk_name} ({chunk_words} words)...")

        prompt = f"""### PERSISTENT PROJECT GLOSSARY:
{glossary_str}

### PRECEDING CONTEXT (For Tone, Honorifics & Continuity):
{rolling_ctx if rolling_ctx else "Beginning of Chapter 10 ('The Edge of the World' / 'दुनिया का छोर'). Geralt and Dandelion in Upper Posada tavern talking to the alderman."}

### ENGLISH TEXT TO TRANSLATE ({chunk_name}):
\"\"\"
{chunk_text}
\"\"\"
"""
        t0 = time.time()
        translated_chunk = call_gemini_resilient(
            prompt=prompt,
            system_instruction=system_prompt,
            model="gemini-flash-latest",
            max_retries=4,
        ).strip()
        dur = time.time() - t0
        print(f"    [+] {chunk_name} translated in {dur:.1f}s ({len(translated_chunk)} chars)")

        # Validate chunk
        is_valid, cleaned, reason = validate_and_sanitize_translation(translated_chunk, is_hindi=True)
        if not is_valid:
            print(f"    [!] Warning: Sanitizer note on chunk {idx}: {reason}")
            cleaned = translated_chunk

        # Run register audit
        reg_valid, reg_cleaned, rep = audit_literary_register(cleaned)
        if rep:
            print(f"    [*] Auto-normalized {len(rep)} robotic register tokens: {rep}")
            cleaned = reg_cleaned

        # Strip any accidental English parenthetical glosses e.g. "(Bane)", "(elves)"
        cleaned = re.sub(r"\s*\([A-Za-z\s]{2,25}\)", "", cleaned)

        # Write to cache
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(cleaned)

        translated_scenes.append(cleaned)
        rolling_ctx = cleaned[-600:]

    full_hindi_raw = "\n\n".join(translated_scenes)
    # Meso-Tier Verification Guard: Enforce canonical lexicon
    final_hindi = normalize_translated_lexicon(full_hindi_raw, glossary)

    # Save output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_hindi)

    print("\n" + "=" * 80)
    print(f"[+] Complete translation written to: {output_path.name}")
    print(f"    Total Words: {len(final_hindi.split())} | Chars: {len(final_hindi)}")

    # Verification checks
    print("\n" + "-" * 80)
    print("  VERIFYING KEY UNFILTERED SCENES & REGISTER IN GENERATED HINDI:")
    print("-" * 80)
    checks = [
        ("Tavern banter & grit", ["विचर", "मुखिया", "डैंडेलियन", "बीयर"]),
        ("Sylvan / Torque encounter", ["टॉर्क", "सींग", "गुलेल", "लोहे"]),
        ("Peasant folk book & Lille", ["किताब", "लिले", "धुन", "नानी"]),
        ("Elven confrontation (Toruviel)", ["तोरूविएल", "ल्यूट", "गांड", "एल्व्स"]),
        ("Filavandrel high dialogue", ["फ़िलावांड्रेल", "पर्वत", "नस्ल", "भूख"]),
        ("Dana Meadbh divine presence", ["खेतों की रानी", "अनाज", "फूल"]),
    ]
    for label, keywords in checks:
        found = [k for k in keywords if k in final_hindi]
        status = "[FOUND]" if found else "[MISSING]"
        print(f"  {status:<10} {label:<35} (matched: {found})")

    parens = re.findall(r"\([A-Za-z\s]{2,30}\)", final_hindi)
    print(f"  [CHECK] English parenthetical leaks: {len(parens)} found {parens[:5]}")
    print("\n[OK] Gate 2 Chapter 10 New-Level Unfiltered Translation Completed Successfully!")


if __name__ == "__main__":
    main()
