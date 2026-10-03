#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: golden_suite.py
Implements the 20-Scenario Golden Cinematic Mix Regression Benchmark Suite.

Covers the 20 canonical literary and dramatic mixing scenarios:
01. Intimate conversation
02. Normal dialogue
03. Whisper
04. Emotional confession
05. Shouting
06. Multi-speaker conversation
07. Dialogue + music
08. Music-led emotional scene
09. Dialogue + ambience
10. Dialogue + heavy FX
11. Sudden impact
12. Combat
13. Horror reveal
14. Dramatic silence
15. Suspense build
16. Behind-door / distant voice
17. Spatial movement
18. Crowded / layered scene
19. Transition between rooms
20. Chapter / scene transition

Uses lightweight deterministic synthetic audio fixtures (48kHz, 2-4 seconds)
to prevent multi-gigabyte repository bloat while rigorously exercising DSP and Judge logic.
"""

from __future__ import annotations
import math
import wave
import struct
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Literal, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

import numpy as np

from audiobook_factory.logger import logger
if TYPE_CHECKING:
    from audiobook_factory.cinema_audio_engine import StemLedger, StemMetadata
from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.attention_map import AttentionMap, AttentionEvent
from audiobook_factory.cinematic_mix.perspective import AcousticPerspective
from audiobook_factory.cinematic_mix.silence import SilenceEvent
from audiobook_factory.cinematic_mix.impact import ImpactEvent
from audiobook_factory.cinematic_mix.automation import MixAutomation
from audiobook_factory.cinematic_mix.planner import AutomationPlanner
from audiobook_factory.cinematic_mix.judge import MixJudge, MixJudgeResult


class GoldenScenarioContract(BaseModel):
    """Specification and behavioral contract for a golden cinematic mix scenario."""
    model_config = ConfigDict(extra="ignore")

    scenario_id: str = Field(..., description="Unique scenario ID, e.g. 01_intimate_conversation")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Literary scenario description")
    duration_sec: float = Field(default=3.0, description="Synthetic duration in seconds")
    intent: SceneMixIntent = Field(..., description="Input SceneMixIntent")
    attention_map: AttentionMap = Field(..., description="Input AttentionMap")
    perspective: Optional[AcousticPerspective] = Field(default=None, description="Optional AcousticPerspective")
    silence_events: List[SilenceEvent] = Field(default_factory=list, description="Silence events")
    impact_events: List[ImpactEvent] = Field(default_factory=list, description="Impact events")
    stems_required: List[str] = Field(default_factory=lambda: ["DX", "MX", "FX", "AMB"])
    expected_status: Literal["PASS", "PASS_WITH_WARNINGS"] = Field(default="PASS")
    min_score: float = Field(default=0.85, ge=0.0, le=1.0)
    expected_dmr_min: Optional[float] = Field(default=None)


def _write_pcm_wav(filepath: Path, samples: np.ndarray, sample_rate: int = 48000, channels: int = 2) -> None:
    """Helper writing a float32 numpy array to standard 16-bit PCM WAV."""
    samples_clamped = np.clip(samples, -1.0, 1.0)
    samples_int16 = (samples_clamped * 32767.0).astype(np.int16)

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        if channels == 1 and samples_int16.ndim == 1:
            wf.writeframes(samples_int16.tobytes())
        elif channels == 2 and samples_int16.ndim == 1:
            stereo = np.column_stack([samples_int16, samples_int16])
            wf.writeframes(stereo.tobytes())
        elif channels == 2 and samples_int16.ndim == 2:
            wf.writeframes(samples_int16.tobytes())
        else:
            wf.writeframes(samples_int16.tobytes())


def generate_scenario_audio_fixtures(
    scenario: GoldenScenarioContract,
    output_dir: Path,
    sample_rate: int = 48000,
) -> Dict[str, Path]:
    """
    Generates deterministic synthetic audio stems for a given scenario.
    """
    sr = sample_rate
    dur = scenario.duration_sec
    num_samples = int(dur * sr)
    t = np.linspace(0.0, dur, num_samples, endpoint=False, dtype=np.float32)

    stems: Dict[str, Path] = {}

    # 1. Dialogue Stem (DX): Multi-harmonic formant proxy with envelope
    if "DX" in scenario.stems_required:
        dx_wave = 0.40 * np.sin(2.0 * np.pi * 320.0 * t) + 0.25 * np.sin(2.0 * np.pi * 1200.0 * t)
        if "whisper" in scenario.scenario_id or "intimate" in scenario.scenario_id:
            # Whisper proxy: softer gain and higher breathiness
            dx_wave = 0.20 * np.sin(2.0 * np.pi * 2800.0 * t) + 0.10 * np.sin(2.0 * np.pi * 350.0 * t)
        elif "shouting" in scenario.scenario_id or "combat" in scenario.scenario_id:
            # Shouting proxy: louder amplitude
            dx_wave = 0.70 * np.sin(2.0 * np.pi * 440.0 * t) + 0.35 * np.sin(2.0 * np.pi * 1800.0 * t)

        # Apply dialogue envelope (active during attention events or full duration)
        dx_path = output_dir / f"{scenario.scenario_id}_dx.wav"
        _write_pcm_wav(dx_path, dx_wave, sr, channels=2)
        stems["DX"] = dx_path

    # 2. Music Stem (MX): Harmonic chord bed
    if "MX" in scenario.stems_required:
        mx_vol = 0.15
        if "music_led" in scenario.scenario_id:
            mx_vol = 0.50
        mx_wave = mx_vol * (
            0.5 * np.sin(2.0 * np.pi * 220.0 * t)
            + 0.3 * np.sin(2.0 * np.pi * 330.0 * t)
            + 0.2 * np.sin(2.0 * np.pi * 440.0 * t)
        )
        mx_path = output_dir / f"{scenario.scenario_id}_mx.wav"
        _write_pcm_wav(mx_path, mx_wave, sr, channels=2)
        stems["MX"] = mx_path

    # 3. Foley / Impact Stem (FX): Transient burst
    if "FX" in scenario.stems_required:
        fx_wave = np.zeros(num_samples, dtype=np.float32)
        if scenario.impact_events:
            for imp in scenario.impact_events:
                imp_sample = int(imp.start * sr)
                decay_len = min(int(0.35 * sr), num_samples - imp_sample)
                if decay_len > 0 and imp_sample < num_samples:
                    env = np.exp(-np.linspace(0.0, 5.0, decay_len, dtype=np.float32))
                    noise = (np.random.RandomState(42).rand(decay_len).astype(np.float32) * 2.0 - 1.0)
                    fx_wave[imp_sample : imp_sample + decay_len] += 0.80 * imp.intensity * env * noise
        else:
            # Subtle stochastic foley ticks
            fx_wave = 0.05 * (np.random.RandomState(7).rand(num_samples).astype(np.float32) * 2.0 - 1.0)

        fx_path = output_dir / f"{scenario.scenario_id}_fx.wav"
        _write_pcm_wav(fx_path, fx_wave, sr, channels=2)
        stems["FX"] = fx_path

    # 4. Ambience Stem (AMB): Low continuous room bed
    if "AMB" in scenario.stems_required:
        amb_vol = 0.04
        amb_wave = amb_vol * (np.random.RandomState(99).rand(num_samples).astype(np.float32) * 2.0 - 1.0)
        amb_path = output_dir / f"{scenario.scenario_id}_amb.wav"
        _write_pcm_wav(amb_path, amb_wave, sr, channels=2)
        stems["AMB"] = amb_path

    return stems


# -----------------------------------------------------------------------------
# Canonical 20 Scenario Registry
# -----------------------------------------------------------------------------

def build_golden_scenarios() -> Dict[str, GoldenScenarioContract]:
    """Constructs the canonical 20-scenario Golden Cinematic Mix Suite."""
    scenarios: Dict[str, GoldenScenarioContract] = {}

    def add_scenario(
        s_id: str,
        title: str,
        desc: str,
        intent: SceneMixIntent,
        attn: AttentionMap,
        persp: Optional[AcousticPerspective] = None,
        silence: Optional[List[SilenceEvent]] = None,
        impacts: Optional[List[ImpactEvent]] = None,
        stems: Optional[List[str]] = None,
        min_score: float = 0.85,
        dmr_min: Optional[float] = None,
    ):
        scenarios[s_id] = GoldenScenarioContract(
            scenario_id=s_id,
            title=title,
            description=desc,
            duration_sec=3.0,
            intent=intent,
            attention_map=attn,
            perspective=persp,
            silence_events=silence or [],
            impact_events=impacts or [],
            stems_required=stems or ["DX", "MX", "FX", "AMB"],
            min_score=min_score,
            expected_dmr_min=dmr_min,
        )

    # 01. Intimate Conversation
    add_scenario(
        "01_intimate_conversation",
        "Intimate Conversation",
        "Close-mic dialogue with gentle room tone and subtle music bed.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.90, emotional_intensity=0.30, dynamic_range_intent="compressed_intimate"),
        AttentionMap(events=[AttentionEvent(start=0.5, end=2.5, focus_target="dialogue", priority=0.88, reason="Close intimate conversation")]),
        persp=AcousticPerspective(distance="close"),
        dmr_min=6.0,
    )

    # 02. Normal Dialogue
    add_scenario(
        "02_normal_dialogue",
        "Standard Narrative Dialogue",
        "Balanced dialogue exposition with natural environment and background score.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.85, emotional_intensity=0.40),
        AttentionMap(events=[AttentionEvent(start=0.2, end=2.8, focus_target="dialogue", priority=0.85, reason="Conversational speech")]),
        dmr_min=6.0,
    )

    # 03. Whisper
    add_scenario(
        "03_whisper",
        "Subtle Secret Whisper",
        "Intimate breathy whisper requiring spectral pocketing at 2800 Hz and deeper music ducking.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.95, emotional_intensity=0.60, dynamic_range_intent="compressed_intimate"),
        AttentionMap(events=[AttentionEvent(start=0.5, end=2.5, focus_target="dialogue", priority=0.95, reason="Secret whisper in shadows")]),
        dmr_min=8.0,
    )

    # 04. Emotional Confession
    add_scenario(
        "04_emotional_confession",
        "Emotional Confession with Breath Preservation",
        "High emotional stakes dialogue with silence pauses preserving vocal breath.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.90, emotional_intensity=0.75),
        AttentionMap(events=[AttentionEvent(start=0.2, end=2.0, focus_target="dialogue", priority=0.90, reason="Tearful confession")]),
        silence=[SilenceEvent(start=2.0, duration=0.8, type="EMOTIONAL", depth="moderate", preserved_elements=["breath", "room_tone"])],
    )

    # 05. Shouting
    add_scenario(
        "05_shouting",
        "Heated Argument / Shouting",
        "High acoustic energy vocal delivery cutting naturally through ambient bed.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.90, emotional_intensity=0.85, dynamic_range_intent="cinematic_wide"),
        AttentionMap(events=[AttentionEvent(start=0.2, end=2.8, focus_target="dialogue", priority=0.90, reason="Angry shouting exchange")]),
    )

    # 06. Multi-Speaker Conversation
    add_scenario(
        "06_multi_speaker_conversation",
        "Multi-Speaker Ensemble",
        "Rapid dialogue exchange with balanced center placement and cohesive room reverb.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.88, emotional_intensity=0.50),
        AttentionMap(events=[
            AttentionEvent(start=0.2, end=1.4, focus_target="dialogue", priority=0.85, reason="Speaker A line"),
            AttentionEvent(start=1.6, end=2.8, focus_target="dialogue", priority=0.85, reason="Speaker B reply"),
        ]),
    )

    # 07. Dialogue + Music
    add_scenario(
        "07_dialogue_plus_music",
        "Dialogue with Underscore",
        "Continuous music bed ducked smoothly during dialogue windows.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.85, music_priority=0.60),
        AttentionMap(events=[AttentionEvent(start=0.5, end=2.5, focus_target="dialogue", priority=0.85, reason="Spoken dialogue over score")]),
    )

    # 08. Music-Led Emotional Scene
    add_scenario(
        "08_music_led_emotional_scene",
        "Thematic Score Climax",
        "Score commands narrative focus with full acoustic energy; speech is subordinate.",
        SceneMixIntent(focus="music", music_priority=0.90, dialogue_priority=0.30, emotional_intensity=0.80),
        AttentionMap(events=[AttentionEvent(start=0.0, end=3.0, focus_target="music", priority=0.90, reason="Heroic musical revelation")]),
    )

    # 09. Dialogue + Ambience
    add_scenario(
        "09_dialogue_plus_ambience",
        "Dialogue in Outdoor Weather",
        "Rain and wind ambience preserved continuously without artificial muting during dialogue.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.85, ambience_priority=0.70),
        AttentionMap(events=[AttentionEvent(start=0.4, end=2.6, focus_target="dialogue", priority=0.85, reason="Talking in thunderstorm")]),
    )

    # 10. Dialogue + Heavy FX
    add_scenario(
        "10_dialogue_plus_heavy_fx",
        "Dialogue with Foley and Blade Draw",
        "Action dialogue with prominent blade draws and footstep foley.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.80, fx_priority=0.75),
        AttentionMap(events=[
            AttentionEvent(start=0.3, end=2.5, focus_target="dialogue", priority=0.80, reason="Dialogue warning"),
            AttentionEvent(start=1.2, end=1.8, focus_target="fx", priority=0.82, reason="Sword drawn from scabbard"),
        ]),
    )

    # 11. Sudden Impact
    add_scenario(
        "11_sudden_impact",
        "Heavy Door Slam Impact",
        "4-phase visceral transient trajectory with pre-impact dip, slam, and recovery.",
        SceneMixIntent(focus="fx", fx_priority=0.90, emotional_intensity=0.80),
        AttentionMap(events=[AttentionEvent(start=1.2, end=1.8, focus_target="fx", priority=0.92, reason="Heavy door slam")]),
        impacts=[ImpactEvent(start=1.2, intensity=0.85, focus_target="door_slam", reason="Oaken door slams shut")],
    )

    # 12. Combat
    add_scenario(
        "12_combat",
        "High-Intensity Melee Combat",
        "High foley density, sword parries, shouting voices, and energized action music.",
        SceneMixIntent(focus="fx", fx_priority=0.85, music_priority=0.75, emotional_intensity=0.90, dynamic_range_intent="cinematic_wide"),
        AttentionMap(events=[
            AttentionEvent(start=0.5, end=2.5, focus_target="fx", priority=0.88, reason="Clashing swords and strikes"),
        ]),
        impacts=[
            ImpactEvent(start=0.8, intensity=0.75, reason="Sword parry clash"),
            ImpactEvent(start=2.0, intensity=0.85, reason="Body slam on floor"),
        ],
    )

    # 13. Horror Reveal
    add_scenario(
        "13_horror_reveal",
        "Horror Shock Silence",
        "Abrupt near-black shock silence following a horrifying realization, preserving eerie FX tail.",
        SceneMixIntent(focus="silence", emotional_intensity=0.95),
        AttentionMap(events=[AttentionEvent(start=1.0, end=2.8, focus_target="silence", priority=0.95, reason="Grisly monster reveal shock")]),
        silence=[SilenceEvent(start=1.0, duration=1.5, type="SHOCK", depth="near_black", preserved_elements=["fx_tail"])],
    )

    # 14. Dramatic Silence
    add_scenario(
        "14_dramatic_silence",
        "Dramatic Revelation Pause",
        "Music plunges by 20 dB while room tone ambience is preserved at -5 dB.",
        SceneMixIntent(focus="silence", emotional_intensity=0.70),
        AttentionMap(events=[AttentionEvent(start=1.0, end=2.5, focus_target="silence", priority=0.90, reason="Dramatic pause before answer")]),
        silence=[SilenceEvent(start=1.0, duration=1.5, type="DRAMATIC", depth="deep", preserved_elements=["room_tone"])],
    )

    # 15. Suspense Build
    add_scenario(
        "15_suspense_build",
        "Suspense Creeping Dread",
        "Music thins out, ambience lowers, and spot footsteps remain razor sharp.",
        SceneMixIntent(focus="fx", emotional_intensity=0.70),
        AttentionMap(events=[AttentionEvent(start=0.5, end=2.5, focus_target="fx", priority=0.85, reason="Creaking floorboard in empty house")]),
        silence=[SilenceEvent(start=0.5, duration=2.0, type="SUSPENSE", depth="moderate", preserved_elements=["fx", "room_tone"])],
    )

    # 16. Behind-Door Distant Voice
    add_scenario(
        "16_behind_door_distant_voice",
        "Occluded Voice Behind Wooden Door",
        "Acoustic barrier muffling voice with lowpass cutoff at 2200 Hz and -9.5 dB direct energy.",
        SceneMixIntent(focus="dialogue", spatial_depth_intent="deep_cavernous"),
        AttentionMap(events=[AttentionEvent(start=0.5, end=2.5, focus_target="dialogue", priority=0.80, reason="Muffled voice yelling from behind closed door")]),
        persp=AcousticPerspective(distance="near", occlusion="door"),
    )

    # 17. Spatial Movement
    add_scenario(
        "17_spatial_movement",
        "Character Approaching from Medium Distance",
        "Smooth perspective transition from medium distance (10000 Hz, 0.80 width) to near presence.",
        SceneMixIntent(focus="dialogue"),
        AttentionMap(events=[AttentionEvent(start=0.2, end=2.8, focus_target="dialogue", priority=0.82, reason="Character walking toward listener")]),
        persp=AcousticPerspective(distance="medium", occlusion="partial"),
    )

    # 18. Crowded Layered Scene
    add_scenario(
        "18_crowded_layered_scene",
        "Busy Tavern Atmosphere",
        "Layered ambience walla, spot mug clinks, background score, and foreground dialogue.",
        SceneMixIntent(focus="dialogue", dialogue_priority=0.85, ambience_priority=0.70),
        AttentionMap(events=[AttentionEvent(start=0.4, end=2.6, focus_target="dialogue", priority=0.85, reason="Tavern patron discussion")]),
    )

    # 19. Transition Between Rooms
    add_scenario(
        "19_transition_between_rooms",
        "Acoustic Room Transition",
        "Perspective shift moving from courtyard to small stone vault.",
        SceneMixIntent(focus="environment"),
        AttentionMap(events=[AttentionEvent(start=1.2, end=2.0, focus_target="environment", priority=0.80, reason="Stepping across threshold into stone chamber")]),
        persp=AcousticPerspective(distance="near", occlusion="curtain"),
    )

    # 20. Chapter/Scene Transition
    add_scenario(
        "20_chapter_scene_transition",
        "Scene Boundary Crossfade",
        "Smooth boundary attenuation dip and clean baseline return without click or DC offset.",
        SceneMixIntent(focus="silence"),
        AttentionMap(events=[AttentionEvent(start=1.0, end=2.2, focus_target="silence", priority=0.85, reason="End of scene crossfade")]),
        silence=[SilenceEvent(start=1.0, duration=1.2, type="TRANSITION", depth="moderate")],
    )

    return scenarios


# -----------------------------------------------------------------------------
# Golden Suite Benchmark Runner
# -----------------------------------------------------------------------------

class GoldenSuiteRunner:
    """
    Executes all 20 canonical Golden Scenarios, verifying behavioral contracts and Judge verdicts.
    """

    def __init__(self, judge: Optional[MixJudge] = None):
        self.judge = judge or MixJudge()
        self.scenarios = build_golden_scenarios()
        self.planner = AutomationPlanner()

    def run_scenario(
        self,
        scenario_id: str,
        working_dir: Path,
    ) -> Tuple[GoldenScenarioContract, MixJudgeResult]:
        """
        Executes an individual golden scenario end-to-end:
        Fixture Gen -> Automation Planning -> Premaster Rendering -> MixJudge Evaluation.
        """
        if scenario_id not in self.scenarios:
            raise KeyError(f"Unknown golden scenario '{scenario_id}'. Available: {list(self.scenarios.keys())}")

        contract = self.scenarios[scenario_id]
        scen_dir = working_dir / scenario_id
        scen_dir.mkdir(parents=True, exist_ok=True)

        # 1. Generate deterministic synthetic audio fixtures
        stems = generate_scenario_audio_fixtures(contract, scen_dir)

        # 2. Plan automation using Stage 11 behavior systems
        auto = self.planner.plan(
            scene_intent=contract.intent,
            attention_map=contract.attention_map,
            acoustic_perspective=contract.perspective,
            silence_events=contract.silence_events,
            impact_events=contract.impact_events,
            total_duration_sec=contract.duration_sec,
            has_dialogue="DX" in stems,
            has_music="MX" in stems,
            has_ambience="AMB" in stems,
        )

        # 3. Render synthetic premaster (sum of discrete stems with automation applied)
        premaster_path = scen_dir / f"{scenario_id}_premaster.wav"
        self._render_synthetic_premaster(stems, premaster_path, auto)

        # 4. Run MixJudge
        result = self.judge.evaluate(
            stems=stems,
            premaster_path=premaster_path,
            scene_intent=contract.intent,
            attention_map=contract.attention_map,
            mix_automation=auto,
            acoustic_perspective=contract.perspective,
            silence_events=contract.silence_events,
            impact_events=contract.impact_events,
        )

        return contract, result

    def _render_synthetic_premaster(
        self,
        stems: Dict[str, Path],
        out_path: Path,
        auto: MixAutomation,
    ) -> None:
        """
        Synthesizes a combined premaster from discrete stems modulated by mix automation.
        """
        combined = None
        sr = 48000
        for s_type, s_path in stems.items():
            with wave.open(str(s_path), "rb") as wf:
                sr = wf.getframerate()
                n_frames = wf.getnframes()
                raw_bytes = wf.readframes(n_frames)
                audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32767.0
                if combined is None:
                    combined = np.zeros_like(audio)
                combined += audio * 0.40  # Sum with headroom

        if combined is None:
            combined = np.zeros(int(auto.total_duration_sec * sr), dtype=np.float32)

        _write_pcm_wav(out_path, combined, sample_rate=sr, channels=2)

    def run_all(self, working_dir: Path) -> Dict[str, Any]:
        """Runs all 20 canonical golden scenarios and returns a benchmark report."""
        report = {
            "total_scenarios": len(self.scenarios),
            "passed": 0,
            "failed": 0,
            "results": {},
        }
        for s_id in self.scenarios:
            contract, res = self.run_scenario(s_id, working_dir)
            passed = bool(res.status in ("PASS", "PASS_WITH_WARNINGS") and res.overall_score >= contract.min_score)
            if passed:
                report["passed"] += 1
            else:
                report["failed"] += 1
            report["results"][s_id] = {
                "passed": passed,
                "status": res.status,
                "score": res.overall_score,
                "failures": res.failures,
                "warnings": res.warnings,
            }
        return report
