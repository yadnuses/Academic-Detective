#!/usr/bin/env python3
"""
data_validator.py — Compatibility shim.

This module has been moved to domestic/data_validator.py.
Please update your imports: `from domestic.data_validator import ...`
"""

import warnings
warnings.warn(
    "scripts/data_validator.py is deprecated. Use domestic.data_validator instead.",
    DeprecationWarning,
    stacklevel=2,
)

from domestic.data_validator import *  # noqa: F401,F403
