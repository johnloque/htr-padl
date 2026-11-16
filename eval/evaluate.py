"""Banc d'évaluation commun : compare les sorties de transcripts/<strategie>/<modele>/ au gold.

    uv run python -m eval.evaluate                      # toutes les sorties présentes
    uv run python -m eval.evaluate --only N0/qwen3-vl-8b

Produit dans results/ :
- metrics.csv  : une ligne par stratégie × modèle × colonne
- summary.csv  : une ligne par stratégie × modèle (validité JSON, lignes, temps, mémoire, seuils)
- errors.csv   : une ligne par cellule erronée (gold, prédiction, image source)
- summary.md   : tableaux de synthèse
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rapidfuzz.distance import Levenshtein

from htr.schema import CLOSED, DATE, FIELDS, LONG, NUMERIC, PHOTO_COL, SHORT, BY_KEY

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROWS = 5000

# Seuils provisoires (README §5)
EXACT_THRESHOLD = 0.95  # champs fermés, numériques, dates
CER_THRESHOLD = 0.05  # noms, prénoms, lieux
CER_FIELDS = ["nom", "prenoms", "lieu_naissance", "departement_naissance"]

# ---------------------------------------------------------------- normalisation

_APOS = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'", " ": " "})


def strict(s: str) -> str:
    return " ".join((s or "").translate(_APOS).split())


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tolerant(s: str) -> str:
    """Minuscules, accents retirés, ponctuation neutralisée (« A.M.G. » == « AMG »)."""
    s = strip_accents(strict(s).lower()).replace(".", "")
    s = re.sub(r"[^\w]+", " ", s)
    # sigles écrits lettre par lettre : « A. M. G. » -> « amg »
    s = re.sub(r"\b(?:[a-z] ){2,}[a-z]\b", lambda m: m.group(0).replace(" ", ""), s)
    return " ".join(s.split())


_ETAT_CIVIL = {"celibataire": "c", "marie": "m", "veuf": "v", "divorce": "d", "div": "d"}


def canonical(key: str, s: str) -> str:
    t = tolerant(s)
    if key == "etat_civil":
        return _ETAT_CIVIL.get(t, t)
    if BY_KEY[key].kind == NUMERIC:
        return re.sub(r"\D", "", t)
    return t


_MONTHS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7,
           "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
_DATE_RE = re.compile(r"(\d{1,2})\s*(?:er)?\s*[/\-. ]\s*([a-z]+|\d{1,2})\s*[/\-. ]\s*(\d{2,4})")


def parse_date(s: str) -> tuple[int, int, int] | None:
    """(jour, mois, année) ; l'année est gardée telle qu'écrite (2 ou 4 chiffres)."""
    m = _DATE_RE.search(strip_accents((s or "").lower()))
    if not m:
        return None
    d, mo, y = m.groups()
    mo = int(mo) if mo.isdigit() else _MONTHS.get(mo)
    if not mo or not 1 <= mo <= 12 or not 1 <= int(d) <= 31:
        return None
    return int(d), mo, int(y)


def same_date(a: tuple | None, b: tuple | None) -> bool:
    if a is None or b is None:
        return False
    if a[:2] != b[:2]:
        return False
    ya, yb = a[2], b[2]
    if ya < 100 or yb < 100:  # année à deux chiffres d'un côté : on compare les deux derniers chiffres
        return ya % 100 == yb % 100
    return ya == yb


def cell_correct(key: str, gold: str, pred: str) -> bool:
    if BY_KEY[key].kind == DATE and strict(gold):
        return same_date(parse_date(gold), parse_date(pred))
    return canonical(key, gold) == canonical(key, pred)


# ---------------------------------------------------------------- chargement

def _norm_header(h: str) -> str:
    return " ".join(h.translate(_APOS).split()).lower()


_GOLD2KEY = {_norm_header(f.gold): f.key for f in FIELDS}


def load_gold(gold_dir: Path) -> dict[str, list[dict]]:
    gold = {}
    for p in sorted(gold_dir.glob("*.csv")):
        with p.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            header = [_GOLD2KEY.get(_norm_header(h)) for h in next(reader)]
            rows = []
            for line in reader:
                if not any(c.strip() for c in line):
                    continue
                r = {k: strict(v) for k, v in zip(header, line) if k}
                rows.append({f.key: r.get(f.key, "") for f in FIELDS})
        gold[p.stem] = rows
    return gold


def load_pred(pred_dir: Path) -> dict[str, list[dict]]:
    preds = {}
    for p in sorted(pred_dir.glob("*.csv")):
        if p.name == "all.csv":
            continue
        with p.open(encoding="utf-8", newline="") as f:
            preds[p.stem] = [{k: strict(v or "") for k, v in r.items()} for r in csv.DictReader(f)]
    return preds


def align(gold_rows: list[dict], pred_rows: list[dict]) -> tuple[list[tuple[dict, dict | None]], int]:
    """Apparie par n° d'ordre, puis dans l'ordre pour les restes. Renvoie (paires, nb de lignes prédites en trop)."""
    num = lambda r: re.sub(r"\D", "", r.get("numero", "") or "")
    free = list(range(len(pred_rows)))
    by_num = {}
    for j in free:
        by_num.setdefault(num(pred_rows[j]), j)
    match: list[int | None] = []
    for g in gold_rows:
        j = by_num.get(num(g)) if num(g) else None
        if j is not None and j in free:
            free.remove(j)
            match.append(j)
        else:
            match.append(None)
    for i, j in enumerate(match):
        if j is None and free:
            match[i] = free.pop(0)
    pairs = [(g, pred_rows[j] if j is not None else None) for g, j in zip(gold_rows, match)]
    return pairs, len(free)


# ---------------------------------------------------------------- évaluation


@dataclass
class Acc:
    n: int = 0
    correct: int = 0
    dist_s: int = 0
    len_s: int = 0
    dist_t: int = 0
    len_t: int = 0
    gold_empty: int = 0
    invented: int = 0
    gold_full: int = 0
    omitted: int = 0
    flagged_err: int = 0
    flagged: int = 0
    errors: int = 0
    has_flags: bool = False


def evaluate_run(strategy: str, model: str, gold: dict, pred_dir: Path, photos_dir: Path):
    preds = load_pred(pred_dir)
    accs = {f.key: Acc() for f in FIELDS}
    errors = []
    rows_gold = rows_found = rows_extra = row_ok_struct = row_ok_all = 0
    for photo, grows in gold.items():
        prows = preds.get(photo, [])
        pairs, extra = align(grows, prows)
        rows_extra += extra
        for g, p in pairs:
            rows_gold += 1
            rows_found += p is not None
            p = p or {}
            ok_struct = ok_all = True
            for f in FIELDS:
                a = accs[f.key]
                gv, pv = g.get(f.key, ""), p.get(f.key, "")
                ok = cell_correct(f.key, gv, pv)
                a.n += 1
                a.correct += ok
                if strict(gv):
                    a.gold_full += 1
                    a.omitted += not strict(pv)
                    a.dist_s += Levenshtein.distance(strict(gv), strict(pv))
                    a.len_s += len(strict(gv))
                    a.dist_t += Levenshtein.distance(tolerant(gv), tolerant(pv))
                    a.len_t += len(tolerant(gv))
                else:
                    a.gold_empty += 1
                    a.invented += bool(strict(pv))
                flag_col = f"{f.key}_flag"
                if flag_col in p:
                    a.has_flags = True
                    flagged = bool(strict(p[flag_col]))
                    a.flagged += flagged
                    a.flagged_err += flagged and not ok
                if not ok:
                    a.errors += 1
                    ok_all = False
                    if f.kind in (NUMERIC, DATE, CLOSED):
                        ok_struct = False
                    cer = Levenshtein.normalized_distance(strict(gv), strict(pv)) if strict(gv) else 1.0
                    errors.append({"strategy": strategy, "model": model, "photo": photo,
                                   "numero": g.get("numero", ""), "field": f.key, "kind": f.kind,
                                   "gold": gv, "pred": pv, "cer": round(cer, 3),
                                   "row_missing": not p, "image": str(photos_dir / f"{photo}.jpg").removeprefix(f"{ROOT}/")})
            row_ok_struct += ok_struct
            row_ok_all += ok_all

    metrics = []
    for f in FIELDS:
        a = accs[f.key]
        metrics.append({
            "strategy": strategy, "model": model, "field": f.key, "kind": f.kind, "n": a.n,
            "exact": a.correct / a.n if a.n else None,
            "cer_strict": a.dist_s / a.len_s if a.len_s else None,
            "cer_tolerant": a.dist_t / a.len_t if a.len_t else None,
            "invention_rate": a.invented / a.gold_empty if a.gold_empty else None,
            "n_gold_empty": a.gold_empty,
            "omission_rate": a.omitted / a.gold_full if a.gold_full else None,
            "flag_precision": (a.flagged_err / a.flagged if a.flagged else None) if a.has_flags else None,
            "flag_recall": (a.flagged_err / a.errors if a.errors else None) if a.has_flags else None,
        })
    rows = {"rows_gold": rows_gold, "rows_found": rows_found, "rows_extra": rows_extra,
            "row_exact_structured": row_ok_struct / rows_gold if rows_gold else None,
            "row_exact_all": row_ok_all / rows_gold if rows_gold else None}
    return metrics, errors, rows


def run_stats(strategy: str, model: str, gold_photos: set[str]) -> dict:
    p = ROOT / "results" / "runs" / strategy / f"{model}.json"
    if not p.exists():
        return {}
    run = json.loads(p.read_text(encoding="utf-8"))
    ph = [r for r in run["photos"] if r["photo"] in gold_photos]
    if not ph:
        return {}
    timed = [r for r in ph if not r.get("cached")] or ph
    model_s = sum(r["model_s"] for r in timed)
    rows = sum(max(r["n_rows"], 1) for r in timed)
    # durée de génération rapportée par le backend : ignorée si plus longue que l'appel lui-même (valeur aberrante)
    gen_ok = [r for r in timed if r["gen_s"] <= r["model_s"]]
    out_tok = sum(r["output_tokens"] for r in gen_ok)
    gen_s = sum(r["gen_s"] for r in gen_ok)
    client = run.get("client", {})
    s_per_row = model_s / rows if rows else None
    return {
        "photos_run": len(ph),
        "json_valid_rate": sum(r["json_valid"] for r in ph) / len(ph),
        "errors_run": sum(bool(r.get("error")) for r in ph),
        "truncated": sum("length" in (r.get("done_reasons") or []) for r in ph),
        "s_per_photo": model_s / len(timed),
        "s_per_row": s_per_row,
        "tokens_per_s": out_tok / gen_s if gen_s else None,
        "peak_memory_gb": (run.get("peak_memory_bytes") or 0) / 1e9 or None,
        "hours_for_5000_rows": s_per_row * CORPUS_ROWS / 3600 if s_per_row else None,
        "model_id": client.get("model_id"),
        "quantization": (client.get("details") or {}).get("quantization_level"),
        "ollama_version": client.get("ollama_version"),
        "git_commit": run.get("git_commit"),
    }


def thresholds(metrics: list[dict]) -> dict:
    ex = [m for m in metrics if m["kind"] in (NUMERIC, DATE, CLOSED)]
    ex_fail = [m["field"] for m in ex if (m["exact"] or 0) < EXACT_THRESHOLD]
    cer_fail = [m["field"] for m in metrics if m["field"] in CER_FIELDS and (1 if m["cer_strict"] is None else m["cer_strict"]) > CER_THRESHOLD]
    return {"exact_fields_ok": not ex_fail, "exact_fields_failing": " ".join(ex_fail),
            "cer_fields_ok": not cer_fail, "cer_fields_failing": " ".join(cer_fail),
            "flags_ok": None}


def fmt(x, pct=True, nd=1):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "–"
    return f"{100 * x:.{nd}f}" if pct else f"{x:.{nd}f}"


def write_markdown(metrics: pd.DataFrame, summary: pd.DataFrame, path: Path):
    lines = ["# Synthèse de l'évaluation", "",
             f"Seuils provisoires : exactitude ≥ {EXACT_THRESHOLD:.0%} (champs fermés, numériques, dates) ; "
             f"CER ≤ {CER_THRESHOLD:.0%} ({', '.join(CER_FIELDS)}) ; ≥ 90 % des erreurs signalées.", "",
             "## Vue d'ensemble", "",
             "| Stratégie | Modèle | JSON valide % | Lignes trouvées | Lignes en trop | Ligne exacte (structurés) % | "
             "s/ligne | tok/s | Mémoire Go | h pour 5000 lignes | Seuils exactitude | Seuils CER |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in summary.iterrows():
        lines.append(
            f"| {r.strategy} | {r.model} | {fmt(r.get('json_valid_rate'))} | {r.rows_found}/{r.rows_gold} | {r.rows_extra} | "
            f"{fmt(r.row_exact_structured)} | {fmt(r.get('s_per_row'), False)} | "
            f"{fmt(r.get('tokens_per_s'), False)} | {fmt(r.get('peak_memory_gb'), False)} | "
            f"{fmt(r.get('hours_for_5000_rows'), False)} | {'✅' if r.exact_fields_ok else '❌'} | "
            f"{'✅' if r.cer_fields_ok else '❌'} |")
    for (strategy, model), g in metrics.groupby(["strategy", "model"], sort=False):
        lines += ["", f"## {strategy} — {model}", "",
                  "| Colonne | Type | Exact % | CER strict % | CER tolérant % | Invention % (n vides) | Omission % |",
                  "|---|---|---|---|---|---|---|"]
        for _, m in g.iterrows():
            lines.append(f"| {m.field} | {m.kind} | {fmt(m.exact)} | {fmt(m.cer_strict)} | {fmt(m.cer_tolerant)} | "
                         f"{fmt(m.invention_rate)} ({m.n_gold_empty}) | {fmt(m.omission_rate)} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", default="gold/transcripts")
    ap.add_argument("--photos", default="gold/photos")
    ap.add_argument("--transcripts", default="transcripts")
    ap.add_argument("--out", default="results")
    ap.add_argument("--only", nargs="*", help="stratégie/modèle à évaluer (ex. N0/qwen3-vl-8b)")
    args = ap.parse_args(argv)

    gold = load_gold(ROOT / args.gold)
    photos_dir = ROOT / args.photos
    runs = sorted(p for p in (ROOT / args.transcripts).glob("*/*") if p.is_dir())
    if args.only:
        runs = [p for p in runs if f"{p.parent.name}/{p.name}" in args.only]
    all_metrics, all_errors, summaries = [], [], []
    for run_dir in runs:
        strategy, model = run_dir.parent.name, run_dir.name
        metrics, errors, rows = evaluate_run(strategy, model, gold, run_dir, photos_dir)
        all_metrics += metrics
        all_errors += errors
        summaries.append({"strategy": strategy, "model": model, **rows,
                          **run_stats(strategy, model, set(gold)), **thresholds(metrics)})
        print(f"{strategy}/{model}: {rows['rows_found']}/{rows['rows_gold']} lignes, "
              f"{len(errors)} cellules erronées")

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    mdf, sdf = pd.DataFrame(all_metrics), pd.DataFrame(summaries)
    mdf.to_csv(out / "metrics.csv", index=False, float_format="%.4f")
    sdf.to_csv(out / "summary.csv", index=False, float_format="%.4f")
    pd.DataFrame(all_errors).to_csv(out / "errors.csv", index=False)
    if len(mdf):
        write_markdown(mdf, sdf, out / "summary.md")
    print(f"→ {out}/metrics.csv, summary.csv, errors.csv, summary.md")


if __name__ == "__main__":
    main()
