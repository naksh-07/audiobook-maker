#!/usr/bin/env python3
"""
Audiobook Factory - Tiered Self-Healing Repair Engine.
Executes surgical, targeted repairs for translation gate failures:
- Level 1: Deterministic regex/lexicon substitutions (instant, 0ms)
- Level 2: Targeted paragraph-level rewrites with focused prompts (max 2 attempts)
- Level 3: Scene-level retranslation (1 attempt)
Never blindly regenerates the entire chapter for a localized failure.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple, Callable
from pydantic import BaseModel, Field

from .terminology_auditor import COMMON_FORBIDDEN_VARIANTS
from audiobook_factory.sanitizer import audit_literary_register

REPAIR_ENGINE_VERSION = "2.0"


class RepairAction(BaseModel):
    level: str  # DETERMINISTIC, PARAGRAPH_REWRITE, SCENE_RETRANSLATE
    target_scope: str  # terminology, calque, paragraph_idx, scene
    issue_description: str
    repaired_successfully: bool
    details: str = ""


class TieredRepairEngine:
    MAX_PARAGRAPH_ATTEMPTS = 2
    MAX_SCENE_ATTEMPTS = 1

    @classmethod
    def plan_repair(
        cls,
        audit_report: Any,
        total_paragraphs: int = 1,
        paragraph_attempts_taken: int = 0,
    ) -> Tuple[str, List[int], List[str]]:
        """
        Plans the repair strategy based on GateAuditResult.
        Returns:
            (repair_level: str, target_paragraphs: List[int], failure_reasons: List[str])
            repair_level in ("NONE", "DETERMINISTIC", "PARAGRAPH_REWRITE", "SCENE_RETRANSLATE")
        """
        if getattr(audit_report, "certified", False) and getattr(audit_report, "overall_status", "") in ("PASS", "PASS_WITH_WARNINGS"):
            return "NONE", [], []

        gates = getattr(audit_report, "gates", {})
        fail_gates = {k: g for k, g in gates.items() if getattr(g, "status", None) == "FAIL"}
        warn_gates = {k: g for k, g in gates.items() if getattr(g, "status", None) == "WARN"}

        failure_reasons: List[str] = []
        for g in fail_gates.values():
            if getattr(g, "failures", None):
                failure_reasons.extend(g.failures)
            elif getattr(g, "details", None):
                failure_reasons.append(g.details)

        for g in warn_gates.values():
            if getattr(g, "warnings", None):
                failure_reasons.extend(g.warnings)

        # Check if only Level 1 deterministic fixes are needed
        only_deterministic = (
            len(fail_gates) > 0
            and all(k in ("T5_terminology", "T9_naturalness") for k in fail_gates)
            and not any(k in ("T0_source_integrity", "T2_semantic_fidelity", "T3_omission", "T4_addition") for k in warn_gates)
        )
        if only_deterministic:
            return "DETERMINISTIC", [], failure_reasons

        # Check for paragraph-level localized repairs (Level 2)
        affected_paras = getattr(audit_report, "affected_paragraphs", []) or []
        if not affected_paras:
            # Fall back to checking gate-specific affected paragraphs
            for g in fail_gates.values():
                if hasattr(g, "affected_paragraphs") and g.affected_paragraphs:
                    affected_paras.extend(g.affected_paragraphs)
            affected_paras = sorted(list(set(affected_paras)))

        # If localized to specific paragraphs and retry budget remains
        can_do_paragraph = (
            paragraph_attempts_taken < cls.MAX_PARAGRAPH_ATTEMPTS
            and len(affected_paras) > 0
            and len(affected_paras) <= max(2, total_paragraphs // 2)
            and getattr(audit_report, "overall_status", "") != "BLOCKED"
        )
        if can_do_paragraph:
            # Clamp indices within range
            valid_targets = [idx for idx in affected_paras if 0 <= idx < total_paragraphs]
            if valid_targets:
                return "PARAGRAPH_REWRITE", valid_targets, failure_reasons

        # Otherwise escalate to Level 3 (scene retranslation)
        return "SCENE_RETRANSLATE", list(range(total_paragraphs)), failure_reasons

    @classmethod
    def apply_deterministic_repair(
        cls,
        text: str,
        terminology_variants: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, List[RepairAction]]:
        """
        Level 1 Repair: Applies deterministic substitutions for forbidden
        terminology variants and unambiguous robotic literalisms.
        Never alters legitimate literary or rustic expressions (नमस्ते, राम-राम, दारू).
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

        # Register unambiguous calques (apply_substitutions=True applies ONLY unambiguous calques)
        is_clean, cleaned_reg, warnings = audit_literary_register(repaired, apply_substitutions=True)
        if cleaned_reg != repaired:
            repaired = cleaned_reg
            for w in warnings:
                if "Antipattern detected" in w:
                    actions.append(RepairAction(
                        level="DETERMINISTIC",
                        target_scope="calque",
                        issue_description=w,
                        repaired_successfully=True,
                        details="Normalized unambiguous calque via Literary Advisory DB",
                    ))

        return repaired, actions

    @classmethod
    def build_paragraph_repair_prompt(
        cls,
        source_paragraph: str,
        current_target_paragraph: str,
        failure_reasons: List[str],
        semantic_beats: Optional[List[str]] = None,
    ) -> str:
        """Constructs surgical prompt for Level 2 paragraph retranslation."""
        issues_formatted = "\n".join(f"- {r}" for r in failure_reasons) if failure_reasons else "- Quality improvement"
        beats_formatted = ""
        if semantic_beats:
            beats_formatted = "\n### CORE SEMANTIC BEATS TO PRESERVE:\n" + "\n".join(f"- {b}" for b in semantic_beats)

        return f"""You are a master Hindi literary translator performing a surgical correction on a single paragraph.

### SOURCE ENGLISH PARAGRAPH:
\"\"\"
{source_paragraph}
\"\"\"

### CURRENT TRANSLATION (FLAGGED WITH ISSUE):
\"\"\"
{current_target_paragraph}
\"\"\"{beats_formatted}

### SPECIFIC ISSUES TO FIX:
{issues_formatted}

Rewrite ONLY this paragraph in flawless Devanagari Hindi, fixing the specific issues while maintaining
literary cadence, authentic profanity/tone, and complete semantic fidelity.
Do not omit any dialogue lines or actions.
Output ONLY the corrected Hindi paragraph.
"""

    @classmethod
    def repair_paragraph(
        cls,
        source_paragraph: str,
        current_target_paragraph: str,
        failure_reason: str,
        call_llm_fn: Callable[[str, str], str],
        semantic_beats: Optional[List[str]] = None,
    ) -> Tuple[str, bool]:
        """
        Level 2 Repair: Targeted rewrite of a single failing paragraph with focused instructions.
        """
        reasons = [failure_reason] if isinstance(failure_reason, str) else failure_reason
        prompt = cls.build_paragraph_repair_prompt(
            source_paragraph=source_paragraph,
            current_target_paragraph=current_target_paragraph,
            failure_reasons=reasons,
            semantic_beats=semantic_beats,
        )
        try:
            repaired = call_llm_fn(prompt, "You are a surgical translation repair editor. Output only the corrected paragraph.").strip()
            if repaired and len(repaired) > 10:
                return repaired, True
        except Exception:
            pass

        return current_target_paragraph, False

    @classmethod
    def build_scene_repair_prompt(
        cls,
        source_scene: str,
        flawed_scene: str,
        failure_reasons: List[str],
        base_prompt: str = "",
    ) -> str:
        """Constructs full-scene prompt for Level 3 scene retranslation."""
        issues_formatted = "\n".join(f"- {r}" for r in failure_reasons) if failure_reasons else "- Systemic fidelity drift"
        return f"""You are a world-class literary translator repairing a scene translation into Hindustani prose.
The previous translation attempt failed certification with the following issues:

### DEFECTS IN PREVIOUS TRANSLATION:
{issues_formatted}

### SOURCE ENGLISH SCENE:
\"\"\"
{source_scene}
\"\"\"

### PREVIOUS FLAWED DRAFT (FOR REFERENCE):
\"\"\"
{flawed_scene}
\"\"\"

Translate the ENTIRE scene afresh into dramatic, cinematic Hindustani prose:
1. Completely resolve the flagged defects above (retain all dialogue beats, maintain negation parity).
2. Use authentic conversational phrasing without modern textbook literalisms.
3. Preserve the exact paragraph breaks of the original scene.
Output ONLY the clean Devanagari translation.
"""
