from .base import PhotoResult, Strategy
from .n0 import N0PageEntiere

STRATEGIES: dict[str, type[Strategy]] = {"N0": N0PageEntiere}

__all__ = ["STRATEGIES", "Strategy", "PhotoResult"]
