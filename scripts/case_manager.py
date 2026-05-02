#!/usr/bin/env python3
"""
case_manager.py — Compatibility shim.

This module has been moved to core/case_manager.py.
Please update your imports: `from core.case_manager import ...`
"""

import warnings
warnings.warn(
    "scripts/case_manager.py is deprecated. Use core.case_manager instead.",
    DeprecationWarning,
    stacklevel=2,
)

from core.case_manager import *  # noqa: F401,F403
