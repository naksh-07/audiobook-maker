#!/usr/bin/env python3
"""
Audiobook Factory - Literary Intensity Model.
Tracks 7-dimensional intensity vectors and enforces the 'Nothing Above Source' principle.
Note: The ±0.75 threshold is treated as a soft evaluation heuristic (emitting WARN),
reserving hard FAIL only for extreme divergence (> 2.0) like full sanitization or gratuitous inflation.
Provides deterministic text-to-vector estimators and full LLM JSON evaluators.
"""

from __future__ import annotations
import re
import json
from typing import Dict, Any, Tuple, List, Optional
from pydantic import BaseModel, Field


class LiteraryIntensityVector(BaseModel):
    profanity: float = Field(default=0.0, ge=0.0, le=5.0)
    sexual_intimacy: float = Field(default=0.0, ge=0.0, le=5.0)
    violence: float = Field(default=0.0, ge=0.0, le=5.0)
    emotional_intensity: float = Field(default=2.0, ge=0.0, le=5.0)
    formality: float = Field(default=2.5, ge=0.0, le=5.0)
    urdu_register: float = Field(default=1.5, ge=0.0, le=5.0)
    colloquiality: float = Field(default=2.0, ge=0.0, le=5.0)


class IntensityEvaluationResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    max_delta: float
    dimension_deltas: Dict[str, float]
    warnings: List[str] = Field(default_factory=list)
    failure_reasons: List[str] = Field(default_factory=list)
    source_vector: Optional[LiteraryIntensityVector] = None
    target_vector: Optional[LiteraryIntensityVector] = None


