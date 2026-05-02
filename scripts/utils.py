#!/usr/bin/env python3
"""
utils.py — Compatibility shim.

This module has been moved to core/utils.py.
Please update your imports: `from core.utils import ...`
"""

import warnings
warnings.warn(
    "scripts/utils.py is deprecated. Use core.utils instead.",
    DeprecationWarning,
    stacklevel=2,
)

from core.utils import *  # noqa: F401,F403
