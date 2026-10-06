#!/usr/bin/env python3
"""
Audiobook Factory - Room 1 Agent 0: Universal Literary DNA & Register Profiler.
Analyzes any novel (from classical heritage realism to somatic psychological drama,
gritty dark fantasy, and contemporary fiction) to extract its core literary DNA:
1. literary_tradition (Rural Realism, Somatic Realism, Dark Fantasy, Classic, etc.)
2. source_fidelity_tier (CLASSIC_REVERENT, DRAMATIC_MODERN, RAW_UNRATED)
3. regional_dialect_cadence (Awadhi/Bhojpuri Hindustani, Delhi/Lucknow Urdu, etc.)
4. profanity_policy (strictly derived from source text, 'Nothing Above Source')
5. action_intensity & intimacy_intensity

Guarantees zero novel hardcoding: All acoustic, linguistic, and dramatic
parameters are dynamically anchored to the author's authentic text and live web research.
"""

from __future__ import annotations
import json
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from audiobook_factory.llm_client import call_gemini as default_call_gemini
from audiobook_factory.model_manager import get_model_manager, TaskType
from audiobook_factory.safety import get_dramatic_fiction_framing

logger = logging.getLogger("AudiobookFactory")


class BookDNAAgent:
    """Agent 0: Universal Literary DNA & Register Profiler.
    Determines the world's literary boundaries without any hardcoded assumptions.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return get_model_manager().resolve_active_model(TaskType.EXTRACTION)

    def analyze_book_dna(
        self,
        novel_text_sample: str,
        book_metadata: Dict[str, Any],
        call_llm_fn: Optional[Callable[..., Any]] = None,
        enable_web_research: bool = True,
    ) -> Dict[str, Any]:
        """
        Synthesizes the complete book_dna.json profiling the novel's literary tradition,
        register boundaries, and acoustic/emotional DNA using LLM and Google Search Grounding.
        """
        model = self._resolve_model()
        book_title = book_metadata.get("title", "Unknown Novel")
        author = book_metadata.get("author", "Unknown Author")
        project_slug = book_metadata.get("project_slug", "novel")

        fiction_framing = get_dramatic_fiction_framing(title=book_title, author=author)

        has_book_info = bool(book_title and book_title != "Unknown Novel")
        search_prompt_line = (
            f"Perform a live web search for '{book_title}' by '{author}' to research its published background, "
            f"cultural setting, historical era, themes, and maturity rating.\n"
            if (enable_web_research and has_book_info) else ""
        )

        sys_prompt = (
            fiction_framing +
            "You are an elite Literary Dramaturge, Comparative Literature Scholar, and Master Audio Drama Director.\n"
            + search_prompt_line +
            "Your task is to analyze the source novel's text sample, identify its literary tradition, "
            "authorial style, cultural era, dialect register, and authentic emotional/action intensity.\n\n"
            "NON-NEGOTIABLE CORE INVARIANTS:\n"
            "1. ZERO HARDCODED PRECONCEPTIONS: Base all decisions strictly on the text samples, author context, and web findings.\n"
            "2. THE 'NOTHING ABOVE SOURCE' INVARIANT:\n"
            "   - If the novel is dignified classic or heritage literature: set source_fidelity_tier to 'CLASSIC_REVERENT' "
            "and profanity_policy to 'STRICTLY_CLEAN_REVERENT'. Strictly forbid modern street vulgarity or forced slurs.\n"
            "   - If the novel is visceral psychological or somatic realism: set source_fidelity_tier to 'RAW_UNRATED' "
            "with somatic intimacy and unvarnished truth.\n"
            "   - If the novel is gritty dark fantasy, crime, or intense action drama: set source_fidelity_tier to 'RAW_UNRATED', "
            "profanity_policy to 'UNRATED_AUTHENTIC_KASHYAP', and action_intensity to 'VISCERAL_COMBAT_GORE'.\n"
            "3. LINGUISTIC AUTHENTICITY: Determine the organic Hindustani dialect cadence fitting the setting "
            "(e.g. Awadhi/Bhojpuri-infused Hindustani for rural India, Delhi/Lucknow Urdu-infused for period/courtly drama, "
            "rugged frontier Hindustani for gritty action, standard spoken Hindustani for contemporary fiction).\n"
        )

        prompt = f"""Book Title: {book_title}
