"""
Audiobook Factory: Production-grade End-to-End Audiobook Production System.
Primary TTS: Google Gemini 3.1 Flash TTS Cloud API (Aoede/Charon/Kore/Puck/Fenrir/Zephyr).
Soundscape: Scene Mood Detection, Procedural BGM & Dynamic Sidechain Ducking.
Platform: High-Performance PC Workstation (Windows/Linux).
"""

import os
from pathlib import Path


def _load_env_file():
    """Load .env variables into os.environ with zero external dependencies."""
    cwd = Path.cwd()
    pkg_root = Path(__file__).resolve().parent.parent
    candidates = [cwd / ".env", pkg_root / ".env"]
    for env_path in candidates:
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = val
            break


_load_env_file()

from .extractor import (
    process_book_file,
    extract_chapters,
    split_large_chapter_on_semantic_boundary,
)
from .translator import (
    translate_book_project,
    normalize_translated_lexicon,
)
from .script_builder import (
    generate_project_scripts,
    build_dramatized_script_llm,
    build_narrator_script,
)
from .tts_dispatcher import TTSDispatcher, UnregisteredSpeakerError, probe_key_health
from .soundscape import (
    detect_chapter_mood,
    resolve_ambient_score,
    generate_chapter_soundscape_plan,
    render_chapter_soundscape,
    generate_project_soundscapes,
    apply_dynamic_sidechain_ducking,
    render_multitrack_chapter_audio,
    get_sound_bank,
    attenuate_foley_whisper_collisions,
)
from .mastering import concatenate_and_master_chapter
from .packager import package_m4b_audiobook
from .sound_bank import SoundBank
from .logger import logger
from .state import ProjectStateLedger
from .orchestrator import PipelineOrchestrator
from .contracts import (
    ProjectConfig,
    CharacterProfile,
    CharacterRoster,
    SceneSource,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    CreativeManifest,
    ManifestValidationError,
    BookPackagingSpecs,
    BookChapterMarker,
    BookTableOfContents,
    BookVoiceRoster,
    GlobalLoreBible,
    BookMasterManifest,
    MasteringSettings,
)
from .agent_director import AgentDirector
from .cinema_audio_engine import (
    render_discrete_stems,
    CinemaAudioManifest,
    StemMetadata,
    StemLedger,
)
from .sonic_bible import SonicBible, LeitmotifDefinition
from .manifest_renderer import render_manifest_soundscape, assemble_master_filter_graph, get_reverb_filter_string
from .sound_bank_ingest import UniversalSoundBankIngester
from .gate_auditor import (
    AuditResult,
    GateAuditError,
    audit_chapter_gates,
    audit_gate0_translation,
    audit_gate1_roster,
    audit_gate2_script,
    audit_gate3_5_acoustic_feasibility,
    audit_gate5_master,
    audit_gate5_2_spectral_masking,
    audit_gate5_3_stereo_phase,
    audit_gate6a_voice_continuity,
    audit_gate6b_loudness_continuity,
    audit_gate6c_toc_integrity,
    audit_gate6c_toc_monotonicity,
    audit_gate6d_packaging_specs,
    audit_book_master,
)

__version__ = "4.0.0b1"


