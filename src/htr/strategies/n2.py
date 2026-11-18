"""N2 — une case, un appel, prompts spécialisés par type de colonne.

Entrée : les crops de cellules de la segmentation (`data/cells/<photo>/rNN/<colonne>.jpg`).
- Description des cases (prompt, champs, longueur de sortie) : `configs/N2/cells.yaml`.
- Champs fermés : `enum` dans le schéma JSON, valeurs de `configs/vocab.yaml`.
- Texte long : longueur de sortie proportionnelle à la largeur de la case, détection de n-grammes répétés
  et nouvelle tentative avec d'autres paramètres (section `long_text` de la config).
- Catégorie médicale : appel de modèle (`categorie_medicale: vlm`) ou petit classifieur d'images
  (`classifier`, entraîné sur le gold sans la photo traitée).
- Variante `context: true` : la demi-ligne de la case est jointe comme seconde image.
- `prompts_dir` (option `--prompts` de htr.run) : un fichier de ce dossier remplace le prompt de même nom.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml
from PIL import Image

from ..parsing import parse_json
from ..schema import FIELD_KEYS
from ..vlm import VLMClient, encode_image
from .base import PhotoResult, Strategy

ROOT = Path(__file__).resolve().parents[3]


def load_yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def repeated_ngram(text: str, n: int, max_repeats: int) -> str | None:
    """Premier n-gramme de mots présent plus de `max_repeats` fois, sinon None."""
    words = re.findall(r"\w+", text.lower())
    counts = Counter(tuple(words[i:i + n]) for i in range(len(words) - n + 1))
    for gram, c in counts.most_common(1):
        if c > max_repeats:
            return " ".join(gram)
    return None


def clean(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return " et ".join(clean(x) for x in v if clean(x))
    return " ".join(str(v).split())


def prompt_path(cfg: dict, rel: str) -> Path:
    """Fichier de prompt : version de `prompts_dir` si elle existe, sinon celle de la config."""
    if cfg.get("prompts_dir") and (alt := ROOT / cfg["prompts_dir"] / Path(rel).name).exists():
        return alt
    return ROOT / rel


class N2Cellule(Strategy):
    name = "N2"

    def __init__(self, cfg: dict, client: VLMClient):
        super().__init__(cfg, client)
        self.cells = load_yaml(cfg["cells_file"])
        vocab = load_yaml(cfg["vocab_file"])
        seg_cfg = load_yaml(cfg.get("segmentation_config", "configs/segmentation.yaml"))
        self.side = {col: side for side, cols in seg_cfg["columns"].items() for col in cols}
        if cfg.get("prompts_dir") and not (ROOT / cfg["prompts_dir"]).is_dir():
            raise FileNotFoundError(f"dossier de prompts introuvable : {cfg['prompts_dir']}")
        header = prompt_path(cfg, cfg["prompts"]["entete"]).read_text(encoding="utf-8")
        image_desc = cfg["prompts"]["image_contexte" if cfg.get("context") else "image_seule"]
        self.prompts, self.schemas = {}, {}
        for col, spec in self.cells.items():
            path = prompt_path(cfg, spec["prompt"])
            consigne = path.read_text(encoding="utf-8").strip()
            props = {}
            for name, f in spec["fields"].items():
                prop = {"type": "string"}
                if f.get("enum"):
                    prop["enum"] = ["", *vocab[f["enum"]]]
                    consigne += f"\nValeurs autorisées pour {name} : " + " ; ".join(f"« {v} »" for v in vocab[f["enum"]]) + "."
                props[name] = {"type": "array", "items": prop} if f.get("array") else prop
            self.prompts[col] = header.replace("{image}", image_desc).replace("{consigne}", consigne)
            self.schemas[col] = {"type": "object", "properties": props, "required": list(props)}
            # trace dans results/runs : fichier utilisé et prompt complet envoyé, pour comparer les versions
            cfg.setdefault("prompts_used", {})[col] = {"file": str(path.relative_to(ROOT)), "text": self.prompts[col]}
        self.cells_dir = ROOT / cfg.get("cells_dir", "data/cells")
        self.rows_dir = ROOT / cfg.get("rows_dir", "data/rows")
        self.seg_dir = ROOT / cfg.get("segmentation_dir", "data/segmentation")
        self.classifier = None
        if cfg.get("categorie_medicale", "vlm") == "classifier":
            from eval.evaluate import load_gold

            from ..classifier.categorie import KNNCategorie, load_gold_cells
            ccfg = load_yaml(cfg["classifier_config"])
            gold = load_gold(ROOT / cfg.get("gold_dir", "gold/transcripts"))
            self.classifier = KNNCategorie(ccfg, load_gold_cells(ccfg, self.cells_dir, gold))

    def _image(self, path: Path) -> bytes:
        im_cfg = self.cfg["image"]
        img = Image.open(path)
        if (up := im_cfg.get("upscale", 1.0)) != 1.0:
            img = img.resize((round(img.width * up), round(img.height * up)), Image.LANCZOS)
        return encode_image(img, im_cfg.get("max_side"), im_cfg.get("jpeg_quality", 90))

    def _read_cell(self, photo: str, rid: str, col: str, warnings: list[str], calls: list):
        """Renvoie (valeurs des champs JSON de la case, JSON valide)."""
        spec = self.cells[col]
        path = self.cells_dir / photo / rid / f"{col}.jpg"
        images = [self._image(path)]
        if self.cfg.get("context"):
            images.append(self._image(self.rows_dir / photo / f"{rid}_{self.side[col]}.jpg"))
        num_predict = spec["num_predict"]
        if spec.get("num_predict_per_100px"):
            num_predict = max(num_predict, round(spec["num_predict_per_100px"] * Image.open(path).width / 100))
        meta = {"photo": photo, "row": rid, "cell": col}
        attempts = [{"num_predict": num_predict}]
        if spec.get("long"):
            lt = self.cfg["long_text"]
            attempts += [{**retry, "num_predict": num_predict} for retry in lt["retries"]]
        best = None
        for k, opts in enumerate(attempts):
            resp = self.client.generate(self.prompts[col], images, self.schemas[col], meta={**meta, "attempt": k},
                                        options=opts)
            calls.append(resp)
            obj, valid = parse_json(resp.text)
            obj = obj if isinstance(obj, dict) else {}
            values = {name: clean(obj.get(name)) for name in spec["fields"]}
            problem = None
            if spec.get("long"):
                text = " ".join(values.values())
                rep = repeated_ngram(text, lt["ngram"], lt["max_repeats"])
                if rep:
                    problem = f"répétition « {rep} »"
                elif resp.done_reason == "length":
                    problem = "sortie tronquée"
            if not valid or not obj:
                problem = problem or "JSON invalide"
            if best is None or (best[2] and not problem):
                best = (values, valid and bool(obj), problem)
            if not problem:
                break
            warnings.append(f"{rid}/{col} essai {k + 1}: {problem}")
        return best[0], best[1]

    def transcribe(self, photo: Path) -> PhotoResult:
        seg_path = self.seg_dir / f"{photo.stem}.json"
        if not seg_path.exists():
            return PhotoResult(rows=[], json_valid=False, warnings=["segmentation absente"])
        seg = json.loads(seg_path.read_text(encoding="utf-8"))
        if seg.get("status") != "ok":
            return PhotoResult(rows=[], json_valid=False, warnings=[f"segmentation {seg.get('status')}: {seg.get('flags')}"])

        row_ids = sorted(p.name for p in (self.cells_dir / photo.stem).glob("r[0-9][0-9]") if p.is_dir())
        rows, calls, warnings, all_valid = [], [], [], True
        for rid in row_ids:
            row = {k: "" for k in FIELD_KEYS}
            for col, spec in self.cells.items():
                if col == "categorie_medicale" and self.classifier:
                    label, conf = self.classifier.predict(self.cells_dir / photo.stem / rid / f"{col}.jpg",
                                                          exclude_photo=photo.stem)
                    row[col] = label
                    continue
                values, valid = self._read_cell(photo.stem, rid, col, warnings, calls)
                all_valid &= valid
                if spec.get("compose"):
                    for key, fmt in spec["compose"].items():
                        row[key] = " ".join(fmt.format(**values).split())
                else:
                    row.update({k: v for k, v in values.items() if k in row})
            rows.append(row)
        return PhotoResult(rows=rows, json_valid=all_valid, calls=calls, warnings=warnings)
