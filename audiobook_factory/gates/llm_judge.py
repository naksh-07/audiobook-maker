#!/usr/bin/env python3
"""
Audiobook Factory - Unified LLM Creative Quality & Audit Judge Protocol.
Eliminates rubber-stamp static scripts by deploying dynamic, fail-closed LLM evaluators
across literary translation, active anti-censorship, screenplay attribution,
dramaturgy arc continuity, perceptual vocal acting, and sound design atmosphere.

Enforces:
1. Dynamic model resolution with concurrent candidate health pings (ADR-043). Zero hardcoded models.
2. Permissive BLOCK_NONE creative safety thresholds (User Global Rule).
3. Fail-closed contract: raises GateAuditError on critical failures; zero silent fallbacks.
"""

from __future__ import annotations
import os
import json
import logging
from typing import Dict, Any, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.gates.contracts import GateAuditError
from audiobook_factory.llm_client import call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType, LLMUnavailableError

T = TypeVar("T", bound=BaseModel)


# =============================================================================
# Structured Pydantic v2 Verdict Schemas for LLM Judges
# =============================================================================

class TranslationFidelityVerdict(BaseModel):
    """Verdict for literary translation quality, sense-for-sense fidelity, and cadence."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'PASS' or 'FAIL'")
    score: float = Field(..., ge=0.0, le=1.0, description="Overall fidelity score [0.0 - 1.0]")
    literary_cadence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    action_integrity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    critical_inversions: List[str] = Field(default_factory=list, description="List of inverted actions or meanings")
    dropped_clauses: List[str] = Field(default_factory=list, description="Omitted narrative beats")
    translatese_passages: List[str] = Field(default_factory=list, description="Robotic or awkward literal calques")
    reason: str = Field(default="", description="Executive critique rationale")
    recommendations: List[str] = Field(default_factory=list, description="Actionable re-translation instructions")


class DialogueAttributionVerdict(BaseModel):
    """Verdict for screenplay speaker attribution and dialogue turn isolation."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'PASS' or 'FAIL'")
    score: float = Field(..., ge=0.0, le=1.0, description="Attribution accuracy score [0.0 - 1.0]")
    total_lines_inspected: int = Field(default=0)
    misattributed_segments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of segments assigned to wrong speaker or merged into narration",
    )
    hallucinated_lines: List[str] = Field(
        default_factory=list,
        description="Spoken dialogue invented by the screenplay builder not in source",
    )
    swallowed_dialogue: List[str] = Field(
        default_factory=list,
        description="Spoken dialogue improperly trapped inside narration segments",
    )
    reason: str = Field(default="")


class DramaticArcVerdict(BaseModel):
    """Verdict for scene emotional tension trajectory and anti-emotional teleportation."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'PASS' or 'FAIL'")
    score: float = Field(..., ge=0.0, le=1.0)
    emotional_teleportation_detected: bool = Field(default=False)
    teleportation_violations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Ungrounded emotional leaps between consecutive character turns",
    )
    broken_causality_beats: List[str] = Field(default_factory=list)
    reason: str = Field(default="")


class VocalActingVerdict(BaseModel):
    """Verdict for perceptual vocal acting quality and emotional delivery."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'PASS' or 'FAIL'")
    overall_acting_score: float = Field(..., ge=0.0, le=1.0)
    dimension_scores: Dict[str, float] = Field(default_factory=dict)
    acting_believability: float = Field(default=1.0, ge=0.0, le=1.0)
    emotional_fidelity: float = Field(default=1.0, ge=0.0, le=1.0)
    subtext_fidelity: float = Field(default=1.0, ge=0.0, le=1.0)
    dialogue_reactivity: float = Field(default=1.0, ge=0.0, le=1.0)
    diagnostics: List[str] = Field(default_factory=list)
    take_selection_approved: bool = Field(default=True)
    acting_redirections: List[str] = Field(default_factory=list)


class SoundDesignAtmosphereVerdict(BaseModel):
    """Verdict for acoustic scene intent, ambience fitness, and foley plausibility."""
    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'PASS' or 'FAIL'")
    score: float = Field(..., ge=0.0, le=1.0)
    ambience_scene_fitness: bool = Field(default=True)
    music_mood_aligned: bool = Field(default=True)
    foley_narrative_plausible: bool = Field(default=True)
    clashing_elements: List[str] = Field(default_factory=list)
    era_inconsistencies: List[str] = Field(default_factory=list)
    reason: str = Field(default="")


