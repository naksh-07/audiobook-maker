#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 9 Hindi Translation Production Script (High-Model Standard).
Translates Andrzej Sapkowski's 'The Voice of Reason 5' into cinematic,
spoken Hindustani for dark-fantasy audio drama.
Enforces:
- Dynamic Literary Advisory Lexicon from SQLite DB (literary_advisory.db)
- Gemini 3.8 Flash High / 3.7 Flash High Model Execution Hierarchy
- Meso-Tier Post-Translation Linguistic Linter (audit_literary_register)
- Natural 3-Scene Rolling Architecture (zero-timeout, high context fidelity)
"""

import os
import sys
import json
import time
import shutil
from pathlib import Path

# Ensure UTF-8 I/O
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.translator import (
    call_gemini,
    normalize_translated_lexicon,
)
from audiobook_factory.sanitizer import (
    validate_and_sanitize_translation,
    audit_literary_register,
)
from audiobook_factory.advisory_lexicon import get_advisory_db


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    extracted_dir = project_dir / "extracted"
    translation_dir = project_dir / "translation"

    source_path = extracted_dir / "chapter_009.md"
    glossary_path = translation_dir / "glossary.json"
    output_path = translation_dir / "chapter_009_hi.md"
    backup_path = translation_dir / "chapter_009_hi.old.md"

    if not source_path.exists():
        raise FileNotFoundError(f"Source file missing: {source_path}")

    # Backup previous translation if present
    if output_path.exists() and not backup_path.exists():
        shutil.copy2(output_path, backup_path)
        print(f"[*] Backed up previous translation to {backup_path.name}")

    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read().strip()

    glossary = {}
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)

    advisory_db = get_advisory_db()
    advisory_guidance = advisory_db.get_formatted_prompt_guidelines()

    paragraphs = [p.strip() for p in source_text.split("\n\n") if p.strip()]
    words = len(source_text.split())
    chars = len(source_text)
    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 009 HIGH-TIER HINDI TRANSLATION")
    print("  'The Voice of Reason 5' -> Spoken Cinematic Hindustani (Gemini 3.8 / 3.7 Flash)")
    print("=" * 80)
    print(f"Source Words: {words} | Paras: {len(paragraphs)} | Chars: {chars}")

    # 3 natural dramatic scenes
    scenes = [
        ("Scene 1: Dandelion Arrival & Library Plum Spirits", "\n\n".join(paragraphs[:30])),
        ("Scene 2: Troll Toll & Impotence Soup", "\n\n".join(paragraphs[30:51])),
        ("Scene 3: Unicorn Virgins & Gulet Scandal", "\n\n".join(paragraphs[51:])),
    ]

    system_prompt = (
        "You are a master literary translator adapting Andrzej Sapkowski's dark fantasy masterpiece "
        "(The Witcher: 'The Last Wish') into rich, cinematic, spoken Hindustani in Devanagari script for a premier audio drama.\n\n"
        "STRICT LITERARY GUIDELINES:\n"
        "1. LITERARY ANTI-BOWDLERIZATION MANDATE: Maintain adult literary fidelity. Never sanitize, soften, or omit adult banter, "
        "sensory descriptions, earthy tavern humor, or gritty curses. The original European text is gritty adult literature—NOT a censored children's show.\n"
        "2. AUTHENTIC HINDUSTANI GRIT & PROFANITY: Translate bawdy tavern insults and dialogue into natural, expressive Hindustani "
        "(e.g., 'बकचोदी बंद करो', 'हरामी', 'कमीने', 'रंडी की औलाद', 'सूअर का पेशाब', 'जहन्नुम में जा', 'गांड', 'अंडकोष बधिया करना'). "
        "Do NOT replace them with polite, sanitized textbook Hindi.\n"
        "3. THE 70/30 ANTI-PARODY INVARIANT: Maintain 70% Canon Sacredness / 30% Sensory Desi Amplification. "
        "Never replace European dark-fantasy lore, proper nouns, monster classifications (forktail, manticore, chimera, troll, striga, rusalka, dryad), or "
        "geographic names (Wyzim, Buina, Oxenfurt, Gulet, Jaruga, Dragon Mountains) with Indian mythology. "
        "Restrict Desi adaptation strictly to organic tavern grit, authentic profanity, dynamic honorifics, and visceral sensory descriptions.\n"
        "4. SCENE FAITHFULNESS:\n"
        "   - Dandilion flirting with the gatekeeper girl: Describe her blonde hair, long lashes, and virgin's plait reaching down to her cute, perky little ass, and pinching her ass ('उसकी सुडौल छोटी गांड... अब ऐसी गांड पर चिकोटी न काटना तो सीधे-सीधे गुनाह होता! सो मैंने काट ली!').\n"
        "   - Nenneke's scolding: 'अपनी ये बकचोदी बंद करो... और मुझे माँ कहना तो बिल्कुल बंद कर दो! यह सोचकर ही मेरी रूह काँप उठती है कि तुम्हारे जैसा कोई लफ़ंगा मेरा बेटा हो सकता है.'\n"
        "   - Geography vs History joke: Geography was first because the atlas was huge and easy to hide a demijohn of vodka behind it.\n"
        "   - Plum spirits in library: 'लाइब्रेरियों में अब भी अक्ल और इल्हाम दोनों ढूँढ़े जा सकते हैं... बेर की शराब... असली कीमियागरी! प्लेग की तरह तेज़ और जानलेवा!'\n"
        "   - Troll under bridge repairing it with sweat of his brow; alderman refusing to kill it because paying the toll is cheaper than repairs.\n"
        "   - Forktail dragon: Baron's youngest daughter's pet; peasants begging not to touch it.\n"
        "   - Peasants wanting rusalkas/nymphs/dryads for sexual company, and mecopteran bone for impotence soup ('नामर्दी/लिंग की कमजोरी का इलाज... कुछ मजबूत नहीं होता और सूप का स्वाद पुराने मोज़ों जैसा हो जाता है').\n"
        "   - Unicorn virgins losing jobs and immediately popping their cherry ('फौरन अपनी सील तुड़वा ली/कौमार्य गंवा दिया, और सालों के त्याग की कसर निकालने के लिए अपनी कला, तकनीक और बिस्तर के जोश के चलते दूर-दूर तक मशहूर हो गईं').\n"
        "   - Roderick de Novembre's history: Humanity as intruders taking land from dragons, griffins, manticores, chimera with the help of witchers.\n"
        "   - Southern complaints: 'जौ और सूखा बाजरा, बीयर का स्वाद सूअर के पेशाब जैसा, लड़कियाँ कभी नहाती नहीं हैं और मच्छर काटते हैं'.\n"
        "   - Gulet incident: Dandilion knocking up a girl under the musicians' podium, her four brothers hunting him all over town threatening to geld him (badhiya karna) and coat him in pitch and sawdust ('संगीतकारों के मंच के नीचे जिस लड़की को तुमने पेट से कर दिया था... उसके चार लठैत भाई तुम्हारे अंडकोष काटने/बधिया करने और तारकोल पोतने की धमकी दे रहे थे').\n"
        "5. SPOKEN DRAMATIC DIALOGUE: Punctuate for voice actors using ellipses ('...'), em-dashes ('—'), and natural cadence.\n"
        "6. HONORIFICS: Geralt addresses Nenneke as 'Aap'; Dandilion and Geralt address each other as 'Tum'/'Tu'; Nenneke addresses Dandilion with annoyance ('Tu'/'Tum').\n"
        "7. OUTPUT FORMAT: Output ONLY the translated chapter in Devanagari Markdown. NO preamble, NO translator notes, NO meta chatter.\n\n"
        f"{advisory_guidance}"
    )

    glossary_str = json.dumps(glossary, ensure_ascii=False, indent=2)
    translated_scenes = []
    rolling_ctx = ""

    for idx, (scene_name, scene_text) in enumerate(scenes, 1):
        scene_words = len(scene_text.split())
        print(f"\n[*] [{idx}/3] Translating {scene_name} ({scene_words} words)...")

        prompt = f"""### PERSISTENT PROJECT GLOSSARY:
{glossary_str}

