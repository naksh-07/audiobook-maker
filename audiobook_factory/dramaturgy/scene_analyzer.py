#!/usr/bin/env python3
"""
Audiobook Factory - Dramaturgy: Scene Analyzer.
Discovers organic scene boundaries and analyzes scene-level dramatic purpose,
stakes, conflicts, opening/closing states, listener knowledge, and complexity.
"""

from __future__ import annotations
import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple

from audiobook_factory.translation.intensity_model import IntensityEvaluator
from .contracts import (
    SceneDramaticPlan,
    SceneType,
    DramaticComplexity,
    DramaticStateDelta,
    StoryConnectionRecord,
    NarrativeDistance,
)


class SceneAnalyzer:
    """
    Analyzes chapter text to discover narrative scene boundaries and construct
    rich SceneDramaticPlan blueprints with dramatic question, stakes, and conflicts.
    """

    # Narrative transition heuristic patterns
    TIME_PATTERNS = [
        r"\b(?:the next morning|at dawn|by dusk|later that evening|several hours later|at midnight|next day|the following day)\b",
        r"\b(?:in the morning|after sunset|as darkness fell|days passed|weeks passed|a moment later|hours passed)\b",
        r"\b(?:अगली\s+सुबह|दोपहर\s+को|शाम\s+ढलते\s+ही|रात\s+के\s+वक्त|कुछ\s+देर\s+बाद|कई\s+दिनों\s+बाद)\b",
    ]
    LOCATION_PATTERNS = [
        r"\b(?:left the|entered the|arrived at|walked into|stepped outside|in the courtyard|in the temple|in the tavern|in the library)\b",
        r"\b(?:at the gates?|on the road|by the river|in the forest|under the bridge|into the chamber|in the alley)\b",
        r"\b(?:कमरे\s+से\s+बाहर|सड़क\s+पर|दरवाजे\s+पर|जंगल\s+में|महल\s+के\s+भीतर|सराय\s+में|नदी\s+किनारे)\b",
    ]
    DIVIDER_PATTERNS = [r"^\s*[-*_~]{3,}\s*$", r"^\s*\*\s*\*\s*\*\s*$"]

    COMPILED_TIME = [re.compile(p, re.IGNORECASE) for p in TIME_PATTERNS]
    COMPILED_LOC = [re.compile(p, re.IGNORECASE) for p in LOCATION_PATTERNS]
    COMPILED_DIVIDERS = [re.compile(p) for p in DIVIDER_PATTERNS]

    @classmethod
    def segment_and_analyze_scenes(
        cls,
        chapter_text: str,
        chapter_num: int = 1,
        chapter_title: str = "Chapter",
        known_characters: Optional[List[str]] = None,
        memory_context: Optional[Any] = None,
    ) -> List[SceneDramaticPlan]:
        """
        Segments chapter into organic dramatic scenes and generates detailed
        dramatic plans for each scene.
        """
        paragraphs = [p.strip() for p in chapter_text.split("\n\n") if p.strip()]
        total_paras = len(paragraphs)
        if total_paras == 0:
            return []

        boundaries = cls._discover_scene_boundaries(paragraphs)
        scenes: List[SceneDramaticPlan] = []

        for s_idx, (start_p, end_p) in enumerate(boundaries, 1):
            scene_paras = paragraphs[start_p : end_p + 1]
            scene_text = "\n\n".join(scene_paras)
            scene_id = f"scene_{s_idx:03d}"
            scene_title_str = f"{chapter_title} - Scene {s_idx}"

            plan = cls.analyze_single_scene(
                scene_text=scene_text,
                scene_id=scene_id,
                chapter_num=chapter_num,
                scene_title=scene_title_str,
                known_characters=known_characters,
                memory_context=memory_context,
            )
            scenes.append(plan)

        return scenes

    @classmethod
    def _discover_scene_boundaries(cls, paragraphs: List[str]) -> List[Tuple[int, int]]:
        """
        Discovers paragraph range tuples (start_idx, end_idx) based on true narrative
        transitions, explicit dividers, or significant character/setting shifts.
        """
        total = len(paragraphs)
        if total <= 3:
            return [(0, total - 1)]

        boundaries: List[int] = [0]
        accum_words = 0

        for i, para in enumerate(paragraphs):
            w_count = len(para.split())
            accum_words += w_count

            # Check explicit scene divider
            if any(p.match(para) for p in cls.COMPILED_DIVIDERS):
                if i not in boundaries and (i - boundaries[-1]) >= 2:
                    boundaries.append(i)
                    accum_words = 0
                continue

            # Check narrative transitions after sufficient paragraph depth
            if (accum_words >= 280 or (i - boundaries[-1]) >= 3) and i < total - 1:
                has_time = any(p.search(para) for p in cls.COMPILED_TIME)
                has_loc = any(p.search(para) for p in cls.COMPILED_LOC)
                if has_time or has_loc:
                    boundaries.append(i)
                    accum_words = 0

        # Build ranges
        ranges: List[Tuple[int, int]] = []
        for idx in range(len(boundaries)):
            s_idx = boundaries[idx]
            e_idx = boundaries[idx + 1] - 1 if idx + 1 < len(boundaries) else total - 1
            if s_idx <= e_idx:
                ranges.append((s_idx, e_idx))
        return ranges

    @classmethod
    def analyze_single_scene(
        cls,
        scene_text: str,
        scene_id: str = "scene_001",
        chapter_num: int = 1,
        scene_title: str = "Scene 1",
        known_characters: Optional[List[str]] = None,
        memory_context: Optional[Any] = None,
    ) -> SceneDramaticPlan:
        """
        Analyzes a single scene text and derives its dramatic architecture.
        """
        loc, time_str = cls._infer_setting(scene_text)
        active_chars = cls._extract_active_characters(scene_text, known_characters, memory_context)
        scene_type = cls._infer_scene_type(scene_text)
        complexity = cls._calculate_complexity(scene_text, active_chars, scene_type)

        primary_conflict, secondary_conflicts = cls._derive_conflicts(scene_text, active_chars, scene_type)
        purpose = cls._derive_dramatic_purpose(scene_text, scene_type, primary_conflict)
        question = cls._derive_scene_question(scene_text, active_chars, scene_type)
        stakes = cls._derive_stakes(scene_text, scene_type)
        opening_state, closing_state = cls._derive_scene_states(scene_text, scene_type)
        listener_knowledge = cls._derive_listener_knowledge(scene_text, active_chars, memory_context)

        reveals, reversals = cls._detect_reveals_and_reversals(scene_text)
        s_hash = hashlib.sha256(scene_text.encode("utf-8")).hexdigest()

        # Capability 2: Dramatic State Delta
        state_delta = cls._derive_state_delta(
            scene_text=scene_text,
            scene_type=scene_type,
            primary_conflict=primary_conflict,
            opening_state=opening_state,
            closing_state=closing_state,
            reveals=reveals,
            reversals=reversals,
            active_chars=active_chars,
        )

        # Capability 4: Power & Epistemic Asymmetry
        epistemic_asymmetry = cls._derive_epistemic_asymmetry(
            listener_knowledge=listener_knowledge,
            active_chars=active_chars,
            memory_context=memory_context,
            reveals=reveals,
        )

        # Capability 6: Narrative Mode, Distance, & Perspective
        narrative_pov, narrative_distance, pov_char = cls._infer_narrative_mode_and_pov(
            scene_text=scene_text,
            active_chars=active_chars,
        )

        # Capability 8: Long-Range Story Connections
        story_connections = cls._detect_story_connections(
            scene_text=scene_text,
            memory_context=memory_context,
        )

        return SceneDramaticPlan(
            scene_id=scene_id,
            chapter_num=chapter_num,
            scene_title=scene_title,
            scene_type=scene_type,
            location=loc,
            time_context=time_str,
            dramatic_purpose=purpose,
            scene_question=question,
            stakes=stakes,
            opening_state=opening_state,
            closing_state=closing_state,
            primary_conflict=primary_conflict,
            secondary_conflicts=secondary_conflicts,
            participants=active_chars,
            dramatic_complexity=complexity,
            listener_knowledge_state=listener_knowledge,
            major_reveals=reveals,
            reversals=reversals,
            tension_curve=[],
            beats=[],
            source_hash=s_hash,
            state_delta=state_delta,
            epistemic_asymmetry=epistemic_asymmetry,
            narrative_pov=narrative_pov,
            narrative_distance=narrative_distance,
            pov_character=pov_char,
            story_connections=story_connections,
        )

    @classmethod
    def _extract_active_characters(
        cls,
        text: str,
        known_characters: Optional[List[str]] = None,
        memory_context: Optional[Any] = None,
    ) -> List[str]:
        """Extract canonical characters active in the scene."""
        found = []
        if known_characters:
            for name in known_characters:
                if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                    if name not in found:
                        found.append(name)

        if memory_context and hasattr(memory_context, "active_character_states"):
            for name in memory_context.active_character_states.keys():
                if name not in found and re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
                    found.append(name)

        if not found:
            # Dynamic proper noun frequency fallback
            candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b", text)
            stop_words = {
                "The", "He", "She", "They", "Then", "After", "Before", "There", "When",
                "What", "It", "In", "On", "At", "And", "But", "Or", "So", "However",
                "Suddenly", "Meanwhile", "Later", "Now", "Just", "Even", "Though"
            }
            freq: Dict[str, int] = {}
            for c in candidates:
                if c not in stop_words and len(c) > 2:
                    freq[c] = freq.get(c, 0) + 1
            found = [name for name, count in sorted(freq.items(), key=lambda x: x[1], reverse=True) if count >= 1][:4]

        return found

    @classmethod
    def _infer_setting(cls, text: str) -> Tuple[str, str]:
        loc = "Unspecified Setting"
        common_locs = (
            "chamber", "tavern", "forest", "dungeon", "courtyard", "corridor", "hall",
            "crypt", "road", "library", "temple", "palace", "street", "alley", "room",
            "study", "garden", "cabin", "cell", "gate", "bridge", "vault"
        )
        for cand in common_locs:
            if re.search(rf"\b{cand}\b", text, re.IGNORECASE):
                loc = cand.title()
                break

        time_str = "Day"
        for t in ("night", "midnight", "dawn", "dusk", "evening", "morning", "twilight"):
            if re.search(rf"\b{t}\b", text, re.IGNORECASE):
                time_str = t.title()
                break

        return loc, time_str

    @classmethod
    def _infer_scene_type(cls, text: str) -> str:
        t_low = text.lower()
        scores: Dict[str, int] = {
            "combat": sum(1 for w in ("sword", "blade", "strike", "blood", "stab", "parry", "blow", "clash", "punch", "shield", "axe", "spear") if w in t_low),
            "confrontation": sum(1 for w in ("threat", "liar", "kill you", "confess", "admit it", "furious", "glared", "trap", "traitor", "roared") if w in t_low),
            "revelation": sum(1 for w in ("truth is", "secret", "revealed", "discovered that", "confession", "betrayed", "the truth", "unmasked", "conspiracy") if w in t_low),
            "romance": sum(1 for w in ("kiss", "passion", "naked", "caress", "tender embrace", "sweetheart", "desire", "caressed", "sensual", "darling") if w in t_low),
            "investigation": sum(1 for w in ("clue", "cipher", "investigat", "search", "tracks", "mystery", "evidence", "inspect", "ledger") if w in t_low),
            "horror": sum(1 for w in ("horror", "corpse", "monster", "dread", "terror", "creature", "abomination", "screamed in terror", "chilling dread") if w in t_low),
            "comedy": sum(1 for w in ("laughed", "smiled", "joke", "witty", "cynical", "banter", "mock", "beer", "wine", "chuckle", "grinned") if w in t_low),
            "introspection": sum(1 for w in ("thought to himself", "reflected", "remembered", "wondered", "pondered", "memory", "alone on", "solitary", "grief", "wept") if w in t_low),
        }

        # Filter categories with at least 1 match
        active_scores = {k: v for k, v in scores.items() if v > 0}
        if not active_scores:
            return "dialogue"

        # Return category with highest signal score
        best_cat = max(active_scores.items(), key=lambda x: x[1])[0]
        return best_cat

    @classmethod
    def _calculate_complexity(cls, text: str, participants: List[str], scene_type: str) -> str:
        """Rate scene complexity: LOW, MEDIUM, HIGH, CRITICAL."""
        t_low = text.lower()
        has_climax = (
            any(w in t_low for w in ("climax", "final strike", "fatal blow", "exploded", "death of"))
            or ("shattered" in t_low and scene_type == "combat" and len(participants) >= 2)
        )
        if has_climax or (scene_type == "combat" and len(participants) >= 3):
            return "CRITICAL"
        if scene_type in ("confrontation", "revelation", "horror"):
            return "HIGH"
        if len(participants) >= 3 or scene_type in ("combat", "investigation", "romance"):
            return "HIGH"
        if scene_type in ("dialogue", "comedy") and len(participants) >= 2:
            return "MEDIUM"
        return "LOW"

    @classmethod
    def _derive_conflicts(cls, text: str, participants: List[str], scene_type: str) -> Tuple[str, List[str]]:
        if len(participants) >= 2:
            p1, p2 = participants[0], participants[1]
            if scene_type == "confrontation":
                primary = f"Direct confrontation between {p1} and {p2}"
                secondary = [f"{p1} seeks leverage while {p2} defends position"]
            elif scene_type == "combat":
                primary = f"Lethal physical engagement between {p1} and {p2}"
                secondary = ["Survival under intense physical strain"]
            elif scene_type == "investigation":
                primary = f"{p1} interrogating or probing {p2} for hidden information"
                secondary = ["Resistance to disclosure"]
            else:
                primary = f"Interpersonal tension between {p1} and {p2}"
                secondary = ["Clash of objectives and unspoken expectations"]
        else:
            primary = "Protagonist against immediate situational obstacles"
            secondary = ["Internal dilemma and environmental uncertainty"]
        return primary, secondary

    @classmethod
    def _derive_dramatic_purpose(cls, text: str, scene_type: str, conflict: str) -> str:
        purposes = {
            "combat": "Test physical survival and shift immediate balance of power",
            "confrontation": "Force an irreconcilable conflict into the open and demand accountability",
            "revelation": "Expose critical narrative truth that alters character trajectories",
            "investigation": "Uncover hidden clues while managing risks of discovery",
            "romance": "Explore emotional vulnerability and shifting relational intimacy",
            "horror": "Induce mounting dread and expose characters to existential peril",
            "introspection": "Process recent emotional trauma and formulate new resolve",
            "comedy": "Subvert tension through sharp character banter and sociolect contrast",
            "dialogue": "Advance plot dynamics, negotiate objectives, and establish character status",
        }
        return purposes.get(scene_type, "Develop narrative arc and character dynamics")

    @classmethod
    def _derive_scene_question(cls, text: str, participants: List[str], scene_type: str) -> str:
        p_name = participants[0] if participants else "The protagonist"
        questions = {
            "combat": f"Will {p_name} survive the clash without suffering a catastrophic defeat?",
            "confrontation": f"Will {p_name} break the opponent's resolve or be forced to yield?",
            "revelation": f"How will {p_name} react once the hidden truth is laid bare?",
            "investigation": f"Can {p_name} extract the vital truth before time or secrecy expires?",
            "romance": f"Will emotional walls collapse or will vulnerability trigger retreat?",
            "horror": f"Can {p_name} escape or endure the encroaching terror?",
            "dialogue": f"Can {p_name} secure their objective without exposing their weakness?",
        }
        return questions.get(scene_type, f"Will {p_name} achieve their objective in this encounter?")

    @classmethod
    def _derive_stakes(cls, text: str, scene_type: str) -> str:
        stakes_map = {
            "combat": "Life, severe bodily trauma, and immediate physical dominion",
            "confrontation": "Status, personal autonomy, and relational destruction",
            "revelation": "Collapse of cherished assumptions and irreversible shift in loyalty",
            "investigation": "Exposure of covert mission or loss of irreplaceable evidence",
            "romance": "Emotional safety, trust, and risk of profound heartbreak",
            "horror": "Sanity, survival, and containment of nightmare forces",
            "dialogue": "Tactical advantage, crucial resources, and interpersonal leverage",
        }
        return stakes_map.get(scene_type, "Narrative momentum and character agency")

    @classmethod
    def _derive_scene_states(cls, text: str, scene_type: str) -> Tuple[str, str]:
        states = {
            "combat": ("Alert vigilance, imminent mortal clash", "Exhausted survival, physical aftermath"),
            "confrontation": ("Simmering suppressed hostility", "Open rupture, polarized terms established"),
            "revelation": ("Guarded ignorance or false certainty", "Disillusioned clarity, irrevocable truth known"),
            "investigation": ("Cautious curiosity, searching shadows", "New evidence discovered, higher danger acknowledged"),
            "romance": ("Defensive distance, simmering attraction", "Deepened intimacy or fraught mutual vulnerability"),
            "horror": ("Unsettling stillness, growing disquiet", "Shocked terror, desperate flight or resilience"),
            "dialogue": ("Controlled negotiation, mutual appraisal", "Shifted alignment, altered expectations"),
        }
        return states.get(scene_type, ("Initial equilibrium", "Altered dramatic landscape"))

    @classmethod
    def _derive_listener_knowledge(cls, text: str, participants: List[str], memory_context: Optional[Any]) -> str:
        """Detect dramatic irony or secret disclosure."""
        if memory_context and hasattr(memory_context, "epistemic_constraints"):
            # Check if one character has unknown facts that others have
            constraints = memory_context.epistemic_constraints
            if len(participants) >= 2:
                p1_unknowns = constraints.get(participants[0], {}).get("UNKNOWN", [])
                p2_knowns = constraints.get(participants[1], {}).get("KNOWN", [])
                if any(k in p1_unknowns for k in p2_knowns):
                    return f"Dramatic irony: Audience and {participants[1]} aware of hidden truth that {participants[0]} does not know."

        t_low = text.lower()
        if "unbeknownst" in t_low:
            return "Dramatic irony: Audience observes concealed dynamics unfolding unbeknownst to active characters."
        if "secret" in t_low or "hidden" in t_low:
            return "Audience observes concealed dynamics unfolding between characters."
        return "Audience and active characters share aligned narrative perspective."

    @classmethod
    def _detect_reveals_and_reversals(cls, text: str) -> Tuple[List[str], List[str]]:
        reveals = []
        reversals = []
        t_low = text.lower()
        for phrase in ("the truth", "revealed", "confessed", "discovered", "unmasked", "secret"):
            if phrase in t_low:
                reveals.append(f"Disclosed: '{phrase}' detected in narrative flow")
        for phrase in ("suddenly turned", "betrayed", "reversed", "in an instant everything changed", "table turned"):
            if phrase in t_low:
                reversals.append(f"Reversal: '{phrase}' marks shift in fortune")
        return reveals, reversals

    @classmethod
    def _derive_state_delta(
        cls,
        scene_text: str,
        scene_type: str,
        primary_conflict: str,
        opening_state: str,
        closing_state: str,
        reveals: List[str],
        reversals: List[str],
        active_chars: List[str],
    ) -> DramaticStateDelta:
        """
        Derives net transformation across knowledge, relationships, objectives,
        power, danger, decisions, and emotional state between scene entry and exit.
        """
        # Knowledge delta
        k_delta = list(reveals)
        if not k_delta:
            k_delta.append(f"Established situational parameters regarding {primary_conflict}")

        # Relationship shifts
        rel_shifts: List[str] = []
        if len(active_chars) >= 2:
            p1, p2 = active_chars[0], active_chars[1]
            if scene_type in ("combat", "confrontation"):
                rel_shifts.append(f"Hostility heightened and stakes polarized between {p1} and {p2}")
            elif scene_type == "romance":
                rel_shifts.append(f"Vulnerability deepened and defensive barriers softened between {p1} and {p2}")
            elif scene_type in ("investigation", "revelation"):
                rel_shifts.append(f"Cooperative reliance tested by emerging evidence between {p1} and {p2}")
            else:
                rel_shifts.append(f"Dynamic shifted through mutual appraisal between {p1} and {p2}")

        # Power shift
        p_shift = None
        if reversals:
            p_shift = f"Leverage inverted: {reversals[0]}"
        elif scene_type in ("combat", "confrontation") and active_chars:
            p_shift = f"{active_chars[0]} asserted dominant initiative in {scene_type}"

        # Danger level delta
        danger_delta: Any = "unchanged"
        if scene_type in ("combat", "horror"):
            danger_delta = "escalated"
        elif scene_type in ("confrontation", "investigation", "revelation"):
            danger_delta = "escalated" if (reveals or "threat" in scene_text.lower()) else "latent"
        elif reversals or "aftermath" in scene_text.lower():
            danger_delta = "reduced"

        # Decisions made
        decisions: List[str] = []
        dec_matches = re.findall(
            r"\b(?:decided|chose|agreed|refused|swore|vowed|resolved|फैसला किया|तय किया)\s+([^.,;\n]{8,40})",
            scene_text,
            re.IGNORECASE,
        )
        for m in dec_matches[:3]:
            decisions.append(f"Committed: '{m.strip()}'")
        if not decisions and scene_type in ("combat", "confrontation", "decision"):
            decisions.append(f"Forced to engage directly with {primary_conflict}")

        return DramaticStateDelta(
            knowledge_delta=k_delta,
            relationship_shifts=rel_shifts,
            power_shift=p_shift,
            danger_level_delta=danger_delta,
            decisions_made=decisions,
            emotional_trajectory=f"{opening_state} -> {closing_state}",
        )

    @classmethod
    def _derive_epistemic_asymmetry(
        cls,
        listener_knowledge: str,
        active_chars: List[str],
        memory_context: Optional[Any],
        reveals: List[str],
    ) -> List[str]:
        """Detect and formalize contrasts between audience awareness and character ignorance."""
        asymmetries: List[str] = []
        if "dramatic irony" in listener_knowledge.lower() or "concealed" in listener_knowledge.lower():
            asymmetries.append(listener_knowledge)
        elif reveals and active_chars:
            asymmetries.append(
                f"Audience witnesses disclosure ({reveals[0]}) altering situational certainty for {active_chars[0]}"
            )

        if memory_context and hasattr(memory_context, "epistemic_constraints"):
            constraints = memory_context.epistemic_constraints
            for char in active_chars:
                unknowns = constraints.get(char, {}).get("UNKNOWN", [])
                if unknowns:
                    unk_sample = [str(u) for u in unknowns[:2] if len(str(u)) > 3]
                    if unk_sample:
                        asymmetries.append(
                            f"Character '{char}' acts under epistemic restriction: blind to {', '.join(unk_sample)}"
                        )
        return asymmetries

    @classmethod
    def _infer_narrative_mode_and_pov(
        cls,
        scene_text: str,
        active_chars: List[str],
    ) -> Tuple[str, NarrativeDistance, Optional[str]]:
        """Determine narrative perspective, distance, and focalizing character."""
        # Strip dialogue quotes to inspect narrative voice alone
        narrative_only = re.sub(r'["“][^"”]*["”]', '', scene_text)

        first_person_tokens = len(re.findall(r"\b(?:I|my|mine|we|our|मैंने|मुझे|हम|मेरा)\b", narrative_only, re.IGNORECASE))
        third_person_tokens = len(re.findall(r"\b(?:he|she|his|her|they|their|उसने|उसका|उसकी|वे|उनका)\b", narrative_only, re.IGNORECASE))

        pov_char = active_chars[0] if active_chars else None

        if first_person_tokens >= 1 and first_person_tokens >= third_person_tokens:
            return "first_person", "first_person_intimate", pov_char
        elif third_person_tokens > 0:
            return "third_person_limited", "close_third_person", pov_char
        return "third_person_omniscient", "objective_detached", None

    @classmethod
    def _detect_story_connections(
        cls,
        scene_text: str,
        memory_context: Optional[Any],
    ) -> List[StoryConnectionRecord]:
        """Link beats/scenes to long-range narrative arcs, setup, and motifs."""
        connections: List[StoryConnectionRecord] = []
        t_low = scene_text.lower()

        # Common motif seeds
        motifs = {
            "dagger": ("Ancient blade with arcane resonance", "motif_echo"),
            "key": ("Physical or symbolic unlocking device", "setup"),
            "prophecy": ("Fateful decree looming over characters", "foreshadowing"),
            "oath": ("Binding promise constraining future choices", "thematic_anchor"),
            "letter": ("Document holding concealed narrative truth", "callback"),
            "ring": ("Token of loyalty or ancient power", "motif_echo"),
            "कटाार": ("प्राचीन खंजर", "motif_echo"),
            "चाबी": ("रहस्यमयी कुंजी", "setup"),
            "शपथ": ("निर्णायक प्रतिज्ञा", "thematic_anchor"),
            "चिठ्ठी": ("गुप्त संदेश", "callback"),
        }

        for motif, (desc, conn_type) in motifs.items():
            if re.search(rf"\b{re.escape(motif)}\b", t_low):
                connections.append(
                    StoryConnectionRecord(
                        connection_type=conn_type,  # type: ignore
                        reference_target=f"motif_{motif}",
                        description=f"Echoes motif '{motif}': {desc}",
                        motif_name=motif,
                        confidence=0.88,
                    )
                )

        # Check MemoryStore plot threads if available
        if memory_context and hasattr(memory_context, "plot_threads"):
            for thread in getattr(memory_context, "plot_threads", []):
                t_name = getattr(thread, "title", getattr(thread, "name", ""))
                t_id = getattr(thread, "thread_id", getattr(thread, "id", "thread_ref"))
                if t_name and re.search(rf"\b{re.escape(t_name)}\b", t_low):
                    connections.append(
                        StoryConnectionRecord(
                            connection_type="foreshadowing",
                            reference_target=str(t_id),
                            description=f"Directly advances narrative thread: {t_name}",
                            confidence=0.92,
                        )
                    )

        return connections

