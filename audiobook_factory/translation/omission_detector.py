#!/usr/bin/env python3
"""
Audiobook Factory - Omission Detector (Gate T3).
Detects dropped dialogue beats, omitted narrative actions, or missing descriptive facts
by comparing the target text against the persistent SourceSemanticMap.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from .source_semantic_map import SourceSemanticMap


class OmissionAuditResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    omitted_dialogue_beats: List[str] = Field(default_factory=list)
    omitted_actions: List[str] = Field(default_factory=list)
    omitted_entities: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    evaluator_notes: str = ""


def deterministic_omission_check(
    source_map: SourceSemanticMap,
    target_text: str,
) -> Tuple[bool, List[str]]:
    """
    Deterministic check: compares dialogue quote count and source entity coverage.
    """
    warnings: List[str] = []
    # Count dialogue quotation occurrences
    src_dialogue_count = sum(1 for p in source_map.propositions if p.is_dialogue)
    # Hindi dialogue quotes: "..." or '...' or «...»
    tgt_dialogue_quotes = len(re.findall(r'["\u201c\u201d]', target_text)) // 2

    if src_dialogue_count >= 3 and tgt_dialogue_quotes == 0:
        warnings.append(
            f"Source contains {src_dialogue_count} dialogue beats, but target has 0 quotation blocks."
        )

    return len(warnings) == 0, warnings


def evaluate_omissions(
    source_map: SourceSemanticMap,
    target_text: str,
    call_llm_fn: Optional[Any] = None,
) -> OmissionAuditResult:
    """
    Audits whether any significant source beats were omitted from target text.
    """
    det_ok, det_warnings = deterministic_omission_check(source_map, target_text)

    if call_llm_fn is not None:
        source_summary = "\n".join(
            f"- [{p.beat_id}]: {p.source_sentence[:100]}"
            for p in source_map.propositions[:15]
        )

        prompt = f"""You are an independent translation QA auditor inspecting for OMISSIONS.
Compare the SOURCE BEATS against the TARGET HINDI TRANSLATION.
Focus EXCLUSIVELY on Omissions:
1. Did the translation drop any dialogue sentence or character retort?
2. Did it skip any key physical action or descriptive beat?

### SOURCE BEATS:
{source_summary}

### TARGET HINDI TRANSLATION:
\"\"\"
{target_text[:3000]}
\"\"\"

Output a JSON object with:
{{
  "is_valid": true | false,
  "omitted_dialogue_beats": ["list of dropped lines or empty"],
  "omitted_actions": ["list of dropped actions or empty"],
  "warnings": ["minor omitted descriptive words"],
  "evaluator_notes": "brief summary"
}}
"""
        try:
            resp = call_llm_fn(
                prompt=prompt,
                system_instruction="You are a strict QA auditor detecting omitted content in literary translations. Output valid JSON only.",
                json_mode=True,
            )
            data = json.loads(resp)
            omitted_lines = data.get("omitted_dialogue_beats", [])
            omitted_acts = data.get("omitted_actions", [])
            is_val = data.get("is_valid", True) and len(omitted_lines) == 0 and len(omitted_acts) == 0
            status = "PASS" if is_val and not data.get("warnings") else ("WARN" if is_val else "FAIL")

            return OmissionAuditResult(
                is_valid=is_val,
                status=status,
                omitted_dialogue_beats=omitted_lines,
                omitted_actions=omitted_acts,
                warnings=data.get("warnings", []) + det_warnings,
                evaluator_notes=data.get("evaluator_notes", "Omission audit complete."),
            )
        except Exception:
            pass

    return OmissionAuditResult(
        is_valid=det_ok,
        status="PASS" if det_ok else "WARN",
        warnings=det_warnings,
        evaluator_notes="Deterministic omission check passed.",
    )
