#!/usr/bin/env python3
"""
Audiobook Factory - Tiered Self-Healing Repair Engine.
Executes surgical, targeted repairs for translation gate failures:
- Level 1: Deterministic regex/lexicon substitutions (instant, 0ms)
- Level 2: Targeted paragraph-level rewrites with focused prompts (max 2 attempts)
- Level 3: Scene-level retranslation (1 attempt)
Never blindly regenerates the entire chapter for a localized failure.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Callable
from pydantic import BaseModel, Field

from .terminology_auditor import COMMON_FORBIDDEN_VARIANTS
from audiobook_factory.sanitizer import audit_literary_register


class RepairAction(BaseModel):
    level: str  # DETERMINISTIC, PARAGRAPH_REWRITE, SCENE_RETRANSLATE
    target_scope: str  # token, paragraph_idx, scene
    issue_description: str
    repaired_successfully: bool
    details: str = ""


class TieredRepairEngine:
    MAX_PARAGRAPH_ATTEMPTS = 2
    MAX_SCENE_ATTEMPTS = 1

    @classmethod
    def apply_deterministic_repair(
        cls,
        text: str,
        terminology_variants: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, List[RepairAction]]:
        """
        Level 1 Repair: Applies deterministic word boundary substitutions
        for forbidden terminology variants and robotic antipatterns.
        """
        actions: List[RepairAction] = []
        repaired = text

        active_variants: Dict[str, str] = dict(COMMON_FORBIDDEN_VARIANTS)
        if terminology_variants:
            active_variants.update(terminology_variants)

        # Terminology variants
        for pattern, canonical in active_variants.items():
            if re.search(pattern, repaired):
                repaired = re.sub(pattern, canonical, repaired)
                actions.append(RepairAction(
                    level="DETERMINISTIC",
                    target_scope="terminology",
                    issue_description=f"Forbidden variant pattern '{pattern}'",
                    repaired_successfully=True,
                    details=f"Substituted with canonical '{canonical}'",
                ))

        # Register antipatterns
        is_clean, cleaned_reg, warnings = audit_literary_register(repaired)
        if not is_clean:
            repaired = cleaned_reg
            for w in warnings:
                actions.append(RepairAction(
                    level="DETERMINISTIC",
                    target_scope="advisory_antipattern",
                    issue_description=w,
                    repaired_successfully=True,
                    details="Normalized via Literary Advisory DB",
                ))

        return repaired, actions

    @classmethod
    def repair_paragraph(
        cls,
        source_paragraph: str,
        current_target_paragraph: str,
        failure_reason: str,
        call_llm_fn: Callable[[str, str], str],
    ) -> Tuple[str, bool]:
        """
        Level 2 Repair: Targeted rewrite of a single failing paragraph with focused instructions.
        """
        prompt = f"""You are a master Hindi literary translator performing a surgical correction on a single paragraph.

### SOURCE ENGLISH PARAGRAPH:
\"\"\"
{source_paragraph}
\"\"\"

### CURRENT TRANSLATION (FLAGGED WITH ISSUE):
\"\"\"
{current_target_paragraph}
\"\"\"

### SPECIFIC ISSUE TO FIX:
{failure_reason}

Rewrite ONLY this paragraph in flawless Devanagari Hindi, fixing the specific issue while maintaining
literary cadence, authentic profanity/tone, and semantic fidelity. Output ONLY the corrected paragraph.
"""
        try:
            repaired = call_llm_fn(prompt, "You are a surgical translation repair editor. Output only the corrected paragraph.").strip()
            if repaired and len(repaired) > 10:
                return repaired, True
        except Exception:
            pass

        return current_target_paragraph, False
