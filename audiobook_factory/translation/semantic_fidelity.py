#!/usr/bin/env python3
"""
Audiobook Factory - Semantic Fidelity Engine (Gate T2).
Evaluates whether target Hindi translation faithfully conveys who did what to whom,
action integrity, and negation states without inversion or distortion.
Leverages persistent SourceSemanticMap and TargetSemanticMap with SemanticAligner
for deterministic pre-validation and full LLM evaluation.
"""

from __future__ import annotations
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from .source_semantic_map import (
    SourceSemanticMap,
    SemanticProposition,
    TargetSemanticMap,
    build_target_semantic_map,
    SemanticAligner,
    SemanticAlignmentResult,
)


class SemanticFidelityResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    critical_inversions: List[str] = Field(default_factory=list)
    action_mismatches: List[str] = Field(default_factory=list)
    affected_paragraphs: List[int] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    evaluator_notes: str = ""
    target_map: Optional[TargetSemanticMap] = None
    alignment: Optional[SemanticAlignmentResult] = None


HINDI_NEGATION_PATTERNS = [
    r"(?<![\u0900-\u097F])नहीं(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])ना(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])मत(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])कभी\s+नहीं(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])इनकार(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])रोका(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])बिना(?![\u0900-\u097F])",
    r"(?<![\u0900-\u097F])बग़ैर(?![\u0900-\u097F])",
]
COMPILED_HINDI_NEG = [re.compile(p) for p in HINDI_NEGATION_PATTERNS]


def deterministic_negation_audit(
    semantic_map: SourceSemanticMap,
    devanagari_text: str,
) -> Tuple[bool, List[str]]:
    """
    Deterministic check: verifies negation parity at both scene level and paragraph level.
    If source proposition contains hard negation ('not enter', 'never said'),
    verifies that the target Hindi text contains corresponding Devanagari negation tokens.
    """
    inversions: List[str] = []
    
    # 1. Whole-scene negation parity
    source_has_neg = any(p.has_negation for p in semantic_map.propositions)
    target_has_neg = any(pat.search(devanagari_text) for pat in COMPILED_HINDI_NEG)

    if source_has_neg and not target_has_neg:
        inversions.append(
            "Source contains critical negation (not/never/refused) but target translation has zero Devanagari negation particles ('नहीं' / 'ना')."
        )
        return False, inversions

    # 2. Paragraph-level negation parity
    src_paras = semantic_map.get_paragraphs()
    tgt_paras = [p.strip() for p in devanagari_text.split("\n\n") if p.strip()]

    if len(src_paras) == len(tgt_paras) and len(src_paras) > 1:
        for p_idx in sorted(src_paras.keys()):
            s_props = src_paras[p_idx]
            s_negs = sum(1 for p in s_props if p.has_negation)
            if s_negs > 0:
                t_text = tgt_paras[p_idx] if p_idx < len(tgt_paras) else ""
                t_has_neg = any(pat.search(t_text) for pat in COMPILED_HINDI_NEG)
                if not t_has_neg:
                    inversions.append(
                        f"Paragraph {p_idx}: Source contains {s_negs} critical negation(s) but aligned target paragraph lacks any Devanagari negation particles."
                    )

    if inversions:
        return False, inversions

    return True, []


