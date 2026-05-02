#!/usr/bin/env python3
"""
paper_quality_rubric.py — Compatibility shim.

This module has been moved to analysis/paper_quality_rubric.py.
Please update your imports: `from analysis.paper_quality_rubric import ...`
"""

import warnings
warnings.warn(
    "scripts/paper_quality_rubric.py is deprecated. Use analysis.paper_quality_rubric instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analysis.paper_quality_rubric import *  # noqa: F401,F403
