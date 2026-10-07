#!/usr/bin/env python3
"""
Audiobook Factory - Room 2 Agent A: Literary Draft Translator.
Performs foundational sense-for-sense dramatic prose translation from English to Hindustani (Devanagari).
Preserves narrative momentum, dramatic stakes, character intentions, and the 70/30 Canon Invariant.
"""

from __future__ import annotations
import os
import json
import time
from typing import Dict, Any, Optional, Callable

from audiobook_factory.logger import logger
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.advisory_lexicon import get_advisory_db
from audiobook_factory.safety import get_dramatic_fiction_framing
from audiobook_factory.sanitizer import validate_and_sanitize_translation, audit_literary_register
from audiobook_factory.llm_client import call_gemini as default_call_gemini


class LiteraryDraftTranslator:
    """Agent A: Master Dramatic Prose & Action Translator.
    Establishes the foundational sense-for-sense translation in cinematic Hindustani Devanagari.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.TRANSLATION)

    def _detect_scene_mode(
        self,
        text_block: str,
        block_title: str,
        book_dna: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Determines the active dramatic scene mode to inject calibrated directives."""
        text_lower = text_block.lower()
        title_lower = block_title.lower()

        dna = book_dna or {}
        fidelity_tier = dna.get("source_fidelity_tier", "RAW_UNRATED")
        cadence = dna.get("regional_dialect_cadence", "Standard Spoken Hindustani")
        profanity_policy = dna.get("profanity_policy", "UNRATED_AUTHENTIC_KASHYAP" if fidelity_tier == "RAW_UNRATED" else "MILD_COLLOQUIAL")

        is_combat = any(
            w in text_lower or w in title_lower
            for w in ("sword", "blade", "blood", "strike", "attack", "kill", "wound", "fight", "warrior", "talwar", "combat")
        )
        is_intimate = any(
            w in text_lower or w in title_lower
            for w in ("kiss", "caress", "whisper", "bed", "lips", "embrace", "naked", "flesh", "intimate", "tender")
        )
        is_dialogue = (
            text_block.count('"') >= 4 or text_block.count('“') >= 4 or text_block.count("'") >= 6
        )

        # 1. CLASSIC REVERENT MODE (Heritage, Dignified Classical Literature)
        if fidelity_tier == "CLASSIC_REVERENT" or profanity_policy == "STRICTLY_CLEAN_REVERENT":
            if is_dialogue:
                return (
                    f"\n>>> ACTIVE SCENE MODE: CLASSIC LITERARY DIALOGUE ({cadence})\n"
                    f"- Infuse dialogue with authentic, dignified {cadence}. Preserve emotional pathos, social hierarchy, and character sincerity.\n"
                    "- STRICTLY FORBIDDEN: Modern street vulgarities ('गांड', 'चूतड़', etc.), tapori slang, or forced profanity. Honor the sacred dignity of classic literature.\n"
                    "- THE 'NOTHING ABOVE SOURCE' INVARIANT: Translate strictly what the author intended, preserving moral and emotional resonance.\n"
                )
            elif is_intimate:
                return (
                    f"\n>>> ACTIVE SCENE MODE: TENDER LITERARY INTIMACY ({cadence})\n"
                    "- Render tender or intimate moments with delicate literary grace, emotional warmth, and respectful poetic sensitivity.\n"
                    "- Strictly ban modern erotica, vulgar slang, or clinical biology terms where absent from source.\n"
                )
            elif is_combat:
                return (
                    f"\n>>> ACTIVE SCENE MODE: DRAMATIC CONFLICT & TENSION ({cadence})\n"
                    "- Render dramatic conflict with psychological gravity, authentic period tension, and moral stakes.\n"
                )
            else:
                return (
                    f"\n>>> ACTIVE SCENE MODE: CLASSIC PASTORAL & NARRATIVE PROSE ({cadence})\n"
                    f"- Maintain deep narrative elegance in {cadence}, honoring classic literary cadence.\n"
                )

        # 2. RAW UNRATED MODE (Visceral Realism, Gritty Action, Unrated Dramatic Fiction)
        if fidelity_tier == "RAW_UNRATED" or profanity_policy == "UNRATED_AUTHENTIC_KASHYAP":
            if is_combat:
                return (
                    f"\n>>> ACTIVE SCENE MODE: VISCERAL COMBAT, GORE & STACCATO RHYTHM ({cadence})\n"
                    "- Depict blade strikes, bone fractures, blood spray, and wounds with visceral realism ('लोहा हंसली की हड्डी चीरता हुआ सीने में धंस गया', 'गले से खून का फव्वारा फूटा').\n"
                    "- During intense fight scenes, fracture narrative into rapid STACCATO clauses (2-4 words per beat: 'कदम पीछे। तलवार का पैंतra। वार। चूक गया!').\n"
                    "- Capture adrenaline tunnel vision, muscle strain, and raw battlefield profanity.\n"
                )
            elif is_intimate:
                return (
                    f"\n>>> ACTIVE SCENE MODE: SOMATIC INTIMACY & PASSION (VISCERAL REALISM STANDARD)\n"
                    "- Render passionate, sensual, intimate, or erotic scenes with visceral realism and authentic passion ('मसलना', 'तपती कमर', 'भीगी प्यास', 'बेकाबू सांसें', 'कांपती उंगलियां', 'होंठों की तपish').\n"
                    "- STRICTLY BANNED: Sterile, clinical biology-textbook words ('योनि', 'लिंग') that sound like high-school exams or hospital autopsies.\n"
                    "- THE 'NOTHING ABOVE SOURCE' INVARIANT: Strictly respect narrative truth. Allow quiet scenes to remain genuinely quiet and tender, without forcing unfiltered passion.\n"
                )
            elif is_dialogue:
                return (
                    f"\n>>> ACTIVE SCENE MODE: HIGH-STAKES DIALOGUE & SOCIAL DYNAMICS ({cadence})\n"
                    "- Translate raw insults and curses into authentic, earthy Hindustani equivalents ('गांड', 'चूतड़', 'बकचोदी', 'सूअर का पेशाब', 'हरामी', 'कमीने').\n"
                    "- 19-TO-21 AMPLIFICATION: When source contains raw vulgarity or curses, do not reduce it to 15. Amplify from 19 to 21 without flinching.\n"
                    "- TU <-> MAAI-BAAP DYNAMIC POWER SHIFT: Honorific dynamics must reflect power shifts. Arrogant characters start with dismissive 'तू / अबे', but when physically intimidated, their speech collapses into groveling 'माई-बाप / सरकार / हुज़ूर'.\n"
                    "- NATURAL DIALOGUE & IDIOMS: Transpose source idioms into organic dramatic Hindustani idioms fitting the narrative world and characters.\n"
                )
            else:
                return (
                    f"\n>>> ACTIVE SCENE MODE: ATMOSPHERIC LORE & WORLDBUILDING ({cadence})\n"
                    "- Maintain authentic literary voice and atmospheric sensory depth.\n"
                    "- CONTEXTUAL HINDUSTANI ('Aate me Namak'): Infuse contextual, evocative Urdu vocabulary ('रूह', 'सन्नाटा', 'ख़ौफ़', 'ज़ख़्म', 'दस्तक', 'सुकून') where scene mood and world atmosphere justify it, without forcing an artificial quota.\n"
                )

        # 3. DRAMATIC MODERN (Default)
        if is_combat:
            return (
                f"\n>>> ACTIVE SCENE MODE: CINEMATIC ACTION ({cadence})\n"
                "- Depict physical combat and high-stakes tension with clarity, visceral momentum, and cinematic rhythm.\n"
            )
        elif is_intimate:
            return (
                f"\n>>> ACTIVE SCENE MODE: EMOTIONAL INTIMACY & SUBTEXT ({cadence})\n"
                "- Render emotional vulnerability, romantic tension, and unspoken longing with natural sensitivity.\n"
            )
        elif is_dialogue:
            return (
                f"\n>>> ACTIVE SCENE MODE: NATURAL CONVERSATIONAL DIALOGUE ({cadence})\n"
                "- Translate spoken dialogue with organic cadence, sharp comedic/dramatic timing, and realistic subtext.\n"
            )
        else:
            return (
                f"\n>>> ACTIVE SCENE MODE: ATMOSPHERIC NARRATIVE PROSE ({cadence})\n"
                "- Maintain engaging narrative flow with natural sensory texture and evocative vocabulary.\n"
            )

    def translate_draft(
        self,
        text_block: str,
        glossary: Dict[str, Any],
        block_title: str = "",
        preceding_context: str = "",
        adult_mode: bool = True,
        book_dna: Optional[Dict[str, Any]] = None,
        call_llm_fn: Optional[Callable[..., str]] = None,
    ) -> str:
        """Generates the foundational literary Hindi translation draft."""
        model = self._resolve_model()
        eff_dna = book_dna or (glossary.get("book_dna") if isinstance(glossary, dict) else None)
        scene_directives = self._detect_scene_mode(text_block, block_title, book_dna=eff_dna)

        tier = eff_dna.get("source_fidelity_tier", "RAW_UNRATED" if adult_mode else "CLASSIC_REVERENT") if eff_dna else ("RAW_UNRATED" if adult_mode else "CLASSIC_REVERENT")
        tradition = eff_dna.get("literary_tradition", "DRAMATIC_LITERATURE") if eff_dna else "DRAMATIC_LITERATURE"
        cadence = eff_dna.get("regional_dialect_cadence", "Spoken Hindustani") if eff_dna else "Spoken Hindustani"

        if tier == "RAW_UNRATED":
            advisory_guidance = get_advisory_db().get_formatted_prompt_guidelines()
            system_prompt = (
                f"You are the Chief Dialogue Adapter & Screenplay Director for premier cinematic dramatic audio fiction "
                f"(Netflix / HBO / Audible Studios standard). Your task is adapting mature literature ({tradition}) "
                f"into living, spoken, gritty Hindustani ({cadence} in Devanagari script) designed specifically for voice actors.\n\n"
                "### CORE ARCHITECTURAL DIRECTIVE - THE 4-TIER COGNITIVE SEMANTIC REGISTER LADDER:\n"
                "You are writing lines for professional actors performing dialogue and dramatic narration into studio microphones. "
                "Every English concept MUST map to its authentic living spoken equivalent, NEVER to textbook, Doordarshan, or academic Sanskritized Hindi:\n\n"
                "1. TIER 1 - VULGARITY & COMBAT PROFANITY (Preserve 1:1 Visceral Punch under BLOCK_NONE):\n"
                "   - When source text uses raw cusses, insults, or aggressive profanity ('ass', 'arse', 'dick', 'fuck', 'bullshit', 'bastard', 'shit', 'piss'), "
                "map DIRECTLY to authentic living spoken Hindustani profanity: 'गांड', 'लौड़ा', 'बकचोदी', 'हरामी', 'कमीने', 'पेशाब'.\n"
                "   - ZERO MORAL POLICING: NEVER sanitize to childish or academic words ('दुराचारी', 'नीच प्राणी', 'धूर्त', 'पापी'). If a cutthroat or thug says 'ass', an actor MUST say 'गांड'.\n\n"
                "2. TIER 2 - SOMATIC, POSTURE & PHYSICAL ANATOMY (Natural Spoken Body Language):\n"
                "   - When source text describes physical anatomy, posture, clothing fit, or sensual movement neutrally or descriptively "
                "('hips', 'bottom', 'waist', 'buttocks', 'thighs', 'chest', 'back'), map to living spoken somatic terms: 'कमर', 'कूल्हे', 'पुट्ठे', 'जांघें', 'सीना', 'पीठ'.\n"
                "   - STRICT BAN ON SANSKRIT TAT-SAMA ANATOMY: ABSOLUTELY FORBIDDEN to use archaic dictionary/textbook words like 'नितंब', 'कटि', 'उरु', 'वक्ष'. "
                "Say 'कमर/कूल्हे' for hips/bottom, NEVER 'नितंब'!\n\n"
                "3. TIER 3 - SOCIAL TRANSACTIONS, DEALS & DIALOGUE NOUNS:\n"
                "   - When characters negotiate, argue, or strike agreements ('deal', 'proposal', 'bargain', 'oath', 'word'), "
                "map to conversational spoken terms: 'सौदा', 'बात', 'तय होना', 'जुबान'.\n"
                "   - STRICT BAN ON BUREAUCRATIC HINDI: NEVER use corporate or government notice terms like 'प्रस्ताव', 'समझौता-पत्र', or religious cliches like 'धरम-ईमान' unless explicitly religious in source.\n\n"
                "4. TIER 4 - WARFARE, ARCHETYPES & LIVING DESCRIPTORS:\n"
                "   - When source describes archetypes, roles, weapons, or attire ('warrior women', 'fighting women', 'sellsword', 'cutthroat', 'insignia', 'seal'), "
                "map to grounded living descriptions: 'लड़ाकू औरतें / लड़ाकू महिलाएं', 'किराए के लड़ाके / हत्यारे', 'कातिल / कसाई', 'शाही मुहर / निशान'.\n"
                "   - STRICT BAN ON MYTHOLOGICAL TROPES: NEVER use textbook poetry tropes like 'वीरांगनाएं' for gritty combat women, or 'राजचिह्न' for an insignia!\n\n"
                "5. SPOKEN DISCOURSE VERBS (Actable Studio Cadence):\n"
                "   - Active living verbs: 'सामने आना', 'दिखना', 'नज़र आना', 'शायद', 'फौरन/तुरंत', 'निकलना'.\n"
                "   - BANNED: 'दृष्टिगोचर होना', 'कदाचित', 'अविलंब', 'प्रस्थान करना', 'विस्मित होना'.\n\n"
                "6. UNIVERSAL IDIOMATIC TRANSPOSITION ('PINCH OF SALT' FRAMEWORK):\n"
                "   - Never translate English idioms literally (anti-calque: e.g. NEVER translate 'as sure as eggs is eggs' as 'अंडे अंडे हैं', or 'kick the bucket' as 'बाल्टी को लात मारना').\n"
                "   - Transpose figurative meaning sense-for-sense into Universal Spoken Hindustani Idioms (Category A: 'लिख के ले लो', 'सूरज का ढलना तय है', 'मौत को दावत देना', 'हाथ साफ़ करना', 'खाल उधेड़ना', 'टांग अड़ाना').\n"
                "   - Strictly ban culturally bound Indian village/panchayat clichés (Category B: 'गंगा नहाना', 'पंचों का फैसला', 'नाच न जाने आँगन टेढ़ा').\n"
                "   - Maintain the 'Aate me Namak' balance: concentrate 85-90% of idiomatic punch in spoken dialogue and combat beats.\n\n"
                "7. THE 70/30 ANTI-PARODY & WORLD-ANCHOR INVARIANT:\n"
                "   - Maintain 70% Canon Sacredness / 30% Sensory Desi Amplification. "
                "If the setting is European, medieval fantasy, foreign, or sci-fi: STRICTLY FORBIDDEN to use Indian rural administrative "
                "or caste/panchayat vocabulary ('पंच जी', 'लंबरदार', 'पटवारी', 'फतुही', 'अशर्फी'). "
                "Translate civic titles as 'एल्डरमैन/मेयर/नगर प्रमुख', currency as 'सिक्के/मुद्राएं/स्वर्ण मुद्राएं', and attire as 'जैकेट/चोगा'.\n\n"
                "8. OUTPUT INVARIANT & ZERO CHATTER:\n"
                "   - Output ONLY the translated passage in Devanagari Markdown without any meta-commentary, notes, disclaimers, or conversational introductions.\n\n"
                "### CRITICAL TRI-PARTITE ENTITY & TAT-SAMA NON-NEGOTIABLES:\n"
                "- HERALDIC MONIKERS & NICKNAMES: Transliterate phonetically into Devanagari. NEVER translate literally into Hindi!\n"
                "  * English: 'Silver Falcon' -> Devanagari: 'सिल्वर फाल्कन' (STRICTLY BANNED: 'चांदी का बाज़')\n"
                "  * English: 'Night Raven' -> Devanagari: 'नाइट रेवेन' (STRICTLY BANNED: 'रात का कौवा')\n"
                "- SOMATIC & BODY ADJECTIVES: Use living spoken Hindi!\n"
                "  * 'bare/naked arms' -> 'नंगी बाँहें / खुली बाँहें' (STRICTLY BANNED: 'नग्न भुजाएँ', 'नग्न थीं', 'अनावृत')\n"
                "  * 'naked' -> 'नंगा / नंगी / खुले' (NEVER 'नग्न' or 'अनावृत')\n"
                "  * 'young women / maidens' -> 'जवान औरतें / लड़कियाँ' (NEVER 'युवतियाँ')\n\n"
                "### FEW-SHOT IN-CONTEXT EXEMPLARS (GOLD STANDARD TARGET VS BANNED FLUFF):\n\n"
                "[EXEMPLAR 1 - HERALDIC MONIKERS & PROPER NAMES]\n"
                "- English Source: 'My name is Sterling, also known as Silver Falcon. And these two warriors are my escort, Elena and Morwen.'\n"
                "- BANNED / FLIMSY (Literal Calque): 'मेरा नाम स्टर्लिंग है, जिसे चांदी का बाज़ भी कहा जाता है। और ये दो सुंदरियाँ मेरी अनुरक्षक हैं—एलेना और मॉरवेन।'\n"
                "- GOLD STANDARD SPOKEN HINDUSTANI: 'मेरा नाम स्टर्लिंग है, लोग मुझे \\'सिल्वर फाल्कन\\' भी कहते हैं। और ये दोनों ख़ूबसूरत लड़कियाँ मेरी अंगरक्षक हैं—एलेना और मॉरवेन।'\n\n"
                "[EXEMPLAR 2 - SOMATIC / BODY DESCRIPTIONS VS SANSKRIT TAT-SAMA]\n"
                "- English Source: 'Above their iron mail gloves, their supple arms were bare, smooth and tanned brown.'\n"
                "- BANNED / FLIMSY (Tat-sama Textbook): 'लोहे के दस्तानों से ऊपर उनकी लचीली भुजाएँ नग्न थीं, चिकनी और धूप में तपी हुई।'\n"
                "- GOLD STANDARD SPOKEN HINDUSTANI: 'लोहे के दस्तानों से ऊपर उनकी लचीली, नंगी बाँहें साफ़ दिख रही थीं—एकदम चिकनी और धूप में पकी तांबई रंगत।'\n\n"
                "[EXEMPLAR 3 - VISCERAL COMBAT GORE & STACCATO PACING]\n"
                "- English Source: 'The cutthroat lunged with his dagger. Edward sidestepped, slashing open the man\\'s throat; blood sprayed across the wooden bar.'\n"
                "- BANNED / FLIMSY (Academic / Sanitized): 'उस दुराचारी ने खंजर से प्रहार किया। एडवर्ड एक ओर हट गया और उसके कंठ को विदीर्ण कर दिया; काष्ठ के तख्ते पर रक्त बिखर गया।'\n"
                "- GOLD STANDARD SPOKEN HINDUSTANI: 'कातिल ने खंजर से सीधा वार किया। एडवर्ड बिजली की तरह एक तरफ़ हटा और एक ही झटके में उसकी गर्दन चीर दी; लकड़ी की मेज़ पर ख़ून का फव्वारा छूट पड़ा।'\n\n"
                "[EXEMPLAR 4 - HONORIFIC DYNAMIC SHIFT (TU TO MAAI-BAAP)]\n"
                "- English Source: '\\'Hand over your coin, mutant,\\' the thug snarled. But once the silver blade touched his adam\\'s apple, he fell to his knees: \\'Please, sir, mercy! I have children!\\''\n"
                "- BANNED / FLIMSY: '\\'अपने सिक्के मुझे दो, राक्षस,\\' उसने कहा। लेकिन जब तलवार लगी: \\'कृपया महोदय, दया करें! मेरे बच्चे हैं!\\''\n"
                "- GOLD STANDARD SPOKEN HINDUSTANI: '\\'अपने सिक्के इधर फेंक, कमीने,\\' वो गुंडा गुर्राया। लेकिन जैसे ही चांदी की धार उसके गले की नस पर टिकी, वो धड़ाम से घुटनों पर आ गिरा: \\'माई-बाप... रहम! छोड़ दीजिए हुज़ूर, मेरे छोटे-छोटे बच्चे हैं!\\''\n\n"
                f"{scene_directives}\n"
                f"{advisory_guidance}"
            )
        else:
            system_prompt = (
                f"You are the Senior Dialogue Adapter & Screenplay Director for classic dramatic audio fiction "
                f"(Audible Studios standard). Your task is adapting classic literature ({tradition}) "
                f"into living, natural spoken Hindustani ({cadence} in Devanagari script) designed for voice actors.\n\n"
                "### CORE ARCHITECTURAL DIRECTIVE - SPOKEN NATURALNESS & SENSORY CADENCE:\n"
                "1. ACTABLE DIALOGUE: Write living, natural spoken Hindustani that rolls effortlessly off an actor's tongue. Avoid Doordarshan-style pedantry.\n"
                "2. NO TAT-SAMA TEXTBOOK DICTION: Use 'कमर/कूल्हे' (never 'नितंब'), 'लड़ाकू औरतें' (never 'वीरांगनाएं'), 'सौदा/बात' (never 'प्रस्ताव'), 'दिखना' (never 'दृष्टिगोचर').\n"
                "3. UNIVERSAL IDIOMATIC TRANSPOSITION: Transpose figurative idioms sense-for-sense into dignified universal Hindustani idioms ('जुबान की कीमत', 'मौत का साया'); strictly ban literal calques and Indian village panchayat clichés.\n"
                "4. DIGNITY WITHOUT SANITIZATION: Honor the author's authentic emotional pathos and dramatic stakes without modern tapori vulgarity.\n"
                "5. WORLD-ANCHOR: Do not map foreign institutions to Indian village panchayat terms ('पंच जी', 'लंबरदार', 'अशर्फी').\n"
                "6. OUTPUT INVARIANT: Output ONLY the translated passage in Devanagari Markdown with zero chatter.\n\n"
                "### CRITICAL TRI-PARTITE ENTITY & TAT-SAMA NON-NEGOTIABLES:\n"
                "- HERALDIC MONIKERS: Transliterate phonetically into Devanagari (e.g. 'Silver Falcon' -> 'सिल्वर फाल्कन'; NEVER 'चांदी का बाज़')!\n"
                "- SOMATIC ADJECTIVES: Use spoken 'नंगी/खुली बाँहें' (NEVER 'नग्न' or 'अनावृत')!\n\n"
                f"{scene_directives}"
            )

        # Dramatic fiction framing to defeat false-positive safety moderation
        book_title = None
        book_author = None
        if isinstance(glossary, dict):
            meta = glossary.get("book_metadata") or {}
            book_title = meta.get("title") or glossary.get("title")
            book_author = meta.get("author") or glossary.get("author")

        fiction_framing = get_dramatic_fiction_framing(title=book_title, author=book_author)
        system_prompt = fiction_framing + system_prompt

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
        t0 = time.time()
        if call_llm_fn:
            raw = call_llm_fn(prompt=prompt, system_instruction=system_prompt, model=model).strip()
        else:
            raw = default_call_gemini(
                prompt=prompt,
                system_instruction=system_prompt,
                task_type=TaskType.TRANSLATION,
                response_mime_type="text/plain",
                max_output_tokens=32768,
                max_retries=8,
                model=model,
                return_raw_text=True,
                thinking_budget=1024,
            ).strip()

        elapsed = time.time() - t0
        logger.info(f"  [LiteraryDraftTranslator] Draft generated in {elapsed:.2f}s ({len(raw)} chars)")

        is_valid, cleaned, reason = validate_and_sanitize_translation(raw, is_hindi=True)
        if not is_valid:
            logger.warning(f"  [LiteraryDraftTranslator] Sanitizer guardrail notice: {reason}")
            cleaned = cleaned if cleaned else raw

        _, cleaned, warnings = audit_literary_register(cleaned)
        for w in warnings:
            logger.debug(f"    [Draft Literary Linter] {w}")

        return cleaned
