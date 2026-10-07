#!/usr/bin/env python3
"""
Audiobook Factory - Room 2 Agent C: Subtext & Idiom Dramaturge.
Injects earthy Hindustani metaphors, rustic dramatic grit, and unsparing literary authenticity
in the tradition of visceral dramatic realism and gritty cinematic fiction, enforcing the 19-to-21 Amplification rule.
"""

from __future__ import annotations
import os
import json
import time
from typing import Dict, Any, Optional, Callable

from audiobook_factory.logger import logger
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing
from audiobook_factory.sanitizer import validate_and_sanitize_translation
from audiobook_factory.llm_client import call_gemini as default_call_gemini


class SubtextAndIdiomDramaturge:
    """Agent C: Earthy Metaphor, Rustic Grit & Dramatic Subtext Dramaturge.
    Elevates dialogue and descriptive subtext with authentic Hindustani flavor without parody.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.TRANSLATION)

    def enrich_idioms_and_subtext(
        self,
        source_text: str,
        cadence_hindi: str,
        glossary: Dict[str, Any],
        block_title: str = "",
        preceding_context: str = "",
        book_dna: Optional[Dict[str, Any]] = None,
        call_llm_fn: Optional[Callable[..., str]] = None,
    ) -> str:
        """Enriches the text with earthy Hindustani idioms, rustic grit, and authentic subtext."""
        model = self._resolve_model()

        book_title = None
        book_author = None
        if isinstance(glossary, dict):
            meta = glossary.get("book_metadata") or {}
            book_title = meta.get("title") or glossary.get("title")
            book_author = meta.get("author") or glossary.get("author")

        fiction_framing = get_dramatic_fiction_framing(title=book_title, author=book_author)

        eff_dna = book_dna or (glossary.get("book_dna") if isinstance(glossary, dict) else None)
        tier = eff_dna.get("source_fidelity_tier", "RAW_UNRATED") if eff_dna else "RAW_UNRATED"
        tradition = eff_dna.get("literary_tradition", "DRAMATIC_LITERATURE") if eff_dna else "DRAMATIC_LITERATURE"
        cadence = eff_dna.get("regional_dialect_cadence", "Spoken Hindustani") if eff_dna else "Spoken Hindustani"

        if tier == "CLASSIC_REVERENT":
            system_instruction = (
                fiction_framing +
                f"You are a master Dramaturge and Literary Dialect Stylist specializing in {tradition}.\n"
                f"Your task is to enrich a spoken Hindi audiobook passage with authentic regional cadence "
                f"and emotional subtext in {cadence}.\n\n"
                "Key Creative Principles:\n"
                "1. AUTHENTIC REGIONAL CADENCE & SUBTEXT: Infuse organic phrasing and emotional subtext that fit the author's world naturally.\n"
                "2. UNIVERSAL IDIOMATIC TRANSPOSITION (CATEGORY A VS CATEGORY B):\n"
                "   - CATEGORY A (UNIVERSAL DIGNIFIED IDIOMS - GREEN-LIT): Transpose emotional tropes into universal human idioms "
                "('जुबान की कीमत', 'मौत का साया मंडराना', 'सांसें थम जाना', 'सूरज का ढलना तय होना').\n"
                "   - CATEGORY B (BANNED LOCAL TROPES): Strictly ban idioms rooted in Indian geography, religion, or village panchayats "
                "('गंगा नहाना', 'चार धाम', 'पंचों का फैसला', 'नाच न जाने आँगन टेढ़ा').\n"
                "3. SACRED REVERENCE (NOTHING ABOVE SOURCE): STRICTLY FORBIDDEN to inject modern street profanity, tapori cuss words, or forced vulgarity. Honor the dignity and pathos of classic literature.\n"
                "4. WORLD-ANCHOR & CANON FIDELITY: STRICTLY FORBIDDEN to inject out-of-place Indian village terms ('पंच जी', 'लंबरदार', 'अशर्फी') into foreign or classical literature. Honor the cultural universe of the author.\n"
                "5. SENSORY & ATMOSPHERIC VOCABULARY: Contextually infuse evocative vocabulary where scene mood justifies it.\n"
                "6. OUTPUT INVARIANT: Retain all dialogue markers, paragraph breaks, and proper nouns. Output ONLY the enriched passage in Devanagari Markdown with zero meta-commentary."
            )
        else:
            system_instruction = (
                fiction_framing +
                f"You are a master Dramaturge and Literary Dialect Stylist in the dramatic tradition of "
                f"visceral dramatic realism and gritty cinematic fiction ({tradition}).\n"
                f"Your task is to enrich a spoken Hindi audiobook passage with authentic Hindustani cadence, "
                f"rustic grit, and cinematic subtext ({cadence}).\n\n"
                "Key Creative Principles:\n"
                "1. AUTHENTIC HINDUSTANI CADENCE & ANTI-SANSKRITIZATION: Eliminate stiff, textbook Sanskrit roots or Doordarshan-style bookish words "
                "('नितंब' -> use 'कमर/कूल्हे', 'वीरांगनाएं' -> use 'लड़ाकू औरतें', 'प्रस्ताव' -> use 'सौदा/बात', 'युवतियां' -> use 'लड़कियां/औरतें', 'विस्मित' -> 'हैरान'). "
                "Use natural, living dramatic Hindustani spoken by real actors on gritty OTT/cinema productions.\n"
                "2. UNIVERSAL IDIOMATIC TRANSPOSITION ('PINCH OF SALT' FRAMEWORK - CATEGORY A VS CATEGORY B):\n"
                "   - CATEGORY A: UNIVERSAL SPOKEN IDIOMS (GREEN-LIT PINCH OF SALT):\n"
                "     When foreign/English dialogue has figurative, sarcastic, threatening, or emotional expressions, NEVER translate words literally (anti-calque).\n"
                "     Transpose them sense-for-sense into universal spoken Hindustani idioms rooted in human psychology:\n"
                "     * Certainty & Inevitability: 'लिख के ले लो', 'खेल ख़त्म', 'पत्थर की लकीर', 'सूरज का ढलना तय है'\n"
                "     * Danger & Mortality: 'मौत के मुँह में कूदना', 'मौत को दावत देना', 'सांसें हलक में अटकना'\n"
                "     * Greed & Exploitation: 'हाथ साफ़ करना', 'राल टपकना', 'हाथ मारना'\n"
                "     * Conflict, Threats & Defiance: 'खाल उधेड़ना', 'टांग अड़ाना', 'धूल चटाना', 'मिट्टी में मिलाना'\n"
                "     * Integrity & Deals: 'जुबान देना', 'बात का पक्का', 'सौदा तय होना'\n"
                "     * Silence & Fear: 'मुँह पर ताला लगाना', 'हलक सूखना'\n"
                "   - CATEGORY B: CULTURALLY BOUND LOCAL TROPES (STRICTLY BANNED IN FOREIGN/FANTASY WORLDS):\n"
                "     STRICTLY FORBIDDEN to inject clichés, idioms, or metaphors tied to Indian geography, religion, caste, or village panchayats:\n"
                "     * Religious/Geographic: 'गंगा नहाना', 'चार धाम', 'पाप धोना', 'यमराज का बुलावा'\n"
                "     * Village/Administrative: 'पंचों का फैसला', 'पटवारी', 'लंबरदार', 'दूध का दूध और पानी का पानी'\n"
                "     * Parody Proverbs: 'नाच न जाने आँगन टेढ़ा', 'अंधों में काना राजा', 'बिल्ली रास्ता काट गई', 'ऊंट के मुँह में जीरा'\n"
                "   - THE 'AATE MEIN NAMAK' RULE:\n"
                "     Concentrate 85-90% of idiomatic punch in character dialogue, threats, banter, and tense exchanges. "
                "In narrative exposition, preserve atmospheric tone ('सन्नाटा', 'तारीकी', 'ख़ौफ़') without overloading with folksy proverbs.\n"
                "3. WORLD-ANCHOR & ANTI-PARODY INVARIANT (CRITICAL): STRICTLY FORBIDDEN to turn foreign, European, medieval, or fantasy works "
                "into an Indian village panchayat farce. NEVER inject rural Indian administrative terms or cliches "
                "('पंच जी', 'लंबरदार', 'पटवारी', 'फतुही', 'अशर्फी'). "
                "Civic magistrates/aldermen must remain 'एल्डरमैन/मेयर/नगर प्रमुख', currency remains 'सिक्के/मुद्राएं', and attire remains 'जैकेट/चोगा'. "
                "Honor the world-building, tone, and authorial soul of the original work.\n"
                "4. 19-TO-21 AMPLIFICATION: When the original source has raw vulgarity, insults, or curses "
                "('गांड', 'चूतड़', 'हरामी', 'कमीने', 'बकचोदी', 'सूअर का पेशाब'), do NOT water them down. "
                "Amplify with rustic, gritty authenticity (19 to 21) without flinching.\n"
                "5. SENSORY & ATMOSPHERIC VOCABULARY: Contextually infuse evocative Urdu/Hindustani loan words "
                "('रूह', 'सन्नाटा', 'ख़ौफ़', 'ज़ख़्म', 'दस्तक', 'सुकून', 'शिकस्त', 'हसरत') where scene mood justifies it "
                "('Aate me Namak' rule — organic seasoning, not artificial purple prose).\n"
                "6. THE 'NOTHING ABOVE SOURCE' INVARIANT: Respect narrative truth. If a scene is somber, tender, "
                "or intellectual, do NOT force vulgarity or comedic tapori banter. Maintain high literary taste.\n"
                "7. OUTPUT INVARIANT: Retain all dialogue markers, paragraph breaks, and proper nouns. "
                "Output ONLY the enriched passage in Devanagari Markdown with zero meta-commentary or conversational intros."
            )

        prompt = f"""### ORIGINAL ENGLISH SOURCE ({block_title}):
