#!/usr/bin/env python3
"""
Audiobook Factory - Script Engine: Pass 2 Screenplay Editorial Cleaner.
Provides pronoun disambiguation, alias resolution, narration/dialogue separation,
and dramatic plan metadata attachment.
"""

from __future__ import annotations
import re
from typing import List, Dict, Any, Optional, Tuple

from audiobook_factory.script.normalizer import normalize_speech_text
from audiobook_factory.sanitizer import sanitize_screenplay_segment


def clean_screenplay_pass2(
    raw_items: List[Dict[str, Any]],
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
    memory_context: Optional[Any] = None,
    dramatic_plan: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Pass 2 (Alexandria Pattern): Two-pass pronoun disambiguation, alias resolution,
    unknown speaker fallback, text normalization, continuous 1-based indexing,
    and dramatic metadata enrichment from DramaticPlan.
    """
    alias_map = {}
    gender_map = {}
    if character_roster and "characters" in character_roster:
        chars = character_roster["characters"]
        if isinstance(chars, dict):
            for canon_name, details in chars.items():
                c_clean = canon_name.strip()
                alias_map[c_clean.lower()] = c_clean
                alias_map[c_clean.lower().replace("_", " ")] = c_clean
                alias_map[c_clean.lower().replace(" ", "_")] = c_clean
                if isinstance(details, dict):
                    gender_map[c_clean] = details.get("gender", "neutral").lower()
                    for alias in details.get("aliases", []):
                        if isinstance(alias, str) and alias.strip():
                            a_clean = alias.strip()
                            alias_map[a_clean.lower()] = c_clean
                            alias_map[a_clean.lower().replace("_", " ")] = c_clean
                            alias_map[a_clean.lower().replace(" ", "_")] = c_clean
        elif isinstance(chars, list):
            for c in chars:
                if isinstance(c, dict):
                    c_name = c.get("hindi_name") if is_hindi and c.get("hindi_name") else c.get("english_name", "")
                    if c_name:
                        c_clean = c_name.strip()
                        alias_map[c_clean.lower()] = c_clean
                        alias_map[c_clean.lower().replace("_", " ")] = c_clean
                        alias_map[c_clean.lower().replace(" ", "_")] = c_clean
                        gender_map[c_clean] = c.get("gender", "neutral").lower()
                        eng = c.get("english_name", "")
                        if eng:
                            e_clean = eng.strip()
                            alias_map[e_clean.lower()] = c_clean
                            alias_map[e_clean.lower().replace("_", " ")] = c_clean
                        for alias in c.get("aliases", []):
                            if isinstance(alias, str) and alias.strip():
                                a_clean = alias.strip()
                                alias_map[a_clean.lower()] = c_clean
                                alias_map[a_clean.lower().replace("_", " ")] = c_clean

    last_male_character = "Narrator"
    last_female_character = "Narrator"
    last_active_character = "Narrator"

    MALE_PRONOUNS = {
        "he", "him", "his", "himself", "the man", "the boy", "the lad", "his voice",
        "उसने", "वह", "उसका", "आदमी", "लड़के ने", "युवक ने"
    }
    FEMALE_PRONOUNS = {
        "she", "her", "hers", "herself", "the woman", "the girl", "the lady", "her voice",
        "लड़की", "महिला", "उसने (महिला)", "स्त्री"
    }

    final_script = []
    for idx, item in enumerate(raw_items, 1):
        speaker = item.get("speaker", "Narrator").strip()
        speaker = speaker.strip(" \"':()[]")
        speaker_lower = speaker.lower()

        # Robust alias matching
        if speaker_lower in alias_map:
            speaker = alias_map[speaker_lower]
        elif speaker_lower.replace("_", " ") in alias_map:
            speaker = alias_map[speaker_lower.replace("_", " ")]
        elif speaker_lower.replace(" ", "_") in alias_map:
            speaker = alias_map[speaker_lower.replace(" ", "_")]
        else:
            # Check parenthetical annotations e.g. "Hero (Warrior)" or "नायक (योद्धा)"
            m = re.search(r"\(([^)]+)\)", speaker)
            if m:
                inner = m.group(1).strip().lower()
                if inner in alias_map:
                    speaker = alias_map[inner]
                elif inner.replace("_", " ") in alias_map:
                    speaker = alias_map[inner.replace("_", " ")]
            if "(" in speaker and speaker.lower() not in alias_map:
                prefix = speaker.split("(")[0].strip().lower()
                if prefix in alias_map:
                    speaker = alias_map[prefix]
                elif prefix.replace("_", " ") in alias_map:
                    speaker = alias_map[prefix.replace("_", " ")]

        speaker_lower = speaker.lower().strip()

        # Disambiguate pronouns if LLM attributed dialogue to a pronoun
        if item.get("type") == "dialogue":
            if speaker_lower in MALE_PRONOUNS:
                speaker = last_male_character if last_male_character != "Narrator" else last_active_character
            elif speaker_lower in FEMALE_PRONOUNS:
                speaker = last_female_character if last_female_character != "Narrator" else last_active_character
            elif speaker_lower in ("unknown", "someone", "voice", "a voice", "stranger"):
                speaker = last_active_character

        # Dedicated action beat support: keep Foley speaker and action type intact
        is_action_beat = item.get("type") == "action" or speaker_lower == "foley"
        if is_action_beat:
            speaker = "Foley"
        elif not speaker or speaker_lower in ("narrator", "narration", "header", "chapter_header"):
            speaker = "Narrator"

        # Update active cast trackers
        if speaker not in ("Narrator", "Foley"):
            last_active_character = speaker
            g = gender_map.get(speaker, "neutral")
            if g == "male":
                last_male_character = speaker
            elif g == "female":
                last_female_character = speaker

        sanitized_item = sanitize_screenplay_segment(item, is_hindi)
        if not sanitized_item:
            continue

        cleaned_text = normalize_speech_text(sanitized_item.get("text", ""), is_hindi)
        if not cleaned_text:
            continue

        # Double-Safety Invariant: Auto-split any direct dialogue mistakenly retained in narration
        quote_matches = list(re.finditer(r'["“]([^"”]+)["”]', cleaned_text))
        if quote_matches and speaker == "Narrator":
            last_end = 0
            for qm in quote_matches:
                q_start, q_end = qm.span()
                pre_part = cleaned_text[last_end:q_start].strip()
                quote_val = qm.group(1).strip()
                post_snip = cleaned_text[q_end:q_end + 120]

                target_speaker = last_active_character if last_active_character != "Narrator" else "Narrator"
                for al, cn in alias_map.items():
                    if al in pre_part.lower() or al in post_snip.lower():
                        target_speaker = cn
                        break

                if pre_part:
                    final_script.append({
                        "index": len(final_script) + 1,
                        "type": "narration",
                        "speaker": "Narrator",
                        "text": pre_part,
                        "emotion": sanitized_item.get("emotion", "neutral"),
                        "pause_after_ms": 400,
                        "acoustic_env": sanitized_item.get("acoustic_env", "domestic_room"),
                    })

                final_script.append({
                    "index": len(final_script) + 1,
                    "type": "dialogue",
                    "speaker": target_speaker,
                    "text": quote_val,
                    "emotion": sanitized_item.get("emotion", "neutral"),
                    "pause_after_ms": 600,
                    "acting": sanitized_item.get("acting", {}),
                    "spatial": sanitized_item.get("spatial", {}),
                    "acoustic_env": sanitized_item.get("acoustic_env", "domestic_room"),
                })
                last_end = q_end

            remaining_txt = cleaned_text[last_end:].strip()
            tag_regexes = [
                r"^(?:,\s*)?(?:मिस्टर|मिसेज़|उसने|उन्होंने|वह)?[^।!?\.\n]+?(?:ने\s+(?:कहा|पूछा|बोला|लाड़ से कहा|हँसकर कहा)|said|replied|asked|muttered)[,\.\s।]*",
            ]
            for tr in tag_regexes:
                remaining_txt = re.sub(tr, "", remaining_txt, flags=re.IGNORECASE).strip()

            if remaining_txt:
                final_script.append({
                    "index": len(final_script) + 1,
                    "type": "narration",
                    "speaker": "Narrator",
                    "text": remaining_txt,
                    "emotion": sanitized_item.get("emotion", "neutral"),
                    "pause_after_ms": int(sanitized_item.get("pause_after_ms", 600)),
                    "acoustic_env": sanitized_item.get("acoustic_env", "domestic_room"),
                })
            continue

        seg_type = "action" if is_action_beat else sanitized_item.get("type", "narration")
        entry = {
            "index": len(final_script) + 1,
            "type": seg_type,
            "speaker": speaker,
            "text": cleaned_text,
            "emotion": sanitized_item.get("emotion", "neutral"),
            "pause_after_ms": int(sanitized_item.get("pause_after_ms", 600)),
        }
        for field in (
            "acting",
            "spatial",
            "acoustic_env",
            "sfx_cues",
            "music",
            "intensity_level",
            "pre_roll_breath_ms",
            "recommended_pronoun",
            "recommended_register",
            "memory_vocal_constraint",
            "scene_id",
            "beat_id",
            "dramatic_function",
            "character_objective",
            "actioning",
            "subtext",
            "subtext_confidence",
            "surface_emotion",
            "underlying_emotion",
            "tension_before",
            "tension_after",
            "listener_knowledge_state",
            "performance_priority",
            "dramatic_provenance",
            "causal_trigger",
            "consequence",
            "relationship_shift",
            "leverage_holder",
            "dramatic_irony",
            "blocking_directive",
            "narrative_mode",
            "narrative_distance",
            "story_connection",
            "conversational_dynamic",
            "is_interruption",
            "hesitation_pause_ms",
            "silence_intent",
        ):
            if field in sanitized_item:
                entry[field] = sanitized_item[field]

        # Automatic Narrative Mode & Turn Dynamic Detection
        if not entry.get("narrative_mode"):
            if seg_type == "narration":
                entry["narrative_mode"] = "narrator_exposition"
            elif seg_type == "dialogue":
                txt_check = cleaned_text.lower()
                _dev_b = r"(?:(?<=[^a-zA-Z\u0900-\u097F])|^)"
                _dev_be = r"(?=[^a-zA-Z\u0900-\u097F]|$)"
                _is_reported = (
                    re.search(r'\b(?:said that|told them that)\b', cleaned_text, re.IGNORECASE)
                    or re.search(
                        _dev_b + r"(?:बता रहा था कि|कहा कि)" + _dev_be,
                        cleaned_text,
                        re.UNICODE,
                    )
                )
                if "(मन में:" in cleaned_text or "binaural_whisper" in str(entry.get("acoustic_env", "")) or "[whispers] (" in cleaned_text:
                    entry["narrative_mode"] = "internal_monologue"
                elif _is_reported:
                    entry["narrative_mode"] = "reported_speech"
                else:
                    entry["narrative_mode"] = "direct_dialogue"

        if entry.get("type") == "dialogue":
            # Check for interruptions (trailing dashes)
            if cleaned_text.rstrip().endswith(("--", "—", "-")):
                entry["is_interruption"] = True
                if not entry.get("conversational_dynamic"):
                    entry["conversational_dynamic"] = "interruption"
            # Check for hesitation markers (ellipses)
            if "..." in cleaned_text or "…" in cleaned_text:
                if entry.get("hesitation_pause_ms") is None:
                    entry["hesitation_pause_ms"] = 350
                if not entry.get("conversational_dynamic"):
                    entry["conversational_dynamic"] = "hesitation"

        if memory_context is not None and hasattr(memory_context, "apply_performance_guidance_to_segment"):
            prev_dialogue_speaker = None
            for prev_seg in reversed(final_script):
                prev_sp = prev_seg.get("speaker", "Narrator")
                if prev_sp not in ("Narrator", "Foley", speaker):
                    prev_dialogue_speaker = prev_sp
                    break
            entry = memory_context.apply_performance_guidance_to_segment(
                entry,
                target_speaker=prev_dialogue_speaker,
            )

        final_script.append(entry)

    # Attach dramatic plan metadata if not already attached
    if dramatic_plan and getattr(dramatic_plan, "scenes", None):
        all_beats: List[Tuple[Any, Any]] = []
        for sc in dramatic_plan.scenes:
            for bt in sc.beats:
                all_beats.append((sc, bt))

        num_segs = len(final_script)
        num_bts = len(all_beats)
        if num_bts > 0 and num_segs > 0:
            segs_per_beat = max(1, num_segs // num_bts)
            for s_idx, entry in enumerate(final_script):
                b_idx = min(s_idx // segs_per_beat, num_bts - 1)
                sc, bt = all_beats[b_idx]
                if not entry.get("scene_id"):
                    entry["scene_id"] = sc.scene_id
                if not entry.get("beat_id"):
                    entry["beat_id"] = bt.beat_id
                if not entry.get("dramatic_function"):
                    entry["dramatic_function"] = bt.dramatic_function
                if entry.get("speaker") not in ("Narrator", "Foley") and bt.objective:
                    if not entry.get("character_objective"):
                        entry["character_objective"] = bt.objective.immediate_goal
                    if not entry.get("actioning"):
                        entry["actioning"] = bt.objective.actioning
                if not entry.get("surface_emotion"):
                    entry["surface_emotion"] = entry.get("emotion") or bt.surface_emotion
                if not entry.get("underlying_emotion") and bt.underlying_emotion:
                    entry["underlying_emotion"] = bt.underlying_emotion
                if not entry.get("subtext") and bt.subtext:
                    entry["subtext"] = bt.subtext
                    entry["subtext_confidence"] = bt.subtext_confidence
                if entry.get("tension_before") is None:
                    entry["tension_before"] = bt.tension_before
                if entry.get("tension_after") is None:
                    entry["tension_after"] = bt.tension_after
                if not entry.get("listener_knowledge_state") and sc.listener_knowledge_state:
                    entry["listener_knowledge_state"] = sc.listener_knowledge_state
                if not entry.get("performance_priority") or entry.get("performance_priority") == "standard":
                    entry["performance_priority"] = bt.performance_priority

                # Attach refined dramatic capabilities
                if not entry.get("causal_trigger") and bt.causal_trigger:
                    entry["causal_trigger"] = bt.causal_trigger
                if not entry.get("consequence") and bt.consequence:
                    entry["consequence"] = bt.consequence
                if not entry.get("relationship_shift") and bt.relationship_shift:
                    entry["relationship_shift"] = bt.relationship_shift.description
                if not entry.get("leverage_holder") and bt.leverage_holder:
                    entry["leverage_holder"] = bt.leverage_holder
                if not entry.get("dramatic_irony") and bt.dramatic_irony:
                    entry["dramatic_irony"] = bt.dramatic_irony
                if not entry.get("blocking_directive") and bt.blocking:
                    entry["blocking_directive"] = bt.blocking.action_description
                if not entry.get("story_connection") and bt.story_connection:
                    entry["story_connection"] = bt.story_connection.description
                if not entry.get("conversational_dynamic") and bt.conversational_dynamic:
                    entry["conversational_dynamic"] = bt.conversational_dynamic.dynamic_type
                if not entry.get("silence_intent") and bt.silence_intent:
                    entry["silence_intent"] = bt.silence_intent.purpose
                if not entry.get("narrative_distance") and sc.narrative_distance:
                    entry["narrative_distance"] = sc.narrative_distance

    return final_script
