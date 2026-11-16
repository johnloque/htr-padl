"""Petit classifieur d'images pour le symbole de la catégorie médicale (N2).

Descripteur HOG de la cellule (niveaux de gris, taille fixe) + k plus proches voisins (distance cosinus),
entraîné sur les cellules du gold. Pour une photo du gold, on entraîne sans cette photo
(validation croisée par photo) : aucune fuite de la référence.

    uv run python -m htr.classifier.categorie      # exactitude en validation croisée par photo
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage
from skimage.feature import hog
from skimage.filters import threshold_sauvola

ROOT = Path(__file__).resolve().parents[3]


def ink_box(gray: np.ndarray, cfg: dict) -> tuple[int, int, int, int]:
    """Boîte englobante du symbole : réglures et pointillés retirés, plus grande composante d'encre et ses voisines.
    Repli sur le cadrage fixe si rien n'est trouvé."""
    h, w = gray.shape
    ink = gray < threshold_sauvola(gray, window_size=cfg["sauvola_window"], k=cfg["sauvola_k"])
    gap = cfg["dot_gap_px"]
    # traits horizontaux (pointillés compris, après fermeture) et verticaux plus longs qu'une fraction de la cellule
    h_lines = ndimage.binary_opening(ndimage.binary_closing(ink, np.ones((1, gap), bool)),
                                     np.ones((1, max(3, int(w * cfg["line_frac"]))), bool))
    v_lines = ndimage.binary_opening(ink, np.ones((max(3, int(h * cfg["line_frac"])), 1), bool))
    ink &= ~ndimage.binary_dilation(h_lines | v_lines, np.ones((3, 3), bool))
    ink[:, : int(w * cfg["crop_x"][0])] = ink[:, int(w * cfg["crop_x"][1]):] = False
    ink[: int(h * cfg["crop_y"][0])] = ink[int(h * cfg["crop_y"][1]):] = False
    lab, n = ndimage.label(ink, np.ones((3, 3), bool))
    if n:
        sizes = ndimage.sum(ink, lab, range(1, n + 1))
        boxes = ndimage.find_objects(lab)
        big = int(np.argmax(sizes))
        by, bx = boxes[big]
        m = cfg["neighbour_frac"] * max(by.stop - by.start, bx.stop - bx.start)
        x0, y0, x1, y1 = bx.start, by.start, bx.stop, by.stop
        for i, (sy, sx) in enumerate(boxes):
            if sizes[i] >= cfg["min_component_frac"] * sizes[big] and sx.start < bx.stop + m and sx.stop > bx.start - m \
                    and sy.start < by.stop + m and sy.stop > by.start - m:
                x0, y0, x1, y1 = min(x0, sx.start), min(y0, sy.start), max(x1, sx.stop), max(y1, sy.stop)
        return x0, y0, x1, y1
    return int(w * cfg["crop_x"][0]), int(h * cfg["crop_y"][0]), int(w * cfg["crop_x"][1]), int(h * cfg["crop_y"][1])


def features(path: Path, cfg: dict) -> np.ndarray:
    img = ImageOps.grayscale(Image.open(path))
    gray = np.asarray(img, dtype=np.float32) / 255.0
    x0, y0, x1, y1 = ink_box(gray, cfg)
    # carré centré sur le symbole, avec une marge : garde les proportions
    side = int(max(x1 - x0, y1 - y0) * (1 + cfg["box_margin"]))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    sq = ImageOps.autocontrast(img.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)))
    sq = np.asarray(sq.resize((cfg["size"], cfg["size"]), Image.LANCZOS), dtype=np.float32) / 255.0
    f = hog(sq, orientations=cfg["orientations"], pixels_per_cell=(cfg["pixels_per_cell"],) * 2, cells_per_block=(2, 2))
    return f / (np.linalg.norm(f) + 1e-9)


def load_gold_cells(cfg: dict, cells_dir: Path, gold: dict[str, list[dict]]):
    """Renvoie [(photo, chemin, étiquette)] pour les cellules du gold dont le crop existe."""
    out = []
    for photo, rows in gold.items():
        for i, r in enumerate(rows, 1):
            p = cells_dir / photo / f"r{i:02d}" / "categorie_medicale.jpg"
            if p.exists() and r["categorie_medicale"]:
                out.append((photo, p, r["categorie_medicale"]))
    return out


class KNNCategorie:
    def __init__(self, cfg: dict, samples: list[tuple[str, Path, str]]):
        self.cfg = cfg
        self.samples = samples
        self.X = np.stack([features(p, cfg) for _, p, _ in samples]) if samples else np.zeros((0, 1))
        self.y = [lab for _, _, lab in samples]
        self.photos = np.array([ph for ph, _, _ in samples])

    def predict(self, path: Path, exclude_photo: str | None = None) -> tuple[str, float]:
        """(étiquette, part des k voisins qui l'ont votée)."""
        mask = self.photos != exclude_photo if exclude_photo else np.ones(len(self.y), bool)
        X, y = self.X[mask], [lab for lab, m in zip(self.y, mask) if m]
        sims = X @ features(path, self.cfg)
        k = min(self.cfg["k"], len(y))
        top = np.argsort(-sims)[:k]
        lab, n = Counter(y[i] for i in top).most_common(1)[0]
        return lab, n / k


def main():
    import yaml
    from eval.evaluate import load_gold

    cfg = yaml.safe_load((ROOT / "configs" / "N2" / "classifier.yaml").read_text(encoding="utf-8"))
    gold = load_gold(ROOT / "gold" / "transcripts")
    samples = load_gold_cells(cfg, ROOT / "data" / "cells", gold)
    clf = KNNCategorie(cfg, samples)
    errs = []
    for ph, p, lab in samples:
        pred, conf = clf.predict(p, exclude_photo=ph)
        if pred != lab:
            errs.append((p.relative_to(ROOT), lab, pred, conf))
    print(f"exactitude (validation croisée par photo) : {1 - len(errs) / len(samples):.3f} sur {len(samples)} cellules")
    for e in errs:
        print("  erreur", *e)


if __name__ == "__main__":
    main()
