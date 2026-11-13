"""Interface commune des stratégies : une photo en entrée, des lignes (schéma commun) en sortie."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path

from ..vlm import VLMClient, VLMResponse


@dataclass
class PhotoResult:
    rows: list[dict]
    json_valid: bool
    calls: list[VLMResponse] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Strategy(abc.ABC):
    name: str = "?"

    def __init__(self, cfg: dict, client: VLMClient):
        self.cfg = cfg
        self.client = client

    @abc.abstractmethod
    def transcribe(self, photo: Path) -> PhotoResult: ...
