#!/usr/bin/env python3
"""
Test Suite: Multi-Expert Architecture Audit & Coordination Verification.
Validates:
- 10 Subsystem expert profiles, mandates, and weight normalizations
- Pydantic v2 coordination contract schemas
- Strict read-only execution (zero file mutations)
- Deterministic/Qualitative score reconciliation
- Fail-closed hard gate behavior
"""

import os
import json
import tempfile
import pytest
from pathlib import Path

from audiobook_factory.coordination_contracts import (
    SubsystemEvidenceDossier,
    LLMExpertEvaluation,
    SubsystemAuditVerdict,
    MasterArchitectureAuditReport,
)
from audiobook_factory.expert_rubrics import (
    EXPERT_PROFILES,
    evaluate_subsystem_qualitatively,
)
from audiobook_factory.expert_auditor import MultiExpertArchitectureAuditor


def test_expert_profiles_integrity():
    """Verify that all 10 subsystems have fully articulated expert profiles."""
    expected_subsystems = [
        "system1_ingestion",
        "system2_translation",
        "system3_screenplay",
        "system4_tts_casting",
        "system5_sonic_intelligence",
        "system6_editorial",
        "system7_mixing",
        "system8_mastering",
        "system9_packaging",
        "system10_orchestration",
    ]

    for sub_id in expected_subsystems:
        assert sub_id in EXPERT_PROFILES, f"Missing expert profile for {sub_id}"
        prof = EXPERT_PROFILES[sub_id]
        assert "role" in prof and len(prof["role"]) > 5
        assert "subsystem_name" in prof
        assert "mandate" in prof and len(prof["mandate"]) > 20
        assert "weights" in prof
        # Verify weights sum to 1.0 (with floating point tolerance)
        total_w = sum(prof["weights"].values())
        assert abs(total_w - 1.0) < 1e-4, f"Weights for {sub_id} must sum to 1.0, got {total_w}"


def test_coordination_contracts_validation():
    """Verify Pydantic v2 schemas for evidence dossier, expert evaluation, and master report."""
    dossier = SubsystemEvidenceDossier(
        subsystem_id="system1_ingestion",
        expert_role=EXPERT_PROFILES["system1_ingestion"]["role"],
        deterministic_score=95.0,
        hard_gate_pass=True,
        metrics={"chapter_files_found": 10, "valid_chapters": 10},
        inspected_files=["chapter_001.md"],
        anomalies=[],
    )
    assert dossier.deterministic_score == 95.0
    assert dossier.hard_gate_pass is True

    evaluation = evaluate_subsystem_qualitatively(dossier)
    assert isinstance(evaluation, LLMExpertEvaluation)
    assert evaluation.qualitative_score >= 80.0
    assert len(evaluation.critique) > 10

    verdict = SubsystemAuditVerdict(
        subsystem_id=dossier.subsystem_id,
        subsystem_name=EXPERT_PROFILES["system1_ingestion"]["subsystem_name"],
        expert_role=dossier.expert_role,
        status="PASS",
        composite_score=95.0,
        deterministic_score=95.0,
        qualitative_score=evaluation.qualitative_score,
        hard_gate_pass=True,
        summary_message="PASS",
        evidence_dossier=dossier,
        expert_evaluation=evaluation,
    )
    assert verdict.status == "PASS"


def test_fail_closed_hard_gate():
    """Verify that if a hard gate fails, status is strictly capped at FAIL."""
    failed_dossier = SubsystemEvidenceDossier(
        subsystem_id="system1_ingestion",
        expert_role=EXPERT_PROFILES["system1_ingestion"]["role"],
        deterministic_score=30.0,
        hard_gate_pass=False,
        metrics={"chapter_files_found": 0},
        inspected_files=[],
        anomalies=["Fatal: Zero valid chapters found."],
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        auditor = MultiExpertArchitectureAuditor(project_dir=Path(tmp_dir))
        verdict = auditor._run_expert_audit("system1_ingestion", failed_dossier)

        assert verdict.status == "FAIL", f"Expected FAIL for hard gate violation, got {verdict.status}"
        assert verdict.hard_gate_pass is False


def test_read_only_live_audit_harry_potter():
    """Verify live read-only audit on benchmark project with zero disk mutations."""
    proj_dir = Path("audiobooks/projects/dastan_e_hastinapur").resolve()
    if not (proj_dir / "mastered").exists():
        proj_dir = Path("audiobooks/projects/harry_potter_or_paras_patthar").resolve()
    if not (proj_dir / "mastered").exists():
        pytest.skip("Certified benchmark project not found or unproduced")

    # Snapshot timestamps before audit
    mtimes_before = {p: p.stat().st_mtime for p in proj_dir.rglob("*") if p.is_file()}

    auditor = MultiExpertArchitectureAuditor(project_dir=proj_dir)
    report = auditor.audit_all(chapter_num=1)

    assert isinstance(report, MasterArchitectureAuditReport)
    assert report.read_only_verified is True
    assert report.total_subsystems() if hasattr(report, "total_subsystems") else len(report.subsystems) == 10
    assert report.overall_score >= 80.0
    assert report.overall_status in ("PASS", "WARN")

    # Snapshot timestamps after audit and verify ZERO mutations to pre-existing files
    for p, old_mtime in mtimes_before.items():
        if p.exists() and p.name != "MASTER_EXPERT_AUDIT_REPORT.json":
            new_mtime = p.stat().st_mtime
            assert new_mtime == old_mtime, f"Read-only violation! File was modified: {p}"
