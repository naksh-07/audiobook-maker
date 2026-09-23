#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 9 Unfiltered Literary Hindustani Translation.
Strict Anti-Bowdlerization Standard:
Translates Andrzej Sapkowski's 'The Voice of Reason 5' without sanitizing
the gritty banter, sexual humor, intimacy, and earthy medieval Hindustani dialogue.
"""

import os
import sys
import json
import time
from pathlib import Path

# Configure UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.logger import logger
from audiobook_factory.translator import (
    call_gemini,
    normalize_translated_lexicon,
    GeminiPayloadError,
)
from audiobook_factory.sanitizer import validate_and_sanitize_translation


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    extracted_dir = project_dir / "extracted"
    translation_dir = project_dir / "translation"
    cache_dir = translation_dir / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    source_path = extracted_dir / "chapter_009.md"
    glossary_path = translation_dir / "glossary.json"
    output_path = translation_dir / "chapter_009_hi.md"

    if not source_path.exists():
        raise FileNotFoundError(f"Source file missing: {source_path}")

    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read().strip()

    glossary = {}
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)

    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 009 UNFILTERED LITERARY TRANSLATION")
    print("  Andrzej Sapkowski's 'The Voice of Reason 5' -> Spoken Dramatic Hindustani")
    print("  Anti-Bowdlerization & Full Intimacy / Gritty Banter Fidelity")
    print("=" * 80)
    print(f"Source Words: {len(source_text.split())} | Chars: {len(source_text)}")

    system_prompt = (
        "You are a master literary translator and audio drama director adapting the mature, grimdark "
        "dark-fantasy works of Andrzej Sapkowski (The Witcher series: 'The Last Wish') into rich, cinematic, "
        "spoken Hindustani (Hindi in Devanagari script) for a professional audio drama.\n\n"
        "STRICT UNFILTERED TRANSLATION RULES:\n"
        "1. LITERARY ANTI-BOWDLERIZATION MANDATE: NEVER sanitize, soften, or omit adult humor, intimate bodily descriptions, "
        "sexual banter, crude tavern jokes, or gritty curses. The original European text is gritty adult literature—NOT a censored "
        "children's cartoon. Any softening of sexual references, swear words, or raw humor is a critical translation failure.\n"
        "2. AUTHENTIC HINDUSTANI GRIT & PROFANITY: Translate bawdy tavern insults and curses into natural, expressive Hindustani "
        "(e.g., 'बकचोदी बंद करो', 'हरामी', 'कमीने', 'रंडी की औलाद', 'सूअर', 'जहन्नुम में जा', 'धत तेरे की'). "
        "Do NOT replace them with polite, sanitized textbook Hindi.\n"
        "3. PRESERVE SPECIFIC SCENES FAITHFULLY:\n"
        "   - Dandilion flirting with the gatekeeper girl: Keep the description of her pretty blonde hair, long lashes, virgin's plait "
        "reaching down to her cute little bottom, and pinching her bottom ('उसकी चोटी उसके उभरे हुए खूबसूरत कूल्हों/चूतड़ों तक जा रही थी... चिकोटी काटना तो गुनाह होता! सो मैंने काट ली!').\n"
        "   - Nenneke's reaction: 'Stop talking bullshit' -> 'ये बकचोदी बंद करो' / 'ये बकवास बंद करो'. 'Don't call me mother... fills me with horror'.\n"
        "   - The mecopteran bone for impotence: Keep the reference to curing impotence/erectile failure ('नामर्दी / लिंग की कमजोरी का इलाज') "
        "and Dandilion saying 'it doesn't strengthen anything and makes the soup taste of old socks'.\n"
        "   - Unicorn virgins losing jobs and 'popping their cherry': Translate accurately as losing their virginity/breaking their seal "
        "and indulging enthusiastically ('फौरन अपनी सील तुड़वा ली/कौमार्य गंवा दिया, और सालों के त्याग की कसर निकालने के लिए अपनी कला, तकनीक और बिस्तर के जोश के चलते दूर-दूर तक मशहूर हो गईं').\n"
        "   - Southern complaints: 'pearl barley and millet, beer tastes like piss, girls don't wash and mosquitoes bite' -> "
        "'जौ और सूखा बाजरा, बीयर का स्वाद सुअर के पेशाब जैसा, लड़कियाँ नहाती नहीं हैं और मच्छर काटते हैं'.\n"
        "   - The Gulet incident: Dandilion knocking up a girl under the musicians' podium, her four brothers wanting to geld him (castrate/badhiya karna) "
        "and cover him in pitch and sawdust ('संगीतकारों के मंच के नीचे जिस लड़की को तुमने पेट से कर दिया था... उसके चार लठैत भाई तुम्हारे अंडकोष काटने/बधिया करने और तारकोल पोतने की धमकी दे रहे थे').\n"
        "4. SPOKEN DRAMATIC DIALOGUE: Punctuate for voice actors using ellipses ('...'), em-dashes ('—'), and expressive phrasing. "
        "Avoid overly formal textbook Sanskrit. Use flowing, dramatic Hindustani.\n"
        "5. HONORIFICS: Geralt addresses Nenneke as 'Aap' (reverent/matronly); Dandilion and Geralt address each other as 'Tum'/'Tu' (intimate brothers in arms); "
        "Nenneke addresses Dandilion with annoyance ('Tu'/'Tum').\n"
        "6. OUTPUT FORMAT: Output ONLY the translated chapter in Devanagari Markdown. NO preamble, NO translator notes, NO conversational filler."
    )

    glossary_str = json.dumps(glossary, ensure_ascii=False, indent=2)

    prompt = f"""### PERSISTENT PROJECT GLOSSARY:
{glossary_str}

