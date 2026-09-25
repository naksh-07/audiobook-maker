#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.1: Screenplay Script Builder & Speech Normalizer.
Converts raw novel prose (English or Hindi) into an annotated Screenplay Script JSON.
Handles dialogue vs. narration segmentation, text normalization, and pause timing.
"""

import os
import re
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


def normalize_speech_text(text: str, is_hindi: bool = False) -> str:
    """Normalize symbols, abbreviations, and numbers for natural TTS reading."""
    if not text:
        return ""

    text = text.strip()

    # Universal symbol replacements
    symbols = {
        "&": " and " if not is_hindi else " और ",
        "%": " percent" if not is_hindi else " प्रतिशत",
        "$": " dollars " if not is_hindi else " डॉलर ",
        "₹": " rupees " if not is_hindi else " रुपये ",
        "@": " at ",
        "#": " number " if not is_hindi else " नंबर ",
        "+": " plus " if not is_hindi else " प्लस ",
        "=": " equals " if not is_hindi else " बराबर ",
    }
    for sym, word in symbols.items():
        text = text.replace(sym, word)

    if not is_hindi:
        # Common English honorifics and abbreviations
        abbrevs = {
            r"\bMr\.\s*": "Mister ",
            r"\bMrs\.\s*": "Missus ",
            r"\bMs\.\s*": "Miss ",
            r"\bDr\.\s*": "Doctor ",
            r"\bProf\.\s*": "Professor ",
            r"\bSt\.\s*": "Saint ",
            r"\bvs\.\s*": "versus ",
            r"\betc\.\s*": "et cetera ",
            r"\bi\.e\.\s*": "that is ",
            r"\be\.g\.\s*": "for example ",
        }
        for pat, repl in abbrevs.items():
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # Strip formatting artifacts
    text = re.sub(r"[\*\_~`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_narrator_script(chapter_text: str, is_hindi: bool = False) -> List[Dict[str, Any]]:
    """
    Standard Audiobook Mode: Groups text into optimal speech chunks (200 - 500 words).
    Maintains dramatic pauses at paragraph boundaries and scene breaks.
    """
    paragraphs = chapter_text.split("\n\n")
    script = []
    chunk_index = 1

    current_chunk = []
    current_words = 0

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        # Skip chapter headers like "# Chapter 1"
        if p.startswith("#"):
            header_text = p.lstrip("#").strip()
            script.append({
                "index": chunk_index,
                "type": "chapter_header",
                "speaker": "Narrator",
                "text": normalize_speech_text(header_text, is_hindi),
                "emotion": "neutral",
                "pause_after_ms": 1200,
            })
            chunk_index += 1
            continue

        # Scene breaks
        if p in ("---", "* * *", "***", "— — —"):
            if current_chunk:
                script.append({
                    "index": chunk_index,
                    "type": "narration",
                    "speaker": "Narrator",
                    "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
                    "emotion": "neutral",
                    "pause_after_ms": 800,
                })
                chunk_index += 1
                current_chunk = []
                current_words = 0
            continue

        words = len(p.split())

        # If adding this paragraph exceeds ~350 words, flush the chunk
        if current_words + words > 350 and current_chunk:
            script.append({
                "index": chunk_index,
                "type": "narration",
                "speaker": "Narrator",
                "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
                "emotion": "neutral",
                "pause_after_ms": 600,
            })
            chunk_index += 1
            current_chunk = [p]
            current_words = words
        else:
            current_chunk.append(p)
            current_words += words

    if current_chunk:
        script.append({
            "index": chunk_index,
            "type": "narration",
            "speaker": "Narrator",
            "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
            "emotion": "neutral",
            "pause_after_ms": 1000,
        })

    return script


def _parse_dramatized_chunk_llm(
    chunk_text: str,
    preceding_context: str = "",
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
    api_key: str = "",
    model: str = "gemini-flash-lite-latest",
    max_retries: int = 3,
    dramatic_context: str = "",
) -> List[Dict[str, Any]]:
    """Helper to parse a single chunk of chapter text into screenplay JSON."""
    import json
    import time
    import urllib.request
    import urllib.error
    from audiobook_factory.key_manager import get_persistent_key_pool
    from audiobook_factory.cadence import get_stealth_sdk_headers

    pool = get_persistent_key_pool()

    sys_prompt = (
        "You are a Hollywood Audio Drama Director (GraphicAudio / BBC Radio 4 / HBO standard). "
        "Convert this book chapter scene into an annotated multi-cast screenplay with deep cinematic audio direction.\n\n"
        "Core Dramaturgy Invariants:\n"
        "1. UNFILTERED ADULT DIALOGUE & DIRTY BANTER MANDATE: Never sanitize, soften, or omit coarse curses ('गांड', 'भोसड़ीके', 'लंड', 'रांड', 'मादरचोद'), "
        "tavern obscenities, or raw intimate bedroom dirty talk ('चोदना', 'मसलना', 'लंड', 'चूत', 'गांड'). Preserve 100% of explicit dramatic truth.\n"
        "2. MULTI-CAST ATTRIBUTION & CANONICAL SPEAKER MANDATE: Split into narration segments and character dialogue segments. "
        "Attribute each dialogue to the correct canonical character by their English canonical name from Known Canon Characters (e.g. 'Hero', NOT transliterations or nicknames). "
        "Use 'Narrator' for narration and 'Foley' for action beats. Never invent new aliases, and never assign pronouns ('उसने', 'वह', 'he', 'she') as the speaker name. "
        "Remove redundant dialogue tags like 'he said', 'she replied', 'उसने कहा' when spoken by the character.\n"
        "3. NEURAL VOCAL TAGS: Gemini 3.1 Flash TTS is steered using inline English audio tags in square brackets. Prepend vocal tags directly inside the 'text' field "
        "when dialogue or dramatic narration demands it: `[whispers]`, `[shouting]`, `[cold menace]`, `[intimate, breathy]`, `[trembling voice]`, `[sighs]`, "
        "`[gasp]`, `[growl]`, `[groan]`, `[spits]`, `[bellowing rage]`, `[bellowing battlecry]`, `[combat strain]`, `[guttural grunt on blade deflect]`, "
        "`[choked gasp]`, `[ragged heaving pant]`, `[breathless_exhaustion]`, `[slow motion]`, `[mocking chuckle]`. Do NOT emit non-vocal action tags in text.\n"
        "4. CYNICAL PROTAGONIST GRUNT ENGINE & PROSODY: When a brooding, cynical protagonist reacts with skepticism, weary resignation, or menacing brevity, "
        "prepend `[growl] हूँ...` or `[sighs] हम्म...` and set 'pause_after_ms' to 1000-1400ms to enforce the iconic 1.2s pregnant pause prosody.\n"
        "5. DURAANGI ZUBAAN (INNER MONOLOGUES): When a character thinks an unfiltered thought or aside (contrasting with polite outward speech), "
        "tag the text with `[whispers] (मन में: ...)` and set spatial.proximity: 'intimate_close' and acoustic_env: 'binaural_whisper'.\n"
        "6. INTIMATE SCENES & ASMR STAGING: For romantic, sensual, erotic, or dirty bedroom scenes, pair raw passion with "
        "`[whispers]` or `[intimate, breathy]` tags, spatial.proximity: 'intimate_close', spatial.pan: 0.0, intensity_level: 'low', "
        "pre_roll_breath_ms: 200-250, and music.ducking_db: -22.0 ('The Erotic Silence'). Use ellipses ('...') for breathless pauses. "
        "Never censor dirty talk or physical passion during explicit encounters.\n"
        "7. TAVERN SHOCK BEAT & COMBAT CHOREOGRAPHY: When a climactic death threat or filthy curse drops in a tavern, set pause_after_ms: 800-1200ms "
        "with a solitary coin_clink or tankard_slam cue for an acoustic shock drop. "
        "For physical combat (sword parries, shield bashes, bone crunches, body slams), emit dedicated segments with type: 'action', speaker: 'Foley', text: '[ACTION]' "
        "and set 'pause_after_ms' to 800-1500ms to allocate speech-free acoustic real estate for the 3-layer combat impact. "
        "DUAL-PERSPECTIVE SPATIAL STAGING: Pan Attacker actions/vocals Left (-0.6), Defender parries/vocals Right (+0.6), and Clash points / fatal strikes Dead Center (0.0). "
        "Set intensity_level: 'explosive' for heavy lethal strikes or concussion shockwaves.\n"
        "8. For EVERY segment, assign audio direction: acting delivery & pacing, spatial stereo panning, acoustic environment, inline Foley SFX cues, and musical mood."
    )

    roster_hint = ""
    if character_roster:
        chars = character_roster.get("characters", {})
        formatted_chars = []
        if isinstance(chars, dict):
            for cname, details in chars.items():
                if cname in ("Narrator", "Foley"):
                    continue
                gender = details.get("gender", "neutral") if isinstance(details, dict) else "neutral"
                aliases = details.get("aliases", []) if isinstance(details, dict) else []
                alias_str = f", aliases: {', '.join(aliases[:4])}" if aliases else ""
                formatted_chars.append(f"{cname} [{gender}{alias_str}]")
        elif isinstance(chars, list):
            for c in chars:
                if isinstance(c, dict):
                    cname = c.get("english_name", "")
                    if cname and cname not in ("Narrator", "Foley"):
                        gender = c.get("gender", "neutral")
                        aliases = c.get("aliases", [])
                        alias_str = f", aliases: {', '.join(aliases[:4])}" if aliases else ""
                        formatted_chars.append(f"{cname} [{gender}{alias_str}]")
        if formatted_chars:
            roster_hint = (
                "\nKnown Canon Characters in Project (Use canonical English name as 'speaker'):\n"
                + "\n".join(f"- {fc}" for fc in formatted_chars)
                + "\n"
            )

    prompt = f"""Language: {"Hindi (Devanagari)" if is_hindi else "English"}
