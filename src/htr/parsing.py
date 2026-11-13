"""Lecture tolérante des sorties JSON des modèles."""
from __future__ import annotations

import json
import re

from .schema import FIELD_KEYS


def parse_json(text: str) -> tuple[object | None, bool]:
    """Renvoie (objet, valide). `valide` est faux si une réparation a été nécessaire ou a échoué."""
    try:
        return json.loads(text), True
    except json.JSONDecodeError:
        pass
    # Bloc ```json … ``` ou texte autour
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    candidate = m.group(1) if m else text[text.find("{"):] if "{" in text else ""
    try:
        return json.loads(candidate), False
    except json.JSONDecodeError:
        pass
    # Sortie tronquée (num_predict atteint, boucle) : on garde les lignes complètes
    rows = []
    for m in re.finditer(r"\{[^{}]*\}", candidate):
        try:
            rows.append(json.loads(m.group(0)))
        except json.JSONDecodeError:
            continue
    return ({"lignes": rows} if rows else None), False


def normalize_row(obj: dict) -> dict:
    """Ne garde que les champs du schéma, en chaînes nettoyées."""
    out = {}
    for k in FIELD_KEYS:
        v = obj.get(k, "")
        if v is None:
            v = ""
        if not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)
        out[k] = " ".join(v.split())
    return out


def extract_rows(obj: object) -> list[dict]:
    if isinstance(obj, dict):
        for key in ("lignes", "rows", "patients"):
            if isinstance(obj.get(key), list):
                return [normalize_row(r) for r in obj[key] if isinstance(r, dict)]
        if any(k in obj for k in FIELD_KEYS):
            return [normalize_row(obj)]
    if isinstance(obj, list):
        return [normalize_row(r) for r in obj if isinstance(r, dict)]
    return []
