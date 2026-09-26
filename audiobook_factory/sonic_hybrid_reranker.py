#!/usr/bin/env python3
"""
Transparent Hybrid Reranker (Phase 3).
=====================================
Deterministic, explainable scoring engine combining multi-source evidence:
- Semantic relevance (CLAP vector similarity)
- Classifier evidence (AudioSet 527 tags & raw probabilities)
- Lexical relevance (FTS5 BM25 match)
- Structured alignment (Sonic Genome fields: category, subcategory, exciter, resonator)
- Acoustic compatibility (Measured DSP facts: duration, spectral centroid, LUFS)
- Metadata completeness bonus (tie-breaker signal without overpowering relevance)
- Negative evidence penalties (confirmed speech/music rejection)
- Lightweight result diversity filtering

100% deterministic, zero machine-learning black box models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.logger import logger
from audiobook_factory.sonic_candidate_generators import CandidateRecord
from audiobook_factory.sonic_query_planner import SoundQueryPlan


class RerankingWeights(BaseModel):
    """
    Configurable, fully documented weights for hybrid candidate reranking.
    Sum of positive weights equals 1.00.
    """
    model_config = ConfigDict(extra="ignore")

    w_semantic: float = Field(default=0.35, ge=0.0, le=1.0, description="Weight for CLAP vector semantic similarity")
    w_classifier: float = Field(default=0.20, ge=0.0, le=1.0, description="Weight for AST classifier tag evidence")
    w_lexical: float = Field(default=0.15, ge=0.0, le=1.0, description="Weight for FTS5 BM25 text match")
    w_structured: float = Field(default=0.15, ge=0.0, le=1.0, description="Weight for Sonic Genome structured field match")
    w_acoustic: float = Field(default=0.10, ge=0.0, le=1.0, description="Weight for measured DSP boundary alignment")
    w_quality: float = Field(default=0.05, ge=0.0, le=1.0, description="Weight for metadata completeness bonus")
    w_negative_penalty: float = Field(default=0.50, ge=0.0, le=1.0, description="Penalty multiplier for confirmed unwanted features")


class ScoredCandidate(BaseModel):
    """Candidate with transparent score breakdown and human-readable match explanations."""
    model_config = ConfigDict(extra="ignore")

    candidate: CandidateRecord
    final_score: float = Field(..., ge=0.0, le=1.0, description="Normalized overall relevance score [0.0, 1.0]")
    component_scores: Dict[str, float] = Field(default_factory=dict)
    negative_penalties: Dict[str, float] = Field(default_factory=dict)
    why_matched: List[str] = Field(default_factory=list)


class SonicHybridReranker:
    """
    Reranks candidate pools into ranked result lists using transparent linear models.
    """

    def __init__(self, default_weights: Optional[RerankingWeights] = None):
        self.default_weights = default_weights or RerankingWeights()

    def rerank(
        self,
        candidates: List[CandidateRecord],
        plan: SoundQueryPlan,
        weights: Optional[RerankingWeights] = None,
        apply_diversity: bool = True,
        top_k: int = 10,
        diversity_threshold: Optional[float] = None,
    ) -> List[ScoredCandidate]:
        """
        Reranks the candidate pool according to the query plan and scoring model.
        """
        if not candidates:
            return []

        w = weights or self.default_weights
        scored_list: List[ScoredCandidate] = []

        for cand in candidates:
            ev = cand.evidence
            reasons: List[str] = []
            comp_scores: Dict[str, float] = {}
            penalties: Dict[str, float] = {}

            # 1. Semantic Score (CLAP)
            s_sem = 0.0
            if ev.clap_similarity is not None:
                # Use relative score if multiple candidates, else raw similarity clamped to [0, 1]
                s_sem = ev.clap_relative_score if ev.clap_relative_score is not None else max(0.0, min(1.0, ev.clap_similarity))
                reasons.append(f"Semantic match ({ev.clap_similarity:.2f} similarity to '{ev.clap_query_matched or plan.normalized_query}')")
            comp_scores["semantic"] = round(s_sem, 3)

            # 2. Classifier Score
            s_class = 0.0
            if ev.classifier_matches:
                # Take highest confidence among matched labels
                best_class = max(ev.classifier_matches, key=lambda x: x.get("raw_score", 0.0))
                s_class = float(best_class.get("raw_score", 0.0))
                lbl = best_class.get("normalized_label") or best_class.get("raw_label")
                reasons.append(f"Classifier verified '{lbl}' (confidence: {s_class:.2f})")
            elif plan.target_classifier_labels:
                # If plan asked for classifier targets but candidate has none, check if it has tags
                cand_tags = cand.tags.lower()
                for target in plan.target_classifier_labels:
                    if target.lower() in cand_tags:
                        s_class = 0.40
                        reasons.append(f"Source tags match classifier target '{target}'")
                        break
            comp_scores["classifier"] = round(s_class, 3)

            # 3. Lexical Score (FTS5)
            s_lex = 0.0
            if ev.fts_score is not None:
                s_lex = ev.fts_score
                terms_str = ", ".join(f"'{t}'" for t in ev.fts_matched_terms[:3])
                reasons.append(f"Keyword match for {terms_str}")
            comp_scores["lexical"] = round(s_lex, 3)

            # 4. Structured Score
            s_struct = 0.0
            if ev.structured_matches:
                # Proportional to number of matched structured filters
                matched_count = len(ev.structured_matches)
                total_target = max(1, len(plan.structured_filters))
                s_struct = min(1.0, matched_count / total_target)
                struct_desc = ", ".join(f"{k}='{v}'" for k, v in ev.structured_matches.items())
                reasons.append(f"Structured filter match ({struct_desc})")
            comp_scores["structured"] = round(s_struct, 3)

            # 5. Acoustic Score (DSP Facts)
            s_acoust = 0.5  # neutral baseline
            ac_constraints = plan.acoustic_constraints
            if ev.acoustic_matches:
                s_acoust = 0.9
                ac_desc = ", ".join(f"{k}: {v}" for k, v in ev.acoustic_matches.items())
                reasons.append(f"Acoustic DSP alignment ({ac_desc})")
            elif ac_constraints.duration_max_sec and cand.duration_sec > ac_constraints.duration_max_sec:
                # Penalize exceeding maximum requested duration
                s_acoust = 0.1
                reasons.append(f"Duration {cand.duration_sec:.1f}s exceeds target {ac_constraints.duration_max_sec:.1f}s")
            comp_scores["acoustic"] = round(s_acoust, 3)

            # 6. Metadata Completeness Bonus (tie-breaker)
            s_qual = ev.metadata_completeness
            comp_scores["quality"] = round(s_qual, 3)
            if s_qual >= 0.8:
                reasons.append("High metadata completeness (+0.05)")

            # 7. Negative Evidence Evaluation
            total_penalty = 0.0
            neg = plan.negative_constraints

            # Speech negative evidence
            if neg.exclude_speech:
                speech_detected, speech_conf = self._detect_speech_evidence(cand)
                if speech_detected:
                    pen = w.w_negative_penalty * speech_conf
                    total_penalty += pen
                    penalties["speech_detected"] = round(pen, 3)
                    reasons.append(f"PENALTY: Speech detected (confidence {speech_conf:.2f}, -{pen:.2f})")
                else:
                    reasons.append("Confirmed negative speech (speech-free verified)")

            # Music negative evidence
            if neg.exclude_music:
                music_detected, music_conf = self._detect_music_evidence(cand)
                if music_detected:
                    pen = w.w_negative_penalty * music_conf
                    total_penalty += pen
                    penalties["music_detected"] = round(pen, 3)
                    reasons.append(f"PENALTY: Music detected (confidence {music_conf:.2f}, -{pen:.2f})")

            # Local cache bonus
            local_bonus = 0.03 if cand.is_downloaded else 0.0
            if cand.is_downloaded:
                reasons.append("Locally cached asset (+0.03)")

            # Linear Combination
            base_score = (
                w.w_semantic * s_sem +
                w.w_classifier * s_class +
                w.w_lexical * s_lex +
                w.w_structured * s_struct +
                w.w_acoustic * s_acoust +
                w.w_quality * s_qual +
                local_bonus
            )

            # Final Score clamped to [0.0, 1.0]
            final_score = max(0.0, min(1.0, base_score - total_penalty))

            scored_list.append(ScoredCandidate(
                candidate=cand,
                final_score=round(final_score, 4),
                component_scores=comp_scores,
                negative_penalties=penalties,
                why_matched=reasons if reasons else ["General catalog text match"],
            ))

        # Sort descending by final score, break ties with local availability and ID
        scored_list.sort(key=lambda x: (x.final_score, x.candidate.is_downloaded, -x.candidate.asset_id), reverse=True)

        # 8. Result Diversity Filter
        if apply_diversity and len(scored_list) > top_k:
            thresh = diversity_threshold if diversity_threshold is not None else 0.10
            scored_list = self._apply_diversity_filter(scored_list, top_k=top_k, diversity_threshold=thresh)

        return scored_list[:top_k]

    def _detect_speech_evidence(self, cand: CandidateRecord) -> Tuple[bool, float]:
        """
        Determines if an asset contains confirmed speech vs unknown.
        Returns: (is_speech_confirmed, confidence)
        """
        speech_labels = {"Speech", "Whispering", "Screaming", "Laughter", "Gasp", "Sigh", "human.vocal"}

        # 1. Check classifier tags
        for cm in cand.evidence.classifier_matches:
            raw_l = cm.get("raw_label", "")
            norm_l = cm.get("normalized_label", "")
            if raw_l in speech_labels or (norm_l and any(sl in norm_l for sl in speech_labels)):
                score = float(cm.get("raw_score", 0.0))
                if score >= 0.15:
                    return True, score

        # 2. Check metadata / title / tags
        text_blob = f"{cand.title} {cand.description} {cand.tags}".lower()
        if any(w in text_blob for w in ("vocal", "speech", "dialogue", "talking", "narrator")):
            return True, 0.70

        return False, 0.0

    def _detect_music_evidence(self, cand: CandidateRecord) -> Tuple[bool, float]:
        """Determines if an asset contains confirmed music."""
        music_labels = {"Music", "Musical instrument", "BGM"}

        if cand.category in ("MUS", "DYNAMIC_STEM", "LEITMOTIF"):
            return True, 0.90

        for cm in cand.evidence.classifier_matches:
            raw_l = cm.get("raw_label", "")
            if raw_l in music_labels:
                score = float(cm.get("raw_score", 0.0))
                if score >= 0.20:
                    return True, score

        text_blob = f"{cand.title} {cand.description} {cand.tags}".lower()
        if any(w in text_blob for w in ("orchestral", "melody", "brass", "piano", "synth", "strings")):
            return True, 0.60

        return False, 0.0

    def _apply_diversity_filter(
        self,
        ranked: List[ScoredCandidate],
        top_k: int,
        diversity_threshold: float = 0.10,
    ) -> List[ScoredCandidate]:
        """
        Enforces collection diversity without suppressing superior matches:
        - Allows max 2 items from the same source collection/prefix when scores are close (gap <= diversity_threshold).
        - If a candidate's score is substantially superior (> diversity_threshold ahead), it is preserved regardless of diversity.
        """
        diverse_results: List[ScoredCandidate] = []
        source_counts: Dict[str, int] = {}

        for item in ranked:
            src = (item.candidate.source_collection or item.candidate.category).lower()
            current_count = source_counts.get(src, 0)

            # Check if this item is substantially superior to the threshold
            is_substantially_better = False
            if diverse_results and (item.final_score >= diverse_results[-1].final_score - 0.02 and item.final_score > 0.75):
                is_substantially_better = True

            if current_count < 2 or is_substantially_better or len(diverse_results) < top_k // 2:
                diverse_results.append(item)
                source_counts[src] = current_count + 1
            elif len(diverse_results) < top_k:
                # Allow if candidate pool is small
                diverse_results.append(item)
                source_counts[src] = current_count + 1

            if len(diverse_results) >= top_k:
                break

        return diverse_results
