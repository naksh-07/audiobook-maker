#!/usr/bin/env python3
"""
Audiobook Factory - Targeted Pronunciation Repair Engine.
Executes surgical, take-level re-synthesis when PronunciationAudioQA flags omissions
or phonetic errors. Modifies spoken representation without ever mutating literary text
or regenerating unaffected segments.
"""

from __future__ import annotations
import re
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.performance.contracts import TakeVariant, PerformanceDirection
from .contracts import (
    PronunciationAudioQAResult,
    PronunciationStatus,
    SpokenTextResult,
)
from .auditor import PronunciationAudioQA


class PronunciationRepairEngine:
    """
    Surgical single-take repair coordinator.
    Enforces a strict circuit breaker of max 1 targeted repair attempt to eliminate
    the risk of infinite retry loops or quota exhaustion.
    """

    def __init__(self, auditor: Optional[PronunciationAudioQA] = None):
        self.auditor = auditor or PronunciationAudioQA()

    def generate_repaired_spoken_text(
        self,
        current_spoken_text: str,
        qa_result: PronunciationAudioQAResult,
    ) -> str:
        """
        Adjusts the spoken text representation for the retry take:
        1. If a token was swallowed/omitted, insulates it with breathing pauses (commas)
           or explicit phonetic anchoring.
        2. If a token suffered stutter/repetition, strips adjacent confusing punctuation.
        """
        repaired = current_spoken_text

        # 1. Swallowed / Omitted tokens repair: insert rhythmic punctuation anchor
        for omission_msg in qa_result.omissions:
            # Extract token between quotes
            m = re.search(r"'(.*?)'", omission_msg)
            if m:
                target_token = m.group(1).strip()
                # Wrap token in gentle micro-pauses: e.g. "token" -> ", token ,"
                # Avoid doubling commas if already present
                pat = re.compile(rf"(?<!,)\b({re.escape(target_token)})\b(?!,)", re.IGNORECASE)
                repaired = pat.sub(r", \1 ,", repaired)

        # 2. Clean multiple consecutive commas or punctuation collisions (e.g. ", ." or ", !")
        repaired = re.sub(r",\s*([.!?।,;])", r"\1", repaired)
        repaired = re.sub(r"([.!?।,;])\s*,", r"\1", repaired)
        repaired = re.sub(r",\s*,+", ",", repaired)
        repaired = re.sub(r"\s+", " ", repaired).strip()

        return repaired

    def attempt_repair(
        self,
        dispatcher: Any,
        segment: Dict[str, Any],
        failed_take: TakeVariant,
        qa_result: PronunciationAudioQAResult,
        chapter_num: int,
        seg_num: int,
        p_dir: Optional[PerformanceDirection] = None,
    ) -> Optional[TakeVariant]:
        """
        Attempts a targeted repair for a failed take.
        Enforces a strict circuit breaker of max 1 targeted repair attempt per segment.
        Returns the new winning TakeVariant if the repair succeeded, or None if repair failed.
        """
        if qa_result.passed:
            return failed_take

        # Circuit breaker: Never retry a take that is itself already a repair attempt
        if failed_take.take_id.endswith("_repair_pron") or failed_take.variant_type == "alternative_cadence":
            logger.warning(
                f"  [PRONUNCIATION REPAIR] Segment {seg_num}: Circuit breaker tripped - "
                f"take {failed_take.take_id} was already a repair attempt. Halting retries."
            )
            return None

        logger.info(
            f"  [PRONUNCIATION REPAIR] Segment {seg_num}: Initiating targeted repair "
            f"(Issues: {qa_result.review_reasons})"
        )

        current_spoken = segment.get("spoken_text", segment.get("text", ""))
        repaired_spoken = self.generate_repaired_spoken_text(current_spoken, qa_result)

        if repaired_spoken == current_spoken:
            logger.info("  [PRONUNCIATION REPAIR] No heuristic phonetic mutation available. Keeping baseline.")
            return None

        # Build repair take file path
        repair_take_path = dispatcher.take_bank.takes_dir / f"c{chapter_num:03d}_s{seg_num:04d}_repair_pron.wav"
        tmp_repair_path = dispatcher.take_bank.takes_dir / f"c{chapter_num:03d}_s{seg_num:04d}_repair_pron.tmp.wav"

        sp_cfg = dispatcher.get_speaker_config(failed_take.direction.speaker, segment.get("type", "narration"))
        voice = sp_cfg.get("voice", dispatcher.default_voice)
        direction = p_dir or failed_take.direction

        try:
            # Re-synthesize ONLY this affected segment atomically with the repaired spoken text
            from audiobook_factory.tts_dispatcher import synthesize_gemini_tts
            synthesize_gemini_tts(
                text=repaired_spoken,
                output_file=tmp_repair_path,
                voice=voice,
                emotion=segment.get("emotion", "neutral"),
                acting=segment.get("acting", {}),
                intensity=segment.get("intensity_level", "medium"),
                memory_vocal_constraint=segment.get("memory_vocal_constraint"),
                performance_direction=direction,
                variant_type="alternative_cadence",
                rate_limiter=dispatcher.rate_limiter,
            )

            # Atomic promotion of synthesized WAV to prevent orphan garbage on failure
            if tmp_repair_path.exists():
                tmp_repair_path.replace(repair_take_path)

            # Register take in TakeBank
            repaired_take = dispatcher.take_bank.create_take(
                segment_uid=direction.segment_uid,
                segment_index=seg_num,
                variant_type="alternative_cadence",
                audio_file=repair_take_path,
                direction=direction,
            )

            # Re-run Pronunciation QA with original resolutions so the auditor actually verifies the token
            repaired_resolutions = []
            meta_list = segment.get("pronunciation_metadata", [])
            from .contracts import PronunciationResolutionResult
            for m_dict in meta_list:
                if isinstance(m_dict, dict):
                    try:
                        repaired_resolutions.append(PronunciationResolutionResult.model_validate(m_dict))
                    except Exception:
                        pass

            spoken_mock = SpokenTextResult(
                literary_text=segment.get("text", ""),
                display_text=segment.get("text", ""),
                spoken_text=repaired_spoken,
                resolutions=repaired_resolutions,
            )
            new_qa = self.auditor.audit_take(
                take_audio_path=repair_take_path,
                spoken_result=spoken_mock,
                take_id=repaired_take.take_id,
                segment_uid=direction.segment_uid,
            )

            if new_qa.passed or len(new_qa.omissions) < len(qa_result.omissions):
                repaired_take.is_selected = True
                repaired_take.selection_reason = (
                    f"Selected repaired pronunciation take: resolved issues from {failed_take.take_id}."
                )
                failed_take.is_selected = False
                failed_take.selection_reason = f"Replaced by pronunciation-repaired take {repaired_take.take_id}."
                logger.info(f"  [+] [PRONUNCIATION REPAIR SUCCESS] Segment {seg_num} repaired take promoted!")
                return repaired_take
            else:
                logger.warning(f"  [!] [PRONUNCIATION REPAIR FAILED] Retried take did not pass. Retaining baseline with REVIEW_REQUIRED.")
                failed_take.selection_reason += f" (Pronunciation issues remain: {new_qa.review_reasons})"
                return None

        except Exception as e:
            if tmp_repair_path.exists():
                try:
                    tmp_repair_path.unlink()
                except Exception:
                    pass
            logger.error(f"  [ERROR] Pronunciation repair failed: {e}")
            return None
