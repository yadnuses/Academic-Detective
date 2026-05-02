#!/usr/bin/env python3
"""
text_profiler.py — Compatibility shim.

This module has been moved to analysis/text_profiler.py.
Please update your imports: `from analysis.text_profiler import ...`
"""

import warnings
warnings.warn(
    "scripts/text_profiler.py is deprecated. Use analysis.text_profiler instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analysis.text_profiler import *  # noqa: F401,F403
