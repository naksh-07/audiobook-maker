"""
Audiobook Factory: Production-grade End-to-End Audiobook Production System.
Primary TTS: Google Gemini Flash TTS Cloud API (Aoede/Charon/Kore/Puck).
Emergency Fallback: Kokoro & Goonj-1-82M on PC / Laptop RTX 4050 Workstation.
Soundscape: Scene Mood Detection, MusicGen / Procedural BGM & Dynamic Sidechain Ducking.
Production Mode: Interactive Antigravity AI Director & Copilot.
"""

from .extractor import process_book_file
from .translator import translate_book_project
from .script_builder import generate_project_scripts
from .tts_dispatcher import TTSDispatcher
from .soundscape import detect_chapter_mood, generate_procedural_ambient_bed, apply_dynamic_sidechain_ducking
from .mastering import concatenate_and_master_chapter
from .packager import package_m4b_audiobook

__version__ = "1.1.0"
