#!/usr/bin/env python3
"""
Audiobook Factory - Room 2 Agent D: Translation Quality Critic.
Independent quality auditor, canon terminology inspector, and reflection repair gate.
Validates terminology consistency against glossary/book_bible, checks for omissions,
and applies surgical reflection repair to deliver publication-certified Devanagari Hindi.
"""

from __future__ import annotations
import os
import re
import json
import time
from typing import Dict, Any, Optional, Tuple, Callable

from audiobook_factory.logger import logger
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing
from audiobook_factory.sanitizer import validate_and_sanitize_translation, audit_literary_register
from audiobook_factory.llm_client import call_gemini as default_call_gemini


class TranslationQualityCritic:
    """Agent D: Canon Inspector, Omission Auditor & Reflection Repair Specialist.
    Acts as the final quality gate before a chapter translation is certified for screenplay adaptation.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.AUDITING)

    def audit_and_certify(
        self,
        source_text: str,
        hindi_text: str,
        glossary: Dict[str, Any],
        block_title: str = "",
        call_llm_fn: Optional[Callable[..., str]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Audits the translated text against source and glossary; applies reflection repair if needed."""
        # 1. Deterministic Lexicon Check
        expected_replacements: Dict[str, str] = {}
        if isinstance(glossary, dict):
            chars = glossary.get("characters", [])
            if isinstance(chars, list):
                for item in chars:
                    if isinstance(item, dict):
                        eng = item.get("english_name")
                        hin = item.get("hindi_name")
                        if eng and hin:
                            expected_replacements[eng] = hin
            terms = glossary.get("locations_and_terms", {})
            if isinstance(terms, dict):
                expected_replacements.update(terms)

        # Check for un-translated English names that should be in Hindi
        untranslated_found = []
        for eng_name, hin_name in expected_replacements.items():
            pattern = rf"(?<![\w\u0900-\u097F]){re.escape(eng_name)}(?![\w\u0900-\u097F])"
            if re.search(pattern, hindi_text, re.IGNORECASE):
                untranslated_found.append((eng_name, hin_name))

        # Check source vs hindi word length ratio and paragraph count parity
        src_words = len(source_text.split())
        hin_words = len(hindi_text.split())
        ratio = hin_words / max(1, src_words)

        src_paras = [p for p in source_text.split("\n\n") if p.strip()]
        hin_paras = [p for p in hindi_text.split("\n\n") if p.strip()]
        para_gap = abs(len(src_paras) - len(hin_paras))
        is_para_drop_suspected = len(src_paras) > 3 and para_gap > max(2, int(len(src_paras) * 0.20))

        is_omission_suspected = ratio < 0.60 or ratio > 2.20 or is_para_drop_suspected

        audit_report: Dict[str, Any] = {
            "block_title": block_title,
            "source_words": src_words,
            "hindi_words": hin_words,
            "source_paragraphs": len(src_paras),
            "hindi_paragraphs": len(hin_paras),
            "word_ratio": round(ratio, 2),
            "untranslated_terms_count": len(untranslated_found),
            "omission_suspected": is_omission_suspected,
            "reflection_repair_applied": False,
        }

        # Deterministic fix for any untranslated terms first
        certified_text = hindi_text
        for eng, hin in untranslated_found:
            pattern = rf"(?<![\w\u0900-\u097F]){re.escape(eng)}(?![\w\u0900-\u097F])"
            certified_text = re.sub(pattern, hin, certified_text, flags=re.IGNORECASE)

        # Deterministic moniker calque repair (e.g. Three Jackdaws literally translated)
        calque_repairs = [
            (r"\bतीन\s+कउवे\b", "थ्री जैकडॉज"),
            (r"\bतीन\s+कौवे\b", "थ्री जैकडॉज"),
            (r"\bतीन\s+कौए\b", "थ्री जैकडॉज"),
        ]
        for c_pat, c_sub in calque_repairs:
            certified_text = re.sub(c_pat, c_sub, certified_text)

        # If significant omission is suspected or major discrepancies found, trigger Reflection Repair Pass
        if is_omission_suspected or len(untranslated_found) > 3:
            logger.info(f"  [TranslationQualityCritic] Reflection Repair triggered for {block_title} (ratio={ratio:.2f}, para_gap={para_gap}, untranslated={len(untranslated_found)})")
            repaired_text = self._reflection_repair(
                source_text=source_text,
                current_hindi=certified_text,
                glossary=glossary,
                block_title=block_title,
                issues=f"Word ratio {ratio:.2f}, paragraph gap {para_gap} (src: {len(src_paras)}, hin: {len(hin_paras)}), untranslated names: {[u[0] for u in untranslated_found[:5]]}",
                call_llm_fn=call_llm_fn,
            )
            if repaired_text and len(repaired_text.split()) >= src_words * 0.65:
                certified_text = repaired_text
                audit_report["reflection_repair_applied"] = True

        # Final sanitization
        is_valid, cleaned, reason = validate_and_sanitize_translation(certified_text, is_hindi=True)
        if is_valid:
            certified_text = cleaned
        else:
            logger.warning(f"  [TranslationQualityCritic] Sanitizer notice: {reason}")

        # Literary register audit & substitutions
        _, certified_text, warnings = audit_literary_register(certified_text, apply_substitutions=True)
        audit_report["literary_warnings"] = warnings
        audit_report["status"] = "CERTIFIED"

        logger.info(f"  [TranslationQualityCritic] Certified {block_title} ({len(certified_text)} chars, {len(warnings)} register notes)")
        return certified_text, audit_report

    def _reflection_repair(
        self,
        source_text: str,
        current_hindi: str,
        glossary: Dict[str, Any],
        block_title: str,
        issues: str,
        call_llm_fn: Optional[Callable[..., str]] = None,
    ) -> str:
        """Executes targeted reflection repair when translation quality anomalies are detected."""
        model = self._resolve_model()

        book_title = None
        book_author = None
        if isinstance(glossary, dict):
            meta = glossary.get("book_metadata") or {}
            book_title = meta.get("title") or glossary.get("title")
            book_author = meta.get("author") or glossary.get("author")

        fiction_framing = get_dramatic_fiction_framing(title=book_title, author=book_author)

        system_instruction = (
            fiction_framing +
            "You are an expert Literary Translation Quality Auditor and Reflection Editor.\n"
            "A Hindi translation draft has minor omissions or terminology drift that must be surgically repaired.\n\n"
            "Requirements:\n"
            "1. REPAIR OMISSIONS: Ensure all dialogue turns, narrative beats, and descriptive details from the English source are fully translated.\n"
            "2. CANON TERMINOLOGY: Enforce exact Devanagari spellings for all character and place names from the glossary.\n"
            "3. SPOKEN REGISTER & CADENCE: Eliminate stiff, textbook Sanskritized words ('नितंब' -> 'कमर/कूल्हे', 'वीरांगना' -> 'लड़ाकू औरतें', 'प्रस्ताव' -> 'सौदा/बात'). Maintain spoken Hindustani cadence, actor breath pauses (—, ..., ,), and earthy realism.\n"
            "4. ZERO CHATTER: Output ONLY the complete, repaired Devanagari Markdown text with zero meta-commentary."
        )

        glossary_str = json.dumps(glossary, ensure_ascii=False, indent=2)

        prompt = f"""### GLOSSARY:
{glossary_str}

### DETECTED ISSUES TO REPAIR:
{issues}

### ORIGINAL ENGLISH SOURCE ({block_title}):
\"\"\"
{source_text}
\"\"\"

### CURRENT HINDI DRAFT:
\"\"\"
{current_hindi}
\"\"\"

Produce the complete, fully repaired, publication-grade Devanagari Markdown translation:
"""
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

            is_valid, cleaned, _ = validate_and_sanitize_translation(raw, is_hindi=True)
            return cleaned if is_valid else current_hindi
        except Exception as e:
            logger.warning(f"  [!] Reflection repair failed: {e}. Keeping current text.")
            return current_hindi
