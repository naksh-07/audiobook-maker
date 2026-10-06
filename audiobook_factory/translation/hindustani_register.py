#!/usr/bin/env python3
"""
Audiobook Factory - Hindustani Literary Register Engine.
Implements the 'Aate mein Namak jitni Urdu' principle: natural contextual seasoning
rather than an arbitrary mechanical 10% quota.
Ensures organic Hindustani literary texture grounded in a strong Hindi foundation.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Set, Tuple, Optional
from pydantic import BaseModel, Field


class HindustaniRegisterSpec(BaseModel):
    atmosphere_words: List[str] = [
        "सन्नाटा", "ख़ामोशी", "दस्तक", "सिहरन", "अंधेरा", "गूंज", "वीरान", "ख़ौफ़"
    ]
    passion_and_somatics: List[str] = [
        "सुकून", "तन्हाई", "बेचैनी", "तपिश", "सांसें", "धड़कन", "नशा"
    ]
    combat_and_grit: List[str] = [
        "ज़ख़्म", "दर्द", "आवाज़", "फ़ासला", "असर", "क़हर", "वार", "ख़ंजर"
    ]
    scholastic_and_courtly: List[str] = [
        "अदब", "तहज़ीब", "वजूद", "इल्म", "हुज़ूर", "सलाम", "हकीकत"
    ]


class HindustaniAuditResult(BaseModel):
    is_balanced: bool
    detected_seasoning_words: List[str]
    seasoning_density: float  # count per 100 words
    notes: List[str] = Field(default_factory=list)


class HindustaniRegisterEngine:
    def __init__(self, spec: Optional[HindustaniRegisterSpec] = None):
        self.spec = spec or HindustaniRegisterSpec()
        self._all_seasoning = set(
            self.spec.atmosphere_words +
            self.spec.passion_and_somatics +
            self.spec.combat_and_grit +
            self.spec.scholastic_and_courtly
        )

    @classmethod
    def from_book_dna(cls, book_dna: Dict[str, Any]) -> HindustaniRegisterEngine:
        """Constructs an engine directly tuned to the novel's DeepSearch DNA."""
        if not book_dna:
            return cls.from_genre("general")

        trad = str(book_dna.get("literary_tradition", "")).lower()
        era = str(book_dna.get("historical_era", "")).lower()

        if "rural" in trad or "awadh" in trad or "bhojpuri" in trad or "village" in era:
            return cls.from_genre("rural_historical")
        elif "sci" in trad or "cyber" in trad or "space" in era:
            return cls.from_genre("scifi")
        elif "period" in era or "19th" in era or "classic" in trad or "victorian" in trad:
            return cls.from_genre("history")
        elif "crime" in trad or "thriller" in trad or "noir" in trad:
            return cls.from_genre("thriller")
        return cls.from_genre("general")

    @classmethod
    def from_genre(cls, genre: str = "general") -> HindustaniRegisterEngine:
        """Constructs a genre-calibrated Hindustani register engine for ANY novel."""
        g = genre.lower()
        if "rural" in g or "village" in g or "awadh" in g:
            spec = HindustaniRegisterSpec(
                atmosphere_words=["सन्नाटा", "चौपाल", "आँगन", "छाँव", "धूप", "सन्नाटा"],
                passion_and_somatics=["सुकून", "ममता", "पीड़ा", "धड़कन", "सांसें"],
                combat_and_grit=["लाठी", "ज़ख़्म", "दर्द", "मार", "चीख़"],
                scholastic_and_courtly=["बाबू", "मालिक", "हुज़ूर", "प्रणाम", "आशीर्वाद"],
            )
        elif "sci" in g or "cyber" in g or "space" in g:
            spec = HindustaniRegisterSpec(
                atmosphere_words=["तारीकी", "गर्दिश", "सन्नाटा", "वीरान", "ख़ामोशी", "फ़ासला"],
                passion_and_somatics=["सुकून", "तन्हाई", "बेख़ौफ़", "तपिश", "जिस्म"],
                combat_and_grit=["फ़ौलाद", "ज़ख़्म", "हैरत", "फ़ासला", "क़हर"],
                scholastic_and_courtly=["इल्म", "वजूद", "इल्हाम", "हकीकत"],
            )
        elif "history" in g or "period" in g or "classic" in g:
            spec = HindustaniRegisterSpec(
                atmosphere_words=["ख़ामोशी", "सन्नाटा", "दस्तक", "रूह", "तारीकी"],
                passion_and_somatics=["सुकून", "तन्हाई", "अफ़साने", "तपिश", "नशा"],
                combat_and_grit=["ख़ंजर", "ज़ख़्म", "शराब", "फ़ौलाद"],
                scholastic_and_courtly=["अदब", "तहज़ीब", "हुज़ूर", "सलाम", "इल्म", "वजूद"],
            )
        elif "thriller" in g or "crime" in g or "noir" in g:
            spec = HindustaniRegisterSpec(
                atmosphere_words=["सन्नाटा", "ख़ौफ़", "दस्तक", "तारीकी", "सिहरन"],
                passion_and_somatics=["बेख़ौफ़", "तन्हाई", "हवस", "तपिश", "शराब"],
                combat_and_grit=["ज़ख़्म", "ख़ंजर", "वहशी", "क़हर"],
                scholastic_and_courtly=["फ़रेब", "वजूद", "क़यामत"],
            )
        else:
            # Default balanced universal literary register
            spec = HindustaniRegisterSpec()
        return cls(spec=spec)

    def get_prompt_guidelines(self, scene_context: str = "") -> str:
        """Returns contextual guidance for prompts without forcing arbitrary quotas."""
        atmosphere_examples = ", ".join(f"'{w}'" for w in self.spec.atmosphere_words[:5])
        somatic_examples = ", ".join(f"'{w}'" for w in self.spec.passion_and_somatics[:5])
        grit_examples = ", ".join(f"'{w}'" for w in self.spec.combat_and_grit[:5])

        return (
            "HINDUSTANI LITERARY TEXTURE (आटे में नमक जितनी उर्दू):\n"
            "- Core Principle: Hindi serves as the solid narrative foundation, seasoned tastefully with evocative Urdu terms.\n"
            f"- Atmospheric Resonance: Use words like {atmosphere_examples} for quiet dread, tension, and ambient weight.\n"
            f"- Somatic Friction & Intimacy: Use words like {somatic_examples} for physical passion, breathing, and longing.\n"
            f"- Combat, Blade & Grit: Use words like {grit_examples} for wounds, steel, and brutality.\n"
            "- CRITICAL RULE: Never force an artificial 10% quota or inject high-flown Persianized words that sound alien. "
            "Let the scene's emotional gravity dictate the seasoning naturally."
        )

    def audit_text(self, devanagari_text: str) -> HindustaniAuditResult:
        """Audits translated Hindi text for healthy, organic Hindustani seasoning."""
        if not devanagari_text:
            return HindustaniAuditResult(is_balanced=True, detected_seasoning_words=[], seasoning_density=0.0)

        words = devanagari_text.split()
        word_count = len(words)
        if word_count == 0:
            return HindustaniAuditResult(is_balanced=True, detected_seasoning_words=[], seasoning_density=0.0)

        detected = []
        for word in self._all_seasoning:
            if word in devanagari_text:
                detected.append(word)

        density = (len(detected) / word_count) * 100.0
        notes = []

        # Check for excessive saturation (> 8% distinct keywords is often forced)
        if density > 8.0:
            notes.append(f"Heavy Urdu seasoning detected ({density:.1f}% density). Verify it does not sound theatrical or forced.")
        elif density < 0.2 and word_count > 300:
            notes.append(f"Very dry/Sanskritized register detected ({density:.1f}% density). Consider infusing more atmospheric Hindustani texture.")
        else:
            notes.append(f"Balanced Hindustani seasoning ({len(detected)} evocative terms across {word_count} words).")

        return HindustaniAuditResult(
            is_balanced=True,
            detected_seasoning_words=detected,
            seasoning_density=round(density, 2),
            notes=notes,
        )
