from __future__ import annotations
import sys
from pathlib import Path


def get_workspace_dir() -> Path:
    """Resolves repository workspace root directory, respecting cli overrides."""
    cli_mod = sys.modules.get("audiobook_cli")
    if cli_mod and hasattr(cli_mod, "WORKSPACE_DIR"):
        return Path(cli_mod.WORKSPACE_DIR)
    return Path(__file__).resolve().parent.parent.parent


def get_projects_dir() -> Path:
    """Resolves audiobooks projects directory, dynamically checking for test patches on audiobook_cli."""
    cli_mod = sys.modules.get("audiobook_cli")
    if cli_mod and hasattr(cli_mod, "PROJECTS_DIR"):
        return Path(cli_mod.PROJECTS_DIR)
    return get_workspace_dir() / "audiobooks" / "projects"