### ENGLISH CHAPTER 9 SOURCE TO TRANSLATE (Complete & Unfiltered):
\"\"\"
{source_text}
\"\"\"
"""

    print("\n[*] Sending full Chapter 9 to Gemini translation engine...")
    t0 = time.time()
    translated_raw = call_gemini(
        prompt=prompt,
        system_instruction=system_prompt,
        model="gemini-flash-latest",
        json_mode=False,
        max_retries=4,
    )
    t_trans = time.time() - t0
    print(f"[+] Translation completed by LLM in {t_trans:.1f}s.")

    # Apply linguistic sanitizer guardrail
    is_valid, cleaned, reason = validate_and_sanitize_translation(translated_raw, is_hindi=True)
    if not is_valid:
        raise RuntimeError(f"Sanitizer guardrail rejected translation: {reason}")

    # Meso-Tier Verification Guard: Enforce canonical lexicon
    final_hindi = normalize_translated_lexicon(cleaned, glossary)

    # Save to translation file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_hindi)

    print(f"[+] Output written to: {output_path.name}")
    print(f"    Words: {len(final_hindi.split())} | Chars: {len(final_hindi)}")

    # Key scene spot checks
    print("\n" + "-" * 80)
    print("  VERIFYING KEY UNFILTERED SCENES IN GENERATED HINDI:")
    print("-" * 80)
    checks = [
        ("Bottom pinch / Gatekeeper", ["चोटी", "कूल्हों", "चिकोटी", "दरबान"]),
        ("Bullshit / Nenneke", ["बकवास", "बकचोदी", "माताजी", "माँ"]),
        ("Impotence soup", ["नामर्दी", "सूप", "मोज़ों"]),
        ("Unicorn cherry", ["सील", "कौमार्य", "यूनिकॉर्न", "तकनीक"]),
        ("Piss beer & unwashed", ["पेशाब", "नहाती", "मच्छर"]),
        ("Gulet pregnancy & gelding", ["पेट से", "गर्भवती", "अंडकोष", "बधिया", "तारकोल"]),
    ]
    for label, keywords in checks:
        found = [k for k in keywords if k in final_hindi]
        status = "[FOUND]" if found else "[MISSING]"
        print(f"  {status:<10} {label:<30} (matched: {found})")

    print("\n[OK] Gate 2 Unfiltered Translation Completed Successfully!")


if __name__ == "__main__":
    main()
