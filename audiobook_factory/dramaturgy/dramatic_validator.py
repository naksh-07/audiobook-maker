#!/usr/bin/env python3
"""
Audiobook Factory - Dramaturgy: Dramatic Validator & Fidelity Guards.
Enforces fail-closed structural validation, anti-emotional teleportation checks,
epistemic isolation bounds, Dramatic Fidelity Guard, and Creative Overreach Guard.
"""

from __future__ import annotations
import re
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from .contracts import (
    DramaticPlan,
    DramaticBeat,
    SceneDramaticPlan,
    DramaticValidationResult,
    DramaticValidationIssue,
)


class DramaticValidator:
    """
    Audits screenplay segments and dramatic plans to prevent emotional teleportation,
    creative overreach, hallucinated dialogue, and broken dramatic arcs.
    """

    VOLATILE_EMOTION_TRANSITIONS = {
        ("calm", "bellowing_rage"),
        ("peaceful", "explosive"),
        ("gentle_tender", "bellowing_battlecry"),
        ("whispering", "bellowing_rage"),
    }

    @classmethod
    def validate_screenplay_and_plan(
        cls,
        segments: List[Dict[str, Any]],
        dramatic_plan: Optional[DramaticPlan] = None,
        source_text: str = "",
        known_characters: Optional[List[str]] = None,
        memory_context: Optional[Any] = None,
    ) -> DramaticValidationResult:
        """
        Executes a 5-pillar dramatic audit across screenplay segments and plan.
        """
        issues: List[DramaticValidationIssue] = []

        if not segments:
            issues.append(
                DramaticValidationIssue(
                    code="EMPTY_SCREENPLAY",
                    severity="ERROR",
                    message="Screenplay contains zero segments.",
                )
            )
            return DramaticValidationResult(
                status="FAIL",
                passed=False,
                total_issues=1,
                issues=issues,
                summary="Screenplay validation failed: empty segment list.",
                checked_at=datetime.datetime.now().isoformat(),
            )

        # ---------------------------------------------------------------------
        # Pillar 1: Structural & Index Consistency
        # ---------------------------------------------------------------------
        cls._audit_structural_integrity(segments, dramatic_plan, issues)

        # ---------------------------------------------------------------------
        # Pillar 2: Character Objectives & Epistemic Sanity
        # ---------------------------------------------------------------------
        cls._audit_character_epistemics(segments, known_characters, memory_context, issues)

        # ---------------------------------------------------------------------
        # Pillar 3: Dramatic Arc Continuity & Anti-Emotional Teleportation
        # ---------------------------------------------------------------------
        cls._audit_arc_continuity(segments, issues)

        # ---------------------------------------------------------------------
        # Pillar 4: Dramatic Fidelity Guard (Source Meaning Preserved)
        # ---------------------------------------------------------------------
        if source_text:
            cls._audit_dramatic_fidelity(segments, source_text, issues)

        # ---------------------------------------------------------------------
        # Pillar 5: Creative Overreach Guard (No Invented Actions/Lore)
        # ---------------------------------------------------------------------
        if source_text:
            cls._audit_creative_overreach(segments, source_text, issues)

        # ---------------------------------------------------------------------
        # Pillar 6: Beat Causality & Continuous Chain Guard
        # ---------------------------------------------------------------------
        if dramatic_plan:
            cls._audit_beat_causality(dramatic_plan, issues)

        # ---------------------------------------------------------------------
        # Pillar 7: Dramatic State Delta Audit
        # ---------------------------------------------------------------------
        if dramatic_plan:
            cls._audit_state_delta(dramatic_plan, issues)

        # ---------------------------------------------------------------------
        # Pillar 8: Adaptation & Fidelity Policy (Gate 2.5 Strictness)
        # ---------------------------------------------------------------------
        if dramatic_plan and source_text:
            cls._audit_adaptation_policy(dramatic_plan, segments, source_text, memory_context, issues)

        # Evaluate final status
        has_errors = any(i.severity == "ERROR" for i in issues)
        has_warnings = any(i.severity == "WARNING" for i in issues)

        if has_errors:
            status = "FAIL"
            passed = False
        elif has_warnings:
            status = "WARNING"
            passed = True
        else:
            status = "PASS"
            passed = True

        summary_str = f"Dramatic Audit {status}: {len(issues)} issue(s) detected across {len(segments)} segments."

        return DramaticValidationResult(
            status=status,
            passed=passed,
            total_issues=len(issues),
            issues=issues,
            summary=summary_str,
            checked_at=datetime.datetime.now().isoformat(),
        )

    @classmethod
    def _audit_structural_integrity(
        cls,
        segments: List[Dict[str, Any]],
        dramatic_plan: Optional[DramaticPlan],
        issues: List[DramaticValidationIssue],
    ) -> None:
        """Verify monotonically increasing indexes and valid beat/scene references."""
        expected_idx = 1
        known_scenes = set()
        known_beats = set()
        if dramatic_plan:
            for s in dramatic_plan.scenes:
                known_scenes.add(s.scene_id)
                for b in s.beats:
                    known_beats.add(b.beat_id)

        for seg in segments:
            idx = seg.get("index")
            if idx != expected_idx:
                issues.append(
                    DramaticValidationIssue(
                        code="NON_MONOTONIC_INDEX",
                        severity="ERROR",
                        message=f"Segment index out of order: expected {expected_idx}, got {idx}.",
                        segment_uid=seg.get("uid"),
                    )
                )
            expected_idx += 1

            s_id = seg.get("scene_id")
            if s_id and known_scenes and s_id not in known_scenes:
                issues.append(
                    DramaticValidationIssue(
                        code="ORPHAN_SCENE_REF",
                        severity="ERROR",
                        message=f"Segment references unknown scene_id: '{s_id}'.",
                        scene_id=s_id,
                        segment_uid=seg.get("uid"),
                    )
                )

            b_id = seg.get("beat_id")
            if b_id and known_beats and b_id not in known_beats:
                issues.append(
                    DramaticValidationIssue(
                        code="ORPHAN_BEAT_REF",
                        severity="WARNING",
                        message=f"Segment references unknown beat_id: '{b_id}'.",
                        beat_id=b_id,
                        segment_uid=seg.get("uid"),
                    )
                )

    @classmethod
    def _audit_character_epistemics(
        cls,
        segments: List[Dict[str, Any]],
        known_characters: Optional[List[str]],
        memory_context: Optional[Any],
        issues: List[DramaticValidationIssue],
    ) -> None:
        """Validate character objectives and prevent epistemic leakage."""
        epistemic_unknowns: Dict[str, List[str]] = {}
        if memory_context and hasattr(memory_context, "epistemic_constraints"):
            for char_name, buckets in memory_context.epistemic_constraints.items():
                epistemic_unknowns[char_name.lower()] = [str(f).lower() for f in buckets.get("UNKNOWN", [])]

        for seg in segments:
            spk = str(seg.get("speaker", "")).strip()
            spk_low = spk.lower()
            seg_type = seg.get("type", "narration")

            if seg_type == "dialogue" and spk_low not in ("narrator", "foley"):
                # Dialogue segments should ideally carry actioning or objective in dramatic mode
                if not seg.get("actioning") and not seg.get("character_objective") and seg.get("scene_id"):
                    issues.append(
                        DramaticValidationIssue(
                            code="MISSING_CHARACTER_OBJECTIVE",
                            severity="WARNING",
                            message=f"Dialogue segment for '{spk}' lacks explicit actioning verb or dramatic objective.",
                            segment_uid=seg.get("uid"),
                        )
                    )

                # Check if speaking character leaks unknown facts
                if spk_low in epistemic_unknowns:
                    txt = str(seg.get("text", "")).lower()
                    for unk in epistemic_unknowns[spk_low]:
                        if unk and unk in txt and len(unk) > 4:
                            issues.append(
                                DramaticValidationIssue(
                                    code="EPISTEMIC_ISOLATION_BREACH",
                                    severity="ERROR",
                                    message=f"Character '{spk}' references fact '{unk}' marked UNKNOWN in epistemic memory.",
                                    segment_uid=seg.get("uid"),
                                )
                            )

    @classmethod
    def _audit_arc_continuity(
        cls,
        segments: List[Dict[str, Any]],
        issues: List[DramaticValidationIssue],
    ) -> None:
        """Detect irrational emotional teleportation between consecutive dialogue lines."""
        prev_speaker = None
        prev_emotion = None

        for seg in segments:
            spk = seg.get("speaker", "Narrator")
            emo = str(seg.get("surface_emotion") or seg.get("emotion") or "neutral").strip().lower()

            if spk == prev_speaker and spk not in ("Narrator", "Foley") and prev_emotion:
                pair = (prev_emotion, emo)
                if pair in cls.VOLATILE_EMOTION_TRANSITIONS:
                    issues.append(
                        DramaticValidationIssue(
                            code="EMOTIONAL_TELEPORTATION",
                            severity="WARNING",
                            message=f"Character '{spk}' jumped abruptly from '{prev_emotion}' to '{emo}' without dramatic bridge.",
                            segment_uid=seg.get("uid"),
                        )
                    )

            if spk not in ("Narrator", "Foley"):
                prev_speaker = spk
                prev_emotion = emo

    @classmethod
    def _audit_dramatic_fidelity(
        cls,
        segments: List[Dict[str, Any]],
        source_text: str,
        issues: List[DramaticValidationIssue],
    ) -> None:
        """Verifies dialogue coverage and speaker preservation against source text."""
        # Simple token presence heuristic: check if major source quotes exist in screenplay
        source_quotes = re.findall(r'["“]([^"”]{12,})["”]', source_text)
        if not source_quotes:
            return

        combined_script_text = " ".join(str(s.get("text", "")) for s in segments)
        dropped_count = 0
        for quote in source_quotes[:15]:
            q_clean = re.sub(r"[^\w\s]", "", quote).strip().lower()
            q_words = q_clean.split()
            if len(q_words) >= 4:
                probe = " ".join(q_words[:4])
                if probe not in combined_script_text.lower():
                    dropped_count += 1

        if dropped_count >= 3 and len(source_quotes) >= 4:
            issues.append(
                DramaticValidationIssue(
                    code="DROPPED_SOURCE_DIALOGUE",
                    severity="WARNING",
                    message=f"Potentially dropped or heavily mutated dialogue detected ({dropped_count} source quotes missing).",
                )
            )

    @classmethod
    def _audit_creative_overreach(
        cls,
        segments: List[Dict[str, Any]],
        source_text: str,
        issues: List[DramaticValidationIssue],
    ) -> None:
        """Flags invented actions, unsupported subtext claims, or hallucinated lore."""
        source_low = source_text.lower()

        for seg in segments:
            # Check subtext classification
            sub_class = seg.get("subtext_classification")
            sub_conf = seg.get("subtext_confidence", 0.0)
            if sub_class == "UNSUPPORTED" and sub_conf > 0.6:
                issues.append(
                    DramaticValidationIssue(
                        code="CREATIVE_OVERREACH_SUBTEXT",
                        severity="WARNING",
                        message=f"Subtext marked UNSUPPORTED with high confidence ({sub_conf}): '{seg.get('subtext')}'.",
                        segment_uid=seg.get("uid"),
                    )
                )

            # Check action segments for extreme hallucination
            if seg.get("type") == "action":
                cues = seg.get("sfx_cues", [])
                for cue in cues:
                    c_tag = cue if isinstance(cue, str) else cue.get("tag", "")
                    if c_tag in ("explosion", "gunshot", "laser") and c_tag not in source_low:
                        issues.append(
                            DramaticValidationIssue(
                                code="CREATIVE_OVERREACH_ACTION",
                                severity="WARNING",
                                message=f"Invented action cue '{c_tag}' not supported by source narrative.",
                                segment_uid=seg.get("uid"),
                            )
                        )

    @classmethod
    def _audit_beat_causality(
        cls,
        dramatic_plan: DramaticPlan,
        issues: List[DramaticValidationIssue],
    ) -> None:
        """Verify beat causality chains are continuous without broken causal links."""
        for sc in dramatic_plan.scenes:
            if len(sc.beats) > 1:
                for idx, b in enumerate(sc.beats):
                    if idx > 0 and not b.causal_trigger:
                        issues.append(
                            DramaticValidationIssue(
                                code="BROKEN_BEAT_CAUSALITY",
                                severity="WARNING",
                                message=f"Beat '{b.beat_id}' in scene '{sc.scene_id}' lacks causal trigger from preceding beat.",
                                scene_id=sc.scene_id,
                                beat_id=b.beat_id,
                            )
                        )

    @classmethod
    def _audit_state_delta(
        cls,
        dramatic_plan: DramaticPlan,
        issues: List[DramaticValidationIssue],
    ) -> None:
        """Verify high-stakes or complex scenes produce a meaningful dramatic transformation."""
        for sc in dramatic_plan.scenes:
            if sc.dramatic_complexity in ("HIGH", "CRITICAL"):
                delta = sc.state_delta
                has_meaningful_change = (
                    delta is not None and (
                        bool(delta.knowledge_delta) or
                        bool(delta.relationship_shifts) or
                        bool(delta.decisions_made) or
                        delta.power_shift is not None or
                        delta.danger_level_delta in ("escalated", "reduced")
                    )
                )
                if not has_meaningful_change:
                    issues.append(
                        DramaticValidationIssue(
                            code="STATIC_SCENE_NO_DELTA",
                            severity="WARNING",
                            message=f"High complexity scene '{sc.scene_id}' lacks meaningful transformation in state delta.",
                            scene_id=sc.scene_id,
                        )
                    )

    @classmethod
    def _audit_adaptation_policy(
        cls,
        dramatic_plan: DramaticPlan,
        segments: List[Dict[str, Any]],
        source_text: str,
        memory_context: Optional[Any],
        issues: List[DramaticValidationIssue],
    ) -> None:
        """Enforce AdaptationFidelityPolicy: fail-closed on fabricated lore and POV violations."""
        policy = getattr(dramatic_plan, "adaptation_policy", None)
        if not policy:
            return

        s_low = source_text.lower()

        # 1. Disallow fabricated reveals (Tier 1: ERROR if ungrounded)
        if policy.disallow_fabricated_reveals:
            for sc in dramatic_plan.scenes:
                for rev in sc.major_reveals:
                    clean_rev = re.sub(r"^(?:Disclosed:\s*'|Reversal:\s*')", "", rev).rstrip("'")
                    core_words = [w for w in re.findall(r"\b[a-zA-Z]{5,}\b", clean_rev.lower()) if w not in ("detected", "narrative", "flow", "marks", "shift", "fortune", "truth")]
                    if core_words:
                        grounded = any(w in s_low for w in core_words)
                        if not grounded and memory_context and hasattr(memory_context, "world_facts"):
                            for f in getattr(memory_context, "world_facts", []):
                                if any(w in str(f).lower() for w in core_words):
                                    grounded = True
                                    break
                        if not grounded:
                            issues.append(
                                DramaticValidationIssue(
                                    code="FABRICATED_REVEAL_BREACH",
                                    severity="ERROR",
                                    message=f"Major reveal '{rev}' in scene '{sc.scene_id}' is not substantiated by source text or memory.",
                                    scene_id=sc.scene_id,
                                )
                            )

        # 2. Preserve narrative POV
        if policy.preserve_narrative_pov:
            for sc in dramatic_plan.scenes:
                if sc.narrative_pov.startswith("third_person"):
                    for seg in segments:
                        if seg.get("scene_id") == sc.scene_id and seg.get("type") == "narration":
                            txt = seg.get("text", "")
                            if re.search(r"\b(?:I thought|I felt|I realized|I saw|मैंने सोचा|मैंने देखा)\b", txt, re.IGNORECASE):
                                issues.append(
                                    DramaticValidationIssue(
                                        code="NARRATIVE_POV_VIOLATION",
                                        severity="WARNING",
                                        message=f"Narration segment '{seg.get('uid')}' adopts first-person narrator voice in third-person scene '{sc.scene_id}'.",
                                        segment_uid=seg.get("uid"),
                                        scene_id=sc.scene_id,
                                    )
                                )
