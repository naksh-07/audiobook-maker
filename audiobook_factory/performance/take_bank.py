#!/usr/bin/env python3
"""
Audiobook Factory - Take Bank & Multi-Take Management (Pillar 3.4).
Allocates and manages intentional candidate performance takes based on performance_priority:
Standard (1 take), Focused (2 takes), High (2-3 takes), Climactic (3-4 takes).
"""

from __future__ import annotations
import json
import wave
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

from audiobook_factory.logger import logger
from .contracts import PerformanceDirection, TakeVariant, PerformancePriority


class TakeBank:
    """
    Manages candidate performance takes for a chapter's segments.
    """

    PRIORITY_VARIANTS: Dict[PerformancePriority, List[str]] = {
        "standard": ["standard"],
        "focused": ["standard", "restraint"],
        "high": ["standard", "restraint", "vulnerable"],
        "climactic": ["standard", "restraint", "vulnerable", "exposed"],
    }

    def __init__(self, takes_dir: Path | str):
        self.takes_dir = Path(takes_dir).resolve()
        self.takes_dir.mkdir(parents=True, exist_ok=True)
        self.takes: Dict[str, List[TakeVariant]] = {}

    def get_candidate_variants(
        self,
        direction: PerformanceDirection,
        strategy_plan: Optional[Any] = None,
        text: str = "",
    ) -> List[str]:
        """Returns the list of intended variant types for a given PerformanceDirection."""
        if strategy_plan and hasattr(strategy_plan, "target_variants") and strategy_plan.target_variants:
            return list(strategy_plan.target_variants)

        if text:
            try:
                from .strategy_resolver import GenerationStrategyResolver
                plan = GenerationStrategyResolver.resolve_strategy(direction, text=text)
                if plan and plan.target_variants:
                    return list(plan.target_variants)
            except Exception:
                pass

        prio = direction.performance_priority
        if prio and prio != "standard" and prio in self.PRIORITY_VARIANTS:
            return list(self.PRIORITY_VARIANTS[prio])

        return ["standard"]

    def create_take(
        self,
        segment_uid: str,
        segment_index: int,
        variant_type: str,
        audio_file: Path | str,
        direction: PerformanceDirection,
        duration_sec: float = 0.0,
    ) -> TakeVariant:
        """
        Registers a generated audio file as a TakeVariant in the TakeBank.
        """
        p = Path(audio_file).resolve()
        if duration_sec <= 0.0 and p.exists() and p.stat().st_size > 44:
            try:
                with wave.open(str(p), "rb") as wf:
                    duration_sec = wf.getnframes() / float(wf.getframerate())
            except Exception:
                duration_sec = 1.0

        take_id = f"take_s{segment_index:04d}_{variant_type}_{p.stem[-6:]}"
        variant = TakeVariant(
            take_id=take_id,
            segment_uid=segment_uid,
            segment_index=segment_index,
            variant_type=variant_type,  # type: ignore
            audio_path=str(p),
            duration_sec=round(duration_sec, 3),
            direction=direction,
            is_selected=False,
            selection_reason="",
        )

        if segment_uid not in self.takes:
            self.takes[segment_uid] = []
        self.takes[segment_uid].append(variant)

        return variant

    def get_takes_for_segment(self, segment_uid: str) -> List[TakeVariant]:
        """Retrieves all registered candidate takes for a given segment UID."""
        return self.takes.get(segment_uid, [])

    def save_manifest(self, filepath: Path | str) -> None:
        """Saves take bank registry as JSON."""
        target = Path(filepath).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        dump_data = {
            uid: [t.model_dump() for t in var_list]
            for uid, var_list in self.takes.items()
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(dump_data, f, ensure_ascii=False, indent=2)
