"""
Audiobook Factory - Agent 3: Master Foley & Micro-Life Artist.
Spots both explicit physical action events (doors, blades, impacts) and implicit living-world micro-foley
(wooden tankard clatter, ale pouring, cloth/leather rustle, fireplace crackle, chair scuffs).
Eliminates dead acoustic voids and grounds characters in tactile physical reality.
"""

from __future__ import annotations
import json
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.llm_client import call_gemini
from audiobook_factory.model_manager import TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing
from .showrunner_agent import ShowrunnerPlan


class FoleyEventDirective(BaseModel):
    """Rich foley directive emitted by the Master Foley Artist."""
    model_config = ConfigDict(extra="ignore")

    segment_index: int = Field(..., ge=1, description="1-based segment index where sound triggers")
    action_verb: str = Field(..., description="Action identifier (e.g. 'tankard_slam', 'ale_pour', 'sword_draw', 'cloth_rustle', 'chair_creak', 'coin_drop', 'boots_flagstone')")
    object_material: str = Field(default="wood", description="'wood', 'pewter', 'metal', 'leather', 'cloth', 'stone', 'glass', 'water', 'fire'")
    trigger_mode: Literal["explicit_anchor", "implicit_scene_physics", "atmospheric_event"] = Field(
        default="implicit_scene_physics",
        description="Whether sound is anchored to a literal word or generated from implicit scene context"
    )
    beat_timing: Literal["pre_speech", "mid_speech_pause", "post_speech", "under_speech"] = Field(
        default="post_speech",
        description="Temporal placement relative to spoken dialogue delivery"
    )
    relative_position: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Fractional timeline offset within the segment duration (0.0=start, 1.0=end)"
    )
    anchor_word: Optional[str] = Field(default="", description="Word in dialogue or narration anchoring the sound if explicit")
    gain_dbfs: float = Field(default=-18.0, ge=-36.0, le=-10.0, description="Calibrated sound level")
    pan: float = Field(default=0.0, ge=-0.8, le=0.8, description="Stereo panning (-0.8 left to +0.8 right)")
    is_micro_foley: bool = Field(default=True, description="True if tactile ambient micro-movement (drink, clothing, chair), False if major action")
    foley_type: str = Field(default="micro", description="'macro' for primary actions, 'micro' for tactile living-world physics")
    duration_sec: Optional[float] = Field(default=None, description="Desired duration in seconds (optional)")
    description: str = Field(default="", description="Artistic description of physical event")
    dramatic_justification: str = Field(default="", description="Artistic rationale for physical action")


class MicroFoleyPlan(BaseModel):
    """Full chapter collection of macro and micro foley events."""
    model_config = ConfigDict(extra="ignore")

    chapter_id: str
    events: List[FoleyEventDirective] = Field(default_factory=list)


