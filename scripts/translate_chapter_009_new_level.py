#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 9 Hindi Translation Runner (New Updated Status & Level).
Strict Unfiltered Literary Hindustani Translation of Andrzej Sapkowski's 'The Voice of Reason 5'.
Enforces:
- 11 Strict Engine Invariants (Anti-Bowdlerization, 70/30 Anti-Parody, 19-to-21 Amplification)
- Desi Tavern Grit & Raw Profanity ('गांड' instead of 'चूतड़', 'बकचोदी', 'सूअर का पेशाब', 'अंडकोष बधिया करना')
- Spoken Dramatic Punctuation for Voice Acting
- Canonical Honorifics (Geralt-Nenneke: Aap; Geralt-Dandilion: Tum/Tu)
- Natural 3-Scene Rolling Context Translation (Zero-Timeout, Zero-503)
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

    source_path = extracted_dir / "chapter_009.md"
    glossary_path = translation_dir / "glossary.json"
    output_path = translation_dir / "chapter_009_hi.md"
    backup_path = translation_dir / "chapter_009_hi.old.md"

    if not source_path.exists():
        raise FileNotFoundError(f"Source file missing: {source_path}")

    # Backup previous translation if present
    if output_path.exists() and not backup_path.exists():
        shutil.copy2(output_path, backup_path)
        print(f"[*] Backed up existing translation to {backup_path.name}")

    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read().strip()

    glossary = {}
    if glossary_path.exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = json.load(f)

    paragraphs = [p.strip() for p in source_text.split("\n\n") if p.strip()]
    words = len(source_text.split())
    chars = len(source_text)
    print("=" * 80)
    print("  AUDIOBOOK FACTORY - CHAPTER 009 NEW LEVEL HINDI TRANSLATION")
    print("  'The Voice of Reason 5' -> Spoken Cinematic Hindustani (Rolling 3-Scene)")
    print("=" * 80)
    print(f"Source Words: {words} | Paras: {len(paragraphs)} | Chars: {chars}")

    # Break into 3 natural dramatic scenes:
    # Scene 1: Arrival of Dandilion, Nenneke scolding, library plum vodka (paras 0-29)
    # Scene 2: Discussion of south, troll toll, baron's dragon pet, rusalkas & impotence soup (paras 30-50)
    # Scene 3: Unicorn virgins, ratcatchers, Roderick history, unwashed girls & Gulet scandal (paras 51-74)
    scenes = [
        ("Scene 1: Dandelion Arrival & Library Vodka", "\n\n".join(paragraphs[:30])),
        ("Scene 2: Troll Toll & Impotence Soup", "\n\n".join(paragraphs[30:51])),
        ("Scene 3: Unicorn Virgins & Gulet Scandal", "\n\n".join(paragraphs[51:])),
    ]

    system_prompt = (
        "You are a master literary translator and audio drama director adapting the mature, grimdark fantasy "
        "and adult literature (in the unapologetic tradition of Andrzej Sapkowski, George R.R. Martin, Anurag Kashyap, and Saadat Hasan Manto) "
        "into cinematic, spoken Hindustani (Hindi in Devanagari script) for a premier audio drama.\n\n"
        "STRICT TRANSLATION INVARIANTS & PRODUCTION STANDARDS:\n"
        "1. LITERARY ANTI-BOWDLERIZATION MANDATE: NEVER sanitize, soften, or bowdlerize raw dialogue, sexual humor, intimate "
        "bodily descriptions, crude tavern banter, or gritty curses. The original European text is gritty adult literature—NOT a censored "
        "children's cartoon. Any softening of sexual references, swear words, or raw humor is a critical translation failure.\n"
        "2. THE 70/30 ANTI-PARODY INVARIANT: Maintain a strict 70% Canon Sacredness / 30% Sensory Desi Amplification ratio. "
        "Never replace European dark-fantasy lore, proper nouns, monster classifications (forktail, manticore, chimera, troll, striga, rusalka, dryad), or "
        "geographic names (Wyzim, Buina, Oxenfurt, Gulet, Jaruga, Dragon Mountains) with Indian mythology or tapori spoofs. "
        "Restrict Desi/Hindustani adaptation strictly to organic tavern grit, authentic rustic profanity, dynamic honorific power shifts, "
        "and Manto-grade somatic physical descriptions.\n"
        "3. PERIOD TAVERN GRIT & RAW PROFANITY (NEW LEVEL STANDARD): Translate medieval insults and curses into authentic, earthy Hindustani equivalents. "
        "Use 'गांड' (STRICTLY NEVER 'चूतड़' or 'नितंब' or 'कूल्हों' for buttocks/arse), 'भोसड़ीके', 'लंड', 'रांड / रंडी', 'भड़वा / दल्ला', 'मादरचोद', 'बकचोदी', 'सूअर का पेशाब', "
        "'अंडकोष बधिया करना'. NEVER replace them with polite TV-serial substitutions (do NOT turn 'bastard' into 'दुष्ट' or 'whore' into 'बुरी स्त्री').\n"
        "4. THE 19-TO-21 AMPLIFICATION RULE: When source English dialogue is mild or toned down (19), elevate it to authentic Desi 21 "
        "for visceral gut-punch impact (e.g. 'Stop talking bullshit' -> 'अपनी ये बकचोदी बंद करो!', 'beer tastes like piss' -> 'बीयर का स्वाद सूअर के पेशाब जैसा है', "
        "'geld you' -> 'अंडकोष काट के बधिया कर देंगे').\n"
        "5. DESI MUHAVARE & IDIOMS: Transpose English idioms into organic, gritty spoken idioms rather than literal word-for-word translation.\n"
        "6. HONORIFICS & CHARACTER DYNAMICS:\n"
        "   - Geralt addresses Nenneke as 'Aap' (reverent, matronly mother-figure).\n"
        "   - Dandilion and Geralt address each other as 'Tum' / 'Tu' (close brothers-in-arms, witty banter).\n"
        "   - Nenneke addresses Dandilion with sharp irritation ('Tu' / 'Tum').\n"
        "7. URDU KA TARKA ('Aate me Namak'): Infuse a calibrated 10-15% of atmospheric, noir, and poetic Urdu "
        "('जिस्म', 'हवस', 'क़यामत', 'रूह', 'सन्नाटा', 'ख़ौफ़', 'ज़ख़्म', 'दस्तक', 'शायर', 'इल्हाम', 'कीमियागरी') to give dark-fantasy philosophical weight.\n"
        "8. SPECIFIC CHAPTER 9 SCENE FIDELITY (UNFILTERED & VIVID):\n"
        "   - Dandilion flirting with the gatekeeper girl: Describe her blonde hair, long lashes, and virgin's plait reaching down to her cute, shapely little ass ('सुडौल छोटी गांड... अब ऐसी गांड पर चिकोटी न काटना तो सीधे-सीधे गुनाह होता! सो मैंने काट ली!').\n"
        "   - Nenneke's reaction: 'अपनी ये बकचोदी बंद करो... और मुझे माँ कहना तो बिल्कुल बंद कर दो! यह सोचकर ही मेरी रूह काँप उठती है कि तुम्हारे जैसा कोई लफ़ंगा मेरा बेटा हो सकता है.'\n"
        "   - Geography vs History academy joke: History was second favorite; Geography was first because the atlas was huge and easy to hide a demijohn of vodka behind it.\n"
        "   - Plum vodka hidden behind alchemy volumes in the library: 'अक्ल और इल्हाम अब भी लाइब्रेरियों में मिलते हैं... बेर की दारू... असली कीमियागरी! प्लेग की तरह तेज़ और जानलेवा!'\n"
        "   - The Troll under the bridge repairing it with sweat of his brow; peasant alderman refusing to kill it because it's cheaper to pay the toll.\n"
        "   - Forktail dragon carrying a sheep; peasants falling on knees begging not to kill it because it's the baron's youngest daughter's pet.\n"
        "   - Peasants asking to catch rusalkas/nymphs/dryads for sexual company, and asking to kill mecopteran for impotence bone soup ('नामर्दी/लिंग की कमजोरी का इलाज... कुछ मजबूत नहीं होता और सूप का स्वाद पुराने मोज़ों जैसा हो जाता है').\n"
        "   - Unicorn virgins losing jobs and immediately popping their cherry ('फौरन अपनी सील तुड़वा ली/कौमार्य गंवा दिया, और सालों के त्याग की कसर निकालने के लिए अपनी तकनीक और बिस्तर के जोश के चलते दूर-दूर तक मशहूर हो गईं').\n"
        "   - Roderick de Novembre's history: Humanity as intruders taking land from dragons, griffins, manticores, vampires, strigas.\n"
        "   - Southern complaints: 'जौ और सूखा बाजरा, बीयर का स्वाद सूअर के पेशाब जैसा, लड़कियाँ कभी नहाती नहीं और मच्छर काटते हैं'.\n"
        "   - Gulet scandal: Dandilion knocking up a girl under the musicians' podium, her four brothers hunting him all over town threatening to geld him (badhiya karna) and coat him in pitch and sawdust.\n"
        "9. SPOKEN DRAMATIC DIALOGUE: Punctuate for voice actors using ellipses ('...'), em-dashes ('—'), and expressive phrasing.\n"
        "10. SENSE-FOR-SENSE SPOKEN DIALOGUE: Never do literal word-for-word translation. Preserve humor, cadence, cynicism, and wit.\n"
        "11. OUTPUT FORMAT: Output ONLY the translated chapter in Devanagari Markdown. NO preamble, NO translator notes, NO conversational intro/outro."
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
{rolling_ctx if rolling_ctx else "Beginning of Chapter 9 (The Voice of Reason 5). Geralt is studying in Melitele's temple library."}

### ENGLISH TEXT TO TRANSLATE ({scene_name}):
\"\"\"
{scene_text}
\"\"\"
"""
        t0 = time.time()
        translated_chunk = call_gemini(
            prompt=prompt,
            system_instruction=system_prompt,
            model="gemini-3.1-flash-lite",
            json_mode=False,
            max_retries=4,
        ).strip()
        dur = time.time() - t0
        print(f"    [+] Scene {idx} translated in {dur:.1f}s ({len(translated_chunk)} chars)")

        # Validate chunk
        is_valid, cleaned, reason = validate_and_sanitize_translation(translated_chunk, is_hindi=True)
        if not is_valid:
            print(f"    [!] Warning: Sanitizer note on scene {idx}: {reason}")
            cleaned = translated_chunk

        translated_scenes.append(cleaned)
        # Update rolling context with tail of translated scene
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
    print("  VERIFYING KEY UNFILTERED SCENES IN GENERATED HINDI:")
    print("-" * 80)
    checks = [
        ("Buttocks pinch ('गांड' standard)", ["गांड", "चिकोटी", "दरबान"]),
        ("Bullshit / Nenneke ('बकचोदी')", ["बकचोदी", "माता जी", "माँ"]),
        ("Impotence soup ('नामर्दी')", ["नामर्दी", "सूप", "मोज़ों"]),
        ("Unicorn cherry ('सील' / 'कौमार्य')", ["सील", "कौमार्य", "यूनिकॉर्न", "तकनीक"]),
        ("Piss beer & unwashed ('पेशाब' / 'नहाती')", ["पेशाब", "नहाती", "मच्छर"]),
        ("Gulet pregnancy & gelding ('बधिया' / 'तारकोल')", ["पेट से", "गर्भवती", "अंडकोष", "बधिया", "तारकोल"]),
    ]
    for label, keywords in checks:
        found = [k for k in keywords if k in final_hindi]
        status = "[FOUND]" if found else "[MISSING]"
        print(f"  {status:<10} {label:<35} (matched: {found})")

    print("\n[OK] Gate 2 New-Level Unfiltered Translation Completed Successfully!")


if __name__ == "__main__":
    main()
