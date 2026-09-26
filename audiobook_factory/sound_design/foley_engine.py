#!/usr/bin/env python3
"""
Audiobook Factory - Capability 07: Foley Intelligence & Relevance Scoring Engine.
================================================================================
Evaluates physical actions described in text, screenplay segments, and blocking,
scoring candidates against dramatic relevance and actively rejecting low-value verbs.
Prevents acoustic clutter while ensuring crucial physical props and movements are heard.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Set, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    ActionCandidate,
    FoleyScoredCandidate,
    CharacterPhysicalProfile,
    RelativeIntensity,
    MixIntent,
)
from audiobook_factory.contracts import FoleyCue


# Low-value trivial physical motions that rarely warrant dedicated foley sound design
LOW_VALUE_TRIVIAL_VERBS: Set[str] = {
    "blink", "blinks", "blinked", "blinking",
    "swallow", "swallows", "swallowed", "swallowing",
    "nod", "nods", "nodded", "nodding",
    "shrug", "shrugs", "shrugged", "shrugging",
    "breathe", "breathes", "breathed", "breathing",
    "sigh", "sighs", "sighed", "sighing",
    "fidget", "fidgets", "fidgeted", "fidgeting",
    "shift", "shifts", "shifted", "shifting",
    "look", "looks", "looked", "looking",
    "glance", "glances", "glanced", "glancing",
    "turn", "turns", "turned", "turning",
    "peer", "peers", "peered", "peering",
    "stare", "stares", "stared", "staring",
    "wince", "winces", "winced", "wincing",
    "frown", "frowns", "frowned", "frowning",
    "smile", "smiles", "smiled", "smiling",
}

# High-value narrative actions that consistently warrant sound
HIGH_VALUE_NARRATIVE_VERBS: Set[str] = {
    "draw", "draws", "drew", "drawn", "drawing",
    "sheathe", "sheathes", "sheathed", "sheathing",
    "unsheathe", "unsheathes", "unsheathed",
    "pour", "pours", "poured", "pouring",
    "strike", "strikes", "struck", "striking",
    "clash", "clashes", "clashed", "clashing",
    "slam", "slams", "slammed", "slamming",
    "creak", "creaks", "creaked", "creaking",
    "shatter", "shatters", "shattered", "shattering",
    "step", "steps", "stepped", "stepping",
    "stride", "strides", "strode", "striding",
    "kick", "kicks", "kicked", "kicking",
    "unlock", "unlocks", "unlocked", "unlocking",
    "drop", "drops", "dropped", "dropping",
    "grasp", "grasps", "grasped", "grasping",
    "snatch", "snatches", "snatched", "snatching",
    "clang", "clangs", "clanged", "clanging",
    "rattle", "rattles", "rattled", "rattling",
}


class FoleyEngine:
    """
    Intelligent Foley relevance evaluator and scoring engine.
    """

    RESTRAINT_THRESHOLDS: Dict[str, float] = {
        "high": 0.55,      # High restraint: only essential physical acts sound
        "moderate": 0.40,  # Standard cinematic density
        "dense": 0.28,     # Action/battle scene: higher foley density allowed
    }

    def evaluate_candidate(
        self,
        action: ActionCandidate,
        tension_level: float = 0.5,
        restraint_target: str = "moderate",
        beat_id: Optional[str] = None,
    ) -> FoleyScoredCandidate:
        """
        Evaluates a single ActionCandidate with narrative relevance scoring
        and explicit low-value verb pruning.
        """
        verb_norm = action.action_verb.lower().strip()
        threshold = self.RESTRAINT_THRESHOLDS.get(restraint_target, 0.40)

        # 1. Check for trivial physical motion
        is_trivial = verb_norm in LOW_VALUE_TRIVIAL_VERBS
        is_high_value = verb_norm in HIGH_VALUE_NARRATIVE_VERBS

        # Base scoring components
        if is_trivial:
            narrative_imp = 0.15
            physical_vis = 0.20
            timing_nec = 0.10
        elif is_high_value:
            narrative_imp = 0.85
            physical_vis = 0.80
            timing_nec = 0.75
        else:
            narrative_imp = 0.50
            physical_vis = 0.50
            timing_nec = 0.50

        # Adjust based on subject (named character vs generic)
        char_relevance = 0.75 if action.subject and action.subject.lower() != "character" else 0.45

        # Dramatic tension amplifies physical visibility
        adj_tension = max(0.0, min(1.0, tension_level))

        candidate = FoleyScoredCandidate(
            candidate_id=f"foley_{action.segment_index}_{verb_norm}",
            segment_index=action.segment_index,
            subject=action.subject,
            action_verb=action.action_verb,
            object_material=action.object_material,
            surface_material=action.surface_material,
            anchor_word=action.anchor_word or action.action_verb,
            narrative_importance=narrative_imp,
            dramatic_tension=adj_tension,
            physical_visibility=physical_vis,
            character_relevance=char_relevance,
            timing_necessity=timing_nec,
            provenance_beat_id=beat_id,
        )

        score = candidate.calculate_score()

        # Decision rule
        if is_trivial and score < 0.40:
            candidate.status = "REJECTED_TRIVIAL"
            candidate.rejection_reason = (
                f"Trivial physical motion '{verb_norm}' rejected (restraint score: {score:.2f} < 0.40)"
            )
        elif score < threshold:
            candidate.status = "REJECTED_RESTRAINT"
            candidate.rejection_reason = (
                f"Score {score:.2f} below {restraint_target} restraint threshold {threshold:.2f}"
            )
        else:
            candidate.status = "ACCEPTED"
            candidate.rejection_reason = None

        return candidate

    def process_scene_actions(
        self,
        candidates: List[ActionCandidate],
        tension_level: float = 0.5,
        restraint_target: str = "moderate",
        beat_id: Optional[str] = None,
    ) -> List[FoleyScoredCandidate]:
        """
        Processes a list of ActionCandidate items for a scene, returning
        scored candidates with acceptance/rejection decisions.
        """
        results: List[FoleyScoredCandidate] = []
        for cand in candidates:
            scored = self.evaluate_candidate(
                action=cand,
                tension_level=tension_level,
                restraint_target=restraint_target,
                beat_id=beat_id,
            )
            results.append(scored)
        return results

    def to_legacy_foley_cues(
        self,
        accepted_candidates: List[FoleyScoredCandidate],
        character_profiles: Optional[Dict[str, CharacterPhysicalProfile]] = None,
        asset_map: Optional[Dict[str, str]] = None,
    ) -> List[FoleyCue]:
        """
        Converts accepted FoleyScoredCandidate items into standard FoleyCue objects
        for 100% backward compatibility with downstream audio drama manifests.
        """
        cues: List[FoleyCue] = []
        profiles = character_profiles or {}
        assets = asset_map or {}

        for idx, item in enumerate(accepted_candidates):
            if item.status != "ACCEPTED":
                continue

            verb = item.action_verb.lower().strip()
            obj_mat = item.object_material.lower().strip()
            surf_mat = (item.surface_material or "stone").lower().strip()

            # Assign UCS category based on verb/material
            ucs = "FOLEOth"
            if verb in ("step", "steps", "stepped", "stride", "strides", "strode"):
                ucs = "FOLEFts"
            elif "sword" in obj_mat or "blade" in obj_mat or "steel" in obj_mat:
                ucs = "WEAPSwd"
            elif "door" in verb or "door" in obj_mat:
                ucs = "DOORDor"
            elif "plate" in obj_mat or "cup" in obj_mat or "goblet" in obj_mat:
                ucs = "DOMETabl"

            # Derive pan coordinate
            pan = 0.0
            profile = profiles.get(item.subject)
            if profile and profile.physical_condition == "stealthy_stalking":
                pan = -0.3

            asset_path = assets.get(item.candidate_id, f"foley_{ucs.lower()}_{verb}_{obj_mat}.wav")

            cue = FoleyCue(
                cue_id=f"fc_{item.segment_index}_{idx+1}",
                segment_index=item.segment_index,
                anchor_word=item.anchor_word or verb,
                pre_roll_ms=80,
                asset_id=100 + idx,
                asset_path=asset_path,
                asset_name=f"{item.subject} {verb} {obj_mat}",
                gain_dbfs=-16.0,
                azimuth_pan=pan,
                ucs_category=ucs,
            )
            cues.append(cue)

        return cues


_GLOBAL_FOLEY_ENGINE: Optional[FoleyEngine] = None

def get_foley_engine() -> FoleyEngine:
    """Returns singleton instance of FoleyEngine."""
    global _GLOBAL_FOLEY_ENGINE
    if _GLOBAL_FOLEY_ENGINE is None:
        _GLOBAL_FOLEY_ENGINE = FoleyEngine()
    return _GLOBAL_FOLEY_ENGINE
