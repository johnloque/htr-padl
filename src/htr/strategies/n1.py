"""N1 — une ligne (un patient), un appel.

Entrée : les crops produits par la segmentation (`data/rows/<photo>/rNN*.jpg`).
Deux variantes (`variant` dans la config) :
- `ligne` : un appel sur la ligne complète (gauche + droite côte à côte), tous les champs ;
- `demi`  : deux appels, demi-ligne gauche (identité) puis demi-ligne droite (séjour).
Une photo dont la segmentation n'est pas au statut `ok` ne produit aucune ligne (avertissement).
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from ..parsing import extract_rows, parse_json
from ..schema import FIELD_KEYS, LEFT_KEYS, RIGHT_KEYS, fields_description, row_json_schema
from ..vlm import VLMClient, encode_image
from .base import PhotoResult, Strategy

ROOT = Path(__file__).resolve().parents[3]

# variante -> [(suffixe du crop, clé du prompt dans la config, champs demandés)]
VARIANTS = {
    "ligne": [("", "ligne", FIELD_KEYS)],
    "demi": [("_left", "gauche", LEFT_KEYS), ("_right", "droite", RIGHT_KEYS)],
}


class N1Ligne(Strategy):
    name = "N1"

    def __init__(self, cfg: dict, client: VLMClient):
        super().__init__(cfg, client)
        self.variant = cfg.get("variant", "ligne")
        self.parts = []
        for suffix, prompt_key, keys in VARIANTS[self.variant]:
            template = (ROOT / cfg["prompts"][prompt_key]).read_text(encoding="utf-8")
            prompt = template.replace("{champs}", fields_description(keys))
            schema = row_json_schema(keys) if cfg.get("json_schema", True) else None
            self.parts.append((suffix, prompt, schema, keys))
        self.rows_dir = ROOT / cfg.get("rows_dir", "data/rows")
        self.seg_dir = ROOT / cfg.get("segmentation_dir", "data/segmentation")

    def transcribe(self, photo: Path) -> PhotoResult:
        seg_path = self.seg_dir / f"{photo.stem}.json"
        if not seg_path.exists():
            return PhotoResult(rows=[], json_valid=False, warnings=["segmentation absente"])
        seg = json.loads(seg_path.read_text(encoding="utf-8"))
        if seg.get("status") != "ok":
            return PhotoResult(rows=[], json_valid=False, warnings=[f"segmentation {seg.get('status')}: {seg.get('flags')}"])

        im_cfg = self.cfg["image"]
        row_ids = sorted(p.stem for p in (self.rows_dir / photo.stem).glob("r[0-9][0-9].jpg"))
        rows, calls, warnings, all_valid = [], [], [], True
        for rid in row_ids:
            row = {k: "" for k in FIELD_KEYS}
            for suffix, prompt, schema, keys in self.parts:
                img = Image.open(self.rows_dir / photo.stem / f"{rid}{suffix}.jpg")
                data = encode_image(img, im_cfg.get("max_side"), im_cfg.get("jpeg_quality", 90))
                resp = self.client.generate(prompt, [data], schema, meta={"photo": photo.stem, "row": rid + suffix})
                calls.append(resp)
                obj, valid = parse_json(resp.text)
                found = extract_rows(obj) if obj is not None else []
                if not (valid and found):
                    all_valid = False
                    warnings.append(f"{rid}{suffix}: JSON {'réparé' if found else 'invalide'}"
                                    f"{' (tronqué)' if resp.done_reason == 'length' else ''}")
                if found:
                    row.update({k: found[0][k] for k in keys})
            # la ligne est gardée même vide : elle conserve l'ordre des patients de la page
            rows.append(row)
        return PhotoResult(rows=rows, json_valid=all_valid, calls=calls, warnings=warnings)
