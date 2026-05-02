#!/usr/bin/env python3
"""
stylometry_profiler.py — Compatibility shim.

This module has been moved to analysis/stylometry_profiler.py.
Please update your imports: `from analysis.stylometry_profiler import ...`
"""

import warnings
warnings.warn(
    "scripts/stylometry_profiler.py is deprecated. Use analysis.stylometry_profiler instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analysis.stylometry_profiler import *  # noqa: F401,F403
