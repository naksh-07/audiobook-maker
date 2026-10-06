#!/usr/bin/env python3
"""
Audiobook Factory - Backwards Compatibility Runner Shim.
Redirects legacy calls to modern production CLI (audiobook_cli.py).
"""
import sys
from audiobook_cli import main

def get_persistent_key_pool(*args, **kwargs):
    """Shim for backward compatibility."""
    from audiobook_factory.tts.providers.gemini import get_persistent_key_pool as _get_pool
    return _get_pool(*args, **kwargs)

def print_keypool_status(*args, **kwargs):
    """Shim for backward compatibility."""
    pass

def run_standalone_pipeline(*args, **kwargs):
    """Deprecated standalone runner shim redirecting to modern orchestrator."""
    import warnings
    msg = "[DEPRECATION WARNING] standalone_pipeline is deprecated. Migrate to ProductionOrchestrator / audiobook_cli.py."
    warnings.warn(msg, DeprecationWarning, stacklevel=2)
    print(msg)
    return None

def parse_literature_offline(*args, **kwargs):
    """Offline screenplay generator forwarding to offline_parser."""
    from audiobook_factory.offline_parser import parse_literature_offline as _offline_parse
    return _offline_parse(*args, **kwargs)

if __name__ == "__main__":
    sys.exit(main())

