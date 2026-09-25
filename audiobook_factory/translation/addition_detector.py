#!/usr/bin/env python3
"""
Audiobook Factory - Addition & Hallucination Detector (Gate T4).
Inspects target translation for unsupported dramatic additions, fabricated physical interactions,
or invented backstory.
"""

from __future__ import annotations
import re
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from .source_semantic_map import SourceSemanticMap, TargetSemanticMap


class AdditionAuditResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    hallucinated_actions: List[str] = Field(default_factory=list)
    unsupported_fabrications: List[str] = Field(default_factory=list)
    affected_paragraphs: List[int] = Field(default_factory=list)
    expansion_ratio: float = 1.0
    warnings: List[str] = Field(default_factory=list)
    evaluator_notes: str = ""


def deterministic_addition_check(
    source_map: SourceSemanticMap,
    target_text: str,
) -> Tuple[bool, List[str], List[int], float]:
    """
    Deterministic check: monitors text expansion ratio and unprompted chatter markers.
    Returns (is_valid, warnings, affected_paragraphs, expansion_ratio).
    """
    warnings: List[str] = []
    affected_paragraphs: List[int] = []

    src_len = max(1, sum(len(p.source_sentence) for p in source_map.propositions))
    tgt_len = len(target_text)
    expansion_ratio = round(tgt_len / src_len, 3)

    # In Devanagari, natural character expansion over English is usually 1.0 - 1.8x
    if expansion_ratio > 2.4:
        warnings.append(
            f"Excessive character expansion ratio ({expansion_ratio:.2f}x). Potential hallucinated content."
        )

    # Check for LLM chatter / meta comments in target text
    chatter_patterns = [
        r"\bयहाँ\s+अनुवाद\s+है\b",
        r"\bटिप्पणी\b",
        r"\bअनुवादक\b",
        r"\bनोट\b",
    ]
    for pat in chatter_patterns:
        if re.search(pat, target_text):
            warnings.append("Detected possible translator notes or conversational meta-chatter.")
            break

    is_valid = expansion_ratio <= 2.4 and len(warnings) == 0
    return is_valid, warnings, affected_paragraphs, expansion_ratio


def evaluate_additions(
    source_map: SourceSemanticMap,
    target_text: str,
    call_llm_fn: Optional[Any] = None,
) -> AdditionAuditResult:
    """
    Audits whether any unsupported information or fabricated actions were added.
    """
    det_ok, det_warnings, affected_paras, exp_ratio = deterministic_addition_check(
        source_map, target_text
    )

    if call_llm_fn is not None:
        props = source_map.propositions
        chunk_size = 20
        hallucinated: List[str] = []
        fab: List[str] = []
        llm_warnings: List[str] = []
        notes: List[str] = []

        for c_idx in range(0, max(1, len(props)), chunk_size):
            chunk_props = props[c_idx:c_idx + chunk_size]
            source_summary = "\n".join(
                f"- [Beat {p.beat_id}, Para {p.paragraph_idx}]: {p.source_sentence[:100]}"
                for p in chunk_props
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
{target_text}
\"\"\"

Output a JSON object with:
{{
  "is_valid": true | false,
  "hallucinated_actions": ["list of invented actions or empty"],
  "unsupported_fabrications": ["list of fabricated plot facts or empty"],
  "affected_paragraphs": [list of 0-based integer paragraph indices with hallucinations],
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
                data = json.loads(resp) if isinstance(resp, str) else resp
                hallucinated.extend(data.get("hallucinated_actions", []))
                fab.extend(data.get("unsupported_fabrications", []))
                llm_warnings.extend(data.get("warnings", []))
                for ap in data.get("affected_paragraphs", []):
                    if isinstance(ap, int):
                        affected_paras.append(ap)
                if data.get("evaluator_notes"):
                    notes.append(data.get("evaluator_notes"))
            except Exception as e:
                llm_warnings.append(f"LLM addition check notice: {e}")

        is_val = len(hallucinated) == 0 and len(fab) == 0 and exp_ratio <= 2.4
        status = "PASS" if is_val and not (det_warnings or llm_warnings) else ("WARN" if is_val else "FAIL")

        return AdditionAuditResult(
            is_valid=is_val,
            status=status,
            hallucinated_actions=hallucinated,
            unsupported_fabrications=fab,
            affected_paragraphs=sorted(list(set(affected_paras))),
            expansion_ratio=exp_ratio,
            warnings=det_warnings + llm_warnings,
            evaluator_notes="; ".join(notes) if notes else "Addition audit complete.",
        )

    status = "PASS" if det_ok else ("WARN" if exp_ratio <= 2.4 else "FAIL")
    return AdditionAuditResult(
        is_valid=det_ok,
        status=status,
        affected_paragraphs=sorted(list(set(affected_paras))),
        expansion_ratio=exp_ratio,
        warnings=det_warnings,
        evaluator_notes="Deterministic addition check completed.",
    )
