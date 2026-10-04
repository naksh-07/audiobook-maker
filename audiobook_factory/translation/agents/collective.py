#!/usr/bin/env python3
"""
Audiobook Factory - Room 2: Multi-Agent Translation Collective Coordinator.
Orchestrates the 4 specialized translation agents into an integrated creative room:
1. LiteraryDraftTranslator: Sense-for-sense dramatic narrative & scene mode translation.
2. HindustaniCadenceSpecialist: Spoken prosody, dialogue breath pauses, and honorific shifts.
3. SubtextAndIdiomDramaturge: Earthy Hindustani metaphors, rustic grit & 19-to-21 amplification.
4. TranslationQualityCritic: Canon consistency audit, anti-omission check & reflection repair.
"""

from __future__ import annotations
import os
import time
from typing import Dict, Any, Optional, Callable, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.model_manager import get_model_manager, TaskType
from .draft_translator import LiteraryDraftTranslator
from .cadence_specialist import HindustaniCadenceSpecialist
from .idiom_dramaturge import SubtextAndIdiomDramaturge
from .translation_critic import TranslationQualityCritic


class MultiAgentTranslationCollective:
    """Coordinates the 4-agent translation collective across the 100+ key pool."""

    def __init__(self, model: Optional[str] = None):
        self.model = model
        self.draft_translator = LiteraryDraftTranslator(model=model)
        self.cadence_specialist = HindustaniCadenceSpecialist(model=model)
        self.idiom_dramaturge = SubtextAndIdiomDramaturge(model=model)
        self.quality_critic = TranslationQualityCritic(model=model)

    def translate_block(
        self,
        text_block: str,
        glossary: Dict[str, Any],
        block_title: str = "",
        preceding_context: str = "",
        adult_mode: bool = True,
        call_llm_fn: Optional[Callable[..., str]] = None,
    ) -> str:
        """Runs the 4-stage translation collective on an English text block."""
        t_start = time.time()
        words = len(text_block.split())
        logger.info(f"[*] [Translation Collective] Commencing 4-Agent Translation for '{block_title}' ({words} words)...")

        # -------------------------------------------------------------
        # Pass 1: Literary Draft Translator (Foundational Sense-for-Sense)
        # -------------------------------------------------------------
        logger.info(f"  [Room 2 Pass 1/4] LiteraryDraftTranslator running...")
        pass1_draft = self.draft_translator.translate_draft(
            text_block=text_block,
            glossary=glossary,
            block_title=block_title,
            preceding_context=preceding_context,
            adult_mode=adult_mode,
            call_llm_fn=call_llm_fn,
        )

        if not pass1_draft or len(pass1_draft.strip()) < 10:
            raise RuntimeError(f"Pass 1 LiteraryDraftTranslator returned empty translation for {block_title}")

        # -------------------------------------------------------------
        # Pass 2: Hindustani Cadence Specialist (Spoken Prosody & Honorifics)
        # -------------------------------------------------------------
        logger.info(f"  [Room 2 Pass 2/4] HindustaniCadenceSpecialist running...")
        try:
            pass2_cadence = self.cadence_specialist.refine_cadence(
                source_text=text_block,
                draft_hindi=pass1_draft,
                glossary=glossary,
                block_title=block_title,
                preceding_context=preceding_context,
                call_llm_fn=call_llm_fn,
            )
        except Exception as e:
            logger.warning(f"  [!] Pass 2 HindustaniCadenceSpecialist notice: {e}. Falling back to Pass 1 draft.")
            pass2_cadence = pass1_draft

        # -------------------------------------------------------------
        # Pass 3: Subtext & Idiom Dramaturge (Earthy Metaphor & Rustic Grit)
        # -------------------------------------------------------------
        logger.info(f"  [Room 2 Pass 3/4] SubtextAndIdiomDramaturge running...")
        try:
            pass3_enriched = self.idiom_dramaturge.enrich_idioms_and_subtext(
                source_text=text_block,
                cadence_hindi=pass2_cadence,
                glossary=glossary,
                block_title=block_title,
                preceding_context=preceding_context,
                call_llm_fn=call_llm_fn,
            )
        except Exception as e:
            logger.warning(f"  [!] Pass 3 SubtextAndIdiomDramaturge notice: {e}. Falling back to Pass 2 cadence.")
            pass3_enriched = pass2_cadence

        # -------------------------------------------------------------
        # Pass 4: Translation Quality Critic (Canon Inspection & Reflection)
        # -------------------------------------------------------------
        logger.info(f"  [Room 2 Pass 4/4] TranslationQualityCritic auditing...")
        try:
            final_certified, report = self.quality_critic.audit_and_certify(
                source_text=text_block,
                hindi_text=pass3_enriched,
                glossary=glossary,
                block_title=block_title,
                call_llm_fn=call_llm_fn,
            )
        except Exception as e:
            logger.warning(f"  [!] Pass 4 TranslationQualityCritic notice: {e}. Preserving Pass 3 text.")
            final_certified = pass3_enriched

        total_elapsed = time.time() - t_start
        logger.info(f"[+] [Translation Collective] Certified '{block_title}' in {total_elapsed:.1f}s ({len(final_certified)} chars)")
        return final_certified


_collective_instance: Optional[MultiAgentTranslationCollective] = None


def get_translation_collective(model: Optional[str] = None) -> MultiAgentTranslationCollective:
    """Returns singleton translation collective instance."""
    global _collective_instance
    if _collective_instance is None or (model and _collective_instance.model != model):
        _collective_instance = MultiAgentTranslationCollective(model=model)
    return _collective_instance
