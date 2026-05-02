#!/usr/bin/env python3
"""
report_prompt_optimizer.py — Compatibility shim.

This module has been moved to report/report_prompt_optimizer.py.
Please update your imports: `from report.report_prompt_optimizer import ...`
"""

import warnings
warnings.warn(
    "scripts/report_prompt_optimizer.py is deprecated. Use report.report_prompt_optimizer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from report.report_prompt_optimizer import *  # noqa: F401,F403
