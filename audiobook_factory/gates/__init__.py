#!/usr/bin/env python3
"""
Audiobook Factory - Quality Gates Package (Gates 0 - 6).
Provides modular, independent verification gates across the entire studio production pipeline:
- Literary & Anti-Censorship: Gate 0, Gate 1, Profanity/Combat/Intimacy Agents
- Screenplay & Dramaturgy: Gate 2, Gate 2 (tags), Gate 2.5, Gate 2.8, Gate 3
- Acoustic & DSP Mastering: Gate 3.5, Gate 4, Gate 5, Gate 5.2, Gate 5.3
- Album & Container: Gate 6A, Gate 6B, Gate 6C, Gate 6D
- Orchestrators: audit_chapter_gates, audit_book_master
"""

from __future__ import annotations

from audiobook_factory.gates.contracts import (
    GateAuditError,
    AuditResult,
)
from audiobook_factory.gates.literary import (
    audit_gate0_translation,
    audit_gate1_roster,
    _audit_profanity_agent,
    _audit_combat_agent,
    _audit_intimacy_agent,
    audit_gate1_anticensorship_agent,
)
from audiobook_factory.gates.screenplay import (
    audit_gate2_script,
    audit_gate2_screenplay_tags,
    audit_gate2_5_dramatic_fidelity,
    audit_gate2_8_performance_fidelity,
    audit_gate3_scenes,
)
from audiobook_factory.gates.acoustics import (
    audit_gate3_5_acoustic_feasibility,
    audit_gate4_ledger,
    audit_gate5_master,
    audit_gate5_2_spectral_masking,
    audit_gate5_3_stereo_phase,
)
from audiobook_factory.gates.album import (
    audit_gate6a_voice_continuity,
    audit_gate6b_loudness_continuity,
    audit_gate6c_toc_integrity,
    audit_gate6c_toc_monotonicity,
    audit_gate6d_packaging_specs,
)
from audiobook_factory.gates.orchestrator import (
    audit_chapter_gates,
    audit_book_master,
)

__all__ = [
    "GateAuditError",
    "AuditResult",
    "audit_gate0_translation",
    "audit_gate1_roster",
    "_audit_profanity_agent",
    "_audit_combat_agent",
    "_audit_intimacy_agent",
    "audit_gate1_anticensorship_agent",
    "audit_gate2_script",
    "audit_gate2_screenplay_tags",
    "audit_gate2_5_dramatic_fidelity",
    "audit_gate2_8_performance_fidelity",
    "audit_gate3_scenes",
    "audit_gate3_5_acoustic_feasibility",
    "audit_gate4_ledger",
    "audit_gate5_master",
    "audit_gate5_2_spectral_masking",
    "audit_gate5_3_stereo_phase",
    "audit_gate6a_voice_continuity",
    "audit_gate6b_loudness_continuity",
    "audit_gate6c_toc_integrity",
    "audit_gate6c_toc_monotonicity",
    "audit_gate6d_packaging_specs",
    "audit_chapter_gates",
    "audit_book_master",
]
