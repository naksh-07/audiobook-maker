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

    import os
    is_offline = (
        os.environ.get("MOCK_OFFLINE", "").lower() in ("true", "1", "yes")
        or os.environ.get("UNIT_TEST_MODE", "").lower() in ("true", "1", "yes")
        or "PYTEST_CURRENT_TEST" in os.environ
    )
    if is_offline:
        return NaturalnessAuditResult(
            is_valid=is_clean,
            status="PASS" if is_clean else "WARN",
            antipatterns_detected=det_warnings,
            warnings=det_warnings,
            evaluator_notes="Deterministic literary register check completed (offline mock).",
        )

    # Step 2: Dedicated LLM Evaluator (dynamic model resolution, ADR-043)
    if call_llm_fn is None:
        from audiobook_factory.llm_client import call_gemini
        from audiobook_factory.model_manager import TaskType

        def _default_llm(prompt: str, system_instruction: str = "", json_mode: bool = True) -> str:
            res = call_gemini(
                prompt=prompt,
                system_instruction=system_instruction,
                task_type=TaskType.AUDITING,
                response_mime_type="application/json" if json_mode else "text/plain",
                temperature=0.1,
            )
            return json.dumps(res) if isinstance(res, (dict, list)) else str(res)

        call_llm_fn = _default_llm

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
        data = json.loads(resp) if isinstance(resp, str) else resp
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
    except Exception as e:
        return NaturalnessAuditResult(
            is_valid=False,
            status="FAIL",
            antipatterns_detected=det_warnings,
            translatese_passages=[f"LLM Naturalness Audit error: {e}"],
            warnings=[str(e)],
            evaluator_notes=f"Audit failed closed: {e}",
        )
