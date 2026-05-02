"""
Delivery layer for academic investigation v3.2.

Contains two specialized delivery agents:
- Xiaotangdou (小糖豆): Material collector and classifier
- Xiaojinjing (小金金): Report generator and self-checker
"""

from .xiaotangdou import Xiaotangdou
from .xiaojinjing import Xiaojinjing
from .delivery_base import BaseDeliveryAgent, ChecklistRunner

__all__ = ["Xiaotangdou", "Xiaojinjing", "BaseDeliveryAgent", "ChecklistRunner"]
