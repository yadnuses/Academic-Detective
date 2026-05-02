#!/usr/bin/env python3
"""
grant_linker.py — Compatibility shim.

This module has been moved to network/grant_linker.py.
Please update your imports: `from network.grant_linker import ...`
"""

import warnings
warnings.warn(
    "scripts/grant_linker.py is deprecated. Use network.grant_linker instead.",
    DeprecationWarning,
    stacklevel=2,
)

from network.grant_linker import *  # noqa: F401,F403
