#!/usr/bin/env python3
"""
hybrid_scorer.py — Compatibility shim.

This module has been moved to analysis/hybrid_scorer.py.
Please update your imports: `from analysis.hybrid_scorer import ...`
"""

import warnings
warnings.warn(
    "scripts/hybrid_scorer.py is deprecated. Use analysis.hybrid_scorer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from analysis.hybrid_scorer import *  # noqa: F401,F403
