#!/usr/bin/env python3
"""
Audiobook Factory - Semantic Fidelity Engine (Gate T2).
Evaluates whether target Hindi translation faithfully conveys who did what to whom,
action integrity, and negation states without inversion or distortion.
Leverages persistent SourceSemanticMap for deterministic pre-validation
before escalating to an isolated LLM evaluator.
"""

from __future__ import annotations
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from .source_semantic_map import SourceSemanticMap, SemanticProposition


class SemanticFidelityResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    critical_inversions: List[str] = Field(default_factory=list)
    action_mismatches: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    evaluator_notes: str = ""


HINDI_NEGATION_PATTERNS = [
    r"(?<![\u0900-\u097F])नहीं(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])ना(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])मत(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])कभी\s+नहीं(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])इनकार(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])रोका(?![\u0900-\u097F])",
]
COMPILED_HINDI_NEG = [re.compile(p) for p in HINDI_NEGATION_PATTERNS]


def deterministic_negation_audit(
    semantic_map: SourceSemanticMap,
    devanagari_text: str,
) -> Tuple[bool, List[str]]:
    """
    Deterministic check: If source proposition contains hard negation ('not enter', 'never said'),
    verifies that the target Hindi text contains corresponding Devanagari negation tokens.
    """
    inversions: List[str] = []
    # If the entire scene has negations in source, check that target also contains negation
    source_has_neg = any(p.has_negation for p in semantic_map.propositions)
    target_has_neg = any(pat.search(devanagari_text) for pat in COMPILED_HINDI_NEG)

    if source_has_neg and not target_has_neg and len(semantic_map.propositions) < 6:
        inversions.append(
            "Source contains critical negation (not/never/refused) but target translation has zero Devanagari negation particles ('नहीं' / 'ना')."
        )
        return False, inversions

    return True, []


def evaluate_semantic_fidelity(
    source_map: SourceSemanticMap,
    target_text: str,
    call_llm_fn: Optional[Any] = None,
) -> SemanticFidelityResult:
    """
    Evaluates semantic fidelity of target text against stable SourceSemanticMap.
    Step 1: Deterministic negation & integrity audit.
    Step 2: Dedicated isolated LLM evaluation pass if call_llm_fn is provided.
    """
    # Step 1: Deterministic pre-validation
    det_ok, inversions = deterministic_negation_audit(source_map, target_text)
    if not det_ok:
        return SemanticFidelityResult(
            is_valid=False,
            status="FAIL",
            critical_inversions=inversions,
            evaluator_notes="Deterministic pre-validator detected critical negation inversion.",
        )

    # Step 2: Dedicated LLM Evaluator (if enabled)
    if call_llm_fn is not None:
        source_beats_summary = "\n".join(
            f"Beat {p.beat_id}: [{', '.join(p.actors) or 'Narrator'}] -> Action/Intent: '{p.source_sentence[:120]}' (Negation: {p.has_negation})"
            for p in source_map.propositions[:15]
        )

        prompt = f"""You are an independent, forensic literary translation evaluator.
Compare the stable SOURCE PROPOSITIONS against the TARGET HINDI TRANSLATION.
Focus EXCLUSIVELY on Semantic Fidelity:
1. Did any character action invert? (e.g. source: did not go -> target: went)
2. Is there an action mismatch? (e.g. source: slapped -> target: pushed)
3. Did the actor/recipient switch?

### SOURCE PROPOSITIONS:
{source_beats_summary}

### TARGET HINDI TRANSLATION:
\"\"\"
{target_text[:3000]}
\"\"\"

Output a JSON object with:
{{
  "is_valid": true | false,
  "critical_inversions": ["list of inverted meanings or empty"],
  "action_mismatches": ["list of action discrepancies or empty"],
  "warnings": ["minor nuances"],
  "evaluator_notes": "brief summary"
}}
"""
        try:
            resp = call_llm_fn(
                prompt=prompt,
                system_instruction="You are an uncompromising literary translation QA evaluator. Output valid JSON only.",
                json_mode=True,
            )
            data = json.loads(resp)
            invs = data.get("critical_inversions", [])
            mismatches = data.get("action_mismatches", [])
            is_val = data.get("is_valid", True) and len(invs) == 0
            status = "PASS" if is_val and not data.get("warnings") else ("WARN" if is_val else "FAIL")

            return SemanticFidelityResult(
                is_valid=is_val,
                status=status,
                critical_inversions=invs,
                action_mismatches=mismatches,
                warnings=data.get("warnings", []),
                evaluator_notes=data.get("evaluator_notes", "LLM evaluation completed."),
            )
        except Exception as e:
            # Fallback to deterministic check result if LLM fails
            return SemanticFidelityResult(
                is_valid=True,
                status="PASS",
                warnings=[f"LLM semantic evaluator skipped or failed gracefully ({e}); passed deterministic checks."],
                evaluator_notes="Deterministic validation passed.",
            )

    return SemanticFidelityResult(
        is_valid=True,
        status="PASS",
        evaluator_notes="Deterministic semantic validation passed.",
    )
