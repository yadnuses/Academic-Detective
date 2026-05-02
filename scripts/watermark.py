#!/usr/bin/env python3
"""
watermark.py — Compatibility shim.

This module has been moved to core/watermark.py.
Please update your imports: `from core.watermark import ...`
"""

import warnings
warnings.warn(
    "scripts/watermark.py is deprecated. Use core.watermark instead.",
    DeprecationWarning,
    stacklevel=2,
)

from core.watermark import *  # noqa: F401,F403
