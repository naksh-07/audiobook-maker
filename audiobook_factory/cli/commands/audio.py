from __future__ import annotations
import os
import sys
import re
import json
from pathlib import Path

from audiobook_factory.cli.context import get_projects_dir, get_workspace_dir
from audiobook_factory.audio_utils import get_ffmpeg, get_audio_duration
from audiobook_factory.packager import package_m4b_audiobook


def cmd_soundscape(args):
    print("[*] Soundscape planning is decoupled in Vocals-Only mode.")


def cmd_bgm(args):
    print("[*] BGM and soundscape scoring are decoupled in Vocals-Only mode.")


def cmd_stems(args):
    print("[*] Discrete multi-track stems are decoupled in Vocals-Only mode (pure vocal master delivered).")


def cmd_package(args):
    target = Path(args.book)
    project_dir = target if (target.exists() and target.is_dir()) else (get_projects_dir() / args.book)
    cover = Path(args.cover) if getattr(args, "cover", None) else None
    enforce = getattr(args, "enforce_gate6", False)
    final_m4b = package_m4b_audiobook(project_dir, cover_image=cover, enforce_gate6=enforce)
    print(f"\n[DONE] Finished Audiobook Package: {final_m4b}")


def cmd_direct(args):
    print("[*] AgentDirector manifest direct is decoupled in Vocals-Only mode.")


def cmd_render(args):
    print("[*] Manifest multitrack render is decoupled in Vocals-Only mode.")


def cmd_timeline(args):
    print("[*] Timeline command executed.")
