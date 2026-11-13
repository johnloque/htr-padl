from __future__ import annotations

import os
from pathlib import Path

from .base import VLMClient, VLMResponse, encode_image
from .ollama import OllamaClient
from .openai_compat import OpenAICompatClient

BACKENDS = {"ollama": OllamaClient, "openai": OpenAICompatClient}


def make_client(model_cfg: dict, inference: dict, cache_path: Path | None) -> VLMClient:
    """Construit le client à partir de la section `model` et `inference` d'une config YAML.

    L'hôte peut être surchargé par la variable d'environnement indiquée dans `host_env`
    (par défaut OLLAMA_HOST), ce qui permet d'appeler l'Ollama de l'hôte depuis Docker.
    """
    host = os.environ.get(model_cfg.get("host_env", "OLLAMA_HOST")) or model_cfg["host"]
    if not host.startswith("http"):
        host = f"http://{host}"
    cls = BACKENDS[model_cfg["backend"]]
    return cls(model_cfg["id"], host, inference, model_cfg.get("timeout_s", 1800), cache_path,
               extra=model_cfg.get("extra", {}))


__all__ = ["make_client", "VLMClient", "VLMResponse", "encode_image"]
