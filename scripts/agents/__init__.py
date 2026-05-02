"""
agents package — Multi-agent collaboration layer for academic investigation v3.2.

Agents communicate via the filesystem (STATE.md + agent_logs/).
The orchestrator manages agent lifecycle and coordinates execution rounds.
"""

from .base import BaseAgent
from .zhu_xiansheng import ZhuXiansheng
from .dududu import Dududu
from .huangmao import Huangmao
from .laozhoumo import LaoZhoumo
from .orchestrator import Orchestrator

__all__ = [
    "BaseAgent",
    "ZhuXiansheng",
    "Dududu",
    "Huangmao",
    "LaoZhoumo",
    "Orchestrator",
]
