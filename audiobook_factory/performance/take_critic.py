#!/usr/bin/env python3
"""
Audiobook Factory - Room 4 Agent C: Take Audition Critic.
Judicial LLM critic for high-stakes / critical scene speech takes.
Conducts comparative auditions between take candidates (e.g. standard vs more_vulnerable vs exposed),
evaluating acting realism, vocal strain, subtext alignment, and dramatic impact.
"""

from __future__ import annotations
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable

from audiobook_factory.llm_client import call_gemini as default_call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing

logger = logging.getLogger("AudiobookFactory")


class TakeAuditionCritic:
    """Agent C: High-Stakes Dramatic Audition & Comparative Take Critic."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.AUDITING)

    def select_best_take_audition(
        self,
        text: str,
        speaker: str,
        subtext: str,
        emotion: str,
        intensity: str,
        candidates: List[Dict[str, Any]],
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> Tuple[int, str]:
        """Compares multiple candidate takes and selects the winner with dramatic justification.
        Returns: (winning_index, justification)
        """
        if not candidates:
            return 0, "No candidates provided."
        if len(candidates) == 1:
            return 0, "Single candidate defaulted."

        model = self._resolve_model()
        fiction_framing = get_dramatic_fiction_framing()

        sys_prompt = (
            fiction_framing +
            "You are an Academy-Award winning Audio Drama Director and Sound Editor.\n"
            "You are auditioning takes for a high-stakes dramatic scene.\n"
            "Compare the audition takes based on:\n"
            "1. Subtext alignment: Does the delivery convey the unspoken psychological truth?\n"
            "2. Emotional truth & vocal strain: Does the performance sound like authentic human experience, "
            "avoiding generic robotic cadence?\n"
            "3. Intensity & Breath: Are the breath intakes, pauses, and intensity appropriate for the stakes?\n\n"
            "Output JSON with:\n"
            "- 'winner_index': int (0-based index of the superior take)\n"
            "- 'justification': string (concise artistic justification)"
        )

        prompt = f"""Dramatic Line:
\"{text}\"

Speaker: {speaker}
Intended Subtext: {subtext}
Target Emotion: {emotion}
Intensity: {intensity}

Candidate Audition Takes:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

Select the winning take index and explain why:
"""
        logger.info(f"  [TakeAuditionCritic] Auditioning {len(candidates)} takes for '{speaker}' using {model}...")

        try:
            if call_llm_fn:
                res = call_llm_fn(prompt=prompt, system_instruction=sys_prompt, model=model, json_mode=True)
                if isinstance(res, str):
                    import json_repair
                    res = json_repair.loads(res)
            else:
                res = default_call_gemini(
                    prompt=prompt,
                    system_instruction=sys_prompt,
                    task_type=TaskType.AUDITING,
                    response_mime_type="application/json",
                    max_output_tokens=4096,
                    thinking_budget=512,
                    max_retries=4,
                    model=model,
                )
        except Exception as e:
            logger.warning(f"  [!] TakeAuditionCritic notice: {e}. Defaulting to first candidate.")
            return 0, f"Critic fallback: {e}"

        winner_idx = 0
        justification = "Audition critic completed."
        if isinstance(res, dict):
            winner_idx = res.get("winner_index", 0)
            justification = res.get("justification", justification)

        if not isinstance(winner_idx, int) or winner_idx < 0 or winner_idx >= len(candidates):
            winner_idx = 0

        logger.info(f"  [TakeAuditionCritic] Take {winner_idx} selected: {justification[:100]}")
        return winner_idx, justification
