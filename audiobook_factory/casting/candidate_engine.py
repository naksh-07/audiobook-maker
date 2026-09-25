#!/usr/bin/env python3
"""
Audiobook Factory - Voice Candidate Engine.
Ranks candidate voices from voice_casting_catalog.json for a given CharacterCastingProfile.
Computes multi-dimensional acoustic and dramatic fit scores with explainable rationale.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from .contracts import CharacterCastingProfile, VoiceCandidateScore


DEFAULT_CATALOG_PATH = Path("audiobooks/voice_casting_catalog.json")


class VoiceCandidateEngine:
    """
    Intelligent Voice Candidate Matcher.
    Ranks 12+ Gemini TTS voices against a character casting profile with explainable breakdown.
    """

    def __init__(self, catalog_data_or_path: Optional[Any] = None):
        self.catalog = self._load_catalog(catalog_data_or_path)

    def _load_catalog(self, source: Optional[Any]) -> Dict[str, Any]:
        if isinstance(source, dict):
            return source
        path = Path(source) if source else DEFAULT_CATALOG_PATH
        if not path.is_absolute():
            # Resolve relative to repo root
            cand = Path(__file__).resolve().parent.parent.parent / path
            if cand.exists():
                path = cand
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning(f"  [CANDIDATE ENGINE] Catalog not found at {path}. Using empty voice catalog.")
        return {"voices": {}}

    def rank_candidates(
        self,
        profile: CharacterCastingProfile,
        ensemble_voices: Optional[Dict[str, str]] = None,
        top_n: int = 5,
    ) -> List[VoiceCandidateScore]:
        """
        Ranks voice candidates against CharacterCastingProfile.
        ensemble_voices: mapping of already-cast characters to voice_ids for distinctiveness.
        """
        voices_dict = self.catalog.get("voices", {})
        if not voices_dict:
            return []

        already_cast_ids = set((ensemble_voices or {}).values())
        scores: List[VoiceCandidateScore] = []

        for v_id, v_meta in voices_dict.items():
            cand_score = self.evaluate_candidate(profile, v_id, v_meta, already_cast_ids)
            scores.append(cand_score)

        # Sort descending by overall score
        scores.sort(key=lambda s: s.overall_score, reverse=True)
        return scores[:top_n]

    def evaluate_candidate(
        self,
        profile: CharacterCastingProfile,
        voice_id: str,
        meta: Dict[str, Any],
        already_cast_ids: set[str],
    ) -> VoiceCandidateScore:
        """
        Calculates multi-dimensional suitability score for a single voice candidate.
        """
        display_name = meta.get("display_name", voice_id.capitalize())
        v_sex = str(meta.get("sex", "neutral")).lower()
        v_age = str(meta.get("perceived_age", "prime_adult")).lower()
        v_pitch = str(meta.get("pitch_category", "medium")).lower()
        v_timbre = str(meta.get("invariant_timbre", "")).lower()
        elasticity = meta.get("elasticity", {})
        styles_supported = [s.lower() for s in elasticity.get("styles_supported", [])]
        forbidden_styles = [s.lower() for s in elasticity.get("forbidden_styles", [])]
        archetypes = [a.lower() for a in meta.get("archetypes", [])]

        strengths: List[str] = []
        risks: List[str] = []
        breakdown: Dict[str, float] = {}

        # 1. Gender Alignment (Hard filter / heavy weight)
        gender_score = 1.0
        if profile.gender in ("male", "female") and v_sex in ("male", "female"):
            if profile.gender == v_sex:
                gender_score = 1.0
                strengths.append(f"Acoustic gender alignment ({v_sex})")
            else:
                gender_score = 0.10
                risks.append(f"Gender mismatch: voice is {v_sex}, character is {profile.gender}")
        breakdown["gender_fit"] = gender_score

        # 2. Perceived Age Match
        age_map = {
            "child": 0, "youth": 1, "young_adult": 2,
            "prime_adult": 3, "mature_adult": 4, "elder": 5
        }
        p_age_idx = age_map.get(profile.perceived_age, 3)
        v_age_idx = age_map.get(v_age, 3)
        age_diff = abs(p_age_idx - v_age_idx)
        if age_diff == 0:
            age_score = 1.0
            strengths.append(f"Exact perceived age match ({v_age})")
        elif age_diff == 1:
            age_score = 0.85
        elif age_diff == 2:
            age_score = 0.55
            risks.append(f"Age disparity: character is {profile.perceived_age}, voice sounds {v_age}")
        else:
            age_score = 0.20
            risks.append(f"Severe age disparity ({profile.perceived_age} vs {v_age})")
        breakdown["age_fit"] = age_score

        # 3. Pitch Band Match
        pitch_map = {"low": 1, "medium_low": 2, "medium": 3, "medium_high": 4, "high": 5}
        p_pitch_idx = pitch_map.get(profile.pitch_preference, 3)
        v_pitch_idx = pitch_map.get(v_pitch, 3)
        pitch_diff = abs(p_pitch_idx - v_pitch_idx)
        if pitch_diff == 0:
            pitch_score = 1.0
            strengths.append(f"Ideal pitch category ({v_pitch})")
        elif pitch_diff == 1:
            pitch_score = 0.85
        elif pitch_diff == 2:
            pitch_score = 0.55
        else:
            pitch_score = 0.25
            risks.append(f"Pitch mismatch: requested {profile.pitch_preference}, candidate is {v_pitch}")
        breakdown["pitch_fit"] = pitch_score

        # 4. Timbre & Vocal Weight Match
        timbre_score = 0.70
        t_pref = profile.timbre_preference.lower()
        if t_pref in v_timbre:
            timbre_score = 1.0
            strengths.append(f"Natural {t_pref} resonance match")
        elif t_pref == "gravelly" and ("raspy" in v_timbre or "gritty" in v_timbre):
            timbre_score = 0.90
            strengths.append("Compatible gritty/raspy chest resonance")
        elif t_pref == "smooth" and ("clear" in v_timbre or "warm" in v_timbre):
            timbre_score = 0.90
            strengths.append("Warm and clear vocal texture")
        elif t_pref == "sharp" and ("crisp" in v_timbre or "resolute" in v_timbre or "commanding" in v_timbre):
            timbre_score = 0.95
            strengths.append("Crisp commanding articulation")
        elif profile.vocal_weight == "heavy" and "heavy" in v_timbre:
            timbre_score = max(timbre_score, 0.90)
            strengths.append("Grounded, heavy vocal presence")
        breakdown["timbre_fit"] = timbre_score

        # 5. Archetype Affinity
        arch_score = 0.50
        p_arch = profile.sociolect_archetype.lower().replace("_", " ")
        matched_archetypes = []
        for arch in archetypes:
            if any(tok in arch for tok in p_arch.split() if len(tok) > 3):
                matched_archetypes.append(arch)
        if matched_archetypes:
            arch_score = 0.95
            strengths.append(f"Aligned archetype: {matched_archetypes[0]}")
        elif "cynic" in p_arch and any("hunter" in a or "hardened" in a for a in archetypes):
            arch_score = 0.90
            strengths.append("Fits stoic cynic archetype")
        elif "wit" in p_arch and any("bard" in a or "rogue" in a or "witty" in a for a in archetypes):
            arch_score = 0.95
            strengths.append("Expressive theatrical wit affinity")
        elif "commander" in p_arch and any("commander" in a or "warrior" in a or "matriarch" in a for a in archetypes):
            arch_score = 0.90
            strengths.append("Authoritative commanding presence")
        breakdown["archetype_fit"] = arch_score

        # 6. Personality & Authority Dynamics
        personality_score = 0.70
        if profile.authority >= 0.70:
            if any("authority" in s or "commanding" in s or "menace" in s for s in styles_supported):
                personality_score += 0.20
                strengths.append("Strong commanding authority range")
            else:
                personality_score -= 0.15
                risks.append("Limited high-authority commanding delivery")
        if profile.restraint >= 0.70:
            if any("suppressed" in s or "restrained" in s or "stoic" in s or "cold" in s for s in styles_supported):
                personality_score += 0.15
                strengths.append("Excellent restrained delivery capability")
        if profile.humor >= 0.60:
            if any("banter" in s or "wit" in s or "sarcasm" in s for s in styles_supported):
                personality_score += 0.15
                strengths.append("Natural comedic cadence and sarcasm")
        personality_score = max(0.1, min(1.0, personality_score))
        breakdown["personality_fit"] = round(personality_score, 2)

        # 7. Elasticity & Dramatic Range Fit
        range_score = 0.75
        for req in profile.required_styles:
            req_l = req.lower()
            if any(req_l in s for s in styles_supported):
                range_score = min(1.0, range_score + 0.08)
            if any(req_l in f for f in forbidden_styles):
                range_score = max(0.1, range_score - 0.35)
                risks.append(f"Forbidden style conflict: character requires '{req}', voice catalog forbids it")

        for f_req in profile.forbidden_styles:
            f_req_l = f_req.lower()
            if any(f_req_l in s for s in styles_supported):
                risks.append(f"Voice natural tendency leans into character-prohibited style '{f_req}'")
                range_score = max(0.2, range_score - 0.15)
        breakdown["range_fit"] = round(range_score, 2)

        # 8. Ensemble Distinctiveness
        distinctiveness_score = 1.0
        if voice_id in already_cast_ids:
            distinctiveness_score = 0.15
            risks.append(f"Voice collision: '{display_name}' is already assigned to another character")
        breakdown["distinctiveness"] = distinctiveness_score

        # Composite Weighted Score
        weights = {
            "gender_fit": 0.30,
            "age_fit": 0.12,
            "pitch_fit": 0.12,
            "timbre_fit": 0.14,
            "archetype_fit": 0.10,
            "personality_fit": 0.10,
            "range_fit": 0.07,
            "distinctiveness": 0.05,
        }
        overall = sum(breakdown[k] * weights[k] for k in weights)
        overall = round(max(0.0, min(1.0, overall)), 2)

        summary_parts = []
        if overall >= 0.85:
            summary_parts.append(f"Top tier match for {profile.canonical_name}")
        elif overall >= 0.70:
            summary_parts.append(f"Solid compatible candidate")
        else:
            summary_parts.append(f"Marginal fit with notable constraints")

        if strengths:
            summary_parts.append(strengths[0])

        return VoiceCandidateScore(
            voice_id=voice_id,
            display_name=display_name,
            overall_score=overall,
            strengths=strengths,
            risks=risks,
            score_breakdown=breakdown,
            recommendation_summary="; ".join(summary_parts),
        )
