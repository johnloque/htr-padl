"""Lance une stratégie × modèle sur un dossier de photos.

    uv run python -m htr.run --strategy N0 --model qwen3-vl-8b [--input gold/photos] [--limit 2]

Sorties :
- transcripts/<strategie>/<modele>/<photo>.csv et all.csv
- results/runs/<strategie>/<modele>.json : config, versions, temps, tokens, mémoire, validité JSON par photo
- data/cache/<strategie>/<modele>.jsonl : réponses brutes (reprise après interruption)
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

import yaml

from .schema import PHOTO_COL, ROW_COLUMNS
from .strategies import STRATEGIES
from .vlm import make_client

ROOT = Path(__file__).resolve().parents[2]
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def load_config(strategy: str, model: str) -> dict:
    path = ROOT / "configs" / strategy / f"{model}.yaml"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["_path"] = str(path.relative_to(ROOT))
    if cfg.get("prompt_file"):
        cfg["prompt_file"] = str(ROOT / cfg["prompt_file"])
    return cfg


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True, text=True)
        return out.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except OSError:
        return None


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ROW_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def photo_sort_key(p: Path):
    import re
    nums = [int(n) for n in re.findall(r"\d+", p.stem)]
    return (nums, p.stem)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategy", required=True, choices=sorted(STRATEGIES))
    ap.add_argument("--model", required=True, help="nom du fichier configs/<strategie>/<modele>.yaml")
    ap.add_argument("--input", default="gold/photos")
    ap.add_argument("--limit", type=int, default=None, help="ne traiter que les N premières photos")
    ap.add_argument("--keep-loaded", action="store_true", help="ne pas décharger le modèle à la fin")
    args = ap.parse_args(argv)

    cfg = load_config(args.strategy, args.model)
    model_slug = cfg["model"]["name"]
    seed = cfg["inference"].get("seed", 0)
    random.seed(seed)

    # des variantes qui partagent la plupart de leurs appels peuvent partager un cache (`model.cache`)
    cache = ROOT / "data" / "cache" / args.strategy / f"{cfg['model'].get('cache', model_slug)}.jsonl"
    client = make_client(cfg["model"], cfg["inference"], cache)
    strategy = STRATEGIES[args.strategy](cfg, client)

    photos = sorted((p for p in (ROOT / args.input).iterdir() if p.suffix.lower() in PHOTO_EXT), key=photo_sort_key)
    if args.limit:
        photos = photos[: args.limit]

    out_dir = ROOT / "transcripts" / args.strategy / model_slug
    run_path = ROOT / "results" / "runs" / args.strategy / f"{model_slug}.json"
    client.unload_others()
    info = client.info()
    run = {
        "strategy": args.strategy, "model": model_slug, "config": cfg, "client": info,
        "git_commit": git_commit(), "python": sys.version.split()[0], "platform": platform.platform(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "input": args.input, "photos": [],
    }
    all_rows, peak_mem = [], 0
    for i, photo in enumerate(photos, 1):
        t0 = time.perf_counter()
        try:
            res = strategy.transcribe(photo)
            error = None
        except Exception as e:  # on note l'échec et on continue : il apparaîtra dans l'évaluation
            res, error = None, f"{type(e).__name__}: {e}"
        wall = time.perf_counter() - t0
        rows = [] if res is None else [{PHOTO_COL: photo.stem, **r} for r in res.rows]
        write_csv(out_dir / f"{photo.stem}.csv", rows)
        all_rows += rows
        mem = client.memory_bytes() or 0
        peak_mem = max(peak_mem, mem)
        calls = res.calls if res else []
        rec = {
            "photo": photo.stem, "n_rows": len(rows), "json_valid": bool(res and res.json_valid),
            "error": error, "wall_s": round(wall, 2), "cached": all(c.cached for c in calls) if calls else False,
            "calls": len(calls),
            "model_s": round(sum(c.wall_s for c in calls), 2),
            "prompt_tokens": sum(c.prompt_tokens or 0 for c in calls),
            "output_tokens": sum(c.output_tokens or 0 for c in calls),
            "gen_s": round(sum(c.gen_s or 0 for c in calls), 2),
            "done_reasons": [c.done_reason for c in calls],
            "warnings": res.warnings if res else [],
            "memory_bytes": mem or None,
        }
        run["photos"].append(rec)
        tps = rec["output_tokens"] / rec["gen_s"] if rec["gen_s"] else 0
        print(f"[{i}/{len(photos)}] {photo.stem}: {len(rows)} lignes, json={'ok' if rec['json_valid'] else 'KO'}, "
              f"{rec['model_s']:.0f}s, {rec['output_tokens']} tok ({tps:.1f} tok/s)"
              f"{' [cache]' if rec['cached'] else ''}{' ERREUR ' + error if error else ''}", flush=True)
        run["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        run["peak_memory_bytes"] = peak_mem or None
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

    write_csv(out_dir / "all.csv", all_rows)
    if not args.keep_loaded:
        client.unload()
    print(f"→ {out_dir.relative_to(ROOT)} ; {run_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