Preceding Scene Context / Characters Speaking:
{preceding_context if preceding_context else "Beginning of scene."}
{f"Dramatic Scene & Beat Context:\n{dramatic_context}" if dramatic_context else ""}
{roster_hint}
Current Scene Text:
\"\"\"
{chunk_text}
\"\"\"

Output JSON: A list of objects where each object has:
- "index": int (1-based relative to this chunk)
- "type": "narration" | "dialogue" | "action" (MANDATORY: emit dedicated "action" segments for major physical beats — weapon draw/clash, door kick/slam, tankard slam, heavy fall/blow, explosion — DO NOT layer heavy impacts directly on top of speech; isolate them with speaker: "Foley", text: "[ACTION]")
- "speaker": character name (e.g. "Alice", "Bob"), "Narrator", or "Foley" (for action segments)
- "text": speech text (clean spoken content in {"Devanagari Hindi" if is_hindi else "English"}, with optional inline vocal tags like [whispers], [shouting], [cold menace] where emotionally appropriate, or "[ACTION]" for action segments)
- "emotion": "neutral" | "angry" | "whispering" | "sad" | "excited" | "growl" | "calm_raspy"
- "actioning": "threaten" | "deflect" | "reassure" | "confess" | "plead" | "probe" | "comfort" | "test" | "intimidate" | "negotiate" | "challenge" | "mock" | "persuade" (transitive dramatic intent)
- "subtext": string (optional unsaid psychological subtext if strongly justified by context, else "")
- "underlying_emotion": string (optional concealed emotional state, else "")
- "intensity_level": "low" | "medium" | "high" | "explosive" (DSP dynamic headroom: "low" for whispered/intimate, "medium" for standard dialogue/narration, "high" for intense confrontation/shouts, "explosive" for climactic battle cries and fatal strikes)
- "pre_roll_breath_ms": int (150 to 250 for intimate/terrified lines, 0 for standard delivery)
- "pause_after_ms": int (300 to 800 for normal dialogue, 800 to 1500 for action impacts)
- "acting": {{
    "delivery_style": "whispering_fear" | "cold_menace" | "breathless_exhaustion" | "ironic_mockery" | "bellowing_rage" | "combat_strain" | "slow_motion" | "calm_authoritative" | "gentle_tender" | "neutral",
    "pacing": float (0.88 to 1.15, e.g. 0.92 for slow/bassy/deliberate, 1.0 for normal, 1.10 for fast action)
  }}
