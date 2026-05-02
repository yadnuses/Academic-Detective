#!/usr/bin/env python3
"""
scholar_data_builder.py — Compatibility shim.

This module has been moved to domestic/scholar_data_builder.py.
Please update your imports: `from domestic.scholar_data_builder import ...`
"""

import warnings
warnings.warn(
    "scripts/scholar_data_builder.py is deprecated. Use domestic.scholar_data_builder instead.",
    DeprecationWarning,
    stacklevel=2,
)

from domestic.scholar_data_builder import *  # noqa: F401,F403
