#!/usr/bin/env python3
"""
timeline_weaver.py — Compatibility shim.

This module has been moved to network/timeline_weaver.py.
Please update your imports: `from network.timeline_weaver import ...`
"""

import warnings
warnings.warn(
    "scripts/timeline_weaver.py is deprecated. Use network.timeline_weaver instead.",
    DeprecationWarning,
    stacklevel=2,
)

from network.timeline_weaver import *  # noqa: F401,F403
