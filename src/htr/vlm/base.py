"""Interface commune aux backends de modèles de vision."""
from __future__ import annotations

import abc
import base64
import hashlib
import io
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image


@dataclass
class VLMResponse:
    text: str
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    wall_s: float = 0.0
    gen_s: float | None = None  # durée de génération (hors chargement / encodage du prompt)
    done_reason: str | None = None
    raw: dict = field(default_factory=dict)
    cached: bool = False

    @property
    def tokens_per_s(self) -> float | None:
        if self.output_tokens and self.gen_s:
            return self.output_tokens / self.gen_s
        return None


def encode_image(img: Image.Image, max_side: int | None, jpeg_quality: int) -> bytes:
    """Redimensionne (côté max) et encode en JPEG."""
    img = img.convert("RGB")
    if max_side and max(img.size) > max_side:
        img = img.copy()
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality)
    return buf.getvalue()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class VLMClient(abc.ABC):
    """Un client = un modèle sur un backend. Les réponses brutes sont mises en cache (JSONL)."""

    backend: str = "?"

    def __init__(self, model_id: str, host: str, options: dict, timeout_s: float,
                 cache_path: Path | None = None, extra: dict | None = None):
        self.model_id = model_id
        self.host = host.rstrip("/")
        self.options = dict(options)
        self.timeout_s = timeout_s
        self.extra = extra or {}
        self.cache_path = cache_path
        self._cache: dict[str, dict] = {}
        if cache_path and cache_path.exists():
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self._cache[rec["key"]] = rec

    # --- à implémenter par backend ---
    @abc.abstractmethod
    def _call(self, prompt: str, images: list[bytes], schema: dict | None) -> VLMResponse: ...

    def info(self) -> dict:
        """Versions et métadonnées (backend, quantification…), enregistrées avec les résultats."""
        return {"backend": self.backend, "model_id": self.model_id, "host": self.host}

    def memory_bytes(self) -> int | None:
        return None

    def unload(self) -> None:
        pass

    def unload_others(self) -> None:
        pass

    # --- commun ---
    def _key(self, prompt: str, images: list[bytes], schema: dict | None) -> str:
        h = hashlib.sha256()
        payload = {"backend": self.backend, "model": self.model_id, "prompt": prompt,
                   "schema": schema, "options": self.options, "extra": self.extra}
        h.update(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())
        for im in images:
            h.update(hashlib.sha256(im).digest())
        return h.hexdigest()

    def generate(self, prompt: str, images: list[bytes], schema: dict | None = None,
                 meta: dict | None = None) -> VLMResponse:
        key = self._key(prompt, images, schema)
        if key in self._cache:
            rec = self._cache[key]
            resp = VLMResponse(**rec["response"])
            resp.cached = True
            return resp
        t0 = time.perf_counter()
        resp = self._call(prompt, images, schema)
        resp.wall_s = time.perf_counter() - t0
        rec = {
            "key": key,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "meta": meta or {},
            "request": {"backend": self.backend, "model": self.model_id, "host": self.host,
                        "options": self.options, "extra": self.extra, "schema": schema,
                        "prompt": prompt,
                        "images_sha256": [hashlib.sha256(im).hexdigest() for im in images]},
            "response": asdict(resp),
        }
        self._cache[key] = rec
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self.cache_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return resp
