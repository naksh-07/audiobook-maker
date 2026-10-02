"""
Audiobook Factory - Orchestration Support Package.
Deconstructs monolithic orchestrator workflows into modular gate auditing,
pipeline coordination, and auto-janitor submodules.
"""

from audiobook_factory.orchestration.gates import (
    verify_pre_synthesis_gates,
    verify_performance_fidelity_gate,
    verify_acoustic_feasibility_gate,
    verify_post_mix_master_gates,
    verify_translation_coverage_gates,
    verify_screenplay_project_gates,
    verify_packaging_gates,
)
from audiobook_factory.orchestration.janitor import cleanup_chapter_chunks
from audiobook_factory.orchestration.dialogue_runner import process_and_master_dialogue_stem

__all__ = [
    "verify_pre_synthesis_gates",
    "verify_performance_fidelity_gate",
    "verify_acoustic_feasibility_gate",
    "verify_post_mix_master_gates",
    "verify_translation_coverage_gates",
    "verify_screenplay_project_gates",
    "verify_packaging_gates",
    "cleanup_chapter_chunks",
    "process_and_master_dialogue_stem",
]
