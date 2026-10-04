"""
Tests for Phase 6: Pipeline Orchestration & Cache Governance.
Verifies:
1. STAGE_NUMBERS mapping and stage order.
2. CLI argument parser supports --force-rebuild and --stage-start on 'auto' and 'produce'.
3. PipelineOrchestrator accepts force_rebuild and stage_start flags.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from audiobook_factory.orchestrator import (
    STAGE_NUMBERS,
    PipelineOrchestrator,
)
import audiobook_cli


def test_stage_numbers_mapping():
    """Verify standard stage number mapping."""
    assert STAGE_NUMBERS["extract"] == 1
    assert STAGE_NUMBERS["translate"] == 2
    assert STAGE_NUMBERS["script"] == 3
    assert STAGE_NUMBERS["tts"] == 4
    assert STAGE_NUMBERS["direct"] == 5
    assert STAGE_NUMBERS["package"] == 6


def test_cli_parser_accepts_governance_flags():
    """Verify that audiobook_cli argument parser recognizes --force-rebuild and --stage-start."""
    with patch("sys.argv", ["audiobook_cli.py", "auto", "dummy.epub", "--force-rebuild", "--stage-start", "script"]):
        with patch.dict(audiobook_cli.__dict__, {"cmd_auto": MagicMock()}) as mocked_dict:
            audiobook_cli.main()
            mocked_auto = audiobook_cli.cmd_auto
            assert mocked_auto.called
            args = mocked_auto.call_args[0][0]
            assert args.force_rebuild is True
            assert args.stage_start == "script"

    with patch("sys.argv", ["audiobook_cli.py", "produce", "dummy_slug", "--chapter", "1", "--force-rebuild", "--stage-start", "mix"]):
        with patch.dict(audiobook_cli.__dict__, {"cmd_produce": MagicMock()}) as mocked_dict:
            audiobook_cli.main()
            mocked_produce = audiobook_cli.cmd_produce
            assert mocked_produce.called
            args = mocked_produce.call_args[0][0]
            assert args.force_rebuild is True
            assert args.stage_start == "mix"


def test_orchestrator_accepts_governance_flags(tmp_path):
    """Verify PipelineOrchestrator method signatures accept force_rebuild and stage_start."""
    orch = PipelineOrchestrator(tmp_path)
    assert hasattr(orch, "run_autonomous_pipeline")
    assert hasattr(orch, "produce_chapter")

    import inspect
    sig_auto = inspect.signature(orch.run_autonomous_pipeline)
    assert "force_rebuild" in sig_auto.parameters
    assert "stage_start" in sig_auto.parameters

    sig_produce = inspect.signature(orch.produce_chapter)
    assert "force_rebuild" in sig_produce.parameters
    assert "stage_start" in sig_produce.parameters
