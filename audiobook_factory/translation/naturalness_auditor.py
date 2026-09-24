#!/usr/bin/env python3
"""
Audiobook Factory - Literary Naturalness & Cadence Auditor (Gate T9 & T10).
Detects English syntax leakage ('translatese'), awkward literal idioms, robotic sentence structures,
excessive Sanskritization, and immersion-breaking antipatterns.
"""

import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from audiobook_factory.sanitizer import audit_literary_register


class NaturalnessAuditResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    antipatterns_detected: List[str] = Field(default_factory=list)
    translatese_passages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    evaluator_notes: str = ""


def evaluate_literary_naturalness(
    target_text: str,
    call_llm_fn: Optional[Any] = None,
) -> NaturalnessAuditResult:
    """
    Evaluates whether the Hindi translation reads as natural literature
    rather than a translated English document.
    """
    # Step 1: Deterministic antipattern check
    is_clean, _, det_warnings = audit_literary_register(target_text)

    # Step 2: Dedicated LLM Evaluator (if enabled)
    if call_llm_fn is not None:
        prompt = f"""You are an independent, highly critical literary editor for premier Hindi literature.
Evaluate this TARGET HINDI TRANSLATION for Spoken Literary Naturalness:
1. Does it sound like translated English ('translatese')? (e.g. awkward passive voice, literal English clauses)
2. Are idioms natural to Hindustani or stiff literal translations?
3. Would an educated Hindi reader find the cadence smooth and compelling?

### TARGET HINDI TEXT:
\"\"\"
{target_text[:3000]}
\"\"\"

Output a JSON object with:
{{
  "is_valid": true | false,
  "translatese_passages": ["list of awkward phrases that sound translated or empty"],
  "warnings": ["rhythm or flow notes"],
  "evaluator_notes": "brief literary critique"
}}
"""
        try:
            resp = call_llm_fn(
                prompt=prompt,
                system_instruction="You are a strict Hindi literary editor. Output valid JSON only.",
                json_mode=True,
            )
            data = json.loads(resp)
            awkward = data.get("translatese_passages", [])
            is_val = data.get("is_valid", True) and len(awkward) == 0 and is_clean
            status = "PASS" if is_val and not data.get("warnings") else ("WARN" if is_val else "FAIL")

            return NaturalnessAuditResult(
                is_valid=is_val,
                status=status,
                antipatterns_detected=det_warnings,
                translatese_passages=awkward,
                warnings=data.get("warnings", []),
                evaluator_notes=data.get("evaluator_notes", "Naturalness audit complete."),
            )
        except Exception:
            pass

    return NaturalnessAuditResult(
        is_valid=is_clean,
        status="PASS" if is_clean else "WARN",
        antipatterns_detected=det_warnings,
        warnings=det_warnings,
        evaluator_notes="Deterministic literary register check completed.",
    )
