#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.5: Pre-TTS Smart Batch Dispatch Planner.
Analyzes screenplay segments to form quota-efficient synthesis batches:
- 2-Speaker Dialogue Rallies -> Multi-Speaker Batches (multiSpeakerVoiceConfig)
- Multi-Paragraph Narrator Runs -> Narrator Super-Chunks
- Intimate Scenes (ASMR / Close-Mic) -> Isolated Single Requests
- Action / Combat Beats (Foley SFX / Stereo Panning) -> Isolated Single Requests
- Full Lifecycle Traceability via Segment UIDs & JSON Manifests.
"""

from __future__ import annotations
import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from audiobook_factory.contracts import (
    ScreenplaySegment,
    BatchPlanItem,
    BatchDispatchManifest,
)
from audiobook_factory.logger import logger


DEFAULT_MAX_BATCH_WORDS = int(os.environ.get("TTS_BATCH_MAX_WORDS", "600"))
DEFAULT_BATCHING_ENABLED = os.environ.get("TTS_BATCHING_ENABLED", "true").lower() in ("true", "1", "yes")


def _clean_token(s: str) -> str:
    """Sanitizes character name or identifier into a safe alphanumeric string without spaces or symbols."""
    clean = re.sub(r"[^a-zA-Z0-9_]+", "_", str(s).strip().lower()).strip("_")
    return clean or "speaker"


class BatchDispatchPlanner:
    """
    Intelligent pre-TTS dispatch planner that groups screenplay segments into
    optimal, rate-limited synthesis batches while preserving acoustic drama integrity.
    """

    def __init__(self, max_words_per_batch: int = DEFAULT_MAX_BATCH_WORDS, enabled: bool = DEFAULT_BATCHING_ENABLED):
        self.max_words_per_batch = max_words_per_batch
        self.enabled = enabled

    @staticmethod
    def is_intimate_segment(seg: ScreenplaySegment) -> bool:
        """Determines if a segment requires isolated close-mic ASMR intimacy treatment."""
        if seg.spatial and seg.spatial.proximity in ("intimate_close", "close_mic"):
            return True
        if seg.pre_roll_breath_ms and seg.pre_roll_breath_ms > 0:
            return True
        if seg.emotion and seg.emotion.lower() in ("intimate", "erotic", "passionate", "sensual"):
            return True
        if seg.acting and seg.acting.delivery_style in (
            "whispered_threat", "breathless_exhaustion", "intimate_breathy", "breathy"
        ):
            return True
        txt_lower = seg.text.lower() if seg.text else ""
        if "[whispers]" in txt_lower or "[intimate" in txt_lower or "[tender" in txt_lower:
            return True
        return False

    @staticmethod
    def is_combat_or_spatial_segment(seg: ScreenplaySegment) -> bool:
        """Determines if a segment requires isolated frame-accurate Foley or action treatment."""
        if seg.type == "action":
            return True
        if seg.sfx_cues and len(seg.sfx_cues) > 0:
            return True
        if seg.spatial and getattr(seg.spatial, "movement", None) in ("flyby", "pan_sweep", "moving"):
            return True
        if seg.intensity_level in ("high", "explosive"):
            return True
        if seg.acting and seg.acting.delivery_style in (
            "slow_motion", "combat_strain", "bellowing_rage", "bellowing_battlecry", "diaphragm_strain"
        ):
            return True
        txt_lower = seg.text.lower() if seg.text else ""
        if any(tag in txt_lower for tag in ("[shouting]", "[bellowing", "[combat", "[spits blood", "[guttural grunt")):
            return True
        return False

    def classify_segment(self, seg: ScreenplaySegment) -> str:
        """Classifies segment into 'isolated_intimate', 'isolated_combat', 'dialogue', or 'narration'."""
        if self.is_intimate_segment(seg):
            return "isolated_intimate"
        if self.is_combat_or_spatial_segment(seg):
            return "isolated_combat"
        if seg.type == "dialogue" and seg.speaker.lower() not in ("narrator", "header", "chapter_header"):
            return "dialogue"
        return "narration"

    def plan_chapter_batches(
        self,
        segments: List[ScreenplaySegment],
        chapter_id: str = "chapter_001",
        chapter_num: int = 1,
        voice_map: Optional[Dict[str, str]] = None,
    ) -> BatchDispatchManifest:
        """
        Partitions screenplay segments into an auditable sequence of BatchPlanItems.
        If batching is disabled via configuration, returns 1-to-1 single isolated batches.
        """
        if not segments:
            return BatchDispatchManifest(
                chapter_id=chapter_id,
                chapter_num=chapter_num,
                total_segments=0,
                total_batches=0,
                quota_savings_ratio=0.0,
                batches=[],
            )

        v_map = voice_map or {}
        batches: List[BatchPlanItem] = []
        batch_counter = 1

        if not self.enabled:
            # Fallback: each segment forms its own isolated batch
            for seg in segments:
                b_item = BatchPlanItem(
                    batch_id=f"b{batch_counter:04d}_single_{seg.speaker.lower()}_{seg.index:04d}",
                    strategy="single_isolated",
                    uids=[seg.uid],
                    speakers=[seg.speaker],
                    voice_map={seg.speaker: v_map.get(seg.speaker, "Aoede")},
                    segments=[seg],
                    total_words=len(seg.text.split()),
                )
                batches.append(b_item)
                batch_counter += 1

            return BatchDispatchManifest(
                chapter_id=chapter_id,
                chapter_num=chapter_num,
                total_segments=len(segments),
                total_batches=len(batches),
                quota_savings_ratio=0.0,
                batches=batches,
            )

        # Sliding Window Batching Algorithm
        i = 0
        n = len(segments)

        while i < n:
            current_seg = segments[i]
            classification = self.classify_segment(current_seg)

            # Case 1: Isolated Segments (Intimate ASMR or Combat / Action / Panned)
            if classification in ("isolated_intimate", "isolated_combat"):
                spk_tok = _clean_token(current_seg.speaker)
                batches.append(
                    BatchPlanItem(
                        batch_id=f"b{batch_counter:04d}_iso_{spk_tok}_{current_seg.index:04d}",
                        strategy="single_isolated",
                        uids=[current_seg.uid],
                        speakers=[current_seg.speaker],
                        voice_map={current_seg.speaker: v_map.get(current_seg.speaker, "Aoede")},
                        segments=[current_seg],
                        total_words=len(current_seg.text.split()),
                    )
                )
                batch_counter += 1
                i += 1
                continue

            # Case 2: Narrator Super-Chunking
            if classification == "narration":
                narrator_batch_segs = [current_seg]
                current_words = len(current_seg.text.split())
                j = i + 1
                while j < n:
                    next_seg = segments[j]
                    if self.classify_segment(next_seg) == "narration" and next_seg.speaker.lower() == current_seg.speaker.lower():
                        next_words = len(next_seg.text.split())
                        if current_words + next_words <= self.max_words_per_batch:
                            narrator_batch_segs.append(next_seg)
                            current_words += next_words
                            j += 1
                            continue
                    break

                batches.append(
                    BatchPlanItem(
                        batch_id=f"b{batch_counter:04d}_narrator_s{narrator_batch_segs[0].index:04d}_to_s{narrator_batch_segs[-1].index:04d}",
                        strategy="narrator_chunk" if len(narrator_batch_segs) > 1 else "single_isolated",
                        uids=[s.uid for s in narrator_batch_segs],
                        speakers=[current_seg.speaker],
                        voice_map={current_seg.speaker: v_map.get(current_seg.speaker, "Aoede")},
                        segments=narrator_batch_segs,
                        total_words=current_words,
                    )
                )
                batch_counter += 1
                i = j
                continue

            # Case 3: Dialogue Exchanges
            if classification == "dialogue":
                # Lookahead to collect contiguous dialogue segments
                dialogue_segs = [current_seg]
                active_speakers = {current_seg.speaker}
                current_words = len(current_seg.text.split())
                j = i + 1

                while j < n:
                    next_seg = segments[j]
                    next_class = self.classify_segment(next_seg)

                    if next_class != "dialogue":
                        # Non-dialogue interrupts the conversation
                        break

                    candidate_speakers = active_speakers | {next_seg.speaker}
                    if len(candidate_speakers) > 2:
                        # 3rd character speaking! Break batch to preserve exact 2-speaker API constraint
                        break

                    next_words = len(next_seg.text.split())
                    if current_words + next_words > self.max_words_per_batch:
                        # Exceeds word budget (avoiding voice drift)
                        break

                    dialogue_segs.append(next_seg)
                    active_speakers = candidate_speakers
                    current_words += next_words
                    j += 1

                # If we collected multiple dialogue lines with exactly 2 speakers -> multi_speaker_duo
                if len(dialogue_segs) > 1 and len(active_speakers) == 2:
                    spk_list = sorted(list(active_speakers))
                    s1 = _clean_token(spk_list[0])
                    s2 = _clean_token(spk_list[1])
                    b_id = f"b{batch_counter:04d}_duo_{s1}_{s2}_s{dialogue_segs[0].index:04d}"
                    batches.append(
                        BatchPlanItem(
                            batch_id=b_id,
                            strategy="multi_speaker_duo",
                            uids=[s.uid for s in dialogue_segs],
                            speakers=spk_list,
                            voice_map={spk: v_map.get(spk, "Aoede") for spk in spk_list},
                            segments=dialogue_segs,
                            total_words=current_words,
                        )
                    )
                    batch_counter += 1
                else:
                    # Single dialogue line or monologue without a 2nd speaker -> single isolated
                    for d_seg in dialogue_segs:
                        spk_tok = _clean_token(d_seg.speaker)
                        batches.append(
                            BatchPlanItem(
                                batch_id=f"b{batch_counter:04d}_single_{spk_tok}_{d_seg.index:04d}",
                                strategy="single_isolated",
                                uids=[d_seg.uid],
                                speakers=[d_seg.speaker],
                                voice_map={d_seg.speaker: v_map.get(d_seg.speaker, "Aoede")},
                                segments=[d_seg],
                                total_words=len(d_seg.text.split()),
                            )
                        )
                        batch_counter += 1

                i = j
                continue

            # Fallback catch-all
            spk_tok = _clean_token(current_seg.speaker)
            batches.append(
                BatchPlanItem(
                    batch_id=f"b{batch_counter:04d}_single_{spk_tok}_{current_seg.index:04d}",
                    strategy="single_isolated",
                    uids=[current_seg.uid],
                    speakers=[current_seg.speaker],
                    voice_map={current_seg.speaker: v_map.get(current_seg.speaker, "Aoede")},
                    segments=[current_seg],
                    total_words=len(current_seg.text.split()),
                )
            )
            batch_counter += 1
            i += 1

        total_input = len(segments)
        total_b = len(batches)
        savings = round((1.0 - (total_b / float(total_input))) * 100.0, 1) if total_input > 0 else 0.0

        manifest = BatchDispatchManifest(
            chapter_id=chapter_id,
            chapter_num=chapter_num,
            total_segments=total_input,
            total_batches=total_b,
            quota_savings_ratio=max(0.0, savings),
            batches=batches,
        )

        logger.info(
            f"[*] BatchDispatchPlanner: Partitioned {total_input} segments into {total_b} batches "
            f"(Quota Savings: {savings:.1f}% reduction in TTS calls)"
        )
        return manifest
