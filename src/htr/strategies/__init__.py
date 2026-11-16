from .base import PhotoResult, Strategy
from .n0 import N0PageEntiere
from .n1 import N1Ligne
from .n2 import N2Cellule

STRATEGIES: dict[str, type[Strategy]] = {"N0": N0PageEntiere, "N1": N1Ligne, "N2": N2Cellule}

__all__ = ["STRATEGIES", "Strategy", "PhotoResult"]
