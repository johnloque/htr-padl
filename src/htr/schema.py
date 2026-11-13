"""Schéma de sortie commun à toutes les stratégies.

Chaque champ a une clé JSON (utilisée par les modèles et dans les CSV de sortie),
l'intitulé de la colonne correspondante dans le gold, et un type qui détermine
les métriques appliquées par l'évaluateur.
"""
from __future__ import annotations

from dataclasses import dataclass

# Types de champs (cf. README §3 N2 et §4 Métriques)
NUMERIC = "numerique"
DATE = "date"
CLOSED = "ferme"
SHORT = "texte_court"
LONG = "texte_long"


@dataclass(frozen=True)
class Field:
    key: str
    gold: str
    kind: str
    description: str


FIELDS: list[Field] = [
    Field("numero", "Numéro", NUMERIC, "N° d'ordre (chiffres uniquement)"),
    Field("nom", "Nom", SHORT, "Nom de famille (écrit en grand, première ligne de la case « Noms et prénoms »)"),
    Field("prenoms", "Prénoms", SHORT, "Prénoms (écrits en petit sous le nom)"),
    Field("profession", "Profession", SHORT, "Profession"),
    Field("date_naissance", "Date de naissance", DATE, "Date de naissance, au format JJ/MM/AAAA"),
    Field("lieu_naissance", "Lieu de naissance", SHORT, "Commune de naissance (2e ligne de la case « Date et lieu de naissance »)"),
    Field("departement_naissance", "Département de naissance", SHORT,
          "Département de naissance (3e ligne) ; vide si la naissance est à l'étranger"),
    Field("pays", "Pays", CLOSED, "Pays de naissance : « France » si un département français est indiqué, sinon le pays écrit"),
    Field("etat_civil", "Marié ou célib", CLOSED, "État civil : C (célibataire), M (marié), V (veuf) ou D (divorcé)"),
    Field("admis_au_titre_de", "Admis au titre de", CLOSED, "Organisme payeur (« Admis au titre de »), département compris"),
    Field("venant_de", "Venant de", SHORT, "Provenance du malade (« Venant de »)"),
    Field("religion", "Religion", CLOSED, "Religion"),
    Field("adresse", "Adresse", LONG,
          "Adresse du malade ou de sa famille, sur une seule ligne : lignes séparées par des virgules"),
    Field("categorie_medicale", "Catégorie médicale", CLOSED,
          "Catégorie médicale : le symbole, transcrit par la lettre majuscule qui lui ressemble le plus"),
    Field("date_entree", "Date d’entrée", DATE, "Date d'entrée, au format JJ/MM/AA (année telle qu'écrite)"),
    Field("date_sortie", "Date de sortie", DATE, "Date de sortie, au format JJ/MM/AA (année telle qu'écrite)"),
    Field("nb_journees", "Nb de journées", NUMERIC, "Nombre de journées (chiffres uniquement)"),
    Field("observations", "Commentaires", LONG, "Observations du médecin-directeur (écriture cursive, encre bleue)"),
]

FIELD_KEYS = [f.key for f in FIELDS]
BY_KEY = {f.key: f for f in FIELDS}
PHOTO_COL = "photo"
ROW_COLUMNS = [PHOTO_COL, *FIELD_KEYS]


def row_json_schema(keys: list[str] | None = None) -> dict:
    """Schéma JSON d'une ligne (tous les champs sont des chaînes, vides si case vide)."""
    keys = keys or FIELD_KEYS
    return {
        "type": "object",
        "properties": {k: {"type": "string"} for k in keys},
        "required": list(keys),
    }


def page_json_schema(keys: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": {"lignes": {"type": "array", "items": row_json_schema(keys)}},
        "required": ["lignes"],
    }


def fields_description(keys: list[str] | None = None) -> str:
    keys = keys or FIELD_KEYS
    return "\n".join(f"- `{k}` : {BY_KEY[k].description}" for k in keys)