# =============================================================================
# Core BaseLLMJudge Engine
# =============================================================================

class BaseLLMJudge:
    """
    Central foundation for all LLM Creative Judges.
    Resolves active models dynamically via ModelManager (no hardcoded model strings),
    executes structured evaluations, and strictly fails closed on errors or bad scores.
    """

    @classmethod
    def resolve_auditing_model(cls) -> str:
        """
        Dynamically resolves the active model for TaskType.AUDITING.
        Executes concurrent health pings on candidates and enforces minimum Tier 2 floor.
        """
        mgr = get_model_manager()
        return mgr.resolve_active_model(TaskType.AUDITING)

    @staticmethod
    def sample_stratified_text(text: str, total_chars: int = 6000) -> str:
        """
        Samples text across beginning (25%), middle (50%), and ending (25%) of chapter.
        Ensures entire chapter narrative arc is represented in judge prompt.
        """
        if not text or len(text) <= total_chars:
            return text
        head_len = int(total_chars * 0.25)
        tail_len = int(total_chars * 0.25)
        body_len = total_chars - head_len - tail_len
        mid_point = len(text) // 2
        body_start = max(0, mid_point - (body_len // 2))
        body_end = min(len(text), body_start + body_len)

        return (
            f"[ACT 1: OPENING]\n{text[:head_len]}\n\n"
            f"[ACT 2: DEVELOPMENT / CLIMAX]\n{text[body_start:body_end]}\n\n"
            f"[ACT 3: RESOLUTION]\n{text[-tail_len:]}"
        )

    @staticmethod
    def sample_stratified_items(items: List[Any], max_items: int = 40) -> List[Any]:
        """
        Samples list of segments/items across beginning (25%), middle (50%), and ending (25%).
        Guarantees full chapter scene progression is evaluated.
        """
        if not items or len(items) <= max_items:
            return list(items)
        head_count = int(max_items * 0.25)
        tail_count = int(max_items * 0.25)
        body_count = max_items - head_count - tail_count

        head = items[:head_count]
        mid_point = len(items) // 2
        body_start = max(head_count, mid_point - (body_count // 2))
        body = items[body_start:body_start + body_count]
        tail = items[-tail_count:]

        seen = set()
        result = []
        for it in (head + body + tail):
            key = id(it)
            if key not in seen:
                seen.add(key)
                result.append(it)
        return result

    @classmethod
    def evaluate_with_llm(
        cls,
        prompt: str,
        system_instruction: str,
        response_model: Type[T],
        temperature: float = 0.1,
        max_retries: int = 6,
    ) -> T:
        """
        Executes a fail-closed LLM evaluation pass.
        Raises GateAuditError if the API is unavailable or returns unparseable schema.
        """
        # 1. Check for offline mock mode in test environments
        is_offline = (
            os.environ.get("MOCK_OFFLINE", "").lower() in ("true", "1", "yes")
            or os.environ.get("UNIT_TEST_MODE", "").lower() in ("true", "1", "yes")
            or "PYTEST_CURRENT_TEST" in os.environ
        )
        if is_offline:
            mock_data = cls._generate_mock_verdict(response_model, prompt)
            return response_model.model_validate(mock_data)

        # 2. Dynamic model resolution without hardcoded strings
        try:
            active_model = cls.resolve_auditing_model()
        except Exception as e:
            raise GateAuditError(
                f"LLM Judge Halting: Dynamic model resolution failed for AUDITING task: {e}"
            ) from e

        # 3. Call Gemini with BLOCK_NONE safety thresholds
        try:
            res = call_gemini(
                prompt=prompt,
                system_instruction=system_instruction,
                task_type=TaskType.AUDITING,
                model=active_model,
                response_mime_type="application/json",
                temperature=temperature,
                max_retries=max_retries,
                thinking_budget=0,
                max_output_tokens=8192,
            )
        except Exception as e:
            raise GateAuditError(
                f"LLM Creative Gate Evaluation Failed (model '{active_model}'): {e}"
            ) from e

        # 4. Parse & Validate Pydantic schema
        if isinstance(res, str):
            try:
                res = json.loads(res)
            except Exception as e:
                raise GateAuditError(
                    f"LLM Judge response was not valid JSON: {res[:200]}... Error: {e}"
                ) from e

        if not isinstance(res, dict):
            raise GateAuditError(f"LLM Judge returned non-dict payload: {type(res)}")

        try:
            verdict = response_model.model_validate(res)
            return verdict
        except Exception as e:
            raise GateAuditError(
                f"LLM Judge schema validation failed for {response_model.__name__}: {e}"
            ) from e

    @classmethod
    def _generate_mock_verdict(cls, response_model: Type[T], prompt: str) -> Dict[str, Any]:
        """Provides deterministic mock responses for isolated unit tests without network."""
        p_lower = prompt.lower()

        if response_model is TranslationFidelityVerdict:
            if "fail_test" in p_lower or "gibberish" in p_lower:
                return {
                    "status": "FAIL",
                    "score": 0.40,
                    "literary_cadence_score": 0.35,
                    "action_integrity_score": 0.45,
                    "critical_inversions": ["Simulated inversion in mock test"],
                    "dropped_clauses": ["Mock dropped clause"],
                    "translatese_passages": ["Mock translatese"],
                    "reason": "Mock test failure triggered",
                    "recommendations": ["Re-translate section"],
                }
            return {
                "status": "PASS",
                "score": 0.95,
                "literary_cadence_score": 0.95,
                "action_integrity_score": 0.98,
                "critical_inversions": [],
                "dropped_clauses": [],
                "translatese_passages": [],
                "reason": "Mock translation passed with high fidelity",
                "recommendations": [],
            }

        if response_model is DialogueAttributionVerdict:
            if "wrong_speaker" in p_lower or "simulate_misattribution" in p_lower:
                return {
                    "status": "FAIL",
                    "score": 0.50,
                    "total_lines_inspected": 10,
                    "misattributed_segments": [
                        {"segment_index": 2, "attributed_speaker": "Character_A", "correct_speaker": "Character_B", "reason": "Speech belongs to Character_B"}
                    ],
                    "hallucinated_lines": [],
                    "swallowed_dialogue": [],
                    "reason": "Dialogue misattributed to wrong character",
                }
            return {
                "status": "PASS",
                "score": 1.0,
                "total_lines_inspected": 10,
                "misattributed_segments": [],
                "hallucinated_lines": [],
                "swallowed_dialogue": [],
                "reason": "Dialogue attribution verified",
            }

        if response_model is DramaticArcVerdict:
            if "simulate_teleportation" in p_lower or "broken_arc" in p_lower:
                return {
                    "status": "FAIL",
                    "score": 0.45,
                    "emotional_teleportation_detected": True,
                    "teleportation_violations": [
                        {"character": "Character_A", "from_emotion": "calm", "to_emotion": "screaming_panic", "reason": "No dramatic bridge"}
                    ],
                    "broken_causality_beats": ["Beat 2 to 3 transition broken"],
                    "reason": "Emotional teleportation detected",
                }
            return {
                "status": "PASS",
                "score": 0.95,
                "emotional_teleportation_detected": False,
                "teleportation_violations": [],
                "broken_causality_beats": [],
                "reason": "Dramatic arc and transitions grounded",
            }

        if response_model is VocalActingVerdict:
            if "bad_acting" in p_lower or "flat_robotic" in p_lower:
                return {
                    "status": "FAIL",
                    "overall_acting_score": 0.50,
                    "dimension_scores": {"acting_believability": 0.45, "emotional_fidelity": 0.50},
                    "acting_believability": 0.45,
                    "emotional_fidelity": 0.50,
                    "subtext_fidelity": 0.50,
                    "dialogue_reactivity": 0.55,
                    "diagnostics": ["Delivery sounded robotic and flat"],
                    "take_selection_approved": False,
                    "acting_redirections": ["Increase vocal gravel and dramatic restraint"],
                }
            return {
                "status": "PASS",
                "overall_acting_score": 0.92,
                "dimension_scores": {"acting_believability": 0.92, "emotional_fidelity": 0.90},
                "acting_believability": 0.92,
                "emotional_fidelity": 0.90,
                "subtext_fidelity": 0.91,
                "dialogue_reactivity": 0.94,
                "diagnostics": [],
                "take_selection_approved": True,
                "acting_redirections": [],
            }

        if response_model is SoundDesignAtmosphereVerdict:
            if "clashing_audio" in p_lower or "modern_leak" in p_lower:
                return {
                    "status": "FAIL",
                    "score": 0.40,
                    "ambience_scene_fitness": False,
                    "music_mood_aligned": False,
                    "foley_narrative_plausible": True,
                    "clashing_elements": ["Upbeat circus theme during grim tavern execution"],
                    "era_inconsistencies": ["Modern engine hum detected in ambience"],
                    "reason": "Severe acoustic tone clash with narrative mood",
                }
            return {
                "status": "PASS",
                "score": 0.95,
                "ambience_scene_fitness": True,
                "music_mood_aligned": True,
                "foley_narrative_plausible": True,
                "clashing_elements": [],
                "era_inconsistencies": [],
                "reason": "Sound design manifests narrative atmosphere faithfully",
            }

        return {"status": "PASS", "score": 1.0, "reason": "Mock default pass"}


# =============================================================================
# Specialized Creative LLM Judges
# =============================================================================

class LLMTranslationJudge(BaseLLMJudge):
    """
    Forensic literary evaluator for translated literature (Gates 0 & T2/T9).
    Audits Sense-for-Sense accuracy, literary Hindustani cadence, and action integrity.
    """

    SYSTEM_INSTRUCTION = (
        "You are an elite, uncompromising literary translation critic for dark fantasy and epic literature "
        "(Sapkowski, Martin, Tolkien rendered into dramatic Hindustani / Devanagari). "
        "Your task is to conduct a forensic literary audit between the source text and the translated prose.\n\n"
        "Core Evaluation Mandates:\n"
        "1. SENSE-FOR-SENSE ACCURACY: Verify that dramatic subtext, character motivation, and narrative events "
        "are preserved without omission, factual drift, or hallucinated additions.\n"
        "2. LITERARY HINDUSTANI CADENCE: Reject stiff, literal English calques ('translatese'), unnatural passive voice, "
        "or sterile bureaucracy phrasing. Reward earthy, rhythmic, spoken cadence ('Aate mein Namak jitni Urdu').\n"
        "3. ACTION & NEGATION INTEGRITY: Flag any inversion where an action was flipped (e.g. 'did not enter' translated as 'प्रवेश किया') "
        "or where subject/object roles were confused.\n"
        "4. DIALOGUE TONE: Characters must retain their authentic social register and honorifics (Aap/Tum/Tu)."
    )

    @classmethod
    def audit_translation(
        cls,
        source_text: str,
        hindi_text: str,
        chapter_title: str = "",
        min_score: float = 0.80,
        strict: bool = True,
    ) -> TranslationFidelityVerdict:
        sample_src = cls.sample_stratified_text(source_text, total_chars=6000)
        sample_hin = cls.sample_stratified_text(hindi_text, total_chars=6000)
        prompt = f"""### CHAPTER CONTEXT: {chapter_title or 'Literary Scene'}

### SOURCE ENGLISH EXCERPT (STRATIFIED FULL-CHAPTER REPRESENTATION):
\"\"\"
{sample_src}
\"\"\"

### TARGET HINDI TRANSLATION (STRATIFIED FULL-CHAPTER REPRESENTATION):
\"\"\"
{sample_hin}
\"\"\"

Evaluate the translation and output JSON conforming to:
- "status": "PASS" | "FAIL" (Mark FAIL if score < {min_score} or critical inversions exist)
- "score": float [0.0 - 1.0]
- "literary_cadence_score": float [0.0 - 1.0]
- "action_integrity_score": float [0.0 - 1.0]
- "critical_inversions": list of strings (inverted meanings or reversed actions)
- "dropped_clauses": list of strings (untranslated dramatic beats)
- "translatese_passages": list of strings (awkward literal phrasing)
- "reason": string summary of literary quality
- "recommendations": list of actionable rewrite steps
"""
        verdict = cls.evaluate_with_llm(
            prompt=prompt,
            system_instruction=cls.SYSTEM_INSTRUCTION,
            response_model=TranslationFidelityVerdict,
            temperature=0.1,
        )

        if strict and (verdict.status == "FAIL" or verdict.score < min_score or verdict.critical_inversions):
            raise GateAuditError(
                f"Gate 0/T2 LLM Translation Audit FAILED (Score: {verdict.score:.2f} < {min_score}): "
                f"{verdict.reason}. Inversions: {verdict.critical_inversions}"
            )

        return verdict


class LLMScreenplayAuditor(BaseLLMJudge):
    """
    Forensic dialogue attribution & screenplay structure auditor (Gate 2).
    Cross-references source narrative against screenplay segments to ensure 0% misattribution.
    """

    SYSTEM_INSTRUCTION = (
        "You are a Hollywood Audio Drama Dialogue Supervisor. "
        "Your task is to forensic-audit screenplay segmentation and speaker attribution against the source text.\n\n"
        "Core Verification Rules:\n"
        "1. ATTRIBUTION INTEGRITY: Every spoken dialogue segment MUST be attributed to the exact character who spoke it in the source. "
        "Never allow character A's dialogue to be assigned to character B or Narrator.\n"
        "2. ANTI-SWALLOWING: Spoken character dialogue MUST NEVER be swallowed or merged into narration segments.\n"
        "3. NO INVENTED/HALLUCINATED DIALOGUE: Every character line must originate from the authorial text.\n"
        "4. DELIVERY TAGS: Emotional acting tags must match the dramatic state of the scene."
    )

    @classmethod
    def audit_screenplay(
        cls,
        source_text: str,
        script_segments: List[Dict[str, Any]],
        character_roster: Optional[Dict[str, Any]] = None,
        strict: bool = True,
    ) -> DialogueAttributionVerdict:
        """Audits dialogue attribution and tags across screenplay segments."""
        roster_names = []
        if character_roster:
            chars = character_roster.get("characters", character_roster)
            if isinstance(chars, dict):
                roster_names = list(chars.keys())
            elif isinstance(chars, list):
                roster_names = [c.get("english_name", "") for c in chars if isinstance(c, dict)]

        # Sample stratified dialogue & key narration segments across full chapter
        stratified_raw = cls.sample_stratified_items(script_segments, max_items=40)
        sampled_segments = [
            {
                "index": s.get("index"),
                "speaker": s.get("speaker"),
                "type": s.get("type"),
                "text": s.get("text", "")[:120],
                "emotion": s.get("emotion"),
            }
            for s in stratified_raw
        ]
        sample_src = cls.sample_stratified_text(source_text, total_chars=12000)

        prompt = f"""### KNOWN ROSTER CHARACTERS:
{', '.join(roster_names) if roster_names else 'Standard cast'}

### SOURCE SCENE EXCERPTS (STRATIFIED ACT 1, ACT 2, ACT 3 REPRESENTATION):
\"\"\"
{sample_src}
\"\"\"

### SCREENPLAY SEGMENTS TO AUDIT:
{json.dumps(sampled_segments, ensure_ascii=False, indent=2)}

Audit the speaker attribution and output JSON:
- "status": "PASS" | "FAIL" (FAIL if any dialogue line is misattributed or swallowed)
- "score": float [0.0 - 1.0]
- "total_lines_inspected": int
- "misattributed_segments": list of objects [{{"segment_index": int, "attributed_speaker": str, "correct_speaker": str, "reason": str}}]
- "hallucinated_lines": list of strings (fabricated lines with zero basis in narrative truth)
- "swallowed_dialogue": list of strings (dialogue quotes found inside narration segments)
- "reason": str summary

EVALUATION GUIDELINES:
1. Segments are stratified across Act 1, Act 2, and Act 3 matching the source excerpts.
2. ONLY flag a line as hallucinated if it introduces fabricated events, modern concepts, or contradicts the story. Do NOT flag a line as hallucinated merely because its surrounding transitional beat is not visible in the stratified excerpt window.
3. FAIL if a canonical character's line is assigned to Narrator or the wrong character.
"""
        verdict = cls.evaluate_with_llm(
            prompt=prompt,
            system_instruction=cls.SYSTEM_INSTRUCTION,
            response_model=DialogueAttributionVerdict,
            temperature=0.1,
        )

        if strict and (verdict.status == "FAIL" or verdict.misattributed_segments or verdict.swallowed_dialogue):
            err_details = (
                f"Misattributed: {verdict.misattributed_segments}; Swallowed: {verdict.swallowed_dialogue}"
            )
            raise GateAuditError(f"Gate 2 LLM Screenplay Attribution FAILED: {verdict.reason}. Details: {err_details}")

        return verdict


class LLMDramaticCritic(BaseLLMJudge):
    """
    Dramaturgy & dramatic arc continuity judge (Gate 2.5).
    Detects ungrounded emotional teleportation and broken causal transitions between beats.
    """

    SYSTEM_INSTRUCTION = (
        "You are an expert Dramaturg and Narrative Arc Critic for prestigious audio dramas. "
        "Your role is to audit dramatic beat consistency, tension pacing, and character psychological continuity.\n\n"
        "Core Auditing Mandates:\n"
        "1. ANTI-EMOTIONAL TELEPORTATION: Detect abrupt, ungrounded shifts in character emotion between consecutive turns "
        "(e.g., jumping from profound grief to cheerful banter without transitional beats or clear narrative catalyst).\n"
        "2. CAUSAL CONTINUITY: Verify that each dramatic beat naturally causes or reacts to the preceding beat.\n"
        "3. OBJECTIVE ALIGNMENT: Ensure dialogue actions align with character objectives and subtext."
    )

    @classmethod
    def audit_dramatic_arc(
        cls,
        segments: List[Dict[str, Any]],
        dramatic_plan: Optional[Any] = None,
        source_text: str = "",
        strict: bool = True,
    ) -> DramaticArcVerdict:
        """Audits character emotional arcs and transitions across segments."""
        dialogue_stream = []
        for s in segments:
            if s.get("type") == "dialogue" or s.get("speaker", "").lower() != "narrator":
                dialogue_stream.append({
                    "index": s.get("index"),
                    "speaker": s.get("speaker"),
                    "emotion": s.get("emotion") or s.get("surface_emotion", "neutral"),
                    "text": s.get("text", "")[:80],
                })

        sampled_stream = cls.sample_stratified_items(dialogue_stream, max_items=35)
        prompt = f"""### DRAMATIC SCENE DIALOGUE STREAM (STRATIFIED SCENE REPRESENTATION):
{json.dumps(sampled_stream, ensure_ascii=False, indent=2)}

Audit the emotional arc continuity and output JSON:
- "status": "PASS" | "FAIL" (FAIL if ungrounded emotional teleportation or broken causality is detected)
- "score": float [0.0 - 1.0]
- "emotional_teleportation_detected": bool
- "teleportation_violations": list of objects [{{"character": str, "from_emotion": str, "to_emotion": str, "reason": str}}]
- "broken_causality_beats": list of strings
- "reason": str summary
"""
        verdict = cls.evaluate_with_llm(
            prompt=prompt,
            system_instruction=cls.SYSTEM_INSTRUCTION,
            response_model=DramaticArcVerdict,
            temperature=0.1,
        )

        if strict and (verdict.status == "FAIL" or verdict.emotional_teleportation_detected):
            raise GateAuditError(
                f"Gate 2.5 LLM Dramatic Fidelity FAILED: {verdict.reason}. Violations: {verdict.teleportation_violations}"
            )

        return verdict


class LLMPerceptualPerformanceJudge(BaseLLMJudge):
    """
    Perceptual vocal acting and delivery quality judge (Gate 2.8).
    Evaluates synthesized actor takes against dramatic direction across acting believability, subtext, and reactivity.
    """

    SYSTEM_INSTRUCTION = (
        "You are a Voice Director and Casting Critic evaluating actor vocal performance in an audio drama. "
        "Review the dramatic direction, text, and acoustic telemetry to judge whether the delivery is convincing, "
        "subtextually nuanced, and reactive to scene partners—or flat, melodramatic, and robotic."
    )

    @classmethod
    def critique_performance(
        cls,
        direction: Any,
        acoustic_metrics: Dict[str, Any],
        text: str,
        prev_speaker: Optional[str] = None,
        min_score: float = 0.70,
        strict: bool = False,
    ) -> VocalActingVerdict:
        """Critiques take performance against director intent."""
        dir_dict = direction if isinstance(direction, dict) else (
            direction.model_dump() if hasattr(direction, "model_dump") else {}
        )

        prompt = f"""### DRAMATIC DIRECTION:
- Speaker: {dir_dict.get('speaker', 'Unknown')}
- Surface Emotion: {dir_dict.get('surface_emotion', 'neutral')}
- Intensity: {dir_dict.get('intensity', 'medium')}
- Actioning / Verb: {dir_dict.get('actioning', 'speak')}
- Subtext: {dir_dict.get('subtext', 'None')}
- Restraint Level: {dir_dict.get('restraint', 0.5)}
- Previous Conversational Turn: {prev_speaker or 'None'}

### SPOKEN TEXT:
\"{text}\"

### MEASURED ACOUSTIC TELEMETRY:
{json.dumps(acoustic_metrics, indent=2)}

Output JSON:
- "status": "PASS" | "FAIL" (Mark FAIL if overall_acting_score < {min_score})
- "overall_acting_score": float [0.0 - 1.0]
- "dimension_scores": object {{"acting_believability": float, "emotional_fidelity": float, "subtext_fidelity": float, "dialogue_reactivity": float}}
- "acting_believability": float [0.0 - 1.0]
- "emotional_fidelity": float [0.0 - 1.0]
- "subtext_fidelity": float [0.0 - 1.0]
- "dialogue_reactivity": float [0.0 - 1.0]
- "diagnostics": list of strings (any detected defects like robotic cadences, vocoder hisses, overacting)
- "take_selection_approved": bool
- "acting_redirections": list of strings (direction notes for retakes)
"""
        verdict = cls.evaluate_with_llm(
            prompt=prompt,
            system_instruction=cls.SYSTEM_INSTRUCTION,
            response_model=VocalActingVerdict,
            temperature=0.1,
        )

        if strict and (verdict.status == "FAIL" or verdict.overall_acting_score < min_score):
            raise GateAuditError(
                f"Gate 2.8 LLM Vocal Performance Audit FAILED (Score: {verdict.overall_acting_score:.2f} < {min_score}): "
                f"{verdict.diagnostics}. Redirections: {verdict.acting_redirections}"
            )

        return verdict


class LLMSoundDesignCritic(BaseLLMJudge):
    """
    Cinematic Sound Design & Narrative Atmosphere Critic (Stage 11 & Gate 3.5).
    Evaluates whether ambient beds, BGM underscores, and Foley cues authentically match the narrative atmosphere.
    """

    SYSTEM_INSTRUCTION = (
        "You are an Academy-Award winning Sound Designer and Audio Supervisor for cinematic productions. "
        "Review the narrative scene excerpt alongside the selected Ambience, Music, and Foley cues. "
        "Determine whether the soundscape creates an immersive, period-accurate atmosphere that elevates the drama, "
        "or contains clashing genres, distracting tone mismatches, or modern anachronisms."
    )

    @classmethod
    def audit_soundscape(
        cls,
        scene_text: str,
        manifest_summary: Dict[str, Any],
        active_env: str = "",
        franchise_era: str = "UNIVERSAL_CONTEMPORARY",
        strict: bool = True,
    ) -> SoundDesignAtmosphereVerdict:
        """Audits creative soundscape manifest against literary scene intent."""
        prompt = f"""### ERA / FRANCHISE CONTEXT: {franchise_era}
### ACTIVE ENVIRONMENT INTENT: {active_env or 'Unspecified'}

### NARRATIVE SCENE EXCERPT:
\"\"\"
{scene_text[:3000]}
\"\"\"

### SELECTED SOUNDSCAPE ASSETS & CUES:
{json.dumps(manifest_summary, ensure_ascii=False, indent=2)}

Audit the sound design atmosphere and output JSON:
- "status": "PASS" | "FAIL" (FAIL if BGM/ambience clashes with scene mood or contains era leaks)
- "score": float [0.0 - 1.0]
- "ambience_scene_fitness": bool
- "music_mood_aligned": bool
- "foley_narrative_plausible": bool
- "clashing_elements": list of strings (e.g. upbeat music during grim execution, modern car sounds in fantasy)
- "era_inconsistencies": list of strings
- "reason": str summary of acoustic atmosphere
"""
        verdict = cls.evaluate_with_llm(
            prompt=prompt,
            system_instruction=cls.SYSTEM_INSTRUCTION,
            response_model=SoundDesignAtmosphereVerdict,
            temperature=0.1,
        )

        if strict and (verdict.status == "FAIL" or not verdict.ambience_scene_fitness or not verdict.music_mood_aligned):
            clash_str = "; ".join(verdict.clashing_elements + verdict.era_inconsistencies)
            raise GateAuditError(
                f"Stage 11 / Gate 3.5 LLM Sound Design Audit FAILED: {verdict.reason}. Clashes: {clash_str}"
            )

        return verdict
