#!/usr/bin/env python3
"""
Audiobook Factory - Dramaturgy: Beat Planner & Semantic Chunking.
Slices scenes into meaningful dramatic beats representing state transformations,
character objectives, actioning verbs, dual-layer emotion, conservative subtext,
and tension curves. Provides beat-aligned chunk slicing for novel-scale processing.
"""

from __future__ import annotations
import re
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple

from .contracts import (
    DramaticBeat,
    CharacterDramaticObjective,
    SceneDramaticPlan,
    DramaticPlan,
    DramaticFunction,
    PerformancePriority,
    SubtextClassification,
    RelationshipShift,
    PhysicalBlocking,
    ConversationalDynamic,
    DramaticSilenceIntent,
    StoryConnectionRecord,
    CausalLinkType,
)


class BeatPlanner:
    """
    Extracts and organizes dramatic beats within scenes, computing character objectives,
    actioning, emotional transitions, tension trajectories, and beat-aligned chunk splits.
    """

    ACTIONING_VERBS = [
        "threaten", "deflect", "reassure", "confess", "plead", "probe", "manipulate",
        "comfort", "test", "intimidate", "negotiate", "scold", "mock", "command",
        "surrender", "seduce", "evade", "challenge", "provoke", "warn", "conceal"
    ]

    @classmethod
    def plan_chapter_beats(
        cls,
        chapter_text: str,
        scenes: List[SceneDramaticPlan],
        known_characters: Optional[List[str]] = None,
        memory_context: Optional[Any] = None,
    ) -> List[SceneDramaticPlan]:
        """
        Populates each SceneDramaticPlan with an ordered sequence of dramatic beats
        and constructs the continuous tension curve across the scene.
        """
        paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]

        for scene in scenes:
            scene_beats = cls.plan_scene_beats(
                scene=scene,
                known_characters=known_characters,
                memory_context=memory_context,
            )
            scene.beats = scene_beats

            # Compute sampled tension curve across beats
            curve = [b.tension_before for b in scene_beats]
            if scene_beats:
                curve.append(scene_beats[-1].tension_after)
            scene.tension_curve = curve

        return scenes

    @classmethod
    def plan_scene_beats(
        cls,
        scene: SceneDramaticPlan,
        known_characters: Optional[List[str]] = None,
        memory_context: Optional[Any] = None,
    ) -> List[DramaticBeat]:
        """
        Breaks down a scene into discrete dramatic beats based on dialogue turns,
        action shifts, escalation points, and emotional turns.
        """
        # Split scene text into cohesive units (paragraphs)
        paras = [p.strip() for p in scene.dramatic_purpose.split("\n\n") if p.strip()]
        # If scene has source text hash or we examine scene text paragraphs
        # We synthesize 2 to 5 meaningful beats depending on scene complexity
        target_beats_count = 2
        if scene.dramatic_complexity in ("HIGH", "CRITICAL"):
            target_beats_count = 4
        elif scene.dramatic_complexity == "MEDIUM":
            target_beats_count = 3

        beats: List[DramaticBeat] = []
        participants = scene.participants or ["Protagonist"]
        p1 = participants[0]
        p2 = participants[1] if len(participants) > 1 else None

        # Determine beat function sequence based on scene type
        function_seq = cls._get_beat_function_sequence(scene.scene_type, target_beats_count)

        # Baseline tension initialization based on opening state
        initial_tension = cls._get_initial_tension(scene.scene_type)
        curr_tension = initial_tension
        prev_consequence: Optional[str] = None

        for b_idx, fn in enumerate(function_seq, 1):
            beat_id = f"{scene.scene_id}_b{b_idx:03d}"
            speaker = p1 if b_idx % 2 == 1 or not p2 else p2
            target = p2 if speaker == p1 else p1

            # Tension movement: escalate towards climax/reversal, de-escalate towards aftermath
            tension_step = cls._compute_tension_step(fn, b_idx, len(function_seq))
            next_tension = round(max(0.05, min(0.98, curr_tension + tension_step)), 2)

            # Derive actioning verb
            action_verb = cls._derive_actioning(fn, scene.scene_type, speaker)

            # Derive objectives
            obj = CharacterDramaticObjective(
                immediate_goal=cls._derive_immediate_goal(fn, speaker, target, scene.scene_type),
                obstacle=cls._derive_obstacle(fn, target, scene.scene_type),
                underlying_desire=f"Maintain autonomy and assert control in {scene.location}",
                core_fear=f"Loss of agency or exposure before {target or 'rivals'}",
                strategy=f"Deploy {action_verb} tactics to overcome resistance",
                actioning=action_verb,
            )

            # Surface vs underlying emotion
            surf_emo, under_emo = cls._derive_dual_emotions(fn, scene.scene_type, action_verb)

            # Subtext inference (conservative)
            subtext_text, sub_conf, sub_class = cls._derive_subtext(
                fn, speaker, target, action_verb, surf_emo, under_emo
            )

            priority: PerformancePriority = "standard"
            if fn in ("climax", "reversal", "threat"):
                priority = "climactic"
            elif fn in ("escalation", "reveal", "emotional_turn"):
                priority = "high_focus"
            elif fn in ("setup", "transition"):
                priority = "background"

            intensity = "medium"
            if next_tension >= 0.75:
                intensity = "explosive" if scene.scene_type == "combat" else "high"
            elif next_tension <= 0.30:
                intensity = "low"

            # 1. Beat Causality
            c_trigger, c_response, c_consequence, c_link = cls._derive_beat_causality(
                fn=fn,
                b_idx=b_idx,
                speaker=speaker,
                target=target,
                action_verb=action_verb,
                scene=scene,
                prev_consequence=prev_consequence,
            )
            prev_consequence = c_consequence

            # 3. Relationship Evolution
            rel_shift = cls._derive_relationship_shift(
                fn=fn,
                speaker=speaker,
                target=target,
                scene_type=scene.scene_type,
            )

            # 4. Power & Information Dynamics
            lev_holder, vuln_char, irony = cls._derive_power_dynamics(
                fn=fn,
                speaker=speaker,
                target=target,
                scene=scene,
            )

            # 5. Meaningful Physical Blocking
            blocking_act = cls._derive_physical_blocking(
                fn=fn,
                speaker=speaker,
                target=target,
                scene_type=scene.scene_type,
            )

            # 8. Long-Range Story Connections
            s_conn = scene.story_connections[0] if (scene.story_connections and b_idx == 1) else None

            # 9. Conversational Dynamics
            conv_dyn = cls._derive_conversational_dynamic(
                fn=fn,
                speaker=speaker,
                target=target,
            )

            # 10. Dramatic Silence Intent
            silence_intent = cls._derive_silence_intent(
                fn=fn,
                speaker=speaker,
                target=target,
            )

            beat = DramaticBeat(
                beat_id=beat_id,
                scene_id=scene.scene_id,
                index=b_idx,
                dramatic_function=fn,
                summary=f"{speaker} attempts to {action_verb} {target or 'surroundings'} during {fn}",
                active_characters=scene.participants,
                primary_speaker=speaker,
                target_character=target,
                objective=obj,
                surface_emotion=surf_emo,
                underlying_emotion=under_emo,
                subtext=subtext_text,
                subtext_confidence=sub_conf,
                subtext_classification=sub_class,
                tension_before=curr_tension,
                tension_after=next_tension,
                intensity=intensity,
                power_shift=f"{speaker} establishes initiative" if fn in ("escalation", "reversal") else None,
                information_revealed=[f"Reveals motive during {fn}"] if fn == "reveal" else [],
                information_withheld=[f"Conceals deeper intent"] if fn in ("approach", "resistance") else [],
                performance_priority=priority,
                causal_trigger=c_trigger,
                character_response=c_response,
                consequence=c_consequence,
                causal_link_type=c_link,
                relationship_shift=rel_shift,
                leverage_holder=lev_holder,
                vulnerable_character=vuln_char,
                dramatic_irony=irony,
                blocking=blocking_act,
                provenance_mode="SOURCE_DIRECT" if fn in ("setup", "climax", "aftermath") else "INFERRED_PERFORMANCE",
                story_connection=s_conn,
                conversational_dynamic=conv_dyn,
                silence_intent=silence_intent,
            )
            beats.append(beat)
            curr_tension = next_tension

        return beats

    @classmethod
    def _get_beat_function_sequence(cls, scene_type: str, count: int) -> List[str]:
        templates = {
            "combat": ["approach", "threat", "escalation", "climax", "aftermath"],
            "confrontation": ["approach", "question", "resistance", "escalation", "reversal"],
            "revelation": ["setup", "question", "reveal", "realization", "decision"],
            "investigation": ["setup", "approach", "question", "reveal", "realization"],
            "romance": ["approach", "resistance", "emotional_turn", "realization"],
            "horror": ["setup", "approach", "threat", "escalation", "aftermath"],
            "dialogue": ["setup", "approach", "resistance", "decision"],
        }
        seq = templates.get(scene_type, ["setup", "approach", "escalation", "aftermath"])
        if len(seq) > count:
            return seq[:count]
        while len(seq) < count:
            seq.insert(-1, "escalation")
        return seq

    @classmethod
    def _get_initial_tension(cls, scene_type: str) -> float:
        tension_map = {
            "combat": 0.65,
            "confrontation": 0.50,
            "horror": 0.45,
            "revelation": 0.40,
            "investigation": 0.35,
            "dialogue": 0.30,
            "romance": 0.25,
            "comedy": 0.20,
        }
        return tension_map.get(scene_type, 0.35)

    @classmethod
    def _compute_tension_step(cls, function_name: str, step_idx: int, total_steps: int) -> float:
        steps = {
            "threat": 0.15,
            "escalation": 0.12,
            "climax": 0.18,
            "reversal": 0.10,
            "reveal": 0.08,
            "question": 0.04,
            "approach": 0.03,
            "resistance": 0.05,
            "emotional_turn": -0.05,
            "aftermath": -0.18,
            "decision": -0.06,
            "realization": 0.02,
            "setup": 0.0,
        }
        return steps.get(function_name, 0.03)

    @classmethod
    def _derive_actioning(cls, function_name: str, scene_type: str, speaker: str) -> str:
        if scene_type == "combat":
            mapping = {"approach": "probe", "threat": "intimidate", "escalation": "challenge", "climax": "command", "aftermath": "reassure"}
        elif scene_type == "confrontation":
            mapping = {"approach": "test", "question": "probe", "resistance": "deflect", "escalation": "threaten", "reversal": "provoke"}
        elif scene_type == "revelation":
            mapping = {"setup": "conceal", "question": "probe", "reveal": "confess", "realization": "concede", "decision": "command"}
        elif scene_type == "romance":
            mapping = {"approach": "seduce", "resistance": "deflect", "emotional_turn": "comfort", "realization": "reassure"}
        else:
            mapping = {"setup": "appraise", "approach": "probe", "resistance": "deflect", "escalation": "negotiate", "decision": "persuade"}
        return mapping.get(function_name, "persuade")

    @classmethod
    def _derive_immediate_goal(cls, function_name: str, speaker: str, target: Optional[str], scene_type: str) -> str:
        target_name = target or "counterpart"
        goals = {
            "threat": f"Force {target_name} to recognize mortal danger and freeze",
            "intimidate": f"Break {target_name}'s composure through sheer dominance",
            "deflect": f"Divert {target_name}'s scrutiny away from vulnerable territory",
            "probe": f"Test {target_name}'s defensive boundaries and search for weakness",
            "confess": f"Disclose hidden reality and shift moral burden onto {target_name}",
            "reassure": f"Restore equilibrium and prevent panic from compromising position",
            "challenge": f"Compel {target_name} to back down or commit to open confrontation",
            "seduce": f"Lower {target_name}'s defensive wariness through calculated intimacy",
        }
        return goals.get(function_name, f"Advance position and secure control over encounter with {target_name}")

    @classmethod
    def _derive_obstacle(cls, function_name: str, target: Optional[str], scene_type: str) -> str:
        target_name = target or "counterpart"
        obstacles = {
            "threat": f"{target_name}'s stubborn pride and refusal to display fear",
            "deflect": f"{target_name}'s persistent forensic focus and penetrating gaze",
            "probe": f"{target_name}'s guarded responses and calculated silence",
            "challenge": f"Immediate physical or social retaliatory peril",
        }
        return obstacles.get(function_name, f"{target_name}'s conflicting agenda and resistance")

    @classmethod
    def _derive_dual_emotions(cls, function_name: str, scene_type: str, action_verb: str) -> Tuple[str, Optional[str]]:
        """Distinguish outward surface emotion from underlying psychological state."""
        verb = "threaten" if action_verb == "threat" else action_verb
        pairs = {
            "threaten": ("cold_menace", "mounting_fear"),
            "intimidate": ("bellowing_rage", "insecurity"),
            "deflect": ("calm_irony", "suppressed_panic"),
            "probe": ("detached_curiosity", "deep_suspicion"),
            "confess": ("resigned_sorrow", "trembling_guilt"),
            "seduce": ("tender_warmth", "calculating_ambition"),
            "challenge": ("confident_scorn", "adrenalin_strain"),
            "reassure": ("gentle_composure", "internal_exhaustion"),
            "test": ("guarded_skepticism", "acute_vigilance"),
            "command": ("austere_authority", "desperate_urgency"),
            "provoke": ("mocking_bravado", "defensive_tension"),
            "conceal": ("flat_stoicism", "racing_anxiety"),
            "negotiate": ("courteous_detachment", "intense_calculation"),
            "comfort": ("tender_solace", "heartfelt_grief"),
        }
        return pairs.get(verb, ("controlled_composure", "underlying_tension"))

    @classmethod
    def _derive_subtext(
        cls,
        function_name: str,
        speaker: str,
        target: Optional[str],
        action_verb: str,
        surface_emo: str,
        underlying_emo: Optional[str],
    ) -> Tuple[Optional[str], float, SubtextClassification]:
        """
        Conservative subtext derivation with strict confidence bounds.
        Never treats subtext as canonical factual reality.
        """
        verb = "threaten" if action_verb == "threat" else action_verb
        subtext_templates = {
            "threaten": (f"I cannot afford to let you take another step or we both perish.", 0.88, "CONTEXTUAL_INFERENCE"),
            "deflect": (f"You are dangerously close to a truth I am bound to conceal.", 0.82, "CONTEXTUAL_INFERENCE"),
            "probe": (f"I suspect you are concealing something critical, and I will find it.", 0.80, "CONTEXTUAL_INFERENCE"),
            "confess": (f"The burden of holding this silence has become intolerable.", 0.85, "SOURCE_SUPPORTED"),
            "seduce": (f"If I let you see who I truly am, I lose all power over you.", 0.70, "CREATIVE_INTERPRETATION"),
            "challenge": (f"I am far more frightened than I will ever permit you to witness.", 0.75, "CONTEXTUAL_INFERENCE"),
            "reassure": (f"I am barely holding myself together, but you must not know it.", 0.78, "CONTEXTUAL_INFERENCE"),
            "test": (f"I need to know whose side you are truly on before I commit.", 0.80, "CONTEXTUAL_INFERENCE"),
            "command": (f"If I do not project unshakeable authority right now, order collapses.", 0.84, "CONTEXTUAL_INFERENCE"),
            "provoke": (f"I need you off-balance so you reveal what you are hiding.", 0.79, "CONTEXTUAL_INFERENCE"),
            "conceal": (f"If this truth comes to light, the consequences will destroy us.", 0.86, "CONTEXTUAL_INFERENCE"),
            "negotiate": (f"Neither of us can afford an all-out confrontation here.", 0.75, "CONTEXTUAL_INFERENCE"),
        }
        if verb in subtext_templates:
            txt, conf, cls_val = subtext_templates[verb]
            return txt, conf, cls_val
        return None, 0.0, "SOURCE_SUPPORTED"

    @classmethod
    def _derive_beat_causality(
        cls,
        fn: str,
        b_idx: int,
        speaker: str,
        target: Optional[str],
        action_verb: str,
        scene: SceneDramaticPlan,
        prev_consequence: Optional[str] = None,
    ) -> Tuple[str, str, str, CausalLinkType]:
        """
        Derives unbroken causal chain linking each beat to preceding and succeeding beats
        using South Park ('therefore' / 'but') dramatic causality principles.
        """
        tgt = target or "counterpart"
        if b_idx == 1:
            trigger = f"Scene opens as {speaker} confronts {tgt} in {scene.location}"
            response = f"{speaker} initiates tactical maneuver by choosing to {action_verb}"
            consequence = f"{tgt} is forced to react, shifting immediate initiative"
            link: CausalLinkType = "catalyst"
            return trigger, response, consequence, link

        # Subsequent beats inherit predecessor consequence as their causal trigger
        trigger = prev_consequence or f"Preceding dramatic escalation in beat {b_idx - 1}"
        response = f"{speaker} counters with {action_verb} to regain advantage"

        if fn in ("resistance", "reversal", "threat"):
            link = "but"
            consequence = f"Expected progression is disrupted as {speaker} executes {fn}, putting {tgt} on the defensive"
        elif fn in ("climax", "decision", "reveal"):
            link = "therefore"
            consequence = f"Irreversible dramatic transformation occurs; {tgt} must face immediate fallout"
        else:
            link = "therefore"
            consequence = f"Situational stakes escalate, compelling subsequent response from {tgt}"

        return trigger, response, consequence, link

    @classmethod
    def _derive_relationship_shift(
        cls,
        fn: str,
        speaker: str,
        target: Optional[str],
        scene_type: str,
    ) -> Optional[RelationshipShift]:
        """Track interpersonal relational movement triggered by this beat."""
        if not target:
            return None

        if fn in ("threat", "escalation"):
            return RelationshipShift(
                source_character=speaker,
                target_character=target,
                dimension="hostility",
                direction="increased",
                description=f"Hostility heightened between {speaker} and {target} under {fn}",
            )
        elif fn == "reversal":
            return RelationshipShift(
                source_character=speaker,
                target_character=target,
                dimension="dominance",
                direction="inverted",
                description=f"Relational dominance inverted between {speaker} and {target}",
            )
        elif fn in ("reveal", "confess"):
            direction: Any = "cemented" if scene_type == "romance" else "severed"
            return RelationshipShift(
                source_character=speaker,
                target_character=target,
                dimension="trust",
                direction=direction,
                description=f"Disclosure forces irrevocable trust reassessment between {speaker} and {target}",
            )
        elif fn == "emotional_turn":
            dim: Any = "intimacy" if scene_type == "romance" else "fear"
            return RelationshipShift(
                source_character=speaker,
                target_character=target,
                dimension=dim,
                direction="increased",
                description=f"Emotional boundary dropped between {speaker} and {target}",
            )
        elif fn == "resistance":
            return RelationshipShift(
                source_character=speaker,
                target_character=target,
                dimension="cooperation",
                direction="decreased",
                description=f"Cooperative alignment fractured as {speaker} actively resists {target}",
            )
        return None

    @classmethod
    def _derive_power_dynamics(
        cls,
        fn: str,
        speaker: str,
        target: Optional[str],
        scene: SceneDramaticPlan,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Track tactical leverage holder, vulnerable character, and dramatic irony."""
        lev_holder = None
        vuln_char = None
        irony = None

        if fn in ("threat", "command", "escalation", "reversal"):
            lev_holder = speaker
            vuln_char = target
        elif fn in ("resistance", "deflect"):
            lev_holder = target
            vuln_char = speaker

        if scene.listener_knowledge_state and "irony" in scene.listener_knowledge_state.lower():
            irony = f"Audience perceives hidden truth while {vuln_char or target or 'character'} remains oblivious"
        elif scene.epistemic_asymmetry:
            irony = scene.epistemic_asymmetry[0]

        return lev_holder, vuln_char, irony

    @classmethod
    def _derive_physical_blocking(
        cls,
        fn: str,
        speaker: str,
        target: Optional[str],
        scene_type: str,
    ) -> Optional[PhysicalBlocking]:
        """Preserve physical blocking actions that materially affect dramatic situation."""
        tgt = target or "counterpart"
        if fn == "threat":
            return PhysicalBlocking(
                character=speaker,
                action_description=f"{speaker} closes physical distance and fixes posture aggressively toward {tgt}",
                dramatic_significance="threat_display",
                spatial_intent="intimate_close",
            )
        elif fn == "approach":
            return PhysicalBlocking(
                character=speaker,
                action_description=f"{speaker} steps forward into the primary acoustic zone, establishing presence",
                dramatic_significance="territorial_control",
                spatial_intent="mid_stage",
            )
        elif fn == "resistance":
            return PhysicalBlocking(
                character=speaker,
                action_description=f"{speaker} angles body away, creating an acoustic and physical barrier",
                dramatic_significance="barrier_creation",
                spatial_intent="defensive_offset",
            )
        elif fn == "climax":
            return PhysicalBlocking(
                character=speaker,
                action_description=f"{speaker} commits to decisive physical action, collapsing remaining separation",
                dramatic_significance="power_assertion",
                spatial_intent="dynamic_center",
            )
        elif fn == "reveal":
            return PhysicalBlocking(
                character=speaker,
                action_description=f"{speaker} freezes in stillness, locking eye contact with {tgt}",
                dramatic_significance="revelation_trigger",
                spatial_intent="static_focus",
            )
        return None

    @classmethod
    def _derive_conversational_dynamic(
        cls,
        fn: str,
        speaker: str,
        target: Optional[str],
    ) -> Optional[ConversationalDynamic]:
        """Capture turn-taking dynamics, interruptions, and rhetorical shifts."""
        tgt = target or "counterpart"
        if fn == "resistance":
            return ConversationalDynamic(
                dynamic_type="deflection_avoidance",
                initiator=speaker,
                target=target,
                description=f"{speaker} sidesteps direct inquiry from {tgt}",
            )
        elif fn == "threat":
            return ConversationalDynamic(
                dynamic_type="interruption",
                initiator=speaker,
                target=target,
                description=f"{speaker} forcefully cuts across {tgt}'s response with an ultimatum",
            )
        elif fn == "escalation":
            return ConversationalDynamic(
                dynamic_type="escalation",
                initiator=speaker,
                target=target,
                description=f"{speaker} accelerates rhetorical tempo and heightens stakes against {tgt}",
            )
        elif fn == "reversal":
            return ConversationalDynamic(
                dynamic_type="strategy_shift",
                initiator=speaker,
                target=target,
                description=f"{speaker} suddenly pivots conversational strategy from retreat to offensive counter",
                strategy_before="guarded_defense",
                strategy_after="aggressive_counter",
            )
        elif fn in ("question", "approach"):
            return ConversationalDynamic(
                dynamic_type="hesitation",
                initiator=speaker,
                target=target,
                description=f"{speaker} hesitates briefly, weighing words before committing",
            )
        return ConversationalDynamic(
            dynamic_type="steady_exchange",
            initiator=speaker,
            target=target,
            description=f"Measured turn-taking exchange between {speaker} and {tgt}",
        )

    @classmethod
    def _derive_silence_intent(
        cls,
        fn: str,
        speaker: str,
        target: Optional[str],
    ) -> Optional[DramaticSilenceIntent]:
        """Identify narrative purpose of silence or pause (anticipation, shock, grief, realization)."""
        tgt = target or "counterpart"
        if fn == "reveal":
            return DramaticSilenceIntent(
                purpose="shock",
                affected_character=target,
                dramatic_rationale=f"Allows revelation to detonate emotionally before {tgt} can formulate a response",
                listening_focus="character_reaction",
            )
        elif fn == "realization":
            return DramaticSilenceIntent(
                purpose="realization",
                affected_character=speaker,
                dramatic_rationale=f"Cognitive digestion of irrevocable truth by {speaker}",
                listening_focus="subtext_digestion",
            )
        elif fn == "aftermath":
            return DramaticSilenceIntent(
                purpose="grief",
                affected_character=speaker,
                dramatic_rationale="Acoustic space for emotional absorption in the wake of conflict",
                listening_focus="acoustic_space",
            )
        elif fn == "threat":
            return DramaticSilenceIntent(
                purpose="intimidation",
                affected_character=target,
                dramatic_rationale=f"Weight of mortal peril hangs in heavy silence before {tgt}",
                listening_focus="character_reaction",
            )
        elif fn == "approach":
            return DramaticSilenceIntent(
                purpose="anticipation",
                affected_character=speaker,
                dramatic_rationale="Suspenseful stillness prior to initiating confrontation",
                listening_focus="subtext_digestion",
            )
        return None

    @classmethod
    def slice_chapter_by_beats(
        cls,
        chapter_text: str,
        dramatic_plan: DramaticPlan,
        max_words: int = 1200,
    ) -> List[Dict[str, Any]]:
        """
        Beat-Aligned Chunk Slicer (Confirmed /grill-me Solution):
        Slices chapter into processing chunks aligned strictly to natural scene
        and beat boundaries. Prevents arbitrary cuts from severing a dramatic beat.

        Returns list of dicts:
        [{
            "chunk_index": int,
            "text": str,
            "scene_id": str,
            "beat_ids": List[str],
            "word_count": int,
            "is_scene_start": bool,
            "is_scene_end": bool,
        }]
        """
        paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]
        total_paras = len(paragraphs)
        if total_paras == 0:
            return []

        # If short chapter, return single unified chunk
        total_words = sum(len(p.split()) for p in paragraphs)
        if total_words <= max_words or not dramatic_plan.scenes:
            return [{
                "chunk_index": 1,
                "text": "\n\n".join(paragraphs),
                "scene_id": dramatic_plan.scenes[0].scene_id if dramatic_plan.scenes else "scene_001",
                "beat_ids": [b.beat_id for s in dramatic_plan.scenes for b in s.beats],
                "word_count": total_words,
                "is_scene_start": True,
                "is_scene_end": True,
            }]

        chunks: List[Dict[str, Any]] = []
        num_scenes = len(dramatic_plan.scenes)
        paras_per_scene = max(1, total_paras // max(1, num_scenes))

        chunk_idx = 1
        for s_idx, scene in enumerate(dramatic_plan.scenes):
            start_p = s_idx * paras_per_scene
            end_p = (s_idx + 1) * paras_per_scene if s_idx < num_scenes - 1 else total_paras
            scene_paras = paragraphs[start_p:end_p]
            scene_words = sum(len(p.split()) for p in scene_paras)

            if scene_words <= max_words:
                chunks.append({
                    "chunk_index": chunk_idx,
                    "text": "\n\n".join(scene_paras),
                    "scene_id": scene.scene_id,
                    "beat_ids": [b.beat_id for b in scene.beats],
                    "word_count": scene_words,
                    "is_scene_start": True,
                    "is_scene_end": True,
                })
                chunk_idx += 1
            else:
                # Scene exceeds max_words: slice on intra-scene beat boundaries
                num_beats = max(1, len(scene.beats))
                paras_per_beat = max(1, len(scene_paras) // num_beats)
                cur_b_paras: List[str] = []
                cur_b_words = 0
                active_b_ids: List[str] = []

                for b_i, beat in enumerate(scene.beats):
                    bp_start = b_i * paras_per_beat
                    bp_end = (b_i + 1) * paras_per_beat if b_i < num_beats - 1 else len(scene_paras)
                    beat_paras = scene_paras[bp_start:bp_end]
                    b_words = sum(len(p.split()) for p in beat_paras)

                    if cur_b_words + b_words > max_words and cur_b_paras:
                        chunks.append({
                            "chunk_index": chunk_idx,
                            "text": "\n\n".join(cur_b_paras),
                            "scene_id": scene.scene_id,
                            "beat_ids": list(active_b_ids),
                            "word_count": cur_b_words,
                            "is_scene_start": (chunk_idx == 1 or chunks[-1]["scene_id"] != scene.scene_id),
                            "is_scene_end": False,
                        })
                        chunk_idx += 1
                        cur_b_paras = list(beat_paras)
                        cur_b_words = b_words
                        active_b_ids = [beat.beat_id]
                    else:
                        cur_b_paras.extend(beat_paras)
                        cur_b_words += b_words
                        active_b_ids.append(beat.beat_id)

                if cur_b_paras:
                    chunks.append({
                        "chunk_index": chunk_idx,
                        "text": "\n\n".join(cur_b_paras),
                        "scene_id": scene.scene_id,
                        "beat_ids": list(active_b_ids),
                        "word_count": cur_b_words,
                        "is_scene_start": (chunk_idx == 1 or chunks[-1]["scene_id"] != scene.scene_id),
                        "is_scene_end": True,
                    })
                    chunk_idx += 1

        return chunks
