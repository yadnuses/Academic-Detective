#!/usr/bin/env python3
"""
negative_space_analyzer.py — Compatibility shim.

This module has been moved to network/negative_space_analyzer.py.
Please update your imports: `from network.negative_space_analyzer import ...`
"""

import warnings
warnings.warn(
    "scripts/negative_space_analyzer.py is deprecated. Use network.negative_space_analyzer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from network.negative_space_analyzer import *  # noqa: F401,F403
