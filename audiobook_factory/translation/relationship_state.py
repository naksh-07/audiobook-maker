#!/usr/bin/env python3
"""
Audiobook Factory - Dynamic Relationship State Engine.
Tracks multi-dimensional interpersonal dynamics (respect, familiarity, hostility, authority, intimacy)
and resolves contextual honorifics (Aap/Tum/Tu) with evidence-driven mutation rules.
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator


class DynamicRelationshipState(BaseModel):
    speaker: str
    target: str
    respect: int = Field(default=3, ge=-5, le=5)
    familiarity: int = Field(default=2, ge=0, le=5)
    hostility: int = Field(default=0, ge=0, le=5)
    intimacy: int = Field(default=1, ge=0, le=5)
    authority_differential: int = Field(default=0, ge=-5, le=5)  # positive = speaker has authority
    fear: int = Field(default=0, ge=0, le=5)
    trust: int = Field(default=3, ge=-5, le=5)
    current_pronoun: str = "tum"  # aap, tum, tu
    current_vocabulary_register: str = "casual"  # formal, casual, derogatory, intimate
    recent_interaction_notes: str = ""
    evidence_event_ids: List[str] = Field(default_factory=list)
    mutation_history: List[Dict[str, Any]] = Field(default_factory=list)
    last_updated_chapter: int = 1
    last_updated_scene: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "active_pronoun" in data and "current_pronoun" not in data:
                data["current_pronoun"] = data.pop("active_pronoun")
            if "tension" in data and "hostility" not in data:
                data["hostility"] = max(0, min(5, int(data.pop("tension"))))
            if "affection" in data and "intimacy" not in data:
                data["intimacy"] = max(0, min(5, int(data.pop("affection"))))
            if "power_balance" in data and "authority_differential" not in data:
                data["authority_differential"] = max(-5, min(5, int(data.pop("power_balance"))))
        return data

    @property
    def active_pronoun(self) -> str:
        return self.current_pronoun

    @active_pronoun.setter
    def active_pronoun(self, val: str) -> None:
        self.current_pronoun = val

    @property
    def tension(self) -> int:
        return self.hostility

    @tension.setter
    def tension(self, val: int) -> None:
        self.hostility = max(0, min(5, int(val)))

    @property
    def affection(self) -> int:
        return self.intimacy

    @affection.setter
    def affection(self, val: int) -> None:
        self.intimacy = max(0, min(5, int(val)))

    @property
    def power_balance(self) -> int:
        return self.authority_differential

    @power_balance.setter
    def power_balance(self, val: int) -> None:
        self.authority_differential = max(-5, min(5, int(val)))


# Bounded heuristic priors (NOT fixed narrative truth; modulated by existing state and semantic evidence)
RELATIONSHIP_INTERACTION_PRIORS: Dict[str, Dict[str, int]] = {
    "betrayal": {"trust": -2, "hostility": 3, "respect": -2},
    "shared_danger": {"trust": 1, "familiarity": 2, "respect": 0},
    "romantic_confession": {"intimacy": 3, "familiarity": 2, "trust": 1},
    "threat": {"fear": 2, "hostility": 1, "trust": -1},
    "reconciliation": {"hostility": -2, "trust": 1, "intimacy": 1},
    "insult": {"hostility": 1, "respect": -1},
    "oath_sworn": {"trust": 1, "respect": 2},
    "authority_assertion": {"authority_differential": 1, "fear": 1},
    "intimidation_collapse": {"fear": 2, "authority_differential": -2},
}


class RelationshipStateEngine:
    @staticmethod
    def resolve_pronoun_level(rel: DynamicRelationshipState) -> str:
        """
        Dynamically calculates the appropriate Hindi pronoun (aap, tum, tu)
        based on multidimensional interpersonal dynamics.
        """
        # Fear or severe subordinate status -> Aap / Maai-Baap
        if rel.fear >= 4 or rel.authority_differential <= -3:
            return "aap"

        # High hostility or severely broken trust -> Tu (aggressive/hostile)
        if rel.hostility >= 3 or rel.trust <= -1:
            return "tu"

        # High intimate closeness -> Tu
        if (rel.intimacy >= 3 and rel.familiarity >= 3) or (rel.intimacy >= 2 and rel.familiarity >= 4 and rel.trust >= 2):
            return "tu"

        # High respect and low familiarity -> Aap
        if rel.respect >= 3 and rel.familiarity <= 1:
            return "aap"

        # Camaraderie / shared danger -> Tum
        if rel.familiarity >= 2 and rel.hostility <= 1:
            return "tum"

        # Default fallback
        return rel.current_pronoun or "tum"

    @staticmethod
    def resolve_hindi_pronoun(rel: DynamicRelationshipState) -> str:
        """Alias for resolve_pronoun_level."""
        return RelationshipStateEngine.resolve_pronoun_level(rel)

    @staticmethod
    def resolve_vocabulary_register(rel: DynamicRelationshipState) -> str:
        """Resolves vocabulary register based on current interpersonal dimensions."""
        if rel.hostility >= 3 or rel.trust <= -1:
            return "hostile_street"
        if (rel.intimacy >= 3 and rel.familiarity >= 3) or (rel.intimacy >= 2 and rel.familiarity >= 4 and rel.trust >= 2):
            return "intimate_warm"
        if (rel.respect >= 3 and rel.familiarity <= 1) or rel.fear >= 4 or rel.authority_differential <= -3:
            return "formal_respectful"
        return "casual_colloquial"

    @staticmethod
    def compute_contextual_prior_deltas(
        rel: Optional[DynamicRelationshipState] = None,
        interaction_type: str = "other",
        importance: int = 3,
        explicit_overrides: Optional[Dict[str, int]] = None,
        existing_rel: Optional[DynamicRelationshipState] = None,
        event_importance: Optional[int] = None,
        explicit_deltas: Optional[Dict[str, int]] = None,
    ) -> Dict[str, int]:
        """
        Computes bounded heuristic adjustments using interaction priors modulated by
        existing relationship state and event importance.
        """
        target_rel = rel or existing_rel or DynamicRelationshipState(speaker="A", target="B")
        eff_importance = event_importance if event_importance is not None else importance
        overrides = explicit_overrides or explicit_deltas

        base_prior = dict(RELATIONSHIP_INTERACTION_PRIORS.get(interaction_type.lower(), {}))
        if overrides:
            alias_map = {
                "tension": "hostility",
                "affection": "intimacy",
                "power_balance": "authority_differential",
            }
            for k, v in overrides.items():
                canon_k = alias_map.get(k, k)
                base_prior[canon_k] = int(v)

        adjusted: Dict[str, int] = {}
        for dim, raw_delta in base_prior.items():
            if raw_delta == 0:
                continue
            val = raw_delta
            if dim == "trust" and interaction_type.lower() == "betrayal":
                if target_rel.trust >= 3 and eff_importance >= 4:
                    val = min(-3, raw_delta)
                elif target_rel.trust <= 1:
                    val = -1
            elif dim == "hostility" and target_rel.trust >= 4 and target_rel.familiarity >= 4 and eff_importance <= 2:
                val = max(0, raw_delta - 1)

            max_step = 3 if eff_importance >= 5 else 2
            val = max(-max_step, min(max_step, int(val)))
            if val != 0:
                adjusted[dim] = val
        return adjusted

    @staticmethod
    def apply_relationship_mutation(
        rel: DynamicRelationshipState,
        deltas: Dict[str, int],
        event_id: str,
        chapter: int = 1,
        scene: Optional[str] = None,
        notes: str = "",
    ) -> DynamicRelationshipState:
        """
        Deterministically applies evidence-backed relationship deltas, clamps bounds,
        updates pronouns/register, and logs event provenance.
        """
        if not event_id or not event_id.strip():
            raise ValueError("Every relationship mutation requires a non-empty source event_id for evidence tracking.")

        updated = rel.model_copy(deep=True)
        applied_changes: Dict[str, Tuple[int, int]] = {}

        alias_map = {
            "tension": "hostility",
            "affection": "intimacy",
            "power_balance": "authority_differential",
        }
        valid_dims = {
            "respect": (-5, 5),
            "familiarity": (0, 5),
            "hostility": (0, 5),
            "intimacy": (0, 5),
            "authority_differential": (-5, 5),
            "fear": (0, 5),
            "trust": (-5, 5),
        }

        for raw_dim, delta_val in deltas.items():
            dim = alias_map.get(raw_dim, raw_dim)
            if dim not in valid_dims or delta_val == 0:
                continue
            low, high = valid_dims[dim]
            old_v = getattr(updated, dim)
            new_v = max(low, min(high, old_v + int(delta_val)))
            if new_v != old_v:
                setattr(updated, dim, new_v)
                applied_changes[dim] = (old_v, new_v)


        if event_id not in updated.evidence_event_ids:
            updated.evidence_event_ids.append(event_id)

        updated.current_pronoun = RelationshipStateEngine.resolve_pronoun_level(updated)
        updated.current_vocabulary_register = RelationshipStateEngine.resolve_vocabulary_register(updated)
        updated.last_updated_chapter = chapter
        if scene:
            updated.last_updated_scene = scene
        if notes:
            updated.recent_interaction_notes = notes

        if applied_changes or notes:
            updated.mutation_history.append({
                "event_id": event_id,
                "chapter": chapter,
                "scene": scene,
                "changes": {k: {"from": v[0], "to": v[1]} for k, v in applied_changes.items()},
                "resolved_pronoun": updated.current_pronoun,
                "notes": notes,
            })

        return updated

    @staticmethod
    def get_relationship_prompt_guidelines(
        speaker: str,
        target: str,
        rel: Optional[DynamicRelationshipState] = None
    ) -> str:
        """Formats dynamic relationship guidelines for translation prompts."""
        if not rel:
            return f"- Interaction [{speaker} -> {target}]: Default polite 'tum' with balanced respect."

        resolved_pronoun = RelationshipStateEngine.resolve_pronoun_level(rel)
        tone_descriptor = []
        if rel.hostility >= 3:
            tone_descriptor.append("tense/hostile")
        if rel.intimacy >= 3:
            tone_descriptor.append("intimate/somatically close")
        if rel.respect >= 4:
            tone_descriptor.append("reverent/respectful")
        if rel.fear >= 3:
            tone_descriptor.append("intimidated/guarded")
        if not tone_descriptor:
            tone_descriptor.append("natural conversational")

        tone_str = ", ".join(tone_descriptor)
        return (
            f"- INTERACTION [{speaker} addresses {target}]:\n"
            f"  * Mandatory Pronoun: '{resolved_pronoun}'\n"
            f"  * Dynamic Stance: {tone_str}\n"
            f"  * Interpersonal Tone: Respect {rel.respect}/5, Familiarity {rel.familiarity}/5, Hostility {rel.hostility}/5, Trust {rel.trust}/5\n"
            f"  * Invariant: Never artificially polite if hostile, and never dismissive if addressing high status."
        )
