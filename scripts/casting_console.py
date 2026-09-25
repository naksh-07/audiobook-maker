#!/usr/bin/env python3
"""
Audiobook Factory - Human Casting Console (CLI).
Interactive CLI for audio directors and casting engineers to explore candidates,
review multi-dimensional radar scores, generate 10-mode audition packs,
lock voice assignments, and execute audit-compliant recasting with audio invalidation.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from audiobook_factory.logger import logger
from audiobook_factory.casting import (
    CharacterCastingProfile,
    VoiceCandidateEngine,
    VoiceAuditionEngine,
    CastLockManager,
)


def load_project_roster(project_dir: Path) -> Dict[str, Any]:
    """Loads character roster from project directory."""
    for p in (project_dir / "character_roster.json", project_dir / "translation" / "character_roster.json"):
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            chars = data.get("characters", data)
            if isinstance(chars, dict):
                return chars
            elif isinstance(chars, list):
                res = {}
                for c in chars:
                    name = c.get("display_name") or c.get("english_name") or c.get("name")
                    if name:
                        res[name] = c
                return res
    return {}


def cmd_list_voices(catalog_path: Optional[Path] = None) -> None:
    """Lists all voices available in the casting catalog."""
    engine = VoiceCandidateEngine(catalog_path)
    voices = engine.catalog.get("voices", {})
    if not voices:
        print("[!] No voices found in catalog.")
        return

    print("=" * 90)
    print(f"{'VOICE ID':<14} | {'GENDER':<8} | {'TIMBRE':<12} | {'AGE':<14} | {'PITCH':<12} | {'ARCHETYPES'}")
    print("-" * 90)
    for vid, vdata in sorted(voices.items()):
        gender = vdata.get("gender", "neutral")
        timbre = vdata.get("timbre", "natural")
        age = vdata.get("perceived_age", "prime_adult")
        pitch = vdata.get("pitch_band", "medium")
        archetypes = ", ".join(vdata.get("best_fit_archetypes", [])[:3])
        print(f"{vid:<14} | {gender:<8} | {timbre:<12} | {age:<14} | {pitch:<12} | {archetypes}")
    print("=" * 90)
    print(f"Total catalog voices: {len(voices)}")


def cmd_status(project_dir: Path) -> None:
    """Displays project casting status, locked cast, and registry synchronization."""
    lock_mgr = CastLockManager(project_dir)
    roster = load_project_roster(project_dir)
    reg_file = project_dir / "voice_registry.json"
    registry = {}
    if reg_file.exists():
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception:
            pass

    locks = lock_mgr.manifest.locks
    all_names = sorted(set(list(roster.keys()) + [l.character_name for l in locks.values()] + list(registry.keys())))

    print("=" * 95)
    print(f"PROJECT CASTING STATUS: {project_dir.resolve().name}")
    print("=" * 95)
    print(f"{'CHARACTER':<24} | {'LOCK STATUS':<12} | {'LOCKED VOICE':<14} | {'REGISTRY VOICE':<15} | {'EVIDENCE'}")
    print("-" * 95)

    for name in all_names:
        if name in ("Narrator", "Foley"):
            continue
        lk = lock_mgr.get_lock(name)
        status_str = "[LOCKED]" if (lk and lk.locked) else "[OPEN]"
        locked_voice = lk.voice_id if lk else "-"
        reg_cfg = registry.get(name, {})
        reg_voice = reg_cfg.get("voice", "-") if isinstance(reg_cfg, dict) else str(reg_cfg)
        evidence = lk.selection_rationale if lk else ""
        if len(evidence) > 22:
            evidence = evidence[:19] + "..."

        print(f"{name:<24} | {status_str:<12} | {locked_voice:<14} | {reg_voice:<15} | {evidence}")
    print("=" * 95)


def cmd_recommend(project_dir: Path, character_name: str, top_n: int = 5) -> None:
    """Generates voice recommendations with explainable dimensional breakdown."""
    engine = VoiceCandidateEngine()
    roster = load_project_roster(project_dir)
    c_data = roster.get(character_name, {})

    profile = CharacterCastingProfile.from_entities(
        character_id=f"char_{character_name.lower().replace(' ', '_')}",
        canonical_name=character_name,
        entity=c_data,
    )

    lock_mgr = CastLockManager(project_dir)
    ensemble = {l.character_name: l.voice_id for l in lock_mgr.manifest.locks.values() if l.locked}

    scores = engine.rank_candidates(profile, ensemble_voices=ensemble, top_n=top_n)

    if not scores:
        print(f"[!] No candidate recommendations available for '{character_name}'.")
        return

    print("=" * 105)
    print(f"CASTING RECOMMENDATIONS FOR: {character_name} (Gender: {profile.gender}, Age: {profile.perceived_age})")
    print("=" * 105)
    print(f"{'RANK':<5} | {'VOICE':<12} | {'SCORE':<7} | {'GENDER':<7} | {'AGE':<6} | {'TIMBRE':<7} | {'DISTINCT':<8} | {'PRIMARY RATIONALE'}")
    print("-" * 105)

    for i, s in enumerate(scores, 1):
        bd = s.score_breakdown
        g_fit = f"{bd.get('gender_fit', 1.0):.2f}"
        a_fit = f"{bd.get('age_fit', 1.0):.2f}"
        t_fit = f"{bd.get('timbre_fit', 1.0):.2f}"
        d_fit = f"{bd.get('distinctiveness', 1.0):.2f}"
        rat = s.recommendation_summary or (s.strengths[0] if s.strengths else "")
        if len(rat) > 42:
            rat = rat[:39] + "..."
        print(f"{i:<5} | {s.voice_id:<12} | {s.overall_score:<7.3f} | {g_fit:<7} | {a_fit:<6} | {t_fit:<7} | {d_fit:<8} | {rat}")
    print("=" * 105)


def cmd_audition(
    project_dir: Path,
    character_name: str,
    voice_id: Optional[str] = None,
    modes: Optional[List[str]] = None,
) -> None:
    """Generates audition scenes for character."""
    roster = load_project_roster(project_dir)
    c_data = roster.get(character_name, {})

    profile = CharacterCastingProfile.from_entities(
        character_id=f"char_{character_name.lower().replace(' ', '_')}",
        canonical_name=character_name,
        entity=c_data,
    )

    engine = VoiceAuditionEngine()
    all_scenes = engine.generate_audition_scenes(profile)
    scenes = [s for s in all_scenes if s.dramatic_mode in modes] if modes else all_scenes

    print("=" * 85)
    print(f"AUDITION PACK: {character_name} ({len(scenes)} Dramatic Modes)")
    if voice_id:
        print(f"Candidate Voice: {voice_id}")
    print("=" * 85)

    for s in scenes:
        print(f"\n>> MODE: {s.dramatic_mode.upper()}")
        print(f"   Directive:   {s.delivery_directive}")
        print(f"   Pacing:      {s.suggested_pace:.2f}x | Target Emotion: {s.target_emotion}")
        print(f"   Line:        \"{s.line_text}\"")

    print("\n" + "=" * 85)


def cmd_lock(
    project_dir: Path,
    character_name: str,
    voice_id: str,
    reason: str = "Director approved via Casting Console",
) -> None:
    """Locks a character to a voice and synchronizes registry."""
    lock_mgr = CastLockManager(project_dir)
    c_id = f"char_{character_name.lower().replace(' ', '_')}"
    lock = lock_mgr.lock_character(
        character_id=c_id,
        character_name=character_name,
        voice_id=voice_id,
        selection_rationale=reason,
    )
    print(f"[+] Successfully LOCKED '{character_name}' to voice '{lock.voice_id}'.")
    print(f"    Cast Lock Manifest: {project_dir / 'cast_lock.json'}")
    print(f"    Voice Registry:    {project_dir / 'voice_registry.json'} (Synchronized)")


def cmd_recast(
    project_dir: Path,
    character_name: str,
    new_voice_id: str,
    reason: str = "Recast via Casting Console",
) -> None:
    """Recasts character, invalidating previous takes and updating manifest."""
    lock_mgr = CastLockManager(project_dir)
    lock = lock_mgr.recast_character(
        character_name_or_id=character_name,
        new_voice_id=new_voice_id,
        reason=reason,
    )
    print(f"[+] Successfully RECAST '{character_name}' to new voice '{lock.voice_id}'.")
    print(f"    Previous takes for '{character_name}' have been invalidated and archived.")
    print(f"    Cast Lock & Voice Registry updated.")


def main():
    parser = argparse.ArgumentParser(description="Audiobook Factory - Human Casting Console")
    parser.add_argument("--project", "-p", type=str, default=".", help="Project directory path")
    parser.add_argument("--list-voices", action="store_true", help="List all catalog voices")
    parser.add_argument("--status", action="store_true", help="View current project casting status")
    parser.add_argument("--recommend", type=str, metavar="CHARACTER", help="Recommend voices for character")
    parser.add_argument("--top", type=int, default=5, help="Number of recommendations to display (default: 5)")
    parser.add_argument("--audition", type=str, metavar="CHARACTER", help="Generate audition pack for character")
    parser.add_argument("--voice", type=str, help="Candidate voice ID for audition")
    parser.add_argument("--mode", type=str, help="Specific audition mode (e.g. anger, whisper, vulnerability)")
    parser.add_argument("--all-modes", action="store_true", help="Generate all 10 audition modes")
    parser.add_argument("--lock", nargs=2, metavar=("CHARACTER", "VOICE"), help="Lock character to voice")
    parser.add_argument("--recast", nargs=2, metavar=("CHARACTER", "NEW_VOICE"), help="Recast character to new voice")
    parser.add_argument("--reason", type=str, default="Director manual override", help="Audit rationale for lock/recast")

    args = parser.parse_args()
    project_dir = Path(args.project).resolve()

    if args.list_voices:
        cmd_list_voices()
    elif args.status:
        cmd_status(project_dir)
    elif args.recommend:
        cmd_recommend(project_dir, args.recommend, top_n=args.top)
    elif args.audition:
        modes = None
        if args.mode:
            modes = [args.mode]
        elif not args.all_modes:
            modes = ["conversational", "authority", "whisper", "anger", "vulnerability"]
        cmd_audition(project_dir, args.audition, voice_id=args.voice, modes=modes)
    elif args.lock:
        char, v_id = args.lock
        cmd_lock(project_dir, char, v_id, reason=args.reason)
    elif args.recast:
        char, new_v_id = args.recast
        cmd_recast(project_dir, char, new_v_id, reason=args.reason)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