def build_scene_physics_context_matrix(
    location_setting: str,
    environment_type: str,
    era: str,
    sonic_bible: Optional[Dict[str, Any]] = None,
    book_dna: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Constructs a rich tactile scene physics matrix dynamically derived from the act's
    environment, setting, era, sonic_bible, and book_dna. Ensures LLM spots living-world tactile presence
    even when prose contains zero explicit object mentions.
    Universal & Novel-Agnostic.
    """
    loc_lower = (location_setting or "").lower()
    env_lower = (environment_type or "").lower()
    combined = f"{loc_lower} {env_lower}"

    custom_props = ""
    if sonic_bible and sonic_bible.get("foley_palette"):
        custom_props = f"\n- Custom Production Sound Palette: {json.dumps(sonic_bible.get('foley_palette'))}"

    if any(k in combined for k in ("rural", "village", "veranda", "courtyard", "patio", "field", "farm", "khet", "aangan")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Rural / Village / Rustic Living Physics):\n"
            "- Available Props & Surfaces: Woven hemp charpai / cots, baked earthenware (matka, surahi, kulhad), brass thali, wooden cartwheels, dried thatch, mud-plastered floor, cow dung courtyard floor, hookahs / chillums, cotton dhotis and kurtas.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Barefoot shifting on dusty earth, dry cough or clearing throat, placing clay cup on wicker table, adjusting cotton shawl.\n"
            "  * mid_speech_pause: Inhaling from clay pipe, creak of charpai ropes as character shifts weight, sudden rustle of dry leaves, cattle bell in distance.\n"
            "  * post_speech: Drawing deep breath, tapping brass cup on wooden bench, standing up with charpai creak, spitting dust onto earth.\n"
            "  * under_speech: Dry afternoon wind rustling thatch, faint clink of brass utensils, embers of clay hearth."
            f"{custom_props}"
        )
    elif any(k in combined for k in ("office", "modern", "boardroom", "corridor", "flat", "apartment", "city", "corporate", "desk")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Modern Contemporary / Office / Urban Living Physics):\n"
            "- Available Props & Surfaces: Polished desks, ergonomic mesh/leather chairs, ceramic coffee mugs, ballpoint pens, keyboards, smartphone screens, glass windows, linoleum / carpeted floors.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Clicking pen top, tapping fingers on laminate desk, setting ceramic mug onto coaster, shifting in swivel chair.\n"
            "  * mid_speech_pause: Swallowing lukewarm coffee, typing two quick keystrokes, deep breath through nostrils, shuffling paper printouts.\n"
            "  * post_speech: Leaning back with leather chair groan, placing phone face down with muted click, closing laptop lid.\n"
            "  * under_speech: Subtle low hum of fluorescent lights, distant muffled city street or HVAC air circulation."
            f"{custom_props}"
        )
    elif any(k in combined for k in ("tavern", "inn", "pub", "bar", "kitchen", "dining", "hall", "taproom")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Tavern / Inn / Interior Gathering):\n"
            "- Available Props & Surfaces: Heavy oak tables, rough wooden benches/stools, pewter & wood ale tankards, ceramic bowls, bread knives, iron fire poker, clay pipes.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Heavy mug set down on wood before answering, scraping bench legs, clearing throat, resting elbows on timber.\n"
            "  * mid_speech_pause: Taking a swallow of ale, pipe puff, hearth log crackle/pop during silence, plate clatter.\n"
            "  * post_speech: Long drink, thumping mug onto table, leaning back (creaking wood), tossing copper coin onto table.\n"
            "  * under_speech: Gentle crackle of fireplace hearth, subtle shift in wooden chair, faint tankard slide."
            f"{custom_props}"
        )
    elif any(k in combined for k in ("stone", "dungeon", "crypt", "castle", "fortress", "tower", "cellar", "vault", "throne")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Stone Chamber / Fortress / Crypt):\n"
            "- Available Props & Surfaces: Cold granite flagstones, iron torch sconces, heavy iron keys, chain links, scabbards, steel armor plates, leather belts, heavy oak doors.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Boots scuffing on cold stone, leather glove tightening on pommel, shifting heavy armor plates.\n"
            "  * mid_speech_pause: Water drop echoing on stone, torch hiss, armor squeak on shift of posture.\n"
            "  * post_speech: Deep exhale through nose, scabbard slapping thigh, footsteps echoing into distance.\n"
            "  * under_speech: Subtle low reverberant room reflections, torch crackle, armor buckle settling."
            f"{custom_props}"
        )
    elif any(k in combined for k in ("forest", "woods", "wilderness", "camp", "road", "swamp", "marsh", "mountain")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Wilderness / Forest / Road / Camp):\n"
            "- Available Props & Surfaces: Pine needles, dry twigs, mud, river stones, campfire embers, canvas tents, horse leather, travel cloaks, water skins.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Boots crunching on twigs/needles, adjusting wet travel cloak, horse snorting.\n"
            "  * mid_speech_pause: Campfire pop/spark, wind rustling canopy, water skin slosh on drink.\n"
            "  * post_speech: Sheathing knife into leather, spitting into dirt, stirrup jingle, sigh.\n"
            "  * under_speech: Gentle breeze through branches, subtle wet leather creak, embers glowing."
            f"{custom_props}"
        )
    elif any(k in combined for k in ("train", "rail", "carriage", "compartment", "platform", "station")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Train / Railway Compartment / Transit):\n"
            "- Available Props & Surfaces: Polished brass fittings, velvet cushions, wooden compartment doors, luggage leather, glass windows, rattling teacups on table, ticket stubs, pocket watches.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Shifting posture against train sway, tapping pocket watch, sliding brass door latch.\n"
            "  * mid_speech_pause: Wheel rhythmic clack on track during pause, teacup clinking on saucer, distant train whistle.\n"
            "  * post_speech: Leaning toward window, pulling curtain, exhaling against train hum.\n"
            "  * under_speech: Continuous steady train track rail rhythm, gentle vibration of carriage."
            f"{custom_props}"
        )
    elif any(k in combined for k in ("ship", "boat", "sea", "ocean", "deck", "cabin", "river")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Ship / Boat / Maritime Setting):\n"
            "- Available Props & Surfaces: Salt-weathered deck timbers, hemp rope rigging, brass compass, oil lamps, canvas sails, wooden oars, iron railings.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Grabbing deck railing, wiping spray from face, coil of rope shifting.\n"
            "  * mid_speech_pause: Heavy creak of timber hull, water lap against wood, wind flapping sailcloth.\n"
            "  * post_speech: Stepping down companionway, lighting pipe with match flick, looking out to sea.\n"
            "  * under_speech: Ocean water swelling against hull, distant wind whistling through ropes."
            f"{custom_props}"
        )
    elif any(k in combined for k in ("cyber", "sci", "space", "terminal", "station", "bridge", "lab")):
        return (
            "TACTILE SCENE PHYSICS MATRIX (Sci-Fi / Spacecraft / High-Tech Lab):\n"
            "- Available Props & Surfaces: Metallic deck plating, polymer consoles, pneumatic sliding doors, holographic touchpads, pressurized suits, synth-fabric jackets.\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Keypad chirp, boots clanging on metal grate, adjusting comm earpiece.\n"
            "  * mid_speech_pause: Soft cooling fan hum, console status ping, pneumatic valve pressure release.\n"
            "  * post_speech: Holstering sidearm with magnetic click, tapping touch display, turning chair.\n"
            "  * under_speech: Low-frequency reactor core hum, subtle electronics air circulation."
            f"{custom_props}"
        )
    else:
        return (
            "TACTILE SCENE PHYSICS MATRIX (General Dramatic Environment):\n"
            "- Available Props & Surfaces: Furniture, doors, cloth/clothing, footwear, small personal props (cups, coins, paper/books, cutlery).\n"
            "- Character Physical Micro-Beats:\n"
            "  * pre_speech: Shifting weight, scuffing shoes, setting down cup/prop before replying.\n"
            "  * mid_speech_pause: Brief pause marked by chair creak, sharp inhale, or small prop adjustment.\n"
            "  * post_speech: Turning away, closing book/door, sighing, settling into posture.\n"
            "  * under_speech: Subtle room tone physics, clothing rustle on movement."
            f"{custom_props}"
        )


from concurrent.futures import ThreadPoolExecutor, as_completed


class MicroFoleyAgent:
    """Specialist Master Foley & Micro-Life LLM Agent with Implicit Scene Physics."""

    def __init__(self, model: Optional[str] = None):
        self.model = model

    @staticmethod
    def _audit_foley_density_and_fill_voids(
        events: List[FoleyEventDirective],
        script_segments: List[Dict[str, Any]],
        showrunner_plan: ShowrunnerPlan,
        era: str = "MEDIEVAL_FANTASY",
    ) -> List[FoleyEventDirective]:
        """
        Zero Dead Voids Guarantee:
        Audits foley distribution across the chapter timeline. If any acoustic void
        exceeds 8 segments (~25-35 seconds of silence), seeds organic, tactile living-world
        micro-foley cues (cloth rustle, weight shift, chair creak, soft step) matching the act's environment.
        Guarantees Audible & GraphicAudio benchmark density without anechoic dead zones.
        """
        if not script_segments:
            return events

        total_segs = len(script_segments)
        existing_indices = {e.segment_index for e in events}
        filled_events = list(events)

        act_for_seg = {}
        for act in showrunner_plan.acts:
            for s_idx in range(act.start_segment, act.end_segment + 1):
                act_for_seg[s_idx] = act

        sorted_indices = sorted(list(existing_indices))
        intervals = []
        if not sorted_indices:
            intervals.append((1, total_segs))
        else:
            if sorted_indices[0] > 8:
                intervals.append((1, sorted_indices[0]))
            for i in range(len(sorted_indices) - 1):
                if sorted_indices[i + 1] - sorted_indices[i] > 8:
                    intervals.append((sorted_indices[i], sorted_indices[i + 1]))
            if total_segs - sorted_indices[-1] > 8:
                intervals.append((sorted_indices[-1], total_segs))

        for start_idx, end_idx in intervals:
            curr = start_idx + 5
            while curr < end_idx:
                if curr not in existing_indices and 1 <= curr <= total_segs:
                    act = act_for_seg.get(curr)
                    env = (act.environment_type if act else "").lower()
                    loc = (act.location_setting if act else "").lower()
                    combined = f"{env} {loc}"

                    if any(k in combined for k in ("rural", "village", "farm", "courtyard")):
                        verb = "charpai_creak" if (curr % 3 == 0) else ("cotton_rustle" if (curr % 3 == 1) else "barefoot_dust_step")
                        mat = "cloth" if "rustle" in verb else ("wood" if "charpai" in verb else "stone")
                    elif any(k in combined for k in ("office", "modern", "city")):
                        verb = "chair_swivel" if (curr % 3 == 0) else ("paper_turn" if (curr % 3 == 1) else "shoe_scuff")
                        mat = "leather" if "chair" in verb else "wood"
                    elif any(k in combined for k in ("stone", "crypt", "castle", "fortress")):
                        verb = "boots_flagstone" if (curr % 3 == 0) else ("leather_creak" if (curr % 3 == 1) else "armor_shift")
                        mat = "stone" if "boots" in verb else ("leather" if "leather" in verb else "metal")
                    elif any(k in combined for k in ("forest", "woods", "camp", "road")):
                        verb = "twigs_crunch" if (curr % 3 == 0) else ("cloak_rustle" if (curr % 3 == 1) else "dirt_step")
                        mat = "wood" if "twigs" in verb else ("cloth" if "cloak" in verb else "stone")
                    else:
                        verb = "cloth_rustle" if (curr % 2 == 0) else "chair_creak"
                        mat = "cloth" if "cloth" in verb else "wood"

                    filled_events.append(
                        FoleyEventDirective(
                            segment_index=curr,
                            action_verb=verb,
                            object_material=mat,
                            trigger_mode="implicit_scene_physics",
                            beat_timing="pre_speech" if curr % 2 == 0 else "under_speech",
                            relative_position=0.3,
                            anchor_word="",
                            gain_dbfs=-26.0,
                            pan=0.0,
                            is_micro_foley=True,
                            foley_type="micro",
                            duration_sec=0.6,
                            description="Organic living-world tactile micro-action bridging acoustic void",
                            dramatic_justification="Density protection preventing anechoic silence void",
                        )
                    )
                    existing_indices.add(curr)
                curr += 6

        filled_events.sort(key=lambda x: x.segment_index)
        return filled_events

    def _spot_act_foley(
        self,
        act: Any,
        act_segs: List[Dict[str, Any]],
        script_segments: List[Dict[str, Any]],
        era: str,
        framing: str,
        sonic_bible: Optional[Dict[str, Any]] = None,
        book_dna: Optional[Dict[str, Any]] = None,
    ) -> List[FoleyEventDirective]:
        lines = []
        for s in act_segs:
            s_idx = s.get("index", 1)
            spk = s.get("speaker", "Narrator")
            styp = (s.get("type") or "narration").upper()
            txt = (s.get("text") or "").strip()
            lines.append(f"[{s_idx:03d} | {styp} | {spk}]: {txt}")
        act_text = "\n".join(lines)

        physics_matrix = build_scene_physics_context_matrix(
            location_setting=act.location_setting,
            environment_type=act.environment_type,
            era=era,
            sonic_bible=sonic_bible,
            book_dna=book_dna,
        )

        sys_prompt = (
            "You are an elite Hollywood Foley Artist and Sound Designer (GraphicAudio & Audible Full-Cast benchmark). "
            f"{framing}"
            f"Setting: {act.location_setting} (Era: {era}, Environment: {act.environment_type}).\n\n"
            f"{physics_matrix}\n\n"
            "CRITICAL HOLLYWOOD LIVING-WORLD MANDATE:\n"
            "Do NOT limit sound design to words explicitly spoken or narrated in text! "
            "In real life and top-tier audio dramas, living physical actions happen continuously around dialogue:\n"
            "- A speaker sets down their mug with a wooden thud before replying ('pre_speech').\n"
            "- A listener's chair creaks or clothes rustle as they lean in during a dramatic pause ('mid_speech_pause').\n"
            "- A character takes a swallow, thumps a cup, tosses a coin, or taps their sword hilt after speaking ('post_speech').\n"
            "- The hearth fire crackles or armor rustles softly beneath dialogue ('under_speech').\n\n"
            "For implicit actions, set trigger_mode='implicit_scene_physics' and leave anchor_word=''. "
            "Only use trigger_mode='explicit_anchor' when a specific object (e.g. 'sword', 'door') is literally spoken in text.\n"
            "Target density: Aim for 10 to 25 organic, tactile cues per act so the scene feels physically alive with texture."
        )

        prompt = f"""Act {act.act_index}: {act.act_title} (Segments {act.start_segment} to {act.end_segment})
Location: {act.location_setting} ({act.environment_type})
Dramatic Subtext: {act.emotional_subtext}

ACT SCREENPLAY:
\"\"\"
{act_text}
\"\"\"

Return a JSON array of foley cues for this act. Include BOTH major actions and implicit living-world physics:
[
  {{
    "segment_index": {act.start_segment},
    "action_verb": "tankard_thump | ale_pour | cloth_rustle | chair_creak | sword_draw | coin_drop | fire_crackle | boots_flagstone",
    "object_material": "pewter | wood | leather | cloth | metal | stone | water | fire",
    "trigger_mode": "implicit_scene_physics | explicit_anchor",
    "beat_timing": "pre_speech | mid_speech_pause | post_speech | under_speech",
    "relative_position": 0.5,
    "anchor_word": "",
    "gain_dbfs": -18.0,
    "pan": -0.2,
    "is_micro_foley": true,
    "foley_type": "micro",
    "duration_sec": 0.8,
    "description": "Character sets down heavy mug on table before speaking",
    "dramatic_justification": "Physical punctuation of disagreement"
  }}
]
"""
        act_events: List[FoleyEventDirective] = []
        try:
            res = call_gemini(
                prompt=prompt,
                system_instruction=sys_prompt,
                task_type=TaskType.SOUND_DESIGN,
                response_mime_type="application/json",
                temperature=0.60,
                max_output_tokens=16384,
                thinking_budget=512,
                model=self.model,
                max_retries=8,
            )
            if isinstance(res, list):
                for item in res:
                    try:
                        directive = FoleyEventDirective.model_validate(item)
                        if 1 <= directive.segment_index <= len(script_segments):
                            act_events.append(directive)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"  [!] MicroFoleyAgent LLM call warning for Act {act.act_index}: {e}")
        return act_events

    def spot_foley_events(
        self,
        showrunner_plan: ShowrunnerPlan,
        script_segments: List[Dict[str, Any]],
        era: str = "MEDIEVAL_FANTASY",
        title: str = "",
        author: str = "",
        sonic_bible: Optional[Dict[str, Any]] = None,
        book_dna: Optional[Dict[str, Any]] = None,
    ) -> MicroFoleyPlan:
        """
        Executes concurrent hierarchical foley spotting across all acts.
        Processes each act cleanly in parallel with rich Implicit Scene Physics so zero text is truncated
        and living world physics trigger naturally without requiring literal word anchors.
        Applies Zero Dead Voids density protection to guarantee no gap exceeds 8 segments.
        """
        logger.info(f"[*] MicroFoleyAgent: Spotting macro & implicit living-world foley across {len(script_segments)} segments in {len(showrunner_plan.acts)} acts...")
        framing = get_dramatic_fiction_framing(title, author)

        seg_by_idx = {s.get("index", idx + 1): s for idx, s in enumerate(script_segments)}
        all_events: List[FoleyEventDirective] = []

        act_tasks = []
        for act in showrunner_plan.acts:
            act_segs = [
                seg_by_idx[i]
                for i in range(act.start_segment, act.end_segment + 1)
                if i in seg_by_idx
            ]
            if act_segs:
                act_tasks.append((act, act_segs))

        # Concurrently process all acts across the 100+ key pool
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(act_tasks)))) as executor:
            futures = [
                executor.submit(self._spot_act_foley, act, act_segs, script_segments, era, framing, sonic_bible, book_dna)
                for act, act_segs in act_tasks
            ]
            for future in as_completed(futures):
                try:
                    events = future.result()
                    all_events.extend(events)
                except Exception as e:
                    logger.warning(f"  [!] Act foley spotting worker notice: {e}")

        # Audit density and fill any dead voids > 8 segments
        all_events = self._audit_foley_density_and_fill_voids(
            events=all_events,
            script_segments=script_segments,
            showrunner_plan=showrunner_plan,
            era=era,
        )

        all_events.sort(key=lambda x: x.segment_index)
        logger.info(f"[+] MicroFoleyAgent: Successfully spotted {len(all_events)} foley cues across the chapter.")
        return MicroFoleyPlan(chapter_id=showrunner_plan.chapter_id, events=all_events)
