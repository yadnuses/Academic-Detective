#!/usr/bin/env python3
"""
investigation_retrospector.py — Compatibility shim.

This module has been moved to network/investigation_retrospector.py.
Please update your imports: `from network.investigation_retrospector import ...`
"""

import warnings
warnings.warn(
    "scripts/investigation_retrospector.py is deprecated. Use network.investigation_retrospector instead.",
    DeprecationWarning,
    stacklevel=2,
)

from network.investigation_retrospector import *  # noqa: F401,F403
