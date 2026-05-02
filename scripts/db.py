#!/usr/bin/env python3
"""
db.py — Compatibility shim.

This module has been moved to core/db.py.
Please update your imports: `from core.db import ...`
"""

import warnings
warnings.warn(
    "scripts/db.py is deprecated. Use core.db instead.",
    DeprecationWarning,
    stacklevel=2,
)

from core.db import *  # noqa: F401,F403
