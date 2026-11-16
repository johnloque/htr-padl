"""Backend Ollama (API native /api/chat)."""
from __future__ import annotations

import httpx

from .base import VLMClient, VLMResponse, b64


class OllamaClient(VLMClient):
    backend = "ollama"

    def _post(self, path: str, payload: dict, timeout: float | None = None) -> dict:
        r = httpx.post(f"{self.host}{path}", json=payload, timeout=timeout or self.timeout_s)
        r.raise_for_status()
        return r.json()

    def _call(self, prompt, images, schema, options):
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt, "images": [b64(i) for i in images]}],
            "stream": False,
            "options": options,
            "keep_alive": self.extra.get("keep_alive", "30m"),
        }
        if schema is not None:
            payload["format"] = schema
        if "think" in self.extra:
            payload["think"] = self.extra["think"]
        data = self._post("/api/chat", payload)
        ns = 1e-9
        return VLMResponse(
            text=data.get("message", {}).get("content", ""),
            prompt_tokens=data.get("prompt_eval_count"),
            output_tokens=data.get("eval_count"),
            gen_s=(data["eval_duration"] * ns) if data.get("eval_duration") else None,
            done_reason=data.get("done_reason"),
            raw={k: v for k, v in data.items() if k != "message"},
        )

    def info(self) -> dict:
        out = super().info()
        try:
            out["ollama_version"] = httpx.get(f"{self.host}/api/version", timeout=10).json().get("version")
            show = self._post("/api/show", {"model": self.model_id}, timeout=30)
            out["details"] = show.get("details", {})
            out["capabilities"] = show.get("capabilities")
            for m in httpx.get(f"{self.host}/api/tags", timeout=10).json().get("models", []):
                if m.get("name") == self.model_id or m.get("model") == self.model_id:
                    out["digest"] = m.get("digest")
                    out["size"] = m.get("size")
        except httpx.HTTPError as e:
            out["info_error"] = str(e)
        return out

    def _loaded(self) -> list[dict]:
        try:
            return httpx.get(f"{self.host}/api/ps", timeout=10).json().get("models", [])
        except httpx.HTTPError:
            return []

    def memory_bytes(self):
        for m in self._loaded():
            if m.get("name") == self.model_id or m.get("model") == self.model_id:
                return m.get("size")
        return None

    def _unload(self, name: str):
        self._post("/api/generate", {"model": name, "keep_alive": 0}, timeout=120)

    def unload(self):
        self._unload(self.model_id)

    def unload_others(self):
        """Un seul modèle chargé à la fois (16 Go de mémoire unifiée)."""
        for m in self._loaded():
            name = m.get("name") or m.get("model")
            if name and name != self.model_id:
                self._unload(name)