def evaluate_semantic_fidelity(
    source_map: SourceSemanticMap,
    target_text: str,
    call_llm_fn: Optional[Any] = None,
    book_bible: Optional[Any] = None,
    target_map: Optional[TargetSemanticMap] = None,
) -> SemanticFidelityResult:
    """
    Evaluates semantic fidelity of target text against stable SourceSemanticMap.
    Step 1: Deterministic negation & integrity audit.
    Step 2: Semantic alignment layer (WHO -> DID WHAT -> TO WHOM -> OBJECT -> NEGATION).
    Step 3: Dedicated LLM evaluation pass across all propositions (when call_llm_fn is provided).
    """
    affected_paragraphs: List[int] = []

    # Step 1: Deterministic negation check
    det_ok, inversions = deterministic_negation_audit(source_map, target_text)

    # Step 2: Target Semantic Map & Alignment Layer
    if target_map is None:
        target_map = build_target_semantic_map(
            target_text=target_text,
            scene_id=source_map.scene_id,
            book_bible=book_bible,
            call_llm_fn=call_llm_fn,
        )

    alignment = SemanticAligner.align(
        source_map=source_map,
        target_map=target_map,
        book_bible=book_bible,
    )
    if alignment.affected_paragraphs:
        affected_paragraphs.extend(alignment.affected_paragraphs)

    if not det_ok:
        affected_paragraphs.extend([p.paragraph_idx for p in source_map.propositions if p.has_negation])
        return SemanticFidelityResult(
            is_valid=False,
            status="FAIL",
            critical_inversions=inversions,
            affected_paragraphs=sorted(list(set(affected_paragraphs))),
            evaluator_notes="Deterministic pre-validator detected critical negation inversion.",
            target_map=target_map,
            alignment=alignment,
        )

    # If alignment found critical failures (e.g. negation mismatch), mark accordingly
    warnings = []
    for pa in alignment.paragraph_alignments:
        if pa.issues:
            warnings.extend(pa.issues)

    # Step 3: Dedicated LLM Evaluator (if enabled, Decision A3)
    if call_llm_fn is not None:
        props = source_map.propositions
        chunk_size = 20
        all_inversions: List[str] = []
        all_mismatches: List[str] = []
        llm_warnings: List[str] = []
        notes: List[str] = []

        for c_idx in range(0, max(1, len(props)), chunk_size):
            chunk_props = props[c_idx:c_idx + chunk_size]
            source_beats_summary = "\n".join(
                f"Beat {p.beat_id} (Para {p.paragraph_idx}): [{', '.join(p.actors) or 'Narrator'}] -> Action/Intent: '{p.source_sentence[:120]}' (Negation: {p.has_negation})"
                for p in chunk_props
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
{target_text}
\"\"\"

Output a JSON object with:
{{
  "is_valid": true | false,
  "critical_inversions": ["list of inverted meanings or empty"],
  "action_mismatches": ["list of action discrepancies or empty"],
  "affected_paragraphs": [list of 0-based integer paragraph indices with issues],
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
                data = json.loads(resp) if isinstance(resp, str) else resp
                all_inversions.extend(data.get("critical_inversions", []))
                all_mismatches.extend(data.get("action_mismatches", []))
                llm_warnings.extend(data.get("warnings", []))
                for ap in data.get("affected_paragraphs", []):
                    if isinstance(ap, int):
                        affected_paragraphs.append(ap)
                if data.get("evaluator_notes"):
                    notes.append(data.get("evaluator_notes"))
            except Exception as e:
                llm_warnings.append(f"LLM semantic chunk evaluation notice: {e}")

        is_val = len(all_inversions) == 0 and alignment.is_valid
        status = "PASS" if (is_val and not (warnings or llm_warnings)) else ("WARN" if is_val else "FAIL")

        return SemanticFidelityResult(
            is_valid=is_val,
            status=status,
            critical_inversions=all_inversions,
            action_mismatches=all_mismatches,
            affected_paragraphs=sorted(list(set(affected_paragraphs))),
            warnings=warnings + llm_warnings,
            evaluator_notes="; ".join(notes) if notes else "Semantic fidelity evaluation completed.",
            target_map=target_map,
            alignment=alignment,
        )

    # Pure deterministic fallback (zero LLM)
    is_val = alignment.is_valid and len(inversions) == 0
    status = "PASS" if is_val and not warnings else ("WARN" if is_val else "FAIL")

    return SemanticFidelityResult(
        is_valid=is_val,
        status=status,
        critical_inversions=inversions,
        affected_paragraphs=sorted(list(set(affected_paragraphs))),
        warnings=warnings,
        evaluator_notes="Deterministic semantic alignment completed.",
        target_map=target_map,
        alignment=alignment,
    )