\"\"\"
{source_text}
\"\"\"

### CURRENT HINDI TEXT TO ENRICH:
\"\"\"
{cadence_hindi}
\"\"\"

Enrich the passage with authentic Hindustani idioms, dramatic subtext, and rustic grit.
Output ONLY the enriched Devanagari Markdown:
"""
        t0 = time.time()
        try:
            if call_llm_fn:
                raw = call_llm_fn(prompt=prompt, system_instruction=system_instruction, model=model).strip()
            else:
                raw = default_call_gemini(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    task_type=TaskType.TRANSLATION,
                    response_mime_type="text/plain",
                    max_output_tokens=32768,
                    max_retries=6,
                    model=model,
                    return_raw_text=True,
                    thinking_budget=1024,
                ).strip()

            elapsed = time.time() - t0
            logger.info(f"  [SubtextAndIdiomDramaturge] Enriched in {elapsed:.2f}s ({len(raw)} chars)")

            is_valid, cleaned, reason = validate_and_sanitize_translation(raw, is_hindi=True)
            if not is_valid:
                logger.warning(f"  [SubtextAndIdiomDramaturge] Sanitizer warning: {reason}. Preserving cadence text.")
                return cadence_hindi

            # Guard against truncation
            if len(cleaned.split()) < len(cadence_hindi.split()) * 0.70:
                logger.warning("  [SubtextAndIdiomDramaturge] Enrichment pass caused truncation. Preserving cadence text.")
                return cadence_hindi

            return cleaned

        except Exception as e:
            logger.warning(f"  [!] SubtextAndIdiomDramaturge error: {e}. Preserving cadence text.")
            return cadence_hindi
