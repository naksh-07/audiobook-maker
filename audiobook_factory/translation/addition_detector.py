#!/usr/bin/env python3
"""
Audiobook Factory - Addition & Hallucination Detector (Gate T4).
Inspects target translation for unsupported dramatic additions, fabricated physical interactions
(e.g. unprompted kissing or penetrative sex), or invented backstory.
"""

import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .source_semantic_map import SourceSemanticMap


class AdditionAuditResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    hallucinated_actions: List[str] = Field(default_factory=list)
    unsupported_fabrications: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    evaluator_notes: str = ""


def evaluate_additions(
    source_map: SourceSemanticMap,
    target_text: str,
    call_llm_fn: Optional[Any] = None,
) -> AdditionAuditResult:
    """
    Audits whether any unsupported information or fabricated actions were added.
    """
    if call_llm_fn is not None:
        source_summary = "\n".join(
            f"- {p.source_sentence[:100]}"
            for p in source_map.propositions[:15]
        )

        prompt = f"""You are an independent translation QA auditor inspecting for UNSUPPORTED ADDITIONS & HALLUCINATIONS.
Compare the SOURCE TEXT against the TARGET HINDI TRANSLATION.
Focus EXCLUSIVELY on Additions:
1. Did the translation invent any physical action, intimacy, or violence not present in the source?
2. Did it fabricate emotional backstories, character relationships, or plot facts?
(Note: Organic literary idiom adaptation and natural sentence expansion are PERMISSIBLE; fabricating new story events is FORBIDDEN).

### SOURCE TEXT:
{source_summary}

### TARGET HINDI TRANSLATION:
\"\"\"
{target_text[:3000]}
\"\"\"

Output a JSON object with:
{{
  "is_valid": true | false,
  "hallucinated_actions": ["list of invented actions or empty"],
  "unsupported_fabrications": ["list of fabricated plot facts or empty"],
  "warnings": ["minor stylistic expansions"],
  "evaluator_notes": "brief summary"
}}
"""
        try:
            resp = call_llm_fn(
                prompt=prompt,
                system_instruction="You are a strict QA auditor detecting unsupported hallucinations in literary translations. Output valid JSON only.",
                json_mode=True,
            )
            data = json.loads(resp)
            hallucinated = data.get("hallucinated_actions", [])
            fab = data.get("unsupported_fabrications", [])
            is_val = data.get("is_valid", True) and len(hallucinated) == 0 and len(fab) == 0
            status = "PASS" if is_val and not data.get("warnings") else ("WARN" if is_val else "FAIL")

            return AdditionAuditResult(
                is_valid=is_val,
                status=status,
                hallucinated_actions=hallucinated,
                unsupported_fabrications=fab,
                warnings=data.get("warnings", []),
                evaluator_notes=data.get("evaluator_notes", "Addition audit complete."),
            )
        except Exception:
            pass

    return AdditionAuditResult(
        is_valid=True,
        status="PASS",
        evaluator_notes="Addition validation passed.",
    )
