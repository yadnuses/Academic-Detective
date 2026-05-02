#!/usr/bin/env python3
"""
data_importer.py — Compatibility shim.

This module has been moved to domestic/data_importer.py.
Please update your imports: `from domestic.data_importer import ...`
"""

import warnings
warnings.warn(
    "scripts/data_importer.py is deprecated. Use domestic.data_importer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from domestic.data_importer import *  # noqa: F401,F403
from domestic.data_importer import (  # noqa: F401
    _find_col,
    _cell_str,
    _split_authors,
    _parse_year,
    _normalize_ris_record,
    _normalize_title,
    _title_similarity,
)
