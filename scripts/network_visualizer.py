#!/usr/bin/env python3
"""
network_visualizer.py — Compatibility shim.

This module has been moved to network/network_visualizer.py.
Please update your imports: `from network.network_visualizer import ...`
"""

import warnings
warnings.warn(
    "scripts/network_visualizer.py is deprecated. Use network.network_visualizer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from network.network_visualizer import *  # noqa: F401,F403
