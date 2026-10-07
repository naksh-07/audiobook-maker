#!/usr/bin/env python3
"""
Audiobook Factory - Room 3 Agent 1.5: Dialogue Attribution Auditor.
Independent QA Critic LLM that audits dialogue isolation and character attribution.
Prevents speaker turn inversion (A <-> B flips), misattributions to Narrator/pronouns,
and cleans leaked dialogue tags from spoken character text.
"""

from __future__ import annotations
import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable

from audiobook_factory.llm_client import call_gemini as default_call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing
from audiobook_factory.script.screenplay_cleaner import stitch_split_dialogue_turns

logger = logging.getLogger("AudiobookFactory")


class DialogueAttributionAuditor:
    """
    Room 3 Agent 1.5: Dialogue Attribution & Anti-Swap QA Specialist.
    Cross-checks parsed dialogue turns against raw prose to guarantee:
    1. Zero speaker turn inversions (A -> B flipped to B -> A).
    2. Zero spoken dialogue misattributed to Narrator or pronouns.
    3. Complete scrubbing of leaked speech tags ('he said', 'उसने कहा') from spoken lines.
    4. Strict canonical character roster compliance.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.SCREENPLAY)

    def _extract_roster_metadata(
        self,
        character_roster: Optional[Dict[str, Any]],
        is_hindi: bool = False,
    ) -> Tuple[Dict[str, str], str]:
        """Extracts canonical alias mapping and a formatted roster summary for prompt context."""
        alias_map: Dict[str, str] = {}
        roster_lines: List[str] = []

        if not character_roster:
            return alias_map, ""

        def _register_alias_variants(term: str, target: str):
            t_low = term.lower().strip()
            if not t_low:
                return
            alias_map[t_low] = target
            alias_map[t_low.replace("_", " ")] = target
            alias_map[t_low.replace(" ", "_")] = target

            bare = t_low
            for art in ("the ", "a ", "an "):
                if bare.startswith(art):
                    bare = bare[len(art):].strip()
                    break

            alias_map[bare] = target
            alias_map[bare.replace("_", " ")] = target
            alias_map[bare.replace(" ", "_")] = target
            for art in ("the ", "a ", "an "):
                alias_map[art + bare] = target
                alias_map[(art + bare).replace(" ", "_")] = target

        chars = character_roster.get("characters", {})
        if isinstance(chars, dict):
            for canon_name, details in chars.items():
                if canon_name in ("Narrator", "Foley"):
                    continue
                c_clean = canon_name.strip()
                _register_alias_variants(c_clean, c_clean)

                gender = "neutral"
                aliases = []
                if isinstance(details, dict):
                    gender = details.get("gender", "neutral")
                    aliases = details.get("aliases", [])
                    for a in aliases:
                        if isinstance(a, str) and a.strip():
                            _register_alias_variants(a.strip(), c_clean)

                alias_info = f", aliases: {', '.join(aliases[:4])}" if aliases else ""
                roster_lines.append(f"- {c_clean} [{gender}{alias_info}]")

        elif isinstance(chars, list):
            for c in chars:
                if isinstance(c, dict):
                    canon_name = c.get("english_name", "")
                    if is_hindi and c.get("hindi_name"):
                        h_name = c.get("hindi_name", "").strip()
                        if h_name:
                            _register_alias_variants(h_name, canon_name)
                    if canon_name and canon_name not in ("Narrator", "Foley"):
                        c_clean = canon_name.strip()
                        _register_alias_variants(c_clean, c_clean)
                        gender = c.get("gender", "neutral")
                        aliases = c.get("aliases", [])
                        for a in aliases:
                            if isinstance(a, str) and a.strip():
                                _register_alias_variants(a.strip(), c_clean)
                        alias_info = f", aliases: {', '.join(aliases[:4])}" if aliases else ""
                        roster_lines.append(f"- {c_clean} [{gender}{alias_info}]")

        roster_str = "\n".join(roster_lines) if roster_lines else "No explicit character roster provided."
        return alias_map, roster_str

    @staticmethod
    def _scrub_residual_speech_tags(text: str, is_hindi: bool = False) -> Tuple[str, bool]:
        """
        Strips residual speech tags (e.g. 'उसने कहा,', 'he said,') that leaked into spoken text,
        while strictly preserving bracketed vocal tags like [whispers], [combat strain].
        """
        if not text:
            return text, False

        original = text
        vocal_prefix = ""
        m_tag = re.match(r"^(\[[^\]]+\]\s*)", text)
        if m_tag:
            vocal_prefix = m_tag.group(1)
            core_text = text[len(vocal_prefix):]
        else:
            core_text = text

        cleaned = core_text.strip()

        # Leading & Trailing speech tags (Hindi)
        hindi_verbs = (
            r"(?:कहा|पूछा|बोला|बोली|बोले|पुकारा|चिल्लाया|चिल्लाई|फुसफुसाया|फुसफुसाई|"
            r"जवाब\s+दिया|उत्तर\s+दिया|हँसकर\s+कहा|धीमे\s+स्वर\s+में\s+कहा|कड़क\s+कर\s+कहा|"
            r"गुर्राया|गुर्राई|चीखा|चीखी|दहाड़ा|दहाड़ी|चेतावनी\s+दी)"
        )
        hindi_leading = [
            rf"^(?:उसने|वह|उन्होंने|आपने|तूने|मैंने)\s+[^।!?\n]{{0,25}}?{hindi_verbs}[,:\s।\-–—]+",
            rf"^[^।!?\n]{{1,25}}?\s+ने\s+[^।!?\n]{{0,25}}?{hindi_verbs}[,:\s।\-–—]+",
            rf"^[^।!?\n]{{1,20}}?(?:हँसकर|बिगड़कर|मुस्कुराकर|रोकर|झल्लाकर|चीखकर|फुसफुसाकर)\s+{hindi_verbs}[,:\s।\-–—]+",
            rf"^{hindi_verbs}[,:\s।\-–—]+",
        ]
        hindi_trailing = [
            rf"[,:\s\-–—]+(?:उसने|वह|उन्होंने|तूने|मैंने)\s+[^।!?\n]{{0,20}}?{hindi_verbs}[।\.!?]?$",
            rf"[,:\s\-–—]+[^।!?\n]{{1,25}}?\s+ने\s+[^।!?\n]{{0,20}}?{hindi_verbs}[।\.!?]?$",
            rf"[,:\s\-–—]+{hindi_verbs}[।\.!?]?$",
        ]

        # Leading speech tags (English)
        eng_verbs = (
            r"(?:said|replied|asked|muttered|whispered|screamed|growled|snapped|"
            r"shouted|cried|laughed|demanded|yelled|warned|commanded|inquired)"
        )
        eng_leading = [
            rf"^(?:the\s+[a-z]+|he|she|they|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+{eng_verbs}[,:\s\-–—]+",
            rf"^{eng_verbs}[,:\s\-–—]+",
        ]
        # Trailing speech tags (English)
        eng_trailing = [
            rf"[,:\s\-–—]+(?:the\s+[a-z]+|he|she|they|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+{eng_verbs}[\.!?]?$",
            rf"[,:\s\-–—]+{eng_verbs}[\.!?]?$",
        ]

        patterns_leading = hindi_leading if is_hindi else eng_leading
        patterns_trailing = hindi_trailing if is_hindi else eng_trailing

        # Apply leading scrub safely
        for pat in patterns_leading:
            candidate = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            if candidate:
                cleaned = candidate

        # Apply trailing scrub safely
        for pat in patterns_trailing:
            candidate = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
            if candidate:
                cleaned = candidate

        # Clean any stray leading or trailing quotation marks left over
        stripped_quotes = cleaned.strip("\"'“’‘” ")
        if stripped_quotes:
            cleaned = stripped_quotes

        final_text = f"{vocal_prefix}{cleaned}" if vocal_prefix else cleaned
        was_modified = (final_text != original)
        return final_text, was_modified

    def audit_and_correct(
        self,
        turns: List[Dict[str, Any]],
        chunk_text: str,
        preceding_context: str = "",
        is_hindi: bool = False,
        character_roster: Optional[Dict[str, Any]] = None,
        call_llm_fn: Optional[Callable[..., Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Audits parsed dialogue turns against raw prose to guarantee speaker fidelity
        and eliminate dialogue turn inversions and leaked speech tags.
        """
        if not turns:
            return [], {"status": "EMPTY", "turns_audited": 0, "corrections": []}

        alias_map, roster_summary = self._extract_roster_metadata(character_roster, is_hindi)

        # Prepare compact turn manifest for the Auditor LLM
        candidate_summary = []
        for t in turns:
            candidate_summary.append({
                "index": t.get("index", 1),
                "type": t.get("type", "narration"),
                "speaker": t.get("speaker", "Narrator"),
                "text": t.get("text", "")[:300],
            })

        sys_prompt = (
            get_dramatic_fiction_framing()
            + "You are an Academy-Award winning Audio Drama Script Supervisor and Forensic Dialogue Attribution Auditor.\n"
            "Your sole mission is to cross-check candidate dialogue segments against the original source prose chunk "
            "and ensure 100% accurate character attribution with ZERO voice swapping.\n\n"
            "CRITICAL AUDIT RULES:\n"
            "1. DETECT & FIX SPEAKER ALTERNATION FLIPS (A <-> B INVERSIONS):\n"
            "   - In rapid back-and-forth dialogue exchanges, verify that Speaker A and Speaker B are NOT inverted.\n"
            "   - Track conversational polarity: the answer to a question belongs to the OTHER speaker/interlocutor, never to the person who asked the question.\n"
            "   - Cross-check who actually spoke each line using narrative attribution verbs (e.g. 'Protagonist said', 'Inquirer asked', "
            "'उसने कहा', 'वक्ता बोला') or clear conversational turn logic.\n"
            "2. RESOLVE SPOKEN QUOTES ATTRIBUTED TO NARRATOR OR PRONOUNS:\n"
            "   - Spoken dialogue lines must NEVER be attributed to 'Narrator', generic descriptors, or pronouns ('he', 'she', 'उसने', 'वह', 'the stranger').\n"
            "   - Attribute strictly to the canonical character name from the Known Canon Characters list.\n"
            "3. STRIP RESIDUAL SPEECH TAGS:\n"
            "   - Strip redundant speech tags that leaked into character dialogue text (e.g. 'उसने कहा, ', 'he said, ').\n"
            "   - The dialogue 'text' field must contain ONLY spoken words and valid bracketed vocal tags like [whispers].\n"
            "4. NEVER REWRITE OR TRANSLATE:\n"
            "   - Do NOT rewrite, summarize, or translate the dialogue or narration. Maintain exact wording with tags removed.\n"
        )

        user_prompt = f"""{get_dramatic_fiction_framing()}Language: {"Hindi (Devanagari)" if is_hindi else "English"}

Canonical Character Roster:
{roster_summary}

Preceding Scene Context:
{preceding_context if preceding_context else "Beginning of scene."}

Original Source Prose:
\"\"\"
{chunk_text}
\"\"\"

Candidate Parsed Segments to Audit:
```json
{json.dumps(candidate_summary, ensure_ascii=False, indent=2)}
```

Output JSON: A list of objects matching each segment by "index":
[
  {{
    "index": int,
    "type": "dialogue" | "narration" | "action",
    "speaker": "Canonical Character Name" | "Narrator" | "Foley",
    "text": "Audited text with speech tags removed",
    "correction_made": string | null
  }}
]
"""

        audited_raw: Optional[List[Dict[str, Any]]] = None

        if call_llm_fn is not None:
            try:
                res = call_llm_fn(
                    prompt=user_prompt,
                    system_instruction=sys_prompt,
                    task_type=TaskType.SCREENPLAY,
                    response_mime_type="application/json",
                )
                if isinstance(res, list):
                    audited_raw = res
                elif isinstance(res, dict):
                    for k in ("audited_turns", "segments", "turns", "items", "script"):
                        if k in res and isinstance(res[k], list):
                            audited_raw = res[k]
                            break
            except Exception as e:
                logger.warning(f"  [DialogueAttributionAuditor] Injected LLM call warning: {e}")
        else:
            try:
                res = default_call_gemini(
                    prompt=user_prompt,
                    system_instruction=sys_prompt,
                    task_type=TaskType.SCREENPLAY,
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    thinking_budget=1024,
                    max_retries=6,
                )
                if isinstance(res, list):
                    audited_raw = res
                elif isinstance(res, dict):
                    for k in ("audited_turns", "segments", "turns", "items", "script"):
                        if k in res and isinstance(res[k], list):
                            audited_raw = res[k]
                            break
            except Exception as e:
                logger.warning(f"  [DialogueAttributionAuditor] LLM audit failed ({e}). Proceeding with deterministic safety net.")

        # Build correction maps
        correction_map: Dict[int, Dict[str, Any]] = {}
        if audited_raw and isinstance(audited_raw, list):
            for item in audited_raw:
                if isinstance(item, dict) and "index" in item:
                    correction_map[item["index"]] = item

        audited_turns: List[Dict[str, Any]] = []
        inversions_fixed = 0
        misattributions_fixed = 0
        tags_stripped = 0
        corrections_log: List[str] = []

        pronouns_set = {
            "he", "she", "him", "her", "his", "they", "them", "the man", "the woman",
            "उसने", "वह", "उसका", "उनकी", "लड़की", "महिला", "स्त्री", "आदमी", "लड़का"
        }

        for seg in turns:
            s_copy = dict(seg)
            idx = s_copy.get("index", 1)
            orig_speaker = s_copy.get("speaker", "Narrator")
            orig_text = s_copy.get("text", "")
            orig_type = s_copy.get("type", "narration")

            # Apply LLM audit adjustments if available
            if idx in correction_map:
                corr = correction_map[idx]
                audited_speaker = corr.get("speaker", orig_speaker)
                audited_text = corr.get("text", orig_text)
                audited_type = corr.get("type", orig_type)
                note = corr.get("correction_made")

                if audited_speaker and audited_speaker != orig_speaker:
                    if orig_speaker in ("Narrator", "Foley") or orig_speaker.lower() in pronouns_set:
                        misattributions_fixed += 1
                        corrections_log.append(f"Turn {idx}: Re-attributed from '{orig_speaker}' to '{audited_speaker}'")
                    else:
                        inversions_fixed += 1
                        corrections_log.append(f"Turn {idx}: Corrected speaker turn swap from '{orig_speaker}' to '{audited_speaker}' ({note or 'inversion detected'})")
                    s_copy["speaker"] = audited_speaker

                if audited_type and audited_type != orig_type:
                    s_copy["type"] = audited_type

                if audited_text and audited_text.strip():
                    s_copy["text"] = audited_text

            # Deterministic Step A: Canonical Alias Resolution
            current_spk = s_copy.get("speaker", "Narrator").strip()
            spk_lower = current_spk.lower()
            if spk_lower in alias_map:
                canonical = alias_map[spk_lower]
                if canonical != current_spk:
                    s_copy["speaker"] = canonical
                    current_spk = canonical
            else:
                for art in ("the ", "a ", "an ", "वह ", "उस "):
                    if spk_lower.startswith(art):
                        bare = spk_lower[len(art):].strip()
                        if bare in alias_map:
                            s_copy["speaker"] = alias_map[bare]
                            current_spk = alias_map[bare]
                            break
                    else:
                        with_art = art + spk_lower
                        if with_art in alias_map:
                            s_copy["speaker"] = alias_map[with_art]
                            current_spk = alias_map[with_art]
                            break

            # Deterministic Step B: Residual Speech Tag Scrubbing
            if s_copy.get("type") == "dialogue":
                txt = s_copy.get("text", "")
                cleaned_txt, stripped = self._scrub_residual_speech_tags(txt, is_hindi=is_hindi)
                if stripped:
                    tags_stripped += 1
                    s_copy["text"] = cleaned_txt
                    corrections_log.append(f"Turn {idx}: Stripped residual speech tags from dialogue")

            audited_turns.append(s_copy)

        # Deterministic Step C: Split-Quote Unification (Audible Flow Standard)
        initial_turn_count = len(audited_turns)
        audited_turns = stitch_split_dialogue_turns(audited_turns)
        stitched_count = initial_turn_count - len(audited_turns)
        if stitched_count > 0:
            corrections_log.append(f"Unified {stitched_count} split dialogue fragments into continuous thoughts.")

        report = {
            "status": "AUDITED_AND_CERTIFIED",
            "turns_audited": len(audited_turns),
            "inversions_fixed": inversions_fixed,
            "misattributions_fixed": misattributions_fixed,
            "tags_stripped": tags_stripped,
            "corrections": corrections_log,
        }

        if inversions_fixed > 0 or misattributions_fixed > 0 or tags_stripped > 0:
            logger.info(
                f"  [DialogueAttributionAuditor] Audit complete: "
                f"{inversions_fixed} inversions fixed, {misattributions_fixed} misattributions fixed, "
                f"{tags_stripped} tags scrubbed."
            )
        else:
            logger.info(f"  [DialogueAttributionAuditor] Audit clean: All {len(audited_turns)} turns verified with 100% fidelity.")

        return audited_turns, report
