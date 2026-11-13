"""Backend compatible OpenAI (/v1/chat/completions) : vLLM, llama.cpp server, mlx_vlm.server…"""
from __future__ import annotations

import os

import httpx

from .base import VLMClient, VLMResponse, b64

# Correspondance options Ollama -> paramètres OpenAI (les autres sont passés tels quels si le serveur les accepte)
_MAP = {"temperature": "temperature", "top_p": "top_p", "num_predict": "max_tokens", "seed": "seed",
        "top_k": "top_k", "repeat_penalty": "repetition_penalty"}


class OpenAICompatClient(VLMClient):
    backend = "openai"

    def _call(self, prompt, images, schema):
        content = [{"type": "text", "text": prompt}]
        content += [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(i)}"}} for i in images]
        payload = {"model": self.model_id, "messages": [{"role": "user", "content": content}]}
        for k, v in self.options.items():
            if k in _MAP:
                payload[_MAP[k]] = v
        if schema is not None:
            payload["response_format"] = {"type": "json_schema",
                                          "json_schema": {"name": "sortie", "schema": schema, "strict": True}}
        headers = {}
        if key := os.environ.get(self.extra.get("api_key_env", "OPENAI_API_KEY")):
            headers["Authorization"] = f"Bearer {key}"
        r = httpx.post(f"{self.host}/v1/chat/completions", json=payload, headers=headers, timeout=self.timeout_s)
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return VLMResponse(
            text=choice["message"].get("content") or "",
            prompt_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            done_reason=choice.get("finish_reason"),
            raw={k: v for k, v in data.items() if k != "choices"},
        )
