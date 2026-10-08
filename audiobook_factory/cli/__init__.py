#!/usr/bin/env python3
"""
Audiobook Studio - Modular Developer CLI Suite.
Standard: v6.0-ENTERPRISE-DAG
"""

from audiobook_factory.cli.main import main, build_cli_parser
from audiobook_factory.cli.doctor import run_doctor_diagnostics

__all__ = ["main", "build_cli_parser", "run_doctor_diagnostics"]
