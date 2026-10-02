#!/usr/bin/env python3
"""
Audiobook Factory - Script Engine: Dramatized Screenplay Builder.
Coordinates beat-aligned chunking, two-pass parsing, and dramatic validation.
"""

from __future__ import annotations
import hashlib
import logging
from typing import List, Dict, Any, Optional

from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.model_manager import get_model_manager, TaskType, LLMUnavailableError
from audiobook_factory.dramaturgy.scene_analyzer import SceneAnalyzer
from audiobook_factory.dramaturgy.beat_planner import BeatPlanner
from audiobook_factory.dramaturgy.contracts import DramaticPlan
from audiobook_factory.dramaturgy.dramatic_validator import DramaticValidator
from audiobook_factory.script.staging_enricher import _parse_dramatized_chunk_llm
from audiobook_factory.script.screenplay_cleaner import clean_screenplay_pass2

logger = logging.getLogger("AudiobookFactory")


def _get_chunk_parser():
    import sys
    sb = sys.modules.get("audiobook_factory.script_builder")
    if sb and hasattr(sb, "_parse_dramatized_chunk_llm"):
        return sb._parse_dramatized_chunk_llm
    return _parse_dramatized_chunk_llm


def build_dramatized_script_llm(
    chapter_text: str,
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
    memory_context: Optional[Any] = None,
    chapter_num: int = 1,
    chapter_id: str = "chapter_001",
    return_dramatic_plan: bool = False,
) -> Any:
    """
    Dramatized Screenplay Mode with Dramatic Intelligence & Beat-Aligned Chunking:
    Builds chapter dramatic plan, aligns chunks to dramatic beats, and enriches segments
    with objectives, actioning verbs, subtext, tension curve, and epistemic bounds.
    """
    known_chars = None
    if character_roster and "characters" in character_roster:
        chars = character_roster["characters"]
        if isinstance(chars, dict):
            known_chars = list(chars.keys())
        elif isinstance(chars, list):
            known_chars = [c.get("english_name", "") for c in chars if isinstance(c, dict) and c.get("english_name")]

    # 1. Synthesize Holistic Chapter Dramatic Plan
    scenes = SceneAnalyzer.segment_and_analyze_scenes(
        chapter_text=chapter_text,
        chapter_num=chapter_num,
        chapter_title=f"Chapter {chapter_num}",
        known_characters=known_chars,
        memory_context=memory_context,
    )
    scenes = BeatPlanner.plan_chapter_beats(
        chapter_text=chapter_text,
        scenes=scenes,
        known_characters=known_chars,
        memory_context=memory_context,
    )
    total_beats = sum(len(s.beats) for s in scenes)
    s_hash = hashlib.sha256(chapter_text.encode("utf-8")).hexdigest()
    dramatic_plan = DramaticPlan(
        chapter_id=chapter_id,
        chapter_num=chapter_num,
        scenes=scenes,
        total_beats=total_beats,
        source_hash=s_hash,
    )

    pool = get_persistent_key_pool()
    api_key = pool.get_key(service="text") if pool else None
    if not api_key:
        try:
            from audiobook_factory.tts_dispatcher import global_key_pool
            api_key = global_key_pool.get_key(service="text")
        except Exception:
            pass

    if not api_key:
        logger.error("  [!] STRICT HALT: No text API key available for dramatized screenplay attribution.")
        raise LLMUnavailableError("API key pool exhausted for screenplay attribution. Production strictly halted.")

    model = get_model_manager().resolve_active_model(TaskType.SCREENPLAY, api_key=api_key)
    memory_prompt_str = (
        memory_context.get_prompt_context()
        if memory_context is not None and hasattr(memory_context, "get_prompt_context")
        else ""
    )

    # 2. Granular Micro-Chunking (~350 words ceiling) to eliminate token fatigue & ensure turn-level attribution
    max_chunk_words = 350
    words_count = len(chapter_text.split())

    if words_count <= max_chunk_words:
        dramatic_context_str = ""
        if scenes:
            primary_scene = scenes[0]
            ctx_parts = [
                f"Active Dramatic Scene: {primary_scene.scene_id} ({primary_scene.scene_type})",
                f"Setting: {primary_scene.location} ({primary_scene.time_context})",
                f"Dramatic Purpose: {primary_scene.dramatic_purpose}",
                f"Scene Question: {primary_scene.scene_question}",
                f"Stakes: {primary_scene.stakes}",
                f"Primary Conflict: {primary_scene.primary_conflict}",
            ]
            if primary_scene.listener_knowledge_state:
                ctx_parts.append(f"Audience Knowledge: {primary_scene.listener_knowledge_state}")
            if primary_scene.beats:
                ctx_parts.append("Planned Dramatic Beats:")
                for b in primary_scene.beats:
                    obj_s = f", Objective: '{b.objective.immediate_goal}'" if b.objective else ""
                    act_s = f", Actioning: '{b.objective.actioning}'" if b.objective else ""
                    ctx_parts.append(f"  - [{b.beat_id}] Function: {b.dramatic_function}{act_s}{obj_s}")
            dramatic_context_str = "\n".join(ctx_parts)

        raw_items = _get_chunk_parser()(
            chunk_text=chapter_text,
            preceding_context=memory_prompt_str,
            is_hindi=is_hindi,
            character_roster=character_roster,
            api_key="",
            model=model,
            dramatic_context=dramatic_context_str,
        )
        if not raw_items:
            logger.error("  [!] STRICT HALT: Screenplay LLM returned no segments. Refusing to degrade to flat narrator.")
            raise LLMUnavailableError("Screenplay LLM returned empty segments. Production strictly halted.")
    else:
        # 3. Novel-Scale Beat-Aligned Chunking (~350 words ceiling)
        chunks = BeatPlanner.slice_chapter_by_beats(
            chapter_text=chapter_text,
            dramatic_plan=dramatic_plan,
            max_words=max_chunk_words,
        )

        raw_items = []
        rolling_context = memory_prompt_str

        for c_idx, chunk_info in enumerate(chunks, 1):
            c_text = chunk_info["text"]
            sc = dramatic_plan.get_scene(chunk_info["scene_id"])
            c_dramatic_lines = []
            if sc:
                c_dramatic_lines.append(f"Dramatic Scene: {sc.scene_id} ({sc.scene_type}) - Setting: {sc.location}")
                c_dramatic_lines.append(f"Scene Purpose: {sc.dramatic_purpose} | Stakes: {sc.stakes}")
                c_dramatic_lines.append(f"Primary Conflict: {sc.primary_conflict}")
                if sc.listener_knowledge_state:
                    c_dramatic_lines.append(f"Audience Knowledge: {sc.listener_knowledge_state}")
            if chunk_info.get("beat_ids"):
                c_dramatic_lines.append("Active Dramatic Beats in this section:")
                for bid in chunk_info["beat_ids"]:
                    b = dramatic_plan.get_beat(bid)
                    if b:
                        obj_s = f", Objective: '{b.objective.immediate_goal}'" if b.objective else ""
                        act_s = f", Actioning: '{b.objective.actioning}'" if b.objective else ""
                        c_dramatic_lines.append(f"  * [{b.beat_id}] Function: {b.dramatic_function}{act_s}{obj_s}, Tension: {b.tension_before}->{b.tension_after}")
            chunk_dramatic_ctx = "\n".join(c_dramatic_lines)

            chunk_items = _get_chunk_parser()(
                chunk_text=c_text,
                preceding_context=rolling_context,
                is_hindi=is_hindi,
                character_roster=character_roster,
                api_key="",
                model=model,
                dramatic_context=chunk_dramatic_ctx,
            )
            if chunk_items:
                raw_items.extend(chunk_items)
                tail_lines = []
                for it in chunk_items[-3:]:
                    sp = it.get("speaker", "Narrator")
                    typ = it.get("type", "dialogue")
                    txt = (it.get("text", "") or "").strip()
                    if len(txt) > 85:
                        txt = txt[:82] + "..."
                    tail_lines.append(f"  - [{typ.upper()}] {sp}: \"{txt}\"")
                rolling_context = (
                    (f"{memory_prompt_str}\n\n" if memory_prompt_str else "")
                    + f"Preceding Scene Context (Last exchanges of chunk {c_idx}):\n"
                    + "\n".join(tail_lines)
                    + "\nATTRIBUTION INSTRUCTION: Use this conversational memory to attribute opening dialogue tags "
                    f"and pronouns (e.g. 'उसने', 'वह', 'he', 'she') to the correct character."
                )
            else:
                logger.error(f"  [!] STRICT HALT: Chunk {c_idx} parsing returned empty segments. Halting to preserve dramatization.")
                raise LLMUnavailableError(f"Screenplay LLM returned empty segments for chunk {c_idx}. Production strictly halted.")

    if not raw_items:
        logger.error("  [!] STRICT HALT: Screenplay LLM returned no segments. Refusing to degrade to flat narrator.")
        raise LLMUnavailableError("Screenplay LLM returned empty segments. Production strictly halted.")

    cleaned = clean_screenplay_pass2(
        raw_items,
        is_hindi=is_hindi,
        character_roster=character_roster,
        memory_context=memory_context,
        dramatic_plan=dramatic_plan,
    )
    val_res = DramaticValidator.validate_screenplay_and_plan(
        segments=cleaned,
        dramatic_plan=dramatic_plan,
        source_text=chapter_text,
        known_characters=known_chars,
        memory_context=memory_context,
    )
    if return_dramatic_plan:
        return cleaned, dramatic_plan, val_res
    return cleaned
