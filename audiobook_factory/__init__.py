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

from .extractor import process_book_file
from .translator import translate_book_project
from .script_builder import generate_project_scripts
from .tts_dispatcher import TTSDispatcher
from .soundscape import (
    detect_chapter_mood,
    generate_procedural_ambient_bed,
    resolve_ambient_score,
    generate_chapter_soundscape_plan,
    render_chapter_soundscape,
    generate_project_soundscapes,
    apply_dynamic_sidechain_ducking,
)
from .mastering import concatenate_and_master_chapter
from .packager import package_m4b_audiobook
from .sound_bank import SoundBank
from .logger import logger
from .state import ProjectStateLedger
from .orchestrator import PipelineOrchestrator

__version__ = "2.0.0"