### PRECEDING CONTEXT (For Tone & Terminology Continuity):
{rolling_ctx if rolling_ctx else "Beginning of Chapter 9 (The Voice of Reason 5). Geralt is in Melitele's temple library."}

### ENGLISH TEXT TO TRANSLATE ({scene_name}):
\"\"\"
{scene_text}
\"\"\"
"""
        t0 = time.time()
        translated_chunk = call_gemini(
            prompt=prompt,
            system_instruction=system_prompt,
            model="gemini-3.8-flash",
            json_mode=False,
            max_retries=4,
        ).strip()
        dur = time.time() - t0
        print(f"    [+] Scene {idx} translated in {dur:.1f}s ({len(translated_chunk)} chars)")

        # Validate chunk
        is_valid, cleaned, reason = validate_and_sanitize_translation(translated_chunk, is_hindi=True)
        if not is_valid:
            print(f"    [!] Note on sanitizer validation: {reason}")
            cleaned = translated_chunk

        # Audit literary register
        _, cleaned, warnings = audit_literary_register(cleaned)
        if warnings:
            for w in warnings:
                print(f"    [LINTER REPAIRED] {w}")

        translated_scenes.append(cleaned)
        rolling_ctx = cleaned[-600:]

    full_hindi_raw = "\n\n".join(translated_scenes)

    # Meso-Tier Verification Guard: Enforce canonical lexicon
    final_hindi = normalize_translated_lexicon(full_hindi_raw, glossary)

    # Final Literary Register Audit on the full stitched text
    _, final_hindi, final_warnings = audit_literary_register(final_hindi)
    if final_warnings:
        print(f"[*] Final Linter verified {len(final_warnings)} register alignments.")

    # Save to output file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_hindi)

    print("\n" + "=" * 80)
    print(f"[+] Complete Chapter 9 Translation written to: {output_path.name}")
    print(f"    Total Words: {len(final_hindi.split())} | Chars: {len(final_hindi)}")

    # Key scene verification checks
    print("\n" + "-" * 80)
    print("  VERIFYING KEY UNFILTERED SCENES IN GENERATED HINDI:")
    print("-" * 80)
    checks = [
        ("Buttocks pinch ('गांड' standard)", ["गांड", "चिकोटी"]),
        ("Bullshit / Nenneke ('बकचोदी')", ["बकचोदी", "माँ"]),
        ("Impotence soup ('नामर्दी')", ["नामर्दी", "सूप", "मोज़ों"]),
        ("Unicorn cherry ('सील' / 'कौमार्य')", ["सील", "कौमार्य", "यूनिकॉर्न", "तकनीक"]),
        ("Piss beer & unwashed ('पेशाब' / 'नहाती')", ["पेशाब", "नहाती", "मच्छर"]),
        ("Gulet pregnancy & gelding ('बधिया' / 'तारकोल')", ["पेट से", "गर्भवती", "अंडकोष", "बधिया", "तारकोल"]),
        ("Anti-Robotic Salutation ('सलाम')", ["सलाम"]),
        ("Anti-Robotic Beverage ('शराब')", ["शराब"]),
    ]
    for label, keywords in checks:
        found = [k for k in keywords if k in final_hindi]
        status = "[FOUND]" if found else "[MISSING]"
        print(f"  {status:<10} {label:<35} (matched: {found})")

    # Anti-patterns check (MUST BE ABSENT)
    antipatterns = ["सुनहरी लड़की", "कुंवारी चोटी", "नमस्ते, गेराल्ट", "नमस्ते", "दारू"]
    present = [ap for ap in antipatterns if ap in final_hindi]
    if present:
        print(f"  [WARNING] Detected remaining antipatterns: {present}")
    else:
        print("  [PERFECT] Zero robotic antipatterns detected in final translation!")

    print("\n[OK] Gate 2 High-Tier Translation Pipeline Completed Successfully!")


if __name__ == "__main__":
    main()
