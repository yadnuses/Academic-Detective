#!/usr/bin/env python3
"""
wechat_search.py — Compatibility shim.

This module has been moved to domestic/wechat_search.py.
Please update your imports: `from domestic.wechat_search import ...`
"""

import warnings
warnings.warn(
    "scripts/wechat_search.py is deprecated. Use domestic.wechat_search instead.",
    DeprecationWarning,
    stacklevel=2,
)

from domestic.wechat_search import *  # noqa: F401,F403