class IntensityEvaluator:
    # Heuristic thresholds
    SOFT_HEURISTIC_THRESHOLD = 0.75
    HARD_REJECTION_THRESHOLD = 2.0

    @classmethod
    def compare_vectors(
        cls,
        source_vec: LiteraryIntensityVector,
        target_vec: LiteraryIntensityVector,
    ) -> IntensityEvaluationResult:
        """
        Compares source and target intensity vectors.
        Enforces 'Nothing Above Source' while treating ±0.75 as a soft heuristic.
        """
        source_dict = source_vec.model_dump()
        target_dict = target_vec.model_dump()

        deltas: Dict[str, float] = {}
        warnings: List[str] = []
        failures: List[str] = []

        max_delta = 0.0

        for dim in source_dict.keys():
            s_val = source_dict[dim]
            t_val = target_dict[dim]
            delta = t_val - s_val
            abs_delta = abs(delta)
            deltas[dim] = round(delta, 2)

            if abs_delta > max_delta:
                max_delta = abs_delta

            # Check for hard rejection (> 2.0 divergence)
            if abs_delta > cls.HARD_REJECTION_THRESHOLD:
                if delta < 0:
                    failures.append(
                        f"CRITICAL SANITIZATION on '{dim}': source was {s_val:.1f} but target dropped to {t_val:.1f} (delta: {delta:.2f})"
                    )
                else:
                    failures.append(
                        f"CRITICAL UNJUSTIFIED AMPLIFICATION on '{dim}': source was {s_val:.1f} but target inflated to {t_val:.1f} (delta: {delta:.2f})"
                    )
            # Check for soft warning (0.75 < abs_delta <= 2.0)
            elif abs_delta > cls.SOFT_HEURISTIC_THRESHOLD:
                if delta < 0:
                    warnings.append(
                        f"Mild softening on '{dim}': source {s_val:.1f} -> target {t_val:.1f} (delta: {delta:.2f})"
                    )
                else:
                    warnings.append(
                        f"Mild elevation on '{dim}': source {s_val:.1f} -> target {t_val:.1f} (delta: {delta:.2f})"
                    )

        if failures:
            return IntensityEvaluationResult(
                is_valid=False,
                status="FAIL",
                max_delta=round(max_delta, 2),
                dimension_deltas=deltas,
                warnings=warnings,
                failure_reasons=failures,
                source_vector=source_vec,
                target_vector=target_vec,
            )
        elif warnings:
            return IntensityEvaluationResult(
                is_valid=True,
                status="WARN",
                max_delta=round(max_delta, 2),
                dimension_deltas=deltas,
                warnings=warnings,
                failure_reasons=[],
                source_vector=source_vec,
                target_vector=target_vec,
            )
        else:
            return IntensityEvaluationResult(
                is_valid=True,
                status="PASS",
                max_delta=round(max_delta, 2),
                dimension_deltas=deltas,
                warnings=[],
                failure_reasons=[],
                source_vector=source_vec,
                target_vector=target_vec,
            )

    @classmethod
    def estimate_source_intensity(
        cls,
        source_text: str,
        semantic_map: Optional[Any] = None,
        call_llm_fn: Optional[Any] = None,
    ) -> LiteraryIntensityVector:
        """
        Estimates the 7-dimensional intensity vector of English source text.
        Step 1: Deterministic lexical & syntactic analysis.
        Step 2: Full LLM JSON refinement if call_llm_fn is provided (Decision A3).
        """
        text_lower = source_text.lower()
        words = re.findall(r"\b[a-z']+\b", text_lower)
        total_words = max(1, len(words))

        # Profanity count
        profanity_set = {"damn", "bastard", "bitch", "hell", "crap", "whore", "piss", "shit", "fuck", "bloody"}
        p_count = sum(1 for w in words if w in profanity_set)
        p_score = min(5.0, round(p_count * (100.0 / total_words) * 1.5, 1))

        # Violence count
        violence_set = {"blade", "sword", "blood", "cut", "slash", "kill", "stab", "corpse", "wound", "death", "strike", "shattered", "choke", "pierce", "fist", "blow", "agony"}
        v_count = sum(1 for w in words if w in violence_set)
        v_score = min(5.0, round(v_count * (100.0 / total_words) * 1.2, 1))

        # Sexual intimacy count
        intimacy_set = {"naked", "caress", "kiss", "bed", "embrace", "skin", "lips", "breast", "thigh", "undress", "moan", "touch", "body"}
        s_count = sum(1 for w in words if w in intimacy_set)
        s_score = min(5.0, round(s_count * (100.0 / total_words) * 1.5, 1))

        # Emotional intensity from exclamation and dramatic speech verbs
        excl_count = source_text.count("!")
        shout_count = sum(1 for w in words if w in {"screamed", "shouted", "yelled", "cried", "roared", "gasped"})
        emo_score = min(5.0, max(1.0, round(2.0 + (excl_count * 0.3) + (shout_count * 0.4), 1)))

        # Formality
        formal_set = {"furthermore", "consequently", "majesty", "honor", "reverence", "sanctuary", "abbess", "indeed", "perhaps", "solemn"}
        form_count = sum(1 for w in words if w in formal_set)
        form_score = min(5.0, max(1.0, round(2.5 + (form_count * 0.4), 1)))

        # Colloquiality
        colloq_set = {"don't", "can't", "won't", "didn't", "it's", "ain't", "gonna", "wanna", "yeah", "hey"}
        c_count = sum(1 for w in words if w in colloq_set)
        colloq_score = min(5.0, max(1.0, round(1.5 + (c_count * (100.0 / total_words) * 0.8), 1)))

        urdu_score = 1.5

        base_vec = LiteraryIntensityVector(
            profanity=p_score,
            sexual_intimacy=s_score,
            violence=v_score,
            emotional_intensity=emo_score,
            formality=form_score,
            urdu_register=urdu_score,
            colloquiality=colloq_score,
        )

        if call_llm_fn is not None:
            prompt = f"""Estimate the literary intensity vector for this passage on a 0.0 to 5.0 scale.
Passage:
\"\"\"
{source_text[:2000]}
\"\"\"
Output valid JSON:
{{
  "profanity": float (0.0 to 5.0),
  "sexual_intimacy": float (0.0 to 5.0),
  "violence": float (0.0 to 5.0),
  "emotional_intensity": float (0.0 to 5.0),
  "formality": float (0.0 to 5.0),
  "colloquiality": float (0.0 to 5.0)
}}
"""
            try:
                resp = call_llm_fn(prompt, system_instruction="Output JSON only.", json_mode=True)
                data = json.loads(resp) if isinstance(resp, str) else resp
                return LiteraryIntensityVector(
                    profanity=float(data.get("profanity", base_vec.profanity)),
                    sexual_intimacy=float(data.get("sexual_intimacy", base_vec.sexual_intimacy)),
                    violence=float(data.get("violence", base_vec.violence)),
                    emotional_intensity=float(data.get("emotional_intensity", base_vec.emotional_intensity)),
                    formality=float(data.get("formality", base_vec.formality)),
                    urdu_register=base_vec.urdu_register,
                    colloquiality=float(data.get("colloquiality", base_vec.colloquiality)),
                )
            except Exception:
                pass

        return base_vec

    @classmethod
    def estimate_target_intensity(
        cls,
        target_text: str,
        target_map: Optional[Any] = None,
        source_vector: Optional[LiteraryIntensityVector] = None,
        call_llm_fn: Optional[Any] = None,
    ) -> LiteraryIntensityVector:
        """
        Estimates the 7-dimensional intensity vector of Hindi target text.
        Step 1: Deterministic lexical & syntactic analysis.
        Step 2: Full LLM JSON refinement if call_llm_fn is provided (Decision A3).
        """
        words = re.findall(r"[\u0900-\u097F]+", target_text)
        total_words = max(1, len(words))

        # Profanity count
        hindi_profanity = {"कमीना", "हरामी", "कुत्ता", "साला", "बदमाश", "रांड", "भड़वा"}
        p_count = sum(1 for w in words if w in hindi_profanity)
        p_score = min(5.0, round(p_count * (100.0 / total_words) * 1.5, 1))

        # Violence count
        hindi_violence = {"तलवार", "ख़ून", "रक्त", "ज़ख़्म", "वार", "मारा", "क़त्ल", "मौत", "लाश", "चीर", "गला", "काट", "चीख़"}
        v_count = sum(1 for w in words if w in hindi_violence)
        v_score = min(5.0, round(v_count * (100.0 / total_words) * 1.2, 1))

        # Intimacy count
        hindi_intimacy = {"नग्न", "आलिंगन", "चुंबन", "होंठ", "बिस्तर", "स्पर्श", "बदन", "साँसें"}
        s_count = sum(1 for w in words if w in hindi_intimacy)
        s_score = min(5.0, round(s_count * (100.0 / total_words) * 1.5, 1))

        # Emotional intensity
        excl_count = target_text.count("!")
        shout_count = sum(1 for w in words if w in {"चिल्लाया", "चिल्लाई", "चीख़ा", "चीख़ी", "दहाड़ा"})
        emo_score = min(5.0, max(1.0, round(2.0 + (excl_count * 0.3) + (shout_count * 0.4), 1)))

        # Formality from honorifics
        has_aap = "आप" in words or "आपने" in words
        form_score = min(5.0, max(1.0, 3.5 if has_aap else 2.0))

        # Urdu register count
        urdu_words = {"सन्नाटा", "ख़ंजर", "ज़ख़्म", "ख़ौफ़", "दस्तक", "इश्क़", "शराब", "हैरत", "सलाम", "अदा", "नफ़रत", "अफ़सोस", "तक़दीर", "फ़ैसला"}
        u_count = sum(1 for w in words if w in urdu_words)
        urdu_score = min(5.0, max(1.0, round(1.5 + (u_count * 0.3), 1)))

        colloq_score = 2.0
        if "यार" in words or "अरे" in words or "काहे" in words:
            colloq_score = 3.0

        base_vec = LiteraryIntensityVector(
            profanity=p_score,
            sexual_intimacy=s_score,
            violence=v_score,
            emotional_intensity=emo_score,
            formality=form_score,
            urdu_register=urdu_score,
            colloquiality=colloq_score,
        )

        if call_llm_fn is not None:
            prompt = f"""Estimate the literary intensity vector for this Hindi passage on a 0.0 to 5.0 scale.
Passage:
\"\"\"
{target_text[:2000]}
\"\"\"
Output valid JSON:
{{
  "profanity": float (0.0 to 5.0),
  "sexual_intimacy": float (0.0 to 5.0),
  "violence": float (0.0 to 5.0),
  "emotional_intensity": float (0.0 to 5.0),
  "formality": float (0.0 to 5.0),
  "urdu_register": float (0.0 to 5.0),
  "colloquiality": float (0.0 to 5.0)
}}
"""
            try:
                resp = call_llm_fn(prompt, system_instruction="Output JSON only.", json_mode=True)
                data = json.loads(resp) if isinstance(resp, str) else resp
                return LiteraryIntensityVector(
                    profanity=float(data.get("profanity", base_vec.profanity)),
                    sexual_intimacy=float(data.get("sexual_intimacy", base_vec.sexual_intimacy)),
                    violence=float(data.get("violence", base_vec.violence)),
                    emotional_intensity=float(data.get("emotional_intensity", base_vec.emotional_intensity)),
                    formality=float(data.get("formality", base_vec.formality)),
                    urdu_register=float(data.get("urdu_register", base_vec.urdu_register)),
                    colloquiality=float(data.get("colloquiality", base_vec.colloquiality)),
                )
            except Exception:
                pass

        return base_vec

    @classmethod
    def evaluate_scene_intensity(
        cls,
        source_text: str,
        target_text: str,
        source_vec: Optional[LiteraryIntensityVector] = None,
        target_vec: Optional[LiteraryIntensityVector] = None,
        call_llm_fn: Optional[Any] = None,
    ) -> IntensityEvaluationResult:
        """Evaluates source vs target intensity and returns comparison result."""
        if source_vec is None:
            source_vec = cls.estimate_source_intensity(source_text, call_llm_fn=call_llm_fn)
        if target_vec is None:
            target_vec = cls.estimate_target_intensity(target_text, source_vector=source_vec, call_llm_fn=call_llm_fn)
        return cls.compare_vectors(source_vec, target_vec)
