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

        # 1. CLASSIC REVERENT MODE (Premchand, Tagore, Classic Literature)
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

        # 2. RAW UNRATED MODE (Manto, Sapkowski, George R.R. Martin, Crime/Dark Fantasy)
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
                    f"\n>>> ACTIVE SCENE MODE: SOMATIC INTIMACY & PASSION (MANTO STANDARD)\n"
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
                f"You are a master literary translator and audio drama director adapting mature literature "
                f"({tradition}) into cinematic, spoken Hindustani ({cadence} in Devanagari script).\n\n"
                "Strict Translation Invariants:\n"
                "1. LITERARY ANTI-BOWDLERIZATION MANDATE: NEVER sanitize, soften, or bowdlerize raw violence, visceral combat, "
                "gritty dialogue, or mature intimacy present in the source text. Faithfully represent the author's authentic dramatic truth.\n"
                "2. THE 70/30 ANTI-PARODY INVARIANT: Maintain a strict 70% Canon Sacredness / 30% Sensory Desi Amplification ratio. "
                "Never replace the book's universe, lore, proper nouns, or geographic names with arbitrary mythology or tapori spoofs.\n"
                "3. SENSE-FOR-SENSE SPOKEN DIALOGUE: Never do literal word-for-word translation. Translate sense-for-sense, preserving drama, "
                "subtext, humor, and emotional depth for professional voice actors. Use flowing, cinematic Hindustani.\n"
                "4. ADHERE TO GLOSSARY & ZERO CHATTER: Strictly adhere to the provided Character Glossary for proper noun spellings. "
                "Output ONLY the translated passage in Devanagari Markdown without any meta-commentary, notes, disclaimers, or conversational introductions.\n"
                f"{scene_directives}\n"
                f"{advisory_guidance}"
            )
        else:
            system_prompt = (
                f"You are a master literary translator and audio drama director adapting classic literature "
                f"({tradition}) into cinematic, spoken Hindustani ({cadence} in Devanagari script).\n\n"
                "Strict Translation Invariants:\n"
                "1. SENSE-FOR-SENSE SPOKEN DIALOGUE: Translate sense-for-sense, preserving drama, subtext, humor, "
                "and emotional depth for professional voice actors. Use flowing, natural Hindustani.\n"
                "2. SACRED REVERENCE & ZERO BOWDLERIZATION: Strictly forbid modern vulgar street slang or tapori cuss words. "
                "Faithfully honor the author's authentic literary dignity, emotional pathos, and regional voice.\n"
                "3. ADHERE TO GLOSSARY & PRONOUNS: Strictly adhere to the provided Character Glossary for proper noun spellings "
                "and honorific dynamics ('Aap' vs 'Tum' vs 'Tu').\n"
                "4. PRESERVE FORMATTING & ZERO CHATTER: Keep headings and dialogue quotation marks intact. Output ONLY the translated "
                "passage in Devanagari Markdown without any meta-commentary, notes, disclaimers, or conversational introductions.\n"
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
                max_output_tokens=16384,
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
