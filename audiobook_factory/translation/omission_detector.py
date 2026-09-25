#!/usr/bin/env python3
"""
Audiobook Factory - Omission Detector (Gate T3).
Detects dropped dialogue beats, omitted narrative actions, or missing descriptive facts
by comparing the target text against the persistent SourceSemanticMap.
"""

from __future__ import annotations
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from .source_semantic_map import SourceSemanticMap, TargetSemanticMap


class OmissionAuditResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    omitted_dialogue_beats: List[str] = Field(default_factory=list)
    omitted_actions: List[str] = Field(default_factory=list)
    omitted_entities: List[str] = Field(default_factory=list)
    affected_paragraphs: List[int] = Field(default_factory=list)
    coverage_ratio: float = 1.0
    warnings: List[str] = Field(default_factory=list)
    evaluator_notes: str = ""


def deterministic_omission_check(
    source_map: SourceSemanticMap,
    target_text: str,
    target_map: Optional[TargetSemanticMap] = None,
) -> Tuple[bool, List[str], List[int], float]:
    """
    Deterministic check: compares dialogue quote count, paragraph beat coverage, and source entities.
    Returns (is_valid, warnings, affected_paragraphs, coverage_ratio).
    """
    warnings: List[str] = []
    affected_paragraphs: List[int] = []

    src_dialogue_count = sum(1 for p in source_map.propositions if p.is_dialogue)
    tgt_dialogue_quotes = len(re.findall(r'["\u201c\u201d]', target_text)) // 2

    if src_dialogue_count >= 3 and tgt_dialogue_quotes == 0:
        warnings.append(
            f"Source contains {src_dialogue_count} dialogue beats, but target has 0 quotation blocks."
        )

    # Paragraph-level beat count comparison
    src_paras = source_map.get_paragraphs()
    tgt_paras = [p.strip() for p in target_text.split("\n\n") if p.strip()]

    total_src_beats = max(1, len(source_map.propositions))
    # Approximate target beats via Devanagari sentences or target_map if present
    if target_map is not None:
        total_tgt_beats = len(target_map.propositions)
    else:
        total_tgt_beats = sum(len([s for s in re.split(r"[।?!]", tp) if s.strip()]) for tp in tgt_paras)

    coverage_ratio = round(total_tgt_beats / total_src_beats, 3)

    if len(src_paras) == len(tgt_paras) and len(src_paras) > 1:
        for p_idx in sorted(src_paras.keys()):
            s_count = len(src_paras[p_idx])
            t_text = tgt_paras[p_idx]
            t_count = len([s for s in re.split(r"[।?!]", t_text) if s.strip()])
            if s_count >= 2 and t_count == 0:
                affected_paragraphs.append(p_idx)
                warnings.append(f"Paragraph {p_idx}: Source has {s_count} beats but target paragraph is empty.")
            elif s_count >= 4 and t_count <= 1:
                affected_paragraphs.append(p_idx)
                warnings.append(f"Paragraph {p_idx}: Severely condensed ({s_count} source beats -> {t_count} target beats).")

    is_valid = len(affected_paragraphs) == 0 and coverage_ratio >= 0.65
    return is_valid, warnings, affected_paragraphs, coverage_ratio


def evaluate_omissions(
    source_map: SourceSemanticMap,
    target_text: str,
    call_llm_fn: Optional[Any] = None,
    target_map: Optional[TargetSemanticMap] = None,
) -> OmissionAuditResult:
    """
    Audits whether any significant source beats were omitted from target text.
    Step 1: Deterministic coverage and dialogue checks.
    Step 2: Full LLM JSON evaluation across all propositions (when call_llm_fn is provided).
    """
    det_ok, det_warnings, affected_paras, cov_ratio = deterministic_omission_check(
        source_map, target_text, target_map
    )

    if call_llm_fn is not None:
        props = source_map.propositions
        chunk_size = 20
        omitted_lines: List[str] = []
        omitted_acts: List[str] = []
        llm_warnings: List[str] = []
        notes: List[str] = []

        for c_idx in range(0, max(1, len(props)), chunk_size):
            chunk_props = props[c_idx:c_idx + chunk_size]
            source_summary = "\n".join(
                f"- [Beat {p.beat_id}, Para {p.paragraph_idx}]: {p.source_sentence[:100]} (Dialogue: {p.is_dialogue})"
                for p in chunk_props
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
{target_text}
\"\"\"

Output a JSON object with:
{{
  "is_valid": true | false,
  "omitted_dialogue_beats": ["list of dropped lines or empty"],
  "omitted_actions": ["list of dropped actions or empty"],
  "affected_paragraphs": [list of 0-based integer paragraph indices with omissions],
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
                data = json.loads(resp) if isinstance(resp, str) else resp
                omitted_lines.extend(data.get("omitted_dialogue_beats", []))
                omitted_acts.extend(data.get("omitted_actions", []))
                llm_warnings.extend(data.get("warnings", []))
                for ap in data.get("affected_paragraphs", []):
                    if isinstance(ap, int):
                        affected_paras.append(ap)
                if data.get("evaluator_notes"):
                    notes.append(data.get("evaluator_notes"))
            except Exception as e:
                llm_warnings.append(f"LLM omission check notice: {e}")

        is_val = len(omitted_lines) == 0 and len(omitted_acts) == 0 and cov_ratio >= 0.65
        status = "PASS" if is_val and not (det_warnings or llm_warnings) else ("WARN" if is_val else "FAIL")

        return OmissionAuditResult(
            is_valid=is_val,
            status=status,
            omitted_dialogue_beats=omitted_lines,
            omitted_actions=omitted_acts,
            affected_paragraphs=sorted(list(set(affected_paras))),
            coverage_ratio=cov_ratio,
            warnings=det_warnings + llm_warnings,
            evaluator_notes="; ".join(notes) if notes else "Omission audit complete.",
        )

    # Deterministic fallback
    status = "PASS" if (det_ok and not det_warnings) else ("WARN" if cov_ratio >= 0.70 else "FAIL")
    return OmissionAuditResult(
        is_valid=det_ok,
        status=status,
        affected_paragraphs=sorted(list(set(affected_paras))),
        coverage_ratio=cov_ratio,
        warnings=det_warnings,
        evaluator_notes="Deterministic omission check completed.",
    )
