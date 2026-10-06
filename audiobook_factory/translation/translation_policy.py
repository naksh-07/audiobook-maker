#!/usr/bin/env python3
"""
Audiobook Factory - Central Translation Policy Engine.
Enforces immutable plot facts, strict semantic fidelity, permissible linguistic adaptation,
and the 'Nothing Above Source' standard.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TranslationPolicyConfig(BaseModel):
    version: str = "2.0.0"
    semantic_fidelity: str = "STRICT"
    plot_facts: str = "IMMUTABLE"
    character_actions: str = "IMMUTABLE"
    world_lore: str = "IMMUTABLE"
    relationship_facts: str = "IMMUTABLE"
    terminology: str = "CANONICAL"
    
    # Permissible adaptations
    idiom_adaptation: str = "ALLOWED"
    syntax_restructuring: str = "ALLOWED"
    spoken_naturalization: str = "ALLOWED"
    metaphor_adaptation: str = "CONTEXTUAL"
    literary_expansion: str = "LIMITED"
    
    # Strictly forbidden operations
    new_information: str = "FORBIDDEN"
    intensity_reduction: str = "FORBIDDEN"
    unjustified_intensity_amplification: str = "FORBIDDEN"
    sanitization: str = "FORBIDDEN"
    
    # Tone & Register
    target_register: str = "LITERARY_HINDUSTANI"
    urdu_seasoning: str = "CONTEXTUAL"  # "Aate mein Namak"
    adult_fidelity_mode: bool = True

    def get_prompt_instructions(self, book_dna: Optional[Dict[str, Any]] = None) -> str:
        """Returns authoritative, visceral system instructions for translation prompts dynamically tuned by book DNA."""
        dna = book_dna or {}
        tier = dna.get("source_fidelity_tier", "RAW_UNRATED" if self.adult_fidelity_mode else "CLASSIC_REVERENT")
        tradition = dna.get("literary_tradition", "DRAMATIC_LITERATURE")
        cadence = dna.get("regional_dialect_cadence", "Spoken Hindustani")

        if tier == "RAW_UNRATED":
            return (
                f"STRICT LITERARY TRANSLATION INVARIANTS ({tradition} - {cadence}):\n"
                "1. LITERARY ANTI-BOWDLERIZATION: This is an unrated, visceral adult literary audio drama. "
                "Do NOT sanitize, dilute, or censor raw tavern profanity, blood, severed limbs, gore, sexual tension, "
                "or somatic intimacy. Faithfully preserve the author's grim, mature dramatic truth.\n"
                "2. 70/30 ANTI-PARODY & WORLD-ANCHOR INVARIANT: Maintain 70% Canon Sacredness / 30% Sensory Desi Spoken Amplification. "
                "Never replace the book's universe, lore, proper nouns, or geographic names with Indian village panchayat names or tapori spoofs. "
                "If the setting is European, medieval fantasy, foreign, or sci-fi: STRICTLY FORBIDDEN to use Indian rural administrative "
                "or caste vocabulary ('पंच जी', 'लंबरदार', 'पटवारी', 'फतुही', 'अशर्फी'). "
                "Translate civic titles as 'एल्डरमैन/मेयर/नगर प्रमुख', currency as 'सिक्के/मुद्राएं/स्वर्ण मुद्राएं', and attire as 'जैकेट/चोगा'.\n"
                "3. PERIOD TAVERN GRIT & RAW PROFANITY: Translate gritty insults and curses into authentic, earthy Hindustani equivalents. "
                "Use 'गांड' (never 'चूतड़' or 'नितंब'), 'भोसड़ीके', 'लंड', 'रांड / रंडी', 'भड़वा / दल्ला', 'मादरचोद', 'बकचोदी', 'सूअर का पेशाब', "
                "'अंडकोष बधिया करना'. NEVER replace them with polite TV-serial substitutions (do NOT turn 'bastard' into 'दुष्ट' or 'whore' into 'बुरी स्त्री').\n"
                "4. THE 19-TO-21 AMPLIFICATION RULE: When source English dialogue is mild or toned down (19), elevate it to authentic Desi 21 "
                "for visceral gut-punch impact (e.g. 'plough yourself' -> 'गांड मरा' / 'जा अपनी मां चुदा', 'damn you' -> 'तेरी मां की...').\n"
                "5. DESI MUHAVARE & IDIOMS: Transpose English idioms into organic dramatic Hindustani idioms fitting the narrative world and characters "
                "rather than literal word-for-word (e.g. 'bite off more than you can chew' -> 'गांड में दम नहीं और चले आसमान चीरने', 'playing with fire' -> 'सांप के बिल में हाथ डालना').\n"
                "6. TU <-> MAAI-BAAP DYNAMIC POWER SHIFT: Honorific dynamics must reflect power shifts. Arrogant thugs start with dismissive "
                "'तू / अबे', but when physically intimidated, their speech collapses into groveling 'माई-बाप / सरकार / हुज़ूर'.\n"
                "7. URDU KA TARKA ('Aate me Namak'): Infuse a calibrated 10-15% of atmospheric, noir, and sensual Urdu "
                "('जिस्म', 'हवस', 'क़यामत', 'वहशी', 'रूह', 'सन्नाटा', 'ख़ंजर', 'ख़ौफ़', 'ज़ख़्म', 'दस्तक') to give dark fantasy existential weight.\n"
                "8. SOMATIC INTIMACY & EROTICA (HBO / MANTO STANDARD): Render passionate, intimate, or erotic scenes with deep somatic realism: "
                "- STRICTLY BANNED: Clinical forensic lab words ('योनि', 'लिंग', 'स्तन', 'नितंब', 'संभोग') and cheap roadside smut.\n"
                "- MANDATED: Somatic touch, heat, skin friction, breath, and clothing physics ('तपती कमर', 'पसलियों की लचक', 'कांपती उंगलियां', "
                "'बेकाबू सांसें', 'रूह तक उतरना', 'होंठों की तपिश', 'चमड़े की तंग पेटी खोलना', 'सीने पर नाखूनों का धंसना'). "
                "Distinguish between Deep Romantic Passion, Raw Primal Friction, and Seductive Power-Plays.\n"
                "9. VISCERAL COMBAT & GORE: Depict blade strikes, bone fractures, blood spray, and wounds with visceral realism "
                "('लोहा हंसली की हड्डी चीरता हुआ सीने में धंस गया', 'गले से खून का फव्वारा फूटा'). During intense fight scenes, fracture narrative into rapid staccato clauses.\n"
                "10. STRICT ANTI-SANSKRITIZATION & NATURAL SPOKEN REGISTER: ABSOLUTELY FORBIDDEN to use stiff, archaic, or textbook Sanskritized Hindi. "
                "BANNED words: 'युवतियां' (use 'लड़कियां/औरतें'), 'साक्षात काल रूपी' (use 'मौत/बला/राक्षस'), 'दर्पण' (use 'आईना'), "
                "'तर्क' (use 'बात/कारण'), 'विस्मित' (use 'हैरान/दंग'), 'प्रस्थान' (use 'निकलना/चलना'), 'कदाचित' (use 'शायद/मुमकिन है'), "
                "'अविलंब' (use 'फौरन/तुरंत'), 'दृष्टिगोचर' (use 'दिखना/नजर आना'). Use flowing, natural spoken Hindustani of gritty OTT/cinema and Audible originals.\n"
                "11. CANON ADHERENCE & ZERO CHATTER: Output ONLY the translated literary prose in Devanagari Markdown. "
                "Do NOT include translator notes, commentary, disclaimers, or scene overviews."
            )
        else:
            return (
                f"STRICT LITERARY TRANSLATION INVARIANTS ({tradition} - {cadence}):\n"
                "1. SACRED REVERENCE & EMOTIONAL PATHOS: Faithfully honor the author's authentic literary dignity, emotional weight, and classical grace. "
                "Strictly forbid modern vulgar street slang or tapori cuss words.\n"
                "2. SENSE-FOR-SENSE SPOKEN DIALOGUE: Translate sense-for-sense, preserving drama, subtext, humor, and emotional depth for professional voice actors. "
                "Use flowing, natural Hindustani.\n"
                "3. STRICT ANTI-SANSKRITIZATION & SPOKEN NATURALNESS: Ban stiff, archaic textbook Sanskrit words. Use authentic, "
                "natural spoken Hindustani that rolls easily off an actor's tongue. Avoid Doordarshan-style pedantry.\n"
                "4. CANON FIDELITY & WORLD-ANCHOR: Strictly respect the cultural and historical universe of the book. "
                "If the setting is authentic Indian rural/heritage literature (e.g., Premchand): Faithfully celebrate authentic rustic Awadhi/Bhojpuri/Hindustani cadence. "
                "If foreign, never map foreign institutions to Indian village panchayat terms ('पंच जी', 'लंबरदार', 'अशर्फी').\n"
                "5. ADHERE TO GLOSSARY & PRONOUNS: Strictly adhere to the provided Character Glossary for proper noun spellings "
                "and honorific dynamics ('Aap' vs 'Tum' vs 'Tu').\n"
                "6. PRESERVE FORMATTING & ZERO CHATTER: Output ONLY the translated literary prose in Devanagari Markdown without any meta-commentary, notes, or introductions."
            )


def get_default_translation_policy() -> TranslationPolicyConfig:
    return TranslationPolicyConfig()