- "spatial": {{
    "pan": float (-0.6 to 0.6, e.g. 0.0 for Narrator / clash point, -0.6 for attacker, +0.6 for defender),
    "proximity": "intimate_close" | "normal_room" | "distant"
  }}
- "acoustic_env": "tavern_interior" | "stone_crypt" | "royal_hall" | "damp_dungeon" | "dense_forest_night" | "quiet_chamber" | "open_road"
- "sfx_cues": [
    {{
      "tag": "sword_draw" | "sword_clash" | "body_fall" | "blood_impact" | "beer_pour" | "tankard_slam" | "coin_clink" | "chair_scrape" | "door_creak" | "footsteps_wood" | "boots_gravel" | "cloak_rustle" | "sign_magic" | "fire_crackle" | "horse_gallop",
      "timing": "before" | "under" | "after",
      "offset_ms": int (-200 to 600),
      "volume": float (0.25 to 0.55),
      "description": "Short explanation of physical sound"
    }}
  ]
- "music": {{
    "mood": "peaceful" | "mysterious" | "tense" | "emotional" | "epic",
    "ducking_db": float (-18.0 to -10.0)
  }}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": sys_prompt}]},
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    from audiobook_factory.logger import logger

    max_retries = max(max_retries, 4)
    for attempt in range(max_retries):
        curr_key = pool.get_key(service="text") if (attempt > 0 or not api_key) else api_key
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={curr_key}"
        headers = get_stealth_sdk_headers(curr_key)
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.warning(f"  [!] Screenplay LLM returned no candidates: {data.get('promptFeedback', {})}")
                    continue
                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                if not parts:
                    continue
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                raw_json = "".join(text_parts).strip()

                # Strip markdown code blocks ```json ... ```
                match = re.search(r"```(?:json)?\s*(.*?)```", raw_json, re.DOTALL)
                if match:
                    raw_json = match.group(1).strip()
                elif raw_json.startswith("```"):
                    raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json)
                    raw_json = re.sub(r"\s*```$", "", raw_json).strip()

                parsed = None
                try:
                    parsed = json.loads(raw_json)
                except json.JSONDecodeError:
                    # [AGENTIC SHIFT] LLM-based Truncation Recovery Loop
                    if (raw_json.startswith("[") or raw_json.startswith("{")) and candidate.get("finishReason") == "MAX_TOKENS":
                        logger.info("  [*] JSON truncated (MAX_TOKENS). Invoking Data Healer Agent...")
                        healer_prompt = f"The following JSON array was truncated. Please continue outputting valid JSON exactly from where it left off, closing the array properly. Only return the continued JSON without markdown.\n\nTruncated JSON end:\n{raw_json[-1000:]}"
                        healer_payload = {
                            "contents": [{"parts": [{"text": healer_prompt}]}],
                            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
                        }
                        try:
                            h_req = urllib.request.Request(
                                url,  # Reusing the same URL with current key
                                data=json.dumps(healer_payload).encode("utf-8"),
                                headers=headers,
                                method="POST",
                            )
                            with urllib.request.urlopen(h_req, timeout=90.0) as h_resp:
                                h_data = json.loads(h_resp.read().decode("utf-8"))
                                h_parts = h_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                continuation = "".join([p.get("text", "") for p in h_parts if "text" in p]).strip()
                                if continuation.startswith("```"):
                                    continuation = re.sub(r"^```(?:json)?\s*", "", continuation)
                                    continuation = re.sub(r"\s*```$", "", continuation).strip()
                                
                                repaired_json = raw_json + continuation
                                parsed = json.loads(repaired_json)
                                logger.info("  [+] Data Healer Agent successfully repaired the truncated JSON.")
                        except Exception as e:
                            logger.warning(f"  [!] Data Healer failed: {e}. Falling back to last safe brace.")
                            repaired = raw_json.strip()
                            last_brace = repaired.rfind("}")
                            if last_brace != -1 and not repaired.endswith("]"):
                                candidate_str = repaired[:last_brace + 1].rstrip() + "\n]"
                                try:
                                    parsed = json.loads(candidate_str)
                                except Exception:
                                    raise
                            else:
                                raise
                    else:
                        # Fallback for incomplete JSON array with safe closing brace
                        repaired = raw_json.strip()
                        last_brace = repaired.rfind("}")
                        if last_brace != -1 and repaired.startswith("[") and not repaired.endswith("]"):
                            candidate_str = repaired[:last_brace + 1].rstrip() + "\n]"
                            parsed = json.loads(candidate_str)
                        else:
                            raise

                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "script" in parsed and isinstance(parsed["script"], list):
                    return parsed["script"]
                elif isinstance(parsed, dict) and "segments" in parsed and isinstance(parsed["segments"], list):
                    return parsed["segments"]
                else:
                    raise ValueError(f"Unexpected JSON structure: {type(parsed)}")

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            logger.warning(f"  [!] Screenplay LLM HTTP {e.code} on key ...{curr_key[-6:]}: {err_body[:120]}")
            if e.code == 429:
                pool.mark_temporary_backoff(curr_key, 12.0, "RPM rate limit in script parsing")
            time.sleep(1.5)
            continue
        except Exception as ex:
            logger.warning(f"  [!] Screenplay LLM parse error: {ex}")
            time.sleep(1.5)
            continue

    logger.warning("  [!] All screenplay retries exhausted. Falling back to narrator chunks.")
    # Guaranteed Zero Text Drop: Fall back to narrator script for this chunk instead of returning []
    return build_narrator_script(chunk_text, is_hindi)


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
    import hashlib
    from audiobook_factory.key_manager import get_persistent_key_pool
    from audiobook_factory.dramaturgy.scene_analyzer import SceneAnalyzer
    from audiobook_factory.dramaturgy.beat_planner import BeatPlanner
    from audiobook_factory.dramaturgy.contracts import DramaticPlan
    from audiobook_factory.dramaturgy.dramatic_validator import DramaticValidator

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
    api_key = pool.get_key(service="text")
    if not api_key:
        script = build_narrator_script(chapter_text, is_hindi)
        if memory_context is not None and hasattr(memory_context, "apply_performance_guidance_to_segment"):
            script = [memory_context.apply_performance_guidance_to_segment(seg) for seg in script]
        cleaned = clean_screenplay_pass2(
            script,
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

    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-lite-latest")
    memory_prompt_str = (
        memory_context.get_prompt_context()
        if memory_context is not None and hasattr(memory_context, "get_prompt_context")
        else ""
    )

    # 2. Process within safe token budget (~7,500 chars) directly
    if len(chapter_text) <= 7500:
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

        raw_items = _parse_dramatized_chunk_llm(
            chunk_text=chapter_text,
            preceding_context=memory_prompt_str,
            is_hindi=is_hindi,
            character_roster=character_roster,
            api_key="",
            model=model,
            dramatic_context=dramatic_context_str,
        )
        if not raw_items:
            fallback = build_narrator_script(chapter_text, is_hindi)
            cleaned = clean_screenplay_pass2(
                fallback,
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
    else:
        # 3. Novel-Scale Beat-Aligned Chunking (Confirmed /grill-me Solution)
        chunks = BeatPlanner.slice_chapter_by_beats(
            chapter_text=chapter_text,
            dramatic_plan=dramatic_plan,
            max_words=1200,
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

            chunk_items = _parse_dramatized_chunk_llm(
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
                fallback_chunk = build_narrator_script(c_text, is_hindi)
                raw_items.extend(fallback_chunk)

    if not raw_items:
        fallback = build_narrator_script(chapter_text, is_hindi)
        cleaned = clean_screenplay_pass2(
            fallback,
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
    import re
    from typing import Tuple
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

        from audiobook_factory.sanitizer import sanitize_screenplay_segment
        sanitized_item = sanitize_screenplay_segment(item, is_hindi)
        if not sanitized_item:
            continue

        cleaned_text = normalize_speech_text(sanitized_item.get("text", ""), is_hindi)
        if not cleaned_text:
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
        ):
            if field in sanitized_item:
                entry[field] = sanitized_item[field]

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

    return final_script


def generate_project_scripts(
    project_dir: Path,
    use_hindi: bool = False,
    dramatized: bool = False,
    overwrite: bool = False,
) -> Path:
    """Generates JSON screenplay scripts for all chapters in project."""
    project_dir = Path(project_dir).resolve()
    input_dir = project_dir / ("translation" if use_hindi else "extracted")
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    target_files = sorted(input_dir.glob("*.md"))
    if not target_files:
        raise FileNotFoundError(f"No markdown chapters found in {input_dir}")

    # Load character roster from translation glossary or project registry if available
    roster = None
    roster_file = project_dir / "character_roster.json"
    glossary_file = project_dir / "translation" / "glossary.json"
    if roster_file.exists():
        try:
            with open(roster_file, "r", encoding="utf-8") as f:
                roster = json.load(f)
        except Exception:
            pass
    elif glossary_file.exists():
        try:
            with open(glossary_file, "r", encoding="utf-8") as f:
                glossary = json.load(f)
                roster = {"characters": {c["hindi_name"] if use_hindi and "hindi_name" in c else c.get("english_name", ""): {"aliases": [c.get("english_name", "")]} for c in glossary.get("characters", [])}}
        except Exception:
            pass

    # Load BookBible & MemoryStore 2.0 for screenplay continuity
    bible = None
    memory_store = None
    memory_store_path = None
    try:
        from audiobook_factory.translation.book_bible import BookBible
        from audiobook_factory.translation.memory import (
            MemoryStore,
            MemoryRetriever,
            EventExtractor,
        )
        bible = BookBible.load_from_project(project_dir)
        memory_store_path = MemoryStore.default_store_path(project_dir)
        memory_store = MemoryStore.load(memory_store_path, book_bible=bible)
    except Exception:
        pass

    if dramatized:
        try:
            from audiobook_factory.dramaturgy.performance_bible import PerformanceBibleGenerator
            pb = PerformanceBibleGenerator.generate_bible_for_project(
                project_dir=project_dir,
                book_bible=bible,
                roster_data=roster,
            )
            pb.save_to_file(project_dir / "performance_bible.json")
        except Exception as e:
            pass

    dramaturgy_dir = project_dir / "dramaturgy"
    if dramatized:
        dramaturgy_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Building audiobook scripts for {len(target_files)} chapters (Mode: {'Dramatized' if dramatized else 'Narrator'})...")

    for seq_idx, chap_file in enumerate(target_files, 1):
        script_file = scripts_dir / f"{chap_file.stem}_script.json"
        if not overwrite and script_file.exists() and script_file.stat().st_size > 50:
            print(f"[-] Script already exists: {script_file.name} (Skipping)")
            continue

        with open(chap_file, "r", encoding="utf-8") as f:
            content = f.read()

        mem_ctx = None
        if memory_store is not None:
            try:
                from audiobook_factory.translation.memory import MemoryRetriever
                mem_ctx = MemoryRetriever.retrieve_for_scene(
                    store=memory_store,
                    book_bible=bible,
                    chapter=seq_idx,
                    scene_id=chap_file.stem,
                    scene_text=content,
                )
            except Exception:
                mem_ctx = None

        if dramatized:
            script, d_plan, val_res = build_dramatized_script_llm(
                content,
                is_hindi=use_hindi,
                character_roster=roster,
                memory_context=mem_ctx,
                chapter_num=seq_idx,
                chapter_id=chap_file.stem,
                return_dramatic_plan=True,
            )
            try:
                d_plan.save_to_file(dramaturgy_dir / f"{chap_file.stem}_dramatic_plan.json")
                val_res.save_to_file(dramaturgy_dir / f"{chap_file.stem}_validation.json")
            except Exception:
                pass
        else:
            script = build_narrator_script(content, is_hindi=use_hindi)
            if mem_ctx is not None:
                script = [mem_ctx.apply_performance_guidance_to_segment(seg) for seg in script]

        # Commit extracted screenplay events to MemoryStore if not already committed
        if memory_store is not None and memory_store_path is not None:
            try:
                from audiobook_factory.translation.memory import EventExtractor
                already_committed = any(c.scene_id == chap_file.stem for c in memory_store.commit_history)
                if not already_committed and content.strip():
                    known_chars = (
                        list(bible.characters.keys())
                        if bible and isinstance(bible.characters, dict)
                        else ([c.canonical_name for c in bible.characters] if bible else [])
                    )
                    llm_wrapper = (
                        lambda prompt, system_instruction="", json_mode=True, **kw: json.dumps(
                            call_gemini_json(f"{system_instruction}\n\n{prompt}")
                        )
                    )
                    events, _ = EventExtractor.extract_scene_events(
                        scene_text=content,
                        chapter=seq_idx,
                        scene_id=chap_file.stem,
                        known_characters=known_chars,
                        location=mem_ctx.location_name if mem_ctx else "Unspecified",
                        call_llm_fn=llm_wrapper,
                    )
                    memory_store.commit_scene_memory(
                        scene_id=chap_file.stem,
                        chapter=seq_idx,
                        events=events,
                        source_text=content,
                        book_bible=bible,
                        location=mem_ctx.location_name if mem_ctx else "Unspecified",
                    )
                    memory_store.save(memory_store_path)
            except Exception:
                pass

        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)

        print(f"[+] Built script for {chap_file.name} -> {len(script)} audio segments")

    print(f"[DONE] All chapter scripts built -> {scripts_dir}")
    return scripts_dir

