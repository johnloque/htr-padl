"""Repli manuel : cliquer les 4 coins du tableau de chaque page d'une photo.

    uv run python -m htr.segmentation.click_corners "1491_W_1 (9)" [--input gold/photos]

Pour chaque page (gauche puis droite), cliquer dans l'ordre : haut-gauche, haut-droit, bas-droit, bas-gauche
du cadre du tableau (en-tête compris). Touches : `r` recommence la page, `Entrée` valide, `Échap` annule.
Les coins sont écrits dans data/corners/<photo>.json et remplacent la détection automatique au prochain
lancement de `htr.segmentation.segment`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[3]
ORDER = ["haut-gauche", "haut-droit", "bas-droit", "bas-gauche"]


def pick(img, title: str, scale: float) -> list | None:
    shown = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    pts: list = []

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and len(pts) < 4:
            pts.append((x / scale, y / scale))

    cv2.namedWindow(title)
    cv2.setMouseCallback(title, on_mouse)
    while True:
        canvas = shown.copy()
        for i, (x, y) in enumerate(pts):
            cv2.circle(canvas, (int(x * scale), int(y * scale)), 6, (0, 0, 255), -1)
            cv2.putText(canvas, ORDER[i], (int(x * scale) + 8, int(y * scale)), 0, 0.6, (0, 0, 255), 2)
        hint = f"cliquer : {ORDER[len(pts)]}" if len(pts) < 4 else "Entrée pour valider, r pour recommencer"
        cv2.putText(canvas, hint, (10, 30), 0, 0.8, (0, 0, 255), 2)
        cv2.imshow(title, canvas)
        k = cv2.waitKey(30) & 0xFF
        if k == 27:
            cv2.destroyWindow(title)
            return None
        if k == ord("r"):
            pts.clear()
        if k in (10, 13) and len(pts) == 4:
            cv2.destroyWindow(title)
            return [[round(x, 1), round(y, 1)] for x, y in pts]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", help="nom de la photo sans extension")
    ap.add_argument("--input", default="gold/photos")
    ap.add_argument("--display", type=int, default=1400, help="largeur d'affichage en pixels")
    args = ap.parse_args(argv)
    path = next((ROOT / args.input).glob(f"{args.photo}.*"))
    img = cv2.imread(str(path))
    scale = args.display / img.shape[1]
    out = {}
    for side, label in (("left", "page gauche"), ("right", "page droite")):
        pts = pick(img, f"{args.photo} — {label}", scale)
        if pts is None:
            print("annulé")
            return
        out[side] = pts
    dest = ROOT / "data" / "corners" / f"{args.photo}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"→ {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
