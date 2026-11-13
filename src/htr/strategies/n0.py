"""N0 — page entière (double page), un seul appel, sortie JSON de toutes les lignes."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from ..parsing import extract_rows, parse_json
from ..schema import fields_description, page_json_schema
from ..vlm import VLMClient, encode_image
from .base import PhotoResult, Strategy


class N0PageEntiere(Strategy):
    name = "N0"

    def __init__(self, cfg: dict, client: VLMClient):
        super().__init__(cfg, client)
        template = Path(cfg["prompt_file"]).read_text(encoding="utf-8")
        self.prompt = template.replace("{champs}", fields_description())
        self.schema = page_json_schema() if cfg.get("json_schema", True) else None

    def transcribe(self, photo: Path) -> PhotoResult:
        img = ImageOps.exif_transpose(Image.open(photo))
        im_cfg = self.cfg["image"]
        data = encode_image(img, im_cfg.get("max_side"), im_cfg.get("jpeg_quality", 90))
        resp = self.client.generate(self.prompt, [data], self.schema, meta={"photo": photo.stem})
        obj, valid = parse_json(resp.text)
        rows = extract_rows(obj) if obj is not None else []
        return PhotoResult(rows=rows, json_valid=valid and obj is not None, calls=[resp])
