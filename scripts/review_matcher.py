#!/usr/bin/env python3
"""
review_matcher.py — Compatibility shim.

This module has been moved to domestic/review_matcher.py.
Please update your imports: `from domestic.review_matcher import ...`
"""

import warnings
warnings.warn(
    "scripts/review_matcher.py is deprecated. Use domestic.review_matcher instead.",
    DeprecationWarning,
    stacklevel=2,
)

from domestic.review_matcher import *  # noqa: F401,F403
