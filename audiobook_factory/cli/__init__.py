from __future__ import annotations

from audiobook_factory.cli.commands.pipeline import (
    cmd_extract,
    cmd_translate,
    cmd_script,
    cmd_synthesize,
    cmd_master,
    cmd_produce,
    cmd_auto,
    cmd_stage_sounds,
)
from audiobook_factory.cli.commands.audio import (
    cmd_soundscape,
    cmd_bgm,
    cmd_stems,
    cmd_package,
    cmd_direct,
    cmd_render,
    cmd_timeline,
)
from audiobook_factory.cli.commands.audit import (
    cmd_audit_book,
    cmd_audit,
)
from audiobook_factory.cli.commands.bank import (
    cmd_bank,
)

__all__ = [
    "cmd_extract",
    "cmd_translate",
    "cmd_script",
    "cmd_synthesize",
    "cmd_master",
    "cmd_produce",
    "cmd_auto",
    "cmd_soundscape",
    "cmd_bgm",
    "cmd_stems",
    "cmd_package",
    "cmd_direct",
    "cmd_render",
    "cmd_timeline",
    "cmd_audit_book",
    "cmd_audit",
    "cmd_bank",
    "cmd_stage_sounds",
]