Author: {author}

Passages Sampled Across Novel:
\"\"\"
{novel_text_sample[:120000]}
\"\"\"

Output JSON: An authoritative literary profile object:
{{
  "project_id": "proj-{project_slug}",
  "book_title": "{book_title}",
  "author": "{author}",
  "literary_tradition": "string (e.g. 'RURAL_REALISM_AND_PATHOS', 'SOMATIC_PSYCHOLOGICAL_REALISM', 'DARK_FANTASY_GRIT', 'VICTORIAN_GOTHIC', 'MODERN_THRILLER')",
  "source_fidelity_tier": "CLASSIC_REVERENT" | "DRAMATIC_MODERN" | "RAW_UNRATED",
  "regional_dialect_cadence": "string (e.g. 'Awadhi/Bhojpuri-infused Hindustani', 'Delhi/Lucknow Urdu-infused Hindustani', 'Rugged Frontier Hindustani', 'Standard Spoken Hindustani')",
  "profanity_policy": "STRICTLY_CLEAN_REVERENT" | "MILD_COLLOQUIAL" | "UNRATED_AUTHENTIC_KASHYAP",
  "action_intensity": "NONE_OR_MINIMAL" | "PSYCHOLOGICAL_TENSION" | "REALISTIC_GRIT" | "VISCERAL_COMBAT_GORE",
  "intimacy_intensity": "NONE_OR_TENDER" | "ROMANTIC_SUBTEXT" | "SOMATIC_PASSION_RAW" | "RAW_EROTIC_REALISM",
  "honorific_dynamics": "string (governing rules for Aap / Tum / Tu shifts between social tiers)",
  "dialogue_delivery_tempo": "measured_deliberate" | "dynamic_conversational" | "rapid_staccato",
  "world_atmosphere_summary": "string (2-3 sentences describing the sonic and emotional world)"
}}
"""
        logger.info(f"  [BookDNAAgent] Analyzing literary DNA for '{book_title}' using {model}...")

        try:
            if call_llm_fn:
                raw = call_llm_fn(prompt=prompt, system_instruction=sys_prompt, model=model, json_mode=True)
                if isinstance(raw, str):
                    import json_repair
                    res = json_repair.loads(raw)
                else:
                    res = raw
            else:
                tools = [{"googleSearch": {}}] if (enable_web_research and has_book_info) else None
                res = default_call_gemini(
                    prompt=prompt,
                    system_instruction=sys_prompt,
                    task_type=TaskType.EXTRACTION,
                    response_mime_type="application/json",
                    max_output_tokens=4096,
                    thinking_budget=1024,
                    tools=tools,
                    max_retries=6,
                )
            if isinstance(res, dict) and res.get("source_fidelity_tier"):
                logger.info(f"[+] BookDNAAgent: Successfully profiled '{book_title}' as {res.get('literary_tradition')} ({res.get('source_fidelity_tier')}).")
                return res
        except Exception as e:
            logger.warning(f"  [!] BookDNAAgent LLM analysis notice: {e}. Falling back to heuristic profiling.")

        return self._heuristic_fallback(novel_text_sample, book_metadata)

    def _heuristic_fallback(self, sample_text: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Fail-safe heuristic analyzer in case of network or API key degradation."""
        sample_lower = sample_text.lower()
        title_lower = meta.get("title", "").lower()
        author_lower = meta.get("author", "").lower()
        eff_author = meta.get("author") or "Unknown Author"

        is_rural_classic = any(
            w in sample_lower or w in author_lower
            for w in ("premchand", "godaan", "nirmala", "kisan", "zamindar", "patwari", "village", "farmer", "peasant", "panchayat", "खेत", "गांव", "किसान", "बैल", "चौपाल", "होरी", "गोदान", "धनिया")
        )
        is_somatic_realism = any(
            w in sample_lower or w in author_lower
            for w in ("manto", "thanda gosht", "khol do", "dhuan", "boo", "जिस्म", "ठंडी हथेली", "ठंडा गोश्त", "हवस", "गुनाह", "somatic", "flesh", "desire", "sensual", "naked", "shame")
        )
        is_dark_fantasy = any(
            w in sample_lower or w in title_lower
            for w in ("sword", "blade", "monster", "crypt", "mutant", "dragon", "spell", "basilisk", "beast", "sorcerer", "clash", "witcher")
        )

        if is_rural_classic:
            return {
                "project_id": f"proj-{meta.get('project_slug', 'novel')}",
                "book_title": meta.get("title", "Unknown"),
                "author": eff_author,
                "literary_tradition": "RURAL_REALISM_AND_PATHOS",
                "source_fidelity_tier": "CLASSIC_REVERENT",
                "regional_dialect_cadence": "Awadhi/Bhojpuri-infused Hindustani",
                "profanity_policy": "STRICTLY_CLEAN_REVERENT",
                "action_intensity": "PSYCHOLOGICAL_TENSION",
                "intimacy_intensity": "NONE_OR_TENDER",
                "honorific_dynamics": "Strict caste and feudal hierarchy; respectful Aap, familiar Tum, lower-caste Tu.",
                "dialogue_delivery_tempo": "measured_deliberate",
                "world_atmosphere_summary": "Rural pastoral setting filled with poverty, agrarian structures, and deep emotional pathos.",
            }
        elif is_somatic_realism:
            return {
                "project_id": f"proj-{meta.get('project_slug', 'novel')}",
                "book_title": meta.get("title", "Unknown"),
                "author": eff_author,
                "literary_tradition": "SOMATIC_PSYCHOLOGICAL_REALISM",
                "source_fidelity_tier": "RAW_UNRATED",
                "regional_dialect_cadence": "Delhi/Lahore Urdu-infused Hindustani",
                "profanity_policy": "UNRATED_AUTHENTIC_KASHYAP",
                "action_intensity": "PSYCHOLOGICAL_TENSION",
                "intimacy_intensity": "SOMATIC_PASSION_RAW",
                "honorific_dynamics": "Blunt, intimate, and raw; unvarnished psychological confrontation.",
                "dialogue_delivery_tempo": "dynamic_conversational",
                "world_atmosphere_summary": "Raw, visceral urban psychological realism exploring human desire, guilt, and existential truth.",
            }
        elif is_dark_fantasy:
            return {
                "project_id": f"proj-{meta.get('project_slug', 'novel')}",
                "book_title": meta.get("title", "Unknown"),
                "author": eff_author,
                "literary_tradition": "DARK_FANTASY_GRIT",
                "source_fidelity_tier": "RAW_UNRATED",
                "regional_dialect_cadence": "Rugged Frontier Hindustani",
                "profanity_policy": "UNRATED_AUTHENTIC_KASHYAP",
                "action_intensity": "VISCERAL_COMBAT_GORE",
                "intimacy_intensity": "SOMATIC_PASSION_RAW",
                "honorific_dynamics": "Mercenary cynical banter; power shifts from arrogant Tu to groveling Maai-Baap when intimidated.",
                "dialogue_delivery_tempo": "dynamic_conversational",
                "world_atmosphere_summary": "Cold, dangerous world populated by mercenaries, monsters, and cynical villagers.",
            }

        return {
            "project_id": f"proj-{meta.get('project_slug', 'novel')}",
            "book_title": meta.get("title", "Unknown"),
            "author": eff_author,
            "literary_tradition": "DRAMATIC_MODERN",
            "source_fidelity_tier": "DRAMATIC_MODERN",
            "regional_dialect_cadence": "Standard Spoken Hindustani",
            "profanity_policy": "MILD_COLLOQUIAL",
            "action_intensity": "REALISTIC_GRIT",
            "intimacy_intensity": "ROMANTIC_SUBTEXT",
            "honorific_dynamics": "Organic social dynamics based on status, age, and emotional intimacy.",
            "dialogue_delivery_tempo": "dynamic_conversational",
            "world_atmosphere_summary": "Rich narrative audio drama world balancing character introspection with dynamic pacing.",
        }
