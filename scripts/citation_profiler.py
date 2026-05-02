#!/usr/bin/env python3
"""
citation_profiler.py — Compatibility shim.

This module has been moved to analysis/citation_profiler.py.
Please update your imports: `from analysis.citation_profiler import ...`
"""

import warnings
warnings.warn(
    "scripts/citation_profiler.py is deprecated. Use analysis.citation_profiler instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analysis.citation_profiler import *  # noqa: F401,F403
